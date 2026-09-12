from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any
from uuid import uuid4

from app.application.use_cases.analyze_measurement import AnalysisOptions, AnalyzeMeasurementUseCase
from app.domain.data_validation import DataValidationError
from app.infrastructure.persistence.analysis_bundle import file_digest, write_analysis_bundle
from app.infrastructure.persistence.measurement_loader import MeasurementLoader
from app.infrastructure.persistence.reference_repo_mat import MatReferenceRepository


def run_offline_analysis(
    input_path: Path,
    output_dir: Path,
    *,
    reference_path: Path | None = None,
    options: AnalysisOptions = AnalysisOptions(),
) -> dict[str, Any]:
    """Compose the file-analysis path without importing the desktop or instrument composition root."""
    input_path = input_path.resolve()
    if not input_path.is_file() or input_path.suffix.lower() not in {".mat", ".csv"}:
        raise DataValidationError("Input must be an existing MAT or CSV file")
    if options.dataset == "raw" and input_path.suffix.lower() != ".mat":
        raise DataValidationError("Raw selection is supported only for MAT files with explicit raw arrays")
    if reference_path is not None:
        reference_path = reference_path.resolve()
        if not reference_path.is_file() or reference_path.suffix.lower() != ".mat":
            raise DataValidationError("Reference must be an existing MAT file")
    output_dir = output_dir.absolute()
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(f"Output directory already exists: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    lock_path = output_dir.parent / f".{output_dir.name}.analysis.lock"
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    reserved = False
    try:
        os.close(lock_fd)
        with tempfile.TemporaryDirectory(prefix=f".{output_dir.name}-", dir=output_dir.parent) as temp:
            staging = Path(temp) / "bundle"
            (staging / "inputs").mkdir(parents=True)
            inputs = []
            for role, source in (("measurement", input_path), ("reference", reference_path)):
                if source is None:
                    continue
                relative = f"inputs/{role}{source.suffix.lower()}"
                snapshot = staging / relative
                shutil.copyfile(source, snapshot)
                inputs.append({"role": role, "original_name": source.name, "path": relative,
                               "sha256": file_digest(snapshot), "bytes": snapshot.stat().st_size})
            loaded = MeasurementLoader().load(str(staging / inputs[0]["path"]))
            reference = None
            if reference_path is not None:
                reference = MatReferenceRepository().load_reference(str(staging / inputs[1]["path"]))
            analysis = AnalyzeMeasurementUseCase().execute(loaded, reference=reference, options=options)
            manifest = write_analysis_bundle(
                staging, analysis, analysis_id=str(uuid4()),
                created_at=datetime.now(timezone.utc).isoformat(), inputs=inputs,
            )
            # Reserve only after staging succeeds. mkdir fails even for an existing empty directory.
            output_dir.mkdir()
            reserved = True
            # Windows cannot replace an existing directory; remove only our own empty reservation.
            if os.name == "nt":
                output_dir.rmdir()
                reserved = False
            os.replace(staging, output_dir)
            reserved = False
        return {"status": "completed", "output_dir": str(output_dir.resolve()),
                "report": str((output_dir / "report.html").resolve()),
                "manifest": str((output_dir / "manifest.json").resolve()),
                "point_count": manifest["summary"]["point_count"], "live_hardware_used": False}
    finally:
        if reserved:
            output_dir.rmdir()
        lock_path.unlink(missing_ok=True)
