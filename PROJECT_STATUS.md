# Project Status and Handoff

> This is the only live resume point. Git supplies branch, HEAD, and working-tree details.
> Completed milestones are summarized in [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md).

## Current Task
- **Task:** P7-14f — staged Tier A authoring and anti-overfitting evaluation.
- **Current work:** complete fixed-case staged execution and its one-task operator command are
  implemented; an authorized Luna canary completed case 01.
- **Product state:** one staged live artifact is preparation-ready. The Tier A quality gate remains
  red because cases 02/03 and the blinded human evidence matrix are incomplete.
- **Schema head:** `0008_workbench_defaults`; no migration is involved.
- **Retention gate:** **not crossed**. Active V1 contracts and disposable alpha data evolve in place.

## Completed Behavior
- The packaged frozen manifest is shared by runtime operators and evaluator tests rather than loaded
  from a test-only path.
- The fixed-case planner now derives trusted policies for puzzle, exploration, feature interaction,
  trap, objective, and room narrative from the exact current parent and manifest case.
- Grounded cases select only the exact authorized continuity fact IDs. Objective context receives the
  bounded accepted mechanic set; narrative receives exactly the planner-selected room set.
- All six task profiles must retain one provider/model/adapter/effort assignment. Every task still
  stores its complete policy/profile privately with body-free replay pins.
- `dm dungeon fixed-case` requires case, artifact, current parent, provider, model, and effort; it
  executes exactly one next task, supports exact failed-run resumption, and never approves or writes
  canon.

## Live Evidence
- Explicit canary authorization was used for four new Luna-fast calls over case 01: feature, trap,
  objective, and room narrative. All succeeded on the first submission with measured usage and no
  repair.
- Artifact `35ec4e9b-cbc5-416b-9ff7-3fade7865044` is complete and preparation-ready at version
  `76a48d8a-1f9c-41c3-9533-890fd21419cd`; it remains a draft.
- Final deterministic validation passed all seven checks with zero diagnostics, including exact
  continuity/source lineage, required content, cross-task references, and player secrecy.
- The earlier case-01 puzzle/exploration remain accepted but predate the exact wrapper. The frozen
  exploration overage remains the only qualifying overage, so its repeat gate is **1 of 2**.
- No retry, debug capture, budget/effort change, Terra comparison, approval, or canonical write ran.

## Verification
- Root unit/eval suite: **242 passed**. Staged coordinator PostgreSQL integration: **10 passed**.
- Focused Ruff, strict mypy, wheel package-data check, and `git diff --check` passed.
- The work is runnable; there is no partial migration, unsafe write path, or intentional uncommitted
  runtime work.

## Single Next Recommended Task
**Add reproducible fixed-case structural startup and whole-artifact evidence output for cases 02/03.**

First action: define and provider-free test a Workbench-owned structural wrapper that loads one
manifest case, constructs only its authorized synthetic grounding, pins the opaque assignment, and
emits body-free measurement/reviewer inputs before making another live call.

## References
[`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md) P7-14f;
[`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md) dungeon/model
sections; [`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md) R5.
