from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.domain.models import ReferenceCurve, SweepResult


class DataValidationError(ValueError):
    """Raised when imported or exported measurement data is structurally unsafe."""


@dataclass(frozen=True, slots=True)
class MeasurementArrays:
    freq_hz: np.ndarray
    gain_linear: np.ndarray
    gain_db: np.ndarray
    phase_deg: np.ndarray | None


def normalize_measurement_arrays(
    *,
    freq_hz: object,
    gain_linear: object | None,
    gain_db: object | None,
    phase_deg: object | None,
) -> MeasurementArrays:
    freq = _vector("frequency", freq_hz)
    if freq.size == 0:
        raise DataValidationError("Measurement frequency data is empty")
    if not np.all(np.isfinite(freq)):
        raise DataValidationError("Measurement frequency contains NaN or infinity")
    if np.any(freq <= 0.0):
        raise DataValidationError("Measurement frequency values must be positive")
    if freq.size > 1 and np.any(np.diff(freq) <= 0.0):
        raise DataValidationError("Measurement frequency values must be strictly increasing without duplicates")

    linear = None if gain_linear is None else _vector("gain_linear", gain_linear)
    db = None if gain_db is None else _vector("gain_db", gain_db)
    if linear is None and db is None:
        raise DataValidationError("Measurement requires gain_linear or gain_db data")

    if linear is not None:
        _require_length("gain_linear", linear, freq.size)
        if not np.all(np.isfinite(linear)):
            raise DataValidationError("Measurement gain_linear contains NaN or infinity")
        if np.any(linear <= 0.0):
            raise DataValidationError("Measurement gain_linear values must be positive")

    if db is not None:
        _require_length("gain_db", db, freq.size)
        if not np.all(np.isfinite(db)):
            raise DataValidationError("Measurement gain_db contains NaN or infinity")

    if linear is None:
        assert db is not None
        linear = np.power(10.0, db / 20.0)
    if db is None:
        db = 20.0 * np.log10(linear)

    phase = None if phase_deg is None else _vector("phase_deg", phase_deg)
    if phase is not None:
        _require_length("phase_deg", phase, freq.size)
        if np.any(np.isinf(phase)):
            raise DataValidationError("Measurement phase_deg contains infinity")
        if np.all(np.isnan(phase)):
            phase = None

    return MeasurementArrays(freq_hz=freq, gain_linear=linear, gain_db=db, phase_deg=phase)


def normalize_reference_curve(curve: ReferenceCurve) -> ReferenceCurve:
    freq = _vector("reference frequency", curve.freq_hz)
    gain_db = _vector("reference gain_db", curve.gain_db)
    if freq.size == 0:
        raise DataValidationError("Reference frequency data is empty")
    _require_length("reference gain_db", gain_db, freq.size)
    if not np.all(np.isfinite(freq)):
        raise DataValidationError("Reference frequency contains NaN or infinity")
    if np.any(freq <= 0.0):
        raise DataValidationError("Reference frequency values must be positive")
    if freq.size > 1 and np.any(np.diff(freq) <= 0.0):
        raise DataValidationError("Reference frequency values must be strictly increasing without duplicates")
    if not np.all(np.isfinite(gain_db)):
        raise DataValidationError("Reference gain_db contains NaN or infinity")

    phase = None if curve.phase_deg is None else _vector("reference phase_deg", curve.phase_deg)
    if phase is not None:
        _require_length("reference phase_deg", phase, freq.size)
        if not np.all(np.isfinite(phase)):
            raise DataValidationError("Reference phase_deg contains NaN or infinity")

    return ReferenceCurve(freq_hz=freq, gain_db=gain_db, phase_deg=phase)


def validate_sweep_result(result: SweepResult) -> MeasurementArrays:
    phase = np.array(
        [np.nan if point.phase_deg is None else float(point.phase_deg) for point in result.points],
        dtype=float,
    )
    return normalize_measurement_arrays(
        freq_hz=np.array([point.freq_hz for point in result.points], dtype=float),
        gain_linear=np.array([point.gain_linear for point in result.points], dtype=float),
        gain_db=np.array([point.gain_db for point in result.points], dtype=float),
        phase_deg=phase,
    )


def _vector(name: str, value: object) -> np.ndarray:
    try:
        array = np.asarray(value, dtype=float).squeeze()
    except (TypeError, ValueError) as exc:
        raise DataValidationError(f"{name} is not numeric") from exc
    if array.ndim > 1:
        raise DataValidationError(f"{name} must be a one-dimensional array")
    return np.atleast_1d(array)


def _require_length(name: str, values: np.ndarray, expected: int) -> None:
    if values.size != expected:
        raise DataValidationError(f"{name} length {values.size} does not match frequency length {expected}")
