# Project Status and Handoff

> Read this bounded live handoff first. Completed milestones and superseded notes are in
> [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md); implementation detail remains available in
> Git. Do not infer the next task from historical V2/V3/V4 names.

## Current State

- **Updated:** 2026-08-31
- **Branch/HEAD:** `fast-track-prompt-to-dungeon` at `b499180`, two commits ahead of
  `origin/fast-track-prompt-to-dungeon`, plus the uncommitted slice below.
- **Working tree:** **uncommitted P7-14f feature-interaction/trap creative-continuity
  propagation**. No migration, live provider call, credential, canonical campaign path,
  preparation approval path, repeated/full-chain dispatcher, or pure-package change is
  partially edited.
- **Current task:** **P7-14f — Staged Tier A authoring and anti-overfitting evaluation.**
- **Task state:** structural, puzzle, exploration, feature-interaction, and trap artifacts/
  tasks now share one exact creative-continuity pin. Objective and room-narrative
  propagation plus the final deterministic/cohesion gate remain.
- **Schema head:** `0008_workbench_defaults`; no migration changed or is pending.
- **Retention gate:** **not crossed.** Active V1 contracts evolve in place; there is no
  retained real-user artifact, external consumer, non-disposable deployment, or promised
  replay requirement.

## Implemented Feature/Trap Continuity Slice

Trusted Workbench code now:

- adds bounded, unique continuity-fact selections to feature-interaction and trap policy
  contracts and includes a required strict `DungeonEnrichmentContinuityContext` in each
  model-visible input;
- rebuilds the persisted structural projection from its exact context/plan before feature
  or trap context construction, then verifies the projection hash, plan, exact package,
  selected room, marker/guide target, authorized facts, and exact cited sources;
- exposes only the selected room intent and explicitly approved fact/source subset while
  preserving feature-local interaction fields and trap-local marker/code-owned DC fields;
- deterministically rebuilds each complete strict context before projecting accepted
  content into one feature or trap guide entry;
- pins the shared continuity hash in feature/trap accepted lineage, publication validators,
  provider-visible context, generation-run scope/schema/report metadata, context source
  links, and atomic child specifications; and
- continues to leave standalone campaign lore `unknown` without inferred facts or sources.

Models still propose preparation content only. They cannot change topology, geometry,
visibility, deterministic arithmetic/DC policy, another task's accepted content,
preparation approval, or canon.

## Tests Added/Extended

- Synthetic grounded Tide Archive coverage proves puzzle, exploration, feature, and trap
  contexts share one projection version/hash while selecting different authorized facts/
  sources, exact room intent, and no unrelated faction fact.
- Negative provider-free coverage proves feature/trap construction rejects a stale hash or
  unauthorized fact before any provider boundary.
- Feature/trap unit contracts now require continuity; deterministic projection tests rebuild
  it against the accepted plan/package/guide.
- Disposable-PostgreSQL faux-provider tests prove prompt hash inheritance, accepted-lineage
  pins, run-scope/schema/report pins, and unchanged atomic child/map behavior.

## Active Boundaries and Known Issues

- Creative continuity is not yet present in objective or room-narrative strict inputs and
  lineages. Do not add repeated/full-chain dispatch until both inherit the same pin and the
  final deterministic continuity gate exists.
- Final continuity/source/dependency/lineage/secrecy checks and the bounded,
  non-authoritative whole-dungeon cohesion report are not implemented.
- Broader resumed coordinator coverage, automatic chain repetition, multi-case quality
  comparison, staged live result, Tier B/C, and resumed output/print work remain pending.
- Live provider use remains paused. Pinned `@earendil-works/pi-ai` Codex transport does not
  serialize the requested hard output limit; post-response checks protect publication but
  cannot prevent provider usage. The frozen-canary exception remains operator risk, not
  ordinary rollout permission.
- Package and root pytest suites must run separately because duplicate test module
  basenames cause an import-file-mismatch when collected in one process.
- The last full disposable-PostgreSQL integration run had three unrelated existing
  failures: Alembic/SQLAlchemy reported 18 metadata differences; one embedding-run fixture
  could write `finished_at` just before its database-authored `started_at`; and one direct
  document-revision fixture omitted required source-path history. It was not rerun here.
- No provider was contacted. No credential, canonical campaign write, preparation
  approval, migration, redaction system, or second persistence store is present.

## Current Files and Verification

Uncommitted implementation/tests:

- `src/dm_assistant/orchestration/dungeons/{contracts.py,service.py}`
- `src/dm_assistant/orchestration/dungeons/{feature_interaction,trap}_prompting.py`
- feature/trap continuity unit and integration tests plus staged-planner fixture updates

Uncommitted documentation:

- `README.md`
- `dm-assistant-implementation-plan.md`
- `dungeon-generation-recovery-plan.md`
- `PROJECT_STATUS.md`

Recorded for this slice:

- `uv run pytest -q tests/unit tests/evals` -> **209 passed**.
- `uv run pytest -q packages/dungeon-engine/tests` -> **139 passed**.
- Disposable-PostgreSQL feature/trap prompt gate -> **7 passed**.
- Strict mypy over changed production and focused unit paths -> **passed**.
- Ruff lint/format over changed Python sources/tests -> **passed**.
- `git diff --check` -> **passed** after the handoff update.

Suggested commit subject: `P7-14f pin creative continuity through feature and trap`

## Single Next Recommended Task

**Propagate the exact persisted creative-continuity pin through the objective context and
lineage before room-narrative or resumed coordinator coverage.**

**First concrete action:** add failing provider-free tests showing the objective builder
receives the same projection version/hash as its trap parent, exposes only the objective
room intent plus explicitly selected authorized facts/sources and bounded accepted-mechanic
summaries, and rejects a stale hash or unauthorized fact before provider dispatch. Then add
the required continuity sub-contract, lineage/publication pin, deterministic rebuild check,
and compact run metadata on the existing artifact/run surfaces.

Do **not** add room-narrative propagation in that slice, automatic chain repetition, a
holistic provider call, live provider use, Tier B/C, a migration, a queue, model-authored
mechanics, preparation approval, or canon writes.

## Authoritative References

- [`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md), P7-14f
- [`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md),
  “Dungeon Generation Architecture” and “Dungeon Primitives and Model Tools”
- [`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md), R5
- [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md) for compact completed-milestone history
