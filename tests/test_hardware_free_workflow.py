from __future__ import annotations

import json
import sys
from pathlib import Path
import tempfile
import unittest

import numpy as np
from scipy.io import loadmat

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.application.dto import SaveTarget
from app.application.services.export_receipts import build_export_receipt
from app.demo.hyperframe_fixture import POINT_COUNT, build_fixture_settings
from app.domain.calibration import apply_reference_to_point, build_reference_interpolator
from app.domain.models import SweepPoint, SweepResult
from app.infrastructure.persistence.measurement_exporter import MeasurementExporter
from app.infrastructure.persistence.measurement_loader import MeasurementLoader
from app.infrastructure.persistence.reference_repo_mat import MatReferenceRepository


class HardwareFreeWorkflowTests(unittest.TestCase):
    def test_fixture_reference_correction_export_and_reload_end_to_end(self) -> None:
        demo_dir = Path(__file__).resolve().parents[1] / "demo_data"
        fixture_path = demo_dir / "hyperframe_simulated_fixture.mat"
        reference_path = demo_dir / "hyperframe_reference_fixture.mat"

        loaded = MeasurementLoader().load(str(fixture_path))
        reference = MatReferenceRepository().load_reference(str(reference_path))
        interpolator = build_reference_interpolator(reference)
        raw = loaded.raw_payload

        freq = _array(raw, "freq_hz")
        raw_gain_db = _array(raw, "gain_db_raw")
        raw_phase_deg = _array(raw, "phase_deg_raw")
        expected_gain_db = _array(raw, "gain_db_corrected")
        expected_phase_deg = _array(raw, "phase_deg_corrected")

        corrected_points: list[SweepPoint] = []
        for freq_hz, gain_db, phase_deg in zip(freq, raw_gain_db, raw_phase_deg, strict=True):
            gain_linear = float(10.0 ** (gain_db / 20.0))
            gain_complex = gain_linear * np.exp(1j * np.deg2rad(phase_deg))
            raw_point = SweepPoint(
                freq_hz=float(freq_hz),
                gain_linear=gain_linear,
                gain_db=float(gain_db),
                phase_deg=float(phase_deg),
                gain_complex=complex(gain_complex),
            )
            corrected_points.append(
                apply_reference_to_point(
                    raw_point,
                    interpolator(np.array([freq_hz], dtype=float))[0],
                    use_phase=True,
                )
            )

        corrected = SweepResult(points=corrected_points, meta=dict(loaded.result.meta))
        corrected.meta["reference_file"] = reference_path.name
        corrected.meta["correction_mode"] = "dual"

        self.assertEqual(len(corrected.points), POINT_COUNT)
        np.testing.assert_allclose(
            np.array([point.gain_db for point in corrected.points]),
            expected_gain_db,
            atol=1e-8,
        )
        phase_delta = _phase_delta(
            np.array([point.phase_deg for point in corrected.points], dtype=float),
            expected_phase_deg,
        )
        np.testing.assert_allclose(phase_delta, np.zeros_like(phase_delta), atol=1e-8)

        settings = build_fixture_settings()
        with tempfile.TemporaryDirectory() as td:
            artifacts = MeasurementExporter().export(
                corrected,
                settings,
                SaveTarget(base_path=Path(td) / "corrected_fixture", figures={}),
            )
            reloaded_mat = MeasurementLoader().load(str(artifacts.mat_path))
            reloaded_csv = MeasurementLoader().load(str(artifacts.csv_path))
            mat_payload = loadmat(artifacts.mat_path)
            txt_header = artifacts.txt_path.read_text(encoding="utf-8").splitlines()[0]

            receipt = build_export_receipt(
                artifacts=artifacts,
                settings=settings,
                result=corrected,
                source_text="Fixture replay · hyperframe_simulated_fixture.mat",
                fixture_badge_text="No hardware - simulated fixture",
            )

        for reloaded in (reloaded_mat, reloaded_csv):
            self.assertEqual(len(reloaded.result.points), POINT_COUNT)
            np.testing.assert_allclose(
                np.array([point.gain_db for point in reloaded.result.points]),
                expected_gain_db,
                atol=1e-8,
            )
            self.assertEqual(reloaded.result.meta["source"], "mock_fixture")
            self.assertIn("not live hardware validation", reloaded.result.meta["validation_boundary"])

        metadata = json.loads(_mat_text(mat_payload["metadata_json"]))
        self.assertEqual(metadata["export"]["source"], "mock_fixture")
        self.assertEqual(metadata["export"]["point_count"], POINT_COUNT)
        self.assertIn("not live hardware validation", metadata["export"]["validation_boundary"])
        self.assertEqual(txt_header, "freq_hz\tgain_linear\tgain_db\tphase_deg")
        self.assertIn("No hardware simulated fixture", receipt.summary)


def _array(payload: dict[str, object], key: str) -> np.ndarray:
    return np.atleast_1d(np.asarray(payload[key], dtype=float).squeeze())


def _phase_delta(actual: np.ndarray, expected: np.ndarray) -> np.ndarray:
    return (actual - expected + 180.0) % 360.0 - 180.0


def _mat_text(value: object) -> str:
    array = np.asarray(value)
    if array.dtype.kind in {"U", "S"}:
        if array.ndim == 2 and array.shape[0] == 1:
            return "".join(str(item) for item in array[0]).strip()
        return "".join(str(item) for item in array.ravel()).strip()
    return str(array.squeeze())


if __name__ == "__main__":
    unittest.main()
