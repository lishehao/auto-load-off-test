from __future__ import annotations

import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PACKAGE_FIXTURE_DIR = SRC / "app" / "runtime" / "demo_data"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app.demo.hyperframe_fixture import write_fixture  # noqa: E402


def main() -> None:
    paths = write_fixture(ROOT / "demo_data")
    PACKAGE_FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    for key in ("measurement_mat", "reference_mat"):
        source = paths[key]
        destination = PACKAGE_FIXTURE_DIR / source.name
        shutil.copyfile(source, destination)
        print(f"{key} package copy: {destination.relative_to(ROOT)}")
    for name, path in paths.items():
        print(f"{name}: {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
