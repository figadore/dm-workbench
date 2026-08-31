# Project Status and Handoff

> Read this bounded live handoff first. Completed milestones and superseded notes are in
> [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md); implementation detail remains available in
> Git. Do not infer the next task from historical V2/V3/V4 names.

## Current State

- **Updated:** 2026-08-31
- **Branch/HEAD:** `fast-track-prompt-to-dungeon` at `ff3546b`, aligned with
  `origin/fast-track-prompt-to-dungeon`, plus the uncommitted slice below.
- **Working tree:** **uncommitted P7-14f objective creative-continuity propagation**.
  No migration, live provider call, credential, canonical campaign path, preparation
  approval path, repeated/full-chain dispatcher, or pure-package change is partially
  edited.
- **Current task:** **P7-14f — Staged Tier A authoring and anti-overfitting evaluation.**
- **Task state:** structural, puzzle, exploration, feature-interaction, trap, and objective
  artifacts/tasks now share one exact creative-continuity pin. Room-narrative propagation
  plus the final deterministic/cohesion gate remain.
- **Schema head:** `0008_workbench_defaults`; no migration changed or is pending.
- **Retention gate:** **not crossed.** Active V1 contracts evolve in place; there is no
  retained real-user artifact, external consumer, non-disposable deployment, or promised
  replay requirement.

## Implemented Objective Continuity Slice

Trusted Workbench code now:

- adds bounded, unique continuity-fact selections to the objective task policy and requires
  `DungeonEnrichmentContinuityContext` in the strict model-visible objective input;
- rebuilds the persisted structural projection from its exact context/plan before objective
  context construction, then verifies the projection hash, plan, exact package, objective
  room/marker/guide target, authorized facts, exact cited sources, and bounded selected
  accepted-mechanic summaries;
- exposes only objective-local structural intent and explicitly approved fact/source subsets
  alongside the existing bounded accepted puzzle/exploration/feature/trap summaries;
- deterministically rebuilds the complete strict context before projecting accepted content
  into one objective guide entry;
- pins the shared continuity hash in accepted objective lineage, publication validation,
  provider-visible context, prompt/artifact generation-run scope and schema metadata,
  context source links, and artifact validation reports; and
- preserves package/map bytes, prior accepted mechanics and lineage, unrelated guide entries,
  readiness blockers, preparation lifecycle, and canonical campaign state.

Models still propose preparation content only. They cannot change topology, geometry,
visibility, deterministic arithmetic, accepted mechanic content, objective identity/kind,
preparation approval, or canon.

## Tests Added/Extended

- Synthetic grounded Tide Archive coverage proves objective joins puzzle, exploration,
  feature, and trap on one projection version/hash while selecting only its authorized fact,
  exact source, exact objective room intent, and named objective intent.
- Provider-free negative coverage proves objective construction rejects a stale hash or
  unauthorized fact before any provider boundary.
- Objective contract coverage proves local intent, standalone lore `unknown`, strict schema,
  bounded accepted-mechanic summaries, and deterministic projection rebuild.
- Faux-provider PostgreSQL assertions cover provider-visible continuity, accepted-lineage
  pins, prompt/artifact run-scope and schema pins, report pins, and unchanged atomic child/map
  behavior when the integration database is available.

## Active Boundaries and Known Issues

- Creative continuity is not yet present in room-narrative strict inputs and lineages. Do
  not add repeated/full-chain dispatch until it inherits the same pin and the final
  deterministic continuity gate exists.
- Final continuity/source/dependency/lineage/secrecy checks and the bounded,
  non-authoritative whole-dungeon cohesion report are not implemented.
- Broader resumed coordinator coverage, automatic chain repetition, multi-case quality
  comparison, staged live result, Tier B/C, and resumed output/print work remain pending.
- Live provider use remains paused. Pinned `@earendil-works/pi-ai` Codex transport does not
  serialize the requested hard output limit; post-response checks protect publication but
  cannot prevent provider usage. The frozen-canary exception remains operator risk, not
  ordinary rollout permission.
- Package and root pytest suites must run separately because duplicate test module basenames
  cause an import-file-mismatch when collected in one process.
- Disposable-PostgreSQL objective integration was skipped locally because
  `DM_TEST_DATABASE_URL` is unset and Docker is unavailable. The last full integration run
  still has the three previously recorded unrelated failures (metadata drift, embedding-run
  timestamp ordering, and missing source-path history in a direct fixture).
- No provider was contacted. No credential, canonical campaign write, preparation approval,
  migration, redaction system, or second persistence store is present.

## Current Files and Verification

Uncommitted production/tests:

- `src/dm_assistant/orchestration/dungeons/{contracts.py,service.py}`
- `src/dm_assistant/orchestration/dungeons/{objective_application,objective_prompting}.py`
- objective continuity unit/integration tests and staged-planner fixture update

Uncommitted documentation:

- `README.md`
- `dm-assistant-implementation-plan.md`
- `dungeon-generation-recovery-plan.md`
- `PROJECT_STATUS.md`

Recorded for this slice:

- `uv run pytest -q tests/unit tests/evals` -> **209 passed**.
- `uv run pytest -q packages/dungeon-engine/tests` -> **139 passed**.
- `uv run pytest -q -rs tests/integration/test_dungeon_objective_prompt.py` -> **3 skipped**
  (`DM_TEST_DATABASE_URL` unset).
- Strict mypy over changed production and focused unit paths -> **passed**.
- Ruff lint/format over changed Python sources/tests -> **passed**.
- `git diff --check` -> **passed** before the final handoff refresh.

Suggested commit subject: `P7-14f pin creative continuity through objectives`

## Single Next Recommended Task

**Propagate the exact persisted creative-continuity pin through room-narrative context and
lineage before resumed coordinator coverage or chain repetition.**

**First concrete action:** add failing provider-free tests showing the narrative builder
receives the same projection version/hash as its objective parent, exposes only the selected
room intents plus explicitly selected authorized facts/sources and existing player-observable
accepted-mechanic summaries, and rejects a stale hash or unauthorized fact before provider
dispatch. Then add the required continuity selection/sub-contract, lineage/publication pin,
deterministic rebuild check, source links, and compact run metadata on existing surfaces.

Do **not** add repeated/full-chain dispatch, a holistic provider call, live provider use,
Tier B/C, a migration, a queue, model-authored mechanics, preparation approval, or canon
writes.

## Authoritative References

- [`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md), P7-14f
- [`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md),
  “Dungeon Generation Architecture” and “Dungeon Primitives and Model Tools”
- [`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md), R5
- [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md) for compact completed-milestone history
