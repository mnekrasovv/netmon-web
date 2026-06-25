#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
PYTHON_SCRIPT="$SCRIPT_DIR/server.py"

if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo "[ERROR] Python 3 not found."
    echo "        Ubuntu/Debian: sudo apt install python3 python3-venv python3-pip"
    exit 1
fi

if ! "$PYTHON" -c "import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)" 2>/dev/null; then
    echo "[ERROR] Python 3.8+ required. Found: $("$PYTHON" --version 2>&1)"
    exit 1
fi

if ! "$PYTHON" -m venv --help &>/dev/null; then
    echo "[ERROR] venv module not found."
    echo "        Ubuntu/Debian: sudo apt install python3-venv"
    exit 1
fi

if [[ ! -f "$VENV_DIR/bin/activate" ]]; then
    echo "Creating virtual environment..."
    "$PYTHON" -m venv "$VENV_DIR" || { echo "[ERROR] Failed to create venv"; exit 1; }
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

if ! python -c "import fastapi, uvicorn" &>/dev/null; then
    echo "Installing dependencies..."
    pip install -r "$SCRIPT_DIR/requirements.txt" --quiet
fi

python "$PYTHON_SCRIPT" "$@"
