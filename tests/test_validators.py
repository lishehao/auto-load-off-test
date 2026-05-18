from __future__ import annotations

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.domain.enums import CouplingMode, CorrectionMode, ImpedanceMode, TriggerMode
from app.domain.models import ChannelSelection, OscSettings, SweepSpec
from app.domain.validators import (
    ValidationError,
    validate_channels,
    validate_osc_settings,
    validate_sweep_spec,
)


class ValidatorTests(unittest.TestCase):
    def test_log_sweep_requires_positive_step_count(self) -> None:
        spec = SweepSpec(start_hz=1.0, stop_hz=10.0, step_hz=None, step_count=0, is_log=True)

        with self.assertRaises(ValidationError):
            validate_sweep_spec(spec)

    def test_dual_correction_requires_reference_channel(self) -> None:
        channels = ChannelSelection(awg_ch=1, osc_test_ch=1, osc_ref_ch=None, osc_trig_ch=2)

        with self.assertRaises(ValidationError):
            validate_channels(channels, CorrectionMode.DUAL, TriggerMode.FREE_RUN)

    def test_triggered_mode_requires_trigger_channel(self) -> None:
        channels = ChannelSelection(awg_ch=1, osc_test_ch=1, osc_ref_ch=2, osc_trig_ch=None)

        with self.assertRaises(ValidationError):
            validate_channels(channels, CorrectionMode.NONE, TriggerMode.TRIGGERED)

    def test_50_ohm_ac_coupling_is_rejected(self) -> None:
        settings = OscSettings(
            full_scale_v=1.0,
            offset_v=0.0,
            points=1000,
            impedance=ImpedanceMode.R50,
            coupling=CouplingMode.AC,
        )

        with self.assertRaises(ValidationError):
            validate_osc_settings(settings)


if __name__ == "__main__":
    unittest.main()
