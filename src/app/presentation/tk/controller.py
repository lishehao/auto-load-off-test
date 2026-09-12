from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from app.application.events import EventEmitter, SweepAutoSaved, SweepFailed, SweepStarted, SweepWarning, SweepWorkerFinished
from app.application.ports.instruments import (
    InstrumentIdentityProbePort, InstrumentPortsFactory, ResourceScannerPort,
)
from app.application.services.calibration_receipts import (
    build_analysis_reference_receipt, build_reference_receipt,
)
from app.application.services.export_receipts import build_export_receipt
from app.application.services.instrument_discovery import (
    InstrumentDiscoveryService, format_connection_receipt, format_scan_receipt,
)
from app.application.services.measurement_workspace import MeasurementWorkspace, save_displayed_data
from app.application.services.sweep_task_runner import SweepTaskRunner
from app.application.use_cases.analyze_measurement import AnalysisOptions, AnalyzeMeasurementUseCase
from app.application.use_cases.load_measurement import LoadMeasurementUseCase
from app.application.use_cases.load_reference import LoadReferenceUseCase
from app.application.use_cases.save_measurement import SaveMeasurementUseCase
from app.application.use_cases.settings_use_case import SettingsUseCase
from app.domain.models import InstrumentEndpoint
from app.domain.validators import validate_settings
from app.presentation.tk import dialogs
from app.presentation.tk.fixture_replay import FixtureReplay
from app.presentation.tk.mapper import settings_to_vm, vm_to_settings
from app.presentation.tk.ui_event_handler import UiEventHandler, _format_frequency
from app.runtime.paths import AppPaths
from app.runtime.event_log import RunEventLog
from app.runtime.resources import bundled_measurement_fixture, bundled_reference_fixture

if TYPE_CHECKING:
    from app.presentation.tk.app_window import AppWindow
    from app.presentation.tk.view_model import ViewModel


@dataclass
class _JobFinished:
    value: object = None
    error: Exception | None = None


class TkController(EventEmitter):
    """Own one foreground operation; workers send values back to the Tk thread."""

    def __init__(
        self, *, window: AppWindow, vm: ViewModel,
        settings_use_case: SettingsUseCase,
        save_measurement_use_case: SaveMeasurementUseCase,
        load_measurement_use_case: LoadMeasurementUseCase,
        load_reference_use_case: LoadReferenceUseCase,
        scanner: ResourceScannerPort, identity_probe: InstrumentIdentityProbePort,
        ports_factory: InstrumentPortsFactory,
        resolve_address: Callable[[InstrumentEndpoint], str],
        paths: AppPaths | None = None,
    ) -> None:
        self.window, self.vm = window, vm
        self.settings_use_case = settings_use_case
        self.save_measurement_use_case = save_measurement_use_case
        self.load_measurement_use_case = load_measurement_use_case
        self.load_reference_use_case = load_reference_use_case
        self._paths = paths or AppPaths.default()
        self._resolve_address = resolve_address
        self._event_queue: queue.Queue[object] = queue.Queue()
        self._ui_handler = UiEventHandler(window=window, vm=vm)
        self._discovery_service = InstrumentDiscoveryService(scanner=scanner, identity_probe=identity_probe)
        self._task_runner = SweepTaskRunner(
            emitter=self, save_measurement_use_case=save_measurement_use_case,
            auto_save_dir=self._paths.measurement_dir, ports_factory=ports_factory,
        )
        self._workspace = MeasurementWorkspace(
            load_measurement_use_case=load_measurement_use_case,
            load_reference_use_case=load_reference_use_case,
        )
        self._replay = FixtureReplay(
            schedule=window.after, cancel=window.after_cancel,
            on_update=self._on_replay_update, on_finish=self._on_replay_finish,
        )
        self._operation = "idle"
        self._job_thread = None
        self._shutdown_thread = None
        self._job_success = None
        self._job_error = None
        self._poll_id = None
        self._closing = False
        self._destroyed = False
        self._connection_signature = None
        self._reference_interpolator = None
        self._reference_curve = None
        self._reference_path = None
        self._reference_snapshot = None
        self._document = None
        self._document_path = None
        self._measurement_snapshot = None
        self._replay_result = None
        self._result_settings = None
        self._applied_options = AnalysisOptions()
        self._applied_reference = None
        self._report_from_document = False
        self._output_dir = None
        self._live_stop_event = threading.Event()
        self._event_log = RunEventLog(self._paths.data_dir / "logs" / "sweep-events.jsonl")

    def initialize(self) -> None:
        self.window.bind_actions(
            on_start=self.on_start, on_stop=self.on_stop,
            on_save_data=self.on_save_data, on_load_data=self.on_load_data,
            on_load_demo_fixture=self.on_load_demo_fixture, on_load_ref=self.on_load_reference,
            on_save_settings=self.on_save_settings, on_load_settings=self.on_load_settings,
            on_scan_resources=self.on_scan_resources, on_test_connect=self.on_test_connect,
            on_close=self.on_close, on_figure_change=self.on_figure_change,
            on_mag_phase_change=self.on_mag_phase_change, on_plot_scale_change=self.on_plot_scale_change,
            on_replay_fixture=self.on_replay_fixture, on_apply_analysis=self.on_apply_analysis,
            on_reset_analysis=self.on_reset_analysis, on_clear_reference=self.on_clear_reference,
            on_export_report=self.on_export_report, on_open_output=self.on_open_output,
        )
        for name in ("freq_unit", "start_freq", "stop_freq", "calibration_enabled",
                     "correction_mode", "trigger_mode", "analysis_correction", "analysis_coverage"):
            getattr(self.vm, name).trace_add("write", lambda *_: self._refresh_reference_receipt(record=False))
        try:
            settings_to_vm(self.settings_use_case.load(), self.vm)
        except Exception as exc:
            self._warn(f"Settings were not loaded: {exc}")
        self._refresh_connection_targets()
        self._refresh_controls()
        self.on_figure_change()
        self.on_mag_phase_change()
        self._poll_id = self.window.after(100, self._process_events)

    def emit(self, event: object) -> None:
        self._event_queue.put(event)

    def _idle(self) -> bool:
        return not self._closing and self._operation == "idle" and not self._task_runner.is_running()

    def _set_operation(self, mode: str) -> None:
        self._operation = mode
        self._refresh_controls()

    def _refresh_controls(self) -> None:
        self.window.set_operation_state(
            self._operation, has_data=not self._ui_handler.latest_result.is_empty,
            can_replay=self._replay_result is not None, has_reference=self._reference_curve is not None,
            can_analyze=self._document is not None, has_output=self._output_dir is not None,
        )

    def _start_job(self, operation, work, success, error=None) -> bool:
        if not self._idle():
            return False
        self._job_success, self._job_error = success, error
        self._set_operation(operation)

        def run():
            try:
                self.emit(_JobFinished(value=work()))
            except Exception as exc:
                self.emit(_JobFinished(error=exc))

        self._job_thread = threading.Thread(target=run, daemon=True)
        self._job_thread.start()
        return True

    def _finish_job(self, event: _JobFinished) -> None:
        success, error = self._job_success, self._job_error
        self._job_thread = self._job_success = self._job_error = None
        if not self._closing:
            try:
                if event.error is not None:
                    if error is not None:
                        error(event.error)
                    else:
                        self._warn(f"Operation failed: {event.error}")
                elif success is not None:
                    success(event.value)
            except Exception as exc:
                self._warn(f"Could not present result: {exc}")
        if not self._closing and not self._task_runner.is_running() and not self._replay.active:
            self._set_operation("idle")

    def _warn(self, message: str) -> None:
        self.vm.status_text.set(message)
        self._ui_handler.record_event(message, level="Warning")
        dialogs.show_warning(self.window, message)

    def on_start(self) -> None:
        if not self._idle():
            return
        try:
            checks = ("safety_limits_checked", "safety_connections_checked", "safety_output_checked")
            if not all(bool(getattr(self.vm, name).get()) for name in checks):
                raise ValueError("Confirm the three operator safety checks before starting hardware.")
            settings = deepcopy(vm_to_settings(self.vm))
            validate_settings(settings)
            enabled = bool(self.vm.calibration_enabled.get())
            if enabled and self._reference_interpolator is None:
                raise ValueError("Load a reference before enabling hardware correction.")
            reference = self._reference_interpolator
        except Exception as exc:
            self._warn(f"Cannot start: {exc}")
            return
        previous = self._ui_handler.latest_result.snapshot()
        previous_settings = self._result_settings
        source_names = ("source_mode", "data_source_text", "fixture_badge_text", "validation_receipt_text",
                        "export_receipt_text", "run_state_text", "progress_text", "elapsed_text",
                        "latest_frequency_text")
        source_state = {name: getattr(self.vm, name).get() for name in source_names}
        self._result_settings = settings
        self._live_stop_event = threading.Event()
        self.vm.run_state_text.set("Connecting")
        self.vm.status_text.set("Connecting instruments; Stop requests cancellation")

        def started(_):
            self._document = self._measurement_snapshot = self._document_path = None
            self._replay_result = None
            self._report_from_document = False
            self.vm.analysis_status_text.set("Hardware result; file analysis not applied")
            self._refresh_reference_receipt(record=False)

        def failed(exc):
            self._result_settings = previous_settings
            self._ui_handler.set_result(previous)
            for name, value in source_state.items():
                getattr(self.vm, name).set(value)
            self._warn(f"Hardware start failed; previous data retained: {exc}")

        self._start_job("live", lambda: self._task_runner.start(
            settings=settings, calibration_enabled=enabled, reference_interpolator=reference,
            cancellation_event=self._live_stop_event,
        ), started, failed)

    def on_stop(self) -> None:
        if self._replay.active:
            self._replay.stop()
        elif self._operation in {"live", "stopping"}:
            self._live_stop_event.set()
            self._task_runner.stop()
            self._set_operation("stopping")
            self.vm.status_text.set("Stop requested; waiting for worker cleanup and save")
            self._ui_handler.record_event("Stop requested; output-off is not yet confirmed")

    def on_save_settings(self) -> None:
        if not self._idle():
            return
        try:
            settings = vm_to_settings(self.vm)
            validate_settings(settings)
            self.settings_use_case.save(settings)
            self.vm.status_text.set("Settings saved")
        except Exception as exc:
            self._warn(f"Cannot save settings: {exc}")

    def on_load_settings(self) -> None:
        if not self._idle():
            return
        try:
            settings_to_vm(self.settings_use_case.load(), self.vm)
            self._refresh_connection_targets()
            self.on_figure_change()
            self.on_mag_phase_change()
            self.vm.status_text.set("Settings loaded; displayed data unchanged")
        except Exception as exc:
            self._warn(f"Cannot load settings: {exc}")

    def on_load_data(self) -> None:
        if not self._idle():
            return
        path = dialogs.ask_open_file(title="Load measurement", initial_dir=self._paths.data_dir,
                                    filetypes=[("Measurement", "*.mat *.csv")])
        if path:
            self._start_job("loading", lambda: self._workspace.read_document(Path(path)), self._present_document)

    def on_load_demo_fixture(self) -> None:
        if not self._idle():
            return

        def load():
            return (self._workspace.read_document(bundled_measurement_fixture()),
                    self._workspace.read_reference(bundled_reference_fixture()))

        def loaded(value):
            self._present_document(value[0])
            self._present_reference(value[1])
            self.vm.status_text.set("72-point simulated fixture loaded; Replay Fixture is ready")

        self._start_job("loading", load, loaded)

    def _load_measurement_from_path(self, path: Path, *, force_fixture: bool = False) -> None:
        """Synchronous file entry for test/capture tooling; never relabel arbitrary data."""
        if self._idle():
            self._present_document(self._workspace.read_document(path))

    def _present_document(self, document) -> None:
        self._document, self._document_path, self._measurement_snapshot = document
        self._applied_options = AnalysisOptions()
        self._applied_reference = None
        self._report_from_document = True
        self._result_settings = None
        self.vm.analysis_dataset.set("canonical")
        self.vm.analysis_correction.set("none")
        self.vm.analysis_coverage.set("reject")
        self.vm.analysis_status_text.set("Original file snapshot; no new correction applied")
        self._present_file_result(self._document.result.snapshot())
        self._refresh_reference_receipt(record=False)
        self._refresh_controls()

    def _present_file_result(self, result) -> None:
        self._ui_handler.set_result(result)
        meta_text = " ".join(str(result.meta.get(key, "")) for key in
                             ("source", "demo_label", "validation_boundary")).lower()
        fixture = "mock_fixture" in meta_text or "simulat" in meta_text
        name = self._document_path.name if self._document_path else "displayed result"
        if fixture:
            self._ui_handler.set_fixture_source(label="Simulated fixture", path_name=name)
            self._replay_result = result.snapshot()
        else:
            self._ui_handler.set_loaded_source(path_name=name)
            self._replay_result = None

    def on_replay_fixture(self) -> None:
        if not self._idle() or self._replay_result is None:
            return
        interval = {"1x": 150, "2x": 75, "4x": 38}.get(self.vm.replay_speed.get(), 150)
        self._report_from_document = False
        self._set_operation("replay")
        self._ui_handler.record_event("Started point-by-point fixture replay; no hardware")
        self._replay.start(self._replay_result, interval_ms=interval)

    def _on_replay_update(self, result, index, total, elapsed) -> None:
        self._ui_handler.set_result(result)
        self.vm.progress_text.set(f"{index} / {total}")
        self.vm.point_count_text.set(f"{index} / {total} points")
        self.vm.elapsed_text.set(f"{int(elapsed) // 60:02d}:{int(elapsed) % 60:02d}")
        self.vm.latest_frequency_text.set(_format_frequency(result.points[-1].freq_hz) if index else "-")
        self.vm.run_state_text.set("Fixture replay")
        self.vm.status_text.set(f"No hardware - simulated fixture: {index} / {total} points")
        self.vm.export_receipt_text.set("Replay in progress; partial results are retained on Stop")

    def _on_replay_finish(self, status) -> None:
        count = len(self._ui_handler.latest_result.points)
        self.vm.run_state_text.set("Replay complete" if status == "completed" else "Replay stopped")
        self.vm.export_receipt_text.set(f"{count} displayed points ready to save or report")
        self._ui_handler.record_event(f"Fixture replay {status}; {count} points retained")
        self._set_operation("idle")

    def on_load_reference(self) -> None:
        if not self._idle():
            return
        path = dialogs.ask_open_file(title="Load reference", initial_dir=self._paths.data_dir,
                                    filetypes=[("Reference", "*.mat")])
        if path:
            self._start_job("loading", lambda: self._workspace.read_reference(Path(path)), self._present_reference)

    def load_reference_from_path(self, path: str | Path, *, record: bool = True) -> tuple[str, ...]:
        if not self._idle():
            return ()
        return self._present_reference(self._workspace.read_reference(Path(path)), record=record)

    def _present_reference(self, value, *, record=True):
        self._reference_curve, self._reference_interpolator, self._reference_path, self._reference_snapshot = value
        freq = self._reference_curve.freq_hz
        self.window.plot_widget.set_reference_coverage(float(np.min(freq)), float(np.max(freq)))
        warnings = self._refresh_reference_receipt(record=record)
        self.vm.status_text.set("Reference loaded; displayed data unchanged until Apply Analysis")
        self._ui_handler.refresh_plot()
        self._refresh_controls()
        return warnings

    def on_clear_reference(self) -> None:
        if not self._idle():
            return
        self._reference_curve = self._reference_interpolator = None
        self._reference_path = self._reference_snapshot = None
        self.vm.calibration_enabled.set(False)
        self.vm.reference_receipt_text.set("No reference loaded; displayed correction is unchanged")
        self.window.plot_widget.clear_reference_coverage()
        self._ui_handler.refresh_plot()
        self._ui_handler.record_event("Reference cleared; existing displayed data retained")
        self._refresh_controls()

    def on_apply_analysis(self) -> None:
        if not self._idle() or self._document is None:
            return
        options = AnalysisOptions(correction=self.vm.analysis_correction.get(),
                                  coverage=self.vm.analysis_coverage.get(), dataset=self.vm.analysis_dataset.get())
        reference = deepcopy(self._reference_curve) if options.correction != "none" else None
        reference_path = self._reference_snapshot if reference is not None else None
        document = deepcopy(self._document)

        def applied(analysis):
            self._applied_options, self._applied_reference = options, reference_path
            self._report_from_document = True
            self._result_settings = None
            self._present_file_result(analysis.measurement)
            self.vm.analysis_status_text.set(
                f"Applied: {options.dataset} / {options.correction} / {options.coverage}")
            self.vm.run_state_text.set("Analysis ready")
            self.vm.status_text.set("Analysis applied to the original file snapshot")
            for warning in analysis.warnings:
                self._ui_handler.record_event(warning, level="Warning")
            self._refresh_reference_receipt(record=False)

        self._start_job("analyzing", lambda: AnalyzeMeasurementUseCase().execute(
            document, reference=reference, options=options), applied)

    def on_reset_analysis(self) -> None:
        if self._idle() and self._document is not None:
            self._present_document((self._document, self._document_path, self._measurement_snapshot))
            self.vm.status_text.set("Original file snapshot restored")

    def on_save_data(self) -> None:
        if not self._idle() or self._ui_handler.latest_result.is_empty:
            return
        path = dialogs.ask_save_file(title="Save displayed data", initial_dir=self._paths.data_dir,
                                    initial_name="measurement", filetypes=[("MAT files", "*.mat")])
        if path:
            self.save_data_to_path(Path(path))

    def save_data_to_path(self, path: Path) -> bool:
        if not self._idle() or self._ui_handler.latest_result.is_empty:
            return False
        stem = path.stem if path.suffix else path.name
        if any((path.parent / f"{stem}.{ext}").exists() for ext in ("mat", "csv", "txt")):
            self._warn("Export would overwrite existing files; choose a new name.")
            return False
        result, settings = self._ui_handler.latest_result.snapshot(), deepcopy(self._result_settings)
        source, badge = self.vm.data_source_text.get(), self.vm.fixture_badge_text.get()

        def saved(artifacts):
            receipt = build_export_receipt(artifacts=artifacts, settings=settings, result=result,
                                           source_text=source, fixture_badge_text=badge)
            self._output_dir = artifacts.mat_path.parent
            self._ui_handler.set_export_saved(receipt_text=receipt.summary)
            self.vm.status_text.set("Displayed data saved: MAT / CSV / TXT")

        return self._start_job("exporting", lambda: save_displayed_data(
            result=result, settings=settings, target_path=path,
            save_use_case=self.save_measurement_use_case), saved)

    def on_export_report(self) -> None:
        if not self._idle() or self._ui_handler.latest_result.is_empty:
            return
        path = dialogs.ask_save_file(title="New report directory", initial_dir=self._paths.data_dir,
                                    initial_name=datetime.now().strftime("analysis_%Y%m%d_%H%M%S"),
                                    filetypes=[("Directory name", "*")])
        if path:
            self.export_report_to_path(Path(path))

    def export_report_to_path(self, path: Path) -> bool:
        if not self._idle() or self._ui_handler.latest_result.is_empty:
            return False
        document_path = self._measurement_snapshot if self._report_from_document else None
        options = self._applied_options if document_path else AnalysisOptions()
        reference_path = self._applied_reference if document_path else None
        result, settings = self._ui_handler.latest_result.snapshot(), deepcopy(self._result_settings)

        def export():
            from app.offline import run_offline_analysis
            source = document_path or self._workspace.snapshot_result(
                result, settings, self.save_measurement_use_case)
            return run_offline_analysis(source, path, reference_path=reference_path, options=options)

        def saved(receipt):
            self._output_dir = Path(receipt["output_dir"])
            self._ui_handler.set_export_saved(receipt_text=(
                f"Report: {self._output_dir}\nMAT / CSV / TXT / PNG / HTML / manifest.json\n"
                f"{receipt['point_count']} displayed points; offline processing, no hardware"))
            self.vm.status_text.set("Reproducible report saved")

        return self._start_job("exporting", export, saved)

    def on_open_output(self) -> None:
        if not self._idle() or self._output_dir is None:
            return
        try:
            if not self._output_dir.is_dir():
                raise FileNotFoundError(self._output_dir)
            if sys.platform == "win32":
                os.startfile(str(self._output_dir))
            else:
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(self._output_dir)])
        except Exception as exc:
            self._warn(f"Could not open output folder: {exc}")

    def on_scan_resources(self) -> None:
        def scanned(scan):
            self.vm.discovery_status_text.set(format_scan_receipt(scan))
            self.vm.status_text.set("Resource scan complete; resource visibility is not a connection test")
        self._start_job("discovery", self._discovery_service.scan_resources, scanned)

    def on_test_connect(self) -> None:
        if not self._idle():
            return
        try:
            setup = deepcopy(vm_to_settings(self.vm).setup)
        except Exception as exc:
            self._warn(f"Cannot test connection: {exc}")
            return

        def checked(checks):
            self.window.set_connection_status(
                any(c.role.value == "awg" and c.status == "connected" for c in checks),
                any(c.role.value == "osc" and c.status == "connected" for c in checks))
            for check in checks:
                text = f"{check.role.value.upper()} {check.status.replace('_', ' ')}"
                getattr(self.vm, f"{check.role.value}_connection_text").set(text)
            self.vm.discovery_status_text.set(format_connection_receipt(checks))
            self.vm.status_text.set("Connection test complete; no sweep performed")

        self._start_job("discovery", lambda: self._discovery_service.test_setup(setup, self._resolve_address), checked)

    def _refresh_connection_targets(self) -> None:
        names = ("awg_model", "osc_model", "awg_connect_mode", "osc_connect_mode",
                 "awg_visa", "osc_visa", "awg_ip", "osc_ip")
        # Read only UI values; never poll hardware simply because the window is open.
        signature = tuple(getattr(self.vm, name).get() for name in names if hasattr(self.vm, name))
        if signature != self._connection_signature:
            self._connection_signature = signature
            self.window.set_connection_idle()
            self.vm.awg_connection_text.set("AWG not tested")
            self.vm.osc_connection_text.set("OSC not tested")
            self.vm.discovery_status_text.set("Setup changed; Test Connect has not run")

    def _refresh_reference_receipt(self, *, record: bool) -> tuple[str, ...]:
        if self._reference_curve is None:
            return ()
        if self._document is not None:
            receipt = build_analysis_reference_receipt(
                path=self._reference_path, curve=self._reference_curve,
                result=self._ui_handler.latest_result,
                requested_correction=self.vm.analysis_correction.get(), coverage=self.vm.analysis_coverage.get())
        else:
            try:
                settings = vm_to_settings(self.vm)
            except Exception:
                settings = None
            receipt = build_reference_receipt(
                path=self._reference_path, curve=self._reference_curve, settings=settings,
                calibration_enabled=bool(self.vm.calibration_enabled.get()))
        self._ui_handler.set_reference_loaded(receipt_text=receipt.summary, warnings=receipt.warnings, record=record)
        return receipt.warnings

    def on_figure_change(self) -> None:
        self.window.plot_widget.set_mode(self.vm.figure_mode.get())

    def on_mag_phase_change(self) -> None:
        self._ui_handler.refresh_plot()

    def on_plot_scale_change(self) -> None:
        self._ui_handler.refresh_plot()

    def on_close(self) -> None:
        if self._closing:
            return
        self._closing = True
        self._replay.stop(notify=False)
        self._live_stop_event.set()
        self._task_runner.stop()
        self._set_operation("stopping")
        self.vm.status_text.set("Closing: waiting for background work and instrument cleanup")
        self._shutdown_thread = threading.Thread(target=self._task_runner.shutdown, daemon=True)
        self._shutdown_thread.start()
        if self._poll_id is None:
            self._poll_id = self.window.after(100, self._process_events)

    def _process_events(self) -> None:
        self._poll_id = None
        self._drain_event_queue()
        shutdown_done = self._shutdown_thread is None or not self._shutdown_thread.is_alive()
        if self._closing and self._job_thread is None and not self._task_runner.is_running() and shutdown_done:
            self._drain_event_queue()
            self._workspace.close()
            self._event_log.close()
            self._destroyed = True
            self.window.destroy()
            return
        if not self._closing:
            if self._operation in {"live", "stopping"} and self._job_thread is None and not self._task_runner.is_running():
                self._set_operation("idle")
            if self._operation == "idle":
                self._refresh_connection_targets()
            self._refresh_controls()
        self._poll_id = self.window.after(100, self._process_events)

    def _drain_event_queue(self) -> None:
        while True:
            try:
                event = self._event_queue.get_nowait()
            except queue.Empty:
                break
            if isinstance(event, _JobFinished):
                self._finish_job(event)
                continue
            if isinstance(event, (SweepWarning, SweepFailed, SweepWorkerFinished)):
                try:
                    self._event_log.record(event)
                except OSError as exc:
                    print(f"Could not persist run warning: {exc}; event={event}", file=sys.stderr)
            if not self._closing:
                if isinstance(event, SweepStarted):
                    self._ui_handler.prepare_for_sweep_start()
                self._ui_handler.handle(event)
                if isinstance(event, SweepAutoSaved):
                    self._output_dir = event.artifacts.mat_path.parent
        if not self._closing:
            self._refresh_controls()
