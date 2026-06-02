from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app.demo.hyperframe_fixture import write_fixture  # noqa: E402


def main() -> None:
    paths = write_fixture(ROOT / "demo_data")
    for name, path in paths.items():
        print(f"{name}: {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
