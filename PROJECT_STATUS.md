# Project Status and Handoff

> Read this bounded live handoff first. Completed milestones and superseded notes are in
> [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md); implementation detail remains available in
> Git. Do not infer the next task from historical V2/V3/V4 names.

## Current State

- **Updated:** 2026-08-30
- **Branch/HEAD:** `fast-track-prompt-to-dungeon` at `b7170c5`; three commits ahead of
  `origin/fast-track-prompt-to-dungeon`.
- **Working tree:** **uncommitted P7-14f trap-contract slice** in the files listed below.
  No migration or provider/persistence path is partially edited.
- **Current task:** **P7-14f — Staged Tier A authoring and anti-overfitting evaluation.**
- **Task state:** the provider-free room-trap context/validation/projection slice is
  complete and green; trap provider dispatch/publication is the next bounded slice.
- **Schema head:** `0008_workbench_defaults`; no migration changed or is pending.
- **Retention gate:** **not crossed.** Active V1 contracts evolve in place; there is no
  retained real-user artifact, external consumer, non-disposable deployment, or promised
  replay requirement.

## Implemented Staged Seam

The model-visible structural proposal no longer contains prose-heavy `guide_content`.
After deterministic topology, certificate, geometry, and secrecy validation, puzzle,
exploration, and feature-interaction tasks each have strict exact-ID contexts/outputs,
semantic validation, independent prompt/profile/budget/repair pins, deterministic guide
projection, accepted-content lineage, and atomic DM-only child publication.

The new provider-free trap seam:

- joins one exact package room-trap marker and current guide entry to local room geometry
  plus deterministic detection and disable difficulties;
- accepts only the exact package/room/trap IDs and typed warning, trigger/effect,
  detection/disable counterplay, consequences, and optional reset/recovery;
- rejects foreign IDs, structural/cross-task fields, numeric difficulty fields, and DCs
  embedded in model-authored text;
- projects into only the selected guide trap while retaining code-owned difficulties and
  rendering every accepted field in Markdown/web output; and
- preserves package/map bytes, accepted puzzle/exploration/feature content, all unrelated
  guide entries, and unrelated readiness diagnostics.

The independent Copper Tide Foundry regression is not derived from the archive fixture.
It includes two traps and accepted puzzle, exploration, and feature content so projection
is tested against real cross-task preservation rather than empty collections.

## Active Boundaries and Known Issues

- Models propose content only. They cannot alter topology, geometry, visibility,
  deterministic arithmetic/DC policy, preparation approval, or canon.
- Trap provider dispatch/repair/lineage/atomic child publication, room narrative
  enrichment, automatic staged orchestration, Tier B/C, and a staged live result are not
  implemented.
- Live provider use remains paused. Pinned `@earendil-works/pi-ai` Codex transport does
  not serialize the requested hard output limit; post-response checks protect publication
  but cannot prevent provider usage. The acknowledged frozen-canary exception remains
  operator risk, not ordinary rollout permission.
- Package and root pytest suites must run separately because duplicate test module
  basenames cause an import-file-mismatch when collected in one process.
- The full integration suite was not run. An older broad P7-14e run had three unrelated
  failures: Alembic/SQLAlchemy metadata diffs, a duplicate retrieval result, and a
  document-history trigger hit by a direct fixture. Their current status is unverified;
  the focused dungeon integration gate is green.
- No provider was contacted. No credential, canonical campaign write, preparation
  approval, pure-package change, migration, redaction system, or second persistence store
  is present in this slice.

## Current Files and Verification

Uncommitted implementation:

- `src/dm_assistant/orchestration/dungeons/contracts.py`
- `src/dm_assistant/orchestration/dungeons/service.py`
- `src/dm_assistant/orchestration/dungeons/__init__.py`
- `src/dm_assistant/web/templates/dungeon_detail.html`
- `tests/unit/test_dungeon_trap_enrichment_contract.py` (new)

Uncommitted documentation:

- `README.md`
- `dm-assistant-implementation-plan.md`
- `dm-assistant-technical-architecture.md`
- `dungeon-generation-recovery-plan.md`
- `PROJECT_STATUS.md`

Recorded for this slice:

- `uv run pytest -q tests/unit tests/evals` -> **196 passed**.
- `uv run pytest -q packages/dungeon-engine/tests` -> **139 passed**.
- Focused trap/puzzle/exploration/workflow/guide unit gate -> **26 passed**.
- Focused dungeon integration gate -> **11 passed** against disposable PostgreSQL.
- Ruff lint/format and strict mypy over changed dungeon Python sources -> **passed**.
- `git diff --check` -> **passed** after the handoff update.

Suggested commit subject: `P7-14f add exact-ID trap enrichment contract`

## Single Next Recommended Task

**Add independently bounded faux-provider trap dispatch, repair, accepted-content lineage,
and atomic DM-only child publication for the exact trap contract.**

**First concrete action:** add a failing integration test in a new
`tests/integration/test_dungeon_trap_prompt.py` that dispatches the Copper Tide Foundry
trap through a task-specific faux profile and proves one 6,000-token cumulative/
2,048-output budget with one complete-input-reserved repair.

Success must publish one child preserving package/map hashes, prior puzzle/exploration/
feature content and lineage, the other trap, and unrelated blockers. Rejection or
publication failure must leave the parent current and persist only body-free diagnostics.
Do **not** add room narrative work, automatic staged orchestration, live calls, Tier B/C,
a migration, or a universal optional-field generation context in that slice.

## Authoritative References

- [`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md), P7-14f
- [`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md),
  “Dungeon Generation Architecture” and “Dungeon Primitives and Model Tools”
- [`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md), R5
- [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md) for compact completed-milestone history
