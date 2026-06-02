# Screenshot Capture Notes

Expected portfolio screenshots:

- `main_ui.png`: the configured desktop app before a sweep.
- `sweep_result.png`: a completed or loaded sweep result. The current file is generated from `demo_data/Demo(2).mat`.
- `auto-load-off-test-demo-capture.mp4`: real Tk operator console capture showing the no-hardware
  Hyperframe fixture load flow.
- `auto-load-off-test-demo-capture.png`: poster frame from that real UI capture.
- `auto-load-off-test-point-replay-demo.mp4`: real Tk operator console capture showing the
  deterministic no-hardware fixture replayed point by point.
- `auto-load-off-test-point-replay-demo.png`: poster frame from the point-by-point replay capture.

Capture these from the real Tk desktop app. Do not replace them with generated mockups, because the value of this project is that it controls a real lab workflow.

For Hyperframe application-material capture without instruments, use a visible label such as
`No hardware - simulated fixture` when showing `demo_data/hyperframe_simulated_fixture.*`.
This demonstrates the UI/data workflow but must not be described as live hardware validation.

The reproducible local capture helper is:

```bash
PYTHONPATH=src python scripts/capture_operator_console_demo.py
```

It starts the real Tk app, loads the deterministic fixture through the UI/controller path, captures
the Tk window with macOS `screencapture`, and writes the mp4/poster files above.

For the point-by-point replay capture:

```bash
PYTHONPATH=src python scripts/capture_operator_console_point_replay.py
```

That helper keeps the replay inside the demo/capture boundary: it feeds partial fixture results to the
existing Tk plot/view-model path and never calls production instrument adapters.
