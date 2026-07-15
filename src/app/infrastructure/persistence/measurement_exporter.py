from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.io import savemat

from app.application.dto import SaveArtifacts, SaveTarget
from app.domain.data_validation import validate_sweep_result
from app.domain.exporters import result_to_arrays, settings_to_metadata
from app.domain.models import AppSettings, SweepResult


class MeasurementExporter:
    def export(self, result: SweepResult, settings: AppSettings, target: SaveTarget) -> SaveArtifacts:
        validate_sweep_result(result)
        directory = target.base_path.parent
        directory.mkdir(parents=True, exist_ok=True)

        stem = target.base_path.stem if target.base_path.suffix else target.base_path.name
        prefix = datetime.now().strftime("%Y%m%d_%H_%M_%S_") if target.include_timestamp else ""
        file_base = f"{prefix}{stem}"

        mat_path = directory / f"{file_base}.mat"
        csv_path = directory / f"{file_base}.csv"
        txt_path = directory / f"{file_base}.txt"

        arrays = result_to_arrays(result)
        source = str(result.meta.get("source") or "unknown")
        validation_boundary = _validation_boundary(result)
        metadata = settings_to_metadata(settings)
        metadata["result"] = dict(result.meta)
        metadata["export"] = {
            "point_count": len(result.points),
            "source": source,
            "validation_boundary": validation_boundary,
            "exported_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        payload: dict[str, object] = {
            "schema_version": settings.schema_version,
            "metadata_json": json.dumps(metadata, ensure_ascii=True, default=_json_default),
            "source": source,
            "point_count": len(result.points),
            "correction_mode": settings.run_mode.correction_mode.value,
            "validation_boundary": validation_boundary,
        }
        payload.update(arrays)
        savemat(mat_path, payload)

        freq = arrays.get("freq_hz", np.array([], dtype=float))
        gain_linear = arrays.get("gain_linear", np.array([], dtype=float))
        gain_db = arrays.get("gain_db", np.array([], dtype=float))
        phase = arrays.get("phase_deg", np.array([], dtype=float))

        headers = [
            "source",
            "validation_boundary",
            "correction_mode",
            "freq_hz",
            "gain_linear",
            "gain_db",
            "phase_deg",
        ]
        with csv_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(headers)
            for idx in range(len(freq)):
                writer.writerow(
                    [
                        source,
                        validation_boundary,
                        settings.run_mode.correction_mode.value,
                        float(freq[idx]),
                        float(gain_linear[idx]) if idx < len(gain_linear) else "",
                        float(gain_db[idx]) if idx < len(gain_db) else "",
                        _optional_float(phase, idx),
                    ]
                )

        rows = np.column_stack(
            [
                freq,
                gain_linear if len(gain_linear) == len(freq) else np.full(len(freq), np.nan),
                gain_db if len(gain_db) == len(freq) else np.full(len(freq), np.nan),
                phase if len(phase) == len(freq) else np.full(len(freq), np.nan),
            ]
        )
        numeric_headers = ["freq_hz", "gain_linear", "gain_db", "phase_deg"]
        np.savetxt(txt_path, rows, delimiter="\t", header="\t".join(numeric_headers), comments="")

        gain_plot_path = None
        db_plot_path = None
        gain_fig = target.figures.get("gain")
        db_fig = target.figures.get("db")
        if gain_fig is not None:
            gain_plot_path = directory / f"{file_base}_gain.png"
            gain_fig.savefig(gain_plot_path, dpi=300)
        if db_fig is not None:
            db_plot_path = directory / f"{file_base}_gain_db.png"
            db_fig.savefig(db_plot_path, dpi=300)

        return SaveArtifacts(
            mat_path=mat_path,
            csv_path=csv_path,
            txt_path=txt_path,
            gain_plot_path=gain_plot_path,
            db_plot_path=db_plot_path,
        )


def _optional_float(values: np.ndarray, idx: int) -> float | str:
    if idx >= len(values):
        return ""
    value = float(values[idx])
    if np.isnan(value):
        return ""
    return value


def _validation_boundary(result: SweepResult) -> str:
    explicit = str(result.meta.get("validation_boundary") or "").strip()
    if explicit:
        return explicit
    source = str(result.meta.get("source") or "").lower()
    if "fixture" in source or "mock" in source:
        return "No hardware - simulated fixture; not live hardware validation"
    return "Export artifact; live hardware validation is not implied"


def _json_default(value: object) -> object:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    return str(value)
