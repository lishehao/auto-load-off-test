# Case Study

## Problem

Manual AWG/oscilloscope sweep measurement is repetitive and error-prone. An operator must configure generator output, oscilloscope channels, trigger mode, acquisition timing, calibration/reference behavior, and data export for each run.

## Constraints

- The application controls physical instruments through VISA/LAN/serial paths.
- The UI must stay responsive while long sweeps run.
- Sweep math and signal processing should be testable without hardware.
- Instrument-specific commands should be isolated from application logic.
- Output data should be usable in analysis tools through MAT/CSV/TXT files.

## Architecture

The refactor separates the workflow into four main layers:

- `presentation/tk`: Tkinter controls, dialogs, event handling, and plots.
- `application`: use cases, events, DTOs, and ports.
- `domain`: settings models, validation, sweep generation, signal processing, calibration, and export shaping.
- `infrastructure`: instrument adapters, resource scanning, settings persistence, and measurement IO.

The legacy `src/equips.py` driver file remains as a vendor compatibility layer and is wrapped by infrastructure adapters.

## Testing Strategy

The automated tests avoid physical instruments by using:

- pure tests for sweep generation, signal processing, auto range, and serialization
- fake AWG/OSC ports for the start-sweep use case
- temporary directories for measurement export/load round trips
- task-runner tests around threading, auto-save, cleanup, and warnings

This keeps the core behavior reviewable on any development machine.

## Output

The app exports measurement data as MAT, CSV, and TXT files. Plot PNGs can be saved when the UI provides figure handles.

## What This Demonstrates

This project demonstrates real-world engineering in a physical-system context: separating hardware side effects from testable logic, preserving a practical desktop workflow, and improving maintainability without pretending the tool is a certified lab platform.
