"""Trusted local checks. Agent judgement and human approval remain separate."""

from __future__ import annotations

import ast
import hashlib
import importlib.metadata
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


class RampError(Exception):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False).encode()


def load(path: Path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise RampError(f"Cannot read JSON {path}: {exc}") from exc


def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def safe_path(root: Path, relative: str) -> Path:
    rel = Path(relative)
    if rel.is_absolute() or not rel.parts or ".." in rel.parts:
        raise RampError(f"Path outside approved workspace: {relative}")
    root = root.resolve()
    path = root / rel
    # Reject symlinks even when their final target happens to be inside the workspace.
    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise RampError(f"Symlink not permitted: {relative}")
    if not path.resolve().is_relative_to(root):
        raise RampError(f"Path outside approved workspace: {relative}")
    return path


def git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True)
    if result.returncode:
        raise RampError(f"git {' '.join(args)} failed: {result.stderr.decode(errors='replace').strip()}")
    return result.stdout


def kit_root() -> Path:
    return Path(__file__).resolve().parent.parent


def profile(root: Path | None = None) -> dict:
    return load((root or kit_root()) / "profiles/diffusers.json")


def kit_hash(root: Path | None = None) -> str:
    root = root or kit_root()
    files = [("run.py", digest((root / "run.py").read_bytes()))]
    for folder in ("rampkit", "profiles", "recipes", "cursor", "templates", "examples", "runtime"):
        for path in sorted((root / folder).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                files.append((str(path.relative_to(root)), digest(path.read_bytes())))
    return digest(canonical(files))


def changed(repo: Path, base: str) -> list[str]:
    git(repo, "cat-file", "-e", f"{base}^{{commit}}")
    # Compare the entire working tree with the explicit base; include deletions and untracked files.
    paths = git(repo, "diff", "--name-only", "--no-renames", "-z", base).split(b"\0")
    paths += git(repo, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0")
    return sorted({p.decode() for p in paths if p})


def task_dir(repo: Path, task_id: str) -> Path:
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,60}", task_id):
        raise RampError("Task ID must use lowercase letters, digits and hyphens, starting with a letter.")
    return safe_path(repo, f".ramp/{task_id}")


def validate_task(task: dict, prof: dict):
    if not isinstance(task, dict):
        raise RampError("Task must be a JSON object.")
    required = ("id", "title", "request", "recipe", "editable_files", "criteria", "regression_test")
    if any(not task.get(key) for key in required):
        raise RampError(f"Task requires nonempty fields: {', '.join(required)}")
    task_dir(Path.cwd(), task["id"])
    if task.get("base_sha", prof["base_sha"]) != prof["base_sha"]:
        raise RampError("Task baseline differs from the installed profile; refresh the task with its owner.")
    if task["recipe"] != "scheduler-input-validation":
        raise RampError("Unsupported recipe. Extend and review the library profile before claiming coverage.")
    if not set(task["editable_files"]) <= set(prof["editable_files"]):
        raise RampError("Task edit scope exceeds the installed profile.")
    if prof["test_file"] not in task["editable_files"]:
        raise RampError("Task edit scope must include its mapped test file.")
    ids = set()
    all_tests = []
    for criterion in task["criteria"]:
        if not criterion.get("id") or criterion["id"] in ids or not criterion.get("text"):
            raise RampError("Each criterion needs a unique ID and text.")
        ids.add(criterion["id"])
        tests = criterion.get("tests", [])
        if not tests:
            raise RampError(f"Criterion {criterion['id']} has no test mapping.")
        for node in tests:
            if not re.fullmatch(
                re.escape(prof["test_file"]) + r"::[A-Za-z_][A-Za-z0-9_]*::test_[A-Za-z0-9_]+", node
            ):
                raise RampError(f"Unsupported test ID: {node}")
        all_tests.extend(tests)
    if task["regression_test"] not in all_tests:
        raise RampError("The regression test must be mapped to an acceptance criterion.")


def read_task(repo: Path, task_id: str) -> dict:
    task = load(task_dir(repo, task_id) / "task.json")
    validate_task(task, profile())
    if task["id"] != task_id:
        raise RampError("Task ID does not match its directory.")
    return task


def context(repo: Path, relative: str, symbol: str | None = None) -> dict:
    prof = profile()
    if relative not in prof["sources"]:
        raise RampError(f"Context path is not approved: {relative}. Ask the profile owner to extend it.")
    path = safe_path(repo, relative)
    text = path.read_text()
    lines = text.splitlines()
    start, end = 1, len(lines)
    if symbol:
        nodes = ast.parse(text).body
        for part in symbol.split("."):
            found = next((n for n in nodes if getattr(n, "name", None) == part), None)
            if found is None:
                raise RampError(f"Missing symbol {symbol} in {relative}; refresh the profile.")
            nodes = getattr(found, "body", [])
        start, end = found.lineno, found.end_lineno
    return {
        "path": relative,
        "start_line": start,
        "end_line": end,
        "sha256": digest(path.read_bytes()),
        "content": "\n".join(lines[start - 1 : end]),
    }


def doctor(repo: Path, dependencies: bool = True) -> dict:
    prof = profile()
    failures = []
    git(repo, "merge-base", "--is-ancestor", prof["base_sha"], "HEAD")
    for relative in prof["editable_files"]:
        if relative not in prof["sources"]:
            failures.append(f"Edit path has no approved source: {relative}")
    for relative, expected in prof["sources"].items():
        path = safe_path(repo, relative)
        if not path.is_file():
            failures.append(f"Missing reference: {relative}")
        original = git(repo, "show", f"{prof['base_sha']}:{relative}")
        if digest(original) != expected:
            failures.append(f"Baseline source mismatch: {relative}")
        if (
            path.is_file()
            and relative not in prof["editable_files"]
            and digest(path.read_bytes()) != expected
        ):
            failures.append(f"Protected reference changed: {relative}")
    for relative, symbols in prof.get("symbols", {}).items():
        for symbol in symbols:
            try:
                context(repo, relative, symbol)
            except (RampError, SyntaxError) as exc:
                failures.append(str(exc))
    for check in prof["upstream_checks"]:
        argv = check.get("command", [])
        if not argv or argv[0] not in ("{python}", "make"):
            failures.append(f"Unsupported check command: {check.get('id')}")
        for arg in argv:
            if arg.endswith(".py") and not safe_path(repo, arg).is_file():
                failures.append(f"Missing executable check input: {arg}")
    manifest = attachment(repo)
    if manifest.get("files"):
        if manifest.get("kit_sha256") != kit_hash():
            failures.append("Installed kit differs from the trusted runner. Review a kit upgrade separately.")
        for relative, checksum in manifest["files"].items():
            path = safe_path(repo, relative)
            if not path.is_file() or digest(path.read_bytes()) != checksum:
                failures.append(f"Protected kit file changed: {relative}")
    runtime = {"python": sys.version.split()[0]}
    if dependencies:
        import importlib.metadata

        for module in ("torch", "pytest", "ruff", "huggingface-hub", "safetensors"):
            try:
                runtime[module] = importlib.metadata.version(module)
            except importlib.metadata.PackageNotFoundError:
                failures.append(f"Missing dependency: {module}; run the bootstrap script.")
        if runtime.get("torch") != "2.7.1+cpu":
            failures.append("Supported demo runtime requires torch==2.7.1+cpu on Linux x86-64.")
        if sys.version_info[:2] != (3, 12):
            failures.append("Supported demo runtime is Python 3.12; other runtimes are unverified.")
    return {
        "status": "ERROR" if failures else "PASS",
        "base_sha": prof["base_sha"],
        "runtime": runtime,
        "findings": failures,
        "kit_sha256": kit_hash(),
        "limitations": [
            "Whole-agent OS/network isolation is not enforced by this kit.",
            "Architectural fit is an agent judgement requiring human review.",
        ],
    }


def prepare(repo: Path, spec: Path) -> dict:
    task = load(spec)
    prof = profile()
    validate_task(task, prof)
    directory = task_dir(repo, task["id"])
    if directory.exists():
        raise RampError(f"Task already exists: {task['id']}; inspect it instead of overwriting it.")
    check = doctor(repo, dependencies=False)
    if check["status"] != "PASS":
        raise RampError("; ".join(check["findings"]))
    task["base_sha"] = prof["base_sha"]
    scaffold = test_scaffold(repo, task)
    write(directory / "task.json", task)
    write(
        directory / "architecture.json",
        {
            "decision": "PENDING",
            "task_sha256": digest(canonical(task)),
            "rationale": "",
            "sources": [],
            "alternative": "",
        },
    )
    write(directory / "context-index.json", {"base_sha": prof["base_sha"], "sources": prof["sources"]})
    (directory / "test-scaffold.txt").write_text(scaffold)
    return {
        "status": "PREPARED",
        "task": str(directory / "task.json"),
        "next_action": "Read approved sources, assess architectural fit, record the assessment before coding.",
        "scaffold": str(directory / "test-scaffold.txt"),
    }


def assess(
    repo: Path, task_id: str, decision: str, rationale: str, sources: list[str], alternative: str
) -> dict:
    task = read_task(repo, task_id)
    if len(rationale.strip()) < 30 or not sources:
        raise RampError("Architecture assessment requires a substantive rationale and source references.")
    for reference in sources:
        context(repo, reference)
    if decision != "COMPATIBLE" and not alternative.strip():
        raise RampError("Pushback must include an alternative or the maintainer decision needed.")
    record = {
        "decision": decision,
        "rationale": rationale,
        "sources": sources,
        "alternative": alternative,
        "task_sha256": digest(canonical(task)),
        "kind": "agent_assessment_not_human_approval",
    }
    directory = task_dir(repo, task_id)
    history = (
        load(directory / "architecture-history.json")
        if (directory / "architecture-history.json").exists()
        else []
    )
    history.append(record)
    write(directory / "architecture-history.json", history)
    write(directory / "architecture.json", record)
    return record


def attachment(repo: Path) -> dict:
    path = safe_path(repo, ".ramp-kit/attachment.json")
    return load(path) if path.is_file() else {"files": {}}


def test_scaffold(repo: Path, task: dict) -> str:
    """Generate incomplete method stubs from the validated task, never a solution."""
    groups = {}
    for criterion in task["criteria"]:
        for node in criterion["tests"]:
            path, klass, method = node.split("::")
            groups.setdefault((path, klass), {}).setdefault(method, []).append(criterion["id"])
    lines = [
        "# Merge these stubs into the existing classes; do not duplicate existing methods.",
        "# Implement real assertions before baseline verification. Stubs deliberately fail.",
    ]
    for (path, klass), methods in groups.items():
        try:
            tree = ast.parse(safe_path(repo, path).read_text())
        except (OSError, SyntaxError) as exc:
            raise RampError(f"Cannot inspect mapped test file {path}: {exc}") from exc
        existing = {
            method.name
            for cls in tree.body
            if isinstance(cls, ast.ClassDef) and cls.name == klass
            for method in cls.body
            if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        lines += ["", f"# {path}", f"class {klass}:"]
        for method, criteria in methods.items():
            if method in existing:
                lines += [
                    f"    # EXISTS — mapped as evidence, do not modify: {method}",
                    f"    # Acceptance: {', '.join(criteria)}",
                    "",
                ]
                continue
            lines += [
                f"    def {method}(self):",
                f"        # Acceptance: {', '.join(criteria)}",
                '        raise NotImplementedError("Write the mapped behavioural assertions")',
                "",
            ]
    return "\n".join(lines) + "\n"


def constant_expression(node: ast.AST) -> bool:
    """Recognize literal-only assertion operands without evaluating test code."""
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return all(constant_expression(n) for n in node.elts)
    if isinstance(node, ast.Dict):
        return all(n is not None and constant_expression(n) for n in [*node.keys, *node.values])
    if isinstance(node, (ast.UnaryOp, ast.BinOp, ast.BoolOp, ast.Compare, ast.IfExp)):
        return all(constant_expression(n) for n in ast.iter_child_nodes(node) if isinstance(n, ast.expr))
    return False


def assertion_findings(repo: Path, task: dict) -> list[dict]:
    """Small syntactic safeguard, not a proof of assertion quality or reachability."""
    findings = []
    for node_id in dict.fromkeys(t for c in task["criteria"] for t in c["tests"]):
        path, klass, method = node_id.split("::")
        try:
            tree = ast.parse(safe_path(repo, path).read_text())
        except (OSError, SyntaxError) as exc:
            findings.append({"rule": "TEST-ASSERTIONS", "path": path, "message": str(exc)})
            continue
        classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == klass]
        methods = [
            n
            for c in classes
            for n in c.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == method
        ]
        if len(classes) != 1 or len(methods) != 1:
            findings.append(
                {
                    "rule": "TEST-ASSERTIONS",
                    "path": path,
                    "message": f"Mapped method missing or duplicated: {node_id}",
                }
            )
            continue

        def has_assertion(node):
            if isinstance(node, ast.Assert):
                return not constant_expression(node.test)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                owner = node.func.value
                if isinstance(owner, ast.Name):
                    if owner.id == "self" and node.func.attr.startswith("assert"):
                        # A dynamic failure message must not make assertTrue(True) count.
                        unary = {"assertTrue", "assertFalse", "assertIsNone", "assertIsNotNone"}
                        operands = node.args[:1] if node.func.attr in unary else node.args[:2]
                        operands += [kw.value for kw in node.keywords if kw.arg != "msg"]
                        return bool(operands) and not all(constant_expression(n) for n in operands)
                    if owner.id == "pytest" and node.func.attr == "raises":
                        return any(not constant_expression(n) for n in node.args)
            # Assertions in uncalled nested helpers/classes do not count.
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                return False
            return any(has_assertion(child) for child in ast.iter_child_nodes(node))

        if not any(has_assertion(n) for n in methods[0].body):
            findings.append(
                {
                    "rule": "TEST-ASSERTIONS",
                    "path": path,
                    "line": methods[0].lineno,
                    "message": f"{node_id} has no non-constant supported assertion. Add a behavioural assert, self.assert*, or pytest.raises; literal-only assertions do not count.",
                }
            )
    return findings


def patch_bytes(repo: Path, task: dict) -> bytes:
    # Keep patch identity independent of local Git display preferences and repo size.
    return git(
        repo,
        "-c",
        "core.quotePath=true",
        "diff",
        "--binary",
        "--full-index",
        "--no-color",
        "--no-ext-diff",
        "--no-textconv",
        "--no-renames",
        "--diff-algorithm=myers",
        "--no-indent-heuristic",
        "--unified=3",
        "--src-prefix=a/",
        "--dst-prefix=b/",
        task["base_sha"],
        "--",
        *sorted(task["editable_files"]),
    )


def required_checks(level: str = "full", phase: str = "candidate") -> list[str]:
    if phase == "baseline":
        return ["regression"]
    checks = ["acceptance", "scheduler-tests", "lint", "format"]
    if level == "full":
        checks += [c["id"] for c in profile()["upstream_checks"]] + ["test-strength"]
    return checks


def policy_provenance(repo: Path) -> dict:
    installed = attachment(repo).get("kit_sha256", "UNAVAILABLE")
    return {
        "runner_kit_sha256": kit_hash(),
        "installation_kit_sha256": installed,
        "reference_source": "attachment.json at installation; locally editable, not an independent trust anchor",
        "full_required_checks": required_checks(),
        "integrity_boundary": "Only fork CI enforces policy integrity.",
    }


def scope_findings(repo: Path, task: dict) -> list[dict]:
    managed = attachment(repo)["files"]
    findings = []
    for relative in changed(repo, task["base_sha"]):
        if relative.startswith(".ramp/"):
            continue
        path = safe_path(repo, relative)
        if relative in managed:
            if not path.is_file() or digest(path.read_bytes()) != managed[relative]:
                findings.append({"rule": "SCOPE", "path": relative, "message": "Installed kit file changed."})
        elif relative == ".ramp-kit/attachment.json":
            continue
        elif relative not in task["editable_files"]:
            findings.append(
                {"rule": "SCOPE", "path": relative, "message": "Change outside the task's editable paths."}
            )
        elif not path.is_file():
            findings.append(
                {
                    "rule": "SCOPE",
                    "path": relative,
                    "message": "Deleting the selected source/test is unsupported.",
                }
            )
    return findings


def fingerprint(repo: Path, task: dict) -> str:
    paths = set(changed(repo, task["base_sha"])) | set(profile()["sources"])
    contents = []
    for relative in sorted(paths):
        if relative.startswith(".ramp/"):
            continue
        path = safe_path(repo, relative)
        contents.append((relative, digest(path.read_bytes()) if path.is_file() else "DELETED"))
    review_path = task_dir(repo, task["id"]) / "architecture.json"
    review = load(review_path) if review_path.exists() else {}
    packages = sorted((d.metadata.get("Name", ""), d.version) for d in importlib.metadata.distributions())
    return digest(
        canonical(
            {
                "files": contents,
                "task": task,
                "review": review,
                "kit": kit_hash(),
                "python": sys.version,
                "packages": packages,
                "base": task["base_sha"],
            }
        )
    )


def diagnostic(repo: Path, task: dict) -> list[dict]:
    """One deliberately narrow anti-pattern rule for newly introduced broad exception swallowing."""
    findings = []
    for relative in task["editable_files"]:
        path = safe_path(repo, relative)
        if not path.is_file():
            continue
        text = path.read_text()
        try:
            tree = ast.parse(text)
            original = ast.parse(git(repo, "show", f"{task['base_sha']}:{relative}"))
        except SyntaxError as exc:
            findings.append({"rule": "SYNTAX", "path": relative, "message": str(exc)})
            continue
        previous = [ast.dump(n) for n in ast.walk(original) if isinstance(n, ast.ExceptHandler)]
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            signature = ast.dump(node)
            if signature in previous:
                previous.remove(signature)
                continue
            broad = (
                node.type is None
                or isinstance(node.type, ast.Name)
                and node.type.id in ("Exception", "BaseException")
            )
            if broad and all(isinstance(n, (ast.Pass, ast.Return)) for n in node.body):
                findings.append(
                    {
                        "rule": "NO-SILENT-FALLBACK",
                        "path": relative,
                        "line": node.lineno,
                        "message": "Broad exception swallowed. Validate the known input and raise a clear error.",
                        "source": ".ai/references/code_style.md",
                    }
                )
    return findings


def runtime_env(repo: Path) -> dict:
    env = os.environ.copy()
    env.update(
        {
            "PATH": str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", ""),
            "PYTHONPATH": str(repo / "src"),
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "DIFFUSERS_TEST_DEVICE": "cpu",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    return env


def run_check(repo: Path, directory: Path, name: str, argv: list[str], timeout: int = 180) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    try:
        result = subprocess.run(
            argv, cwd=repo, env=runtime_env(repo), capture_output=True, text=True, timeout=timeout
        )
        output = result.stdout + result.stderr
        code = result.returncode
        status = "PASS" if code == 0 else "FAIL"
    except (OSError, subprocess.TimeoutExpired) as exc:
        output, code, status = str(exc), None, "ERROR"
    log = directory / f"{name}.log"
    log.write_text(output)
    return {
        "id": name,
        "status": status,
        "command": argv,
        "exit_code": code,
        "seconds": round(time.monotonic() - started, 3),
        "log": str(log.relative_to(repo)),
    }


def pytest_check(repo: Path, directory: Path, name: str, nodes: list[str]) -> dict:
    xml = directory / f"{name}.xml"
    if xml.exists():
        xml.unlink()
    result = run_check(
        repo,
        directory,
        name,
        [sys.executable, "-m", "pytest", "-q", "-o", "addopts=", "--junitxml", str(xml), *nodes],
    )
    result["tests"] = []
    result["counts"] = {state: 0 for state in ("PASS", "FAIL", "ERROR", "SKIPPED", "total")}
    if not xml.exists():
        result["status"] = "ERROR"
        return result
    try:
        for node in ET.parse(xml).getroot().iter("testcase"):
            status = "PASS"
            detail = ""
            for tag, value in (("failure", "FAIL"), ("error", "ERROR"), ("skipped", "SKIPPED")):
                child = node.find(tag)
                if child is not None:
                    status = value
                    detail = child.get("message", "") + "\n" + (child.text or "")
                    break
            result["tests"].append(
                {"name": node.get("name"), "class": node.get("classname"), "status": status, "detail": detail}
            )
    except ET.ParseError as exc:
        result["status"] = "ERROR"
        result["error"] = str(exc)
    statuses = [t["status"] for t in result["tests"]]
    if not statuses:
        result["status"] = "ERROR"
    elif "ERROR" in statuses:
        result["status"] = "ERROR"
    elif "FAIL" in statuses:
        result["status"] = "FAIL"
    elif "SKIPPED" in statuses and result["status"] == "PASS":
        result["status"] = "SKIPPED"
    if result.get("exit_code") not in (0, 1):
        result["status"] = "ERROR"
    result["counts"] = {state: statuses.count(state) for state in ("PASS", "FAIL", "ERROR", "SKIPPED")}
    result["counts"]["total"] = len(statuses)
    if result["status"] == "PASS":
        observed = {(t["class"], t["name"]) for t in result["tests"]}
        for node in nodes:
            if "::" not in node:
                continue
            path, klass, test = node.split("::")
            expected = (path.removesuffix(".py").replace("/", ".") + "." + klass, test)
            if expected not in observed:
                result["status"] = "ERROR"
                result["error"] = f"Mapped test did not execute: {node}"
    return result


def expected_regression(check: dict, task: dict) -> bool:
    tests = check.get("tests", [])
    if len(tests) != 1 or tests[0]["status"] != "FAIL" or check.get("exit_code") != 1:
        return False
    detail = tests[0].get("detail", "")
    return detail.startswith(task.get("baseline_error", "IndexError") + ":") and any(
        path in detail for path in profile()["implementation_files"]
    )


def regression_failure(check: dict, task: dict) -> str:
    expected = task.get("baseline_error", "IndexError")
    tests = check.get("tests", [])
    if check.get("status") == "ERROR":
        return "REGRESSION_EXECUTION_ERROR: inspect collection/import/runtime errors in the regression log."
    if len(tests) != 1:
        return f"REGRESSION_NOT_REPRODUCED: observed {len(tests)} tests, expected exactly one."
    observed = tests[0]["status"]
    if observed != "FAIL":
        return f"REGRESSION_NOT_REPRODUCED: observed {observed}, expected {expected} from the original implementation."
    detail = tests[0].get("detail", "")
    exception = detail.split(":", 1)[0].splitlines()[0] if detail else "unknown failure"
    if exception != expected:
        return f"REGRESSION_WRONG_FAILURE: observed {exception}, expected {expected}."
    return f"REGRESSION_WRONG_ORIGIN: {expected} must reach an approved implementation file; inspect the traceback."


def isolated_check(repo: Path, task: dict, logs: Path, name: str, argv: list[str]) -> dict:
    """Keep upstream checks that rewrite generated data outside the working contribution."""
    with tempfile.TemporaryDirectory(prefix="ramp-check-") as tmp:
        work = Path(tmp) / "checkout"
        work.mkdir()
        archive = Path(tmp) / "baseline.tar"
        git(repo, "archive", "--format=tar", f"--output={archive}", task["base_sha"])
        with tarfile.open(archive) as source:
            source.extractall(work, filter="data")
        for relative in task["editable_files"]:
            safe_path(work, relative).write_bytes(safe_path(repo, relative).read_bytes())
        result = run_check(work, work / ".ramp-check", name, argv, timeout=300)
        log = logs / f"{name}.log"
        log.write_text((work / result["log"]).read_text())
        result["log"] = str(log.relative_to(repo))
        result["working_directory"] = "Disposable candidate snapshot (removed after check)"
    return result


def replay_regression(repo: Path, task: dict, logs: Path) -> dict:
    """Restore the pinned implementation in a disposable tracked snapshot; retain current tests."""
    with tempfile.TemporaryDirectory(prefix="ramp-strength-") as tmp:
        work = Path(tmp) / "checkout"
        work.mkdir()
        archive = Path(tmp) / "baseline.tar"
        git(repo, "archive", "--format=tar", f"--output={archive}", task["base_sha"])
        with tarfile.open(archive) as source:
            source.extractall(work, filter="data")
        test_path = profile()["test_file"]
        safe_path(work, test_path).write_bytes(safe_path(repo, test_path).read_bytes())
        result = pytest_check(work, work / ".ramp-replay", "regression", [task["regression_test"]])
        log = logs / "test-strength.log"
        log.write_text((work / result["log"]).read_text())
        if (work / ".ramp-replay/regression.xml").is_file():
            (logs / "test-strength.xml").write_bytes((work / ".ramp-replay/regression.xml").read_bytes())
        result["log"] = str(log.relative_to(repo))
        result["working_directory"] = "Disposable pinned snapshot (removed after check)"
    observed = expected_regression(result, task)
    reason = None if observed else regression_failure(result, task)
    result.update(
        id="test-strength",
        status="PASS" if observed else "ERROR" if result["status"] == "ERROR" else "FAIL",
        expected_failure_observed=observed,
        method="Restore pinned implementation with the candidate regression test in a disposable snapshot.",
        implementation_changed=any(
            safe_path(repo, p).read_bytes() != git(repo, "show", f"{task['base_sha']}:{p}")
            for p in profile()["implementation_files"]
        ),
    )
    if reason:
        result["error"] = reason
    if not result["implementation_changed"]:
        result["status"] = "FAIL"
        result["error"] = "No implementation change to remove; test-strength evidence is incomplete."
    return result


def verify(repo: Path, task_id: str, level: str, phase: str) -> dict:
    task = read_task(repo, task_id)
    directory = task_dir(repo, task_id)
    preflight = doctor(repo)
    if preflight["status"] != "PASS":
        raise RampError("; ".join(preflight["findings"]))
    review = load(directory / "architecture.json") if (directory / "architecture.json").exists() else {}
    findings = scope_findings(repo, task) + diagnostic(repo, task) + assertion_findings(repo, task)
    if review.get("decision") != "COMPATIBLE" or review.get("task_sha256") != digest(canonical(task)):
        findings.append(
            {"rule": "DESIGN", "message": "Current task needs a compatible, cited architecture assessment."}
        )
    before = fingerprint(repo, task)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    logs = directory / "runs" / run_id
    checks = []
    if not findings:
        if phase == "baseline":
            for source in profile()["implementation_files"]:
                if safe_path(repo, source).read_bytes() != git(repo, "show", f"{task['base_sha']}:{source}"):
                    raise RampError(
                        "Baseline evidence requires unchanged implementation; keep only the new tests."
                    )
            checks.append(pytest_check(repo, logs, "regression", [task["regression_test"]]))
        else:
            acceptance = list(dict.fromkeys(t for c in task["criteria"] for t in c["tests"]))
            checks.append(pytest_check(repo, logs, "acceptance", acceptance))
            checks.append(
                pytest_check(
                    repo, logs, "scheduler-tests", profile().get("test_modules", [profile()["test_file"]])
                )
            )
            checks.append(
                run_check(
                    repo, logs, "lint", [sys.executable, "-m", "ruff", "check", *task["editable_files"]]
                )
            )
            checks.append(
                run_check(
                    repo,
                    logs,
                    "format",
                    [sys.executable, "-m", "ruff", "format", "--check", *task["editable_files"]],
                )
            )
            if level == "full":
                for check in profile()["upstream_checks"]:
                    argv = [sys.executable if a == "{python}" else a for a in check["command"]]
                    if check.get("isolated"):
                        checks.append(isolated_check(repo, task, logs, check["id"], argv))
                    else:
                        checks.append(run_check(repo, logs, check["id"], argv, timeout=300))
                checks.append(replay_regression(repo, task, logs))
    after = fingerprint(repo, task)
    if after != before:
        findings.append(
            {"rule": "STALE", "message": "Inputs changed during verification; rerun on a stable patch."}
        )
    result = {
        "schema_version": 1,
        "task_id": task_id,
        "phase": phase,
        "level": level,
        "run_id": run_id,
        "fingerprint": before,
        "base_sha": task["base_sha"],
        "kit_sha256": kit_hash(),
        "patch_sha256": digest(patch_bytes(repo, task)),
        "policy": policy_provenance(repo),
        "required_checks": required_checks(level, phase),
        "runtime": preflight["runtime"],
        "findings": findings,
        "checks": checks,
        "status": "FAIL" if findings or any(c["status"] == "FAIL" for c in checks) else "PASS",
        "remote_ci": "NOT_RUN",
        "human_review": "NOT_RUN",
        "deployment": "NOT_RUN",
    }
    result["counts"] = {
        state: sum(c["status"] == state for c in checks)
        for state in ("PASS", "FAIL", "ERROR", "SKIPPED", "NOT_RUN")
    }
    result["counts"]["checks"] = len(checks)
    if any(c["status"] == "ERROR" for c in checks):
        result["status"] = "ERROR"
    elif any(c["status"] in ("SKIPPED", "NOT_RUN") for c in checks) and result["status"] == "PASS":
        result["status"] = "INCOMPLETE"
    if phase == "baseline":
        intended = bool(not findings and checks and expected_regression(checks[0], task))
        result["intended_failure_observed"] = intended
        result["status"] = (
            "EXPECTED_FAILURE"
            if intended
            else ("ERROR" if any(c["status"] == "ERROR" for c in checks) else "FAIL")
        )
        result["origin"] = "Pre-implementation run on the unchanged implementation"
        if not intended:
            result["reason"] = (
                "; ".join(f["message"] for f in findings)
                if findings
                else regression_failure(checks[0], task)
                if checks
                else "Regression did not execute."
            )
        result["test_sha256"] = digest(safe_path(repo, profile()["test_file"]).read_bytes())
        result["task_sha256"] = digest(canonical(task))
    elif level == "full":
        strength = next((c for c in checks if c["id"] == "test-strength"), None)
        if strength and strength["status"] == "PASS":
            # CI reruns this evidence using its own environment; it never trusts a submitted green result.
            write(
                directory / "replay.json",
                {
                    "status": "EXPECTED_FAILURE",
                    "run_id": run_id,
                    "intended_failure_observed": True,
                    "origin": "Disposable original-implementation replay during full verification",
                    "base_sha": task["base_sha"],
                    "kit_sha256": kit_hash(),
                    "test_sha256": digest(safe_path(repo, profile()["test_file"]).read_bytes()),
                    "task_sha256": digest(canonical(task)),
                    "checks": [strength],
                },
            )
    result["next_action"] = {
        "PASS": "Generate the shared review report.",
        "EXPECTED_FAILURE": "Implement the scoped fix, then run candidate verification.",
        "ERROR": "Resolve the execution/configuration error shown in the checks, then rerun.",
        "INCOMPLETE": "Resolve required skipped or unavailable checks, then rerun.",
    }.get(result["status"], "Resolve findings and failed checks; rerun verification.")
    if result.get("reason"):
        result["next_action"] = result["reason"]
    elif findings:
        result["next_action"] = "; ".join(f["message"] for f in findings)
    write(logs / "result.json", result)
    write(directory / f"{phase}.json", result)
    return result


def readiness(repo: Path, task: dict) -> dict:
    directory = task_dir(repo, task["id"])
    candidate = load(directory / "candidate.json") if (directory / "candidate.json").exists() else None
    baseline = load(directory / "baseline.json") if (directory / "baseline.json").exists() else None
    replay = load(directory / "replay.json") if (directory / "replay.json").exists() else None
    if candidate is None:
        return {
            "status": "NOT_RUN",
            "reason": "Run verification.",
            "candidate": None,
            "baseline": baseline,
            "replay": replay,
        }
    if candidate["fingerprint"] != fingerprint(repo, task):
        status, reason = "STALE", "Code, policy, requirements or assessment changed; rerun verification."
    elif candidate["status"] != "PASS":
        status, reason = candidate["status"], "Resolve failed, skipped or unavailable checks."
    elif not any(
        e
        and e.get("status") == "EXPECTED_FAILURE"
        and e.get("task_sha256") == digest(canonical(task))
        and e.get("test_sha256") == digest(safe_path(repo, profile()["test_file"]).read_bytes())
        for e in (baseline, replay)
    ):
        status, reason = (
            "INCOMPLETE",
            "Missing current regression evidence against the original implementation.",
        )
    elif candidate["level"] != "full":
        status, reason = "FAST_CHECKS_PASSED", "Run full verification before calling the PR clean."
    elif not any(c["id"] == "test-strength" and c["status"] == "PASS" for c in candidate.get("checks", [])):
        status, reason = "INCOMPLETE", "Full verification must include the disposable fix-removal replay."
    elif set(required_checks()) != {c["id"] for c in candidate.get("checks", [])}:
        status, reason = "INCOMPLETE", "Executed checks do not match the required profile checks."
    else:
        status, reason = (
            "READY_FOR_HUMAN_REVIEW",
            "Local required checks passed. Remote CI and human review are separate.",
        )
    return {
        "status": status,
        "reason": reason,
        "candidate": candidate,
        "baseline": baseline,
        "replay": replay,
    }
