from __future__ import annotations

from pathlib import Path
import os
import shutil
import tempfile
from typing import Any
from uuid import uuid4

from app.application.dto import LoadedMeasurement, SaveArtifacts, SaveTarget
from app.application.use_cases.analyze_measurement import AnalyzeMeasurementUseCase
from app.domain.models import AppSettings, ReferenceCurve, SweepResult


class MeasurementWorkspace:
    """Own input snapshots and temporary exports for a file-based workflow."""

    def __init__(self, load_measurement_use_case: Any, load_reference_use_case: Any) -> None:
        self.load_measurement_use_case = load_measurement_use_case
        self.load_reference_use_case = load_reference_use_case
        self._temporary_directory = tempfile.TemporaryDirectory(prefix="auto-load-off-test-")
        self.root = Path(self._temporary_directory.name)
        self._closed = False

    def read_document(self, path: str | Path) -> tuple[LoadedMeasurement, Path, Path]:
        original, snapshot = self._snapshot(path, "measurements")
        loaded = self.load_measurement_use_case.execute(str(snapshot))
        canonical = AnalyzeMeasurementUseCase().execute(loaded).measurement
        return LoadedMeasurement(result=canonical, raw_payload=loaded.raw_payload), original, snapshot

    def read_reference(self, path: str | Path) -> tuple[ReferenceCurve, Any, Path, Path]:
        original, snapshot = self._snapshot(path, "references")
        curve, interpolator = self.load_reference_use_case.execute(str(snapshot))
        return curve, interpolator, original, snapshot

    def snapshot_result(
        self,
        result: SweepResult,
        settings: AppSettings | None,
        save_use_case: Any,
    ) -> Path:
        self._ensure_open()
        target = SaveTarget(
            base_path=self.root / "exports" / uuid4().hex / "measurement_snapshot",
            include_timestamp=False,
        )
        artifacts: SaveArtifacts = save_use_case.execute(result=result, settings=settings, target=target)
        return artifacts.mat_path

    def close(self) -> None:
        if not self._closed:
            self._temporary_directory.cleanup()
            self._closed = True

    def __enter__(self) -> "MeasurementWorkspace":
        self._ensure_open()
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()

    def _snapshot(self, path: str | Path, bucket: str) -> tuple[Path, Path]:
        self._ensure_open()
        original = Path(path).resolve()
        if not original.is_file():
            raise FileNotFoundError(f"Measurement workspace input is missing: {original}")
        snapshot = self.root / bucket / uuid4().hex / original.name
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, snapshot)
        return original, snapshot

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Measurement workspace is closed")


def save_displayed_data(
    result: SweepResult,
    settings: AppSettings | None,
    target_path: str | Path,
    save_use_case: Any,
) -> SaveArtifacts:
    """Stage a display export, then publish MAT/CSV/TXT without overwriting."""
    destination_base = Path(target_path)
    destination_base.parent.mkdir(parents=True, exist_ok=True)
    published_paths: list[Path] = []

    with tempfile.TemporaryDirectory(prefix="auto-load-off-test-save-") as temporary:
        stage_base = Path(temporary) / destination_base.name
        staged: SaveArtifacts = save_use_case.execute(
            result=result,
            settings=settings,
            target=SaveTarget(base_path=stage_base, include_timestamp=False),
        )
        staged_paths = {
            "mat": staged.mat_path,
            "csv": staged.csv_path,
            "txt": staged.txt_path,
            "gain": staged.gain_plot_path,
            "db": staged.db_plot_path,
        }
        staged_paths = {key: path for key, path in staged_paths.items() if path is not None}

        try:
            published: dict[str, Path] = {}
            for key, source in staged_paths.items():
                destination = destination_base.parent / source.name
                _publish_exclusive(source, destination)
                published_paths.append(destination)
                published[key] = destination
        except Exception:
            for path in published_paths:
                path.unlink(missing_ok=True)
            raise

    return SaveArtifacts(
        mat_path=published["mat"],
        csv_path=published["csv"],
        txt_path=published["txt"],
        gain_plot_path=published.get("gain"),
        db_plot_path=published.get("db"),
    )


def _publish_exclusive(source: Path, destination: Path) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = -1
    created = False
    try:
        descriptor = os.open(destination, flags, 0o600)
        created = True
        with source.open("rb") as source_stream, os.fdopen(descriptor, "wb") as destination_stream:
            descriptor = -1
            shutil.copyfileobj(source_stream, destination_stream)
    except Exception:
        if created:
            destination.unlink(missing_ok=True)
        raise
    finally:
        if descriptor >= 0:
            os.close(descriptor)
