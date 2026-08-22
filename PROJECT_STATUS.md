# Project Status and Handoff

> Read this file first. Historical milestones and superseded handoffs belong in
> [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md). Do not infer the next task from old V2/V3/V4
> names in the tree.

## Current Snapshot

- **Last updated:** 2026-08-21
- **Branch:** `fast-track-prompt-to-dungeon`, two commits ahead of origin before this WIP.
- **Current task:** **P7-14b — One alpha V1 and dead-code deletion.**
- **Task state:** **complete in the working tree; not committed.** The model,
  proposal/design/compiler/mechanics, package/reader, layout generator, renderer, and
  Roll20 paths now expose one suffix-free alpha V1.
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

## P7-14a Work Completed

The architecture/reset, topology-math guide, active-path safety fixes, characterization,
and known-bad output-baseline deletion were committed at `25c031e` before the current
P7-14b WIP.

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

## P7-14b Work Completed in This WIP

### Old arbitrary-topology prompt path removed

- Deleted `DungeonPromptService.create`'s obsolete direct `DungeonGenerationIntentV1`
  workflow and made the active one-submission workflow the sole `create` method.
- Deleted the five old model tools: `review_dungeon_brief`,
  `review_dungeon_topology`, `generate_dungeon_layout`, `validate_dungeon_intent`, and
  `regenerate_dungeon_layout`, including their private input contracts, handlers,
  prompts, repair path, preflight path, and targeted-regeneration preview.
- Deleted `DungeonGenerationIntentV1` from the modeling contracts/barrel and removed
  the legacy `PromptedDungeonModelLineage.intent` branch. Active lineage now has one
  model-result shape.
- Removed the obsolete profile resolver and renamed the active resolver to
  `resolve_dungeon_prompt_profile`; CLI/web and application orchestration now use only
  the one-submission path.
- Removed associated obsolete unit/integration tests while retaining active compact-
  submission, guide, CLI, web, package, and eval coverage.

### Modeling import cycle removed

- Stopped `modules.modeling.__init__` from eagerly importing the Workbench service,
  which itself depends on orchestration modeling. `GatewayCompletion` can now be
  imported directly in a fresh process without import-order priming.
- Updated the API composition root to import `ModelWorkbenchService` from its owning
  module and removed the eval-suite import-order workaround.
- Added a typed provider-state mapping in `modules/modeling/workbench.py`, restoring
  strict mypy over the touched modeling/orchestration surface.
- Updated stale browser-auth export payloads with their required explicit
  `export_format`, restoring the full root unit suite.

This slice removes 1,100+ lines and leaves exactly one prompted dungeon orchestration
path.

### Sole public package and reader

- Merged the mechanics-aware exact package into
  `contracts/package.py` as the sole public `DungeonPackage` and deleted
  `contracts/package_v2.py`/`DungeonPackageV2`.
- Reset the package and topology roots to schema `1.0.0`; serialization now accepts
  exactly that package root instead of dispatching retained `1.1.0` and active `1.3.0`
  readers.
- Removed numeric suffixes from active exact-package records (`DoorMechanics`,
  `MechanicDoorLayout`, `RoomMechanicMarker`, and `VerticalEndpointDoorLayout`).
- Regenerated `sunken_archive.v1.json` through the active mechanics-aware generator and
  refreshed SVG/PNG goldens. It no longer preserves the old hand-authored package
  geometry or known-bad output assumptions.
- Rebased package, geometry, rendering, export, CLI, Workbench guide, and test typing on
  the sole exact package. Added a missing invariant that composable-door visibility must
  match its render layer.
- Deleted three compatibility/duplicate tests, including the V3 package-dispatch test,
  while retaining deterministic generation, geometry, secrecy, rendering, PNG/PDF,
  Roll20, CLI, and contract coverage.

### Suffix-free alpha V1 and sole layout path

- Renamed `design_v2.py` and `mechanics_v2.py` to suffix-free modules and removed
  numeric suffixes from every active design, mechanics, proposal, submission, compiler,
  serialization, test, and eval public name.
- Reset the design/proposal schema to `1.0.0`, proposal version to `1`, compiler pin to
  `dungeon-design-compiler-v1`, mechanics policy to `dungeon-mechanics-policy-v1`,
  generated IDs to `v1-*`, renderer to `svg-v1`, and Roll20 exporter to `roll20-v1`.
- Renamed the only model tool to `submit_dungeon_plan`; CLI/web profile policies and
  durable attempt pins now use the one alpha V1 names. The payload intentionally keeps
  the temporary arbitrary-edge design only until P7-14c introduces `DungeonPlan`.
- Made `LayoutRequest.generator_version` exactly `orthogonal-v1`, made
  `mechanics_plan` required, and deleted all `orthogonal-v2/v3/v4` dispatch and fallback
  behavior.
- Removed the old package `doors` projection and obsolete `DoorLayout` contract. Exact
  same-floor locks now retain `MechanicDoorLayout` directly; layout uses only a private
  pre-mechanics geometry record.
- Removed now-always-true package compatibility checks from geometry validation,
  rendering, annotations, Roll20 export, CLI, and Workbench regeneration/guide code.
- Deleted the old V1/V2 eval-comparison API/test because no retained consumer or
  artifact requires generation-version comparison. Renamed the synthetic eval fixture
  to `dungeon_intent.json`.
- Regenerated `sunken_archive.v1.json` with `orthogonal-v1` and refreshed SVG/PNG
  goldens. Updated focused PostgreSQL fixtures, README guidance, CLI/web faux gateway
  payloads, schema/generator expectations, and preparation pins to the sole alpha V1.

## Verification

Completed P7-14b working tree:

- Fresh-process direct imports of `GatewayCompletion` and `ModelWorkbenchService` →
  passed without import-order priming in the first P7-14b slice.
- `uv run pytest -q packages/dungeon-engine/tests` → **`203 passed`**.
- `uv run pytest -q tests/unit tests/evals` → **`173 passed`**; the count decreased by
  one because the obsolete V1/V2 comparison test was deleted.
- Focused CLI/web/workflow/web-prompt integration files → **`6 skipped`** because the
  integration database gate was unavailable; collection had no failure.
- Strict mypy over the package, dungeon orchestration, and touched CLI → passed
  (**`53` source files**).
- Focused Ruff check and format over all changed Python files → passed (**`51` files**).
- `git diff --check` → passed before this final status edit.

A broad `ruff check src tests/unit tests/evals` also exposed six unrelated baseline
violations in untouched Library/scope files (`modules/library/__init__.py`,
`modules/library/retrieval.py`, `modules/scope.py`, and
`tests/unit/test_library_contracts.py`). They are not part of this dungeon slice and
remain unresolved.

## Working Tree

The complete P7-14b work remains uncommitted on a branch two commits ahead of origin.
It includes the first model-orchestration/package-reader collapse plus the suffix-free
contract/compiler/mechanics rename, sole generator path, old door projection deletion,
Workbench/CLI/web updates, focused integration fixtures, README, regenerated synthetic
fixture/goldens, tests, and this handoff.

Deleted paths include `contracts/design_v2.py`, `contracts/mechanics_v2.py`,
`contracts/package_v2.py`, `test_design_v2_compiler.py`, `test_package_v2.py`, and
`tests/evals/golden/dungeon_intent_v2.json`; suffix-free replacements are present in the
working tree. No migration, provider response, real campaign content, credential, or
live-provider call changed in P7-14b.

## Single Next Recommended Task

**Begin P7-14c — creative `DungeonPlan` and topology certificate.**

**First concrete action:** add the strict `DungeonPlan` V1 creative contract and
provider-safe schema tests for one floor, 4–8 rooms, one entrance/objective critical
path, bounded branches/loop, gate/dependency, secret route, and bounded room-content
intent. Replace the temporary arbitrary model-authored edge aggregate only after the
new contract and its reference/cardinality diagnostics are green.

Then build the deterministic series/parallel-with-spurs topology compiler and an
independently recomputed `TopologyCertificate` with connectivity, cycle, branch,
gate-order, public/secret reachability, room-demand, port-demand, and embedding
witnesses. Do not start constructive geometry (P7-14d) in the same task.

Suggested commit subject for the completed current work:

`P7-14b collapse dungeon generation to one alpha V1`
