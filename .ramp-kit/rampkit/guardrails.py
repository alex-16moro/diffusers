"""What the agent can reach in this checkout, derived from the installed policy rather than restated by hand."""

from __future__ import annotations

import json
from pathlib import Path

from .core import doctor, load, profile, required_checks, safe_path

NOT_ENFORCED = [
    "Operating-system and network isolation of the agent process.",
    "Egress allowlisting; configure it on the agent host or Cursor environment.",
    "MCP servers or tools configured outside this repository (user, team or dashboard level).",
    "Cursor's own file tools can read paths outside the approved sources; .cursorignore is a context hint only.",
]


def workflow_controls(text: str) -> dict:
    return {
        "read_only_token": "contents: read" in text,
        "credentials_not_persisted": "persist-credentials: false" in text,
        "policy_from_pr_base_commit": "github.event.pull_request.base.sha" in text,
        "rejects_changed_policy": "cmp policy/.ramp-kit/attachment.json" in text,
        "requires_task_record": "No task record committed" in text,
    }


def mcp_servers(repo: Path) -> dict:
    path = safe_path(repo, ".cursor/mcp.json")
    if not path.is_file():
        return {"configured_in_repository": [], "source": ".cursor/mcp.json absent"}
    try:
        servers = sorted(json.loads(path.read_text()).get("mcpServers", {}))
    except (ValueError, AttributeError):
        return {"configured_in_repository": None, "source": ".cursor/mcp.json unreadable; inspect it by hand"}
    return {"configured_in_repository": servers, "source": ".cursor/mcp.json"}


def ignore_entries(repo: Path) -> list[str]:
    path = safe_path(repo, ".cursorignore")
    if not path.is_file():
        return []
    return [line for line in path.read_text().splitlines() if line.strip() and not line.startswith("#")]


def publication(repo: Path) -> dict | None:
    path = safe_path(repo, ".ramp-kit/publication.json")
    return load(path) if path.is_file() else None


def markdown(summary: dict) -> str:
    target = summary["publication"]
    mcp = summary["mcp"]["configured_in_repository"]
    lines = [
        "# Ramp Kit guardrails",
        "",
        f"Kit integrity: **{summary['integrity']['status']}**"
        + "".join(f"\n- {finding}" for finding in summary["integrity"]["findings"]),
        "",
        "## What the agent can edit",
        "Any other change fails verification with a SCOPE finding.",
        *[f"- `{p}`" for p in summary["editable_files"]],
        "",
        "## What the kit serves as context",
        "The `context` command serves only these pinned files and rejects anything else.",
        *[f"- `{p}`" for p in summary["approved_sources"]],
        "",
        "## Checks that gate a contribution",
        *[f"- {c}" for c in summary["required_checks"]],
        "",
        "## Publication",
        f"- Target: `{target['repository']}` on `{target['base_branch']}`" if target else "- Target: not configured",
        "- Commit, push and pull request each wait for human approval of the exact wording.",
        "",
        "## Fork CI controls",
        *[f"- {name.replace('_', ' ')}: {'yes' if ok else 'NO'}" for name, ok in summary["ci_controls"].items()],
        "",
        "## MCP",
        f"- Configured in this repository: {', '.join(mcp) if mcp else 'none' if mcp == [] else 'unknown'}"
        f" ({summary['mcp']['source']})",
        "",
        "## Context hints (.cursorignore)",
        *[f"- `{entry}`" for entry in summary["cursorignore"]],
        "",
        "## Not enforced by this kit",
        *[f"- {item}" for item in summary["not_enforced"]],
    ]
    return "\n".join(lines) + "\n"


def guardrails(repo: Path) -> dict:
    prof = profile()
    workflow = safe_path(repo, ".github/workflows/ramp-kit.yml")
    check = doctor(repo, dependencies=False)
    summary = {
        "status": "PASS" if check["status"] == "PASS" else "ERROR",
        "integrity": {"status": check["status"], "findings": check["findings"]},
        "editable_files": prof["editable_files"],
        "approved_sources": sorted(prof["sources"]),
        "required_checks": required_checks(),
        "publication": publication(repo),
        "ci_controls": workflow_controls(workflow.read_text() if workflow.is_file() else ""),
        "mcp": mcp_servers(repo),
        "cursorignore": ignore_entries(repo),
        "not_enforced": NOT_ENFORCED,
    }
    path = safe_path(repo, ".ramp/guardrails.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown(summary))
    summary["markdown"] = str(path)
    summary["next_action"] = (
        "Share guardrails.md with security; the items under 'Not enforced' need a deployment answer."
        if summary["status"] == "PASS"
        else "Resolve the integrity findings before presenting these guardrails."
    )
    return summary
