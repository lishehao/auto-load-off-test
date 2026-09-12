# Desktop Workflow Acceptance: 2026-09-12

## Candidate And Scope

Local candidate on `codex/offline-analysis-workflow`, based on local main `73b5d5067c4c5518138aef5b5c59ba0345aee742`.
This record is not a commit, push, CI result, or release announcement. Production instrument adapters and
`src/equips.py` were not changed. No physical instruments were used.

The user approved committing this work locally and selected **macOS-only UI acceptance** for this iteration.
Windows UI validation is out of scope, not a pending delivery gate and not a verified capability.
Existing cross-platform CI and Windows packaging configuration are retained; no new remote result is claimed here.

Runtime fingerprint: `94c6d9efa555f4f9fedc58e84bf83b6cd98843245618726b4e4cd05ffb3fe308`.
Computed from 96 sorted files: `src/**/*.py`, `src/app/runtime/demo_data/*.mat`, and `pyproject.toml`, hashing
each relative path, a NUL byte, and its contents. Documentation and capture images are excluded.

The previous [offline analysis acceptance](offline-analysis-2026-09-12.md) remains a historical slice record.
This pass adds integrated desktop workflows, installed resources, cancellation/cleanup reliability, and
numeric preflight guards. It does not turn simulated data into hardware validation.

## Validation Results

| Check | Observed result |
| --- | --- |
| Full hardware-free unittest suite, Python 3.11.14 | 168 tests passed. |
| Full hardware-free unittest suite, Python 3.13.5 | 168 tests passed. |
| Ruff, `src/app tests scripts` | Passed. Legacy `src/equips.py` is outside the established lint scope and was not rewritten. |
| Compile check, application/main/scripts/tests | Passed. |
| `git diff --check` | Passed. |
| Independent task/numeric/persistence review | Original failure cases re-run after repairs; 29 focused tests passed, no remaining P1/P2 in reviewed scope. |
| Independent controller review | 10 controller tests passed after delayed-shutdown warning regression was added. |
| Real macOS Tk workflow | Python 3.13.5, Tcl/Tk 8.6.14; actual window and callbacks at 1440x810 and 1280x760. |
| Installed wheel outside repository | Built wheel, installed into a clean Python 3.11 environment; bundled fixtures resolved under site-packages from `/tmp`. |
| Installed console command | `--package-smoke` passed; raw/complex/reject analysis produced a 72-point report with no-hardware metadata. |
| New target-Windows frozen build | Not run locally; existing CI workflow is configured for it, but this candidate was not published. |

## Real Desktop Evidence

The [machine-readable receipt](desktop-smoke-2026-09-12.json) records actual Tk assertions and capture filenames.
Two selected native screenshots are checked in:

- [Operator console, 1440x810](../images/desktop-operator-workspace.png)
- [Analysis workspace, 1280x760](../images/desktop-analysis-workspace.png)

The complete local capture was produced with `scripts/smoke_desktop_workflow.py`. It verified:

1. The initial window maps; Load Demo Fixture is enabled independently of Replay.
2. The normal load action returns 72 points, a reference receipt, and a visible no-hardware label.
3. Replay clears the displayed result, adds points, disables conflicting actions, and updates progress/frequency.
4. Stop retains 13/72 points in this run; restarting reaches 72/72 with a populated Matplotlib line.
5. Raw/complex analysis is applied explicitly; merely loading the reference does not enable calibration.
6. Numeric save and report export run from the real controller and produce files; the last output receipt updates.
7. The smaller layout keeps the main plot controls and Run/Analysis actions inside the window.
8. The final close lifecycle waits for its shutdown thread and exits cleanly.

Native captures were visually inspected, not just checked for file existence. An initial capture attempt exposed
stale presented frames and a small-window plot-toolbar overlap. The smoke now allows the native frame to present;
the toolbar uses two rows, receipts span both columns, and axis margins preserve labels. Early/partial/final
frames show the real Tk app and explicit simulated source. No generated UI image substitutes were used.

## Defects Fixed During Review

- Failure discarded valid earlier points: terminal results now carry partial data and failure-stage metadata.
- Queued data events shared a mutable result: emitted result snapshots are independent.
- Cancel could be lost before the startup thread entered: the cancellation token now exists before scheduling.
- Slow connection relabeled old fixture data as live: source changes only together with sweep-start data reset.
- Auto-save could begin before concurrent shutdown cleanup finished: a cleanup lock preserves ordering.
- Closing could miss trailing warnings: the shutdown thread is joined logically before final queue drain/log close.
- A NaN or non-increasing measured point made all results unexportable: points are validated before append.
- Tiny linear steps bypassed the sweep-point guard: validation and bounded generation share the same count rule.
- Reloading a same-name reference could change a later report: every input and result snapshot is unique.
- A failed multi-file save could leave a truncated file: exclusive publication rolls back this attempt's files.

## Reproduce

```bash
python -m pip install -e '.[dev]'
PYTHONPATH=src python -m unittest discover -s tests
python -m ruff check src/app tests scripts
python -m compileall -q src/app src/main.py scripts tests
git diff --check
python scripts/smoke_desktop_workflow.py --output-dir /tmp/auto-desktop-smoke-new
```

For native macOS screenshots, install `.[capture]` and add `--screenshots` with an existing Screen Recording grant.
Each smoke output directory must be new. The test uses temporary runtime data and prohibits hardware construction.
The revised point-replay capture script also drives normal controller callbacks; a new video was not produced in
this pass, and the existing YouTube walkthrough remains an earlier UI revision.

## Explicit Gaps

- No live VISA discovery, identity probe, firmware compatibility, electrical output-off, or calibrated bench test.
- No native file-chooser or file-manager interaction acceptance; save/report paths were supplied by the smoke.
- HTML contents, links, and output hashes are checked; browser-rendered report layout is not accepted here.
- Windows UI validation is outside this iteration's scope. No new Windows EXE, signing/notarization, installer,
  or target-Windows GUI acceptance is claimed for this branch.
- Exception rollback is not crash/power-loss atomicity. Python cancellation cannot interrupt a blocked driver call.
- No large-dataset performance benchmark. The new point/sample limits are software guards, not measured capacity.

## Defensible Project Description

Built a layered Python desktop measurement workbench with cancellable task orchestration, immutable file
snapshots, explicit reference correction, partial-result recovery, guarded exports, and reproducible analysis
reports. Validated software behavior through hardware-free tests, installed-package checks, and actual Tk
workflow captures; kept live-instrument and electrical-safety claims outside the demonstrated scope.
