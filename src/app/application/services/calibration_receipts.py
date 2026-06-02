from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.domain.models import AppSettings, ReferenceCurve


@dataclass(frozen=True, slots=True)
class ReferenceReceipt:
    summary: str
    warnings: tuple[str, ...] = ()


def build_reference_receipt(
    *,
    path: Path,
    curve: ReferenceCurve,
    settings: AppSettings | None,
    calibration_enabled: bool,
) -> ReferenceReceipt:
    freq = np.atleast_1d(np.asarray(curve.freq_hz, dtype=float).squeeze())
    phase = None if curve.phase_deg is None else np.atleast_1d(np.asarray(curve.phase_deg, dtype=float).squeeze())

    point_count = int(freq.size)
    phase_present = phase is not None and phase.size > 0 and bool(np.any(np.isfinite(phase)))
    coverage_text = "coverage unavailable"
    warnings: list[str] = []

    if point_count > 0:
        finite_freq = freq[np.isfinite(freq)]
        if finite_freq.size > 0:
            ref_min = float(np.min(finite_freq))
            ref_max = float(np.max(finite_freq))
            coverage_text = f"{_format_frequency(ref_min)} - {_format_frequency(ref_max)}"
            if ref_min == ref_max:
                warnings.append("Reference has one frequency; all sweep points use the same reference value.")
            if settings is not None:
                sweep_min = min(settings.sweep.start_hz, settings.sweep.stop_hz)
                sweep_max = max(settings.sweep.start_hz, settings.sweep.stop_hz)
                if sweep_min < ref_min or sweep_max > ref_max:
                    warnings.append(
                        "Sweep range is outside reference coverage; out-of-range points will use edge-clamped reference values."
                    )
        else:
            warnings.append("Reference frequency data has no finite values.")
    else:
        warnings.append("Reference frequency data is empty.")

    if settings is None:
        warnings.append("Sweep settings unavailable; reference coverage was not checked against the current sweep.")

    correction_text = "active" if calibration_enabled else "inactive"
    run_mode_text = settings.run_mode.correction_mode.value if settings is not None else "unknown"
    sweep_text = _format_sweep_range(settings) if settings is not None else "sweep unavailable"
    dir_text = str(path.parent) if str(path.parent) else "."

    summary = "\n".join(
        [
            f"Reference: {path.name}",
            f"Dir: {dir_text}",
            f"Coverage: {coverage_text} · {point_count} pts · phase {'yes' if phase_present else 'no'}",
            f"Correction: {correction_text} · mode {run_mode_text}",
            f"Sweep: {sweep_text}",
        ]
    )
    return ReferenceReceipt(summary=summary, warnings=tuple(warnings))


def _format_sweep_range(settings: AppSettings) -> str:
    return f"{_format_frequency(settings.sweep.start_hz)} - {_format_frequency(settings.sweep.stop_hz)}"


def _format_frequency(freq_hz: float) -> str:
    if abs(freq_hz) >= 1_000_000:
        return f"{freq_hz / 1_000_000:.3g} MHz"
    if abs(freq_hz) >= 1_000:
        return f"{freq_hz / 1_000:.3g} kHz"
    return f"{freq_hz:.3g} Hz"
