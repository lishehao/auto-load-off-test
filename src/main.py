from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import traceback


def main() -> int:
    if "--package-smoke" in sys.argv[1:]:
        try:
            from app.demo.package_smoke import run_package_smoke

            run_package_smoke()
        except Exception as exc:
            _write_package_smoke_failure(exc)
            return 1
        return 0

    from app.bootstrap import run_desktop_app

    run_desktop_app()
    return 0


def _write_package_smoke_failure(exc: Exception) -> None:
    root = Path(os.environ.get("AUTO_LOAD_OFF_TEST_ROOT", Path.cwd())).resolve()
    receipt_path = root / "__data__" / "package_smoke_receipt.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(
        json.dumps(
            {
                "status": "failed",
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
                "validation_boundary": "No hardware - simulated fixture; not live hardware validation",
                "live_hardware_used": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
