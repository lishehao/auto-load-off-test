from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

from app.application.dto import SaveTarget, StartSweepCommand
from app.application.errors import describe_exception
from app.application.events import EventEmitter, SweepFailed, SweepWarning
from app.application.ports.instruments import InstrumentPorts, InstrumentPortsFactory
from app.application.use_cases.save_measurement import SaveMeasurementUseCase
from app.application.use_cases.start_sweep import StartSweepUseCase
from app.application.use_cases.stop_sweep import StopSweepUseCase
from app.domain.models import AppSettings


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
    ) -> None:
        if self.is_running():
            return

        awg_channel = settings.setup.channels.awg_ch
        ports: InstrumentPorts | None = None
        try:
            ports = self._ports_factory(settings.setup)
            stop_event = threading.Event()
            self._stop_use_case = StopSweepUseCase(stop_event=stop_event)

            cmd = StartSweepCommand(
                settings=settings,
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
        try:
            result = start_use_case.run(cmd, self._emitter)
        except Exception as exc:  # noqa: BLE001
            self._emitter.emit(SweepFailed(error_code="SWEEP_THREAD", message=describe_exception(exc)))
        else:
            self._auto_save_if_requested(result=result, cmd=cmd)
        finally:
            self._close_ports()

    def _auto_save_if_requested(self, *, result, cmd: StartSweepCommand) -> None:
        if result.is_empty or not cmd.settings.auto_save_data:
            return

        target = SaveTarget(
            base_path=self._auto_save_dir / "measurement",
            include_timestamp=True,
            figures={},
        )
        try:
            self._save_measurement_use_case.execute(result=result, settings=cmd.settings, target=target)
        except Exception as exc:  # noqa: BLE001
            self._emit_warning(code="AUTO_SAVE_FAILED", message=describe_exception(exc))

    def _close_ports(self) -> None:
        with self._ports_lock:
            ports = self._ports
            awg_channel = self._active_awg_channel
            self._ports = None
            self._active_awg_channel = None

        if ports is None:
            return

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
