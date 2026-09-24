#!/usr/bin/env bash
set -euo pipefail

PHASE=${1:?Pass install or start}
case "$PHASE" in
    install|start) ;;
    *) echo 'Expected install or start.' >&2; exit 2 ;;
esac
REPO=$(git rev-parse --show-toplevel)
cd "$REPO"

if [ -e ramp-kit ] || [ -L ramp-kit ]; then
    echo 'Legacy ramp-kit path detected. Create a fresh Cursor environment without the diffuser_agent repository or legacy install command. Do not reuse this Build for clean acceptance.' >&2
    exit 2
fi

if [ ! -f .ramp-kit/runtime/bootstrap.sh ]; then
    if [ "$PHASE" = install ]; then
        echo 'Default-branch preparation complete. No external kit repository was cloned. Start the Ramp Kit session on ramp-demo; startup will prepare its installed .ramp-kit runtime.'
        exit 0
    fi
    echo 'This branch has no installed .ramp-kit. Start the Ramp Kit session on ramp-demo.' >&2
    exit 2
fi

if [ "$PHASE" = install ] || [ ! -x .ramp-venv/bin/python ]; then
    bash .ramp-kit/runtime/bootstrap.sh "$REPO"
fi
.ramp-venv/bin/python .ramp-kit/run.py --repo "$REPO" doctor
