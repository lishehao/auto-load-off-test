# Safety Notes

Auto-Load-off-Test controls physical lab instruments. It should be used as a local engineering tool by an operator who understands the connected AWG, oscilloscope, cables, probes, load impedance, and device-under-test limits.

## Scope

This project is not a certified production test platform. It does not replace lab safety procedures, instrument manuals, current/voltage limits, or operator judgment.

## Hardware Assumptions

- Supported model metadata is defined in `src/app/domain/instrument_capabilities.py`; the UI model list is derived
  from that registry.
- Model capability profiles provide software preflight checks for supported channels, modes, and known limits.
  They are not a substitute for instrument manuals or live bench validation.
- Live operation uses VISA/LAN/serial access through `src/equips.py` via infrastructure adapters.
- Default settings are conservative examples, not a guarantee that a connected DUT is safe.
- The operator must verify AWG amplitude, frequency range, impedance, coupling mode, oscilloscope vertical range, and trigger configuration before starting a sweep.

Capability preflight prevents known-invalid software selections. It cannot detect probe attenuation, cabling,
termination errors, DUT limits, stale instrument firmware behavior, or incorrect capability source data.

## Stop And Shutdown Behavior

- Pressing Stop sets a shared stop event.
- The sweep loop checks that event between frequency points and emits `SweepStopped` with the partial result.
- The same cancellation token exists before background connection starts. Cancellation is checked before
  configuration and after acquisition; a point completed during cancellation is retained.
- Runner shutdown signals stop and waits briefly for the worker thread before closing instrument ports.
- AWG shutdown attempts to turn the configured output channel off before closing the port.
- If the worker does not stop before the shutdown timeout, the runner emits `SHUTDOWN_TIMEOUT` and still attempts to turn AWG output off and close the known ports.
- If output-off or port-close fails, the runner emits a `SweepWarning` so the UI/event log can surface the cleanup failure.
- Instrument cleanup runs before auto-save. The UI remains busy until cleanup and saving finish, including after
  the last point or a failure. Closing the window requests cancellation without blocking the Tk event loop.
- Shutdown warnings are retained in `__data__/logs/sweep-events.jsonl`, including warnings arriving during close.
  Logs rotate at 1 MB with two backups and remain local. Error messages can contain instrument addresses or paths;
  review them before sharing. A blocked driver call cannot be forcibly interrupted by a Python event.
- Treat any cleanup warning after Stop or window close as hardware-significant: verify the AWG front panel/output indicator and the DUT state before touching the setup or starting another sweep.

## Exception Behavior

- Validation failures emit `SweepFailed` with a validation code.
- Runtime sweep failures emit `SweepFailed` with the points already completed, stage/error metadata, and a
  termination reason. Nonempty stopped or failed runs are eligible for auto-save when enabled.
- Queued result events contain independent snapshots, so later points cannot alter earlier event payloads.
- Cleanup failures should not hide the original sweep result, but they should be visible as warnings.

## Operator Responsibility

Before live measurement:

1. Confirm the selected instrument models and VISA addresses.
2. Confirm load impedance and coupling.
3. Confirm AWG amplitude and sweep frequency limits.
4. Confirm oscilloscope range, offset, and trigger channel.
5. Keep physical access to instrument front panels and emergency stop procedures.

Automated tests use mocked ports and do not validate real hardware behavior.

See [validation_matrix.md](validation_matrix.md) for the distinction between fake-port cleanup tests and electrical
output-off validation, which has not been performed.

## Runtime File Location

Settings and auto-save output default to a per-user application-data directory, independent of the launch
directory. `AUTO_LOAD_OFF_TEST_ROOT` overrides that location. Existing working-directory settings are left
untouched and are not silently migrated. See [packaging.md](packaging.md).

## Software Resource Guards

Preflight rejects non-finite numeric values, fractional channel/point counts, non-positive amplitude/range, and
requests over 100,000 sweep points or 10,000,000 waveform samples. These bounds prevent accidental resource
exhaustion; they do not establish safe electrical limits or validate an instrument's full capability range.
