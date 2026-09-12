# Engineering Workflows

## 1. Summary

Make Auto-Load-off-Test useful for repeatable offline measurement analysis while strengthening its inspectable
engineering evidence. The first slice is a command-line workflow that validates MAT/CSV data, optionally applies a
reference, and produces a self-contained result bundle without starting Tkinter or connecting to instruments.

Status: the user requested implementation of foundational improvements on 2026-09-12. This document records the
bounded first slice and a proposed follow-up backlog; it does not mark future features as approved or delivered.

## 2. Contacts

| Role | Responsibility |
| --- | --- |
| Project owner | Product direction, target applications, real-world use feedback |
| Implementation agent | Changes, regression tests, reproducible local evidence, delivery state |
| Reviewer | Review a fixed candidate separately from implementation when available |

## 3. Background

Baseline: commit `73b5d50`, 82 local hardware-free tests passing. The operator console, fixture capture, adapter
registry, and Windows package smoke exist. Public historical CI is not a fresh validation of this new slice.

Code inspection found gaps that affect correctness and reuse:

- Derived linear gain can overflow/underflow; supplied linear and dB values can contradict each other.
- Magnitude-only correction leaves the old complex gain attached to the corrected point.
- Near-zero reference values are silently replaced by epsilon; missing phase can be invented as zero.
- Normal users have no headless file-analysis command; `--package-smoke` is a diagnostic only.
- Existing export requires acquisition settings even when analyzing an imported file of unknown acquisition origin.
- Export reload drops most result metadata, making processing history difficult to follow.

Further workflow findings are tracked below, rather than silently bundled into this first implementation.

## 4. Objective

Acceptance criteria for this slice:

1. One documented command processes MAT or CSV and returns structured success/error output with an exit code.
2. No Tk window, VISA scan, or production adapter is required or imported by the offline path.
3. Calibration rejects invalid numerical data, incomplete phase for complex correction, and uncovered frequencies
   by default. An explicit clamp policy records how many points use the reference endpoints.
4. Every successful run contains input snapshots, MAT/CSV/TXT output, Bode PNG, an HTML report, and a versioned
   JSON manifest with file hashes, processing options, warnings, counts, and provenance.
5. An existing output directory is never overwritten. A failed export does not appear as a successful bundle.
6. Tests cover analytical expected values, errors, partial phase, coverage, metadata roundtrip, rollback, and real CLI
   subprocess use. Existing tests remain passing. HTML reports are inspected separately from test success.

## 5. Users And Jobs

- A student or researcher reviewing exported measurements without access to the original lab workstation.
- A developer or reviewer reproducing a result and inspecting processing decisions from a clean checkout.
- A graduate admissions reviewer evaluating quantitative reasoning, experimental reproducibility, and limitations.
- An internship interviewer evaluating API design, failure handling, regression tests, and maintainable code.

The user confirmed the internship focus on 2026-09-12: software engineering, Python, and backend roles.
No admissions or hiring outcome is promised. No current real-instrument access is assumed.

## 6. Value

The same result can be recalculated from the bundled inputs and explicit options. A reviewer can inspect the
numerical output, visual plot, checksums, and test cases without installing instrument drivers or navigating Tk.
Unknown file provenance stays unknown; offline processing does not prove that input data came from live hardware.

## 7. Solution

### Workflow And Contract

```text
auto-load-off-test analyze INPUT --output NEW_DIRECTORY
auto-load-off-test analyze INPUT --reference REF.mat --correction magnitude --output NEW_DIRECTORY
auto-load-off-test analyze INPUT --reference REF.mat --correction complex --coverage clamp --output NEW_DIRECTORY
auto-load-off-test analyze FIXTURE.mat --dataset raw --reference REF.mat --correction complex --output NEW_DIRECTORY
```

- `--correction`: `none` (default), `magnitude`, or `complex`; a correction requires a reference and vice versa.
- `--coverage`: `reject` (default) or explicit `clamp`; count/report frequencies outside the reference interval.
- `--dataset`: `canonical` (default) or `raw`. Raw selection requires explicit `gain_db_raw`/`gain_linear_raw` (or
  legacy `gain_raw`) fields in MAT; it never falls back to canonical data. Hyperframe canonical arrays are already
  corrected, so another reference correction requires selecting raw. Acquisition mode `dual` alone is not used to
  infer prior file-reference correction.
- Complex correction requires measured phase for every input point and phase in the reference.
- Already reference-corrected output is rejected for another correction to prevent accidental double application.
- All errors return a nonzero code. JSON goes to stdout on success and stderr on data/IO failure; invalid command
  syntax uses argparse's error/help text.
- The report distinguishes input source claims from actions performed during this run (`live_hardware_used: false`).
- Report paths are relative. Input filenames are escaped in HTML and absolute local paths are not published.

### Design And Implementation

Reuse current loaders, domain calibration and exporter. Keep numerical analysis in the application/domain layers,
file bundle/report writing in infrastructure, and command parsing at the entry point. No UI framework migration.
Use explicit analysis metadata when acquisition settings are unavailable rather than inventing AWG/OSC settings.
Stage the complete bundle before moving it to a new destination; write the success manifest last.

### Risk Review

| Failure | Mitigation / validation |
| --- | --- |
| Inconsistent or unrepresentable gain | Validate derived values and linear/dB agreement with a documented tolerance |
| Invented phase or huge artificial gain | Require phase where needed; reject zero/non-finite references and invalid results |
| Reference extrapolation hidden from reviewer | Reject by default; explicit clamp policy with point count and warning |
| Source metadata mistaken for verified acquisition | Preserve source claims; record only offline actions as verified |
| Inputs change while processing | Copy to staging first; load and hash the same snapshots |
| Partial output presented as success | New destination only; stage all files and publish only after completion |
| Report injection / local path disclosure | HTML escaping, relative artifact links, filenames rather than absolute paths |
| Silent recalibration | Persist reference-correction marker in exported MAT and CSV; reject repeat correction |

This is a focused engineering review for the current slice, not a claim of independent acceptance.

### Assumptions And Boundaries

- Keep legacy interpolation behavior in existing sweep paths. Offline analysis uses shape-preserving PCHIP over
  log frequency for dB gain and unwrapped phase. This avoids negative interpolated magnitude from an ordinary cubic
  amplitude spline. The report records the method; tests compare analytic curves and exact reference nodes.
  See [SciPy PCHIP documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.PchipInterpolator.html).
- MAT binary headers and timestamps can differ across reruns; numeric output and input hashes are reproducible,
  not all file bytes. No unsupported performance or accuracy metric is advertised.
- Existing GUI export overwrite behavior and live adapter semantics are outside this slice.

## 8. Delivery And Backlog

| Priority | Slice | Benefit / status |
| --- | --- | --- |
| P0 | Numerical integrity + offline analysis bundle | Current implementation scope; useful without instruments |
| P1 | Installed-resource and GUI replay parity | Fix runtime-root/bundled-resource mismatch; make point replay available in normal UI |
| P1 | Genuine simulated acquisition and fault scenarios | Exercise orchestration with synthetic waveforms, stop and timeout behavior |
| P2 | Compare runs and uncertainty/error study | Quantitative evidence with declared assumptions and independent expected curves |
| P2 | Installed wheel and desktop workflow checks | Validate clean installation, bundled data and GUI entry points on target OSes |

Delivery means a locally validated candidate with usage docs and evidence. Commit, push, PR, release and live hardware
validation are recorded separately; this workflow does not infer them from a completed local implementation.
