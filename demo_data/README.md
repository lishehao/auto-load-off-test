# Demo Data

This folder contains sample MAT files that can be used to inspect the measurement data shape without connecting instruments.

## Files

- `hyperframe_simulated_fixture.mat`
  - Contains 72 logarithmic frequency points from 1 kHz to 1 MHz.
  - Source metadata: `source=mock_fixture`.
  - Visible demo label: `Simulated no-hardware demo fixture`.
  - Includes `freq_hz`, `gain_linear`, `gain_db`, `phase_deg`, raw gain/phase,
    reference gain/phase, and corrected gain/phase fields.
  - Useful for Hyperframe or portfolio capture when no AWG/oscilloscope hardware is connected.

- `hyperframe_simulated_fixture.csv`
  - Human-readable version of the same simulated fixture.
  - Includes the same source label and raw/reference/corrected measurement columns.

- `hyperframe_simulated_fixture.txt`
  - Tab-separated numeric export for quick inspection.

- `hyperframe_reference_fixture.mat`
  - Reference calibration curve paired with the Hyperframe simulated fixture.

- `hyperframe_simulated_fixture_metadata.json`
  - Human-readable metadata and validation boundary.

- `Deme(1).mat`
  - Contains 15 frequency points.
  - Keys observed: `freq`, `gain_db_raw`, `config`.
  - Useful for checking older/raw gain-only measurement loading behavior.

- `Demo(2).mat`
  - Contains 50 frequency points.
  - Keys observed: `freq`, `gain_db_corr`, `phase_corr`, `config`.
  - Useful for checking corrected gain/phase measurement structure.

## How To Use

1. Start the desktop app with `python src/main.py`.
2. Use `Load Demo Fixture` for the Hyperframe fixture, or use the load-measurement action.
3. If loading manually, select one of the MAT files in this directory.
4. Confirm the plot, source receipt, no-hardware label, and point count look reasonable.

These files are sample data for review and local testing. They are not a substitute for live instrument verification.

The Hyperframe fixture is explicitly simulated no-hardware data. Do not describe it as a live hardware validation run.

Regenerate the deterministic Hyperframe fixture with:

```bash
python scripts/generate_hyperframe_fixture.py
```
