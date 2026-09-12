# Offline Measurement Analysis

Analyze exported measurements without opening the desktop app or connecting to instruments. The command accepts
MAT and CSV input and produces a directory containing input snapshots, data exports, a Bode plot, a readable HTML
report, and a JSON processing manifest.

## Quick Start

From a checkout with Python 3.10 or newer:

```bash
python -m pip install -e .
auto-load-off-test analyze demo_data/hyperframe_simulated_fixture.mat --output __data__/analysis-demo
```

Open `__data__/analysis-demo/report.html`. The file is self-contained within its result directory and requires no
server, account, instrument driver, or JavaScript. Keep the directory together when sharing it.

The checked-in fixture is simulated and already contains corrected canonical curves. To independently reconstruct
the corrected output from its raw arrays and reference:

```bash
auto-load-off-test analyze demo_data/hyperframe_simulated_fixture.mat \
  --dataset raw \
  --reference demo_data/hyperframe_reference_fixture.mat \
  --correction complex \
  --output __data__/analysis-corrected
```

On PowerShell, run the command on one line or use PowerShell's continuation syntax. Source checkout users can
replace `auto-load-off-test` with `python src/main.py`.

## Input Contract

CSV requires `freq_hz` and either `gain_linear` or `gain_db`. `phase_deg` is optional; blank phase cells stay missing.
MAT accepts the same primary arrays, plus the legacy `freq` alias. For example:

```csv
freq_hz,gain_db,phase_deg
1000,0,0
10000,-3,-45
100000,-20,-84
```

- Frequencies must be finite, positive and strictly increasing, with no duplicates.
- Linear gains must be finite and positive. dB values must map to representable positive linear gains.
- When both gain forms are supplied, they must agree to `0.0001 dB` absolute tolerance, allowing rounded CSV values.
- Phase may be absent or partly missing for magnitude analysis. Complex correction requires all measurement phases
  and a reference phase curve; no zero phase is invented.
- `--dataset raw` requires explicit raw MAT fields; it does not silently select primary arrays. Raw aliases are
  `gain_db_raw`, `gain_linear_raw` / `gain_raw`, and optional `phase_deg_raw` / `phase_raw`.
- Result metadata and repeated CSV provenance fields are checked for consistency. Unknown acquisition provenance
  is reported as unverified.

## Calibration Choices

| Option | Behavior |
| --- | --- |
| `--correction none` | Default: validate and export selected data without applying a reference |
| `--correction magnitude` | Divide measured magnitude by reference magnitude; preserve measured phase |
| `--correction complex` | Divide the complex response by the complex reference |
| `--coverage reject` | Default: fail when any input frequency is outside reference coverage |
| `--coverage clamp` | Explicitly use the nearest reference endpoint outside coverage; report the affected count |

A reference and a non-`none` correction must be specified together. New output preserves a `reference_correction`
marker; the command rejects accidental reapplication to known corrected data. Processing history from arbitrary
external files cannot be independently verified. The acquisition field `correction_mode=dual` is a separate concept
and does not by itself mean a file reference has already been applied.

Offline interpolation uses PCHIP in `log10(frequency)` for dB gain and unwrapped phase. Interpolating dB prevents a
negative magnitude between valid positive reference nodes. PCHIP preserves local monotonicity and avoids overshoot
([SciPy documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.PchipInterpolator.html)).
A single reference point is treated as a constant, and range policy still applies. Sparse phase samples cannot
identify unknown full-cycle phase rotations; unwrapping assumes adjacent reference phase differences represent the
shortest continuation. This is an explicit modeling assumption, not a calibration accuracy claim.

Existing sweep interpolation remains unchanged. Shared numerical checks now reject zero/non-finite reference
responses instead of replacing zero with epsilon; failures reach the existing error/cleanup path.

## Result Bundle

```text
analysis-corrected/
  inputs/measurement.mat    copy used by the loader and hash calculation
  inputs/reference.mat     present when a reference was supplied
  measurement.mat          analysis result and metadata; no invented instrument setup
  measurement.csv          numeric result and processing/source markers
  measurement.txt          tab-separated numeric output
  bode.png                 input/result comparison when corrected; gaps remain missing
  report.html              readable processing record and local artifact links
  manifest.json            versioned provenance, options, warnings, hashes and file sizes
```

The manifest includes a unique run ID, UTC timestamp, dependency versions, file-supplied source, selected arrays,
reference coverage, correction and interpolation policy, warnings, and artifact hashes. `live_hardware_used: false`
describes this processing run, not how the original input was acquired. Input snapshots contain their original
content; review that content before sharing external measurement files.

Numerical output is reproducible from the input snapshots and options. Run IDs, timestamps and MAT binary headers
vary between executions, so byte-for-byte equality of entire bundles is not promised. `manifest.json` lists hashes
for inputs and generated artifacts; it intentionally does not hash itself.

## Failure Behavior

The output directory must be new, even if an existing directory is empty. Files are staged and the success manifest
is written only after all exports and the plot/report complete. A cooperating concurrent run targeting the same
directory is rejected by an exclusive lock. On failure, temporary files and the lock are removed. A process killed
by the operating system may leave a hidden staging directory or lock beside the target; inspect it and confirm no
analysis is active before removing it. This is not a distributed filesystem transaction guarantee.

Successful execution prints a JSON receipt to stdout and exits `0`. Data/IO failures print JSON to stderr and exit
`1`. Invalid command syntax uses argparse's help/error output and exits `2`. Invoking without a subcommand starts the usual Tk UI;
`--help`, `analyze --help`, and `--package-smoke` remain available.

## Engineering Evidence

- [Numerical and calibration regressions](../tests/test_calibration.py)
- [Input contract tests](../tests/test_data_validation.py)
- [Metadata roundtrip tests](../tests/test_analysis_metadata.py)
- [Offline use case, bundle, failure and CLI subprocess tests](../tests/test_offline_analysis.py)
- [Requirements, risk review and next slices](PRD-engineering-workflows.md)
- [Local validation record and remaining limits](validation/offline-analysis-2026-09-12.md)

For research-oriented discussion, the useful evidence is explicit numerical assumptions and reproducible outputs.
For software engineering discussion, it is a reusable application use case, strict input contracts, transaction-like
file delivery, error handling, and integration tests. Neither establishes live instrument or metrology validation.
