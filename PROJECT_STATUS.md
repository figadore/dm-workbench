# Project Status and Handoff

> Read this bounded live handoff first. Completed milestones and superseded notes are in
> [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md); implementation detail remains available in
> Git. Do not infer the next task from historical V2/V3/V4 names.

## Current State

- **Updated:** 2026-08-30
- **Branch/HEAD:** `fast-track-prompt-to-dungeon` at `3267ee1`, one commit ahead of
  `origin/fast-track-prompt-to-dungeon`, plus the uncommitted slice below.
- **Working tree:** **uncommitted P7-14f faux-provider room-narrative dispatch plus
  provider-free staged-planner slices**. No migration, live provider call, credential,
  canonical campaign path, preparation approval path, or staged dispatcher is partially
  edited.
- **Current task:** **P7-14f — Staged Tier A authoring and anti-overfitting evaluation.**
- **Task state:** all required Tier A enrichment kinds have provider-free exact-ID
  boundaries and independently bounded faux-provider dispatch/publication. Deterministic
  next-task planning is complete; a one-step provider-free staged coordinator is next.
- **Schema head:** `0008_workbench_defaults`; no migration changed or is pending.
- **Retention gate:** **not crossed.** Active V1 contracts evolve in place; there is no
  retained real-user artifact, external consumer, non-disposable deployment, or promised
  replay requirement.

## Implemented Room-Narrative Dispatch Slice

The homogeneous room-narrative task now runs after accepted local mechanics:

- one independently pinned `submit_dungeon_room_narrative` tool accepts only the existing
  exact-ID output contract for 1–8 selected rooms;
- its task-specific profile has a 6,000-token cumulative budget, 2,048-output ceiling,
  one repair, and a complete canonical repair-message/tool-schema reservation estimate;
- semantic diagnostics identify foreign and omitted rooms without copying rejected prose;
- accepted output and final model lineage are retained only in the authorized DM-only
  child specification;
- deterministic projection fills only selected blank room read-aloud/framing and removes
  only their exact room blockers;
- publication is atomic and preserves package/map bytes, all puzzle/exploration/feature/
  trap/objective content and lineage, unselected rooms, and unrelated blockers; and
- rejected submissions or publication failures leave the objective parent current with
  body-free durable diagnostics.

The staged Copper Tide integration starts from independently accepted puzzle,
exploration, feature, trap, and objective content. It proves exact-set repair, independent
profile/budgets, lineage retention, projection isolation, blocker isolation, byte-identical
map assets, and safe rejection/publication failure.

## Implemented Staged-Planner Slice

`plan_dungeon_staged_enrichment` is a pure decision boundary over one immutable current
specification:

- it derives exact puzzle rooms, exploration slots, feature/trap/objective markers, and
  narrative rooms from the package and exact guide;
- it compares projected content with matching retained successful lineage, skips accepted
  tasks, and chooses one deterministic mechanic target in puzzle/exploration/feature/trap/
  objective order;
- it chooses the bounded homogeneous narrative room set only after local mechanics are
  accepted; and
- missing/mismatched guides, unsupported blockers, stale/duplicate lineage, and untracked
  projected content fail closed with body-free blocked state.

The planner has no provider, persistence, topology, geometry, approval, preparation-write,
or canonical operation. Two materially independent synthetic plans prove the exact target
order, accepted skipping, narrative gate, blocked state, complete state, and input
immutability.

## Active Boundaries and Known Issues

- Models propose preparation content only. They cannot alter topology, geometry,
  visibility, deterministic arithmetic/DC policy, preparation approval, or canon.
- One-step dispatch and automatic/repeated staged orchestration, the multi-case quality
  comparison, staged live result, Tier B/C, and resumed output/print work are not
  implemented.
- Live provider use remains paused. Pinned `@earendil-works/pi-ai` Codex transport does
  not serialize the requested hard output limit; post-response checks protect publication
  but cannot prevent provider usage. The acknowledged frozen-canary exception remains
  operator risk, not ordinary rollout permission.
- Narrative dispatch can cover only rooms whose required local mechanics are accepted;
  rooms sharing an incomplete mechanic remain readiness-blocked and are skipped by caller
  selection until that mechanic is accepted.
- Package and root pytest suites must run separately because duplicate test module
  basenames cause an import-file-mismatch when collected in one process.
- The full integration suite was not run. An older broad P7-14e run had three unrelated
  failures: Alembic/SQLAlchemy metadata diffs, a duplicate retrieval result, and a
  document-history trigger hit by a direct fixture. Their current status is unverified.
- No provider was contacted. No credential, canonical campaign write, preparation
  approval, pure-package change, migration, redaction system, or second persistence store
  is present in this slice.

## Current Files and Verification

Uncommitted implementation:

- `src/dm_assistant/orchestration/dungeons/contracts.py`
- `src/dm_assistant/orchestration/dungeons/service.py`
- `src/dm_assistant/orchestration/dungeons/__init__.py`
- `src/dm_assistant/orchestration/dungeons/room_narrative_prompting.py` (new)
- `src/dm_assistant/orchestration/dungeons/room_narrative_application.py` (new)
- `src/dm_assistant/orchestration/dungeons/staged_enrichment.py` (new)
- `tests/integration/test_dungeon_room_narrative_prompt.py` (new)
- `tests/unit/test_dungeon_staged_enrichment_plan.py` (new)

Uncommitted documentation:

- `README.md`
- `dm-assistant-implementation-plan.md`
- `dm-assistant-technical-architecture.md`
- `dungeon-generation-recovery-plan.md`
- `PROJECT_STATUS.md`

Recorded for this slice:

- Focused isolated-PostgreSQL narrative integration -> **3 passed**.
- Prior isolated-PostgreSQL staged integration gate -> **15 passed**; current rerun ->
  **15 skipped** because `DM_TEST_DATABASE_URL` is unavailable.
- Focused staged-planner unit gate -> **3 passed**.
- `uv run pytest -q tests/unit tests/evals` -> **206 passed**.
- `uv run pytest -q packages/dungeon-engine/tests` -> **139 passed**.
- Ruff lint/format over changed Python sources and integration test -> **passed**.
- Strict mypy over changed dungeon contracts/service/prompt/application -> **passed**.
- `git diff --check` -> **passed** after the final handoff update.

Suggested commit subject: `P7-14f add room narrative dispatch and staged planning`

## Single Next Recommended Task

**Add a provider-free one-step staged coordinator that consumes the planner result and
invokes exactly one existing task seam with explicit trusted task-policy input.**

**First concrete action:** add a failing
`tests/integration/test_dungeon_staged_enrichment_coordinator.py` case that starts from a
structural parent, supplies explicit policy for its selected puzzle target, uses the faux
provider, and proves exactly one accepted atomic child plus a newly planned exploration
task. Add sibling rejection coverage proving the parent remains current and no second task
is attempted.

Do **not** add repeated/full-chain dispatch, contact a live provider, add Tier B/C, add a
migration, a queue, model-authored mechanics, preparation approval, or a universal
optional-field generation context in that slice.

## Authoritative References

- [`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md), P7-14f
- [`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md),
  “Dungeon Generation Architecture” and “Dungeon Primitives and Model Tools”
- [`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md), R5
- [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md) for compact completed-milestone history
