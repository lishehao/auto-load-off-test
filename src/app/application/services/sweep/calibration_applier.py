from __future__ import annotations

import numpy as np

from app.application.dto import StartSweepCommand
from app.domain.calibration import apply_reference_to_point
from app.domain.enums import CorrectionMode, TriggerMode
from app.domain.models import SweepPoint


class CalibrationApplier:
    def apply(self, *, point: SweepPoint, cmd: StartSweepCommand) -> SweepPoint:
        if not cmd.calibration_enabled or cmd.reference_interpolator is None:
            return point

        run_mode = cmd.settings.run_mode
        use_phase = run_mode.correction_mode == CorrectionMode.DUAL or run_mode.trigger_mode == TriggerMode.TRIGGERED
        ref_value = cmd.reference_interpolator(np.array([point.freq_hz]))[0]
        return apply_reference_to_point(point, ref_value, use_phase=use_phase)
