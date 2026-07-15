from __future__ import annotations

from datetime import datetime
import sys
from pathlib import Path
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.application.dto import SaveArtifacts
from app.application.services.calibration_receipts import build_reference_receipt
from app.application.services.export_receipts import build_export_receipt
from app.domain.enums import CorrectionMode
from app.domain.models import ReferenceCurve, SweepPoint, SweepResult
from app.infrastructure.persistence.settings_defaults import DefaultSettingsFactory
from app.presentation.tk.ui_event_handler import UiEventHandler


class FakeVar:
    def __init__(self, value: str = "") -> None:
        self._value = value

    def get(self) -> str:
        return self._value

    def set(self, value: str) -> None:
        self._value = value


class ReceiptViewModel:
    def __init__(self) -> None:
        self.reference_receipt_text = FakeVar("No reference loaded")
        self.export_receipt_text = FakeVar("No export yet")
        self.event_history_text = FakeVar("No warnings or workflow events")
        self.source_mode = FakeVar("live")
        self.figure_mode = FakeVar("gain")
        self.magnitude_phase_mode = FakeVar("magnitude")
        self.plot_scale = FakeVar("auto")
        self.data_source_text = FakeVar("Live instrument path")
        self.fixture_badge_text = FakeVar("")
        self.validation_receipt_text = FakeVar("")
        self.run_state_text = FakeVar("Idle")
        self.progress_text = FakeVar("0 / 0")
        self.latest_frequency_text = FakeVar("-")
        self.elapsed_text = FakeVar("00:00")
        self.point_count_text = FakeVar("0 points")
        self.freq_unit = FakeVar("Hz")


class FakePlotWidget:
    def __init__(self) -> None:
        self.mode = "gain"
        self.updated = False

    def set_mode(self, mode: str) -> None:
        self.mode = mode

    def update_result(self, *_args) -> None:
        self.updated = True


class FakeWindow:
    def __init__(self) -> None:
        self.plot_widget = FakePlotWidget()
        self.connection_idle = False

    def set_connection_idle(self) -> None:
        self.connection_idle = True


class WorkflowReceiptTests(unittest.TestCase):
    def test_reference_receipt_reports_coverage_phase_and_active_correction(self) -> None:
        settings = DefaultSettingsFactory().create()
        settings.sweep.start_hz = 1_000.0
        settings.sweep.stop_hz = 1_000_000.0
        settings.run_mode.correction_mode = CorrectionMode.DUAL
        curve = ReferenceCurve(
            freq_hz=np.array([1_000.0, 10_000.0, 1_000_000.0]),
            gain_db=np.array([0.1, 0.2, 0.3]),
            phase_deg=np.array([1.0, 2.0, 3.0]),
        )

        receipt = build_reference_receipt(
            path=Path("/tmp/reference_fixture.mat"),
            curve=curve,
            settings=settings,
            calibration_enabled=True,
        )

        self.assertIn("Reference: reference_fixture.mat", receipt.summary)
        self.assertIn("1 kHz - 1 MHz", receipt.summary)
        self.assertIn("3 pts", receipt.summary)
        self.assertIn("phase yes", receipt.summary)
        self.assertIn("Correction: active", receipt.summary)
        self.assertIn("mode dual", receipt.summary)
        self.assertEqual(receipt.warnings, ())

    def test_reference_receipt_warns_when_sweep_exceeds_coverage(self) -> None:
        settings = DefaultSettingsFactory().create()
        settings.sweep.start_hz = 100.0
        settings.sweep.stop_hz = 2_000_000.0
        curve = ReferenceCurve(
            freq_hz=np.array([1_000.0, 1_000_000.0]),
            gain_db=np.array([0.0, 0.5]),
            phase_deg=None,
        )

        receipt = build_reference_receipt(
            path=Path("/tmp/reference.mat"),
            curve=curve,
            settings=settings,
            calibration_enabled=True,
        )

        self.assertIn("phase no", receipt.summary)
        self.assertTrue(any("outside reference coverage" in warning for warning in receipt.warnings))
        self.assertTrue(any("edge-clamped" in warning for warning in receipt.warnings))

    def test_export_receipt_lists_artifacts_and_no_hardware_boundary(self) -> None:
        settings = DefaultSettingsFactory().create()
        settings.run_mode.correction_mode = CorrectionMode.DUAL
        result = SweepResult(
            points=[
                SweepPoint(freq_hz=1_000.0, gain_linear=1.0, gain_db=0.0, phase_deg=1.0),
                SweepPoint(freq_hz=2_000.0, gain_linear=2.0, gain_db=6.0, phase_deg=2.0),
            ]
        )
        artifacts = SaveArtifacts(
            mat_path=Path("/tmp/out/measurement.mat"),
            csv_path=Path("/tmp/out/measurement.csv"),
            txt_path=Path("/tmp/out/measurement.txt"),
            gain_plot_path=Path("/tmp/out/measurement_gain.png"),
            db_plot_path=None,
        )

        receipt = build_export_receipt(
            artifacts=artifacts,
            settings=settings,
            result=result,
            source_text="Fixture replay · hyperframe_simulated_fixture.mat",
            fixture_badge_text="No hardware - simulated fixture",
            saved_at=datetime(2026, 6, 2, 9, 30, 0),
        )

        self.assertIn("measurement.mat", receipt.summary)
        self.assertIn("measurement.csv", receipt.summary)
        self.assertIn("measurement.txt", receipt.summary)
        self.assertIn("measurement_gain.png", receipt.summary)
        self.assertIn("correction=dual", receipt.summary)
        self.assertIn("points=2", receipt.summary)
        self.assertIn("2026-06-02 09:30:00", receipt.summary)
        self.assertIn("No hardware simulated fixture", receipt.summary)
        self.assertEqual(len(receipt.artifacts), 4)

    def test_ui_handler_updates_reference_export_and_event_history_state(self) -> None:
        vm = ReceiptViewModel()
        handler = UiEventHandler(window=object(), vm=vm)

        handler.set_reference_loaded(
            receipt_text="Reference: ref.mat\nCoverage: 1 kHz - 1 MHz · 2 pts · phase yes",
            warnings=("Sweep range is outside reference coverage.",),
        )
        handler.set_export_saved(receipt_text="Saved: measurement.mat\nArtifacts: measurement.mat")

        self.assertIn("Reference: ref.mat", vm.reference_receipt_text.get())
        self.assertIn("Saved: measurement.mat", vm.export_receipt_text.get())
        self.assertIn("Reference receipt updated", vm.event_history_text.get())
        self.assertIn("outside reference coverage", vm.event_history_text.get())
        self.assertIn("Export artifacts saved", vm.event_history_text.get())

    def test_fixture_source_uses_bode_defaults_and_neutral_connection_state(self) -> None:
        vm = ReceiptViewModel()
        window = FakeWindow()
        handler = UiEventHandler(window=window, vm=vm)
        handler.set_result(
            SweepResult(
                points=[SweepPoint(freq_hz=1_000.0, gain_linear=1.0, gain_db=0.0, phase_deg=0.0)]
            ),
            refresh_plot=False,
        )

        handler.set_fixture_source(
            label="Simulated no-hardware demo fixture",
            path_name="hyperframe_simulated_fixture.mat",
        )

        self.assertEqual(vm.source_mode.get(), "fixture")
        self.assertEqual(vm.figure_mode.get(), "gain_db")
        self.assertEqual(vm.magnitude_phase_mode.get(), "magnitude_phase")
        self.assertEqual(vm.plot_scale.get(), "log")
        self.assertTrue(window.connection_idle)
        self.assertEqual(window.plot_widget.mode, "gain_db")
        self.assertTrue(window.plot_widget.updated)


if __name__ == "__main__":
    unittest.main()
