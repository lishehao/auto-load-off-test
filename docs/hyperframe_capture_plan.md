# Hyperframe Fixture Replay Capture Plan

This plan documents the reproducible deterministic fixture replay. It does not imply live hardware validation.

Required visible label in the capture:

```text
No hardware - simulated fixture
```

or:

```text
Simulated no-hardware demo fixture
```

The real Tk operator console owns this label; no external overlay is required.

## Current Tooling Status

The repository contains a real-window capture path:

- `scripts/capture_operator_console_point_replay.py`: primary 0/72 -> 72/72 replay.
- `scripts/capture_operator_console_demo.py`: shorter immediate-load capture helper and shared macOS capture code.
- `docs/images/auto-load-off-test-point-replay-demo.mp4`: current primary video.
- `docs/images/auto-load-off-test-point-replay-demo.png`: current poster.

The point-replay helper uses only these deterministic local inputs:

- `demo_data/hyperframe_simulated_fixture.mat`
- `demo_data/hyperframe_simulated_fixture.csv`
- `demo_data/hyperframe_simulated_fixture.txt`
- `demo_data/hyperframe_reference_fixture.mat`
- `demo_data/hyperframe_simulated_fixture_metadata.json`

## Capture Storyboard

1. Ready frame
   - Show the empty gain-dB/phase workbench at 0/72.
   - Show the persistent label: `No hardware - simulated fixture`.
   - Show `AWG/OSC not used` rather than offline/connected.

2. Sweep configuration frame
   - Show a conservative sweep setup: 1 kHz to 1 MHz, log-spaced fixture points.
   - Show correction mode as dual and trigger mode as triggered.
   - Load the matching deterministic reference through the application use case and show its coverage receipt.
   - Keep the wording clear that this is fixture replay, not connected instruments.

3. Fixture replay frame
   - Activate `Load Demo Fixture` in the real Tk window.
   - Feed each point through the existing result/view-model plotting path.
   - Show progress, point count, and latest frequency changing with the curve.

4. Gain and phase frame
   - Show gain dB with a plausible roll-off and mild noise.
   - Show phase shifting across frequency.
   - Optional: show raw/reference/corrected fields from the CSV as a small data callout.

5. Export/data frame
   - Run a real MAT/CSV/TXT export into the capture's temporary directory.
   - Show the resulting artifact receipt without presenting it as a hardware measurement.

6. README context outside the video
   - Link the validation matrix and architecture notes next to the capture.
   - Keep the supporting copy concise:
     `Core sweep math and persistence are testable without instruments; live hardware validation remains manual.`

## Exact Capture Steps

1. Regenerate fixture data if needed:

   ```bash
   python scripts/generate_hyperframe_fixture.py
   ```

2. Install the macOS capture-only dependencies:

   ```bash
   python -m pip install -e ".[capture]"
   ```

3. Run the point replay:

   ```bash
   PYTHONPATH=src python scripts/capture_operator_console_point_replay.py
   ```

4. Inspect early, middle, and final frames. Confirm 0/few points, a partial curve, 72/72, source badge, neutral
   hardware state, reference coverage receipt, and the final export receipt.

5. Verify the poster/MP4 paths and keep the YouTube description explicit about simulated no-hardware data.

## Do Not Claim

- Do not say the fixture is a live AWG/oscilloscope run.
- Do not say the demo validates connected hardware.
- Do not edit production instrument adapters for this capture.
- Do not capture an unverified desktop region; use the resolved Tk CGWindowID.

## Implementation Boundary

Capture automation remains under `scripts/`. It consumes checked-in fixture files and updates the existing
Tk view-model/plot path. It never constructs production instrument ports or presents the temporary export as live data.
