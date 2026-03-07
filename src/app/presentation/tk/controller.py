from __future__ import annotations

import queue
from pathlib import Path

from app.application.events import EventEmitter
from app.application.services.connection_monitor import ConnectionMonitor
from app.application.use_cases.load_measurement import LoadMeasurementUseCase
from app.application.use_cases.load_reference import LoadReferenceUseCase
from app.application.use_cases.save_measurement import SaveMeasurementUseCase
from app.application.use_cases.settings_use_case import SettingsUseCase
from app.application.ports.instruments import ResourceScannerPort
from app.presentation.tk import dialogs
from app.presentation.tk.app_window import AppWindow
from app.presentation.tk.mapper import settings_to_vm, vm_to_settings
from app.presentation.tk.sweep_task_runner import SweepTaskRunner
from app.presentation.tk.ui_event_handler import UiEventHandler
from app.presentation.tk.view_model import ViewModel
from app.infrastructure.instruments.equips_factory import resolve_visa_address


class TkController(EventEmitter):
    def __init__(
        self,
        *,
        window: AppWindow,
        vm: ViewModel,
        settings_use_case: SettingsUseCase,
        save_measurement_use_case: SaveMeasurementUseCase,
        load_measurement_use_case: LoadMeasurementUseCase,
        load_reference_use_case: LoadReferenceUseCase,
        scanner: ResourceScannerPort,
    ) -> None:
        self.window = window
        self.vm = vm
        self.settings_use_case = settings_use_case
        self.save_measurement_use_case = save_measurement_use_case
        self.load_measurement_use_case = load_measurement_use_case
        self.load_reference_use_case = load_reference_use_case

        self._event_queue: queue.Queue[object] = queue.Queue()
        self._reference_interpolator = None
        self._root_dir = Path(__file__).resolve().parents[4]

        self._ui_handler = UiEventHandler(window=window, vm=vm)
        self._task_runner = SweepTaskRunner(
            emitter=self,
            save_measurement_use_case=save_measurement_use_case,
            root_dir=self._root_dir,
        )
        self._monitor = ConnectionMonitor(
            scanner=scanner,
            get_awg_address=self._get_awg_target_address,
            get_osc_address=self._get_osc_target_address,
            emitter=self,
        )

    def initialize(self) -> None:
        self.window.bind_actions(
            on_start=self.on_start,
            on_stop=self.on_stop,
            on_save_data=self.on_save_data,
            on_load_data=self.on_load_data,
            on_load_ref=self.on_load_reference,
            on_save_settings=self.on_save_settings,
            on_load_settings=self.on_load_settings,
            on_close=self.on_close,
            on_figure_change=self.on_figure_change,
            on_mag_phase_change=self.on_mag_phase_change,
        )

        try:
            settings = self.settings_use_case.load()
            settings_to_vm(settings, self.vm)
        except Exception as exc:  # noqa: BLE001
            dialogs.show_warning(self.window, f"Failed to load settings: {exc}")

        self._monitor.start()
        self.window.after(100, self._process_events)
        self.on_figure_change()
        self.on_mag_phase_change()

    def emit(self, event: object) -> None:
        self._event_queue.put(event)

    def on_start(self) -> None:
        if self._task_runner.is_running():
            return

        try:
            settings = vm_to_settings(self.vm)
            self._task_runner.start(
                settings=settings,
                calibration_enabled=bool(self.vm.calibration_enabled.get()),
                reference_interpolator=self._reference_interpolator,
            )
            self._ui_handler.prepare_for_sweep_start()
        except Exception as exc:  # noqa: BLE001
            dialogs.show_warning(self.window, f"Invalid settings: {exc}")

    def on_stop(self) -> None:
        self._task_runner.stop()

    def on_save_settings(self) -> None:
        try:
            settings = vm_to_settings(self.vm)
            self.settings_use_case.save(settings)
            dialogs.show_info(self.window, "Settings saved")
        except Exception as exc:  # noqa: BLE001
            dialogs.show_warning(self.window, f"Failed to save settings: {exc}")

    def on_load_settings(self) -> None:
        try:
            settings = self.settings_use_case.load()
            settings_to_vm(settings, self.vm)
            self.on_figure_change()
            self.on_mag_phase_change()
            dialogs.show_info(self.window, "Settings loaded")
        except Exception as exc:  # noqa: BLE001
            dialogs.show_warning(self.window, f"Failed to load settings: {exc}")

    def on_save_data(self) -> None:
        if self._ui_handler.latest_result.is_empty:
            dialogs.show_warning(self.window, "No measurement data available")
            return

        fp = dialogs.ask_save_file(
            title="Save measurement",
            initial_dir=self._root_dir / "__data__",
            initial_name="measurement",
            filetypes=[("MAT files", "*.mat"), ("All files", "*.*")],
        )
        if fp is None:
            return

        try:
            settings = vm_to_settings(self.vm)
            artifacts = self.save_measurement_use_case.execute(
                result=self._ui_handler.latest_result,
                settings=settings,
                target=dialogs_to_target(fp, self.window),
            )
            dialogs.show_info(self.window, f"Saved: {artifacts.mat_path.name}")
        except Exception as exc:  # noqa: BLE001
            dialogs.show_warning(self.window, f"Failed to save data: {exc}")

    def on_load_data(self) -> None:
        fp = dialogs.ask_open_file(
            title="Load measurement",
            initial_dir=self._root_dir / "__data__",
            filetypes=[("Measurement", "*.mat *.csv"), ("All files", "*.*")],
        )
        if fp is None:
            return

        try:
            loaded = self.load_measurement_use_case.execute(str(fp))
            self._ui_handler.set_result(loaded.result)
            dialogs.show_info(self.window, "Measurement loaded")
        except Exception as exc:  # noqa: BLE001
            dialogs.show_warning(self.window, f"Failed to load data: {exc}")

    def on_load_reference(self) -> None:
        fp = dialogs.ask_open_file(
            title="Load reference",
            initial_dir=self._root_dir / "__data__",
            filetypes=[("MAT files", "*.mat"), ("All files", "*.*")],
        )
        if fp is None:
            return

        try:
            _curve, interpolator = self.load_reference_use_case.execute(str(fp))
            self._reference_interpolator = interpolator
            self.vm.calibration_enabled.set(True)
            dialogs.show_info(self.window, "Reference loaded")
        except Exception as exc:  # noqa: BLE001
            dialogs.show_warning(self.window, f"Failed to load reference: {exc}")

    def on_figure_change(self) -> None:
        self.window.plot_widget.set_mode(self.vm.figure_mode.get())

    def on_mag_phase_change(self) -> None:
        self._ui_handler.refresh_plot()

    def on_close(self) -> None:
        self._monitor.stop()
        try:
            settings = vm_to_settings(self.vm)
            self.settings_use_case.save(settings)
        except Exception:
            pass

        self._task_runner.shutdown()
        self.window.destroy()

    def _process_events(self) -> None:
        try:
            while True:
                event = self._event_queue.get_nowait()
                self._ui_handler.handle(event)
        except queue.Empty:
            pass
        finally:
            self.window.after(100, self._process_events)

    def _get_awg_target_address(self) -> str:
        try:
            settings = vm_to_settings(self.vm)
            return resolve_visa_address(settings.setup.awg)
        except Exception:
            return ""

    def _get_osc_target_address(self) -> str:
        try:
            settings = vm_to_settings(self.vm)
            return resolve_visa_address(settings.setup.osc)
        except Exception:
            return ""


def dialogs_to_target(path, window: AppWindow):
    from app.application.dto import SaveTarget

    return SaveTarget(
        base_path=path,
        include_timestamp=False,
        figures=window.plot_widget.figures(),
    )
