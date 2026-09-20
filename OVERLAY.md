# Ramp Kit overlay (customer convention-as-code)

This checkout is a **fork of huggingface/diffusers**. The overlay lives in a
separate repo: [alex-16moro/diffuser_agent](https://github.com/alex-16moro/diffuser_agent).

Cloud Agent install clones it to `ramp-kit/` (gitignored). Do not edit
upstream `AGENTS.md` / `.ai/` — those stay Hugging Face's.

PRs from this overlay are **fork-demo only, not for upstream**. Keep them draft
and titled `[fork demo — not for upstream]`. Overlay clearance is the customer
gate (`ramp-kit/tools/convention_check.py` on the new file). Upstream GitHub
Actions may go red; that is expected — we do not claim Hugging Face's CI.

## Grounding (default path — no MCP)

The first contribution is what `ramp-kit/conventions/rules.yaml` checks:

1. Copy `ramp-kit/templates/scheduler/scheduling_TEMPLATE.py` and
   `ramp-kit/tests/_templates/scheduler_test.py`.
2. Run the file-scoped gate on the new scheduler file. Never `--all`.

Docs search and reading `scheduling_euler_discrete.py` / `scheduling_ddpm.py`
are how the *kit* verified the YAML. They are not part of the first PR.

`.cursor/mcp.json` is **empty by default** so Cloud launches do not hit Hub
OAuth or stdio cwd failures. Opt-in servers: `.cursor/mcp.optional.json`.

## Demo (Cloud Agent)

1. On the **kit** first: catch-early on `examples/candidate_scheduler`, then
   `make demo-maintain` if you show maintainability.
2. Then launch on **this fork** (`alex-16moro/diffusers`), branch `main`.
3. Scaffold writes `src/diffusers/schedulers/scheduling_<name>.py` here
   (HeunLite if EulerLite already exists). Gate:
   `python3 ramp-kit/tools/convention_check.py <that file>` (never `--all`).
4. Open the PR **on this fork**, not on huggingface/diffusers, **draft, base
   `main`**, those two files only.

Catch-early fixture: `ramp-kit/examples/candidate_scheduler` — do not copy it.

## Overlay CI (file-scoped)

Attach copies `.github/workflows/ramp-kit-overlay.yml`. It runs
`convention_check` on **changed** `scheduling_*.py` / `test_scheduling_*.py`
only. It does **not** run `--all`. It does **not** replace inherited
Hugging Face workflows.

GitHub runs workflows that already exist on the PR **base** (usually
`main`). Land this file on `main` before you expect a check-run. The kit
workflow `convention-gate.yml` stays in the kit repo.
