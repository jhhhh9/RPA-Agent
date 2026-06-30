$ErrorActionPreference = "Stop"

# Build a standalone Windows exe for ordinary users.
# Run on Windows PowerShell from the project root:
#   powershell -ExecutionPolicy Bypass -File .\scripts\build-windows.ps1
#
# This script intentionally does not activate the virtualenv. Some Windows
# machines block Activate.ps1 by execution policy, so we call the venv python
# executable directly.

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

function Invoke-PythonLauncher {
  param([string[]]$Arguments)
  if (Get-Command py -ErrorAction SilentlyContinue) {
    try {
      & py -3.11 @Arguments
      return
    } catch {
      Write-Host "Python 3.11 launcher failed, falling back to default Python 3..."
      & py -3 @Arguments
      return
    }
  }
  if (Get-Command python -ErrorAction SilentlyContinue) {
    & python @Arguments
    return
  }
  throw "Python was not found. Install Python 3.11+ and enable 'Add python.exe to PATH'."
}

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (!(Test-Path $VenvPython)) {
  Invoke-PythonLauncher -Arguments @("-m", "venv", ".venv")
}
if (!(Test-Path $VenvPython)) {
  throw "Virtualenv python not found: $VenvPython"
}

& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -e . pyinstaller
& $VenvPython -m PyInstaller --clean --onefile --name local-rpa-agent --paths src run_agent.py

Write-Host "Built: dist\local-rpa-agent.exe"
