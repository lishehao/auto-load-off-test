from __future__ import annotations

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.application.services.sweep.planner import SweepPlanner
from app.domain.enums import ConnectionMode, CorrectionMode, CouplingMode, ImpedanceMode, MagnitudePhaseMode, TriggerMode
from app.domain.models import (
    AppSettings,
    AwgSettings,
    ChannelSelection,
    InstrumentEndpoint,
    InstrumentSetup,
    OscSettings,
    RunMode,
    SweepSpec,
)


def build_settings(*, is_log: bool) -> AppSettings:
    return AppSettings(
        schema_version=1,
        freq_unit="Hz",
        sweep=SweepSpec(
            start_hz=1.0,
            stop_hz=100.0 if is_log else 5.0,
            step_hz=None if is_log else 2.0,
            step_count=5 if is_log else None,
            is_log=is_log,
        ),
        run_mode=RunMode(
            correction_mode=CorrectionMode.NONE,
            trigger_mode=TriggerMode.FREE_RUN,
            auto_range=False,
            auto_reset=True,
        ),
        setup=InstrumentSetup(
            awg=InstrumentEndpoint(model="DSG4102", connect_mode=ConnectionMode.AUTO),
            osc=InstrumentEndpoint(model="MDO34", connect_mode=ConnectionMode.AUTO),
            channels=ChannelSelection(awg_ch=1, osc_test_ch=1, osc_ref_ch=2, osc_trig_ch=2),
            awg_settings=AwgSettings(amplitude_vpp=1.0, impedance=ImpedanceMode.R50),
            osc_settings=OscSettings(
                full_scale_v=1.0,
                offset_v=0.0,
                points=10_000,
                impedance=ImpedanceMode.R50,
                coupling=CouplingMode.DC,
            ),
        ),
        magnitude_phase_mode=MagnitudePhaseMode.MAG,
        auto_save_data=False,
    )


class SweepPlannerServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.planner = SweepPlanner()

    def test_linear_plan_matches_expected_points(self) -> None:
        plan = self.planner.plan(build_settings(is_log=False))
        self.assertEqual(plan.freq_points.tolist(), [1.0, 3.0, 5.0])
        self.assertEqual(plan.total_points, 3)

    def test_log_plan_uses_step_count(self) -> None:
        plan = self.planner.plan(build_settings(is_log=True))
        self.assertEqual(plan.total_points, 5)
        self.assertAlmostEqual(float(plan.freq_points[0]), 1.0)
        self.assertAlmostEqual(float(plan.freq_points[-1]), 100.0)

    def test_sampling_window_is_positive(self) -> None:
        window = self.planner.compute_sampling_window_s(freq_hz=1e3, sample_rate_hz=1e6, points=10_000)
        self.assertGreater(window, 0.0)


if __name__ == "__main__":
    unittest.main()
