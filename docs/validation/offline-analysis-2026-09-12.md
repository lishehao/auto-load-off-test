# Offline Analysis: Local Validation

Date: 2026-09-12. Scope: the first hardware-free engineering-workflow slice, not the entire product or a release.

## Candidate

- Local branch: `codex/offline-analysis-workflow`, based on `73b5d50`.
- No commit, push, PR, or remote CI run is claimed for this candidate.
- Runtime fingerprint: `cf11440806f3d612bfedaeee57e6d7d36517a2be3a27fcb433481c1a8a0d4580`.
- Fingerprint method: sort the eight paths below; concatenate each UTF-8 path, a NUL byte, and its binary SHA-256;
  SHA-256 the concatenation. Tests and documentation are outside this runtime fingerprint.

```text
src/main.py
src/app/offline.py
src/app/application/use_cases/analyze_measurement.py
src/app/domain/calibration.py
src/app/domain/data_validation.py
src/app/infrastructure/persistence/analysis_bundle.py
src/app/infrastructure/persistence/measurement_exporter.py
src/app/infrastructure/persistence/measurement_loader.py
```

## Results

| Check | Observed result | Boundary |
| --- | --- | --- |
| Full hardware-free suite | 113 tests passed; baseline was 82 | Local Python 3.11 on macOS, no instruments |
| Ruff | Passed for `src/app`, `tests`, `scripts`, and `src/main.py` | Static checks, not behavioral proof |
| Compile | All eight runtime files compiled | Syntax/import compilation only |
| Documentation hygiene | 39 relative links/assets resolved across six touched documents; `git diff --check` passed | External URLs and new remote CI were not checked |
| Independent read-only review | Three reproduced data-integrity findings fixed; 22 focused tests and original reproductions passed | File workflow/code review, not hardware or browser acceptance |
| Actual analysis command | 72-point raw fixture plus reference produced a complete report bundle | Simulated fixture only |
| Fixture expected values | Maximum gain difference `3.664e-15 dB`; wrapped phase difference `0 deg` at fixture nodes | Numerical reconstruction, not measured accuracy or uncertainty |
| Bundle integrity | 7 input/artifact hashes and sizes matched; 8 local HTML links resolved | Hashes identify bytes, not trustworthy acquisition |
| Report and plot | Real generated 1400 x 910 PNG inspected; curves, axes, legend and simulated label visible; HTML structure, label, escaping and paths checked | Browser-rendered HTML layout was not verified |
| Installed command | Fresh temporary environment installed declared dependencies; console entry produced 72-point output outside the repo without `PYTHONPATH` | macOS editable install; not an installed wheel, Windows executable or GUI check |
| Existing package smoke entry | Returned `status=passed`, 72 points, export/reload artifacts and `live_hardware_used=false` | Source invocation only; no new frozen Windows build |

The isolated installation resolved NumPy 2.4.6, SciPy 1.17.1 and Matplotlib 3.11.2. Its successful command run is
separate from the full test suite in the existing development environment. An earlier attempt to reuse host packages
in a temporary environment failed because NumPy was not inherited; installing the declared dependencies resolved it.

## Review Findings Closed

1. CSV fixture canonical curves could be corrected twice. The loader now preserves the fixture's corrected-field
   signal; analysis rejects another correction, including after pass-through MAT/CSV export and reload.
2. MAT top-level provenance could conflict with `metadata_json.result`. Conflicting source/correction/identity
   fields and malformed nested text are rejected instead of silently selecting one value.
3. A simulation declaration could disappear when `source` was absent. Source, demo label and input boundary are
   considered together; original declarations remain in the manifest, and simulated labels survive export.

## Reproduce

```bash
PYTHONPATH=src python -m unittest discover -s tests
python -m ruff check src/app tests scripts src/main.py
python src/main.py analyze demo_data/hyperframe_simulated_fixture.mat \
  --dataset raw --reference demo_data/hyperframe_reference_fixture.mat \
  --correction complex --output __data__/offline-analysis-final-20260912
git diff --check
```

Choose a new output directory for another run. The local example contains `report.html`, `bode.png`, `manifest.json`,
MAT/CSV/TXT results and two input snapshots. Generated files remain under ignored `__data__`, not public repo evidence.

## Remaining Limits

- The browser tool blocked local `file:` navigation. No alternate route was used; HTML browser layout is still a
  manual review item. Static HTML checks and visual PNG inspection must not be described as browser acceptance.
- No current Windows/macOS frozen-app build, manual Tk GUI smoke, or physical instrument run was performed for this slice.
- Remote refresh failed with an HTTP/2 transport error. Cached `origin/main` is not proof of fresh public state;
  refresh before publishing this branch. Unrelated local draft media was left untouched.
- The local output lock coordinates cooperating processes. Process termination can leave a stale lock/staging
  directory; network filesystem transactions and power-loss durability are not promised.
- Input snapshots preserve original file content. External files may contain private metadata; inspect before sharing.
- Source claims and simulation labels are file-supplied. Software cannot independently certify acquisition origin,
  calibration traceability, electrical safety, or admission/hiring outcomes.

## Evidence Use

For graduate applications: discuss numerical assumptions, explicit calibration limits and reproducible analysis.
For software engineering/Python/backend internships: demonstrate the application boundary, CLI contract, metadata
roundtrip, failure cleanup and integration tests. Cite this as local implementation evidence until it is published
and remote checks are separately verified.
