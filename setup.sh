#!/bin/bash
#
# LUMO-Term Setup Script (Linux/macOS)
#
# Thin wrapper around install.py, which does the actual cross-platform work
# (Windows users run install.py directly, or setup.ps1).
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 not found. Please install Python 3.10+"
    exit 1
fi

exec python3 "$SCRIPT_DIR/install.py" "$@"
