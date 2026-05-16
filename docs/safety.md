# Safety Notes

Auto-Load-off-Test controls physical lab instruments. It should be used as a local engineering tool by an operator who understands the connected AWG, oscilloscope, cables, probes, load impedance, and device-under-test limits.

## Scope

This project is not a certified production test platform. It does not replace lab safety procedures, instrument manuals, current/voltage limits, or operator judgment.

## Hardware Assumptions

- Supported model labels are defined in `src/app/shared/mapping.py`.
- Live operation uses VISA/LAN/serial access through `src/equips.py` via infrastructure adapters.
- Default settings are conservative examples, not a guarantee that a connected DUT is safe.
- The operator must verify AWG amplitude, frequency range, impedance, coupling mode, oscilloscope vertical range, and trigger configuration before starting a sweep.

## Stop And Shutdown Behavior

- Pressing Stop sets a shared stop event.
- The sweep loop checks that event between frequency points and emits `SweepStopped` with the partial result.
- Runner shutdown signals stop and waits briefly for the worker thread before closing instrument ports.
- AWG shutdown attempts to turn the configured output channel off before closing the port.
- If output-off or port-close fails, the runner emits a `SweepWarning` so the UI/event log can surface the cleanup failure.

## Exception Behavior

- Validation failures emit `SweepFailed` with a validation code.
- Runtime sweep failures emit `SweepFailed` and return an empty result.
- Cleanup failures should not hide the original sweep result, but they should be visible as warnings.

## Operator Responsibility

Before live measurement:

1. Confirm the selected instrument models and VISA addresses.
2. Confirm load impedance and coupling.
3. Confirm AWG amplitude and sweep frequency limits.
4. Confirm oscilloscope range, offset, and trigger channel.
5. Keep physical access to instrument front panels and emergency stop procedures.

Automated tests use mocked ports and do not validate real hardware behavior.

## Runtime File Location

Settings and auto-save output default to the process working directory. Set `AUTO_LOAD_OFF_TEST_ROOT` to use an explicit writable runtime directory on lab machines or packaged installs.
