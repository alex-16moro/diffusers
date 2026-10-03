#!/usr/bin/env bash
# Bootstrap is networked. Verification uses local dependencies and HF offline settings.
set -euo pipefail
REPO=$(cd "${1:?Pass the Diffusers checkout}" && pwd)
HERE=$(cd "$(dirname "$0")" && pwd)
PY=${PYTHON:-python3.12}
command -v "$PY" >/dev/null || { echo 'Python 3.12 is required. Install it or set PYTHON to its executable.' >&2; exit 2; }
"$PY" -c 'import sys; assert sys.version_info[:2] == (3, 12), "Use Python 3.12 (set PYTHON to its executable)"'
create_venv() {
    VENV="$REPO/.ramp-venv"
    rm -rf "$VENV"
    "$PY" -m venv "$VENV" 2>/dev/null && return 0
    # Debian/Ubuntu images often ship Python without ensurepip (python3.12-venv).
    # Create the environment without pip, then install pip into it with the
    # interpreter's own pip. No sudo or system package change is needed.
    echo "venv could not install pip (no ensurepip); creating .ramp-venv without pip and adding pip." >&2
    rm -rf "$VENV"
    if "$PY" -m venv --without-pip "$VENV" 2>/dev/null \
        && "$PY" -m pip --python "$VENV/bin/python" install --quiet pip 2>/dev/null; then
        return 0
    fi
    rm -rf "$VENV"
    "$PY" -m virtualenv --quiet "$VENV" 2>/dev/null && return 0
    rm -rf "$VENV"
    return 1
}
if [ ! -x "$REPO/.ramp-venv/bin/python" ] || ! "$REPO/.ramp-venv/bin/python" -m pip --version >/dev/null 2>&1; then
    if ! create_venv; then
        echo "Cannot create .ramp-venv: venv lacks ensurepip, and neither the interpreter's pip nor virtualenv is available." >&2
        echo "Install python3.12-venv (Debian/Ubuntu) or virtualenv for $PY, or set PYTHON to a Python 3.12 that has them, then rerun this script." >&2
        echo "In a Cursor cloud environment, add the package to the environment image; do not change the repository." >&2
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
