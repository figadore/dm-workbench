# Project Status and Handoff

> Read this bounded live handoff first. Completed milestones and superseded notes are in
> [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md); implementation detail remains available in
> Git. Do not infer the next task from historical V2/V3/V4 names.

## Current State

- **Updated:** 2026-08-30
- **Branch/HEAD:** `fast-track-prompt-to-dungeon` at `231a39f`, two commits ahead of
  `origin/fast-track-prompt-to-dungeon`, plus the uncommitted slice below.
- **Working tree:** **uncommitted P7-14f provider-free one-step staged coordinator**.
  No migration, live provider call, credential, canonical campaign path, preparation
  approval path, repeated/full-chain dispatcher, or pure-package change is partially
  edited.
- **Current task:** **P7-14f — Staged Tier A authoring and anti-overfitting evaluation.**
- **Task state:** all Tier A enrichment kinds have independently bounded faux-provider
  seams; deterministic planning and one-step policy-checked dispatch are complete. Broader
  resumed-task coordinator coverage is next.
- **Schema head:** `0008_workbench_defaults`; no migration changed or is pending.
- **Retention gate:** **not crossed.** Active V1 contracts evolve in place; there is no
  retained real-user artifact, external consumer, non-disposable deployment, or promised
  replay requirement.

## Implemented One-Step Coordinator Slice

`DungeonStagedEnrichmentCoordinator` now composes the pure planner with existing task
application seams without creating a second orchestration or persistence path:

- one command carries the campaign/artifact/current-parent identity plus exactly one
  discriminated puzzle, exploration, feature, trap, objective, or narrative policy;
- exact task kind, room IDs, and target IDs must match the planner result before provider
  dispatch; stale or cross-artifact parents fail closed;
- a ready plan invokes exactly one existing independently budgeted task application seam;
- an accepted task creates the existing atomic DM-only child and the coordinator replans
  only that current child;
- rejection returns the unchanged plan, leaves the parent current, and never attempts the
  next staged task; and
- blocked/complete plans make no task attempt. There is no automatic loop, provider/profile
  resolver, topology/geometry mutation, approval, or canonical operation.

The new faux-provider integration starts from a structural Cobalt Orrery parent. Success
proves one puzzle child followed by a newly selected exploration task. Sibling semantic
rejection proves only the puzzle task's bounded repair occurs, no child is created, the
puzzle parent remains current, no next staged task is attempted, and rejected IDs remain
absent from durable diagnostics.

## Active Boundaries and Known Issues

- Models propose preparation content only. They cannot alter topology, geometry,
  visibility, deterministic arithmetic/DC policy, preparation approval, or canon.
- Automatic/repeated full-chain orchestration, broad coordinator coverage for resumed
  later task kinds, the multi-case quality comparison, staged live result, Tier B/C, and
  resumed output/print work are not implemented.
- Live provider use remains paused. Pinned `@earendil-works/pi-ai` Codex transport does
  not serialize the requested hard output limit; post-response checks protect publication
  but cannot prevent provider usage. The acknowledged frozen-canary exception remains
  operator risk, not ordinary rollout permission.
- Narrative dispatch can cover only rooms whose required local mechanics are accepted;
  rooms sharing an incomplete mechanic remain readiness-blocked until it is accepted.
- Package and root pytest suites must run separately because duplicate test module
  basenames cause an import-file-mismatch when collected in one process.
- PostgreSQL coordinator integration was collected but skipped because
  `DM_TEST_DATABASE_URL` is unavailable. The full integration suite was not run. An older
  broad P7-14e run had three unrelated failures: Alembic/SQLAlchemy metadata diffs, a
  duplicate retrieval result, and a document-history trigger hit by a direct fixture;
  their current status is unverified.
- No provider was contacted. No credential, canonical campaign write, preparation
  approval, migration, redaction system, or second persistence store is present.

## Current Files and Verification

Uncommitted implementation:

- `src/dm_assistant/orchestration/dungeons/staged_enrichment_coordinator.py` (new)
- `src/dm_assistant/orchestration/dungeons/__init__.py`
- `tests/integration/test_dungeon_staged_enrichment_coordinator.py` (new)

Uncommitted documentation:

- `README.md`
- `dm-assistant-implementation-plan.md`
- `dm-assistant-technical-architecture.md`
- `dungeon-generation-recovery-plan.md`
- `PROJECT_STATUS.md`

Recorded for this slice:

- Focused planner/coordinator gate -> **3 passed, 2 skipped** (PostgreSQL unavailable).
- `uv run pytest -q tests/unit tests/evals` -> **206 passed**.
- `uv run pytest -q packages/dungeon-engine/tests` -> **139 passed**.
- Ruff lint/format over changed Python sources and integration test -> **passed**.
- Strict mypy over planner/coordinator/public exports and the new integration test ->
  **passed**.
- `git diff --check` -> **passed**.

Suggested commit subject: `P7-14f add one-step staged enrichment coordination`

## Single Next Recommended Task

**Extend the one-step coordinator regression across a resumed exploration task before
adding any repeated/full-chain runner.**

**First concrete action:** add a failing integration case that starts from the accepted
puzzle child, supplies an exact `DungeonStagedExplorationPolicy`, proves exactly one
exploration child is published, and verifies the replanned task is the expected next
feature/trap/objective target. Add a mismatched-slot policy sibling proving zero provider
calls and no version change.

Do **not** add automatic chain repetition, contact a live provider, add Tier B/C, add a
migration, a queue, model-authored mechanics, preparation approval, or a universal
optional-field generation context in that slice.

## Authoritative References

- [`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md), P7-14f
- [`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md),
  “Dungeon Generation Architecture” and “Dungeon Primitives and Model Tools”
- [`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md), R5
- [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md) for compact completed-milestone history
