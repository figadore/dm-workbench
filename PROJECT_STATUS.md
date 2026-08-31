# Project Status and Handoff

> Read this bounded live handoff first. Completed milestones and superseded notes are in
> [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md); implementation detail remains available in
> Git. Do not infer the next task from historical V2/V3/V4 names.

## Current State

- **Updated:** 2026-08-31
- **Branch/HEAD:** `fast-track-prompt-to-dungeon` at `468c162`, one commit ahead of
  `origin/fast-track-prompt-to-dungeon`, plus the uncommitted slice below.
- **Working tree:** **uncommitted P7-14f creative-continuity foundation and puzzle/
  exploration propagation**. No migration, live provider call, credential, canonical
  campaign path, preparation approval path, repeated/full-chain dispatcher, or pure-package
  change is partially edited.
- **Current task:** **P7-14f — Staged Tier A authoring and anti-overfitting evaluation.**
- **Task state:** one bounded dungeon-only creative foundation is now derived and persisted;
  puzzle and exploration contexts/lineages inherit it. Propagation to feature, trap,
  objective, and narrative tasks plus the final deterministic/cohesion gate remains.
- **Schema head:** `0008_workbench_defaults`; no migration changed or is pending.
- **Retention gate:** **not crossed.** Active V1 contracts evolve in place; there is no
  retained real-user artifact, external consumer, non-disposable deployment, or promised
  replay requirement.

## Implemented Creative-Continuity Slice

Trusted Workbench code now:

- extends the narrow `DungeonGenerationContext` with explicit grounding mode, tones,
  motif-variation constraints, and bounded cited facts while rejecting facts in standalone
  mode;
- records per-source/fact visibility and fails closed on mismatched visibility,
  unauthorized/stale citations, incomplete grounding pins, or standalone source leakage;
- derives one deterministic `DungeonCreativeContinuityProjection` from the exact resolved
  envelope and accepted `DungeonPlan`, including premise/themes, room purposes,
  critical-path/branch/loop/gate intent, objectives, selected facts, tone, motifs, and
  source lineage;
- self-hashes that projection over its complete hash-excluded document and pins source
  envelope/payload plus structural-plan hashes;
- persists the structural context and projection in the DM-only dungeon specification and
  records compact version/hash metadata in the structural generation run;
- requires puzzle and exploration builders to verify the projection against the exact plan
  and package, then expose only relevant room intent and explicitly approved fact/source
  subsets while carrying one shared projection version/hash; and
- pins the same hash in puzzle/exploration accepted lineage, task context pins, generation-
  run scope/report metadata, provider-visible strict context, and atomic child specs.

Standalone prompt-to-dungeon generation remains ungrounded and reports campaign lore as
`unknown`; it does not infer campaign facts from the campaign ID or source corpus.

## Tests Added/Extended

- New synthetic Tide Archive contract tests prove puzzle and exploration contexts inherit
  one hash while receiving different authorized fact/source subsets and excluding an
  unrelated faction fact.
- Negative tests cover stale projection hashes, unauthorized fact IDs, broader-visibility
  sources, source leakage into standalone mode, and direct standalone-fact construction.
- Puzzle/exploration unit contracts now require continuity and deterministic projection
  rebuilds verify it against the accepted plan/package.
- Disposable-PostgreSQL prompt tests prove structural projection persistence, prompt hash
  inheritance, accepted-lineage pins, run-scope pins, and unchanged atomic child behavior.

## Active Boundaries and Known Issues

- Models propose preparation content only. They cannot alter topology, geometry,
  visibility, deterministic arithmetic/DC policy, preparation approval, or canon.
- Creative continuity is not yet present in feature, trap, objective, or room-narrative
  strict inputs/lineages. Do not add repeated/full-chain dispatch until all required tasks
  inherit the same pin and the final deterministic continuity gate exists.
- Final deterministic continuity/source/dependency/lineage/secrecy checks and the bounded
  non-authoritative whole-dungeon cohesion report are not implemented.
- Automatic chain repetition, broader resumed coordinator coverage, multi-case quality
  comparison, staged live result, Tier B/C, and resumed output/print work remain pending.
- Live provider use remains paused. Pinned `@earendil-works/pi-ai` Codex transport does not
  serialize the requested hard output limit; post-response checks protect publication but
  cannot prevent provider usage. The frozen-canary exception remains operator risk, not
  ordinary rollout permission.
- Package and root pytest suites must run separately because duplicate test module
  basenames cause an import-file-mismatch when collected in one process.
- The full disposable-PostgreSQL integration run has three unrelated existing failures:
  Alembic/SQLAlchemy reports 18 metadata differences; one embedding-run fixture can write
  `finished_at` just before its database-authored `started_at`; and one direct document
  revision fixture omits required source-path history. The remaining 62 tests pass.
- No provider was contacted. No credential, canonical campaign write, preparation
  approval, migration, redaction system, or second persistence store is present.

## Current Files and Verification

Uncommitted implementation/tests include:

- `src/dm_assistant/modules/preparation/{contracts.py,__init__.py}`
- `src/dm_assistant/orchestration/dungeons/{continuity.py,contracts.py,service.py}`
- dungeon exports plus structural/puzzle/exploration prompting modules
- continuity, preparation, puzzle, exploration, planner, and focused integration tests

Uncommitted documentation:

- `README.md`
- `dm-assistant-implementation-plan.md`
- `dungeon-generation-recovery-plan.md`
- `PROJECT_STATUS.md`

Recorded for this slice:

- `uv run pytest -q tests/unit tests/evals` -> **209 passed**.
- `uv run pytest -q packages/dungeon-engine/tests` -> **139 passed**.
- Focused disposable-PostgreSQL puzzle/exploration/coordinator gate -> **10 passed**.
- Full disposable-PostgreSQL integration suite -> **62 passed, 3 unrelated failures**
  described above.
- Strict mypy over changed production continuity paths and new/updated core tests ->
  **passed**.
- Ruff lint/format over changed Python sources/tests -> **passed**.
- `git diff --check` -> **passed**.

Suggested commit subject: `P7-14f pin creative continuity through puzzle and exploration`

## Single Next Recommended Task

**Propagate the exact persisted creative-continuity pin through feature-interaction and trap
contexts/lineages before adding resumed coordinator coverage.**

**First concrete action:** add failing provider-free tests showing feature and trap builders
receive the same projection version/hash as their puzzle/exploration parent, expose only
their exact room/marker intent plus explicitly selected authorized facts/sources, and reject
a stale hash or unauthorized fact before provider dispatch. Then add required continuity
sub-contracts, lineage pins, deterministic rebuild checks, and compact run metadata using
the existing artifact/run surfaces.

Do **not** add automatic chain repetition, a holistic provider call, live provider use,
Tier B/C, a migration, a queue, model-authored mechanics, preparation approval, or canon
writes in that slice.

## Authoritative References

- [`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md), P7-14f
- [`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md),
  “Dungeon Generation Architecture” and “Dungeon Primitives and Model Tools”
- [`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md), R5
- [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md) for compact completed-milestone history
