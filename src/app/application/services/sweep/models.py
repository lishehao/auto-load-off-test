from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass(slots=True)
class SweepPlan:
    freq_points: np.ndarray

    @property
    def total_points(self) -> int:
        return int(len(self.freq_points))


@dataclass(slots=True)
class SweepServiceWarning:
    code: str
    message: str


@dataclass(slots=True)
class AcquiredPointData:
    actual_freq_hz: float
    read_amp_vpp: float
    test_times: np.ndarray
    test_volts: np.ndarray
    ref_times: np.ndarray | None = None
    ref_volts: np.ndarray | None = None
    warnings: list[SweepServiceWarning] = field(default_factory=list)
