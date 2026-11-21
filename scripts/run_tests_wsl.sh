#!/bin/bash
# Run the tests from Windows through WSL (Home Assistant doesn't run on Windows):
#   MSYS_NO_PATHCONV=1 wsl -d Ubuntu -- bash scripts/run_tests_wsl.sh
# Expects a venv at ~/.venvs/assist-utils with requirements_test.txt installed.
cd "$(dirname "$0")/.." && "$HOME/.venvs/assist-utils/bin/python" -m pytest -q -p no:cacheprovider -rs "$@"
