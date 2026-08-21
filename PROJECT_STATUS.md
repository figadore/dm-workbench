# Project Status and Handoff

> Read this file first. Historical milestones and superseded handoffs belong in
> [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md). Do not infer the next task from old V2/V3/V4
> names in the tree.

## Current Snapshot

- **Last updated:** 2026-08-21
- **Branch:** `fast-track-prompt-to-dungeon`, one commit ahead of origin before this WIP.
- **Current task:** **P7-14b — One alpha V1 and dead-code deletion.**
- **Task state:** first model-orchestration deletion/circular-import slice complete but
  uncommitted; pure package/contract/generator collapse remains.
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
path. It does **not** yet rename the active V2 proposal/design/package classes or remove
`orthogonal-v2/v3/v4` package dispatch; those are the next P7-14b slice.

## Verification

Current P7-14b WIP:

- Fresh-process direct imports of `GatewayCompletion` and `ModelWorkbenchService` →
  passed without import-order priming.
- Focused modeling/prompt/eval tests → `23 passed`.
- `uv run pytest -q tests/unit` → **`169 passed`**.
- `uv run pytest -q tests/evals` → **`5 passed`**.
- `uv run pytest -q packages/dungeon-engine/tests` → **`206 passed`**.
- Focused CLI/web prompt integration files → `3 skipped` because the integration
  database gate was unavailable; no failure.
- Strict mypy over touched modeling/dungeon/API/CLI source → passed.
- Focused Ruff check and format over all touched Python files → passed.
- `git diff --check` → passed before the final status edit.

A broad `ruff check src tests/unit tests/evals` also exposed six unrelated baseline
violations in untouched Library/scope files (`modules/library/__init__.py`,
`modules/library/retrieval.py`, `modules/scope.py`, and
`tests/unit/test_library_contracts.py`). They are not part of this dungeon slice and
remain unresolved.

## Working Tree

Uncommitted P7-14b changes:

- `src/dm_assistant/api/app.py`
- `src/dm_assistant/cli/main.py`
- `src/dm_assistant/modules/modeling/{__init__,contracts,workbench}.py`
- `src/dm_assistant/orchestration/dungeons/{__init__,application,contracts,prompting,service,web_prompt}.py`
- `tests/evals/test_dungeon_evals.py`
- `tests/integration/test_dungeon_studio_workflow.py`
- `tests/unit/{test_prompted_dungeon_workflow,test_web_auth}.py`
- `PROJECT_STATUS.md`

No migration, provider response, real campaign content, credential, live-provider call,
or package schema changed in this WIP.

## Single Next Recommended Task

**Continue P7-14b — collapse the pure package and active contracts to one V1.**

**First concrete action:** inventory every test/fixture still read through the retained
`DungeonPackage` 1.1 versus active `DungeonPackageV2` 1.3 dispatch, then make the active
mechanics-aware package the sole `DungeonPackage` schema `1.0.0`. Delete the retained
reader and regenerate only fixtures still exercising useful behavior.

Then rename active design/mechanics/compiler/proposal/submission public names without
numeric suffixes, pin them to V1, replace `submit_dungeon_intent_v2` with the sole
`submit_dungeon_plan` name, and remove `orthogonal-v2/v3/v4` layout branching in favor
of one generator pin. Re-run package, root unit/eval, strict mypy, focused PostgreSQL
integration, Ruff, and `git diff --check` before P7-14c.

Suggested commit subject when all P7-14b work is complete:

`P7-14b collapse dungeon generation to one alpha V1`
