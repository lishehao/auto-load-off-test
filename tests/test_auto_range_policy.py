from __future__ import annotations

import sys
from pathlib import Path
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.domain.auto_range import AutoRangePolicy


class AutoRangePolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = AutoRangePolicy()

    def test_expand_range_when_signal_near_clipping(self) -> None:
        decision = self.policy.decide(
            volts=np.array([-0.45, 0.45]),
            current_range_v=1.0,
            current_offset_v=0.0,
            requested_offset_v=0.0,
        )

        self.assertTrue(decision.changed)
        self.assertGreater(decision.target_range_v, 1.0)
        self.assertAlmostEqual(decision.target_offset_v, 0.0)

    def test_shrink_range_when_signal_small(self) -> None:
        decision = self.policy.decide(
            volts=np.array([-0.1, 0.1]),
            current_range_v=1.0,
            current_offset_v=0.0,
            requested_offset_v=0.0,
        )

        self.assertTrue(decision.changed)
        self.assertAlmostEqual(decision.target_range_v, 0.5, delta=1e-6)

    def test_adjust_offset_when_midpoint_drifts(self) -> None:
        decision = self.policy.decide(
            volts=np.array([0.35, 0.45, 0.55]),
            current_range_v=1.0,
            current_offset_v=0.0,
            requested_offset_v=0.0,
        )

        self.assertTrue(decision.changed)
        self.assertAlmostEqual(decision.target_offset_v, 0.45, delta=1e-6)


if __name__ == "__main__":
    unittest.main()
