from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.application.dto import SaveArtifacts
from app.domain.models import AppSettings, SweepResult


@dataclass(frozen=True, slots=True)
class ExportReceipt:
    summary: str
    artifacts: tuple[Path, ...]


def build_export_receipt(
    *,
    artifacts: SaveArtifacts,
    settings: AppSettings,
    result: SweepResult,
    source_text: str,
    fixture_badge_text: str,
    saved_at: datetime | None = None,
) -> ExportReceipt:
    saved_at = saved_at or datetime.now()
    paths = _artifact_paths(artifacts)
    artifact_names = ", ".join(path.name for path in paths)
    boundary = _boundary_text(source_text=source_text, fixture_badge_text=fixture_badge_text)

    summary = "\n".join(
        [
            f"Saved: {artifacts.mat_path.name}",
            f"Dir: {artifacts.mat_path.parent}",
            f"Artifacts: {artifact_names}",
            (
                f"Metadata: source={source_text or 'unknown'}; "
                f"correction={settings.run_mode.correction_mode.value}; "
                f"points={len(result.points)}; "
                f"saved={saved_at.strftime('%Y-%m-%d %H:%M:%S')}"
            ),
            f"Boundary: {boundary}",
        ]
    )
    return ExportReceipt(summary=summary, artifacts=paths)


def _artifact_paths(artifacts: SaveArtifacts) -> tuple[Path, ...]:
    paths = [
        artifacts.mat_path,
        artifacts.csv_path,
        artifacts.txt_path,
        artifacts.gain_plot_path,
        artifacts.db_plot_path,
    ]
    return tuple(path for path in paths if path is not None)


def _boundary_text(*, source_text: str, fixture_badge_text: str) -> str:
    source_lower = source_text.lower()
    fixture_lower = fixture_badge_text.lower()
    if "fixture" in source_lower or "simulated" in fixture_lower or "no hardware" in fixture_lower:
        return "No hardware simulated fixture; not live hardware validation"
    if "loaded measurement" in source_lower:
        return "Loaded file; live hardware state not implied"
    return "Live path selected; export does not prove hardware validation"
