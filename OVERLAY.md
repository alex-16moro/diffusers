# Ramp Kit overlay (customer convention-as-code)

This checkout is a **fork of huggingface/diffusers**. The overlay lives in a
separate repo: [alex-16moro/diffuser_agent](https://github.com/alex-16moro/diffuser_agent).

Cloud Agent install clones it to `ramp-kit/` (gitignored).

Root `AGENTS.md` and `.ai/` stay Hugging Face's agent guide. Do not overwrite
them. A new engineer's agent should follow that guide **and** this overlay so
generated code is library-CI aligned by default (`make style`, `make quality`,
copies/dummies) plus the customer file-scoped gate.

PRs from this overlay are **fork-demo only, not for upstream**. Keep them draft
and titled `[fork demo — not for upstream]`. Do not disable inherited GitHub
workflows. Jobs that need Hugging Face's private runners or size labels may
still be red on this personal fork; that is repo-hosting, not a reason to skip
`make quality`.

## Grounding (default path — no MCP)

The first contribution:

1. Copy `ramp-kit/templates/scheduler/scheduling_TEMPLATE.py` and
   `ramp-kit/tests/_templates/scheduler_test.py`. Replace every template token.
   Keep `TODO(engineer)` in `step()`.
2. Register the class in `schedulers/__init__.py`, `diffusers/__init__.py`, and
   dummy objects (`python utils/check_dummies.py --fix_and_overwrite`).
3. File-scoped overlay gate on the new file. Never `--all`.
4. Invoke the library's own tooling until exit 0: `make style`, `make quality`,
   `python utils/check_copies.py && python utils/check_dummies.py && python utils/check_repo.py`.

Do not copy `ramp-kit/examples/candidate_scheduler/`.

`.cursor/mcp.json` ships **stdio `diffusers-docs` only** (`python3 -u
.cursor/mcp-diffusers-docs.py`). Do not enable Hub HTTP MCP (OAuth). Cloud
dropdown: `diffusers-docs-mcp` (PATH shim from `install-docs-mcp.sh`) or
`python3 -u .cursor/mcp-diffusers-docs.py`. Cloud `mcpServerAllowlist` must
permit **both** `python3` (what `.cursor/mcp.json` spawns) and
`diffusers-docs-mcp`. The launcher finds `ramp-kit/tools/docs_mcp_server.py`
from `/agent` as well as the repo root. `start` copies the relative launcher
into `/agent/.cursor/` so that python3 spawn works.

Hub HTTP and extra servers stay in `.cursor/mcp.optional.json`.

## Demo (Cloud Agent)

1. On the **kit** first: catch-early on `examples/candidate_scheduler`, then
   `make demo-maintain` if you show maintainability.
2. Then launch on **this fork** (`alex-16moro/diffusers`), branch `main`.
3. `/scaffold scheduler <unused Name>`. Follow `.cursor/commands/scaffold.md`
   (copied from the overlay). Register + library CI until green. Never `--all`.
4. Open the PR **on this fork**, not on huggingface/diffusers, **draft, base
   `main`**, only after those library gates pass.

Catch-early fixture: `ramp-kit/examples/candidate_scheduler` — do not copy it.

## Overlay CI (file-scoped)

Attach copies `.github/workflows/ramp-kit-overlay.yml`. It runs
`convention_check` on **changed** `scheduling_*.py` / `test_scheduling_*.py`
only. It does **not** run `--all`. It does **not** replace inherited
Hugging Face workflows.

GitHub runs workflows that already exist on the PR **base** (usually
`main`). Land this file on `main` before you expect a check-run. The kit
workflow `convention-gate.yml` stays in the kit repo.
