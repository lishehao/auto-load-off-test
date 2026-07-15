# Case Study

## Problem

Manual AWG/oscilloscope sweep measurement is repetitive and easy to misconfigure. An operator must coordinate
generator output, oscilloscope channels, trigger mode, acquisition timing, reference correction, progress/stop
behavior, and export for every run. The original implementation also coupled UI choices to a large vendor-driver
module, which made software changes hard to verify without the lab bench.

## Constraints

- Physical instruments use VISA/LAN/serial paths and model-specific commands.
- Long sweeps must not block the Tk main thread.
- The available development environment has no live AWG/oscilloscope validation path.
- Existing low-level behavior should not be broadly rewritten without physical regression testing.
- MAT/CSV/TXT data must remain usable outside the application.
- Demo evidence must not make simulated data look like a live measurement.

## Engineering Decisions

### Isolate, do not rewrite, the legacy driver

`src/equips.py` remains a vendor compatibility layer. Application use cases depend on `AwgPort` and `OscPort`;
registered infrastructure adapters are the only production path into the legacy module. This reduces coupling while
avoiding an unverified SCPI rewrite.

### Separate model capabilities from construction

Current models have explicit capability profiles for role, channels, known ranges, coupling/impedance/trigger modes,
transports, timeouts, validation status, and safety notes. A separate adapter registry resolves model/role pairs.
The UI consumes registry-backed model lists, and unsupported selections fail clearly.

### Make data contracts strict at every boundary

Measurement/reference loaders reject invalid frequencies, mismatched arrays, and non-finite values instead of
sorting, deduplicating, or filling missing gain silently. Export validates again and preserves source, correction
mode, point count, timestamp, and the simulated/live boundary.

### Treat source state as an operator concept

The console distinguishes `live`, `loaded`, and `fixture` states. Fixture replay switches to gain-dB/phase on a log
axis, shows `AWG/OSC not used`, and keeps `No hardware - simulated fixture` visible. Reference coverage, export
artifacts, warnings, and safety checks remain receipts rather than transient dialogs.

### Build evidence that does not require hardware

The deterministic fixture contains raw, reference, and expected corrected gain/phase arrays. The end-to-end test
reconstructs correction, compares exact expected curves, exports MAT/CSV/TXT, reloads MAT/CSV, and checks metadata.
The Windows package smoke exercises bundled resources and the same persistence path without opening Tk or VISA.

## Result

- Layered presentation, application, domain, and infrastructure boundaries.
- Responsive event-driven sweep updates with stop/cleanup warnings.
- Registry-backed capability validation and mockable resource discovery/test-connect.
- Strict reference/measurement IO and deterministic correction/export evidence.
- A single-screen operator console with Bode plotting, source receipts, event history, and scroll-safe side panels.
- Cross-platform tests plus a Windows PyInstaller one-folder smoke.
- A reproducible real-Tk point replay capture with explicit no-hardware labeling.

## Limitations

This work proves software structure and hardware-free workflows. It does not prove real VISA enumeration, model
firmware compatibility, electrical shutdown timing, calibration uncertainty, code signing, or safe DUT operation.
Those claims require a documented physical bench matrix and remain intentionally out of scope.

## What This Demonstrates

The project is supporting evidence for engineering judgment in a physical-system context: preserving uncertain
hardware behavior behind adapters, making the rest of the system testable, surfacing operator safety state, and
documenting exactly where evidence stops.
