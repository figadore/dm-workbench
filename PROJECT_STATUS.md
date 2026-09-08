# Project Status and Handoff

> This is the only live resume point. Git supplies branch, HEAD, and working-tree details.
> Completed milestones are summarized in [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md).

## Current Task
- **Task:** P7-14f — staged Tier A authoring and anti-overfitting evaluation.
- **Current work:** a provider-free fixed-case puzzle/exploration execution and exact-resumption
  boundary is implemented and uncommitted.
- **Product state:** staged orchestration and final validation remain implemented. The Tier A quality
  gate is red because no preparation-ready live artifact or completed blinded human matrix exists.
- **Schema head:** `0008_workbench_defaults`; no migration is involved.
- **Retention gate:** **not crossed**. Active V1 contracts and disposable alpha data evolve in place.

## Completed Behavior
- A pure fixed-case planner verifies the exact structural prompt hash and authorized synthetic facts,
  requires one matched provider/model/effort assignment, and selects only the deterministic next
  puzzle or exploration target from the current staged plan.
- Puzzle policy is derived from the manifest setting/interaction style and exact puzzle room.
  Exploration policy uses the manifest interaction style, exact encounter slot, and sorted local
  feature affordances. Both retain the existing Luna-fast budgets/contracts.
- A Workbench application wrapper computes case, parent specification, policy, built context,
  resolved profile, variant assignment, and exploration-contract hashes before dispatching the
  existing one-step coordinator.
- Each wrapper generation run stores the complete trusted policy and resolved profile in a private
  generation-context envelope. Ordinary run inspection exposes only body-free hashes and IDs.
- Resumption accepts only a failed fixed-case wrapper whose input, context payload, task profile,
  schema, and generator pins recompute exactly. Drift or a pre-boundary attempt fails before provider
  dispatch; accepted content still publishes through the existing atomic DM-only task seam.
- The composition root exposes the new application service when the model gateway is enabled.
  Architecture, implementation, and recovery policy now describe this replay boundary.

## Faux Evidence
- PostgreSQL/faux coverage creates a case-01 structural parent, rejects an over-budget puzzle without
  publishing, and persists its private replay payload plus body-free pins.
- A changed manifest is rejected before the faux gateway is called. The unchanged manifest resumes
  with the same input/context hashes, accepts the puzzle, publishes exactly one child, and leaves the
  artifact a draft.
- This boundary currently supports puzzle and exploration only. Feature, trap, objective, narrative,
  complete fixed-case execution, and a user-facing command remain outside this slice.

## Live Evidence and Authorization
- The frozen canary remains the only qualifying exploration overage; the repeat gate is **1 of 2**.
- Case 01 puzzle/exploration succeeded in the prior bounded live check. Disposable artifact
  `35ec4e9b-cbc5-416b-9ff7-3fade7865044` remains a draft at version
  `e6902ff4-87e8-4966-8d83-25dd744ddc5d`, with feature interaction next.
- Those attempts predate the new wrapper and cannot be claimed as exact-resumption evidence.
- No live call, retry, debug capture, effort/budget change, or Terra comparison is authorized.

## Intentional Uncommitted Work and Verification
- Runtime: `src/dm_assistant/runtime.py` and
  `src/dm_assistant/orchestration/dungeons/{__init__,evals,eval_application}.py`.
- Faux integration: `tests/integration/test_dungeon_staged_enrichment_coordinator.py`.
- Policy/handoff: `dm-assistant-implementation-plan.md`,
  `dm-assistant-technical-architecture.md`, `dungeon-generation-recovery-plan.md`, and this file.
- Root unit/eval suite: **241 passed**. Staged coordinator PostgreSQL integration: **10 passed**.
  Focused Ruff check/format and strict mypy passed. `git diff --check` passed before this update.
- The work is runnable; there is no partial migration or unsafe write path. Existing unrelated
  repository-wide Ruff/mypy and Library/schema findings remain documented in history.

## Single Next Recommended Task
**Review and commit the P7-14f fixed-case execution/resumption boundary; do not make a live call.**

First action: inspect the uncommitted runtime/test/policy diff, rerun focused checks and
`git diff --check`, then commit with subject `P7-14f pin reproducible fixed-case task resumption`.

## References
[`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md) P7-14f;
[`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md) dungeon/model
sections; [`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md) R5.
