# First contribution: scheduler input validation

Supported profile: DDPM `set_timesteps` at the exact revision in `profiles/diffusers.json`.
The kit prepares context and a structural test scaffold. It does not supply a finished source patch to the development agent.

## The user journey

Example request: “Make passing an empty timestep list produce a clear error. Could we just replace it with `[999]`?”

First review the proposal. Read `.ai/references/code_style.md`, `docs/source/en/conceptual/philosophy.md`, and `DDPMScheduler.set_timesteps`.
Explain that silently choosing a list changes the caller's requested behaviour, while the library guidance favours a clear error. Propose a small input guard in the existing method. Cite the actual evidence. If the user insists on changing the behavioural contract, record `NEEDS_MAINTAINER` and explain the decision needed.

## Commands the agent runs

All commands run from the Diffusers checkout with `.ramp-venv` active. Read `.ai/AGENTS.md`; upstream coding/review instructions still apply. Setup is already supplied by the kit: do not create another environment or install/update skills. Inspect local skills only; registry listing may require network access.

Before `prepare`, the agent writes `.ramp/specs/empty-timesteps.json` from the actual request and inspected code. Use `.ramp-kit/examples/empty-timesteps.json` only as a schema guide; do not blindly load its prewritten request or criteria. Validate request, scope, regression exception, and criterion-to-test mappings. The engineer does not need to author JSON. Keep draft specs outside `.ramp/<task>/`, which `prepare` creates.

```bash
python .ramp-kit/run.py --repo . doctor
python .ramp-kit/run.py --repo . context .ai/references/code_style.md
python .ramp-kit/run.py --repo . context src/diffusers/schedulers/scheduling_ddpm.py --symbol DDPMScheduler.set_timesteps
python .ramp-kit/run.py --repo . context tests/schedulers/test_scheduler_ddpm.py
python .ramp-kit/run.py --repo . prepare --spec .ramp/specs/empty-timesteps.json
```

For a different supported validation task, prepare a separate spec modeled on this example: real request, compatible scope and actual test IDs. Do not reuse the empty-list acceptance criteria for unrelated requests.

Record architectural assessment with `assess empty-timesteps --decision REVISE --rationale "..." --source .ai/references/code_style.md --alternative "..."`.
When the plan fits, record `COMPATIBLE` with its evidence. The history retains earlier pushback. It is agent judgement, not human approval.

The scaffold appears under `.ramp/empty-timesteps/test-scaffold.txt`. It parses the mapped test files and marks existing methods `EXISTS — mapped as evidence, do not modify`. Only missing mapped methods become stubs; merge these into the existing class and preserve the marked upstream methods. Replace every stub with meaningful assertions. Raise-only stubs and literal-only assertions such as `self.assertTrue(True)` do not satisfy the assertion check. The task record maps acceptance criteria to those methods. Keep the test file unchanged between the baseline and candidate runs.

```bash
python .ramp-kit/run.py --repo . verify empty-timesteps --phase baseline
```

Confirm that the new regression fails with the observed `IndexError`, not an import/collection failure. Then implement the minimal validation change. Preserve valid lists, single-element lists, existing count-based behaviour and mutual-exclusion errors.

The pinned repository copies this method into `scheduling_ddpm_parallel.py`. Inspect its `# Copied from` marker. Run `python utils/check_copies.py --fix_and_overwrite` to propagate the authoritative source change, then inspect the diff. Both implementations are in this recipe's scope; unrelated changes are not. Verification runs both scheduler test modules. This is a source-derived dependency, not a reason to hand-maintain two implementations.

```bash
python .ramp-kit/run.py --repo . verify empty-timesteps
python .ramp-kit/run.py --repo . verify empty-timesteps --level full
python .ramp-kit/run.py --repo . report empty-timesteps
```

Fast verification gives prompt feedback. Full verification invokes upstream checks and reruns the current regression against the original implementation in a disposable snapshot. That replay must fail for the intended reason; its PASS means the removed fix was detected. Failures stay failures even if pre-existing; run the same command on the clean reference to classify them. Do not repair unrelated upstream files.

If tests change after baseline evidence, replay the same new tests against a disposable copy of the original implementation. Do not reset the user's checkout. The pre-implementation record remains historical if tests change; the separate replay record proves sensitivity of the current tests. Full verification never overwrites the pre-implementation baseline.

## Human handoff

Open `.ramp/empty-timesteps/review.html` or `review.md`; inspect the patch and `PR-DRAFT.md`. The PM reviews criteria; QA reviews mapped tests and the before/after evidence; DevOps reviews CI wiring and remaining release gates. Review the generated inventory of changed string literals (including errors), docstrings and comments, the complete patch, proposed commit message and exact PR title/body. Publication and merge remain human decisions; no approval is inferred.

## Explicit limits

This is one complete contribution path. It is not a universal Diffusers generator, semantic architecture validator, hosted approval product or security sandbox. The whole-agent boundary remains a deployment responsibility.
