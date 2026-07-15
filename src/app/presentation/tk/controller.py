from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from pathlib import Path

import numpy as np

from app.application.events import EventEmitter
from app.application.ports.instruments import (
    InstrumentIdentityProbePort,
    InstrumentPortsFactory,
    ResourceScannerPort,
)
from app.application.services.instrument_discovery import (
    InstrumentDiscoveryService,
    format_connection_receipt,
    format_scan_receipt,
)
from app.application.services.calibration_receipts import build_reference_receipt
from app.application.services.export_receipts import build_export_receipt
from app.application.services.sweep_task_runner import SweepTaskRunner
from app.application.services.connection_monitor import ConnectionMonitor
from app.application.use_cases.load_measurement import LoadMeasurementUseCase
from app.application.use_cases.load_reference import LoadReferenceUseCase
from app.application.use_cases.save_measurement import SaveMeasurementUseCase
from app.application.use_cases.settings_use_case import SettingsUseCase
from app.domain.models import InstrumentEndpoint, ReferenceCurve
from app.presentation.tk import dialogs
from app.presentation.tk.app_window import AppWindow
from app.presentation.tk.mapper import settings_to_vm, vm_to_settings
from app.presentation.tk.ui_event_handler import UiEventHandler
from app.presentation.tk.view_model import ViewModel
from app.runtime.paths import AppPaths


DEMO_FIXTURE_FILE = Path("demo_data") / "hyperframe_simulated_fixture.mat"


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
        identity_probe: InstrumentIdentityProbePort,
        ports_factory: InstrumentPortsFactory,
        resolve_address: Callable[[InstrumentEndpoint], str],
        paths: AppPaths | None = None,
    ) -> None:
        self.window = window
        self.vm = vm
        self.settings_use_case = settings_use_case
        self.save_measurement_use_case = save_measurement_use_case
        self.load_measurement_use_case = load_measurement_use_case
        self.load_reference_use_case = load_reference_use_case

        self._event_queue: queue.Queue[object] = queue.Queue()
        self._reference_interpolator = None
        self._reference_curve: ReferenceCurve | None = None
        self._reference_path: Path | None = None
        self._reference_trace_tokens: list[str] = []
        self._paths = paths or AppPaths.default()
        self._resolve_address = resolve_address
        self._connection_target_lock = threading.Lock()
        self._awg_target_address = ""
        self._osc_target_address = ""
        self._closing = False

        self._ui_handler = UiEventHandler(window=window, vm=vm)
        self._discovery_service = InstrumentDiscoveryService(scanner=scanner, identity_probe=identity_probe)
        self._task_runner = SweepTaskRunner(
            emitter=self,
            save_measurement_use_case=save_measurement_use_case,
            auto_save_dir=self._paths.measurement_dir,
            ports_factory=ports_factory,
        )
        self._monitor = ConnectionMonitor(
            scanner=scanner,
            get_awg_address=self._get_cached_awg_target_address,
            get_osc_address=self._get_cached_osc_target_address,
            emitter=self,
        )

    def initialize(self) -> None:
        self.window.bind_actions(
            on_start=self.on_start,
            on_stop=self.on_stop,
            on_save_data=self.on_save_data,
            on_load_data=self.on_load_data,
            on_load_demo_fixture=self.on_load_demo_fixture,
            on_load_ref=self.on_load_reference,
            on_save_settings=self.on_save_settings,
            on_load_settings=self.on_load_settings,
            on_scan_resources=self.on_scan_resources,
            on_test_connect=self.on_test_connect,
            on_close=self.on_close,
            on_figure_change=self.on_figure_change,
            on_mag_phase_change=self.on_mag_phase_change,
        )
        self._bind_reference_receipt_traces()

        try:
            settings = self.settings_use_case.load()
            settings_to_vm(settings, self.vm)
        except Exception as exc:  # noqa: BLE001
            dialogs.show_warning(self.window, f"Failed to load settings: {exc}")

        self._refresh_connection_targets()
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
            self._ui_handler.set_live_source()
            self._refresh_reference_receipt(record=True)
            if bool(self.vm.calibration_enabled.get()) and self._reference_interpolator is None:
                self._ui_handler.record_event("Calibration enabled but no reference loaded", level="Warning")
            self._refresh_connection_targets(settings)
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
            self._refresh_connection_targets(settings)
            dialogs.show_info(self.window, "Settings saved")
        except Exception as exc:  # noqa: BLE001
            dialogs.show_warning(self.window, f"Failed to save settings: {exc}")

    def on_load_settings(self) -> None:
        try:
            settings = self.settings_use_case.load()
            settings_to_vm(settings, self.vm)
            self._refresh_connection_targets(settings)
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
            initial_dir=self._paths.data_dir,
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
            receipt = build_export_receipt(
                artifacts=artifacts,
                settings=settings,
                result=self._ui_handler.latest_result,
                source_text=self.vm.data_source_text.get(),
                fixture_badge_text=self.vm.fixture_badge_text.get(),
            )
            self._ui_handler.set_export_saved(receipt_text=receipt.summary)
            dialogs.show_info(self.window, f"Saved: {artifacts.mat_path.name}")
        except Exception as exc:  # noqa: BLE001
            self._ui_handler.record_event(f"Save data failed: {exc}", level="Warning")
            dialogs.show_warning(self.window, f"Failed to save data: {exc}")

    def on_load_data(self) -> None:
        fp = dialogs.ask_open_file(
            title="Load measurement",
            initial_dir=self._paths.data_dir,
            filetypes=[("Measurement", "*.mat *.csv"), ("All files", "*.*")],
        )
        if fp is None:
            return

        try:
            self._load_measurement_from_path(Path(fp))
            dialogs.show_info(self.window, "Measurement loaded")
        except Exception as exc:  # noqa: BLE001
            dialogs.show_warning(self.window, f"Failed to load data: {exc}")

    def on_load_demo_fixture(self) -> None:
        fixture_path = self._paths.root_dir / DEMO_FIXTURE_FILE
        if not fixture_path.exists():
            dialogs.show_warning(
                self.window,
                f"Demo fixture not found: {fixture_path}",
            )
            return

        try:
            self._load_measurement_from_path(fixture_path, force_fixture=True)
            point_count = self.vm.point_count_text.get()
            self.vm.status_text.set(f"Demo fixture loaded ({point_count}; no hardware)")
        except Exception as exc:  # noqa: BLE001
            dialogs.show_warning(self.window, f"Failed to load demo fixture: {exc}")

    def on_load_reference(self) -> None:
        fp = dialogs.ask_open_file(
            title="Load reference",
            initial_dir=self._paths.data_dir,
            filetypes=[("MAT files", "*.mat"), ("All files", "*.*")],
        )
        if fp is None:
            return

        try:
            curve, interpolator = self.load_reference_use_case.execute(str(fp))
            self._reference_interpolator = interpolator
            self._reference_curve = curve
            self._reference_path = Path(fp)
            self.vm.calibration_enabled.set(True)
            warnings = self._refresh_reference_receipt(record=True)
            if warnings:
                self.vm.status_text.set("Reference loaded with coverage warning")
            else:
                self.vm.status_text.set("Reference loaded")
            dialogs.show_info(self.window, "Reference loaded")
        except Exception as exc:  # noqa: BLE001
            self._ui_handler.record_event(f"Reference load failed: {exc}", level="Warning")
            dialogs.show_warning(self.window, f"Failed to load reference: {exc}")

    def on_scan_resources(self) -> None:
        try:
            scan = self._discovery_service.scan_resources()
            self.vm.discovery_status_text.set(format_scan_receipt(scan))
            self.vm.status_text.set("Resource scan completed")
        except Exception as exc:  # noqa: BLE001
            self.vm.discovery_status_text.set(f"Resource scan failed: {exc}")
            self._ui_handler.record_event(f"Resource scan failed: {exc}", level="Warning")
            dialogs.show_warning(self.window, f"Resource scan failed: {exc}")

    def on_test_connect(self) -> None:
        try:
            settings = vm_to_settings(self.vm)
            checks = self._discovery_service.test_setup(settings.setup, self._resolve_address)
            self._apply_connection_checks(checks)
            self.vm.discovery_status_text.set(format_connection_receipt(checks))
            self.vm.status_text.set("Connection test completed")
        except Exception as exc:  # noqa: BLE001
            self.vm.discovery_status_text.set(f"Connection test failed: {exc}")
            self._ui_handler.record_event(f"Connection test failed: {exc}", level="Warning")
            dialogs.show_warning(self.window, f"Connection test failed: {exc}")

    def on_figure_change(self) -> None:
        self.window.plot_widget.set_mode(self.vm.figure_mode.get())

    def on_mag_phase_change(self) -> None:
        self._ui_handler.refresh_plot()

    def _load_measurement_from_path(self, path: Path, *, force_fixture: bool = False) -> None:
        loaded = self.load_measurement_use_case.execute(str(path))
        self._ui_handler.set_result(loaded.result)
        source = _describe_loaded_source(path=path, raw_payload=loaded.raw_payload)
        if force_fixture or source["fixture"]:
            self._ui_handler.set_fixture_source(label=source["label"], path_name=path.name)
        else:
            self._ui_handler.set_loaded_source(path_name=path.name)

    def on_close(self) -> None:
        self._closing = True
        self._monitor.stop()
        try:
            settings = vm_to_settings(self.vm)
            self.settings_use_case.save(settings)
        except Exception:
            pass

        self._task_runner.shutdown()
        self._drain_event_queue()
        self.window.destroy()

    def _process_events(self) -> None:
        self._drain_event_queue()
        if not self._closing:
            self._refresh_connection_targets()
            self.window.after(100, self._process_events)

    def _drain_event_queue(self) -> None:
        try:
            while True:
                event = self._event_queue.get_nowait()
                self._ui_handler.handle(event)
        except queue.Empty:
            pass

    def _refresh_connection_targets(self, settings=None) -> None:
        try:
            settings = settings or vm_to_settings(self.vm)
            awg_address = self._resolve_address(settings.setup.awg)
            osc_address = self._resolve_address(settings.setup.osc)
        except Exception:
            awg_address = ""
            osc_address = ""

        with self._connection_target_lock:
            self._awg_target_address = awg_address
            self._osc_target_address = osc_address

    def _get_cached_awg_target_address(self) -> str:
        with self._connection_target_lock:
            return self._awg_target_address

    def _get_cached_osc_target_address(self) -> str:
        with self._connection_target_lock:
            return self._osc_target_address

    def _apply_connection_checks(self, checks) -> None:
        for check in checks:
            label = check.role.value.upper()
            if check.status == "connected":
                text = f"{label} connected"
            elif check.status == "address_empty":
                text = f"{label} address empty"
            elif check.status == "unsupported_model":
                text = f"{label} unsupported"
            else:
                text = f"{label} offline"

            if check.role.value == "awg":
                self.vm.awg_connection_text.set(text)
            else:
                self.vm.osc_connection_text.set(text)

    def _bind_reference_receipt_traces(self) -> None:
        variables = [
            self.vm.freq_unit,
            self.vm.start_freq,
            self.vm.stop_freq,
            self.vm.calibration_enabled,
            self.vm.correction_mode,
            self.vm.trigger_mode,
        ]
        for variable in variables:
            token = variable.trace_add("write", self._on_reference_setting_changed)
            self._reference_trace_tokens.append(token)

    def _on_reference_setting_changed(self, *_args) -> None:
        self._refresh_reference_receipt(record=False)

    def _refresh_reference_receipt(self, *, record: bool) -> tuple[str, ...]:
        if self._reference_curve is None or self._reference_path is None:
            return ()

        try:
            settings = vm_to_settings(self.vm)
        except Exception:
            settings = None

        receipt = build_reference_receipt(
            path=self._reference_path,
            curve=self._reference_curve,
            settings=settings,
            calibration_enabled=bool(self.vm.calibration_enabled.get()),
        )
        self._ui_handler.set_reference_loaded(
            receipt_text=receipt.summary,
            warnings=receipt.warnings,
            record=record,
        )
        return receipt.warnings


def dialogs_to_target(path, window: AppWindow):
    from app.application.dto import SaveTarget

    return SaveTarget(
        base_path=path,
        include_timestamp=False,
        figures=window.plot_widget.figures(),
    )


def _describe_loaded_source(path: Path, raw_payload: dict[str, np.ndarray]) -> dict[str, object]:
    source = _payload_text(raw_payload, "source")
    label = _payload_text(raw_payload, "demo_label") or "Loaded fixture"
    is_fixture = source == "mock_fixture" or "hyperframe_simulated_fixture" in path.name
    return {
        "fixture": is_fixture,
        "label": label,
    }


def _payload_text(payload: dict[str, np.ndarray], key: str) -> str:
    value = payload.get(key)
    if value is None:
        return ""
    arr = np.asarray(value)
    if arr.dtype.kind in {"U", "S"}:
        if arr.ndim == 2 and arr.shape[0] == 1:
            return "".join(str(item) for item in arr[0]).strip()
        return "".join(str(item) for item in arr.ravel()).strip()
    squeezed = arr.squeeze()
    if squeezed.shape == ():
        return str(squeezed.item()).strip()
    return ""
