param(
    [string]$RuntimeRoot = "$env:LOCALAPPDATA\AutoLoadOffTest",
    [switch]$SkipSmoke
)

$ErrorActionPreference = "Stop"

$isWindowsPlatform = [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform(
    [System.Runtime.InteropServices.OSPlatform]::Windows
)
if (-not $isWindowsPlatform) {
    Write-Warning "This packaging spike is intended for Windows. Continuing because PyInstaller may still validate the spec."
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

python -m pip install --upgrade pip
python -m pip install -e ".[build]"

$env:AUTO_LOAD_OFF_TEST_ROOT = $RuntimeRoot
python -m PyInstaller packaging/pyinstaller/auto_load_off_test_onefolder.spec --clean --noconfirm

$exePath = Join-Path $repoRoot "dist\AutoLoadOffTest\AutoLoadOffTest.exe"
if (-not (Test-Path $exePath)) {
    throw "PyInstaller did not create $exePath"
}

if (-not $SkipSmoke) {
    $process = Start-Process -FilePath $exePath -ArgumentList "--package-smoke" -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "Packaged no-hardware smoke failed with exit code $($process.ExitCode)"
    }

    $receiptPath = Join-Path $RuntimeRoot "__data__\package_smoke_receipt.json"
    if (-not (Test-Path $receiptPath)) {
        throw "Packaged smoke did not create receipt: $receiptPath"
    }

    $receipt = Get-Content $receiptPath -Raw | ConvertFrom-Json
    if ($receipt.status -ne "passed" -or $receipt.live_hardware_used -ne $false) {
        throw "Packaged smoke receipt did not preserve the hardware-free boundary"
    }
    foreach ($artifact in $receipt.artifacts) {
        if (-not (Test-Path $artifact)) {
            throw "Packaged smoke artifact is missing: $artifact"
        }
    }
    Write-Host "Automated no-hardware package smoke passed: $receiptPath"
}

Write-Host ""
Write-Host "Built: dist\AutoLoadOffTest\AutoLoadOffTest.exe"
Write-Host "Runtime root for smoke testing: $env:AUTO_LOAD_OFF_TEST_ROOT"
Write-Host ""
Write-Host "Manual UI smoke checklist:"
Write-Host "1. Launch dist\AutoLoadOffTest\AutoLoadOffTest.exe"
Write-Host "2. Click Load Demo Fixture"
Write-Host "3. Confirm the plot and 'No hardware - simulated fixture' label are visible"
Write-Host "4. Save Data to a writable folder and verify MAT/CSV/TXT files"
Write-Host ""
Write-Host "Live hardware still requires NI-VISA/Keysight IO Libraries or a working pyvisa backend plus drivers."
