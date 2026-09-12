from __future__ import annotations

import json
import sys
from pathlib import Path
import tempfile
import unittest

import numpy as np
from scipy.io import loadmat, savemat

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.application.dto import SaveTarget
from app.domain.data_validation import DataValidationError
from app.domain.models import SweepPoint, SweepResult
from app.infrastructure.persistence.measurement_exporter import MeasurementExporter
from app.infrastructure.persistence.measurement_loader import MeasurementLoader


def _result(**meta: object) -> SweepResult:
    return SweepResult(
        points=[
            SweepPoint(freq_hz=1_000.0, gain_linear=1.0, gain_db=0.0, phase_deg=2.0),
            SweepPoint(freq_hz=2_000.0, gain_linear=2.0, gain_db=6.020599913279624, phase_deg=4.0),
        ],
        meta=dict(meta),
    )


def _mat_text(value: object) -> str:
    array = np.asarray(value)
    if array.dtype.kind in {"U", "S"}:
        if array.ndim == 2 and array.shape[0] == 1:
            return "".join(str(item) for item in array[0]).strip()
        return "".join(str(item) for item in array.ravel()).strip()
    return str(array.squeeze())


class AnalysisMetadataTests(unittest.TestCase):
    def test_offline_mat_has_no_fabricated_setup(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            artifacts = MeasurementExporter().export(
                _result(source="offline-analysis", validation_boundary="offline only"),
                None,
                SaveTarget(base_path=Path(td) / "analysis", figures={}),
            )
            payload = loadmat(artifacts.mat_path)
            metadata = json.loads(_mat_text(payload["metadata_json"]))

        self.assertEqual(int(payload["schema_version"].squeeze()), 1)
        self.assertEqual(payload["correction_mode"].squeeze().item(), "unknown")
        self.assertNotIn("setup", metadata)
        self.assertEqual(metadata["result"]["source"], "offline-analysis")
        self.assertIn("exported_at_utc", metadata["export"])

    def test_mat_nested_result_metadata_round_trip_uses_actual_file_values(self) -> None:
        result = _result(
            source="analysis-source",
            validation_boundary="offline only",
            correction_mode="unknown",
            reference_correction="complex",
            analysis_id="analysis-42",
            dataset="canonical",
            source_file="old-name.mat",
            point_count=999,
            processing_note="restored",
        )
        with tempfile.TemporaryDirectory() as td:
            artifacts = MeasurementExporter().export(
                result, None, SaveTarget(base_path=Path(td) / "analysis", figures={})
            )
            loaded = MeasurementLoader().load(str(artifacts.mat_path))

        self.assertEqual(loaded.result.meta["source_file"], "analysis.mat")
        self.assertEqual(loaded.result.meta["point_count"], 2)
        self.assertEqual(loaded.result.meta["processing_note"], "restored")
        self.assertEqual(loaded.result.meta["reference_correction"], "complex")
        self.assertEqual(loaded.result.meta["analysis_id"], "analysis-42")
        self.assertEqual(loaded.result.meta["dataset"], "canonical")

    def test_csv_provenance_markers_round_trip(self) -> None:
        result = _result(
            source="analysis-source",
            validation_boundary="offline only",
            correction_mode="unknown",
            reference_correction="magnitude",
            analysis_id="analysis-7",
            dataset="raw",
        )
        with tempfile.TemporaryDirectory() as td:
            artifacts = MeasurementExporter().export(
                result, None, SaveTarget(base_path=Path(td) / "analysis", figures={})
            )
            loaded = MeasurementLoader().load(str(artifacts.csv_path))

        for key in (
            "source",
            "validation_boundary",
            "correction_mode",
            "reference_correction",
            "analysis_id",
            "dataset",
        ):
            self.assertEqual(loaded.result.meta[key], result.meta[key])

    def test_malformed_mat_metadata_json_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "malformed.mat"
            savemat(
                path,
                {
                    "freq_hz": [1_000.0],
                    "gain_linear": [1.0],
                    "gain_db": [0.0],
                    "metadata_json": "{not valid json",
                },
            )
            with self.assertRaisesRegex(DataValidationError, "metadata_json.*malformed"):
                MeasurementLoader().load(str(path))

    def test_csv_conflicting_provenance_is_rejected(self) -> None:
        for column in ("source", "reference_correction", "analysis_id", "dataset"):
            with self.subTest(column=column), tempfile.TemporaryDirectory() as td:
                path = Path(td) / "conflicting.csv"
                path.write_text(
                    "source,reference_correction,analysis_id,dataset,freq_hz,gain_db\n"
                    f"a,none,id-1,canonical,1000,0\n"
                    f"{'b' if column == 'source' else 'a'},"
                    f"{'magnitude' if column == 'reference_correction' else 'none'},"
                    f"{'id-2' if column == 'analysis_id' else 'id-1'},"
                    f"{'raw' if column == 'dataset' else 'canonical'},2000,1\n",
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(DataValidationError, "conflicting values"):
                    MeasurementLoader().load(str(path))

    def test_mat_conflicting_or_invalid_processing_metadata_is_rejected(self) -> None:
        for key in ("source", "reference_correction", "analysis_id", "dataset"):
            for nested_value in ("different", None, False, 7, ""):
                with self.subTest(key=key, value=nested_value), tempfile.TemporaryDirectory() as td:
                    path = Path(td) / "conflicting.mat"
                    savemat(path, {
                        "freq_hz": [1_000.0], "gain_db": [0.0], key: "original",
                        "metadata_json": json.dumps({"result": {key: nested_value}}),
                    })
                    with self.assertRaises(DataValidationError):
                        MeasurementLoader().load(str(path))

    def test_old_minimal_csv_remains_supported(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "minimal.csv"
            path.write_text("freq_hz,gain_db\n1000,0\n2000,6.020599913279624\n", encoding="utf-8")
            loaded = MeasurementLoader().load(str(path))

        self.assertEqual(len(loaded.result.points), 2)
        self.assertNotIn("source", loaded.result.meta)


if __name__ == "__main__":
    unittest.main()
