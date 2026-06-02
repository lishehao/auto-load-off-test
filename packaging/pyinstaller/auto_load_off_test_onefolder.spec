# PyInstaller spec for a Windows one-folder build.
# Run from the repository root:
#   python -m PyInstaller packaging/pyinstaller/auto_load_off_test_onefolder.spec --clean --noconfirm

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

datas = [
    (str(ROOT / "demo_data"), "demo_data"),
    (str(ROOT / "docs" / "images" / "auto-load-off-test-point-replay-demo.png"), "docs/images"),
]

block_cipher = None

a = Analysis(
    [str(ROOT / "src" / "main.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "scipy.io",
        "scipy.interpolate",
        "matplotlib.backends.backend_tkagg",
        "mplcursors",
        "pyvisa",
        "pyvisa_py",
        "serial",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AutoLoadOffTest",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="AutoLoadOffTest",
)
