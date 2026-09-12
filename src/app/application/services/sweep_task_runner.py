from __future__ import annotations

import threading
from collections.abc import Callable
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from app.application.dto import SaveTarget, StartSweepCommand
from app.application.errors import describe_exception
from app.application.events import EventEmitter, SweepAutoSaved, SweepFailed, SweepWarning, SweepWorkerFinished
from app.application.ports.instruments import InstrumentPorts, InstrumentPortsFactory
from app.application.use_cases.save_measurement import SaveMeasurementUseCase
from app.application.use_cases.start_sweep import StartSweepUseCase
from app.application.use_cases.stop_sweep import StopSweepUseCase
from app.domain.models import AppSettings, SweepResult
from app.domain.validators import validate_settings


class SweepTaskRunner:
    def __init__(
        self,
        *,
        emitter: EventEmitter,
        save_measurement_use_case: SaveMeasurementUseCase,
        auto_save_dir: Path,
        ports_factory: InstrumentPortsFactory,
        use_case_factory: Callable[..., StartSweepUseCase] = StartSweepUseCase,
    ) -> None:
        self._emitter = emitter
        self._save_measurement_use_case = save_measurement_use_case
        self._auto_save_dir = auto_save_dir
        self._ports_factory = ports_factory
        self._use_case_factory = use_case_factory

        self._ports: InstrumentPorts | None = None
        self._ports_lock = threading.Lock()
        self._cleanup_lock = threading.Lock()
        self._sweep_thread: threading.Thread | None = None
        self._stop_use_case: StopSweepUseCase | None = None
        self._active_awg_channel: int | None = None

    def is_running(self) -> bool:
        return self._sweep_thread is not None and self._sweep_thread.is_alive()

    def start(
        self,
        *,
        settings: AppSettings,
        calibration_enabled: bool,
        reference_interpolator: object | None,
        cancellation_event: threading.Event | None = None,
    ) -> None:
        if self.is_running():
            return

        self._stop_use_case = None
        self._sweep_thread = None
        # Validate and freeze the caller's settings before constructing any
        # instrument resources or starting the worker thread.
        frozen_settings = deepcopy(settings)
        validate_settings(frozen_settings)

        awg_channel = frozen_settings.setup.channels.awg_ch
        stop_event = cancellation_event if cancellation_event is not None else threading.Event()
        self._stop_use_case = StopSweepUseCase(stop_event=stop_event)
        ports: InstrumentPorts | None = None
        try:
            if stop_event.is_set():
                raise InterruptedError("Start cancelled before instrument connection")
            ports = self._ports_factory(frozen_settings.setup)

            cmd = StartSweepCommand(
                settings=frozen_settings,
                calibration_enabled=calibration_enabled,
                reference_interpolator=reference_interpolator,
            )
            start_use_case = self._use_case_factory(awg=ports.awg, osc=ports.osc, stop_event=stop_event)

            thread = threading.Thread(target=self._run_sweep, args=(start_use_case, cmd), daemon=True)
            with self._ports_lock:
                self._ports = ports
                self._active_awg_channel = awg_channel
                self._sweep_thread = thread
            thread.start()
        except Exception:
            if ports is not None:
                with self._ports_lock:
                    if self._ports is ports:
                        self._ports = None
                        self._active_awg_channel = None
                self._close_port_set(ports=ports, awg_channel=awg_channel)
            self._stop_use_case = None
            self._sweep_thread = None
            raise

    def stop(self) -> None:
        if self._stop_use_case is not None:
            self._stop_use_case.stop()

    def wait(self, timeout: float | None = None) -> None:
        if self._sweep_thread is not None:
            self._sweep_thread.join(timeout=timeout)

    def shutdown(self, timeout: float = 2.0) -> None:
        self.stop()
        self.wait(timeout=timeout)
        if self.is_running():
            self._emit_warning(
                code="SHUTDOWN_TIMEOUT",
                message=(
                    "Sweep worker did not stop before shutdown timeout; forcing AWG output off "
                    "and closing ports during shutdown."
                ),
            )
            self._close_ports()
            return
        self._close_ports()

    def _run_sweep(self, start_use_case: StartSweepUseCase, cmd: StartSweepCommand) -> None:
        result: SweepResult
        try:
            result = start_use_case.run(cmd, self._emitter)
        except Exception as exc:  # noqa: BLE001
            message = describe_exception(exc)
            result = SweepResult(
                meta={
                    "run_status": "failed",
                    "termination_reason": "worker_error",
                    "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "planned_points": 0,
                    "completed_points": 0,
                    "error_code": "SWEEP_THREAD",
                    "error_message": message,
                    "error_stage": "worker",
                }
            )
            self._emitter.emit(
                SweepFailed(error_code="SWEEP_THREAD", message=message, result=result.snapshot())
            )
        finally:
            # Instrument shutdown must happen before persistence, even when
            # saving fails or the sweep ended with a partial result.
            self._close_ports()
            self._auto_save_if_requested(result=result, cmd=cmd)
            self._emitter.emit(SweepWorkerFinished(result=result.snapshot()))

    def _auto_save_if_requested(self, *, result, cmd: StartSweepCommand) -> None:
        if result.is_empty or not cmd.settings.auto_save_data:
            return

        target = SaveTarget(
            base_path=self._auto_save_dir / "measurement",
            include_timestamp=True,
            figures={},
        )
        try:
            artifacts = self._save_measurement_use_case.execute(
                result=result, settings=cmd.settings, target=target
            )
            self._emitter.emit(
                SweepAutoSaved(
                    artifacts=artifacts,
                    result=result.snapshot(),
                    settings=cmd.settings,
                )
            )
        except Exception as exc:  # noqa: BLE001
            self._emit_warning(code="AUTO_SAVE_FAILED", message=describe_exception(exc))

    def _close_ports(self) -> None:
        # A timeout cleanup may already own the ports. The worker must wait
        # for that cleanup to finish before publishing its save/finished events.
        with self._cleanup_lock:
            with self._ports_lock:
                ports = self._ports
                awg_channel = self._active_awg_channel
                self._ports = None
                self._active_awg_channel = None

            if ports is not None:
                self._close_port_set(ports=ports, awg_channel=awg_channel)

    def _close_port_set(self, *, ports: InstrumentPorts, awg_channel: int | None) -> None:
        if awg_channel is not None:
            try:
                ports.awg.output_off(awg_channel)
            except Exception as exc:  # noqa: BLE001
                self._emit_warning(code="AWG_OUTPUT_OFF_FAILED", message=describe_exception(exc))

        try:
            ports.awg.close()
        except Exception as exc:  # noqa: BLE001
            self._emit_warning(code="AWG_CLOSE_FAILED", message=describe_exception(exc))

        try:
            ports.osc.close()
        except Exception as exc:  # noqa: BLE001
            self._emit_warning(code="OSC_CLOSE_FAILED", message=describe_exception(exc))

    def _emit_warning(self, *, code: str, message: str) -> None:
        self._emitter.emit(SweepWarning(code=code, message=message))
