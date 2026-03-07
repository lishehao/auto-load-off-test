from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(slots=True)
class AutoRangeDecision:
    changed: bool
    target_range_v: float
    target_offset_v: float


class AutoRangePolicy:
    def __init__(
        self,
        *,
        high_threshold: float = 0.85,
        low_threshold: float = 0.55,
        target_fill_ratio: float = 0.7,
        offset_threshold_ratio: float = 0.2,
    ) -> None:
        self._high_threshold = high_threshold
        self._low_threshold = low_threshold
        self._target_fill_ratio = target_fill_ratio
        self._offset_threshold_ratio = offset_threshold_ratio

    def decide(
        self,
        *,
        volts: np.ndarray,
        current_range_v: float,
        current_offset_v: float,
        requested_offset_v: float,
    ) -> AutoRangeDecision:
        if volts is None or len(volts) == 0 or current_range_v <= 0:
            return AutoRangeDecision(
                changed=False,
                target_range_v=float(current_range_v),
                target_offset_v=float(current_offset_v),
            )

        vmax = float(np.max(volts))
        vmin = float(np.min(volts))
        vpp = vmax - vmin
        midpoint = (vmax + vmin) / 2.0

        target_range = float(current_range_v)
        target_offset = float(requested_offset_v)
        ratio = vpp / current_range_v

        if ratio > self._high_threshold:
            target_range = vpp / self._target_fill_ratio
        elif 0.0 < ratio < self._low_threshold:
            target_range = max(vpp / self._target_fill_ratio, current_range_v * 0.5)

        if abs(midpoint - current_offset_v) > (current_range_v * self._offset_threshold_ratio):
            target_offset = midpoint

        range_changed = not np.isclose(target_range, current_range_v, rtol=1e-2, atol=1e-3)
        offset_changed = not np.isclose(target_offset, current_offset_v, rtol=1e-2, atol=1e-3)
        return AutoRangeDecision(
            changed=bool(range_changed or offset_changed),
            target_range_v=float(target_range),
            target_offset_v=float(target_offset),
        )
