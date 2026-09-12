from __future__ import annotations

import math
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.domain.enums import CorrectionMode, CouplingMode, ImpedanceMode, TriggerMode
from app.domain.models import ChannelSelection, OscSettings, SweepSpec
from app.domain.validators import (
    MAX_CAPTURE_POINTS,
    MAX_SWEEP_POINTS,
    ValidationError,
    validate_channels,
    validate_osc_settings,
    validate_settings,
    validate_sweep_spec,
)
from app.infrastructure.persistence.settings_defaults import DefaultSettingsFactory


class ValidatorNumericGuardTests(unittest.TestCase):
    def test_sweep_rejects_nonfinite_values(self) -> None:
        for field, value in (("start_hz", math.nan), ("stop_hz", math.inf), ("step_hz", math.nan)):
            with self.subTest(field=field):
                values = {"start_hz": 1.0, "stop_hz": 10.0, "step_hz": 1.0}
                values[field] = value
                with self.assertRaisesRegex(ValidationError, field):
                    validate_sweep_spec(SweepSpec(**values, step_count=None, is_log=False))

    def test_sweep_rejects_noninteger_count_and_software_overflow(self) -> None:
        with self.assertRaisesRegex(ValidationError, "integer"):
            validate_sweep_spec(SweepSpec(1.0, 10.0, None, 2.5, True))
        with self.assertRaisesRegex(ValidationError, "MAX_SWEEP_POINTS"):
            validate_sweep_spec(SweepSpec(1.0, 10.0, None, MAX_SWEEP_POINTS + 1, True))
        with self.assertRaisesRegex(ValidationError, "MAX_SWEEP_POINTS"):
            validate_sweep_spec(SweepSpec(1.0, 100_001.0, 0.1, None, False))

    def test_capture_points_and_offset_are_finite_and_bounded(self) -> None:
        base = dict(full_scale_v=1.0, offset_v=0.0, impedance=ImpedanceMode.R50, coupling=CouplingMode.DC)
        with self.assertRaisesRegex(ValidationError, "integer"):
            validate_osc_settings(OscSettings(points=100.5, **base))
        with self.assertRaisesRegex(ValidationError, "MAX_CAPTURE_POINTS"):
            validate_osc_settings(OscSettings(points=MAX_CAPTURE_POINTS + 1, **base))
        with self.assertRaisesRegex(ValidationError, "offset_v"):
            validate_osc_settings(OscSettings(points=100, offset_v=math.inf, full_scale_v=1.0,
                                               impedance=ImpedanceMode.R50, coupling=CouplingMode.DC))

    def test_channels_reject_nonpositive_noninteger_and_allow_optional_none(self) -> None:
        for field, value in (("awg_ch", 1.5), ("osc_test_ch", 0), ("osc_ref_ch", math.nan), ("osc_trig_ch", -1)):
            with self.subTest(field=field):
                channels = ChannelSelection(awg_ch=1, osc_test_ch=1, osc_ref_ch=None, osc_trig_ch=None)
                setattr(channels, field, value)
                with self.assertRaises(ValidationError):
                    validate_channels(channels, CorrectionMode.NONE, TriggerMode.FREE_RUN)

        validate_channels(ChannelSelection(1, 1, None, None), CorrectionMode.NONE, TriggerMode.FREE_RUN)

    def test_validate_settings_rejects_zero_or_negative_amplitude(self) -> None:
        for amplitude in (0.0, -1.0):
            with self.subTest(amplitude=amplitude):
                settings = DefaultSettingsFactory().create()
                settings.setup.awg_settings.amplitude_vpp = amplitude
                with self.assertRaisesRegex(ValidationError, "AWG amplitude"):
                    validate_settings(settings)


if __name__ == "__main__":
    unittest.main()
