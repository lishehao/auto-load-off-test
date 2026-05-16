from __future__ import annotations

import math
import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.application.dto import SaveTarget
from app.domain.models import SweepPoint, SweepResult
from app.infrastructure.persistence.measurement_exporter import MeasurementExporter
from app.infrastructure.persistence.measurement_loader import MeasurementLoader
from app.infrastructure.persistence.settings_defaults import DefaultSettingsFactory


class MeasurementIOTests(unittest.TestCase):
    def test_export_and_load_round_trip_for_mat_and_csv(self) -> None:
        settings = DefaultSettingsFactory().create()
        result = SweepResult(
            points=[
                SweepPoint(freq_hz=1_000.0, gain_linear=1.0, gain_db=0.0, phase_deg=5.0),
                SweepPoint(freq_hz=2_000.0, gain_linear=2.0, gain_db=20.0 * math.log10(2.0), phase_deg=10.0),
            ]
        )
        exporter = MeasurementExporter()
        loader = MeasurementLoader()

        with tempfile.TemporaryDirectory() as td:
            artifacts = exporter.export(
                result=result,
                settings=settings,
                target=SaveTarget(base_path=Path(td) / "measurement", include_timestamp=False, figures={}),
            )

            loaded_mat = loader.load(str(artifacts.mat_path))
            loaded_csv = loader.load(str(artifacts.csv_path))

        self.assertEqual(len(loaded_mat.result.points), 2)
        self.assertEqual(len(loaded_csv.result.points), 2)
        self.assertAlmostEqual(loaded_mat.result.points[1].gain_linear, 2.0, delta=1e-6)
        self.assertAlmostEqual(loaded_csv.result.points[1].phase_deg or 0.0, 10.0, delta=1e-6)

    def test_sparse_phase_values_keep_row_alignment(self) -> None:
        settings = DefaultSettingsFactory().create()
        result = SweepResult(
            points=[
                SweepPoint(freq_hz=1_000.0, gain_linear=1.0, gain_db=0.0, phase_deg=None),
                SweepPoint(freq_hz=2_000.0, gain_linear=2.0, gain_db=20.0 * math.log10(2.0), phase_deg=10.0),
            ]
        )
        exporter = MeasurementExporter()
        loader = MeasurementLoader()

        with tempfile.TemporaryDirectory() as td:
            artifacts = exporter.export(
                result=result,
                settings=settings,
                target=SaveTarget(base_path=Path(td) / "measurement", include_timestamp=False, figures={}),
            )
            loaded_csv = loader.load(str(artifacts.csv_path))
            csv_text = artifacts.csv_path.read_text(encoding="utf-8")

        self.assertIsNone(loaded_csv.result.points[0].phase_deg)
        self.assertAlmostEqual(loaded_csv.result.points[1].phase_deg or 0.0, 10.0, delta=1e-6)
        self.assertIn("1000.0,1.0,0.0,", csv_text)

    def test_demo_data_mat_files_load(self) -> None:
        loader = MeasurementLoader()
        demo_dir = Path(__file__).resolve().parents[1] / "demo_data"

        raw = loader.load(str(demo_dir / "Deme(1).mat"))
        corrected = loader.load(str(demo_dir / "Demo(2).mat"))

        self.assertEqual(len(raw.result.points), 15)
        self.assertEqual(len(corrected.result.points), 50)
        self.assertIsNone(raw.result.points[0].phase_deg)
        self.assertIsNotNone(corrected.result.points[0].phase_deg)
        self.assertGreater(raw.result.points[0].gain_linear, 0.0)


if __name__ == "__main__":
    unittest.main()
