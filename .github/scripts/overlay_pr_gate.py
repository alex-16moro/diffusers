#!/usr/bin/env python3
"""File-scoped overlay gate for a diffusers-fork PR.

Never runs convention_check --all. Changed scheduler/test files only.
Exit code = convention_check blocking count (0 = pass). No matching
files → skip 0.

  OVERLAY_GATE_FILES   space-separated paths (tests / CI override)
  OVERLAY_GATE_BASE    git sha to diff against (PR base or previous push)
  OVERLAY_GATE_HEAD    git sha (default HEAD)
  OVERLAY_KIT          path to the ramp-kit clone (default: ./ramp-kit or this repo)
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
# Copied onto the fork at .github/scripts/; lives in the kit at tools/.
KIT_CANDIDATES = []
env_kit = os.environ.get("OVERLAY_KIT")
if env_kit:
    KIT_CANDIDATES.append(Path(env_kit))
KIT_CANDIDATES.extend(
    [
        Path.cwd() / "ramp-kit",
        HERE.parent.parent if HERE.parent.name == "tools" else HERE.parent.parent.parent,
        Path.cwd(),
    ]
)

RELEVANT = re.compile(
    r"(?:^|/)(?:scheduling_[^/]+\.py|test_scheduling_[^/]+\.py)$"
)


def _kit() -> Path:
    for cand in KIT_CANDIDATES:
        check = cand / "tools" / "convention_check.py"
        if check.is_file():
            return cand
    sys.stderr.write(
        "overlay_pr_gate: cannot find ramp-kit/tools/convention_check.py "
        "(clone alex-16moro/diffuser_agent as ramp-kit/)\n"
    )
    sys.exit(2)


def _git_changed(base: str, head: str) -> list[str]:
    if not base or set(base) <= {"0"}:
        return []
    proc = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACMR", f"{base}...{head}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        return []
    return [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]


def changed_files() -> list[str]:
    override = os.environ.get("OVERLAY_GATE_FILES", "").strip()
    if override:
        return override.split()
    base = os.environ.get("OVERLAY_GATE_BASE") or os.environ.get("BASE_SHA") or ""
    head = os.environ.get("OVERLAY_GATE_HEAD") or "HEAD"
    return _git_changed(base, head)


def is_relevant(path: str) -> bool:
    return bool(RELEVANT.search(path.replace("\\", "/")))


def main(argv=None) -> int:
    if argv and "--all" in argv:
        sys.stderr.write("overlay_pr_gate: refusing --all on the library fork\n")
        return 2
    kit = _kit()
    check = kit / "tools" / "convention_check.py"
    files = [
        f
        for f in changed_files()
        if is_relevant(f) and Path(f).is_file()
    ]
    if not files:
        print("ramp-kit overlay: no scheduler/test files in this change; skip")
        return 0
    print("ramp-kit overlay: file-scoped gate (never --all)")
    for f in files:
        print(f"  {f}")
    proc = subprocess.run([sys.executable, str(check), *files])
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
