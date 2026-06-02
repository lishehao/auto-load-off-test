from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
from scipy.io import savemat

from app.domain.enums import (
    ConnectionMode,
    CorrectionMode,
    CouplingMode,
    ImpedanceMode,
    MagnitudePhaseMode,
    TriggerMode,
)
from app.domain.exporters import settings_to_metadata
from app.domain.models import (
    AppSettings,
    AwgSettings,
    ChannelSelection,
    InstrumentEndpoint,
    InstrumentSetup,
    OscSettings,
    RunMode,
    SweepPoint,
    SweepResult,
    SweepSpec,
)


SOURCE = "mock_fixture"
DEMO_LABEL = "Simulated no-hardware demo fixture"
SEED = 20260601
POINT_COUNT = 72
START_HZ = 1_000.0
STOP_HZ = 1_000_000.0


def build_fixture_settings() -> AppSettings:
    return AppSettings(
        schema_version=1,
        freq_unit="Hz",
        sweep=SweepSpec(
            start_hz=START_HZ,
            stop_hz=STOP_HZ,
            step_hz=None,
            step_count=POINT_COUNT,
            is_log=True,
        ),
        run_mode=RunMode(
            correction_mode=CorrectionMode.DUAL,
            trigger_mode=TriggerMode.TRIGGERED,
            auto_range=True,
            auto_reset=True,
        ),
        setup=InstrumentSetup(
            awg=InstrumentEndpoint(
                model="DSG4102",
                connect_mode=ConnectionMode.AUTO,
                visa_address="SIMULATED_AWG",
                ip_address="0.0.0.0",
            ),
            osc=InstrumentEndpoint(
                model="MDO34",
                connect_mode=ConnectionMode.AUTO,
                visa_address="SIMULATED_OSC",
                ip_address="0.0.0.0",
            ),
            channels=ChannelSelection(awg_ch=1, osc_test_ch=1, osc_ref_ch=2, osc_trig_ch=2),
            awg_settings=AwgSettings(amplitude_vpp=1.0, impedance=ImpedanceMode.R50),
            osc_settings=OscSettings(
                full_scale_v=1.0,
                offset_v=0.0,
                points=10_000,
                impedance=ImpedanceMode.R50,
                coupling=CouplingMode.DC,
            ),
        ),
        magnitude_phase_mode=MagnitudePhaseMode.MAG_AND_PHASE,
        auto_save_data=False,
    )


def build_fixture_curves(point_count: int = POINT_COUNT, seed: int = SEED) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    freq_hz = np.logspace(np.log10(START_HZ), np.log10(STOP_HZ), point_count)
    log_pos = (np.log10(freq_hz) - np.log10(START_HZ)) / (np.log10(STOP_HZ) - np.log10(START_HZ))

    reference_gain_db = (
        -0.22
        - 0.42 * log_pos
        + 0.09 * np.sin(2.0 * np.pi * log_pos * 2.3)
        + rng.normal(0.0, 0.018, point_count)
    )
    reference_phase_deg = (
        -1.2
        - 7.5 * log_pos
        + 0.35 * np.sin(2.0 * np.pi * log_pos * 1.6)
        + rng.normal(0.0, 0.12, point_count)
    )

    cutoff_hz = 115_000.0
    low_pass_gain_db = -10.0 * np.log10(1.0 + (freq_hz / cutoff_hz) ** 2)
    resonance_bump_db = 1.35 * np.exp(-0.5 * (np.log10(freq_hz / 28_000.0) / 0.16) ** 2)
    ripple_db = 0.16 * np.sin(2.0 * np.pi * log_pos * 4.7 + 0.35)
    corrected_gain_db = (
        0.72
        + low_pass_gain_db
        + resonance_bump_db
        + ripple_db
        + rng.normal(0.0, 0.045, point_count)
    )
    corrected_phase_deg = (
        -np.degrees(np.arctan(freq_hz / cutoff_hz))
        + 5.0 * np.exp(-0.5 * (np.log10(freq_hz / 34_000.0) / 0.2) ** 2)
        + 0.8 * np.sin(2.0 * np.pi * log_pos * 2.1)
        + rng.normal(0.0, 0.32, point_count)
    )

    raw_gain_db = corrected_gain_db + reference_gain_db
    raw_phase_deg = corrected_phase_deg + reference_phase_deg
    gain_linear = 10.0 ** (corrected_gain_db / 20.0)
    gain_complex = gain_linear * np.exp(1j * np.deg2rad(corrected_phase_deg))

    return {
        "freq_hz": freq_hz,
        "gain_linear": gain_linear,
        "gain_db": corrected_gain_db,
        "phase_deg": corrected_phase_deg,
        "gain_db_raw": raw_gain_db,
        "phase_deg_raw": raw_phase_deg,
        "gain_db_reference": reference_gain_db,
        "phase_deg_reference": reference_phase_deg,
        "gain_db_corrected": corrected_gain_db,
        "phase_deg_corrected": corrected_phase_deg,
        "gain_complex_real": gain_complex.real,
        "gain_complex_imag": gain_complex.imag,
    }


def build_fixture_result(curves: dict[str, np.ndarray] | None = None) -> SweepResult:
    data = curves or build_fixture_curves()
    points = []
    for freq_hz, gain_linear, gain_db, phase_deg, real, imag in zip(
        data["freq_hz"],
        data["gain_linear"],
        data["gain_db"],
        data["phase_deg"],
        data["gain_complex_real"],
        data["gain_complex_imag"],
        strict=True,
    ):
        points.append(
            SweepPoint(
                freq_hz=float(freq_hz),
                gain_linear=float(gain_linear),
                gain_db=float(gain_db),
                phase_deg=float(phase_deg),
                gain_complex=complex(float(real), float(imag)),
            )
        )
    return SweepResult(
        points=points,
        meta={
            "source": SOURCE,
            "demo_label": DEMO_LABEL,
            "point_count": len(points),
            "sweep_start_hz": START_HZ,
            "sweep_stop_hz": STOP_HZ,
        },
    )


def build_measurement_payload(
    curves: dict[str, np.ndarray] | None = None,
    settings: AppSettings | None = None,
) -> dict[str, object]:
    data = curves or build_fixture_curves()
    app_settings = settings or build_fixture_settings()
    metadata = settings_to_metadata(app_settings)
    metadata["demo_fixture"] = {
        "source": SOURCE,
        "label": DEMO_LABEL,
        "point_count": int(len(data["freq_hz"])),
        "sweep_start_hz": START_HZ,
        "sweep_stop_hz": STOP_HZ,
        "validation_boundary": "No hardware - simulated fixture; not live hardware validation.",
    }

    payload: dict[str, object] = {
        "schema_version": app_settings.schema_version,
        "metadata_json": json.dumps(metadata, ensure_ascii=True, sort_keys=True),
        "source": SOURCE,
        "demo_label": DEMO_LABEL,
        "point_count": int(len(data["freq_hz"])),
        "sweep_start_hz": START_HZ,
        "sweep_stop_hz": STOP_HZ,
        "correction_mode": app_settings.run_mode.correction_mode.value,
        "trigger_mode": app_settings.run_mode.trigger_mode.value,
        "awg_impedance": app_settings.setup.awg_settings.impedance.value,
        "osc_impedance": app_settings.setup.osc_settings.impedance.value,
        "osc_coupling": app_settings.setup.osc_settings.coupling.value,
    }
    payload.update(data)
    return payload


def build_reference_payload(curves: dict[str, np.ndarray] | None = None) -> dict[str, object]:
    data = curves or build_fixture_curves()
    return {
        "source": SOURCE,
        "demo_label": DEMO_LABEL,
        "fixture_role": "reference_calibration",
        "freq_hz": data["freq_hz"],
        "gain_db": data["gain_db_reference"],
        "phase_deg": data["phase_deg_reference"],
    }


def write_fixture(output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    curves = build_fixture_curves()
    measurement_payload = build_measurement_payload(curves)
    reference_payload = build_reference_payload(curves)

    measurement_base = output_dir / "hyperframe_simulated_fixture"
    reference_mat = output_dir / "hyperframe_reference_fixture.mat"
    metadata_json = output_dir / "hyperframe_simulated_fixture_metadata.json"

    mat_path = measurement_base.with_suffix(".mat")
    csv_path = measurement_base.with_suffix(".csv")
    txt_path = measurement_base.with_suffix(".txt")

    _write_mat(mat_path, measurement_payload)
    _write_mat(reference_mat, reference_payload)
    _write_csv(csv_path, measurement_payload)
    _write_txt(txt_path, measurement_payload)

    metadata_json.write_text(
        json.dumps(
            {
                "source": SOURCE,
                "demo_label": DEMO_LABEL,
                "validation_boundary": "No hardware - simulated fixture; not live hardware validation.",
                "point_count": int(measurement_payload["point_count"]),
                "sweep_start_hz": START_HZ,
                "sweep_stop_hz": STOP_HZ,
                "correction_mode": measurement_payload["correction_mode"],
                "trigger_mode": measurement_payload["trigger_mode"],
                "generated_from": "src/app/demo/hyperframe_fixture.py",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "measurement_mat": mat_path,
        "measurement_csv": csv_path,
        "measurement_txt": txt_path,
        "reference_mat": reference_mat,
        "metadata_json": metadata_json,
    }


def _write_mat(path: Path, payload: dict[str, object]) -> None:
    savemat(path, payload)
    header = (
        b"MATLAB 5.0 MAT-file, Auto-Load-off-Test simulated no-hardware fixture, "
        b"source=mock_fixture"
    )
    if len(header) > 116:
        raise ValueError("MAT header is too long")
    with path.open("r+b") as fh:
        fh.write(header.ljust(116, b" "))


def _write_csv(path: Path, payload: dict[str, object]) -> None:
    numeric_fields = [
        "freq_hz",
        "gain_linear",
        "gain_db",
        "phase_deg",
        "gain_db_raw",
        "phase_deg_raw",
        "gain_db_reference",
        "phase_deg_reference",
        "gain_db_corrected",
        "phase_deg_corrected",
    ]
    fields = [
        "source",
        "demo_label",
        "freq_hz",
        "gain_linear",
        "gain_db",
        "phase_deg",
        "gain_db_raw",
        "phase_deg_raw",
        "gain_db_reference",
        "phase_deg_reference",
        "gain_db_corrected",
        "phase_deg_corrected",
    ]
    count = int(payload["point_count"])
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for idx in range(count):
            row: dict[str, object] = {
                "source": SOURCE,
                "demo_label": DEMO_LABEL,
            }
            for field in numeric_fields:
                row[field] = float(np.asarray(payload[field]).squeeze()[idx])
            writer.writerow(row)


def _write_txt(path: Path, payload: dict[str, object]) -> None:
    fields = [
        "freq_hz",
        "gain_linear",
        "gain_db",
        "phase_deg",
        "gain_db_raw",
        "phase_deg_raw",
        "gain_db_reference",
        "phase_deg_reference",
        "gain_db_corrected",
        "phase_deg_corrected",
    ]
    rows = np.column_stack([np.asarray(payload[field], dtype=float).squeeze() for field in fields])
    header = (
        f"source={SOURCE}; label={DEMO_LABEL}; "
        "boundary=No hardware - simulated fixture; not live hardware validation.\n"
        + "\t".join(fields)
    )
    np.savetxt(path, rows, delimiter="\t", header=header, comments="")
