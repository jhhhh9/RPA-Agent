#!/usr/bin/env bash
set -euo pipefail

# Developer build helper for local macOS testing.
# Windows customer releases should be built on Windows with build-windows.ps1.

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e . pyinstaller
pyinstaller --clean --onefile --name local-rpa-agent src/local_rpa_agent/main.py
echo "Built: dist/local-rpa-agent"
