"""Workflow evidence for cycle time and rework. It measures kit-gated steps, not business value."""

from __future__ import annotations

import os
import statistics
from datetime import datetime, timezone
from pathlib import Path

from .core import RampError, load, read_task, safe_path, task_dir, write

LEDGER = "ledger.json"

# Events the kit cannot observe. A person or the forge must have done them; the agent only records them.
REPORTED_EVENTS = ("wording_approved", "pr_opened", "remote_ci", "merged", "closed_unmerged")

WORKFLOW = [
    {"step": "Describe the outcome", "actor": "human"},
    {"step": "Write the task spec from source", "actor": "agent"},
    {"step": "Validate the spec and scaffold tests", "actor": "kit"},
    {"step": "Assess architectural fit", "actor": "agent"},
    {"step": "Reproduce the problem on the original implementation", "actor": "kit"},
    {"step": "Implement and propagate marked copies", "actor": "agent"},
    {"step": "Fast and full verification", "actor": "kit"},
    {"step": "Generate the review report and reviewer-text inventory", "actor": "kit"},
    {"step": "Approve the exact reviewer-visible wording", "actor": "human"},
    {"step": "Publish to the named fork", "actor": "agent"},
    {"step": "Fork CI re-verification", "actor": "kit"},
    {"step": "Maintainer review and merge", "actor": "human"},
]

MILESTONES = (
    "baseline_reproduced",
    "fast_checks_passed",
    "full_checks_passed",
    "wording_approved",
    "pr_opened",
    "merged",
)

LIMITATIONS = [
    "Timestamps come from the clock of the machine that ran each command.",
    "Reported events (approval, PR, remote CI, merge) are recorded on instruction; the kit cannot verify them.",
    "Tasks prepared before the ledger existed have no lifecycle data.",
    "The ledger measures the after-state only. The before-state baseline must come from the process owner.",
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_time(value: str) -> datetime:
    try:
        moment = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise RampError(f"Timestamp must be ISO 8601 with a timezone: {value}") from exc
    if moment.tzinfo is None:
        raise RampError(f"Timestamp must include a timezone: {value}")
    return moment


def where() -> str:
    return "ci" if os.environ.get("GITHUB_ACTIONS") == "true" else "local"


def events(directory: Path) -> list[dict]:
    path = directory / LEDGER
    if not path.is_file():
        return []
    entries = load(path)
    if not isinstance(entries, list) or any(not isinstance(e, dict) for e in entries):
        raise RampError(f"Malformed ledger: {path}; expected a list of event objects.")
    return entries


def append(directory: Path, event: str, at: str | None = None, **details) -> dict:
    entry = {"event": event, "at": at or now(), "where": where(), **details}
    write(directory / LEDGER, [*events(directory), entry])
    return entry


def record(repo: Path, task_id: str, event: str, by: str, ref: str, status: str, at: str | None) -> dict:
    read_task(repo, task_id)
    if event not in REPORTED_EVENTS:
        raise RampError(f"Unsupported event: {event}. Record one of: {', '.join(REPORTED_EVENTS)}.")
    if not by.strip():
        raise RampError("Name who performed the event; do not record an approval nobody gave.")
    if event == "remote_ci" and status not in ("PASS", "FAIL"):
        raise RampError("remote_ci needs --status PASS or FAIL from the actual CI run.")
    if event != "remote_ci" and status:
        raise RampError("--status applies only to remote_ci.")
    if at:
        parse_time(at)
    details = {"by": by.strip(), "observed_by": "reported"}
    if ref:
        details["ref"] = ref
    if status:
        details["status"] = status
    entry = append(task_dir(repo, task_id), event, at, **details)
    return {
        "status": "RECORDED",
        "entry": entry,
        "next_action": "Commit the updated ledger with the task record when publishing.",
    }


def first(entries: list[dict], **match) -> dict | None:
    return next((e for e in entries if all(e.get(k) == v for k, v in match.items())), None)


def hours(start: str, end: str) -> float:
    return round((parse_time(end) - parse_time(start)).total_seconds() / 3600, 2)


def task_metrics(task: dict, entries: list[dict]) -> dict:
    entries = sorted(entries, key=lambda e: parse_time(e["at"]))
    local = [e for e in entries if e.get("where") == "local"]
    prepared = first(entries, event="prepared")
    reached = {
        "baseline_reproduced": first(local, event="verified", phase="baseline", status="EXPECTED_FAILURE"),
        "fast_checks_passed": first(local, event="verified", phase="candidate", status="PASS"),
        "full_checks_passed": first(local, event="verified", phase="candidate", level="full", status="PASS"),
        "wording_approved": first(entries, event="wording_approved"),
        "pr_opened": first(entries, event="pr_opened"),
        "merged": first(entries, event="merged"),
    }
    milestones = {"prepared": prepared["at"] if prepared else None}
    milestones.update({name: entry["at"] if entry else None for name, entry in reached.items()})
    candidate_runs = [e for e in local if e["event"] == "verified" and e.get("phase") == "candidate"]
    baseline_runs = [e for e in local if e["event"] == "verified" and e.get("phase") == "baseline"]
    ci_runs = [e for e in entries if e.get("where") == "ci" and e["event"] == "verified"]
    reported_ci = [e for e in entries if e["event"] == "remote_ci"]
    if first(entries, event="merged"):
        outcome = "merged"
    elif first(entries, event="closed_unmerged"):
        outcome = "closed_unmerged"
    else:
        outcome = "open"
    return {
        "task_id": task["id"],
        "recipe": task["recipe"],
        "outcome": outcome,
        "milestones": milestones,
        "hours_from_prepared": {
            name: hours(prepared["at"], at) if prepared and at else None
            for name, at in milestones.items()
            if name != "prepared"
        },
        "rework": {
            "candidate_runs": len(candidate_runs),
            "failed_candidate_runs": sum(e.get("status") != "PASS" for e in candidate_runs),
            "baseline_runs_not_reproduced": sum(e.get("status") != "EXPECTED_FAILURE" for e in baseline_runs),
            "architecture_pushback": sum(
                e["event"] == "assessed" and e.get("decision") in ("REVISE", "NEEDS_MAINTAINER") for e in entries
            ),
            "remote_ci_failures": sum(e.get("status") != "PASS" for e in ci_runs)
            + sum(e.get("status") == "FAIL" for e in reported_ci),
        },
    }


def workflow_summary() -> dict:
    counts = {actor: sum(s["actor"] == actor for s in WORKFLOW) for actor in ("kit", "agent", "human")}
    return {
        "steps": WORKFLOW,
        "counts": counts,
        "automated_share": round((counts["kit"] + counts["agent"]) / len(WORKFLOW), 2),
        "human_gates": [s["step"] for s in WORKFLOW if s["actor"] == "human"],
        "basis": "Designed workflow, not measured per task.",
    }


def median_hours(tasks: list[dict], milestone: str) -> dict:
    values = [t["hours_from_prepared"][milestone] for t in tasks if t["hours_from_prepared"][milestone] is not None]
    return {"median": statistics.median(values) if values else None, "tasks": len(values)}


def by_recipe(tasks: list[dict]) -> dict:
    result = {}
    for recipe in sorted({t["recipe"] for t in tasks}):
        group = [t for t in tasks if t["recipe"] == recipe]
        starts = [t["milestones"]["prepared"] for t in group if t["milestones"]["prepared"]]
        merges = [t["milestones"]["merged"] for t in group if t["milestones"]["merged"]]
        first_start = min(starts, key=parse_time) if starts else None
        first_merge = min(merges, key=parse_time) if merges else None
        result[recipe] = {
            "tasks": len(group),
            "merged": len(merges),
            "first_prepared": first_start,
            "first_merged": first_merge,
            "hours_to_first_merge": hours(first_start, first_merge) if first_start and first_merge else None,
        }
    return result


def compare(tasks: list[dict], baseline_hours: float | None, baseline_source: str) -> dict:
    if baseline_hours is None:
        return {"status": "NOT_SUPPLIED", "note": "Ask the process owner for the measured before-state cycle time."}
    if baseline_hours <= 0:
        raise RampError("--baseline-hours must be positive.")
    if not baseline_source.strip():
        raise RampError("--baseline-hours needs --baseline-source naming who measured it and how.")
    current = median_hours(tasks, "merged")["median"]
    return {
        "status": "SUPPLIED",
        "hours": baseline_hours,
        "source": baseline_source.strip(),
        "median_hours_to_merge": current,
        "reduction": round(1 - current / baseline_hours, 2) if current is not None else None,
        "note": "Compare like with like: the baseline should span the same request-to-merge boundary.",
    }


def metrics(repo: Path, baseline_hours: float | None = None, baseline_source: str = "") -> dict:
    root = safe_path(repo, ".ramp")
    measured, unmeasured = [], []
    for path in sorted(root.glob("*/task.json")) if root.is_dir() else []:
        task = read_task(repo, path.parent.name)
        entries = events(path.parent)
        if entries:
            measured.append(task_metrics(task, entries))
        else:
            unmeasured.append(task["id"])
    candidate = sum(t["rework"]["candidate_runs"] for t in measured)
    failed = sum(t["rework"]["failed_candidate_runs"] for t in measured)
    result = {
        "status": "MEASURED" if measured else "NO_DATA",
        "generated_at": now(),
        "tasks_measured": len(measured),
        "tasks_without_ledger": unmeasured,
        "median_hours_from_prepared": {name: median_hours(measured, name) for name in MILESTONES},
        "candidate_exception_rate": round(failed / candidate, 2) if candidate else None,
        "architecture_pushback": sum(t["rework"]["architecture_pushback"] for t in measured),
        "remote_ci_failures": sum(t["rework"]["remote_ci_failures"] for t in measured),
        "by_recipe": by_recipe(measured),
        "baseline": compare(measured, baseline_hours, baseline_source),
        "workflow": workflow_summary(),
        "tasks": measured,
        "limitations": LIMITATIONS,
    }
    write(root / "metrics.json", result)
    result["next_action"] = (
        "Share metrics.json with the metric owner; the before-state baseline remains their measurement."
        if measured
        else "No task has a ledger yet; prepare a task to start recording."
    )
    return result
