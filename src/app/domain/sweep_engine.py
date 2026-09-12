from __future__ import annotations

import numpy as np

from app.domain.models import SweepSpec


MAX_SWEEP_POINTS = 100_000


def generate_frequency_points(spec: SweepSpec) -> np.ndarray:
    try:
        start_hz = float(spec.start_hz)
        stop_hz = float(spec.stop_hz)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Sweep frequencies must be finite and numeric") from exc
    if not np.isfinite(start_hz) or not np.isfinite(stop_hz) or start_hz <= 0 or stop_hz <= 0:
        raise ValueError("Sweep frequencies must be finite and positive")
    if stop_hz < start_hz:
        raise ValueError("Sweep frequencies must be ordered")

    if spec.is_log:
        if spec.step_count is None or isinstance(spec.step_count, bool):
            raise ValueError("Logarithmic sweep requires a positive integer step_count")
        step_count_float = float(spec.step_count)
        if not np.isfinite(step_count_float) or not step_count_float.is_integer() or step_count_float <= 0:
            raise ValueError("Logarithmic sweep requires a positive integer step_count")
        step_count = int(step_count_float)
        if step_count > MAX_SWEEP_POINTS:
            raise ValueError(f"Sweep exceeds software guard MAX_SWEEP_POINTS={MAX_SWEEP_POINTS}")
        return np.logspace(np.log10(start_hz), np.log10(stop_hz), step_count)

    step_hz = float(spec.step_hz or 0.0)
    if not np.isfinite(step_hz) or step_hz <= 0:
        raise ValueError("Linear sweep requires step_hz > 0")

    if np.isclose(start_hz, stop_hz):
        return np.array([start_hz], dtype=float)

    count = estimate_linear_sweep_points(start_hz, stop_hz, step_hz)
    if count > MAX_SWEEP_POINTS:
        raise ValueError(f"Sweep exceeds software guard MAX_SWEEP_POINTS={MAX_SWEEP_POINTS}")
    points = start_hz + step_hz * np.arange(count, dtype=float)
    # Multiplication can round the final in-range point one ulp above stop.
    return np.minimum(points, stop_hz)


def estimate_linear_sweep_points(start_hz: float, stop_hz: float, step_hz: float) -> int:
    """Estimate inclusive linear points without allocating a frequency array."""
    if np.isclose(start_hz, stop_hz):
        return 1
    ratio = (stop_hz - start_hz) / step_hz
    if not np.isfinite(ratio) or ratio < 0:
        raise ValueError("Linear sweep frequencies must be finite and ordered")
    # A relative floating-point allowance includes an intended endpoint such
    # as 0.3/0.1 without introducing an absolute-frequency overshoot.
    ratio_tolerance = 8.0 * np.finfo(float).eps * max(1.0, abs(ratio))
    return int(np.floor(ratio + ratio_tolerance)) + 1


def compute_sampling_window_s(
    freq_hz: float,
    sample_rate_hz: float,
    points: int,
    *,
    min_window_s: float = 1e-6,
    min_cycles: int = 10,
    max_points: int = 10_000_000,
) -> float:
    freq = max(float(freq_hz), 1e-12)
    sr = max(float(sample_rate_hz), 1.0)
    target = max(points / sr, min_cycles / freq, min_window_s)
    if max_points > 0:
        target = min(target, max_points / sr)
    return target
