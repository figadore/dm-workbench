# Project Status and Handoff

> Read this file first. Historical milestones and superseded handoffs belong in
> [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md). Do not infer the next task from old V2/V3/V4
> names in the tree.

## Current Snapshot

- **Last updated:** 2026-08-21
- **Branch:** `fast-track-prompt-to-dungeon`, synchronized with its origin before this WIP.
- **Current task:** **P7-14a — Dungeon generation alpha reset, characterization, and green baseline.**
- **Task state:** architecture/reset decision and first safety/deletion slice complete but uncommitted.
- **Schema head:** `0008_workbench_defaults`; no migration changed.
- **Live providers:** no call was made. Do not resume the stopped live suite during P7-14a/b.

## User Direction and Architecture Decision

The prior P7-13 feature program is paused. The project had optimized contracts,
compatibility, rendering, and edge mechanics before reliably producing a small coherent
dungeon. The active recovery is specified in
[`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md).

The target pipeline is:

```text
one submit_dungeon_plan V1 model call
    -> deterministic critical-path/branch/loop topology compiler
    -> independently checked TopologyCertificate
    -> constructive orthogonal layout with computed bounds
    -> independent geometry/secrecy validation
    -> optional independently-failable guide enrichment
    -> atomic draft publication
```

Correctness must not depend on random placement/routing retries. Tier A uses a bounded
series/parallel-with-spurs graph grammar. Connectivity is true by construction; loop,
branch, gate-order, public/secret reachability, room interior demand, wall-port demand,
and embedding witnesses are recomputed by validators. Layout allocates backbone columns,
branch/loop bands, room dimensions, openings, and corridor channels from the certificate.
Seeded search may improve a proven baseline but cannot be required to find one.

There are no retained user dungeons or external dungeon consumers. Collapse application
contract/generator history to one clean V1 and delete old generation/readers/fixtures.
This does **not** authorize rewriting or force-pushing Git history.

## P7-14a Work Completed in This WIP

### Planning and architecture

- Added `dungeon-generation-recovery-plan.md` with:
  - the Tier A scope and exact model tool-call example;
  - graph construction and topology-certificate rules;
  - gate/secret reachability proofs;
  - room port/interior feasibility arithmetic;
  - constructive layout rules that do not use backtracking for correctness;
  - Tier A through Tier E stress progression;
  - resumable R0–R5 implementation slices.
- Updated `dm-assistant-technical-architecture.md` to make the proof-carrying V1 pipeline normative.
- Added P7-14a through P7-14e and the Tier A gate to `dm-assistant-implementation-plan.md`.
- Added `packages/dungeon-engine/src/dm_dungeon/validation/TOPOLOGY_MATH.md`
  beside the executable topology validator. It introduces graph/topology terms in code
  order and explains adjacency, BFS reachability, components, cycle rank, branch
  witnesses, separators, secret subgraphs, Tarjan SCCs, monotone gate-progression fixed
  points, planarity limits, the constructive series/parallel V1 boundary, room-port
  arithmetic, and which proofs are current versus P7-14c/d work. `topology.py` and the
  package README link to it.

### Active-path safety and characterization

- Fixed `layout/routing.py` so the exclusive width/height floor boundary cannot be
  entered; the previous `>` check allowed `x == width` or `y == height`.
- Fixed `layout/engine.py` so an active explicit-passage routing failure cannot silently
  fall back to the legacy router and then crash on `assert passage_route is not None`.
  It now returns `layout.connection_routing_failed`.
- Added focused regressions for both defects.
- Replaced legacy `orthogonal-v2` Hypothesis coverage with property tests through the
  actual active compact-design/compiler/mechanics/layout path.
- The current characterization certifies 2–5 room chains across generated seeds. This
  is an interim green floor, not the Tier A gate. A sampled 7-room chain still had 5/30
  ordinary routing failures; an 8-room chain had 7/30 failures. There were no crashes or
  out-of-bounds diagnostics after the safety fix. P7-14d must replace this fallible path,
  not increase retries.

### Dead-code deletion

Deleted the obsolete known-bad output baseline:

- `packages/dungeon-engine/tests/fixtures/output_quality_baseline.v1.json`
- `packages/dungeon-engine/tests/golden/output_quality_baseline.upper.dm.svg`
- `packages/dungeon-engine/tests/test_output_quality_baseline.py`

Those files existed to preserve/count defects including raw IDs, overlaps, missing
mechanics, and 73 mostly blank PDF pages. No retained user artifact required them.

## Verification

- `uv run pytest -q packages/dungeon-engine/tests/test_routing.py packages/dungeon-engine/tests/test_design_v2_compiler.py` → `90 passed` before the property rewrite.
- Focused active property/compiler/routing gate → `92 passed`.
- `uv run pytest -q packages/dungeon-engine/tests` → **`206 passed`**.
- `uv run ruff check packages/dungeon-engine/src/dm_dungeon packages/dungeon-engine/tests` → passed.
- `uv run ruff format --check packages/dungeon-engine/src/dm_dungeon packages/dungeon-engine/tests` → passed.
- `uv run mypy --strict packages/dungeon-engine/src/dm_dungeon` → passed.
- `uv run pytest -q packages/dungeon-engine/tests/test_topology_validation.py packages/dungeon-engine/tests/test_topology_properties.py` → `11 passed`.
- Focused Ruff check/format over `validation/topology.py` → passed.
- `git diff --check` → passed.
- Root unit/integration suites were not run; the Workbench/model contract was not changed in this slice.

## Working Tree

Uncommitted P7-14a changes:

- `dungeon-generation-recovery-plan.md` (new)
- `dm-assistant-implementation-plan.md`
- `dm-assistant-technical-architecture.md`
- `PROJECT_STATUS.md`
- `packages/dungeon-engine/README.md`
- `packages/dungeon-engine/src/dm_dungeon/layout/{engine,routing}.py`
- `packages/dungeon-engine/src/dm_dungeon/validation/{topology.py,TOPOLOGY_MATH.md}`
- `packages/dungeon-engine/tests/{test_design_v2_compiler,test_layout_properties,test_routing}.py`
- the three deleted output-baseline files listed above

No migration, provider response, real campaign content, credential, or live-provider state changed.

## Single Next Recommended Task

**P7-14b — collapse model generation and exact package/layout dispatch to one alpha V1.**

**First concrete action:** remove the unused `DungeonPromptService.create` V1 arbitrary-
topology workflow, its five old model tools, `DungeonGenerationIntentV1`, legacy lineage
field, and their tests. Keep the currently active single-submission workflow working while
renaming it toward `submit_dungeon_plan`; do not leave both old and replacement paths
half-supported.

Then, in the same ordered slice:

1. break the `modules.modeling` ↔ `orchestration.modeling` circular import;
2. collapse active design/proposal/package/mechanics names and schema pins to V1;
3. delete `orthogonal-v2/v3/v4` dispatch and keep one current generator pin;
4. regenerate or delete remaining synthetic legacy fixtures;
5. restore green package, root unit/eval, strict mypy, Ruff, and integration focus before
   starting the new topology certificate.

Suggested commit subject for the completed current slice:

`P7-14a reset dungeon generation architecture and baseline`
