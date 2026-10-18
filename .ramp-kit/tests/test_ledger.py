import json
import sys
from pathlib import Path

import pytest

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT))

from rampkit import cli, guardrails, ledger  # noqa: E402
from rampkit.core import RampError  # noqa: E402


def make_task(repo: Path, task_id: str = "empty-timesteps", recipe: str = "scheduler-input-validation") -> Path:
    task = json.loads((KIT / "examples/empty-timesteps.json").read_text())
    task["id"] = task_id
    task["recipe"] = recipe
    directory = repo / ".ramp" / task_id
    directory.mkdir(parents=True)
    (directory / "task.json").write_text(json.dumps(task))
    return directory


def write_ledger(directory: Path, entries: list[dict]):
    (directory / ledger.LEDGER).write_text(json.dumps(entries))


def event(name: str, at: str, where: str = "local", **details) -> dict:
    return {"event": name, "at": at, "where": where, **details}


def verified(at: str, phase: str, status: str, level: str = "fast", where: str = "local") -> dict:
    return event("verified", at, where, phase=phase, level=level, status=status)


def test_task_metrics_measures_milestones_and_rework(tmp_path):
    directory = make_task(tmp_path)
    write_ledger(
        directory,
        [
            event("prepared", "2026-10-01T09:00:00+00:00", recipe="scheduler-input-validation"),
            event("assessed", "2026-10-01T09:20:00+00:00", decision="REVISE"),
            event("assessed", "2026-10-01T09:40:00+00:00", decision="COMPATIBLE"),
            verified("2026-10-01T10:00:00+00:00", "baseline", "FAIL"),
            verified("2026-10-01T10:30:00+00:00", "baseline", "EXPECTED_FAILURE"),
            verified("2026-10-01T11:00:00+00:00", "candidate", "FAIL"),
            verified("2026-10-01T11:30:00+00:00", "candidate", "PASS"),
            verified("2026-10-01T12:00:00+00:00", "candidate", "PASS", level="full"),
            event("wording_approved", "2026-10-01T13:00:00+00:00", by="Alessandro"),
            event("pr_opened", "2026-10-01T13:30:00+00:00", by="agent"),
            verified("2026-10-01T13:45:00+00:00", "candidate", "FAIL", level="full", where="ci"),
            event("remote_ci", "2026-10-01T14:00:00+00:00", by="github", status="PASS"),
            event("merged", "2026-10-02T09:00:00+00:00", by="maintainer"),
        ],
    )
    result = ledger.metrics(tmp_path)
    task = result["tasks"][0]
    assert result["status"] == "MEASURED"
    assert task["outcome"] == "merged"
    assert task["hours_from_prepared"] == {
        "baseline_reproduced": 1.5,
        "fast_checks_passed": 2.5,
        "full_checks_passed": 3.0,
        "wording_approved": 4.0,
        "pr_opened": 4.5,
        "merged": 24.0,
    }
    assert task["rework"] == {
        "candidate_runs": 3,
        "failed_candidate_runs": 1,
        "baseline_runs_not_reproduced": 1,
        "architecture_pushback": 1,
        "remote_ci_failures": 1,
    }
    assert result["candidate_exception_rate"] == 0.33
    assert (tmp_path / ".ramp/metrics.json").is_file()


def test_ci_runs_do_not_count_as_local_milestones(tmp_path):
    directory = make_task(tmp_path)
    write_ledger(
        directory,
        [
            event("prepared", "2026-10-01T09:00:00+00:00"),
            verified("2026-10-01T10:00:00+00:00", "candidate", "PASS", level="full", where="ci"),
        ],
    )
    task = ledger.metrics(tmp_path)["tasks"][0]
    assert task["milestones"]["full_checks_passed"] is None
    assert task["rework"]["candidate_runs"] == 0
    assert task["outcome"] == "open"


def test_metrics_reports_tasks_without_ledger_and_no_data(tmp_path):
    make_task(tmp_path)
    result = ledger.metrics(tmp_path)
    assert result["status"] == "NO_DATA"
    assert result["tasks_without_ledger"] == ["empty-timesteps"]
    assert result["baseline"]["status"] == "NOT_SUPPLIED"


def test_by_recipe_reports_time_to_first_merge(tmp_path):
    first = make_task(tmp_path, "first-task")
    second = make_task(tmp_path, "second-task")
    write_ledger(first, [event("prepared", "2026-10-01T09:00:00+00:00")])
    write_ledger(
        second,
        [event("prepared", "2026-10-02T09:00:00+00:00"), event("merged", "2026-10-03T09:00:00+00:00", by="m")],
    )
    recipe = ledger.metrics(tmp_path)["by_recipe"]["scheduler-input-validation"]
    assert recipe == {
        "tasks": 2,
        "merged": 1,
        "first_prepared": "2026-10-01T09:00:00+00:00",
        "first_merged": "2026-10-03T09:00:00+00:00",
        "hours_to_first_merge": 48.0,
    }


def test_baseline_comparison_requires_a_source(tmp_path):
    directory = make_task(tmp_path)
    write_ledger(
        directory,
        [event("prepared", "2026-10-01T00:00:00+00:00"), event("merged", "2026-10-02T00:00:00+00:00", by="m")],
    )
    with pytest.raises(RampError, match="baseline-source"):
        ledger.metrics(tmp_path, baseline_hours=240)
    baseline = ledger.metrics(tmp_path, baseline_hours=240, baseline_source="Ops lead, Q3 ticket export")["baseline"]
    assert baseline["median_hours_to_merge"] == 24.0
    assert baseline["reduction"] == 0.9


def test_workflow_summary_counts_human_gates():
    summary = ledger.workflow_summary()
    assert summary["counts"] == {"kit": 5, "agent": 4, "human": 3}
    assert summary["automated_share"] == 0.75
    assert len(summary["human_gates"]) == 3


def test_record_appends_reported_event(tmp_path):
    directory = make_task(tmp_path)
    result = ledger.record(tmp_path, "empty-timesteps", "remote_ci", "github", "https://ci/run/1", "PASS", None)
    assert result["status"] == "RECORDED"
    [entry] = json.loads((directory / ledger.LEDGER).read_text())
    assert entry["event"] == "remote_ci"
    assert entry["status"] == "PASS"
    assert entry["observed_by"] == "reported"


@pytest.mark.parametrize(
    "event_name, by, status, at, message",
    [
        ("prepared", "x", "", None, "Unsupported event"),
        ("wording_approved", "  ", "", None, "do not record an approval nobody gave"),
        ("remote_ci", "github", "", None, "PASS or FAIL"),
        ("merged", "m", "PASS", None, "only to remote_ci"),
        ("merged", "m", "", "2026-10-01T09:00:00", "timezone"),
    ],
)
def test_record_rejects_invalid_events(tmp_path, event_name, by, status, at, message):
    make_task(tmp_path)
    with pytest.raises(RampError, match=message):
        ledger.record(tmp_path, "empty-timesteps", event_name, by, "", status, at)


def test_malformed_ledger_is_an_error(tmp_path):
    directory = make_task(tmp_path)
    (directory / ledger.LEDGER).write_text('{"event": "prepared"}')
    with pytest.raises(RampError, match="Malformed ledger"):
        ledger.metrics(tmp_path)


def test_cli_records_verify_result_with_environment(tmp_path, monkeypatch, capsys):
    directory = make_task(tmp_path)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setattr(
        cli.core,
        "verify",
        lambda repo, task, level, phase: {
            "status": "PASS",
            "phase": phase,
            "level": level,
            "run_id": "20261001T000000Z",
        },
    )
    assert cli.main(["--repo", str(tmp_path), "verify", "empty-timesteps", "--level", "full"]) == 0
    capsys.readouterr()
    [entry] = json.loads((directory / ledger.LEDGER).read_text())
    assert entry["where"] == "ci"
    assert (entry["phase"], entry["level"], entry["status"]) == ("candidate", "full", "PASS")


def test_cli_metrics_without_data_exits_cleanly(tmp_path, capsys):
    assert cli.main(["--repo", str(tmp_path), "metrics"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "NO_DATA"


def test_guardrails_summarise_installed_policy(tmp_path, monkeypatch):
    monkeypatch.setattr(guardrails, "doctor", lambda repo, dependencies: {"status": "PASS", "findings": []})
    (tmp_path / ".github/workflows").mkdir(parents=True)
    (tmp_path / ".github/workflows/ramp-kit.yml").write_text((KIT / "templates/fork-ci.yml").read_text())
    (tmp_path / ".cursorignore").write_text((KIT / "templates/cursorignore.txt").read_text())
    (tmp_path / ".cursor").mkdir()
    (tmp_path / ".cursor/mcp.json").write_text(json.dumps({"mcpServers": {"docs": {}}}))
    result = guardrails.guardrails(tmp_path)
    assert result["status"] == "PASS"
    assert all(result["ci_controls"].values())
    assert result["mcp"]["configured_in_repository"] == ["docs"]
    assert ".env" in result["cursorignore"]
    assert "src/diffusers/schedulers/scheduling_ddpm.py" in result["editable_files"]
    text = (tmp_path / ".ramp/guardrails.md").read_text()
    assert "## Not enforced by this kit" in text
    assert "Target: not configured" in text


def test_guardrails_flag_missing_ci_controls(tmp_path, monkeypatch):
    monkeypatch.setattr(guardrails, "doctor", lambda repo, dependencies: {"status": "ERROR", "findings": ["x"]})
    result = guardrails.guardrails(tmp_path)
    assert result["status"] == "ERROR"
    assert not any(result["ci_controls"].values())
    assert result["mcp"]["configured_in_repository"] == []
