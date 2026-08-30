# Project Status and Handoff

> Read this bounded live handoff first. Completed milestones and superseded notes are in
> [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md); implementation detail remains available in
> Git. Do not infer the next task from historical V2/V3/V4 names.

## Current State

- **Updated:** 2026-08-30
- **Branch/HEAD:** `fast-track-prompt-to-dungeon` at `397c35d`, one commit ahead of
  `origin/fast-track-prompt-to-dungeon` before the uncommitted slice below.
- **Working tree:** **uncommitted P7-14f objective-dispatch/publication slice** in the
  files listed below. No migration, provider credential, live dispatch, or canonical
  campaign path is partially edited.
- **Current task:** **P7-14f — Staged Tier A authoring and anti-overfitting evaluation.**
- **Task state:** exact-ID objective provider dispatch, bounded repair, accepted-content
  lineage, and atomic DM-only child publication are complete and green. Provider-free
  room-narrative contracts are next.
- **Schema head:** `0008_workbench_defaults`; no migration changed or is pending.
- **Retention gate:** **not crossed.** Active V1 contracts evolve in place; there is no
  retained real-user artifact, external consumer, non-disposable deployment, or promised
  replay requirement.

## Implemented Staged Seam

The objective task now follows the same independently failable boundary as puzzle,
exploration, feature-interaction, and trap enrichment:

- trusted code builds one exact objective context from immutable package geometry, the
  current guide target, bounded stakes/constraints, and selected summaries copied only
  from accepted puzzle/exploration/feature/trap content;
- a distinct task profile exposes only `submit_dungeon_objective`, with a 6,000-token
  cumulative budget, 2,048-output ceiling, and one repair whose complete canonical input
  plus schema is reserved from measured remaining usage;
- schema and semantic checks reject foreign package/room/objective/mechanic IDs and do not
  expose objective rename/kind, structure, geometry, deterministic arithmetic, approval,
  canon, or another task's content;
- accepted output and final model lineage remain in the authorized DM-only child artifact;
  ordinary attempt records retain body-free IDs, hashes, usage, stages, and diagnostics;
- deterministic projection changes only the exact objective, removes only its runnable-
  content blocker, and preserves package/map bytes, objective identity/kind, all accepted
  prior content and lineage, other guide entries, and unrelated blockers; and
- rejection or publication failure leaves the Copper Tide Foundry trap parent current and
  persists no rejected or exception body.

The new integration regression starts from independently accepted Copper Tide puzzle,
exploration, feature, and trap children, then proves objective repair/publication and both
failure paths. It is independent of the Synthetic Constructive Archive review fixture.

## Active Boundaries and Known Issues

- Models propose preparation content only. They cannot alter topology, geometry,
  visibility, deterministic arithmetic/DC policy, preparation approval, or canon.
- Room narrative enrichment, repeated/automatic staged orchestration, Tier B/C, the
  multi-case quality comparison, and a staged live result are not implemented.
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
- `src/dm_assistant/orchestration/dungeons/objective_prompting.py` (new)
- `src/dm_assistant/orchestration/dungeons/objective_application.py` (new)
- `src/dm_assistant/orchestration/dungeons/__init__.py`
- `tests/integration/test_dungeon_objective_prompt.py` (new)

Uncommitted documentation:

- `README.md`
- `dm-assistant-implementation-plan.md`
- `dm-assistant-technical-architecture.md`
- `dungeon-generation-recovery-plan.md`
- `PROJECT_STATUS.md`

Recorded for this slice:

- `uv run pytest -q tests/unit tests/evals` -> **199 passed**.
- `uv run pytest -q packages/dungeon-engine/tests` -> **139 passed**.
- Focused puzzle/exploration/trap/objective integration gate -> **12 passed** against a
  disposable PostgreSQL/pgvector container.
- Focused objective/trap/exploration/puzzle contract gate -> **14 passed**.
- Ruff lint/format and strict mypy over changed dungeon Python sources -> **passed**.
- `git diff --check` -> **passed** after the final handoff rewrite.

Suggested commit subject: `P7-14f add bounded objective dispatch and publication`

## Single Next Recommended Task

**Add a provider-free exact-ID room-narrative context, output, semantic validation, and
deterministic guide projection after accepted mechanics exist.**

**First concrete action:** add failing unit cases in a new
`tests/unit/test_dungeon_room_narrative_enrichment_contract.py` using a materially
different synthetic setting. Prove that a bounded homogeneous input includes only exact
selected room geometry, existing room guide state, tone/constraints, and player-observable
summaries copied from accepted local mechanics. Output may add concise observable
read-aloud and room framing only; it must preserve exact package/room IDs, reject foreign
or duplicate rooms and structural/cross-task fields, and project only into selected room
narratives without changing package/map bytes, accepted mechanics, objective content,
lineage, other guide entries, or unrelated blockers.

Do **not** add narrative provider dispatch, automatic orchestration, live calls, Tier B/C,
a migration, model-authored hidden mechanics, or a universal optional-field generation
context in that provider-free slice.

## Authoritative References

- [`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md), P7-14f
- [`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md),
  “Dungeon Generation Architecture” and “Dungeon Primitives and Model Tools”
- [`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md), R5
- [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md) for compact completed-milestone history
