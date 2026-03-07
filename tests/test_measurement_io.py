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


if __name__ == "__main__":
    unittest.main()
