# Project Status and Handoff

> Read this file first. Historical milestones and superseded handoffs belong in
> [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md). Do not infer the next task from old
> V2/V3/V4 names in Git history or implementation-plan history.

## Current Snapshot

- **Last updated:** 2026-08-21
- **Branch:** `fast-track-prompt-to-dungeon`, three commits ahead of origin before
  this WIP (`dd54b4e` committed P7-14b).
- **Current task:** **P7-14c — Creative `DungeonPlan` and topology certificate.**
- **Task state:** **complete in the working tree; not committed.**
- **Schema head:** `0008_workbench_defaults`; no migration changed.
- **Live providers:** no call was made. Keep live canaries paused until the P7-14
  Tier A provider-free and faux gates pass.

## Active Direction

P7-13 feature/polish work remains paused. The active recovery is defined by
[`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md):

```text
one submit_dungeon_plan V1 model call
    -> deterministic critical-path/branch/loop topology compiler
    -> independently checked TopologyCertificate
    -> constructive orthogonal layout with computed bounds
    -> independent geometry/secrecy validation
    -> optional independently-failable guide enrichment
    -> atomic draft publication
```

P7-14c completes the abstract creative/topology proof layer only. The existing
place-then-route geometry implementation remains an interim compatibility seam and
must be replaced, not given more retries, in P7-14d.

## P7-14c Work Completed

### Sole bounded creative contract

- Replaced `DungeonDesignSpec` and its model-authored floors/connections with one
  provider-visible `DungeonPlan` schema `1.0.0`.
- Tier A schema bounds are enforced before provider-independent compilation:
  - one floor represented implicitly;
  - 4–8 rooms;
  - exactly one entrance/objective critical path;
  - zero to two ordered optional branch paths;
  - zero or one non-duplicate loop/secret route;
  - zero or one gate with key/clue intent;
  - bounded room encounter, trap, feature, and named-objective intent.
- The schema contains no arbitrary edge list, IDs, floor geometry, coordinates,
  dimensions, seed, numeric DC, visibility, lifecycle, or publication fields.
- Added provider-schema tests for strict objects, cardinality bounds, unsupported
  fields/enums, version rejection, and canonical round trips.

### Deterministic graph compiler

- Replaced `compile_dungeon_design` with `compile_dungeon_plan` pinned to
  `dungeon-plan-compiler-v1`.
- The compiler now constructs every graph edge from the critical path, ordered
  branches, and optional loop. Stable IDs derive from semantic identity and the
  compiler pin, not model prose, array position, or seed.
- Compiler diagnostics reject duplicate/unknown/reused/unassigned refs, invalid
  critical-path endpoints, non-optional branch rooms, duplicate/self loops,
  unsupported branch attachments, malformed objective content, gates without a
  constructed public edge, gate/dependency-kind mismatch, and dependency rooms not
  publicly reachable with the gate closed.
- Gate/key/clue, secret door/bypass, objective, encounter, trap, and feature intent
  compile into the existing exact topology/mechanics records. The lower topology
  validator now accepts the ordered branch witness while retaining the synthetic
  package fixture's historical star witness.

### Proof-carrying topology certificate

- Added `TopologyCertificate` version `topology-certificate-v1` and grammar pin
  `series-parallel-with-spurs-v1`.
- Certificates bind exact plan/topology hashes and semantic-ref-to-ID mappings and
  carry:
  - grammar production steps and entrance/objective critical-path witness;
  - connected-component, room, edge, and cycle-rank facts;
  - ordered branch and simple-cycle loop witnesses;
  - closed-gate dependency reachability/open order;
  - full DM and public reachability sets;
  - room degree, port/opening/clearance demand, and interior encounter/feature/trap
    demand;
  - backbone/branch embedding order, dedicated bands, and loop interval bands.
- Added `validate_topology_certificate`, which independently reconstructs graph,
  grammar, branch/loop/gate, public/secret reachability, demand, and embedding facts.
  Compilation fails as an engine invariant if its newly emitted certificate does not
  pass this independent validator.
- Added example and Hypothesis coverage over 4–8 room Tier A plans, branches, loops,
  secret routes, graph rank, demands, deterministic IDs, and deliberately mutated
  certificate claims.

### Workbench and synthetic evidence

- Updated the sole proposal wrapper to carry `plan`, updated the prompt/tool schema,
  compiler call, bounded repair diagnostics, eval projection, DM-guide projection,
  run pins, faux CLI/web payloads, and integration expectations.
- Accepted tool results now expose plan hash, compact graph counts, cycle rank,
  secret/gate counts, certificate version, compiler pins, and bounded warnings.
- Regenerated the provider-free dungeon eval fixture for Tier A; removed obsolete
  multi-floor/arbitrary-edge cases.
- Deleted `contracts/design.py` and `test_design_compiler.py`; there is no retained
  active `DungeonDesignSpec` or `compile_dungeon_design` path.
- Updated root guidance and `TOPOLOGY_MATH.md` to distinguish completed P7-14c proofs
  from P7-14d side-port/exact-bounds/geometry work.

## Files Changed

No migration changed. Main changes are in:

- `packages/dungeon-engine/src/dm_dungeon/contracts/plan.py` (new)
- `packages/dungeon-engine/src/dm_dungeon/contracts/certificate.py` (new)
- `packages/dungeon-engine/src/dm_dungeon/compiler.py`
- `packages/dungeon-engine/src/dm_dungeon/validation/certificate.py` (new)
- `packages/dungeon-engine/src/dm_dungeon/validation/topology.py`
- package barrels/serialization/mechanics imports and topology math documentation
- `src/dm_assistant/orchestration/dungeons/{contracts,prompting,service,evals}.py`
- plan/compiler/property/workflow/eval/faux-integration tests and synthetic eval fixture
- `README.md`, `PROJECT_HISTORY.md`, and this handoff

Deleted:

- `packages/dungeon-engine/src/dm_dungeon/contracts/design.py`
- `packages/dungeon-engine/tests/test_design_compiler.py`

## Verification

- `uv run pytest -q packages/dungeon-engine/tests` → **129 passed**.
- `uv run pytest -q tests/unit tests/evals` → **173 passed**.
- Focused CLI/web/workflow/web-prompt/preparation integration files → **19 skipped**
  because the PostgreSQL integration gate was unavailable; collection succeeded.
- `uv run mypy --strict packages/dungeon-engine/src/dm_dungeon src/dm_assistant/orchestration/dungeons src/dm_assistant/cli/main.py` → passed (**55 source files**).
- Focused Ruff check/format over changed package, orchestration, unit/eval, and faux
  integration Python files → passed.
- `git diff --check` → passed before this final status update.

Package and root tests must continue to run as separate pytest invocations: combining
both test roots in one process causes pytest's existing duplicate module basenames
(`test_cli.py`, `test_package.py`) to produce an import-file-mismatch collection error.
This is not a P7-14c product failure.

## Working Tree

P7-14c is uncommitted on a branch three commits ahead of origin. The tree contains only
this task's plan/compiler/certificate/orchestration/test/documentation changes. No
migration, real campaign content, provider response, credential, live-provider call, or
constructive geometry implementation changed.

Suggested commit subject:

`P7-14c construct and certify Tier A dungeon topology`

## Single Next Recommended Task

**Begin P7-14d — constructive Tier A geometry.**

**First concrete action:** make the exact accepted `TopologyCertificate` a required
layout input/pin, then add failing constructive-layout tests for certified 4–8 room
critical paths, upper/lower branches, and one public/secret loop. Implement exact
required bounds, backbone columns, dedicated branch/loop bands, room expansion from
interior demand, side-specific port assignments, and reserved noncrossing channels from
the certificate. Keep optional seeded compaction separate and fall back to the proven
baseline; do not increase random placement/routing attempts.
