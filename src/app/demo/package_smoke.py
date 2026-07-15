from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

import numpy as np

from app.application.dto import SaveTarget
from app.demo.hyperframe_fixture import POINT_COUNT, SOURCE, build_fixture_settings
from app.domain.calibration import build_reference_interpolator
from app.infrastructure.persistence.measurement_exporter import MeasurementExporter
from app.infrastructure.persistence.measurement_loader import MeasurementLoader
from app.infrastructure.persistence.reference_repo_mat import MatReferenceRepository
from app.runtime.paths import AppPaths


VALIDATION_BOUNDARY = "No hardware - simulated fixture; not live hardware validation"
RECEIPT_NAME = "package_smoke_receipt.json"


def run_package_smoke(
    *,
    runtime_root: Path | None = None,
    resource_root: Path | None = None,
) -> Path:
    """Exercise bundled fixture IO and export without opening Tk or VISA resources."""
    resources = (resource_root or bundled_resource_root()).resolve()
    paths = AppPaths.from_root(runtime_root) if runtime_root is not None else AppPaths.default()
    fixture_path = resources / "demo_data" / "hyperframe_simulated_fixture.mat"
    reference_path = resources / "demo_data" / "hyperframe_reference_fixture.mat"

    loaded = MeasurementLoader().load(str(fixture_path))
    reference = MatReferenceRepository().load_reference(str(reference_path))
    reference_values = build_reference_interpolator(reference)(loaded.result.freq_array())

    if len(loaded.result.points) != POINT_COUNT:
        raise RuntimeError(f"Expected {POINT_COUNT} fixture points, got {len(loaded.result.points)}")
    if loaded.result.meta.get("source") != SOURCE:
        raise RuntimeError(f"Expected fixture source {SOURCE!r}, got {loaded.result.meta.get('source')!r}")
    if reference_values.shape != (POINT_COUNT,) or not np.all(np.isfinite(reference_values)):
        raise RuntimeError("Bundled reference interpolation produced invalid values")

    output_dir = paths.measurement_dir / "package_smoke"
    artifacts = MeasurementExporter().export(
        loaded.result,
        build_fixture_settings(),
        SaveTarget(base_path=output_dir / "simulated_fixture_export", figures={}),
    )
    reloaded_mat = MeasurementLoader().load(str(artifacts.mat_path))
    reloaded_csv = MeasurementLoader().load(str(artifacts.csv_path))

    for label, result in (("MAT", reloaded_mat.result), ("CSV", reloaded_csv.result)):
        if len(result.points) != POINT_COUNT:
            raise RuntimeError(f"{label} export reload returned {len(result.points)} points")
        if result.meta.get("source") != SOURCE:
            raise RuntimeError(f"{label} export lost fixture source metadata")
        if "not live hardware validation" not in str(result.meta.get("validation_boundary", "")):
            raise RuntimeError(f"{label} export lost the no-hardware validation boundary")

    artifact_paths = [artifacts.mat_path, artifacts.csv_path, artifacts.txt_path]
    missing = [str(path) for path in artifact_paths if not path.is_file() or path.stat().st_size == 0]
    if missing:
        raise RuntimeError(f"Package smoke export artifacts are missing or empty: {missing}")

    receipt_path = paths.data_dir / RECEIPT_NAME
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt: dict[str, Any] = {
        "status": "passed",
        "source": SOURCE,
        "point_count": POINT_COUNT,
        "fixture": str(fixture_path),
        "reference": str(reference_path),
        "artifacts": [str(path.resolve()) for path in artifact_paths],
        "validation_boundary": VALIDATION_BOUNDARY,
        "live_hardware_used": False,
    }
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt_path


def bundled_resource_root() -> Path:
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(frozen_root)
    return Path(__file__).resolve().parents[3]
