"""Record which revisions fork CI actually verified.

Fork CI runs this from the trusted policy checkout (the PR base), after verification and
whether or not it passed. It reads only Git state, GitHub-provided environment variables
and the verification records under candidate/.ramp/. It never changes local readiness.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def load(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def task_records(candidate: Path) -> list[dict]:
    records = []
    for path in sorted((candidate / ".ramp").glob("*/candidate.json")):
        result = load(path) or {}
        policy = result.get("policy") if isinstance(result.get("policy"), dict) else {}
        records.append(
            {
                "task": path.parent.name,
                "status": result.get("status"),
                "level": result.get("level"),
                "patch_sha256": result.get("patch_sha256"),
                "patch_base_sha": result.get("base_sha"),
                "runner_kit_sha256": policy.get("runner_kit_sha256"),
                "installation_kit_sha256": policy.get("installation_kit_sha256"),
            }
        )
    return records


def provenance(policy: Path, candidate: Path, env: dict) -> dict:
    kit = policy / ".ramp-kit"
    sys.path.insert(0, str(kit))
    from rampkit import core  # the trusted runner from the policy checkout

    profile = load(kit / "profiles/diffusers.json") or {}
    pr_base, pr_head = env.get("RAMP_PR_BASE_SHA") or None, env.get("RAMP_PR_HEAD_SHA") or None
    tested = git(candidate, "rev-parse", "HEAD")
    parents = git(candidate, "rev-parse", "HEAD^@").split()
    policy_sha = git(policy, "rev-parse", "HEAD")
    tasks = task_records(candidate)
    upstream_pin = profile.get("base_sha")
    return {
        "kind": "fork_ci_provenance",
        "repository": env.get("GITHUB_REPOSITORY"),
        "pull_request": env.get("RAMP_PR_NUMBER") or None,
        "upstream_pin": upstream_pin,
        "pr_base_sha": pr_base,
        "pr_head_sha": pr_head,
        "tested_ref": env.get("GITHUB_REF"),
        "tested_checkout_sha": tested,
        "tested_checkout_parents": parents,
        "policy_checkout_sha": policy_sha,
        "run_id": env.get("GITHUB_RUN_ID"),
        "run_attempt": env.get("GITHUB_RUN_ATTEMPT"),
        "workflow": env.get("GITHUB_WORKFLOW"),
        "runner_kit_sha256": core.kit_hash(kit),
        "policy_installed_kit_sha256": (load(kit / "attachment.json") or {}).get("kit_sha256"),
        "candidate_installed_kit_sha256": (load(candidate / ".ramp-kit/attachment.json") or {}).get(
            "kit_sha256"
        ),
        "tasks": tasks,
        "consistency": {
            "policy_checkout_is_pr_base": policy_sha == pr_base,
            "tested_checkout_contains_pr_head": tested == pr_head or pr_head in parents,
            "tested_checkout_contains_pr_base": tested == pr_base or pr_base in parents,
            "task_patches_use_upstream_pin": all(t["patch_base_sha"] == upstream_pin for t in tasks),
        },
        "comparison_contract": (
            "Patch digests are computed against upstream_pin, so a local and a CI digest are comparable "
            "only when both records name the same pin. The tested checkout is GitHub's PR merge ref "
            "unless it equals the head SHA. This record does not change local readiness, remote CI "
            "status or human approval."
        ),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--policy", type=Path, required=True, help="Trusted PR-base checkout")
    parser.add_argument("--candidate", type=Path, required=True, help="Checkout that was verified")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    record = provenance(args.policy.resolve(), args.candidate.resolve(), dict(os.environ))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
