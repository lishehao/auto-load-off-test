# Operator Guide

The desktop has two distinct workflows: file-based review and instrument acquisition. Opening the app does not
scan or connect to instruments. File operations never instantiate production instrument ports.

## No-Hardware Walkthrough

1. Choose **Load Demo Fixture**. This loads the bundled 72-point measurement and reference.
2. Choose **Replay Fixture** for incremental playback at 1x, 2x, or 4x.
3. **Stop** retains the currently displayed points. Replay starts a fresh pass from zero.
4. In the **Analysis** tab, choose a dataset, correction, and coverage policy.
5. Choose **Apply Analysis**, then inspect the plot and reference receipt.
6. **Save Data** saves the displayed MAT/CSV/TXT. **Export Report** creates a new reproducible report directory.

The persistent label is **No hardware - simulated fixture**. Playback is deterministic file replay, not an
acquisition or a live validation result. The source label is independent of the editable hardware setup form.

## File Analysis And Reference Correction

**Load Data** accepts MAT/CSV. The application creates a private temporary input snapshot before parsing it.
Changes to the original file after loading do not silently affect Apply or Export. Loading another file replaces
the active document; **Reset Analysis** returns to that document's original snapshot, not an earlier file.

| Option | Meaning |
| --- | --- |
| Dataset: canonical | Analyze the file's primary arrays. Known previous correction remains recorded. |
| Dataset: raw | Use explicitly supplied raw gain/phase arrays in MAT. Missing raw arrays are an error. |
| Correction: none | Preserve the selected input values; this does not undo prior correction. |
| Correction: magnitude | Divide gain by the reference magnitude; preserve measured phase. |
| Correction: complex | Correct gain and phase; requires phase at every measured and reference point. |
| Coverage: reject | Reject correction when measured points lie outside reference coverage. |
| Coverage: clamp | Explicitly permit endpoint clamping, with a recorded warning and point count. |

For the bundled demo, use **raw + complex + reject** to reconstruct the corrected response. Its canonical arrays
are already marked corrected and are protected against accidental double correction.

**Load Reference** only changes the available reference. It does not enable hardware calibration or modify the
plot. The receipt shows the reference filename/path, frequency span, point count, phase availability, requested
correction, and the correction on the displayed result. Coverage is compared with the loaded measurement, not
with the unrelated future hardware sweep form.

**Apply Analysis** always starts from the original input snapshot. Repeated Apply does not compound corrections.
A failed Apply leaves the previous valid plot and applied export options intact. Changing a selector without
applying it also leaves the displayed result and report unchanged.

**Clear Reference** removes the available reference and turns off future hardware calibration. It does not undo
already-corrected data. A report of previously applied analysis retains the exact reference snapshot used then.
Use **Reset Analysis** to restore the original file result.

## Results And Export

**Save Data** writes the currently displayed values, including a stopped partial replay, as MAT/CSV/TXT. It stages
files before publication and refuses collisions or symlinks. If publication fails, only files created by that
attempt are removed. This is exception rollback, not a guarantee against power loss or process termination.

**Export Report** creates a new directory containing:
- `measurement.mat`, `measurement.csv`, `measurement.txt`
- `bode.png`, `report.html`
- `manifest.json` with input/artifact hashes and processing parameters
- `inputs/` with stable measurement and, when applicable, reference snapshots

The report uses the applied analysis options, not uncommitted selector changes. For a partial replay or hardware
result, it snapshots the displayed points before offline report generation. **Open Output** opens only the last
successful output directory in the OS file manager. The folder location and artifact list also remain in the
receipt; a failed save leaves the previous successful output available.

File-supplied acquisition provenance is retained but not independently verified. Offline processing does not
prove that an imported file came from validated hardware. Missing phase remains missing, including visible gaps
in the plot. See [offline_analysis.md](offline_analysis.md) for the file contract and headless CLI.

## Hardware Setup And Acquisition

This path has code-level fake-port coverage, not current live bench validation.

1. Verify physical cabling, DUT limits, probe attenuation, termination, and instrument output state.
2. Select the AWG/oscilloscope model and connection mode in **Instruments**.
3. **Scan Resources** lists resource addresses; visibility alone is not a connection.
4. **Test Connect** probes identity and displays model/address/backend/last-seen status. It does not acquire data.
5. Configure frequency, amplitude, capture range/offset/points, channels, coupling, correction, and trigger mode.
6. Confirm all three operator safety checks, then choose **Start Hardware**.

Linear sweeps use a frequency step; logarithmic sweeps use a point count. Invalid numbers fail explicitly.
The software guards are 100,000 sweep points and 10,000,000 capture samples, not electrical capability guarantees.

The left **Channels / Correction** controls affect future hardware acquisition. Dual-channel correction uses the
measured reference channel; reference calibration additionally requires a loaded reference and an explicit
calibration checkbox. This hardware calibration path retains its existing interpolation behavior, including
endpoint clamping. The Analysis tab's reject/clamp choice applies to offline file analysis only.

During connection, the previous plot retains its original source. When a sweep starts, the plot is cleared and
the source changes to the hardware path. Conflicting load/analyze/save/setup operations are disabled until the
worker has stopped, cleaned up, and completed any requested auto-save.

**Stop** requests cancellation. Valid points completed before an error or during cancellation remain available,
with a run status, termination reason, planned/completed counts, and error stage where relevant. Invalid points
are rejected before they contaminate earlier results. Auto-save includes nonempty failed/stopped runs when enabled.

Output-off and close are attempts, not electrical guarantees. A blocked driver call cannot be interrupted by a
Python stop event. The window remains responsive while waiting; inspect the instrument front panel whenever
shutdown is uncertain. See [safety.md](safety.md).

## History, Paths, And Troubleshooting

The **History** tab retains the most recent 100 timestamped events. Sweep failure/cleanup diagnostics also persist
under `__data__/logs/sweep-events.jsonl` in the per-user runtime root, including during window close.
Logs remain local and may contain paths or instrument addresses; review before sharing.

Runtime locations and bundled resource behavior are described in [packaging.md](packaging.md). Existing legacy
cwd settings are not migrated automatically; set `AUTO_LOAD_OFF_TEST_ROOT` explicitly to reuse them.

- Cannot launch Tk: use a Python distribution with Tcl/Tk installed; the offline CLI remains separate.
- Missing resources: reinstall the wheel or rebuild; do not point the writable runtime root at the source fixture folder.
- Reference correction rejected: inspect dataset, known prior correction, phase, and coverage in Analysis.
- Export collision: choose a new base filename or report directory. Existing results are never silently replaced.
- Discovery/connection failure: inspect VISA runtime and address settings only on a properly prepared lab workstation.
- Cleanup warning: check the AWG output indicator and DUT state before touching the setup or starting again.

## Local Desktop Validation

```bash
python scripts/smoke_desktop_workflow.py --output-dir /tmp/auto-desktop-smoke
```

This opt-in test requires a graphical desktop. It invokes real Tk callbacks, checks incremental replay/stop/restart,
applies reference correction, saves data, exports a report, and checks both 1440x810 and 1280x760 layouts.
On macOS, `--screenshots` captures the actual Tk window with the optional capture dependencies and existing
Screen Recording permission. It does not exercise the native file chooser or physical instruments.

The [acceptance record](validation/desktop-workflows-2026-09-12.md) records the tested candidate and remaining gaps.
