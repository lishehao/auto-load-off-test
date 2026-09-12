from __future__ import annotations

from collections.abc import Callable

import numpy as np
from scipy.interpolate import PchipInterpolator, make_interp_spline

from app.domain.data_validation import DataValidationError, normalize_reference_curve
from app.domain.models import ReferenceCurve, SweepPoint


def build_reference_interpolator(curve: ReferenceCurve) -> Callable[[np.ndarray], np.ndarray]:
    normalized = normalize_reference_curve(curve)
    freq = normalized.freq_hz
    gain_db = normalized.gain_db
    phase = normalized.phase_deg

    if phase is None or phase.size == 0:
        href = 10 ** (gain_db / 20.0)
    else:
        href = 10 ** (gain_db / 20.0) * np.exp(1j * np.deg2rad(phase))

    if freq.size == 1:
        h0 = href[0]

        def constant_interp(xs: np.ndarray) -> np.ndarray:
            x = _query_frequencies(xs)
            out = np.empty_like(x, dtype=np.complex128 if np.iscomplexobj(h0) else float)
            out[...] = h0
            return out

        return constant_interp

    spline_order = int(min(3, freq.size - 1))
    if np.iscomplexobj(href):
        spline_real = make_interp_spline(freq, href.real, k=spline_order)
        spline_imag = make_interp_spline(freq, href.imag, k=spline_order)

        def complex_interp(xs: np.ndarray) -> np.ndarray:
            x = _query_frequencies(xs)
            y = np.empty_like(x, dtype=np.complex128)
            lo = x < freq[0]
            hi = x > freq[-1]
            mid = ~(lo | hi)
            if np.any(mid):
                y[mid] = spline_real(x[mid]) + 1j * spline_imag(x[mid])
            if np.any(lo):
                y[lo] = href[0]
            if np.any(hi):
                y[hi] = href[-1]
            return y

        return complex_interp

    spline_mag = make_interp_spline(freq, np.abs(href), k=spline_order)

    def magnitude_interp(xs: np.ndarray) -> np.ndarray:
        x = _query_frequencies(xs)
        y = np.empty_like(x, dtype=float)
        lo = x < freq[0]
        hi = x > freq[-1]
        mid = ~(lo | hi)
        if np.any(mid):
            y[mid] = spline_mag(x[mid])
        if np.any(lo):
            y[lo] = float(np.abs(href[0]))
        if np.any(hi):
            y[hi] = float(np.abs(href[-1]))
        return y

    return magnitude_interp


def build_offline_reference_interpolator(curve: ReferenceCurve) -> Callable[[np.ndarray], np.ndarray]:
    """Build a stable hardware-free reference interpolator.

    The offline path interpolates gain in dB and phase in radians against
    ``log10(frequency)`` using PCHIP.  dB interpolation keeps the response
    strictly positive after conversion, while phase unwrapping avoids a
    discontinuity at +/-pi.  Queries are clamped to the reference endpoints;
    a single reference point becomes a constant response.
    """
    normalized = normalize_reference_curve(curve)
    freq = normalized.freq_hz
    gain_db = normalized.gain_db
    phase = normalized.phase_deg

    if freq.size == 1:
        magnitude = float(10.0 ** (gain_db[0] / 20.0))
        if phase is None:
            constant: float | complex = magnitude
        else:
            constant = magnitude * np.exp(1j * np.deg2rad(phase[0]))

        def constant_interp(xs: np.ndarray) -> np.ndarray:
            x = _query_frequencies(xs)
            out = np.empty_like(x, dtype=np.complex128 if isinstance(constant, complex) else float)
            out[...] = constant
            return out

        return constant_interp

    log_freq = np.log10(freq)
    gain_interp = PchipInterpolator(log_freq, gain_db)
    phase_interp = None
    if phase is not None:
        phase_interp = PchipInterpolator(log_freq, np.unwrap(np.deg2rad(phase)))

    def offline_interp(xs: np.ndarray) -> np.ndarray:
        query = _query_frequencies(xs)
        clamped = np.clip(query, freq[0], freq[-1])
        log_query = np.log10(clamped)
        interpolated_db = np.asarray(gain_interp(log_query), dtype=float)
        with np.errstate(over="ignore", under="ignore", invalid="ignore"):
            magnitude = np.power(10.0, interpolated_db / 20.0)
        if not np.all(np.isfinite(magnitude)) or np.any(magnitude <= 0.0):
            raise DataValidationError("Offline reference gain is not finite and strictly positive representable")
        if phase_interp is None:
            return magnitude
        interpolated_phase = np.asarray(phase_interp(log_query), dtype=float)
        response = magnitude * np.exp(1j * interpolated_phase)
        if not np.all(np.isfinite(response)) or np.any(np.abs(response) <= 0.0):
            raise DataValidationError("Offline reference response is not finite and non-zero")
        return response

    return offline_interp


def apply_reference_to_point(point: SweepPoint, ref_value: complex | float, use_phase: bool) -> SweepPoint:
    try:
        reference = complex(ref_value)
    except (TypeError, ValueError) as exc:
        raise DataValidationError("Reference response is not numeric") from exc
    if not np.isfinite(reference.real) or not np.isfinite(reference.imag) or abs(reference) <= 0.0:
        raise DataValidationError("Reference response must be finite and non-zero")
    ref_abs = float(abs(reference))

    if use_phase:
        if point.gain_complex is not None:
            raw = complex(point.gain_complex)
        elif point.phase_deg is not None:
            if not np.isfinite(point.phase_deg):
                raise DataValidationError("Measured phase must be finite for phase correction")
            raw = point.gain_linear * np.exp(1j * np.deg2rad(point.phase_deg))
        else:
            raise DataValidationError("Phase correction requires measured complex gain or phase")

        corrected = raw / reference
        _require_finite_nonzero_complex(corrected, "Corrected complex gain")
        gain_linear = float(np.abs(corrected))
        gain_db = float(20.0 * np.log10(gain_linear))
        phase_deg = float(np.degrees(np.angle(corrected)))
        return SweepPoint(
            freq_hz=point.freq_hz,
            gain_linear=gain_linear,
            gain_db=gain_db,
            phase_deg=phase_deg,
            gain_complex=complex(corrected),
        )

    gain_linear = float(point.gain_linear / ref_abs)
    if not np.isfinite(gain_linear) or gain_linear <= 0.0:
        raise DataValidationError("Corrected gain must be finite and positive")
    gain_db = float(20.0 * np.log10(gain_linear))
    gain_complex = None
    if point.gain_complex is not None:
        gain_complex = complex(point.gain_complex) / ref_abs
        _require_finite_nonzero_complex(gain_complex, "Corrected complex gain")
    return SweepPoint(
        freq_hz=point.freq_hz,
        gain_linear=gain_linear,
        gain_db=gain_db,
        phase_deg=point.phase_deg,
        gain_complex=gain_complex,
    )


def _query_frequencies(xs: object) -> np.ndarray:
    try:
        x = np.atleast_1d(np.asarray(xs, dtype=float))
    except (TypeError, ValueError) as exc:
        raise DataValidationError("Reference query frequencies are not numeric") from exc
    if not np.all(np.isfinite(x)):
        raise DataValidationError("Reference query frequencies must be finite")
    if np.any(x <= 0.0):
        raise DataValidationError("Reference query frequencies must be positive")
    return x


def _require_finite_nonzero_complex(value: complex, name: str) -> None:
    if not np.isfinite(value.real) or not np.isfinite(value.imag) or abs(value) <= 0.0:
        raise DataValidationError(f"{name} must be finite and non-zero")
