from __future__ import annotations

import threading
import time
from copy import deepcopy
from datetime import datetime, timezone

from app.application.dto import StartSweepCommand
from app.application.errors import describe_exception
from app.application.events import (
    EventEmitter,
    SweepCompleted,
    SweepFailed,
    SweepDataUpdated,
    SweepProgress,
    SweepStarted,
    SweepStopped,
    SweepWarning,
)
from app.application.ports.instruments import AwgPort, OscPort
from app.application.services.sweep import (
    CalibrationApplier,
    InstrumentConfigurator,
    PointMeasurementService,
    SweepPlanner,
    WaveformAcquirer,
)
from app.domain.auto_range import AutoRangePolicy
from app.domain.data_validation import DataValidationError, validate_sweep_result
from app.domain.models import SweepResult
from app.domain.validators import ValidationError, validate_settings


class StartSweepUseCase:
    def __init__(
        self,
        awg: AwgPort,
        osc: OscPort,
        stop_event: threading.Event,
        *,
        planner: SweepPlanner | None = None,
        configurator: InstrumentConfigurator | None = None,
        acquirer: WaveformAcquirer | None = None,
        measurement_service: PointMeasurementService | None = None,
        calibration_applier: CalibrationApplier | None = None,
    ) -> None:
        self._awg = awg
        self._osc = osc
        self._stop_event = stop_event
        self._planner = planner or SweepPlanner()
        self._configurator = configurator or InstrumentConfigurator(awg=awg, osc=osc)
        self._acquirer = acquirer or WaveformAcquirer(
            awg=awg,
            osc=osc,
            planner=self._planner,
            auto_range_policy=AutoRangePolicy(),
        )
        self._measurement_service = measurement_service or PointMeasurementService()
        self._calibration_applier = calibration_applier or CalibrationApplier()

    def run(self, cmd: StartSweepCommand, emitter: EventEmitter) -> SweepResult:
        result = SweepResult(
            meta={
                "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "freq_unit": cmd.settings.freq_unit,
                "schema_version": cmd.settings.schema_version,
                "planned_points": 0,
                "completed_points": 0,
            }
        )
        stage = "validation"
        point_index: int | None = None
        point_freq: float | None = None
        try:
            validate_settings(cmd.settings)

            settings = cmd.settings
            stage = "planning"
            plan = self._planner.plan(settings)
            result.meta["planned_points"] = plan.total_points
            emitter.emit(SweepStarted(total_points=plan.total_points))

            if self._stop_event.is_set():
                return self._stopped(result=result, emitter=emitter)

            stage = "configure"
            self._configurator.configure(settings)
            emitter.emit(SweepWarning(code="READY", message="Instruments configured"))

            for index, target_freq in enumerate(plan.freq_points, start=1):
                point_index = index
                point_freq = float(target_freq)
                if self._stop_event.is_set():
                    return self._stopped(result=result, emitter=emitter)

                stage = "acquire"
                acquired = self._acquirer.acquire(target_freq_hz=point_freq, settings=settings)
                stage = "publish"
                for warning in acquired.warnings:
                    emitter.emit(SweepWarning(code=warning.code, message=warning.message))

                stage = "measure"
                point = self._measurement_service.measure(settings=settings, acquired=acquired)
                stage = "calibrate"
                point = self._calibration_applier.apply(point=point, cmd=cmd)

                stage = "point_validation"
                validate_sweep_result(SweepResult(points=[point]))
                if result.points and point.freq_hz <= result.points[-1].freq_hz:
                    raise DataValidationError("Measured frequencies must remain strictly increasing")
                result.append(point)
                result.meta["completed_points"] = len(result.points)

                stage = "publish"
                emitter.emit(SweepProgress(freq_hz=point.freq_hz, point_index=index, total_points=plan.total_points))
                emitter.emit(SweepDataUpdated(last_point=deepcopy(point), partial_result=result.snapshot()))

                # Keep the completed point when stop arrives during its acquisition.
                if self._stop_event.is_set():
                    return self._stopped(result=result, emitter=emitter)

                time.sleep(0.001)

            if self._stop_event.is_set():
                return self._stopped(result=result, emitter=emitter)
            self._mark_terminal(result=result, status="completed", reason="completed")
            emitter.emit(SweepCompleted(result=result.snapshot()))
            return result

        except ValidationError as exc:
            message = describe_exception(exc)
            self._mark_failed(
                result=result,
                error_code="VALIDATION",
                message=message,
                stage=stage,
                point_index=point_index,
                point_freq=point_freq,
            )
            emitter.emit(SweepFailed(error_code="VALIDATION", message=message, result=result.snapshot()))
            return result
        except Exception as exc:  # noqa: BLE001
            message = describe_exception(exc)
            self._mark_failed(
                result=result,
                error_code="SWEEP_RUNTIME",
                message=message,
                stage=stage,
                point_index=point_index,
                point_freq=point_freq,
            )
            emitter.emit(SweepFailed(error_code="SWEEP_RUNTIME", message=message, result=result.snapshot()))
            return result

    def _stopped(self, *, result: SweepResult, emitter: EventEmitter) -> SweepResult:
        self._mark_terminal(result=result, status="stopped", reason="stop_requested")
        emitter.emit(SweepStopped(result=result.snapshot()))
        return result

    @staticmethod
    def _mark_terminal(*, result: SweepResult, status: str, reason: str) -> None:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        result.meta["run_status"] = status
        result.meta["termination_reason"] = reason
        result.meta["finished_at"] = now
        result.meta["completed_points"] = len(result.points)
        if status == "completed":
            result.meta["completed_at"] = now
        elif status == "stopped":
            result.meta["stopped_at"] = now

    @classmethod
    def _mark_failed(
        cls,
        *,
        result: SweepResult,
        error_code: str,
        message: str,
        stage: str,
        point_index: int | None,
        point_freq: float | None,
    ) -> None:
        cls._mark_terminal(result=result, status="failed", reason=f"{stage}_error")
        result.meta["error_code"] = error_code
        result.meta["error_message"] = message
        result.meta["error_stage"] = stage
        if point_index is not None:
            result.meta["error_point_index"] = point_index
        if point_freq is not None:
            result.meta["error_freq_hz"] = point_freq
