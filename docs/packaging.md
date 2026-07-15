# Packaging

This project can be packaged for review or lab workstation setup, but packaged
artifacts are not live-hardware validated by default. Hardware use still depends
on the target machine's VISA backend, instrument drivers, cabling, and operator
safety checks.

## Recommended First Target

Use a Windows PyInstaller one-folder build first. One-folder output is easier to
debug than a one-file executable when bundling Tkinter, Matplotlib, SciPy,
PyVISA, and instrument-driver dependencies.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_windows_onefolder.ps1
```

The script installs the local package with the optional `build` dependency and
then runs:

```powershell
python -m PyInstaller packaging/pyinstaller/auto_load_off_test_onefolder.spec --clean --noconfirm
```

Expected output:

```text
dist/AutoLoadOffTest/AutoLoadOffTest.exe
```

## External Prerequisites

The package does not bundle lab driver runtimes. A live-hardware workstation
still needs one of these paths configured:

- NI-VISA, Keysight IO Libraries, or another compatible VISA runtime.
- Or a working `pyvisa-py` backend plus any USB/GPIB/serial support libraries
  required by the connected instruments.
- OS-level USB/GPIB/serial permissions where relevant.
- Verified instrument addresses and model labels.

## Runtime Data Paths

Set `AUTO_LOAD_OFF_TEST_ROOT` on packaged workstations so settings and saved
measurements do not depend on the launch directory:

```powershell
$env:AUTO_LOAD_OFF_TEST_ROOT = "$env:LOCALAPPDATA\\AutoLoadOffTest"
```

The app writes:

- `__config__/settings.json`
- `__data__/measurement/`

under that root.

## No-Hardware Packaging Smoke

Before using a packaged artifact as portfolio/demo evidence:

1. Launch `dist/AutoLoadOffTest/AutoLoadOffTest.exe`.
2. Confirm the operator console opens without a Python traceback.
3. Click `Load Demo Fixture`.
4. Confirm the plot is visible and labeled `No hardware - simulated fixture`.
5. Confirm the source receipt names `hyperframe_simulated_fixture.mat`.
6. Click `Save Data` and verify MAT/CSV/TXT files are written to a writable path.
7. Close the app and confirm no shutdown error appears.

This smoke check validates packaged UI/data workflow only. It is not live
hardware validation.

## Live-Hardware Packaging Smoke

Do this only on a real lab workstation:

1. Install/verify the VISA backend and drivers.
2. Set `AUTO_LOAD_OFF_TEST_ROOT` to a writable app-data folder.
3. Launch the packaged app.
4. Use `Scan Resources` and `Test Connect`.
5. Confirm IDN/address/model status before starting a sweep.
6. Run a short, conservative sweep into a safe load/DUT.
7. Verify Stop turns the AWG output off and warnings are visible.

Record the instrument models, VISA backend, OS version, and result artifacts.
