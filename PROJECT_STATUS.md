# Project Status and Handoff

> Read this bounded live handoff first. Completed milestones and superseded notes are in
> [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md); implementation detail remains available in
> Git. Do not infer the next task from historical V2/V3/V4 names.

## Current State

- **Updated:** 2026-08-30
- **Branch/HEAD:** `fast-track-prompt-to-dungeon` at `7387d29`; two commits ahead of
  `origin/fast-track-prompt-to-dungeon`.
- **Working tree:** documentation-only handoff compaction is uncommitted in `AGENTS.md`,
  `PROJECT_HISTORY.md`, and this file. No implementation or migration is partially edited.
- **Current task:** **P7-14f — Staged Tier A authoring and anti-overfitting evaluation.**
- **Task state:** **WIP.** The latest completed implementation slice adds bounded
  feature-interaction faux-provider dispatch and atomic DM-only child publication on top
  of accepted puzzle and exploration children.
- **Schema head:** `0008_workbench_defaults`; no migration changed or is pending.
- **Retention gate:** **not crossed.** Active V1 contracts evolve in place; there is no
  retained real-user artifact, external consumer, non-disposable deployment, or promised
  replay requirement.

## Implemented Staged Seam

The model-visible structural proposal no longer contains prose-heavy `guide_content`.
After deterministic topology, certificate, geometry, and secrecy validation, puzzle,
exploration, and feature-interaction tasks each have:

- a strict task-specific exact-ID input/output contract and trusted local context slice;
- semantic rejection of foreign IDs and structural or cross-task mutation;
- independent profile, effort, prompt/schema pins, a 6,000-token cumulative ceiling,
  a 2,048-output ceiling, and one complete-input-reserved repair;
- deterministic projection into only the selected guide entry;
- accepted-content/model lineage in the authorized DM-only artifact; and
- atomic child publication whose failure leaves the parent current with body-free bounded
  diagnostics.

The current feature child preserves exact package geometry and map hashes, accepted
puzzle/exploration content and lineage, every unrelated feature entry, and unrelated
readiness blockers. Success removes only the selected feature blocker.

## Active Boundaries and Known Issues

- Models propose content only. They cannot alter topology, geometry, visibility,
  deterministic arithmetic/DC policy, preparation approval, or canon.
- Trap enrichment, room narrative enrichment, automatic initial staged orchestration,
  Tier B/C, and a staged live result are not implemented.
- Live provider use remains paused. Pinned `@earendil-works/pi-ai` Codex transport does
  not serialize the requested hard output limit; post-response checks protect publication
  but cannot prevent provider usage. The acknowledged frozen-canary exception remains
  operator risk, not ordinary rollout permission.
- Package and root pytest suites must run separately because duplicate test module
  basenames cause an import-file-mismatch when collected in one process.
- The full integration suite was not rerun after the latest staged slices. An older broad
  P7-14e run had three unrelated failures: Alembic/SQLAlchemy metadata diffs, a duplicate
  retrieval result, and a document-history trigger hit by a direct fixture. Their current
  status is unverified; the focused dungeon integration gate is green.
- Generated review packets remain ignored. No live provider response, credential,
  canonical campaign write, preparation approval, pure-package change, redaction system,
  or second persistence store is present in this handoff.

## Current Files and Verification

Latest implementation commit `7387d29` added or updated the feature prompt/application
services, dungeon contracts/service exports, the Skyroot integration workflow, and
matching architecture/plan documentation. Use `git show --stat 7387d29` for the exact
committed list instead of treating this file as a Git inventory.

Recorded on current HEAD before this documentation-only compaction:

- `uv run pytest -q tests/unit tests/evals` -> **193 passed**.
- `uv run pytest -q packages/dungeon-engine/tests` -> **139 passed**.
- `make test-integration PYTEST_ARGS='-q tests/integration/test_dungeon_exploration_prompt.py tests/integration/test_dungeon_puzzle_prompt.py tests/integration/test_dungeon_studio_cli.py tests/integration/test_dungeon_studio_workflow.py tests/integration/test_dungeon_studio_web_prompt.py'`
  -> **11 passed** against disposable PostgreSQL.
- Focused feature/puzzle/exploration contract gate -> **19 passed**.
- Focused Ruff lint/format and strict mypy over changed dungeon sources -> **passed**.
- No provider was contacted.

No implementation tests were rerun for the handoff-only Markdown changes.
`git diff --check` -> **passed** after the compaction.

Suggested commit subject: `P7-14f compact the active project handoff`

## Single Next Recommended Task

**Add the provider-free exact-ID contract/context/validation/projection seam for one trap
interaction in an independent synthetic case.**

**First concrete action:** add a failing non-archive unit regression, preferably in
`tests/unit/test_dungeon_trap_enrichment_contract.py`, that joins one exact package trap
marker and its current guide entry to local geometry and deterministic trap mechanics.

Require a trap-only output with observable warning, actual trigger/effect narration,
reasonable detection and disable counterplay without model-authored numeric DCs,
consequences, and reset/recovery when applicable. Prove that foreign package/room/trap IDs
and structural/cross-task fields are rejected. Deterministic projection must remove only
the selected trap blocker while preserving package/map state, accepted puzzle,
exploration, and feature content/lineage, other guide entries, and unrelated blockers.

Do **not** add trap provider dispatch, narrative work, live calls, Tier B/C, or a universal
optional-field generation context in the same slice.

## Authoritative References

- [`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md), P7-14f
- [`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md),
  “Dungeon Generation Architecture” and “Dungeon Primitives and Model Tools”
- [`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md), R5
- [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md) for compact completed-milestone history
