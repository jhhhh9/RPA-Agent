$ErrorActionPreference = "Stop"

# Build a standalone Windows exe for ordinary users.
# Run on Windows PowerShell from the project root:
#   .\scripts\build-windows.ps1

if (!(Test-Path ".venv")) {
  py -3.11 -m venv .venv
}
. .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e . pyinstaller
pyinstaller --clean --onefile --name local-rpa-agent src\local_rpa_agent\main.py
Write-Host "Built: dist\local-rpa-agent.exe"
