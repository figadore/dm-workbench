# Project Status and Handoff

> Read this bounded live handoff first. Completed milestones and superseded notes are in
> [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md); implementation detail remains available in
> Git. Do not infer the next task from historical V2/V3/V4 names.

## Current State

- **Updated:** 2026-08-30
- **Branch/HEAD:** `fast-track-prompt-to-dungeon` at `c9cab08`; four commits ahead of
  `origin/fast-track-prompt-to-dungeon`.
- **Working tree:** **uncommitted P7-14f trap-dispatch slice** in the files below. No
  migration or provider credential path is partially edited.
- **Current task:** **P7-14f — Staged Tier A authoring and anti-overfitting evaluation.**
- **Task state:** exact-ID trap context/validation/projection plus independently bounded
  faux-provider dispatch, repair, lineage, and atomic publication are complete and green.
- **Schema head:** `0008_workbench_defaults`; no migration changed or is pending.
- **Retention gate:** **not crossed.** Active V1 contracts evolve in place; there is no
  retained real-user artifact, external consumer, non-disposable deployment, or promised
  replay requirement.

## Implemented Staged Seam

The model-visible structural proposal no longer contains prose-heavy `guide_content`.
After deterministic topology, certificate, geometry, and secrecy validation, puzzle,
exploration, feature-interaction, and room-trap tasks each have strict exact-ID contexts/
outputs, semantic validation, independent prompt/profile/budget/repair pins,
deterministic guide projection, accepted-content lineage, and atomic DM-only child
publication.

The completed trap dispatch slice:

- joins one exact package room-trap marker and current guide entry to local room geometry
  plus code-owned detection and disable difficulties;
- exposes only `submit_dungeon_trap` through a task-specific profile with a 6,000-token
  cumulative budget, 2,048-output ceiling, and one complete-input-reserved repair;
- rejects foreign package/room/trap IDs, structural/cross-task fields, numeric difficulty
  fields, and DCs embedded in model-authored text;
- projects accepted warning, trigger/effect, detection/disable counterplay, consequences,
  and optional recovery into only the selected guide trap; and
- atomically publishes accepted content and lineage while preserving package/map hashes,
  accepted puzzle/exploration/feature content and lineage, the other trap, and unrelated
  readiness blockers. Rejection leaves the parent current and stores body-free
  diagnostics only.

The independent Copper Tide Foundry integration case is not derived from the archive
fixture. It exercises a staged structural -> puzzle -> exploration -> feature -> trap
lineage with two traps and verifies cross-task preservation.

## Active Boundaries and Known Issues

- Models propose content only. They cannot alter topology, geometry, visibility,
  deterministic arithmetic/DC policy, preparation approval, or canon.
- Objective enrichment, room narrative enrichment, automatic staged orchestration, Tier
  B/C, the multi-case quality comparison, and a staged live result are not implemented.
- Live provider use remains paused. Pinned `@earendil-works/pi-ai` Codex transport does
  not serialize the requested hard output limit; post-response checks protect publication
  but cannot prevent provider usage. The acknowledged frozen-canary exception remains
  operator risk, not ordinary rollout permission.
- Package and root pytest suites must run separately because duplicate test module
  basenames cause an import-file-mismatch when collected in one process.
- The full integration suite was not run. An older broad P7-14e run had three unrelated
  failures: Alembic/SQLAlchemy metadata diffs, a duplicate retrieval result, and a
  document-history trigger hit by a direct fixture. Their current status is unverified;
  the focused staged dungeon integration gate is green.
- No provider was contacted. No credential, canonical campaign write, preparation
  approval, pure-package change, migration, redaction system, or second persistence store
  is present in this slice.

## Current Files and Verification

Uncommitted implementation:

- `src/dm_assistant/orchestration/dungeons/contracts.py`
- `src/dm_assistant/orchestration/dungeons/service.py`
- `src/dm_assistant/orchestration/dungeons/trap_prompting.py` (new)
- `src/dm_assistant/orchestration/dungeons/trap_application.py` (new)
- `src/dm_assistant/orchestration/dungeons/__init__.py`
- `tests/integration/test_dungeon_trap_prompt.py` (new)

Uncommitted documentation:

- `README.md`
- `dm-assistant-implementation-plan.md`
- `dm-assistant-technical-architecture.md`
- `dungeon-generation-recovery-plan.md`
- `PROJECT_STATUS.md`

Recorded for this slice:

- `uv run pytest -q tests/unit tests/evals` -> **196 passed**.
- `uv run pytest -q packages/dungeon-engine/tests` -> **139 passed**.
- `uv run pytest -q tests/unit/test_dungeon_trap_enrichment_contract.py` -> **3 passed**.
- Focused staged dungeon integration gate -> **12 passed** against disposable PostgreSQL
  with pgvector (includes **3 new trap tests**).
- Ruff lint/format and strict mypy over changed dungeon Python sources -> **passed**.

Suggested commit subject: `P7-14f add bounded trap dispatch and publication`

## Single Next Recommended Task

**Add a provider-free exact-ID objective enrichment contract and deterministic projection
using the Copper Tide Foundry staged child as the independent regression.**

**First concrete action:** add a failing unit contract test that builds objective context
from the exact objective marker, current guide entry, local geometry, accepted mechanic
summaries, and bounded stakes/constraints, then rejects foreign IDs and cross-task or
structural mutation.

Success must update only the selected objective and remove only its readiness blocker while
preserving package/map bytes, all accepted puzzle/exploration/feature/trap content and
lineage, other guide entries, and unrelated diagnostics. Do **not** add provider dispatch,
room narrative, automatic orchestration, live calls, Tier B/C, a migration, or a universal
optional-field generation context in that provider-free slice.

## Authoritative References

- [`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md), P7-14f
- [`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md),
  “Dungeon Generation Architecture” and “Dungeon Primitives and Model Tools”
- [`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md), R5
- [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md) for compact completed-milestone history
