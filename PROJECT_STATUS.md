# Project Status and Handoff

> Read this bounded live handoff first. Completed milestones and superseded notes are in
> [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md); implementation detail remains available in
> Git. Do not infer the next task from historical V2/V3/V4 names.

## Current State

- **Updated:** 2026-08-31
- **Branch/HEAD:** `fast-track-prompt-to-dungeon` at `4a4e0a2`, synchronized with
  `origin/fast-track-prompt-to-dungeon`, plus the uncommitted slice below.
- **Working tree:** **uncommitted P7-14f resumed exploration coordinator regression**.
  No migration, live provider call, credential, canonical campaign path, preparation
  approval path, repeated/full-chain dispatcher, or pure-package change is partially
  edited.
- **Current task:** **P7-14f — Staged Tier A authoring and anti-overfitting evaluation.**
- **Task state:** one-step coordination is covered through accepted puzzle and resumed
  exploration children. The newly explicit creative-continuity/final-cohesion boundary is
  the next slice before broader resumed coordination or any repeated runner.
- **Schema head:** `0008_workbench_defaults`; no migration changed or is pending.
- **Retention gate:** **not crossed.** Active V1 contracts evolve in place; there is no
  retained real-user artifact, external consumer, non-disposable deployment, or promised
  replay requirement.

## Implemented Resumed Exploration Slice

`DungeonStagedEnrichmentCoordinator` now exercises a resumed exploration task without
introducing chain repetition:

- `DungeonStagedExplorationPolicy` carries the exact planner-selected encounter-slot ID
  separately from its room-local affordance/pacing/stakes selection;
- coordinator target checks compare task kind, room ID, and encounter-slot ID before the
  exploration application seam can construct context or call a provider;
- an accepted faux-provider exploration publishes exactly one atomic DM-only child and
  replans that current child to the expected exact feature-interaction target;
- a mismatched slot raises a conflict before any provider call, attempt run, or artifact
  version write and leaves the accepted puzzle parent current; and
- stored JSONB specifications are decoded through strict model JSON validation, matching
  the existing Dungeon Studio load boundary instead of incorrectly treating JSON strings
  as already-instantiated enum/UUID objects.

The synthetic Cobalt Orrery regression now includes one room-local exploration affordance.
Success proves structural -> puzzle -> exploration parent/child lineage, one call for the
resumed step, exact exploration lineage, and feature replanning. The mismatch sibling
proves zero provider calls and no third version.

## Planned Creative Continuity and Final Cohesion Gate

Before broader coordination, chain repetition, or live Tier A, the plan now requires:

- one bounded dungeon-only continuity projection derived from the resolved
  `DungeonGenerationContext` and accepted structural plan;
- pinned version/hash/source lineage across every strict enrichment context, with only
  relevant authorized facts, accepted intent, and bounded prior-task summaries exposed;
- standalone lore remaining unknown unless campaign grounding is explicitly selected;
- deterministic final checks for continuity/source inheritance, dependencies, required
  content, lineage, secrecy, and typed cross-task consistency; and
- a DM-facing whole-dungeon rubric covering thematic reinforcement, history/environment
  causality, mechanic/objective unity, progression, motif variation, and selected-lore
  consistency. A bounded reviewer may diagnose only; it cannot edit, approve, or write
  canon, and fixes target one exact enrichment seam.

This is planning/documentation only in the current uncommitted slice; no continuity
contract, context propagation, reviewer, or final report is implemented yet.

## Active Boundaries and Known Issues

- Models propose preparation content only. They cannot alter topology, geometry,
  visibility, deterministic arithmetic/DC policy, preparation approval, or canon.
- Creative-continuity propagation/final cohesion reporting, automatic/repeated full-chain
  orchestration, resumed feature/trap/objective/narrative coordinator coverage, the
  multi-case quality comparison, staged live result, Tier B/C, and resumed output/print
  work are not implemented.
- Live provider use remains paused. Pinned `@earendil-works/pi-ai` Codex transport does
  not serialize the requested hard output limit; post-response checks protect publication
  but cannot prevent provider usage. The frozen-canary exception remains operator risk,
  not ordinary rollout permission.
- Narrative dispatch can cover only rooms whose required local mechanics are accepted;
  rooms sharing an incomplete mechanic remain readiness-blocked until it is accepted.
- Package and root pytest suites must run separately because duplicate test module
  basenames cause an import-file-mismatch when collected in one process.
- The full disposable-PostgreSQL integration run has three unrelated existing failures:
  Alembic/SQLAlchemy reports 18 metadata differences; one embedding-run fixture can write
  `finished_at` just before its database-authored `started_at`; and one direct document
  revision fixture omits required source-path history. The remaining 62 tests pass.
- No provider was contacted. No credential, canonical campaign write, preparation
  approval, migration, redaction system, or second persistence store is present.

## Current Files and Verification

Uncommitted implementation:

- `src/dm_assistant/orchestration/dungeons/staged_enrichment_coordinator.py`
- `tests/integration/test_dungeon_staged_enrichment_coordinator.py`

Uncommitted documentation:

- `README.md`
- `dm-assistant-implementation-plan.md`
- `dm-assistant-technical-architecture.md`
- `dungeon-generation-recovery-plan.md`
- `PROJECT_STATUS.md`

Recorded for this slice:

- Disposable-PostgreSQL focused coordinator gate -> **4 passed**.
- Full disposable-PostgreSQL integration suite -> **62 passed, 3 unrelated failures**
  described above.
- `uv run pytest -q tests/unit tests/evals` -> **206 passed**.
- `uv run pytest -q packages/dungeon-engine/tests` -> **139 passed**.
- Ruff lint/format over changed Python sources and integration test -> **passed**.
- Strict mypy over coordinator and its integration test -> **passed**.
- `git diff --check` -> **passed**.

Suggested commit subject: `P7-14f cover resumed exploration and plan cohesion gate`

## Single Next Recommended Task

**Define the provider-free dungeon creative-continuity contract and projection before
extending resumed feature coordination or adding any repeated/full-chain runner.**

**First concrete action:** add failing contract tests that derive one bounded continuity
projection from a synthetic `GenerationContextEnvelope<DungeonGenerationContext>` plus an
accepted structural plan, then prove puzzle and exploration context builders carry the
same version/hash while exposing only relevant authorized fields. Include negative cases
for stale hashes, broader-visibility sources, and ungrounded standalone lore.

Keep this a dungeon-specific required sub-contract inside strict task payloads—not a
universal optional-field generation context or corpus dump. Do **not** add a holistic
provider call, automatic chain repetition, live provider use, Tier B/C, a migration, a
queue, model-authored mechanics, preparation approval, or canon writes in that slice.

## Authoritative References

- [`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md), P7-14f
- [`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md),
  “Dungeon Generation Architecture” and “Dungeon Primitives and Model Tools”
- [`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md), R5
- [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md) for compact completed-milestone history
