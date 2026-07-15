from __future__ import annotations

import numpy as np


def choose_frequency_scale(
    freq_hz: object,
    *,
    requested: str = "auto",
    sweep_is_log: bool = False,
) -> str:
    if requested not in {"auto", "linear", "log"}:
        raise ValueError(f"Unsupported frequency scale: {requested}")
    if requested != "auto":
        return requested

    freq = np.atleast_1d(np.asarray(freq_hz, dtype=float).squeeze())
    if freq.size == 0 or np.any(~np.isfinite(freq)) or np.any(freq <= 0.0):
        return "linear"
    if sweep_is_log:
        return "log"
    if freq.size < 3:
        return "linear"

    linear_steps = np.diff(freq)
    log_steps = np.diff(np.log10(freq))
    linear_cv = _coefficient_of_variation(linear_steps)
    log_cv = _coefficient_of_variation(log_steps)
    return "log" if log_cv <= 0.05 and log_cv < linear_cv else "linear"


def _coefficient_of_variation(values: np.ndarray) -> float:
    mean = float(np.mean(np.abs(values)))
    if mean == 0.0:
        return float("inf")
    return float(np.std(values) / mean)
