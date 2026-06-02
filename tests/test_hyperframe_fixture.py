from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
import unittest

import numpy as np
from scipy.io import loadmat

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.demo.hyperframe_fixture import (  # noqa: E402
    DEMO_LABEL,
    POINT_COUNT,
    SOURCE,
    build_fixture_curves,
    build_measurement_payload,
    write_fixture,
)
from app.infrastructure.persistence.measurement_loader import MeasurementLoader  # noqa: E402
from app.infrastructure.persistence.reference_repo_mat import MatReferenceRepository  # noqa: E402


class HyperframeFixtureTests(unittest.TestCase):
    def test_fixture_payload_has_demo_metadata_and_non_smooth_curve(self) -> None:
        curves = build_fixture_curves()
        payload = build_measurement_payload(curves)

        self.assertEqual(payload["source"], SOURCE)
        self.assertEqual(payload["demo_label"], DEMO_LABEL)
        self.assertEqual(payload["point_count"], POINT_COUNT)
        self.assertEqual(payload["correction_mode"], "dual")
        self.assertEqual(payload["trigger_mode"], "triggered")

        metadata = json.loads(str(payload["metadata_json"]))
        self.assertEqual(metadata["demo_fixture"]["source"], "mock_fixture")
        self.assertIn("No hardware", metadata["demo_fixture"]["validation_boundary"])

        freq = curves["freq_hz"]
        gain = curves["gain_db_corrected"]
        self.assertEqual(len(freq), POINT_COUNT)
        self.assertTrue(np.all(np.diff(freq) > 0.0))

        # The fixture should look measured, not like a perfectly smooth textbook curve.
        x = np.log10(freq)
        residual = gain - np.polyval(np.polyfit(x, gain, deg=5), x)
        self.assertGreater(float(np.std(residual)), 0.015)

    def test_written_fixture_loads_through_existing_measurement_and_reference_paths(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            paths = write_fixture(Path(td))
            loaded_mat = MeasurementLoader().load(str(paths["measurement_mat"]))
            loaded_csv = MeasurementLoader().load(str(paths["measurement_csv"]))
            reference = MatReferenceRepository().load_reference(str(paths["reference_mat"]))
            mat_payload = loadmat(paths["measurement_mat"])

        self.assertEqual(len(loaded_mat.result.points), POINT_COUNT)
        self.assertEqual(len(loaded_csv.result.points), POINT_COUNT)
        self.assertIsNotNone(loaded_mat.result.points[0].phase_deg)
        self.assertEqual(len(reference.freq_hz), POINT_COUNT)
        self.assertIsNotNone(reference.phase_deg)

        self.assertEqual(_mat_string(mat_payload["source"]), SOURCE)
        self.assertEqual(_mat_string(mat_payload["demo_label"]), DEMO_LABEL)
        self.assertIn("gain_db_raw", mat_payload)
        self.assertIn("gain_db_reference", mat_payload)
        self.assertIn("gain_db_corrected", mat_payload)

    def test_written_fixture_is_binary_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_paths = write_fixture(Path(first))
            second_paths = write_fixture(Path(second))

            self.assertEqual(
                first_paths["measurement_mat"].read_bytes(),
                second_paths["measurement_mat"].read_bytes(),
            )
            self.assertEqual(
                first_paths["reference_mat"].read_bytes(),
                second_paths["reference_mat"].read_bytes(),
            )


def _mat_string(value: object) -> str:
    arr = np.asarray(value)
    if arr.dtype.kind in {"U", "S"}:
        if arr.ndim == 2 and arr.shape[0] == 1:
            return "".join(str(item) for item in arr[0]).strip()
        return "".join(str(item) for item in arr.ravel()).strip()
    return str(arr.squeeze())


if __name__ == "__main__":
    unittest.main()
