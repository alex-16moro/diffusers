# /scaffold — first contribution on the REAL library checkout

Usage: `/scaffold <component> <Name>`

This workspace is `huggingface/diffusers` (fork). Overlay kit is `ramp-kit/`
(cloned from alex-16moro/diffuser_agent). Do not overwrite `.ai/` or root `AGENTS.md`.

`$1` = component (`scheduler`). `$2` = PascalCase name without suffix (`HeunLite`
→ `HeunLiteScheduler`, `scheduling_heun_lite.py`).

Done is only what `ramp-kit/conventions/rules.yaml` checks. Copy the templates.
Do not start from library scheduler source and do not search docs for this PR.

## 0. Ground in the registry

Read `ramp-kit/conventions/rules.yaml`. Blocking ids for this contribution:
SCHED001, SCHED002, SCHED003, REPRO001, DEVICE001, DEPR001, MUT001, TEST001,
TEST002.

The overlay templates already satisfy them. Stay inside `.cursorignore`. Do not
read or copy `ramp-kit/examples/candidate_scheduler/`.

## 1. Paths (library layout, not the kit stand-in)

Convert `$2` to snake_case (`HeunLite` → `heun_lite`). The class is `$2Scheduler`.

- Implementation: `src/diffusers/schedulers/scheduling_<snake>.py`
- Test: `tests/schedulers/test_scheduling_<snake>.py`

If `scheduling_euler_lite.py` already exists, do not overwrite it — use a new `$2`.

## 2. Copy from the overlay templates

- `ramp-kit/templates/scheduler/scheduling_TEMPLATE.py` → implementation
- Rename `TemplateScheduler` → `$2Scheduler`
- Keep `TODO(engineer)` in `step()`. Do not replace the placeholder.

## 3. Copy the contract test (TEST001 / TEST002)

Copy `ramp-kit/tests/_templates/scheduler_test.py`. Set `TARGET` and `CLASS`
only. Do not add files or tests the template does not already contain.

## 4. Gate (file-scoped — do not `--all` this library)

```bash
python3 ramp-kit/tools/convention_check.py src/diffusers/schedulers/scheduling_<snake>.py
python3 -m unittest tests.schedulers.test_scheduling_<snake> -v
```

Fix every **blocking** finding. Stop at 0 blocking. Behavioral skips without
torch are success — do not edit `step()` to make them pass.

Do not open a PR against huggingface/diffusers — PR this fork, **draft, base
`main`**, those two files only.
