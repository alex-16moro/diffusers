#!/usr/bin/env python3
"""Cwd-independent stdio entry for diffusers-docs MCP.

Cloud Agent stdio is spawned from `/agent` (not the git repo) and cannot
create `/agent/.cursor`. Desktop Cursor uses the repo root as cwd. This
file is the `python3 -c` body in `.cursor/mcp.json` (keep them in sync)
and is also runnable as `python3 -u .cursor/mcp_stdio_boot.py`.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _launchers():
    yield Path(".cursor") / "mcp-diffusers-docs.py"
    repos = Path("/agent/repos")
    if repos.is_dir():
        yield from repos.glob("*/.cursor/mcp-diffusers-docs.py")
        yield from repos.glob("*/ramp-kit/.cursor/mcp-diffusers-docs.py")
    here = Path(__file__).resolve().parent / "mcp-diffusers-docs.py"
    yield here


def main() -> int:
    extra = [a for a in sys.argv[1:] if a != "--serve"]
    for raw in _launchers():
        path = Path(raw)
        if path.is_file():
            os.execv(
                sys.executable,
                [sys.executable, "-u", str(path.resolve()), "--serve", *extra],
            )
    sys.stderr.write(
        "diffusers-docs MCP: launcher not found "
        f"(cwd={Path.cwd()} file={Path(__file__).resolve() if '__file__' in dir() else 'stdin'}).\n"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
