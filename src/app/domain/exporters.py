from __future__ import annotations

from dataclasses import asdict

import numpy as np

from app.domain.models import AppSettings, SweepResult


def result_to_arrays(result: SweepResult) -> dict[str, np.ndarray]:
    freq = np.array([p.freq_hz for p in result.points], dtype=float)
    gain = np.array([p.gain_linear for p in result.points], dtype=float)
    gain_db = np.array([p.gain_db for p in result.points], dtype=float)

    phase_values = np.array(
        [np.nan if p.phase_deg is None else float(p.phase_deg) for p in result.points],
        dtype=float,
    )
    complex_real = np.array(
        [np.nan if p.gain_complex is None else float(p.gain_complex.real) for p in result.points],
        dtype=float,
    )
    complex_imag = np.array(
        [np.nan if p.gain_complex is None else float(p.gain_complex.imag) for p in result.points],
        dtype=float,
    )

    arrays: dict[str, np.ndarray] = {
        "freq_hz": freq,
        "gain_linear": gain,
        "gain_db": gain_db,
    }

    if np.any(~np.isnan(phase_values)):
        arrays["phase_deg"] = phase_values
    if np.any(~np.isnan(complex_real)) or np.any(~np.isnan(complex_imag)):
        arrays["gain_complex_real"] = complex_real
        arrays["gain_complex_imag"] = complex_imag
    return arrays


def settings_to_metadata(settings: AppSettings) -> dict[str, object]:
    data = asdict(settings)
    return {
        "schema_version": data["schema_version"],
        "freq_unit": data["freq_unit"],
        "sweep": data["sweep"],
        "run_mode": data["run_mode"],
        "setup": data["setup"],
        "magnitude_phase_mode": data["magnitude_phase_mode"],
    }
