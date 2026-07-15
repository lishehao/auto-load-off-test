from __future__ import annotations

import sys
from pathlib import Path
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.domain.plotting import choose_frequency_scale


class PlottingPolicyTests(unittest.TestCase):
    def test_auto_detects_log_spaced_fixture_frequency(self) -> None:
        freq = np.geomspace(1_000.0, 1_000_000.0, 72)
        self.assertEqual(choose_frequency_scale(freq), "log")

    def test_auto_keeps_linear_spaced_frequency_linear(self) -> None:
        freq = np.linspace(1_000.0, 10_000.0, 20)
        self.assertEqual(choose_frequency_scale(freq), "linear")

    def test_sweep_mode_and_explicit_selection_override_detection(self) -> None:
        freq = np.linspace(1_000.0, 10_000.0, 20)
        self.assertEqual(choose_frequency_scale(freq, sweep_is_log=True), "log")
        self.assertEqual(choose_frequency_scale(freq, requested="log"), "log")
        self.assertEqual(choose_frequency_scale(np.geomspace(1.0, 100.0, 10), requested="linear"), "linear")

    def test_invalid_auto_data_falls_back_to_linear(self) -> None:
        self.assertEqual(choose_frequency_scale([0.0, 1.0, 2.0]), "linear")
        with self.assertRaisesRegex(ValueError, "Unsupported frequency scale"):
            choose_frequency_scale([1.0, 2.0], requested="decade")

    def test_requested_log_waits_for_first_frequency(self) -> None:
        self.assertEqual(choose_frequency_scale([], requested="log"), "linear")
        self.assertEqual(choose_frequency_scale([1_000.0], requested="log"), "log")


if __name__ == "__main__":
    unittest.main()
