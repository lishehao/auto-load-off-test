from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from app.application.dto import LoadedMeasurement
from app.domain.calibration import apply_reference_to_point, build_offline_reference_interpolator
from app.domain.data_validation import (
    DataValidationError,
    normalize_measurement_arrays,
    normalize_reference_curve,
    validate_sweep_result,
)
from app.domain.models import ReferenceCurve, SweepPoint, SweepResult


@dataclass(frozen=True, slots=True)
class AnalysisOptions:
    correction: str = "none"
    coverage: str = "reject"
    dataset: str = "canonical"


@dataclass(slots=True)
class AnalysisResult:
    measurement: SweepResult
    input_measurement: SweepResult
    reference: ReferenceCurve | None
    options: AnalysisOptions
    outside_reference_count: int
    warnings: tuple[str, ...]


class AnalyzeMeasurementUseCase:
    def execute(
        self,
        loaded: LoadedMeasurement,
        *,
        reference: ReferenceCurve | None = None,
        options: AnalysisOptions = AnalysisOptions(),
    ) -> AnalysisResult:
        if options.correction not in {"none", "magnitude", "complex"}:
            raise DataValidationError(f"Unknown correction: {options.correction}")
        if options.coverage not in {"reject", "clamp"} or options.dataset not in {"canonical", "raw"}:
            raise DataValidationError("Unknown coverage or dataset selection")
        if (reference is None) != (options.correction == "none"):
            raise DataValidationError("A reference and magnitude/complex correction must be supplied together")

        measurement = _select_measurement(loaded, options.dataset)
        arrays = validate_sweep_result(measurement)
        warnings: list[str] = []
        outside_count = 0
        points = [replace(point) for point in measurement.points]
        if reference is not None:
            if measurement.meta.get("reference_correction", "none") != "none":
                raise DataValidationError("Input is already reference-corrected; select raw MAT arrays or original data")
            reference = normalize_reference_curve(reference)
            outside_count = int(np.count_nonzero(
                (arrays.freq_hz < reference.freq_hz[0]) | (arrays.freq_hz > reference.freq_hz[-1])
            ))
            if outside_count and options.coverage == "reject":
                raise DataValidationError(
                    f"{outside_count} measurement points are outside reference coverage; "
                    "use --coverage clamp only when endpoint clamping is intended"
                )
            if outside_count:
                warnings.append(f"{outside_count} points use edge-clamped reference values outside coverage.")
            if reference.freq_hz.size == 1:
                warnings.append("Single-point reference: a constant reference value is used.")
            if options.correction == "complex":
                if reference.phase_deg is None:
                    raise DataValidationError("Complex correction requires reference phase data")
                if arrays.phase_deg is None or not np.all(np.isfinite(arrays.phase_deg)):
                    raise DataValidationError("Complex correction requires measured phase at every input point")
            reference_values = build_offline_reference_interpolator(reference)(arrays.freq_hz)
            points = [
                apply_reference_to_point(point, value, use_phase=options.correction == "complex")
                for point, value in zip(points, reference_values, strict=True)
            ]

        if arrays.phase_deg is None:
            warnings.append("Input has no measured phase; no phase has been inferred.")
        elif not np.all(np.isfinite(arrays.phase_deg)):
            warnings.append("Input phase is incomplete; gaps remain missing in the output and plot.")
        warnings.append("Input acquisition provenance is file-supplied and has not been independently verified.")
        meta = dict(measurement.meta)
        # Preserve prior correction state through a pass-through export.
        meta["reference_correction"] = (
            options.correction if reference is not None else meta.get("reference_correction", "none")
        )
        meta.update({
            "dataset": options.dataset,
            "source": meta.get("source") or "unknown",
            "processing": "offline_analysis",
            "live_hardware_used": False,
            "interpolation": "pchip_log_frequency_db_unwrapped_phase" if reference is not None else "none",
            "coverage_policy": options.coverage,
            "outside_reference_count": outside_count,
        })
        output = SweepResult(points=points, meta=meta)
        validate_sweep_result(output)
        return AnalysisResult(output, measurement, reference, options, outside_count, tuple(warnings))


def _select_measurement(loaded: LoadedMeasurement, dataset: str) -> SweepResult:
    meta = dict(loaded.result.meta)
    if dataset == "canonical":
        # The checked-in Hyperframe fixture declares corrected canonical arrays separately from raw arrays.
        if meta.get("source") == "mock_fixture" and "gain_db_corrected" in loaded.raw_payload:
            meta.setdefault("reference_correction", "fixture_corrected")
        return SweepResult([replace(point) for point in loaded.result.points], meta)

    payload = loaded.raw_payload
    raw_linear = payload.get("gain_linear_raw", payload.get("gain_raw"))
    raw_db = payload.get("gain_db_raw")
    if raw_linear is None and raw_db is None:
        raise DataValidationError("Raw selection requires explicit raw gain arrays in a MAT file")
    arrays = normalize_measurement_arrays(
        freq_hz=payload.get("freq_hz", payload.get("freq")),
        gain_linear=raw_linear,
        gain_db=raw_db,
        phase_deg=payload.get("phase_deg_raw", payload.get("phase_raw")),
    )
    points = []
    for index, freq in enumerate(arrays.freq_hz):
        phase = None if arrays.phase_deg is None or np.isnan(arrays.phase_deg[index]) else float(arrays.phase_deg[index])
        gain = float(arrays.gain_linear[index])
        points.append(SweepPoint(
            freq_hz=float(freq), gain_linear=gain, gain_db=float(arrays.gain_db[index]), phase_deg=phase,
            gain_complex=None if phase is None else complex(gain * np.exp(1j * np.deg2rad(phase))),
        ))
    meta["reference_correction"] = "none"
    return SweepResult(points, meta)
