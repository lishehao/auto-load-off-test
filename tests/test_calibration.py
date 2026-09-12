from __future__ import annotations

import sys
from pathlib import Path
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.domain.calibration import (
    apply_reference_to_point,
    build_offline_reference_interpolator,
    build_reference_interpolator,
)
from app.domain.data_validation import DataValidationError
from app.domain.models import ReferenceCurve, SweepPoint


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

    def test_offline_pchip_preserves_sparse_notch_as_positive_response(self) -> None:
        interp = build_offline_reference_interpolator(
            ReferenceCurve(
                freq_hz=np.array([100.0, 1_000.0, 10_000.0]),
                gain_db=np.array([0.0, -40.0, 0.0]),
                phase_deg=None,
            )
        )

        values = interp(np.array([100.0, 300.0, 1_000.0, 3_000.0, 10_000.0]))

        self.assertTrue(np.all(np.isfinite(values)))
        self.assertTrue(np.all(values > 0.0))
        np.testing.assert_allclose(interp(np.array([100.0, 1_000.0, 10_000.0])), 10 ** (np.array([0.0, -40.0, 0.0]) / 20.0))

    def test_offline_interpolator_unwraps_phase_and_matches_exact_nodes(self) -> None:
        curve = ReferenceCurve(
            freq_hz=np.array([1_000.0, 2_000.0, 4_000.0]),
            gain_db=np.array([0.0, 6.0, 12.0]),
            phase_deg=np.array([170.0, -170.0, -160.0]),
        )
        interp = build_offline_reference_interpolator(curve)

        values = interp(curve.freq_hz)

        np.testing.assert_allclose(np.abs(values), 10 ** (curve.gain_db / 20.0))
        np.testing.assert_allclose(
            values / np.abs(values),
            np.exp(1j * np.unwrap(np.deg2rad(curve.phase_deg))),
            atol=1e-10,
        )

    def test_reference_query_frequencies_must_be_finite_and_positive(self) -> None:
        interp = build_offline_reference_interpolator(
            ReferenceCurve(freq_hz=np.array([1_000.0, 2_000.0]), gain_db=np.array([0.0, 6.0]))
        )
        for query in ([0.0], [np.nan], [np.inf]):
            with self.subTest(query=query):
                with self.assertRaisesRegex(DataValidationError, "query frequencies"):
                    interp(np.array(query))

    def test_apply_magnitude_correction_synchronizes_complex_gain(self) -> None:
        raw_complex = 2.0 * np.exp(1j * np.deg2rad(30.0))
        corrected = apply_reference_to_point(
            SweepPoint(
                freq_hz=1_000.0,
                gain_linear=2.0,
                gain_db=6.020599913,
                phase_deg=30.0,
                gain_complex=complex(raw_complex),
            ),
            2.0,
            use_phase=False,
        )

        self.assertAlmostEqual(corrected.gain_linear, 1.0, delta=1e-12)
        self.assertAlmostEqual(abs(corrected.gain_complex), 1.0, delta=1e-12)
        self.assertAlmostEqual(float(np.angle(corrected.gain_complex, deg=True)), 30.0, delta=1e-10)
        self.assertEqual(corrected.phase_deg, 30.0)

    def test_apply_phase_correction_requires_measured_phase_or_complex_gain(self) -> None:
        point = SweepPoint(freq_hz=1_000.0, gain_linear=1.0, gain_db=0.0)
        with self.assertRaisesRegex(DataValidationError, "requires measured complex gain or phase"):
            apply_reference_to_point(point, 1.0, use_phase=True)

    def test_apply_rejects_zero_reference_and_zero_or_nonfinite_results(self) -> None:
        point = SweepPoint(freq_hz=1_000.0, gain_linear=1.0, gain_db=0.0)
        for reference in (0.0, complex(np.nan, 0.0), complex(np.inf, 0.0)):
            with self.subTest(reference=reference):
                with self.assertRaisesRegex(DataValidationError, "Reference response"):
                    apply_reference_to_point(point, reference, use_phase=False)

        for invalid_gain in (0.0, np.inf):
            with self.subTest(invalid_gain=invalid_gain):
                invalid_point = SweepPoint(freq_hz=1_000.0, gain_linear=invalid_gain, gain_db=0.0)
                with self.assertRaisesRegex(DataValidationError, "Corrected gain"):
                    apply_reference_to_point(invalid_point, 1.0, use_phase=False)


if __name__ == "__main__":
    unittest.main()
