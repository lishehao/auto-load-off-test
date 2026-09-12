from __future__ import annotations

import json
import argparse
from pathlib import Path
import sys
import traceback


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AWG/oscilloscope desktop console and offline measurement analysis")
    parser.add_argument("--package-smoke", action="store_true", help="Run the bundled no-hardware packaging check")
    commands = parser.add_subparsers(dest="command")
    analyze = commands.add_parser("analyze", help="Analyze MAT/CSV files without Tk or instruments")
    analyze.add_argument("input", type=Path)
    analyze.add_argument("--output", required=True, type=Path, help="New output directory (must not exist)")
    analyze.add_argument("--reference", type=Path, help="Reference MAT file")
    analyze.add_argument("--correction", choices=("none", "magnitude", "complex"), default="none")
    analyze.add_argument("--coverage", choices=("reject", "clamp"), default="reject")
    analyze.add_argument("--dataset", choices=("canonical", "raw"), default="canonical")
    args = parser.parse_args(argv)
    if args.package_smoke and args.command:
        parser.error("--package-smoke cannot be combined with an analysis command")
    if args.command == "analyze":
        try:
            from app.application.use_cases.analyze_measurement import AnalysisOptions
            from app.offline import run_offline_analysis

            result = run_offline_analysis(
                args.input, args.output, reference_path=args.reference,
                options=AnalysisOptions(args.correction, args.coverage, args.dataset),
            )
        except Exception as exc:
            print(json.dumps({"status": "failed", "error_type": type(exc).__name__,
                              "error": str(exc), "live_hardware_used": False}), file=sys.stderr)
            return 1
        print(json.dumps(result, sort_keys=True))
        return 0

    if args.package_smoke:
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
    from app.runtime.paths import AppPaths

    receipt_path = AppPaths.default().data_dir / "package_smoke_receipt.json"
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
