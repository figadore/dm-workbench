# Project Status and Handoff

> Read this bounded live handoff first. Completed milestones and superseded notes are in
> [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md); implementation detail remains available in
> Git. Do not infer the next task from historical V2/V3/V4 names.

## Current State

- **Updated:** 2026-08-31
- **Branch/HEAD:** `fast-track-prompt-to-dungeon` at `9a3d87f`, two commits ahead of
  `origin/fast-track-prompt-to-dungeon`, plus the uncommitted slice below.
- **Working tree:** **uncommitted P7-14f final deterministic staged-dungeon gate and
  read-only cohesion-report contracts**. No migration, live provider call, credential,
  canonical campaign path, preparation approval enforcement, repeated/full-chain
  dispatcher, or pure-package change is partially edited.
- **Current task:** **P7-14f — Staged Tier A authoring and anti-overfitting evaluation.**
- **Task state:** the pure final gate and strict report shape now exist. They are not yet
  enforced by prompted preparation approval/readiness or written into the DM review packet;
  no holistic provider call or DM disposition workflow exists.
- **Schema head:** `0008_workbench_defaults`; no migration changed or is pending.
- **Retention gate:** **not crossed.** Active V1 contracts evolve in place; there is no
  retained real-user artifact, external consumer, non-disposable deployment, or promised
  replay requirement.

## Implemented Final-Gate Slice

Trusted Workbench code now:

- exposes `validate_final_staged_dungeon()` as a pure provider-free function over one
  immutable `DungeonStudioSpecification`;
- rebuilds the accepted structural plan/context and exact creative-continuity projection,
  validates structural context pin/source inheritance, and compares the persisted
  projection;
- evolves accepted puzzle/exploration/feature/trap/objective/narrative lineage in place to
  retain the continuity version/hash plus exact selected fact and cited source IDs;
- recomputes topology/geometry and exact gate/dependency projection, current preparation
  readiness, complete staged slot/content/successful-lineage coverage, typed cross-task
  references, and player SVG secrecy;
- returns seven stable check families with bounded code/ID-only diagnostics and no prompt,
  guide, provider, or campaign body;
- defines a separate six-dimension `DungeonCohesionReviewReport` contract with bounded
  findings, exact evidence IDs, and only targeted existing-seam recommendations; and
- gives that report no content-edit, blocker-clearing, preparation-approval, persistence,
  provider, or canonical operation.

The gate does not mutate or persist the artifact and does not approve preparation. The
cohesion report is a contract only; no model has been called and no report can self-approve.

## Tests Added/Extended

A grounded synthetic glasshouse fixture now exercises all staged task kinds plus a real
certified gate/dependency. Provider-free coverage proves:

- one fully enriched specification passes all seven final checks without mutation;
- every enrichment lineage carries the exact authorized fact/source inheritance;
- stale package/dependency projection, readiness, continuity lineage, and source lineage
  fail closed with bounded body-free diagnostics;
- a malformed protected trap marker exposed to the player renderer is detected even when
  its in-memory package classification is relabelled; and
- the cohesion report requires all six dimensions and rejects approval/edit fields.

## Active Boundaries and Known Issues

- Prompted `DungeonStudioService.approve()` still checks only legacy preparation readiness.
  It must invoke the final gate for staged prompted artifacts and fail closed before the
  lifecycle transition. Provider-independent manually authored Studio artifacts must retain
  their existing approval path rather than being forced to fabricate model lineage.
- The development review packet still predates the six-dimension cohesion report and does
  not record deterministic-gate evidence or explicit DM disposition.
- Broader resumed feature/trap/objective/narrative coordinator coverage, automatic chain
  repetition, multi-case quality comparison, staged live result, Tier B/C, and resumed
  output/print work remain pending.
- Live provider use remains paused. Pinned `@earendil-works/pi-ai` Codex transport does not
  serialize the requested hard output limit; post-response checks protect publication but
  cannot prevent provider usage. The frozen-canary exception remains operator risk, not
  ordinary rollout permission.
- Package and root pytest suites must run separately because duplicate test module basenames
  cause an import-file-mismatch when collected in one process.
- Disposable-PostgreSQL enrichment integration is skipped locally because
  `DM_TEST_DATABASE_URL` is unset and Docker is unavailable.
- A repository-wide Ruff/format run still reports unrelated pre-existing Library/import and
  formatting drift outside this slice; focused lint/format over every changed Python file
  passes.
- No provider was contacted. No credential, canonical campaign write, preparation approval,
  migration, redaction system, or second persistence store is present.

## Current Files and Verification

Uncommitted production/tests:

- `src/dm_assistant/orchestration/dungeons/final_validation.py`
- dungeon exports/contracts and all six enrichment prompting modules
- `tests/unit/test_dungeon_staged_enrichment_plan.py`

Uncommitted documentation:

- `README.md`
- `dm-assistant-{implementation-plan,technical-architecture}.md`
- `dungeon-generation-recovery-plan.md`
- `PROJECT_HISTORY.md`
- `PROJECT_STATUS.md`

Recorded for this slice:

- `uv run pytest -q tests/unit tests/evals` -> **213 passed**.
- `uv run pytest -q packages/dungeon-engine/tests` -> **139 passed**.
- focused final-gate/continuity/enrichment contract tests -> **28 passed**.
- focused PostgreSQL enrichment suites -> **15 skipped** (`DM_TEST_DATABASE_URL` unset).
- strict mypy over every changed production Python file and focused tests -> **passed**.
- Ruff lint/format over every changed Python file -> **passed**.
- `git diff --check` -> **passed** before this handoff refresh.

Suggested commit subject: `P7-14f add final staged-dungeon continuity gate`

## Single Next Recommended Task

**Enforce the final deterministic gate at the prompted preparation approval boundary and
surface its evidence in the DM review packet before resumed coordination or repetition.**

**First concrete action:** add failing provider-free service tests proving a fully enriched
prompted artifact cannot transition to `approved_for_play` when any final-gate check fails,
while an existing model-independent manually authored artifact keeps its current readiness-
based approval path. Then persist/render only the final result's body-free hash/check
summary and require explicit DM disposition of all six cohesion dimensions; do not let a
report clear deterministic blockers.

Do **not** add repeated/full-chain dispatch, a live/holistic provider call, Tier B/C, a
migration, queue, model-authored mechanics, automatic preparation approval, or canon writes.

## Authoritative References

- [`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md), P7-14f
- [`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md),
  “Dungeon Generation Architecture” and “Dungeon Primitives and Model Tools”
- [`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md), R5
- [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md) for compact completed-milestone history
