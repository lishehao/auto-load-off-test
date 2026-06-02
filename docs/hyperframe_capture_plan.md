# Hyperframe Fixture Replay Capture Plan

This plan captures the deterministic fixture replay first. It does not add an app-level demo-mode banner
and does not imply live hardware validation.

Required visible label in the capture:

```text
No hardware - simulated fixture
```

or:

```text
Simulated no-hardware demo fixture
```

Keep the label small and persistent, for example in the lower-left corner or as a compact title overlay.

## Current Tooling Status

No `hyperframe` CLI or repo-local capture script is available in this workspace. The capture itself should
be done in the coordinator's Hyperframe environment or by the person running the desktop capture.

Available local inputs:

- `demo_data/hyperframe_simulated_fixture.mat`
- `demo_data/hyperframe_simulated_fixture.csv`
- `demo_data/hyperframe_simulated_fixture.txt`
- `demo_data/hyperframe_reference_fixture.mat`
- `demo_data/hyperframe_simulated_fixture_metadata.json`

## Capture Storyboard

1. Setup frame
   - Show the app purpose in one line: AWG/oscilloscope sweep measurement automation.
   - Show the persistent label: `No hardware - simulated fixture`.
   - Show the fixture source: `source=mock_fixture`.

2. Sweep configuration frame
   - Show a conservative sweep setup: 1 kHz to 1 MHz, log-spaced fixture points.
   - Show correction mode as dual and trigger mode as triggered.
   - Keep the wording clear that this is fixture replay, not connected instruments.

3. Fixture replay frame
   - Use `Load Demo Fixture` in the UI, or load `demo_data/hyperframe_simulated_fixture.mat`
     through the normal load-measurement path.
   - Show the plot after load.
   - If Hyperframe supports animation, reveal points progressively from the fixture CSV.

4. Gain and phase frame
   - Show gain dB with a plausible roll-off and mild noise.
   - Show phase shifting across frequency.
   - Optional: show raw/reference/corrected fields from the CSV as a small data callout.

5. Export/data frame
   - Show MAT/CSV/TXT artifacts already present in `demo_data/`.
   - Highlight that the same shape is accepted by the existing loader/export paths.

6. Evidence frame
   - Show: no-hardware tests, architecture boundaries, and live hardware validation boundary.
   - Recommended copy:
     `Core sweep math and persistence are testable without instruments; live hardware validation remains manual.`

## Exact Manual Capture Steps

1. Regenerate fixture data if needed:

   ```bash
   python scripts/generate_hyperframe_fixture.py
   ```

2. Start the desktop app only in the capture environment:

   ```bash
   python src/main.py
   ```

3. In the UI, choose `Load Demo Fixture`.

   If that action is unavailable in an older build, choose the load-measurement action and open:

   ```text
   demo_data/hyperframe_simulated_fixture.mat
   ```

4. Capture the loaded plot and settings area.

5. In Hyperframe, add a small persistent label:

   ```text
   No hardware - simulated fixture
   ```

6. Add one short data callout using `demo_data/hyperframe_simulated_fixture_metadata.json`:

   ```text
   source=mock_fixture; not live hardware validation
   ```

7. Add one short engineering callout:

   ```text
   Hardware side effects are isolated behind adapters; fixture replay exercises loader, plotting, and export shape.
   ```

## Do Not Claim

- Do not say the fixture is a live AWG/oscilloscope run.
- Do not say the demo validates connected hardware.
- Do not add an app-level demo-mode banner before the first capture.
- Do not edit production instrument adapters for this capture.

## If Hyperframe Automation Is Later Added

Prefer a separate capture helper that consumes the existing fixture files. Keep it outside production
instrument code, and preserve the same visible no-hardware label in every exported clip.
