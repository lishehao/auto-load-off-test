from __future__ import annotations

import sys
from pathlib import Path
import tempfile
import unittest

from scipy.io import savemat

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.application.dto import SaveTarget
from app.domain.data_validation import DataValidationError, normalize_measurement_arrays
from app.domain.models import SweepPoint, SweepResult
from app.infrastructure.persistence.measurement_exporter import MeasurementExporter
from app.infrastructure.persistence.measurement_loader import MeasurementLoader
from app.infrastructure.persistence.reference_repo_mat import MatReferenceRepository
from app.infrastructure.persistence.settings_defaults import DefaultSettingsFactory


class DataValidationTests(unittest.TestCase):
    def test_measurement_frequency_must_be_positive_and_strictly_increasing(self) -> None:
        for freq, message in (
            ([0.0, 1_000.0], "must be positive"),
            ([1_000.0, 1_000.0], "strictly increasing"),
            ([2_000.0, 1_000.0], "strictly increasing"),
        ):
            with self.subTest(freq=freq):
                with self.assertRaisesRegex(DataValidationError, message):
                    normalize_measurement_arrays(
                        freq_hz=freq,
                        gain_linear=[1.0, 1.0],
                        gain_db=[0.0, 0.0],
                        phase_deg=None,
                    )

    def test_measurement_arrays_must_have_matching_lengths_and_finite_gain(self) -> None:
        with self.assertRaisesRegex(DataValidationError, "does not match frequency length"):
            normalize_measurement_arrays(
                freq_hz=[1_000.0, 2_000.0],
                gain_linear=[1.0],
                gain_db=[0.0, 0.0],
                phase_deg=None,
            )

        with self.assertRaisesRegex(DataValidationError, "gain_db contains NaN"):
            normalize_measurement_arrays(
                freq_hz=[1_000.0, 2_000.0],
                gain_linear=None,
                gain_db=[0.0, float("nan")],
                phase_deg=None,
            )

    def test_csv_requires_frequency_and_a_gain_column(self) -> None:
        loader = MeasurementLoader()
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bad.csv"
            path.write_text("gain_db\n0.0\n", encoding="utf-8")
            with self.assertRaisesRegex(DataValidationError, "missing required column: freq_hz"):
                loader.load(str(path))

            path.write_text("freq_hz,phase_deg\n1000,0\n", encoding="utf-8")
            with self.assertRaisesRegex(DataValidationError, "requires gain_linear or gain_db"):
                loader.load(str(path))

    def test_csv_can_compute_linear_gain_from_db_without_silent_zero_fill(self) -> None:
        loader = MeasurementLoader()
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "db_only.csv"
            path.write_text(
                "source,validation_boundary,freq_hz,gain_db,phase_deg\n"
                "mock_fixture,No hardware fixture,1000,0,\n"
                "mock_fixture,No hardware fixture,2000,6.020599913279624,10\n",
                encoding="utf-8",
            )
            loaded = loader.load(str(path))

        self.assertAlmostEqual(loaded.result.points[0].gain_linear, 1.0, delta=1e-9)
        self.assertAlmostEqual(loaded.result.points[1].gain_linear, 2.0, delta=1e-9)
        self.assertIsNone(loaded.result.points[0].phase_deg)
        self.assertEqual(loaded.result.meta["source"], "mock_fixture")
        self.assertIn("No hardware", loaded.result.meta["validation_boundary"])

    def test_csv_blank_required_gain_value_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "blank.csv"
            path.write_text("freq_hz,gain_db\n1000,\n", encoding="utf-8")
            with self.assertRaisesRegex(DataValidationError, "row 2 has no value for gain_db"):
                MeasurementLoader().load(str(path))

    def test_mat_measurement_and_reference_reject_length_or_order_errors(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            measurement = root / "bad_measurement.mat"
            savemat(measurement, {"freq_hz": [1_000.0, 2_000.0], "gain_db": [0.0]})
            with self.assertRaisesRegex(DataValidationError, "does not match frequency length"):
                MeasurementLoader().load(str(measurement))

            reference = root / "bad_reference.mat"
            savemat(reference, {"freq_hz": [1_000.0, 1_000.0], "gain_db": [0.0, 0.0]})
            with self.assertRaisesRegex(DataValidationError, "strictly increasing"):
                MatReferenceRepository().load_reference(str(reference))

    def test_export_rejects_invalid_result_before_writing_artifacts(self) -> None:
        result = SweepResult(
            points=[
                SweepPoint(freq_hz=2_000.0, gain_linear=1.0, gain_db=0.0),
                SweepPoint(freq_hz=1_000.0, gain_linear=1.0, gain_db=0.0),
            ]
        )
        with tempfile.TemporaryDirectory() as td:
            target = SaveTarget(base_path=Path(td) / "invalid", figures={})
            with self.assertRaisesRegex(DataValidationError, "strictly increasing"):
                MeasurementExporter().export(result, DefaultSettingsFactory().create(), target)
            self.assertFalse((Path(td) / "invalid.mat").exists())


if __name__ == "__main__":
    unittest.main()
