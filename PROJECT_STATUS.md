# Project Status and Handoff

> Read this bounded live handoff first. Completed milestones and superseded notes are in
> [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md); implementation detail remains available in
> Git. Do not infer the next task from historical V2/V3/V4 names.

## Current State

- **Updated:** 2026-08-30
- **Branch/HEAD:** `fast-track-prompt-to-dungeon` at `e6f7110`, matching
  `origin/fast-track-prompt-to-dungeon` before the uncommitted slice below.
- **Working tree:** **uncommitted P7-14f provider-free objective-enrichment slice** in the
  files listed below. No migration, provider credential, dispatch, or persistence path is
  partially edited.
- **Current task:** **P7-14f — Staged Tier A authoring and anti-overfitting evaluation.**
- **Task state:** exact-ID objective context, semantic validation, and deterministic guide
  projection are complete and green. Objective provider dispatch/publication is next.
- **Schema head:** `0008_workbench_defaults`; no migration changed or is pending.
- **Retention gate:** **not crossed.** Active V1 contracts evolve in place; there is no
  retained real-user artifact, external consumer, non-disposable deployment, or promised
  replay requirement.

## Implemented Staged Seam

The model-visible structural proposal no longer contains prose-heavy `guide_content`.
After deterministic topology, certificate, geometry, and secrecy validation, puzzle,
exploration, feature-interaction, and trap tasks have strict exact-ID contexts/outputs,
independent faux-provider budgets/repairs, deterministic guide projection, accepted model
lineage, and atomic DM-only child publication.

The new provider-free objective slice:

- joins one exact objective marker and current guide entry to its local package geometry;
- includes only a bounded exact-ID selection of summaries copied from already accepted
  puzzle, exploration, feature, and trap guide content plus trusted stakes/constraints;
- accepts only the exact package/room/objective IDs, observable goal, adjudication,
  two-to-four resolutions, optional accepted-mechanic references, and setback/aftermath;
- rejects foreign package/room/objective/mechanic IDs and structural, cross-task, rename,
  or objective-kind mutation through strict schema and semantic checks; and
- projects only into the selected objective, removes only its missing-content blocker,
  and preserves package/map bytes, accepted prior mechanics, all other guide entries, and
  unrelated diagnostics.

The Copper Tide Foundry regression is independent of the archive fixture and exercises an
accepted puzzle, exploration challenge, feature interaction, and two traps before objective
projection. This provider-free boundary does not alter persisted artifact lineage; objective
lineage and atomic child publication belong to the next dispatch slice.

## Active Boundaries and Known Issues

- Models propose content only. They cannot alter topology, geometry, visibility,
  deterministic arithmetic/DC policy, preparation approval, or canon.
- Objective dispatch/repair/lineage/publication, room narrative enrichment, automatic
  staged orchestration, Tier B/C, the multi-case quality comparison, and a staged live
  result are not implemented.
- Live provider use remains paused. Pinned `@earendil-works/pi-ai` Codex transport does
  not serialize the requested hard output limit; post-response checks protect publication
  but cannot prevent provider usage. The acknowledged frozen-canary exception remains
  operator risk, not ordinary rollout permission.
- Package and root pytest suites must run separately because duplicate test module
  basenames cause an import-file-mismatch when collected in one process.
- The full integration suite was not run. An older broad P7-14e run had three unrelated
  failures: Alembic/SQLAlchemy metadata diffs, a duplicate retrieval result, and a
  document-history trigger hit by a direct fixture. Their current status is unverified;
  the focused staged dungeon integration gate was green for the prior trap-dispatch slice.
- No provider was contacted. No credential, canonical campaign write, preparation
  approval, pure-package change, migration, redaction system, or second persistence store
  is present in this slice.

## Current Files and Verification

Uncommitted implementation:

- `src/dm_assistant/orchestration/dungeons/contracts.py`
- `src/dm_assistant/orchestration/dungeons/service.py`
- `src/dm_assistant/orchestration/dungeons/__init__.py`
- `tests/unit/test_dungeon_objective_enrichment_contract.py` (new)

Uncommitted documentation:

- `README.md`
- `dm-assistant-implementation-plan.md`
- `dm-assistant-technical-architecture.md`
- `dungeon-generation-recovery-plan.md`
- `PROJECT_STATUS.md`

Recorded for this slice:

- `uv run pytest -q tests/unit tests/evals` -> **199 passed**.
- `uv run pytest -q packages/dungeon-engine/tests` -> **139 passed**.
- Focused objective/trap/exploration/puzzle/guide contract gate -> **17 passed**.
- Ruff lint/format and strict mypy over changed dungeon Python sources -> **passed**.
- `git diff --check` -> **passed** after the final handoff rewrite.

Suggested commit subject: `P7-14f add exact-ID objective enrichment contract`

## Single Next Recommended Task

**Add independently bounded faux-provider objective dispatch, repair, accepted-content
lineage, and atomic DM-only child publication for the exact objective contract.**

**First concrete action:** add a failing integration test in a new
`tests/integration/test_dungeon_objective_prompt.py` that starts from the Copper Tide
Foundry trap child, dispatches the exact objective through a task-specific faux profile,
and proves its own 6,000-token cumulative/2,048-output budget with one complete-input-
reserved repair.

Success must publish one child preserving package/map hashes, all accepted puzzle/
exploration/feature/trap content and lineage, objective identity/kind, other guide entries,
and unrelated blockers. Rejection or publication failure must leave the trap parent
current and persist only body-free diagnostics. Do **not** add room narrative, automatic
orchestration, live calls, Tier B/C, a migration, or a universal optional-field generation
context in that slice.

## Authoritative References

- [`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md), P7-14f
- [`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md),
  “Dungeon Generation Architecture” and “Dungeon Primitives and Model Tools”
- [`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md), R5
- [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md) for compact completed-milestone history
