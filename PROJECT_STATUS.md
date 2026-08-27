# Project Status and Handoff

> Read this file first. Historical milestones and superseded handoffs belong in
> [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md). Do not infer the next task from old
> V2/V3/V4 names in Git history or implementation-plan history.

## Current Snapshot

- **Last updated:** 2026-08-21
- **Branch:** `fast-track-prompt-to-dungeon`; `cc02441` was equal to origin before
  this working-tree task.
- **Current task:** **P7-14d — Constructive Tier A geometry.**
- **Task state:** **complete in the working tree; not committed.**
- **Schema head:** `0008_workbench_defaults`; no migration changed.
- **Live providers:** no call was made. Keep live canaries paused until the P7-14
  provider-free and faux-provider gates pass.

## Active Direction

P7-13 feature/polish work remains paused. The active recovery is defined by
[`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md):

```text
one submit_dungeon_plan V1 model call
    -> deterministic critical-path/branch/loop topology compiler
    -> independently checked TopologyCertificate
    -> certificate-driven constructive orthogonal layout
    -> independent geometry/secrecy validation
    -> optional independently-failable guide enrichment
    -> atomic draft publication
```

P7-14d completes the Tier A geometry slice. The active generator no longer uses random
room-placement or routing retries for correctness. Seeded optimization is not yet
implemented; every seed currently uses the same zero-draw proven baseline, which is the
required fallback for future optional compaction.

## P7-14d Work Completed

### Certificate-driven physical proof

- Made the exact `TopologyCertificate` a required `LayoutRequest` input and verified its
  topology ID, canonical topology hash, room mapping, and connection mapping before
  layout.
- Added independently recomputed `RoomPortAssignmentWitness` records with exact
  north/east/south/west incident connection lists.
- Added `ConnectionChannelWitness` records for backbone, upper/lower branch, and loop
  bands. Mutated side and channel claims are rejected by certificate validation.
- Compiler output now carries certificate-derived exact floor bounds instead of a fixed
  56x56 compatibility rectangle.

### Constructive Tier A baseline

- Added `layout/constructive.py` for one-floor 4–8 room construction:
  - critical-path rooms occupy ordered backbone columns;
  - upper/lower branch rooms occupy dedicated vertical bands;
  - room dimensions expand within their declared size bands for side-port and certified
    interior demand;
  - every connection receives a deterministic one-cell orthogonal passage with explicit
    wall openings and straight endpoint leads;
  - already reserved passage cells are blocked from later channels, including the
    public/secret loop, so channels do not cross or share cells;
  - exact required width/height plus rock margin is computed before package geometry.
- Caller floor bounds now act as optional maxima: a too-small maximum fails with exact
  required dimensions; a larger maximum still emits the exact proven bounds.
- All same-floor door intents may be corridor-realized at a declared passage opening;
  gate/secret mechanics remain on an exact door segment at that opening. Geometry
  validation accepts either a shared-wall door or this explicit passage-door form and
  independently rejects corridor crossings/shared cells.
- Removed the inactive random room-placement/retry implementation and the obsolete
  `maximum_placement_attempts` request field. The retained generic routing module is
  test utility code, not part of active generation.
- Locks are accepted only when byte-equal to the certificate-derived baseline; stale or
  conflicting locks fail explicitly.

### Properties and integration fixtures

- Expanded active Hypothesis coverage to generated 4–8 room plans across seeds, room
  demand, upper/lower branches, public/secret loops, exact bounds, openings, and geometry
  validity.
- Added regressions for noncrossing reserved cells, exact-versus-maximum bounds,
  certificate binding mutation, side/channel proof mutation, zero random draws, and
  constructive secret-channel/player-render leakage.
- Replaced root Dungeon Studio integration request construction with one shared
  synthetic proof-carrying Tier A request. The historical multi-floor package fixture
  remains only for package reader/export/pathfinding compatibility tests; active layout
  does not generate it.
- Updated topology math, architecture-facing README direction, and milestone history.

## Files Changed

No migration changed. Main changes are in:

- `packages/dungeon-engine/src/dm_dungeon/contracts/{certificate,package}.py`
- `packages/dungeon-engine/src/dm_dungeon/compiler.py`
- `packages/dungeon-engine/src/dm_dungeon/layout/{contracts,constructive,engine,placement}.py`
- `packages/dungeon-engine/src/dm_dungeon/validation/{certificate,geometry,geometry_contracts,TOPOLOGY_MATH.md}`
- package plan/compiler/layout/property/rendering/geometry/pathfinding tests
- `src/dm_assistant/orchestration/dungeons/{prompting,evals}.py`
- `tests/integration/dungeon_fixtures.py` and focused unit/integration request fixtures
- `README.md`, `PROJECT_HISTORY.md`, and this handoff

## Verification

- `uv run pytest -q packages/dungeon-engine/tests` → **135 passed**.
- `uv run pytest -q tests/unit tests/evals` → **173 passed**.
- Focused Dungeon Studio CLI/workflow/web/web-prompt integration files → **6 skipped**
  because the PostgreSQL integration gate was unavailable; collection succeeded.
- `uv run mypy --strict packages/dungeon-engine/src/dm_dungeon src/dm_assistant/orchestration/dungeons src/dm_assistant/cli/main.py`
  → passed (**56 source files**).
- Focused Ruff check over changed package, orchestration, unit, and integration Python
  files → passed.
- `git diff --check` → passed.

Package and root tests must continue to run as separate pytest invocations: combining
both test roots in one process causes pytest's existing duplicate module basenames to
produce an import-file-mismatch collection error.

## Working Tree

P7-14d is uncommitted. The tree contains this task's certificate/layout/validation,
test-fixture, property, and documentation changes. No migration, real campaign content,
provider response, credential, live-provider call, canonical campaign write, or
preparation approval changed.

Suggested commit subject:

`P7-14d construct certified Tier A dungeon geometry`

## Single Next Recommended Task

**Begin P7-14e — prompt/guide integration and provider-free stress ladder.**

**First concrete action:** run the faux-provider prompt through the exact accepted
certificate/layout path and add one end-to-end assertion set that an accepted
`submit_dungeon_plan` publishes an atomic draft with DM/player SVG+PNG, exact keyed guide
references, preparation-readiness diagnostics, and no player-visible secret channel or
door. Keep optional guide enrichment independently failable and do not resume live
provider calls yet.
