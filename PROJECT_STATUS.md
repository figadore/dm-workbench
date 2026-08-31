# Project Status and Handoff

> Read this bounded live handoff first. Completed milestones and superseded notes are in
> [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md); implementation detail remains available in
> Git. Do not infer the next task from historical V2/V3/V4 names.

## Current State

- **Updated:** 2026-08-31
- **Branch/HEAD:** `fast-track-prompt-to-dungeon` at `b9f9371`, one commit ahead of
  `origin/fast-track-prompt-to-dungeon`, plus the uncommitted slice below.
- **Working tree:** **uncommitted P7-14f room-narrative creative-continuity
  propagation**. No migration, live provider call, credential, canonical campaign path,
  preparation approval path, repeated/full-chain dispatcher, final continuity gate, or
  pure-package change is partially edited.
- **Current task:** **P7-14f — Staged Tier A authoring and anti-overfitting evaluation.**
- **Task state:** structural and every staged enrichment artifact/task now share one exact
  creative-continuity pin. The final deterministic continuity/readiness gate and bounded
  non-authoritative cohesion report remain before repeated orchestration or live use.
- **Schema head:** `0008_workbench_defaults`; no migration changed or is pending.
- **Retention gate:** **not crossed.** Active V1 contracts evolve in place; there is no
  retained real-user artifact, external consumer, non-disposable deployment, or promised
  replay requirement.

## Implemented Room-Narrative Continuity Slice

Trusted Workbench code now:

- adds bounded, unique continuity-fact selections to room-narrative policy and requires
  `DungeonEnrichmentContinuityContext` in the strict model-visible input;
- rebuilds the persisted structural projection from its exact context/plan before narrative
  context construction, then verifies the projection hash, exact package, selected rooms,
  authorized facts, and exact cited sources;
- exposes only selected room intents and approved fact/source subsets alongside existing
  player-observable local puzzle/exploration/feature/trap/objective summaries;
- deterministically rebuilds the complete strict context before projecting accepted prose
  into only the selected blank room narratives;
- pins the shared continuity hash in accepted narrative lineage, publication validation,
  provider-visible context, prompt/artifact run scope and schema metadata, context source
  links, and artifact validation reports; and
- preserves package/map bytes, every accepted mechanic/objective and lineage, unselected
  room state, unrelated readiness blockers, preparation lifecycle, and canonical state.

Models still propose preparation prose only. They cannot change topology, geometry,
visibility, deterministic arithmetic, accepted mechanics/objectives, preparation approval,
or canon.

## Tests Added/Extended

- Grounded synthetic Moonseed coverage proves narrative and objective contexts share one
  version/hash while narrative receives only selected room intents, its authorized fact and
  exact source, and player-observable accepted-mechanic summaries.
- Provider-free negatives prove narrative construction rejects a stale hash or unauthorized
  fact before any provider boundary and requires unique fact selections.
- Projection coverage proves deterministic continuity rebuild while preserving package,
  prior guide state, unselected rooms, and unrelated blockers.
- Faux-provider PostgreSQL assertions cover provider-visible continuity, objective-to-
  narrative hash inheritance, accepted-lineage pins, prompt/artifact run metadata, report
  pins, source links, and unchanged atomic child/map behavior when a database is available.

## Active Boundaries and Known Issues

- Final continuity/source/dependency/lineage/secrecy checks and the bounded,
  non-authoritative whole-dungeon cohesion report are not implemented. Do not add repeated/
  full-chain dispatch until that gate exists.
- Broader resumed feature/trap/objective/narrative coordinator coverage, automatic chain
  repetition, multi-case quality comparison, staged live result, Tier B/C, and resumed
  output/print work remain pending.
- Live provider use remains paused. Pinned `@earendil-works/pi-ai` Codex transport does not
  serialize the requested hard output limit; post-response checks protect publication but
  cannot prevent provider usage. The frozen-canary exception remains operator risk, not
  ordinary rollout permission.
- Package and root pytest suites must run separately because duplicate test module basenames
  cause an import-file-mismatch when collected in one process.
- Disposable-PostgreSQL narrative integration was skipped locally because
  `DM_TEST_DATABASE_URL` is unset and Docker is unavailable. The last full integration run
  still has three unrelated failures (metadata drift, embedding-run timestamp ordering,
  and missing source-path history in a direct fixture).
- No provider was contacted. No credential, canonical campaign write, preparation approval,
  migration, redaction system, or second persistence store is present.

## Current Files and Verification

Uncommitted production/tests:

- `src/dm_assistant/orchestration/dungeons/{contracts.py,service.py}`
- `src/dm_assistant/orchestration/dungeons/{room_narrative_application,room_narrative_prompting}.py`
- room-narrative continuity unit/integration tests and staged-planner fixture update

Uncommitted documentation:

- `README.md`
- `dm-assistant-implementation-plan.md`
- `dungeon-generation-recovery-plan.md`
- `PROJECT_HISTORY.md`
- `PROJECT_STATUS.md`

Recorded for this slice:

- `uv run pytest -q tests/unit tests/evals` -> **209 passed**.
- `uv run pytest -q packages/dungeon-engine/tests` -> **139 passed**.
- `uv run pytest -q -rs tests/integration/test_dungeon_room_narrative_prompt.py` ->
  **3 skipped** (`DM_TEST_DATABASE_URL` unset).
- Strict mypy over changed production and focused unit paths -> **passed**.
- Ruff lint/format over changed Python sources/tests -> **passed**.
- `git diff --check` -> **passed** before the final handoff refresh.

Suggested commit subject: `P7-14f pin creative continuity through room narratives`

## Single Next Recommended Task

**Add the final deterministic staged-dungeon continuity/readiness gate before resumed
coordinator coverage or chain repetition.**

**First concrete action:** add failing provider-free tests over a fully enriched synthetic
specification that recompute and require one structural/enrichment continuity hash, exact
authorized-source inheritance, exact slot/dependency and successful-lineage coverage,
required content, typed cross-task consistency, and player-secrecy cleanliness. Then expose
bounded body-free diagnostics plus a separate read-only cohesion-report contract that cannot
edit content, clear blockers, approve preparation, or write canon.

Do **not** add repeated/full-chain dispatch, a live/holistic provider call, Tier B/C, a
migration, queue, model-authored mechanics, preparation approval, or canon writes.

## Authoritative References

- [`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md), P7-14f
- [`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md),
  “Dungeon Generation Architecture” and “Dungeon Primitives and Model Tools”
- [`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md), R5
- [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md) for compact completed-milestone history
