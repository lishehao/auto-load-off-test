from __future__ import annotations

import threading
import time
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
        try:
            validate_settings(cmd.settings)
            result = SweepResult(
                meta={
                    "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "freq_unit": cmd.settings.freq_unit,
                    "schema_version": cmd.settings.schema_version,
                }
            )

            settings = cmd.settings
            plan = self._planner.plan(settings)
            emitter.emit(SweepStarted(total_points=plan.total_points))

            self._configurator.configure(settings)
            emitter.emit(SweepWarning(code="READY", message="Instruments configured"))

            for index, target_freq in enumerate(plan.freq_points, start=1):
                if self._stop_event.is_set():
                    result.meta["stopped_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                    emitter.emit(SweepStopped(result=result))
                    return result

                acquired = self._acquirer.acquire(target_freq_hz=float(target_freq), settings=settings)
                for warning in acquired.warnings:
                    emitter.emit(SweepWarning(code=warning.code, message=warning.message))

                point = self._measurement_service.measure(settings=settings, acquired=acquired)
                point = self._calibration_applier.apply(point=point, cmd=cmd)

                result.append(point)

                emitter.emit(SweepProgress(freq_hz=point.freq_hz, point_index=index, total_points=plan.total_points))
                emitter.emit(SweepDataUpdated(last_point=point, partial_result=result))

                time.sleep(0.001)

            result.meta["completed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            emitter.emit(SweepCompleted(result=result))
            return result

        except ValidationError as exc:
            emitter.emit(SweepFailed(error_code="VALIDATION", message=describe_exception(exc)))
            return SweepResult()
        except Exception as exc:  # noqa: BLE001
            emitter.emit(SweepFailed(error_code="SWEEP_RUNTIME", message=describe_exception(exc)))
            return SweepResult()
