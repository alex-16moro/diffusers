# /scaffold — first contribution on the REAL library checkout

Usage: `/scaffold <component> <Name>`

This workspace is `huggingface/diffusers` (fork). Overlay kit is `ramp-kit/`
(cloned from alex-16moro/diffuser_agent).

Root `AGENTS.md` and `.ai/` are Hugging Face's agent guide. **Read them. Do not
overwrite them.** They are how the library itself wants code to look (`make
style`, `make quality`, `# Copied from`, self-review). This overlay adds the
first-contribution recipe and a customer file-scoped gate. It does not replace
the library guide.

Do not disable or guard inherited GitHub workflows.

`$1` = component (`scheduler`). `$2` = PascalCase name without suffix (`PNDMLite`
→ `PNDMLiteScheduler`, `scheduling_pndm_lite.py`). If `scheduling_<snake>.py`
already exists, pick a new unused `$2`.

Copy the overlay templates. Do not start from library scheduler source. Keep
`TODO(engineer)` in `step()`.

## 0. Ground in the registry **and** the library guide

Read `ramp-kit/conventions/rules.yaml`. Blocking ids for this contribution:
SCHED001, SCHED002, SCHED003, REPRO001, DEVICE001, DEPR001, MUT001, TEST001,
TEST002.

Read root `AGENTS.md` and `.ai/` (library guide / review-rules / skills). Do
not overwrite them. Also read the reference source those files name. Optional
keyword search of this checkout's docs:

```bash
python3 ramp-kit/tools/docs_mcp_server.py --query "set_timesteps"
```

That CLI is a fallback, not a deliverable. Default `.cursor/mcp.json` has no
servers.

The templates already satisfy the overlay registry. Library CI (`make style` /
`make quality` / copies / dummies) is also required before the PR.

Stay inside `.cursorignore`. Do not read or copy
`ramp-kit/examples/candidate_scheduler/`.

## 1. Paths (library layout, not the kit stand-in)

Convert `$2` to snake_case (`PNDMLite` → `pndm_lite`). The class is `$2Scheduler`.

- Implementation: `src/diffusers/schedulers/scheduling_<snake>.py`
- Test: `tests/schedulers/test_scheduling_<snake>.py`

Do not overwrite `scheduling_euler_lite.py` or `scheduling_heun_lite.py`.

## 2. Copy from the overlay templates — replace every placeholder

- `ramp-kit/templates/scheduler/scheduling_TEMPLATE.py` → implementation
- Rename `TemplateScheduler` → `$2Scheduler`
- Keep `TODO(engineer)` in `step()`. Do not replace that placeholder.
- After the copy, the new files must not contain `TEMPLATE —`, `CHANGE_ME`,
  `ChangeMeScheduler`, or `TemplateScheduler`.
- Add a `# Copied from` marker only when a block is actually copied.

## 3. Copy the contract test (TEST001 / TEST002)

Copy `ramp-kit/tests/_templates/scheduler_test.py`. Set `TARGET` and `CLASS`.
Replace every other template token so the test names `$2Scheduler`.

## 4. Register the scheduler (library public API)

Alphabetically insert `$2Scheduler` in:

- `src/diffusers/schedulers/__init__.py` — `_import_structure["scheduling_<snake>"]`
  and the matching TYPE_CHECKING import
- `src/diffusers/__init__.py` — the torch schedulers lazy-import list and the
  TYPE_CHECKING import from `.schedulers`

Then invoke (do not hand-write dummy classes):

```bash
python utils/check_dummies.py --fix_and_overwrite
```

## 5. File-scoped convention gate (never `--all`)

```bash
python3 ramp-kit/tools/convention_check.py src/diffusers/schedulers/scheduling_<snake>.py
python3 -m unittest tests.schedulers.test_scheduling_<snake> -v
```

Fix every **blocking** finding. Stop at 0 blocking. Do not edit `step()` math.

## 6. Library CI — invoke until green, then open the PR

These are the library's own checks from `AGENTS.md`. Iterate until all exit 0.
Do not reimplement them:

```bash
make style
make quality
python utils/check_copies.py && python utils/check_dummies.py && python utils/check_repo.py
python3 -m unittest tests.schedulers.test_scheduling_<snake> -v
```

Only then open a **draft** PR on this fork, **base `main`**. Never PR
huggingface/diffusers. Title prefix: `[fork demo — not for upstream]`.
