from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import time
import unittest
from unittest.mock import Mock, patch

import numpy as np

from app.application.events import SweepCompleted, SweepWarning
from app.application.use_cases.load_measurement import LoadMeasurementUseCase
from app.application.use_cases.load_reference import LoadReferenceUseCase
from app.application.use_cases.save_measurement import SaveMeasurementUseCase
from app.infrastructure.persistence.measurement_repo_mat_csv import MatCsvMeasurementRepository
from app.infrastructure.persistence.reference_repo_mat import MatReferenceRepository
from app.infrastructure.persistence.settings_defaults import DefaultSettingsFactory
from app.presentation.tk.controller import TkController
from app.presentation.tk.mapper import settings_to_vm
from app.runtime.paths import AppPaths
from app.runtime.resources import bundled_measurement_fixture


class Variable:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value

    def trace_add(self, *_):
        return "trace"


class Variables:
    def __init__(self):
        self.values = {}

    def __getattr__(self, name):
        return self.values.setdefault(name, Variable())


class Window:
    def __init__(self):
        self.plot_widget = Mock()
        self.btn_start, self.btn_stop = Mock(), Mock()
        self.pending = {}
        self.counter = 0
        self.destroyed = False
        self.mode = "idle"

    def after(self, _, callback):
        self.counter += 1
        self.pending[self.counter] = callback
        return self.counter

    def after_cancel(self, key):
        self.pending.pop(key, None)

    def tick(self):
        key = min(self.pending)
        self.pending.pop(key)()

    def set_operation_state(self, mode, **_):
        self.mode = mode

    def set_connection_idle(self):
        pass

    def set_connection_status(self, *_):
        pass

    def destroy(self):
        self.destroyed = True


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.vm, self.window = Variables(), Window()
        settings = DefaultSettingsFactory().create()
        settings_to_vm(settings, self.vm)
        for key, value in {"figure_mode": "gain_db", "plot_scale": "log", "replay_speed": "1x",
                           "source_mode": "live", "analysis_correction": "none", "analysis_coverage": "reject",
                           "analysis_dataset": "canonical"}.items():
            getattr(self.vm, key).set(value)
        self.repository = MatCsvMeasurementRepository()
        self.ports_factory = Mock(side_effect=AssertionError("Hardware must not be used"))
        self.controller = TkController(
            window=self.window, vm=self.vm, settings_use_case=Mock(),
            save_measurement_use_case=SaveMeasurementUseCase(self.repository),
            load_measurement_use_case=LoadMeasurementUseCase(self.repository),
            load_reference_use_case=LoadReferenceUseCase(MatReferenceRepository()),
            scanner=Mock(), identity_probe=Mock(), ports_factory=self.ports_factory,
            resolve_address=lambda endpoint: endpoint.visa_address, paths=AppPaths.from_root(self.root),
        )
        self.addCleanup(self.controller._workspace.close)
        self.addCleanup(self.controller._event_log.close)
        self.warning = self.enterContext(patch("app.presentation.tk.controller.dialogs.show_warning"))

    def settle(self):
        deadline = time.monotonic() + 10
        while self.controller._job_thread is not None and time.monotonic() < deadline:
            self.controller._job_thread.join(0.01)
            self.controller._drain_event_queue()
        self.assertIsNone(self.controller._job_thread)

    def load_demo(self):
        self.controller.on_load_demo_fixture()
        self.settle()
        self.assertEqual(len(self.controller._ui_handler.latest_result.points), 72)
        self.assertIn("No hardware", self.vm.fixture_badge_text.get())

    def test_load_replay_stop_restart_and_busy_guards(self):
        self.load_demo()
        self.controller.on_replay_fixture()
        self.assertTrue(self.controller._ui_handler.latest_result.is_empty)
        self.assertEqual(self.window.mode, "replay")
        for _ in range(5):
            self.window.tick()
        self.controller.on_load_demo_fixture()
        self.controller._load_measurement_from_path(bundled_measurement_fixture())
        self.controller.on_apply_analysis()
        self.assertEqual(len(self.controller._ui_handler.latest_result.points), 5)
        self.controller.on_stop()
        self.assertEqual(self.window.mode, "idle")
        self.assertEqual(self.vm.progress_text.get(), "5 / 72")
        self.assertEqual(self.controller._ui_handler.latest_result.meta["run_status"], "stopped")
        self.controller.on_replay_fixture()
        for _ in range(72):
            self.window.tick()
        self.assertEqual(self.vm.progress_text.get(), "72 / 72")
        self.assertEqual(self.window.mode, "idle")
        self.ports_factory.assert_not_called()

    def test_reference_load_is_not_implicit_apply_and_analysis_uses_original_snapshot(self):
        self.load_demo()
        original = self.controller._ui_handler.latest_result.gain_db_array().copy()
        self.assertFalse(self.vm.calibration_enabled.get())
        self.vm.analysis_dataset.set("raw")
        self.vm.analysis_correction.set("complex")
        self.controller.on_apply_analysis()
        self.settle()
        first = self.controller._ui_handler.latest_result.gain_db_array().copy()
        self.assertEqual(self.controller._ui_handler.latest_result.meta["reference_correction"], "complex")
        self.warning.assert_not_called()
        self.controller.on_apply_analysis()
        self.settle()
        np.testing.assert_allclose(first, self.controller._ui_handler.latest_result.gain_db_array())
        self.controller.on_clear_reference()
        np.testing.assert_allclose(first, self.controller._ui_handler.latest_result.gain_db_array())
        self.controller.on_reset_analysis()
        np.testing.assert_allclose(original, self.controller._ui_handler.latest_result.gain_db_array())

    def test_failed_analysis_keeps_display_and_applied_report_options(self):
        self.load_demo()
        original = self.controller._ui_handler.latest_result.gain_db_array().copy()
        self.vm.analysis_correction.set("complex")
        self.controller.on_apply_analysis()
        self.settle()
        self.warning.assert_called_once()
        np.testing.assert_array_equal(original, self.controller._ui_handler.latest_result.gain_db_array())
        self.assertEqual(self.controller._applied_options.correction, "none")
        self.assertEqual(self.window.mode, "idle")

    def test_save_partial_and_report_match_display_without_fabricated_hardware_settings(self):
        self.load_demo()
        self.controller.on_replay_fixture()
        for _ in range(3):
            self.window.tick()
        self.controller.on_stop()
        self.vm.awg_amp.set("this is intentionally not a hardware setting")
        self.assertTrue(self.controller.save_data_to_path(self.root / "partial.mat"))
        self.settle()
        loaded = self.repository.load(str(self.root / "partial.mat"))
        self.assertEqual(len(loaded.result.points), 3)
        self.assertEqual(loaded.result.meta["source"], "mock_fixture")
        self.assertEqual(loaded.result.meta["run_status"], "stopped")
        self.assertNotIn("settings", loaded.raw_payload)
        self.assertTrue(self.controller.export_report_to_path(self.root / "report"))
        self.settle()
        self.assertTrue((self.root / "report" / "report.html").is_file())
        exported = self.repository.load(str(self.root / "report" / "measurement.mat"))
        self.assertEqual(len(exported.result.points), 3)
        self.assertEqual(self.controller._output_dir, (self.root / "report").resolve())
        self.assertFalse(self.controller.save_data_to_path(self.root / "partial.mat"))
        self.ports_factory.assert_not_called()

    def test_hardware_start_requires_safety_and_failure_restores_prior_source(self):
        self.load_demo()
        self.controller.on_start()
        self.ports_factory.assert_not_called()
        for name in ("safety_limits_checked", "safety_connections_checked", "safety_output_checked"):
            getattr(self.vm, name).set(True)
        with patch.object(self.controller._task_runner, "start", side_effect=RuntimeError("offline")):
            self.controller.on_start()
            self.settle()
        self.assertEqual(self.vm.source_mode.get(), "fixture")
        self.assertEqual(len(self.controller._ui_handler.latest_result.points), 72)
        self.assertEqual(self.window.mode, "idle")

    def test_terminal_event_does_not_unlock_before_worker_finishes(self):
        self.load_demo()
        self.controller._set_operation("live")
        with patch.object(self.controller._task_runner, "is_running", return_value=True):
            self.controller.emit(SweepCompleted(self.controller._ui_handler.latest_result.snapshot()))
            self.controller._process_events()
            self.assertEqual(self.window.mode, "live")
        self.controller._process_events()
        self.assertEqual(self.window.mode, "idle")

    def test_stop_before_runner_entry_persists_cancellation_and_connection_preserves_source(self):
        self.load_demo()
        for name in ("safety_limits_checked", "safety_connections_checked", "safety_output_checked"):
            getattr(self.vm, name).set(True)
        release, entered = threading.Event(), threading.Event()
        original_start = self.controller._task_runner.start

        def delayed_start(**kwargs):
            entered.set()
            release.wait(2)
            return original_start(**kwargs)

        with patch.object(self.controller._task_runner, "start", side_effect=delayed_start):
            self.controller.on_start()
            self.assertTrue(entered.wait(1))
            self.assertEqual(self.vm.source_mode.get(), "fixture")
            self.assertIn("No hardware", self.vm.fixture_badge_text.get())
            self.controller.on_stop()
            release.set()
            self.settle()
        self.ports_factory.assert_not_called()
        self.assertEqual(self.vm.source_mode.get(), "fixture")
        self.assertEqual(len(self.controller._ui_handler.latest_result.points), 72)

    def test_close_warning_is_persisted_without_late_dialog(self):
        self.controller._closing = True
        self.controller.emit(SweepWarning("AWG_OUTPUT_OFF_FAILED", "output off timed out"))
        self.controller._drain_event_queue()
        log_path = self.controller._event_log.path
        self.assertIn("AWG_OUTPUT_OFF_FAILED", log_path.read_text())
        self.warning.assert_not_called()

    def test_close_waits_for_shutdown_thread_and_persists_its_last_warning(self):
        entered, release = threading.Event(), threading.Event()

        def shutdown():
            entered.set()
            release.wait(2)
            self.controller.emit(SweepWarning("AWG_CLOSE_FAILED", "late cleanup warning"))

        with patch.object(self.controller._task_runner, "shutdown", side_effect=shutdown):
            self.controller.on_close()
            self.assertTrue(entered.wait(1))
            self.controller._process_events()
            self.assertFalse(self.window.destroyed)
            release.set()
            self.controller._shutdown_thread.join(1)
            self.controller._process_events()
        self.assertTrue(self.window.destroyed)
        self.assertIn("late cleanup warning", self.controller._event_log.path.read_text())

    def test_close_during_file_job_defers_destroy_and_skips_late_ui_update(self):
        release = threading.Event()
        self.addCleanup(release.set)
        callback = Mock()
        self.controller._start_job("loading", lambda: release.wait(2), callback)
        self.controller.on_close()
        self.controller._process_events()
        self.assertFalse(self.window.destroyed)
        release.set()
        self.settle()
        self.controller._process_events()
        self.assertTrue(self.window.destroyed)
        callback.assert_not_called()


if __name__ == "__main__":
    unittest.main()
