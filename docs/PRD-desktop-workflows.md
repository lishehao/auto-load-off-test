# Desktop Workflow Hardening

## Scope And Authorization

On 2026-09-12 the user requested goal-mode improvement of both the interface and underlying application layers.
The target remains the Python/Tkinter desktop tool, with hardware-free usefulness and inspectable evidence for
graduate applications and software engineering/Python/backend internships. No Web service, new instrument model,
framework migration, live bench claim, or automatic publication is included.

The user subsequently approved a local Git commit and selected macOS as the UI acceptance target.
Windows UI validation is outside this iteration's acceptance scope. Existing cross-platform tests and packaging
configuration remain in place; they do not establish Windows GUI acceptance. Remote publication remains separate.

The existing offline-analysis slice remains the starting candidate. This iteration delivers three related slices:
installed resources, reliable task outcomes, and an integrated desktop file/replay/analysis workflow.

## Root Causes

Independent code investigation and fake-port reproductions found:

- The GUI resolves fixture data relative to the writable runtime directory; package smoke resolves it separately.
  Wheel installations do not include the fixture. Changing launch directory can change settings/data locations.
- Only Start guards against concurrent sweeps. Loading another file during a run can mix a new source label with
  points arriving from the old task. Terminal acquisition events arrive before cleanup/export actually finishes.
- A second-point failure discards the first point in the returned result; queued data events share a growing result
  object. Auto-save starts before AWG output-off/port-close attempts. Stop at the last point can appear completed.
- Reference loading enables a receipt but does not correct already loaded data. GUI export supplies current form
  settings even for imported data. Missing phase points are dropped from the plot, connecting across gaps.
- Point replay is implemented only in the capture helper, not in the normal application.

## Required Workflow

### Task State

One operation owns the data view at a time. Live acquisition, fixture replay, loading, analysis, export and discovery
cannot overwrite each other's inputs. Both controls and command handlers enforce this. Plot display options remain
available. Worker completion, not a measurement-completed event alone, releases the operation lock.

Closing stops replay and requests live stop. Non-cancellable file export finishes before owned temporary input
snapshots are removed. No background callback updates a destroyed window. Stop is a request, not proof of electrical
shutdown; shutdown timeout/cleanup failures remain visible.

### File And Reference Analysis

Loading a file creates a stable local snapshot. Apply uses that source snapshot, explicit canonical/raw selection,
none/magnitude/complex correction, and reject/clamp coverage. Applying twice recomputes from the source, never from
the last corrected curve. Reset restores the original canonical data. Invalid options leave the displayed result intact.

The reference receipt distinguishes next-sweep calibration from offline correction. Coverage for loaded data uses
the loaded frequencies. Clear removes both the reference and its plot coverage overlay. Changing analysis controls
does not silently change the current result or the options recorded in its report.

Save Data exports the displayed numerical result. Loaded/replayed/analyzed files do not inherit instrument form
settings. Actual run results use a frozen copy of their start settings. Export Report generates the existing
HTML/PNG/data/manifest bundle from stable inputs or an explicit snapshot of the displayed partial result.

### Fixture Replay

Load Demo prepares the current deterministic fixture. Replay starts at zero and appends points through Tk scheduling;
the user can choose 1x/2x/4x speed. Progress, latest frequency, elapsed time and point count follow the same point index.
Stop retains the partial curve; replay again starts a fresh session. Cancelled/stale callbacks cannot append points.
The plot and source receipt retain `No hardware - simulated fixture` throughout. No simulated timing is called live
acquisition. Capture tooling must drive normal application actions instead of replacing their logic.

## Interface Direction

- Preserve three columns and the current light operator-console styling; default 1440 x 810, also check 1280 x 760.
- Left: instrument/sweep/channel settings with actual safety acknowledgements, disabled during conflicting work.
- Center: frequency response, compact display controls, wrapped source label, explicit simulated label, phase gaps.
- Right: persistent run status and source, compact Run/Analysis/History tabs, action availability tied to task state.
- Replace repeated settings actions and decorative checklist squares. Warnings are durable non-modal history;
  dialogs are reserved for blocking user errors. Export receipt lists actual output, not expected files.

## Reliability Contract

- Failed/stopped tasks retain completed points with terminal reason, planned/completed counts and error context.
- Published data/terminal events own snapshots. Later mutation cannot rewrite earlier queued data.
- Check cancellation before configuration, before acquisition and after completing a point. A final-point stop is
  still stopped, even when the retained count equals the plan count.
- Attempt output-off and both port closes before auto-save. An individual cleanup/save failure must not skip the
  remaining cleanup or discard the acquisition outcome.
- Validate configuration before constructing adapters. Hardware behavior remains unverified.

## Distribution Contract

Bundled sample resources and writable user data are distinct. Normal installs use a stable per-user data root;
`AUTO_LOAD_OFF_TEST_ROOT` remains an explicit portable override. Do not silently migrate/delete old cwd settings.
Source, installed wheel and frozen-resource lookup should share one resource API and existing fixture content.

## Acceptance

1. Existing tests plus new fake-scheduler/controller/task/IO regressions pass; Ruff, compile and diff checks pass.
2. Replay covers empty, partial, stopped, restarted, complete and closed states without calling an instrument factory.
3. File export preserves source/correction and frozen settings; reference/analysis errors preserve existing data.
4. Failed fake acquisitions retain points and clean up before saving; event snapshots and late cancellation are tested.
5. Wheel resource and command checks run outside the source tree, with a distinct writable root.
6. Exercise the real Tk window on macOS; verify readable controls/plot at both target sizes and
   capture actual UI evidence. Record any missing OS/driver/browser permissions separately.
7. Independent reviewer checks the final candidate; fix findings together and revalidate affected paths.

The preceding offline HTML browser limitation remains recorded. No new Windows frozen build or remote CI pass is
inferred from local tests. A local commit is authorized; push/release remains a separate user-controlled step.
