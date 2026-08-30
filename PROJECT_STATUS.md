# Project Status and Handoff

> Read this bounded live handoff first. Completed milestones and superseded notes are in
> [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md); implementation detail remains available in
> Git. Do not infer the next task from historical V2/V3/V4 names.

## Current State

- **Updated:** 2026-08-30
- **Branch/HEAD:** `fast-track-prompt-to-dungeon` at `a8625ce`, matching
  `origin/fast-track-prompt-to-dungeon` before the uncommitted slice below.
- **Working tree:** **uncommitted P7-14f provider-free room-narrative slice** in the files
  listed below. No migration, provider dispatch, credential, canonical campaign path, or
  preparation approval path is partially edited.
- **Current task:** **P7-14f — Staged Tier A authoring and anti-overfitting evaluation.**
- **Task state:** provider-free exact-ID room-narrative context, output, semantic
  validation, and deterministic guide projection are complete and green. Independently
  bounded faux-provider dispatch/publication is next.
- **Schema head:** `0008_workbench_defaults`; no migration changed or is pending.
- **Retention gate:** **not crossed.** Active V1 contracts evolve in place; there is no
  retained real-user artifact, external consumer, non-disposable deployment, or promised
  replay requirement.

## Implemented Provider-Free Narrative Seam

The homogeneous room-narrative task now has a strict boundary after accepted mechanics:

- trusted code selects 1–8 exact rooms and exposes only their exact local geometry,
  bounded existing room guide state, tone/constraints, and player-observable
  summaries copied from complete accepted local puzzle, exploration, feature, trap, and
  objective content;
- hidden adjudication, puzzle solutions, trap trigger/effect/counterplay, mechanic
  outcomes, plan topology, preparation notes, and approval/canon state do not enter the
  narrative context;
- strict output contains only the package ID and one concise read-aloud plus 2–4
  observable framing details for each exact selected room;
- schema and semantic checks reject structural/cross-task fields, duplicate rooms,
  foreign package/room IDs, and omitted selected rooms; and
- deterministic projection refuses to replace accepted narrative content, rechecks the
  context against the immutable package/current guide and plan topology, fills only the
  selected blank room narratives, and removes only their exact room-content blockers.
  Package/map bytes, all accepted mechanics and objectives, other guide entries, and
  unrelated blockers remain unchanged.

The new Moonseed Aviary regression is materially independent of the Synthetic
Constructive Archive and the Copper Tide/Skyroot staged fixtures. It proves observable-
only context slicing across trap, exploration, feature, and objective content; bounded
schemas; exact-set rejection; projection isolation; blocker isolation; stale-context
rejection; and no replacement of accepted narrative prose.

## Active Boundaries and Known Issues

- Models propose preparation content only. They cannot alter topology, geometry,
  visibility, deterministic arithmetic/DC policy, preparation approval, or canon.
- Narrative provider dispatch/publication, repeated or automatic staged orchestration,
  Tier B/C, the multi-case quality comparison, and a staged live result are not
  implemented.
- Live provider use remains paused. Pinned `@earendil-works/pi-ai` Codex transport does
  not serialize the requested hard output limit; post-response checks protect publication
  but cannot prevent provider usage. The acknowledged frozen-canary exception remains
  operator risk, not ordinary rollout permission.
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
- `tests/unit/test_dungeon_room_narrative_enrichment_contract.py` (new)

Uncommitted documentation:

- `README.md`
- `dm-assistant-implementation-plan.md`
- `dm-assistant-technical-architecture.md`
- `dungeon-generation-recovery-plan.md`
- `PROJECT_STATUS.md`

Recorded for this slice:

- Initial focused test -> expected import failure before implementation.
- Focused room-narrative contract gate -> **4 passed**.
- `uv run pytest -q tests/unit tests/evals` -> **203 passed**.
- `uv run pytest -q packages/dungeon-engine/tests` -> **139 passed**.
- Ruff lint/format over changed Python sources -> **passed**.
- Strict mypy over changed dungeon contracts/service -> **passed**.
- `git diff --check` -> **passed** after the final handoff update.

Suggested commit subject: `P7-14f add provider-free room narrative enrichment`

## Single Next Recommended Task

**Add independently pinned faux-provider room-narrative dispatch, bounded repair,
accepted-content lineage, and atomic DM-only child publication over the current objective
child.**

**First concrete action:** add a failing
`tests/integration/test_dungeon_room_narrative_prompt.py` that starts from independently
accepted puzzle, exploration, feature, trap, and objective content. Prove exact-set tool
submission, a task-specific 6,000-token cumulative/2,048-output budget, one repair whose
complete canonical input/schema is reserved, accepted output/lineage in one DM-only child,
byte-identical package/map assets, and rejection/publication-failure paths that leave the
objective parent current with body-free diagnostics.

Do **not** add automatic orchestration, live calls, Tier B/C, a migration, model-authored
mechanics, preparation approval, or a universal optional-field generation context in that
slice.

## Authoritative References

- [`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md), P7-14f
- [`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md),
  “Dungeon Generation Architecture” and “Dungeon Primitives and Model Tools”
- [`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md), R5
- [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md) for compact completed-milestone history
