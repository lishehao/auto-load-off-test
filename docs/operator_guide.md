# Operator Guide

This guide summarizes the live workflow for the desktop app. The original Word guide in `UserGuide/` can remain as a detailed operator artifact, but this Markdown version is readable directly on GitHub.

## 1. Connect Instruments

1. Connect the AWG output to the device under test.
2. Connect the oscilloscope test channel to the measured output.
3. For dual-channel correction, connect the oscilloscope reference channel.
4. For triggered operation, connect or select the trigger channel.
5. Confirm VISA/LAN visibility with the instrument scanner or external VISA tooling.

## 2. Configure Sweep Parameters

- Start/stop frequency define the sweep range.
- Linear mode uses a frequency step.
- Log mode uses a step count.
- AWG amplitude is configured in Vpp.
- Oscilloscope range and offset define the vertical acquisition window.
- Coupling and impedance should match the probe, DUT, and measurement setup.

## 3. Choose Correction And Trigger Mode

- No correction: gain is computed against the configured AWG amplitude.
- Dual-channel correction: gain and phase are computed against a measured reference channel.
- Reference calibration: a loaded reference MAT file can correct measured points.
- Free-run mode captures without arming an edge trigger.
- Triggered mode arms the selected oscilloscope trigger channel.

## 4. Run A Sweep

1. Review hardware settings and safety limits.
2. Start the sweep.
3. Watch progress and warnings.
4. Stop if the DUT, waveform, range, or instrument state looks wrong.
5. Save the measurement if auto-save is disabled.

## 5. Output Files

Saving a measurement writes MAT, CSV, and TXT files. If plot figures are supplied, gain and gain-dB PNG files are also written.

The CSV columns are:

- `freq_hz`
- `gain_linear`
- `gain_db`
- `phase_deg`

Missing phase values are exported as blank cells in CSV and `nan` values in TXT/MAT arrays.

## 6. Demo Data

The files in `demo_data/` can be loaded through the measurement loader path to inspect historical/sampled measurement structure without instruments. See `demo_data/README.md`.

## 7. Troubleshooting

- No resources visible: check VISA backend, LAN connectivity, USB/GPIB cable, or serial permissions.
- Sweep fails immediately: verify model label, address, impedance/coupling combinations, and numeric settings.
- Cleanup warning after Stop or window close: verify the AWG front-panel output state before touching the DUT or starting another sweep.
- Flat or clipped waveform: reduce AWG amplitude or adjust oscilloscope range/offset.
- Unexpected phase: verify reference channel, trigger mode, and cable/probe delays.
- Save/load failure: confirm output directory permissions and supported file suffixes.

## 8. Screenshots

For portfolio documentation, capture:

- `docs/images/main_ui.png`: app configured before a sweep.
- `docs/images/sweep_result.png`: completed sweep with plotted result.

Screenshots should be captured from the real desktop app rather than mocked or generated images.
