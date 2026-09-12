from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy.io import loadmat

from app.application.dto import LoadedMeasurement
from app.domain.data_validation import DataValidationError, normalize_measurement_arrays
from app.domain.models import SweepPoint, SweepResult


class MeasurementLoader:
    def load(self, file_path: str) -> LoadedMeasurement:
        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix == ".mat":
            payload = loadmat(path)
            freq = self._get_array(payload, ["freq_hz", "freq"])  # type: ignore[arg-type]
            gain_db = self._get_array(payload, ["gain_db", "gain_db_raw", "gain_db_corr"], required=False)
            gain_linear = self._get_array(payload, ["gain_linear", "gain_raw"], required=False)
            phase = self._get_array(payload, ["phase_deg", "phase", "phase_deg_corr", "phase_corr"], required=False)
        elif suffix == ".csv":
            payload, freq, gain_linear, gain_db, phase = self._read_csv(path)
        else:
            raise ValueError(f"Unsupported file type: {suffix}")

        arrays = normalize_measurement_arrays(
            freq_hz=freq,
            gain_linear=gain_linear,
            gain_db=gain_db,
            phase_deg=phase,
        )
        points: list[SweepPoint] = []
        for idx in range(len(arrays.freq_hz)):
            phase_deg = _optional_phase(arrays.phase_deg, idx)
            points.append(
                SweepPoint(
                    freq_hz=float(arrays.freq_hz[idx]),
                    gain_linear=float(arrays.gain_linear[idx]),
                    gain_db=float(arrays.gain_db[idx]),
                    phase_deg=phase_deg,
                    gain_complex=(
                        complex(
                            float(arrays.gain_linear[idx]) * np.cos(np.deg2rad(phase_deg)),
                            float(arrays.gain_linear[idx]) * np.sin(np.deg2rad(phase_deg)),
                        )
                        if phase_deg is not None
                        else None
                    ),
                )
            )

        return LoadedMeasurement(
            result=SweepResult(points=points, meta=_result_meta(payload, path=path, point_count=len(points))),
            raw_payload=payload,
        )

    def _read_csv(
        self,
        path: Path,
    ) -> tuple[dict[str, Any], np.ndarray, np.ndarray | None, np.ndarray | None, np.ndarray | None]:
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            fieldnames = set(reader.fieldnames or [])
            if "freq_hz" not in fieldnames:
                raise DataValidationError("CSV is missing required column: freq_hz")
            if "gain_linear" not in fieldnames and "gain_db" not in fieldnames:
                raise DataValidationError("CSV requires gain_linear or gain_db column")
            rows = list(reader)

        if not rows:
            raise DataValidationError("Measurement CSV has no data rows")

        _validate_csv_provenance(rows, fieldnames)

        freq = np.array(
            [_required_float(row, "freq_hz", row_number) for row_number, row in enumerate(rows, start=2)],
            dtype=float,
        )
        gain_linear = (
            np.array(
                [_required_float(row, "gain_linear", row_number) for row_number, row in enumerate(rows, start=2)],
                dtype=float,
            )
            if "gain_linear" in fieldnames
            else None
        )
        gain_db = (
            np.array(
                [_required_float(row, "gain_db", row_number) for row_number, row in enumerate(rows, start=2)],
                dtype=float,
            )
            if "gain_db" in fieldnames
            else None
        )
        phase = (
            np.array(
                [_optional_float(row, "phase_deg", row_number) for row_number, row in enumerate(rows, start=2)],
                dtype=float,
            )
            if "phase_deg" in fieldnames
            else None
        )

        payload: dict[str, Any] = {"freq_hz": freq}
        if gain_linear is not None:
            payload["gain_linear"] = gain_linear
        if gain_db is not None:
            payload["gain_db"] = gain_db
        if phase is not None:
            payload["phase_deg"] = phase
        for key in (
            "source",
            "demo_label",
            "correction_mode",
            "validation_boundary",
            "reference_correction",
            "analysis_id",
            "dataset",
        ):
            value = (rows[0].get(key) or "").strip()
            if value:
                payload[key] = value
        if payload.get("source") == "mock_fixture" and "gain_db_corrected" in fieldnames:
            payload["gain_db_corrected"] = np.array(
                [_required_float(row, "gain_db_corrected", number) for number, row in enumerate(rows, start=2)],
                dtype=float,
            )
        return payload, freq, gain_linear, gain_db, phase

    def _get_array(
        self,
        payload: dict[str, Any],
        keys: list[str],
        *,
        required: bool = True,
    ) -> np.ndarray | None:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, np.ndarray):
                return np.atleast_1d(np.asarray(value, dtype=float).squeeze())
        if required:
            raise DataValidationError(f"Missing required measurement keys: {keys}")
        return None


def _required_float(row: dict[str, str | None], field: str, row_number: int) -> float:
    raw = row.get(field)
    if raw is None or not raw.strip():
        raise DataValidationError(f"CSV row {row_number} has no value for {field}")
    try:
        return float(raw)
    except ValueError as exc:
        raise DataValidationError(f"CSV row {row_number} has non-numeric {field}: {raw!r}") from exc


def _optional_float(row: dict[str, str | None], field: str, row_number: int) -> float:
    raw = row.get(field)
    if raw is None or not raw.strip():
        return float("nan")
    try:
        return float(raw)
    except ValueError as exc:
        raise DataValidationError(f"CSV row {row_number} has non-numeric {field}: {raw!r}") from exc


def _optional_phase(phase: np.ndarray | None, idx: int) -> float | None:
    if phase is None or idx >= len(phase):
        return None
    value = float(phase[idx])
    if np.isnan(value):
        return None
    return value


def _result_meta(payload: dict[str, Any], *, path: Path, point_count: int) -> dict[str, Any]:
    meta: dict[str, Any] = {"source_file": path.name, "point_count": point_count}
    for key in ("source", "demo_label", "correction_mode", "trigger_mode", "validation_boundary"):
        value = _payload_text(payload.get(key))
        if value:
            meta[key] = value
    for key in ("reference_correction", "analysis_id", "dataset"):
        value = _payload_text(payload.get(key))
        if value:
            meta[key] = value

    # MAT exports carry processing provenance inside metadata_json.result. The
    # file path and reconstructed point count above are authoritative.
    result_meta = _mat_result_meta(payload)
    for key in ("source", "demo_label", "validation_boundary", "reference_correction", "analysis_id", "dataset"):
        if key not in result_meta:
            continue
        value = result_meta[key]
        if not isinstance(value, str) or not value.strip():
            raise DataValidationError(f"MAT result metadata {key!r} must be non-empty text")
        if key in meta and meta[key] != value:
            raise DataValidationError(f"MAT provenance field {key!r} conflicts with metadata_json.result")
    for key, value in result_meta.items():
        if key not in {"source_file", "point_count"}:
            meta[key] = value
    if meta.get("source") == "mock_fixture":
        meta.setdefault("validation_boundary", "No hardware - simulated fixture; not live hardware validation")
    return meta


def _mat_result_meta(payload: dict[str, Any]) -> dict[str, Any]:
    raw_metadata = payload.get("metadata_json")
    if raw_metadata is None:
        return {}
    text = _payload_text(raw_metadata)
    if not text:
        raise DataValidationError("MAT metadata_json is malformed: expected a JSON object")
    try:
        metadata = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise DataValidationError("MAT metadata_json is malformed JSON") from exc
    if not isinstance(metadata, dict):
        raise DataValidationError("MAT metadata_json is malformed: expected a JSON object")
    if "result" not in metadata:
        return {}
    result = metadata["result"]
    if not isinstance(result, dict):
        raise DataValidationError("MAT metadata_json.result is malformed: expected a JSON object")
    return result


def _validate_csv_provenance(rows: list[dict[str, str | None]], fieldnames: set[str]) -> None:
    for key in (
        "source",
        "demo_label",
        "correction_mode",
        "validation_boundary",
        "reference_correction",
        "analysis_id",
        "dataset",
    ):
        if key not in fieldnames:
            continue
        values = [(row.get(key) or "").strip() for row in rows]
        if any(value != values[0] for value in values[1:]):
            raise DataValidationError(f"CSV provenance column {key!r} has conflicting values across rows")


def _payload_text(value: object) -> str:
    if value is None:
        return ""
    array = np.asarray(value)
    if array.dtype.kind in {"U", "S"}:
        if array.ndim == 2 and array.shape[0] == 1:
            return "".join(str(item) for item in array[0]).strip()
        return "".join(str(item) for item in array.ravel()).strip()
    squeezed = array.squeeze()
    if squeezed.shape == () and isinstance(squeezed.item(), str):
        return str(squeezed.item()).strip()
    return ""
