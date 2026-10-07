# Contribution recipes

Start with the engineer's requested outcome. Select a recipe by contribution type and verify that the installed profile covers the owning API, related files and required checks before editing.

A recipe is a reusable route to a bounded contribution. A task is one concrete request with its own acceptance criteria, regression and evidence. The empty-timesteps example demonstrates a recipe; it does not define every task that recipe can support.

## Available coverage

| Contribution type | Recipe | Current executable coverage |
|---|---|---|
| Input-validation improvement in an existing scheduler | [scheduler-input-validation](scheduler-input-validation.md) | Pinned DDPM `set_timesteps`, its marked parallel copy, and tests allowed by `profiles/diffusers.json`. Baseline reproduction must satisfy the runner's exception/traceback contract. |

Documentation corrections, other bug fixes, new schedulers and cross-component features do not yet have supported recipes. Do not route them through this recipe just to obtain a passing report.

## Selection and scope

1. Identify the desired behaviour and the API that owns it. Separate the engineer's proposed implementation from that outcome.
2. Compare the request with the recipe's eligibility, profile paths, baseline requirements and exclusions. Report the selected recipe and the reason it fits in plain language. Start with its curated references; broader exploration must have a concrete reason.
3. Check related implementations, marked copies, shared tests, public exports and documentation implications. Bounded does not mean a single file or no dependencies. The DDPM parallel copy is already inside this recipe's boundary.
4. Review architectural fit using the current pinned source and applicable upstream guidance. Cite evidence for pushback and propose a compatible alternative. General architectural preferences are not automatically library requirements.
5. If the task exceeds coverage, explain what changed and propose a smaller contribution or a reviewed recipe/profile extension. Stop unsupported implementation work. Do not widen the allowlist, weaken checks or edit kit policy from the contribution session.

The engineer describes the problem in normal language. The agent selects the recipe, authors the task record and runs its commands. Do not ask the engineer to fill out JSON or select test commands.

## Recipe contract

Every supported recipe should state: contribution type; eligibility and exclusions; pinned source and canonical examples; related-file obligations; architecture review questions; task/scaffold inputs; verification and its limits; handoff evidence; and conditions requiring a broader plan.

Adding a Markdown recipe alone does not add executable support. The platform owner must review the profile, runner assumptions, installation and verification for the new contribution type. Existing upstream instructions remain authoritative for repository conventions.
