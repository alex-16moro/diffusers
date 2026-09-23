#!/usr/bin/env bash
# Bootstrap is networked. Verification uses local dependencies and HF offline settings.
set -euo pipefail
REPO=$(cd "${1:?Pass the Diffusers checkout}" && pwd)
HERE=$(cd "$(dirname "$0")" && pwd)
PY=${PYTHON:-python3.12}
command -v "$PY" >/dev/null || { echo 'Python 3.12 is required. Install it or set PYTHON to its executable.' >&2; exit 2; }
"$PY" -c 'import sys; assert sys.version_info[:2] == (3, 12), "Use Python 3.12 (set PYTHON to its executable)"'
if [ ! -x "$REPO/.ramp-venv/bin/python" ] || ! "$REPO/.ramp-venv/bin/python" -m pip --version >/dev/null 2>&1; then
    if ! "$PY" -m venv "$REPO/.ramp-venv"; then
        echo "Cannot create .ramp-venv. Install python3.12-venv (Debian/Ubuntu), then rerun this script." >&2
        echo "Alternatively, if virtualenv is already available: $PY -m virtualenv $REPO/.ramp-venv; then rerun this script." >&2
        exit 2
    fi
fi
printf '*\n' > "$REPO/.ramp-venv/.gitignore"
PY="$REPO/.ramp-venv/bin/python"
"$PY" -c 'import sys; assert sys.version_info[:2] == (3, 12), "Existing .ramp-venv must use Python 3.12"'
"$PY" -m pip install 'torch==2.7.1+cpu' --index-url https://download.pytorch.org/whl/cpu
"$PY" -m pip install -r "$HERE/requirements.txt"
"$PY" -m pip install --no-deps --no-build-isolation -e "$REPO"
"$PY" -c 'import torch; assert torch.version.cuda is None; print(torch.__version__)'
