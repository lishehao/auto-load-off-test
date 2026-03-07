from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

from app.application.dto import SaveTarget, StartSweepCommand
from app.application.events import SweepFailed
from app.application.use_cases.save_measurement import SaveMeasurementUseCase
from app.application.use_cases.start_sweep import StartSweepUseCase
from app.application.use_cases.stop_sweep import StopSweepUseCase
from app.domain.models import AppSettings, InstrumentSetup, SweepResult
from app.infrastructure.instruments.equips_factory import InstrumentPorts, create_instrument_ports


class SweepTaskRunner:
    def __init__(
        self,
        *,
        emitter,
        save_measurement_use_case: SaveMeasurementUseCase,
        root_dir: Path,
        ports_factory: Callable[[InstrumentSetup], InstrumentPorts] = create_instrument_ports,
        use_case_factory: Callable[..., StartSweepUseCase] = StartSweepUseCase,
    ) -> None:
        self._emitter = emitter
        self._save_measurement_use_case = save_measurement_use_case
        self._root_dir = root_dir
        self._ports_factory = ports_factory
        self._use_case_factory = use_case_factory

        self._ports: InstrumentPorts | None = None
        self._sweep_thread: threading.Thread | None = None
        self._stop_use_case: StopSweepUseCase | None = None

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

        ports = self._ports_factory(settings.setup)
        stop_event = threading.Event()
        self._stop_use_case = StopSweepUseCase(stop_event=stop_event)

        cmd = StartSweepCommand(
            settings=settings,
            calibration_enabled=calibration_enabled,
            reference_interpolator=reference_interpolator,
        )
        start_use_case = self._use_case_factory(awg=ports.awg, osc=ports.osc, stop_event=stop_event)

        self._ports = ports
        self._sweep_thread = threading.Thread(target=self._run_sweep, args=(start_use_case, cmd), daemon=True)
        self._sweep_thread.start()

    def stop(self) -> None:
        if self._stop_use_case is not None:
            self._stop_use_case.stop()

    def wait(self, timeout: float | None = None) -> None:
        if self._sweep_thread is not None:
            self._sweep_thread.join(timeout=timeout)

    def shutdown(self) -> None:
        self.stop()
        self._close_ports()

    def _run_sweep(self, start_use_case: StartSweepUseCase, cmd: StartSweepCommand) -> None:
        try:
            result = start_use_case.run(cmd, self._emitter)
            if not result.is_empty and cmd.settings.auto_save_data:
                target = SaveTarget(
                    base_path=self._root_dir / "__data__" / "measurement",
                    include_timestamp=True,
                    figures={},
                )
                self._save_measurement_use_case.execute(result=result, settings=cmd.settings, target=target)
        except Exception as exc:  # noqa: BLE001
            self._emitter.emit(SweepFailed(error_code="SWEEP_THREAD", message=str(exc)))
        finally:
            self._close_ports()

    def _close_ports(self) -> None:
        if self._ports is None:
            return

        try:
            self._ports.awg.close()
        except Exception:
            pass

        try:
            self._ports.osc.close()
        except Exception:
            pass

        self._ports = None
