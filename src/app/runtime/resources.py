from __future__ import annotations

import sys
from pathlib import Path


FIXTURE_DIR_NAME = "demo_data"
MEASUREMENT_FIXTURE_NAME = "hyperframe_simulated_fixture.mat"
REFERENCE_FIXTURE_NAME = "hyperframe_reference_fixture.mat"


def bundled_resource_root() -> Path:
    """Return the read-only resource root containing the bundled demo_data."""
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(frozen_root).resolve()

    source_root = Path(__file__).resolve().parents[3]
    if (source_root / FIXTURE_DIR_NAME).is_dir():
        return source_root

    # Wheel installs carry the same MAT files as package data next to this
    # module, while preserving the public root/demo_data layout for callers.
    return Path(__file__).resolve().parent


def bundled_fixture_path(name: str) -> Path:
    """Return a path to one bundled fixture by filename."""
    path = bundled_resource_root() / FIXTURE_DIR_NAME / name
    if not path.is_file():
        raise FileNotFoundError(f"Bundled fixture is missing: {path}")
    return path


def bundled_measurement_fixture() -> Path:
    return bundled_fixture_path(MEASUREMENT_FIXTURE_NAME)


def bundled_reference_fixture() -> Path:
    return bundled_fixture_path(REFERENCE_FIXTURE_NAME)
