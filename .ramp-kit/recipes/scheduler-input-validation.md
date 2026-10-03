# First contribution: scheduler input validation

Supported profile: input validation in DDPM `set_timesteps` at the exact revision in `profiles/diffusers.json`, including its `# Copied from` copy in the parallel scheduler.
The kit prepares context and a structural test scaffold. It does not supply a finished source patch to the development agent.

## The user journey

The engineer describes an outcome and may suggest how to achieve it. The suggestion is a hypothesis to evaluate, not an instruction.

First review the proposal against the library's own guidance. Read `.ai/references/code_style.md`, `docs/source/en/conceptual/philosophy.md` and the method you would change, then decide whether the suggested approach fits. Cite the evidence you actually read. If it does not fit, explain the concrete consequence and propose an alternative before editing code. If the user insists on changing a behavioural contract, record `NEEDS_MAINTAINER` and explain the decision needed.

## Naming the task

Choose a short task ID for the request, for example `my-task`, using lowercase letters, digits and hyphens. The commands below write it as `<task-id>`; substitute your ID everywhere.

- Your spec is `.ramp/specs/<task-id>.json`, and its `"id"` field is `<task-id>`.
- `prepare` creates the task record under `.ramp/<task-id>/`.
- Every later command takes `<task-id>` as its task argument.

## Commands the agent runs

All commands run from the Diffusers checkout with `.ramp-venv`, the environment the kit prepared. Read `.ai/AGENTS.md`; upstream coding and review instructions still apply. Setup is already supplied by the kit: do not create another environment or install or update skills. Inspect local skills only; registry listing may require network access.

Before `prepare`, write `.ramp/specs/<task-id>.json` from the actual request and the code you inspected. Use `.ramp-kit/examples/empty-timesteps.json` only as a schema guide for a different, earlier task: do not copy its request, criteria, test names or expected error. Keep draft specs outside `.ramp/<task-id>/`, which `prepare` creates.

Set these spec fields from what you observe in this checkout:
- `regression_test`: the one test that reproduces the reported problem against the unchanged implementation.
- `baseline_error`: the exception class name, exactly as it begins the failure line, that the regression test raises when you run it against the unchanged implementation. Always set it explicitly. Baseline verification accepts the reproduction only if the failure starts with this exception **and** its traceback passes through an implementation file. Behaviour that is wrong but raises nothing cannot be the designated regression; cover it with other mapped tests.
- `criteria`: each acceptance criterion mapped to the test IDs that demonstrate it.

```bash
.ramp-venv/bin/python .ramp-kit/run.py --repo . doctor
.ramp-venv/bin/python .ramp-kit/run.py --repo . context .ai/references/code_style.md
.ramp-venv/bin/python .ramp-kit/run.py --repo . context src/diffusers/schedulers/scheduling_ddpm.py --symbol DDPMScheduler.set_timesteps
.ramp-venv/bin/python .ramp-kit/run.py --repo . context tests/schedulers/test_scheduler_ddpm.py
.ramp-venv/bin/python .ramp-kit/run.py --repo . prepare --spec .ramp/specs/<task-id>.json
```

Record your architectural assessment with `assess <task-id> --decision <COMPATIBLE|REVISE|NEEDS_MAINTAINER> --rationale "..." --source <approved-path> [--alternative "..."]`. Pushback (`REVISE` or `NEEDS_MAINTAINER`) needs an alternative or the decision required. When the plan fits, record `COMPATIBLE` with its evidence; the history keeps earlier pushback. The assessment is agent judgement, not human approval.

The scaffold appears under `.ramp/<task-id>/test-scaffold.txt`. It parses the mapped test files and marks existing methods `EXISTS — mapped as evidence, do not modify`. Only missing mapped methods become stubs; merge these into the existing class and preserve the marked upstream methods. Replace every stub with meaningful assertions. Raise-only stubs and literal-only assertions such as `self.assertTrue(True)` do not satisfy the assertion check. The task record maps acceptance criteria to those methods. Keep the test file unchanged between the baseline and candidate runs.

```bash
.ramp-venv/bin/python .ramp-kit/run.py --repo . verify <task-id> --phase baseline
```

Confirm that the regression fails with your spec's `baseline_error`, not with an import or collection failure. Then implement the minimal validation change. Preserve every input the method already accepts correctly and every existing error and its precedence.

The pinned repository copies this method into `scheduling_ddpm_parallel.py`. Inspect its `# Copied from` marker. Propagate the authoritative change with the upstream copy tool, run with the prepared environment active so the tool finds the environment's formatter:

```bash
PATH="$PWD/.ramp-venv/bin:$PATH" .ramp-venv/bin/python utils/check_copies.py --fix_and_overwrite
```

`source .ramp-venv/bin/activate` followed by `python utils/check_copies.py --fix_and_overwrite` is equivalent when your shell session persists. Then inspect the diff. Both implementations are in this recipe's scope; unrelated changes are not. Verification runs both scheduler test modules. This is a source-derived dependency, not a reason to hand-maintain two implementations.

```bash
.ramp-venv/bin/python .ramp-kit/run.py --repo . verify <task-id>
.ramp-venv/bin/python .ramp-kit/run.py --repo . verify <task-id> --level full
.ramp-venv/bin/python .ramp-kit/run.py --repo . report <task-id>
```

Fast verification gives prompt feedback. Full verification invokes upstream checks and reruns the current regression against the original implementation in a disposable snapshot. That replay must fail for the intended reason; its PASS means the removed fix was detected. Failures stay failures even if pre-existing; run the same command on the clean reference to classify them. Do not repair unrelated upstream files.

If tests change after baseline evidence, replay the same new tests against a disposable copy of the original implementation. Do not reset the user's checkout. The pre-implementation record remains historical if tests change; the separate replay record proves sensitivity of the current tests. Full verification never overwrites the pre-implementation baseline.

## Human handoff

Open `.ramp/<task-id>/review.html` or `review.md`; inspect the patch and `PR-DRAFT.md`. The PM reviews criteria; QA reviews mapped tests and the before/after evidence; DevOps reviews CI wiring and remaining release gates. Review the generated inventory of changed string literals (including errors), docstrings and comments, the complete patch, proposed commit message and exact PR title/body. Publication and merge remain human decisions; no approval is inferred.

## Publishing, after approval only

Publish only after a human approves the exact wording, and only to the target named by the installation (see the entry rule). The commit must contain:
- the source and test changes, and
- the task record that fork CI re-verifies: `.ramp/<task-id>/task.json`, `.ramp/<task-id>/architecture.json` and `.ramp/<task-id>/architecture-history.json`.

Fork CI rejects a PR without the task record (`No task record committed`). Do not commit run logs, reports, the scaffold or the draft spec; CI regenerates its own evidence.

## Explicit limits

This is one complete contribution path. It is not a universal Diffusers generator, semantic architecture validator, hosted approval product or security sandbox. The whole-agent boundary remains a deployment responsibility.
