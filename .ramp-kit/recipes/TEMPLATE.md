# Recipe proposal template

This is not a recipe. It gives a team proposing the next contribution type the sections every supported recipe must state (see the recipe contract in `README.md`). A completed proposal still needs the platform owner to review and extend the profile, runner and verification before any task may use it.

## Ownership

- Proposing team and recipe owner:
- Platform-owner reviewer:
- Time-to-value target: hours from the first prepared task to its first merge, as reported by `metrics` under `by_recipe`.

## Contribution type

One sentence naming the kind of change and the public API that owns it.

## Eligibility and exclusions

- Eligible requests:
- Out of scope, and what to propose instead:

## Pinned source and canonical examples

- Files and symbols the agent may read through `context`, with the profile revision:
- Existing code and tests that show the expected pattern:

## Related-file obligations

Marked copies, shared tests, exports and documentation that must change with the primary file.

## Architecture review questions

| Question | Source to inspect |
|---|---|
| | |

## Task and scaffold inputs

- Editable files:
- Test file and class the regression belongs to:
- What makes a valid baseline reproduction (exception and traceback origin):

## Verification and its limits

- Fast and full checks, including upstream checks:
- What these checks do not cover:

## Handoff evidence

What PM, QA and DevOps each review in the generated report.

## Conditions requiring a broader plan

Signals that a request has outgrown this recipe and needs a maintainer decision.
