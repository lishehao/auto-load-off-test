# Validation Matrix

This matrix separates software evidence from claims that require physical instruments, a calibrated bench, or a
target workstation. The project currently has no public live-instrument validation record.

## Evidence Levels

- **Automated hardware-free**: runs with deterministic data, pure domain logic, temporary files, or fake ports.
- **Manual real-UI**: uses the actual Tkinter application window but no AWG/oscilloscope hardware.
- **Not validated**: requires physical instruments, electrical measurements, or target-machine certification.

## Matrix

| Surface | Level | Current evidence | What it does not prove |
| --- | --- | --- | --- |
| Sweep generation and DSP | Automated hardware-free | Domain tests cover linear/log sweeps, gain/phase, auto-range, and correction behavior. | Instrument timing, acquisition fidelity, or DUT response. |
| Capability preflight | Automated hardware-free | Registry tests cover current model profiles, channels, ranges, coupling, impedance, trigger modes, and unsupported selections. | That every documented limit has been re-verified on a physical unit. |
| Adapter selection | Automated hardware-free | Registry/factory tests resolve known production and fake adapters and reject unsupported models clearly. | SCPI compatibility with connected firmware revisions. |
| Resource discovery and test-connect | Automated hardware-free | Fake scanners and identity probes cover empty, offline, unsupported, and connected receipt states. | Live VISA backend enumeration or real `*IDN?` responses. |
| Measurement/reference input | Automated hardware-free | Strict tests reject missing fields, length mismatches, NaN/inf gain, non-positive/duplicate/unsorted frequencies, and invalid references. | Provenance or metrological quality of third-party files. |
| Reference correction | Automated hardware-free | The 72-point fixture reconstructs corrected gain/phase from raw plus reference curves and compares against checked-in expected arrays. | Calibration traceability, uncertainty, or bench accuracy. |
| Export and reload | Automated hardware-free | MAT/CSV/TXT export, metadata boundary, and MAT/CSV reload are verified end to end. | Compatibility with every external analysis tool/version. |
| Tk workflow state | Automated hardware-free | Pure view-model/event-handler tests cover fixture/live/loaded source states, receipts, Bode defaults, and neutral hardware status. | Pixel-perfect rendering on every OS/theme. |
| Operator demo | Manual real-UI | The checked-in poster/MP4 captures the actual Tk window from 0/72 through 72/72, a loaded reference/coverage receipt, and a temporary export receipt. | A live sweep or connected-instrument validation. |
| Windows one-folder package | Automated hardware-free | CI builds PyInstaller output and runs bundled fixture/reference/export/reload through `--package-smoke`. | Driver installation, manual Windows GUI smoke, code signing, or live VISA access. |
| Stop/output-off behavior | Automated hardware-free only | Fake-port task-runner tests cover stop, cleanup attempts, timeout, and warning events. | Electrical output-off latency or fail-safe behavior on real hardware. |
| Live AWG/oscilloscope workflow | Not validated | Production adapters and capability profiles are inspectable in code. | Discovery, configure, trigger, sweep, stop, calibration, or export on a physical bench. |
| Metrology and safety certification | Not validated | Operator checks and software preflight are documented. | Measurement uncertainty, calibration certification, DUT protection, or production safety certification. |

## Reproducible Checks

```bash
PYTHONPATH=src python -m unittest discover -s tests
python -m ruff check src/app tests scripts
```

The Windows packaging job additionally runs:

```text
AutoLoadOffTest.exe --package-smoke
```

It writes `__data__/package_smoke_receipt.json` with `live_hardware_used: false` and verifies exported artifacts.

## Safe Public Wording

Safe:

> Refactored a Python/Tkinter AWG-oscilloscope workflow into layered application, domain, persistence, and adapter
> boundaries; added deterministic hardware-free calibration/export tests, mocked discovery, operator receipts, and
> cross-platform CI with a Windows packaged smoke.

Not supported by current evidence:

- "Validated on live AWG and oscilloscope hardware."
- "Calibrated or metrology-grade measurement system."
- "Production-certified test platform" or "fail-safe hardware shutdown."
- "Works with any VISA instrument" or any unregistered model.
