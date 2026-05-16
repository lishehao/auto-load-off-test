from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
from scipy.io import loadmat

from app.application.dto import LoadedMeasurement
from app.domain.models import SweepPoint, SweepResult


class MeasurementLoader:
    def load(self, file_path: str) -> LoadedMeasurement:
        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix == ".mat":
            payload = loadmat(path)
            freq = self._get_array(payload, ["freq_hz", "freq"])  # type: ignore[arg-type]
            gain_db = self._get_array(payload, ["gain_db", "gain_db_raw", "gain_db_corr"])
            gain_linear = self._get_array(payload, ["gain_linear", "gain_raw"], required=False)
            if gain_linear is None:
                gain_linear = np.power(10.0, gain_db / 20.0)
            phase = self._get_array(payload, ["phase_deg", "phase", "phase_deg_corr", "phase_corr"], required=False)
        elif suffix == ".csv":
            freq_l: list[float] = []
            gain_l: list[float] = []
            gain_db_l: list[float] = []
            phase_l: list[float] = []
            with path.open("r", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    freq_l.append(float(row.get("freq_hz", "0") or 0.0))
                    gain_l.append(float(row.get("gain_linear", "0") or 0.0))
                    gain_db_l.append(float(row.get("gain_db", "0") or 0.0))
                    phase_value = row.get("phase_deg")
                    phase_l.append(float(phase_value) if phase_value not in (None, "") else np.nan)
            freq = np.array(freq_l, dtype=float)
            gain_linear = np.array(gain_l, dtype=float)
            gain_db = np.array(gain_db_l, dtype=float)
            phase_values = np.array(phase_l, dtype=float) if phase_l else None
            phase = phase_values if phase_values is not None and np.any(~np.isnan(phase_values)) else None
            payload = {"freq_hz": freq, "gain_linear": gain_linear, "gain_db": gain_db}
            if phase is not None:
                payload["phase_deg"] = phase
        else:
            raise ValueError(f"Unsupported file type: {suffix}")

        points: list[SweepPoint] = []
        for idx in range(len(freq)):
            phase_deg = _optional_phase(phase, idx)
            points.append(
                SweepPoint(
                    freq_hz=float(freq[idx]),
                    gain_linear=float(gain_linear[idx]) if idx < len(gain_linear) else 0.0,
                    gain_db=float(gain_db[idx]) if idx < len(gain_db) else 0.0,
                    phase_deg=phase_deg,
                    gain_complex=(
                        complex(
                            float(gain_linear[idx]) * np.cos(np.deg2rad(phase_deg)),
                            float(gain_linear[idx]) * np.sin(np.deg2rad(phase_deg)),
                        )
                        if phase_deg is not None and idx < len(gain_linear)
                        else None
                    ),
                )
            )

        return LoadedMeasurement(result=SweepResult(points=points), raw_payload=payload)

    def _get_array(
        self,
        payload: dict[str, np.ndarray],
        keys: list[str],
        *,
        required: bool = True,
    ) -> np.ndarray | None:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, np.ndarray):
                return np.atleast_1d(np.asarray(value, dtype=float).squeeze())
        if required:
            raise ValueError(f"Missing required keys: {keys}")
        return None


def _optional_phase(phase: np.ndarray | None, idx: int) -> float | None:
    if phase is None or idx >= len(phase):
        return None
    value = float(phase[idx])
    if np.isnan(value):
        return None
    return value
