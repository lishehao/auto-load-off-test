from __future__ import annotations

from app.application.services.sweep.models import SweepPlan
from app.domain.models import AppSettings
from app.domain.sweep_engine import compute_sampling_window_s, generate_frequency_points


class SweepPlanner:
    def plan(self, settings: AppSettings) -> SweepPlan:
        return SweepPlan(freq_points=generate_frequency_points(settings.sweep))

    def compute_sampling_window_s(self, *, freq_hz: float, sample_rate_hz: float, points: int) -> float:
        return compute_sampling_window_s(freq_hz=freq_hz, sample_rate_hz=sample_rate_hz, points=points)
