# Screenshot Capture Notes

Current review assets:

- `desktop-operator-workspace.png`: real 1440x810 Tk window after ordinary controller-driven fixture replay.
- `desktop-analysis-workspace.png`: real 1280x760 Tk window after explicit raw/complex analysis; current branch UI.
  These are macOS native window captures, not generated designs. The local acceptance record is in
  `docs/validation/desktop-workflows-2026-09-12.md`.

- `sweep_result.png`: a completed or loaded sweep result. The current file is generated from `demo_data/Demo(2).mat`.
- `auto-load-off-test-point-replay-demo.mp4`: real Tk operator console capture showing the
  deterministic no-hardware fixture from 0/72 through 72/72, a loaded reference receipt, and a temporary export receipt.
- `auto-load-off-test-point-replay-demo.png`: poster frame from the point-by-point replay capture.
- `auto-load-off-test-demo-capture.mp4` and `.png`: older immediate-load capture retained for history/fallback.

Capture these from the real Tk desktop app. Do not replace them with generated mockups, because the value of this project is that it controls a real lab workflow.

For Hyperframe application-material capture without instruments, use a visible label such as
`No hardware - simulated fixture` when showing `demo_data/hyperframe_simulated_fixture.*`.
This demonstrates the UI/data workflow but must not be described as live hardware validation.

Install capture-only dependencies and run the primary helper:

```bash
python -m pip install -e ".[capture]"
PYTHONPATH=src python scripts/capture_operator_console_point_replay.py
```

The current helper writes a new controller-driven capture to `docs/images/desktop-workflow-replay/` by default;
it does not overwrite the primary MP4/poster. Use `--output-dir` to select another review-only destination.

It starts the real Tk app at 1440x810, applies the fixture's 1 kHz-1 MHz/72-point/log settings, loads the matching
reference through the application use case, and captures only the resolved Tk CGWindowID. Quartz is preferred;
`screencapture -l` is the precise-window fallback. Every PNG is flattened to RGB and rejected/retried if it looks
like a partial black frame.

The shorter immediate-load helper remains available:

```bash
PYTHONPATH=src python scripts/capture_operator_console_demo.py
```

Both helpers stay inside the demo/capture boundary and never call production instrument adapters.
