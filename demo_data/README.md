# Demo Data

This folder contains sample MAT files that can be used to inspect the measurement data shape without connecting instruments.

## Files

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
2. Use the load-measurement action.
3. Select one of the MAT files in this directory.
4. Confirm the plot and loaded point count look reasonable.

These files are sample data for review and local testing. They are not a substitute for live instrument verification.
