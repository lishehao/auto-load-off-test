from __future__ import annotations

import sys
from pathlib import Path
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.domain.calibration import build_reference_interpolator
from app.domain.models import ReferenceCurve


class ReferenceInterpolatorTests(unittest.TestCase):
    def test_single_point_reference_returns_constant(self) -> None:
        interp = build_reference_interpolator(
            ReferenceCurve(freq_hz=np.array([1_000.0]), gain_db=np.array([6.0]), phase_deg=None)
        )

        values = interp(np.array([100.0, 1_000.0, 10_000.0]))

        self.assertTrue(np.allclose(values, values[0]))

    def test_magnitude_reference_clamps_out_of_range(self) -> None:
        interp = build_reference_interpolator(
            ReferenceCurve(freq_hz=np.array([1_000.0, 2_000.0]), gain_db=np.array([0.0, 6.0]), phase_deg=None)
        )

        values = interp(np.array([100.0, 1_500.0, 5_000.0]))

        self.assertAlmostEqual(float(values[0]), 1.0, delta=1e-9)
        self.assertAlmostEqual(float(values[-1]), 10 ** (6.0 / 20.0), delta=1e-9)

    def test_complex_reference_preserves_phase_and_clamps_edges(self) -> None:
        interp = build_reference_interpolator(
            ReferenceCurve(
                freq_hz=np.array([1_000.0, 2_000.0, 3_000.0]),
                gain_db=np.array([0.0, 0.0, 0.0]),
                phase_deg=np.array([0.0, 45.0, 90.0]),
            )
        )

        values = interp(np.array([500.0, 2_000.0, 4_000.0]))

        self.assertTrue(np.iscomplexobj(values))
        self.assertAlmostEqual(float(np.angle(values[0], deg=True)), 0.0, delta=1e-9)
        self.assertAlmostEqual(float(np.angle(values[1], deg=True)), 45.0, delta=1e-6)
        self.assertAlmostEqual(float(np.angle(values[2], deg=True)), 90.0, delta=1e-9)


if __name__ == "__main__":
    unittest.main()
