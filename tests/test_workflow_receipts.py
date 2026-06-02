from __future__ import annotations

from datetime import datetime
import sys
from pathlib import Path
import tkinter as tk
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
from app.presentation.tk.view_model import ViewModel


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
        root = tk.Tcl()
        vm = ViewModel(root)
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


if __name__ == "__main__":
    unittest.main()
