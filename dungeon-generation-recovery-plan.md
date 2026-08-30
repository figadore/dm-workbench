# Dungeon Generation Alpha Reset and Recovery Plan

> Status: active. This plan supersedes new P7-13 feature work until the Tier A gate
> passes. There are no retained user dungeons or external dungeon consumers. Synthetic
> and live-canary alpha artifacts are disposable. Collapse the implementation to one
> honest V1; do not preserve unused V1/V2/V3/V4 generation paths.

## 1. Product reset

The next milestone is not “support every dungeon primitive.” It is:

> One bounded model submission reliably becomes a coherent, connected, playable,
> secrecy-clean Tier A dungeon through deterministic construction.

Keep the pure `dm_dungeon` package, Workbench/preparation boundary, private model
transport, deterministic validation/rendering, and atomic publication. Replace the
model-authored arbitrary graph and place-then-route layout strategy.

Pause asset-catalog polish, print re-enable, additional mechanics, campaign grounding,
and live-provider suite execution until Tier A passes provider-free and faux-provider
gates. Do not compensate with more retries or a larger model.

## 2. One alpha V1

Before a real user artifact or external consumer exists:

- the model tool is `submit_dungeon_plan` version `1`;
- the creative contract is `DungeonPlan` schema `1.0.0`;
- the compiled topology/certificate is V1;
- the exact package is `DungeonPackage` schema `1.0.0`;
- the compiler, topology grammar, layout, mechanics policy, and renderer each have one
  V1 pin;
- public Python names have no `V2`, `V3`, or `V4` suffix;
- the layout engine contains no legacy-version branches;
- new V1 generation is the only generation path;
- old synthetic fixtures and disposable alpha database artifacts are deleted or
  regenerated, not retained through compatibility readers.

This resets application contract history, not Git history. Do not force-push or rewrite
commits as part of this task.

All active V1 labels evolve in place until the retention gate is explicitly declared in
both `PROJECT_STATUS.md` and the architecture. Synthetic fixtures, ignored review
packets, disposable alpha database rows, and provider canaries do not cross that gate.
Declare it no later than the first intentionally retained real-user artifact/campaign,
external consumer, non-disposable deployment, or promised replay requirement; only then
freeze pins and require documented readers, migrations, rollback, or compatibility
versions.

## 3. Tier A scope

A Tier A dungeon has:

- one floor and 4–8 rooms;
- exactly one entrance and one final objective;
- one ordered critical path between them;
- zero to two branch paths and zero or one loop/bypass;
- ordinary doors/passages and at most one secret route;
- at most one gate with a key or clue reachable before the gate;
- bounded room-local traps/features and encounter intent;
- rectangular rooms, one-cell openings, and orthogonal one-cell-wide corridors;
- a readable DM guide and secrecy-clean DM/player SVG and PNG.

Tier A deliberately excludes multiple floors, arbitrary graph edges, arbitrary room
polygons, dynamic encounter composition/stat blocks, exact-scale print, and unconstrained
feature packing. Existing exporters may remain disabled or internal, but they do not
block the gate.

## 4. End-to-end flow

```text
DM prompt + authorized narrow context + server seed
    |
    v
one model tool call: submit_dungeon_plan(proposal fields at root, including plan)
    |
    v
validate the small creative contract
    |
    v
deterministic topology compiler
    |-- build graph from critical path / branches / loop grammar
    |-- assign IDs and connection semantics
    |-- place gates, keys, secrets, traps, features, encounter intent
    `-- emit TopologyCertificate
    |
    v
constructive orthogonal layout
    |-- derive room demand and port demand
    |-- allocate backbone columns, branch/loop bands, and corridor channels
    |-- compute exact required floor bounds before emitting cells
    `-- emit exact DungeonPackage
    |
    v
independent topology + geometry + secrecy validation
    |
    v
optional independently-failable DM-guide enrichment
    |
    v
atomic preview/assets/specification publication as a draft
```

The accepted tool arguments are the model result. The model is not asked for a second
text answer. A schema-invalid call may receive at most one bounded repair with the
original request and safe diagnostics. A structurally accepted plan is not sent back to
the model for topology or geometry repair: code owns those steps.

## 5. Model tool contract

The model expresses narrative identity and progression, not an arbitrary edge list. The
`DungeonGenerationProposal` fields are the `submit_dungeon_plan` tool arguments directly;
there is no additional `proposal` envelope around them. Schema diagnostics and the one
bounded repair therefore operate on `/plan`, `/guide_content`, and other actual root paths
and must never tell the model to delete a valid proposal merely because an adapter added
an avoidable wrapper.

Illustrative input:

```json
{
  "plan": {
    "schema_version": "1.0.0",
    "title": "Flooded Archive",
    "premise": "A drowned archive beneath a lighthouse protects the Stone of Redemption.",
    "themes": ["flooded records", "lighthouse machinery"],
    "rooms": [
      {"ref": "entry", "name": "Keeper's Stair", "role": "entrance", "size": "small", "purpose": "establish the flooded descent"},
      {"ref": "stacks", "name": "Drowned Stacks", "role": "exploration", "size": "medium", "purpose": "reveal the archive's history"},
      {"ref": "workshop", "name": "Lens Workshop", "role": "optional", "size": "small", "purpose": "hold a bypass clue"},
      {"ref": "vault", "name": "Stone Vault", "role": "objective", "size": "medium", "purpose": "hold the Stone of Redemption"}
    ],
    "critical_path": ["entry", "stacks", "vault"],
    "branches": [{"ref": "workshop_branch", "from_room": "stacks", "rooms": ["workshop"]}],
    "loops": [{"ref": "workshop_bypass", "from_room": "workshop", "to_room": "vault", "secret": true}],
    "gates": [{"between_rooms": ["stacks", "vault"], "kind": "locked", "dependency_room": "workshop", "dependency_name": "Brass Lens Key"}],
    "room_contents": [
      {"room_ref": "stacks", "encounter": "exploration", "feature": "collapsing shelves"},
      {"room_ref": "vault", "trap": "flood-release plate", "objective": "Stone of Redemption"}
    ]
  }
}
```

The server returns a compact tool result and continues without another model turn:

```json
{
  "accepted": true,
  "plan_hash": "<sha256>",
  "topology": {
    "rooms": 4,
    "connections": 4,
    "branches": 1,
    "cycle_rank": 1,
    "secret_routes": 1,
    "gates": 1
  },
  "certificate_version": "topology-certificate-v1",
  "warnings": []
}
```

A rejected plan returns only bounded codes, paths, affected refs, and repair actions.
It never returns exact geometry, provider bodies, or arbitrary model prose. A repair is
started only when a conservative estimate of its complete canonical message plus tool
schema leaves output room inside the measured cumulative budget. Measured output or total
usage above a pinned ceiling fails before publication and is durably inspectable without
retaining provider/model bodies. Provider-reported usage above a requested transport cap blocks ordinary live rollout:
rejecting the result cannot recover already consumed usage. One frozen non-production
Tier A canary may use its dedicated CLI command with an explicit acknowledged
`openai-codex` advisory-output policy. That exception leaves the requested cap in the
transport request, retains the measured 12,000-token cumulative publication ceiling and
repair reservation, records durable policy lineage, and permits only one stop-on-failure
operator run after the other gates pass.

## 6. Topology construction and proof

### 6.1 Supported graph grammar

Tier A does not accept an arbitrary model-authored graph. It constructs a connected
series/parallel-with-spurs graph:

1. The critical path creates a connected path from entrance to objective.
2. Each branch attaches an ordered path to one existing room.
3. A loop adds one route between two existing rooms only under the supported embedding
   rule.

Connectivity is therefore true by construction. The loop raises the graph cycle rank
by exactly one. For one connected floor:

```text
cycle_rank = edge_count - room_count + 1
```

The compiler checks that this equals the number of realized independent loops.

The initial loop embedding uses intervals over the critical-path/branch ordering.
Multiple later loops are allowed only when their intervals are disjoint or nested;
interleaving intervals are rejected as an unsupported topology before layout. This is
an explicit supported graph class, not random routing failure.

### 6.2 Gate and secret proofs

For a gate on connection `g`:

1. Treat `g` as closed.
2. Compute rooms reachable from the entrance.
3. Require the key/clue room to be in that reachable set.
4. Open gates whose dependencies are reachable and repeat to a fixed point.
5. Require every mandatory room and the final objective to become reachable.

A secret route is represented as a discoverable edge/path, not as hidden geometry
invented by the renderer. The full DM graph must be connected. The initial player graph
may omit a secret optional wing; it may not require an undiscovered secret to reach a
mandatory objective unless the plan explicitly marks that discovery as required.

### 6.3 Topology certificate

The compiler emits a deterministic certificate consumed by layout and independently
checked by validation:

- supported graph grammar and parse tree;
- room/connection IDs and stable semantic refs;
- entrance/objective path;
- connected-component count;
- cycle rank and loop witnesses;
- branch witnesses;
- gate/dependency reachability order;
- secret/public reachability sets;
- degree and wall-port demand per room;
- room interior demand from encounters/features;
- constructive embedding order and required bands.

Validation recomputes these facts; it does not trust booleans in the certificate.

## 7. Physical feasibility without correctness-by-backtracking

A valid abstract graph does not automatically imply the requested rectangle contacts
or a compact crossing-free drawing. Tier A therefore supports a constructive physical
class and computes required bounds before emitting geometry.

### 7.1 Constructive layout

- Critical-path rooms occupy ordered backbone columns.
- Branch paths occupy dedicated bands above or below their attachment.
- A loop/bypass occupies a reserved band over its interval.
- Every corridor receives a reserved channel in that construction.
- Rooms are expanded before placement to satisfy interior and boundary-port demand.
- Floor bounds are the exact union of allocated columns/bands plus rock margin; a
  caller-supplied maximum is checked against this computed requirement.

The baseline construction may be spacious and plain, but it always realizes the
supported certificate. Seeded search may later compact it or vary orientation; failure
of that optional optimization falls back to the constructive layout.

### 7.2 Room demand arithmetic

For each room, deterministic code derives:

- minimum interior width/height/area from the size band;
- encounter footprint and circulation cells;
- reserved cells for blocking features/hazards;
- number and width of connection openings;
- required wall clearance between openings.

For a rectangular room of width `w`, height `h`, opening width `o`, and clearance `c`,
a necessary perimeter check is:

```text
available_boundary_cells = 2w + 2h
required_boundary_cells >= port_count * o + separation_clearance
```

The constructive layout uses side-specific port counts, which is stronger than the
perimeter lower bound, and expands `w` or `h` until every assigned side fits. Interior
validation separately checks that usable cells after reserved features satisfy the
encounter demand.

Direct shared-wall doors are a geometry choice only when the construction assigns two
rooms adjacent compatible sides. A model-requested connection remains realizable as a
corridor with explicit openings; Tier A does not require an arbitrary rectangle-contact
graph, because not every planar graph is a rectangle-contact graph.

### 7.3 Why validation still exists

Constructive proofs establish that a solution should exist. Independent raster/grid
validation catches implementation defects such as an off-by-one bound, wrong opening,
room overlap, corridor contact, disconnected walkable cell, or secrecy leak. A
validator failure is an engine bug/regression, not a cue to ask the model for another
random graph.

## 8. Coherence and feature realization

Mathematics can prove connectivity and spatial feasibility; it cannot prove that a
story is interesting. Coherence is handled in layers:

- the model supplies each room's purpose and its relationship to progression;
- the compiler requires every mandatory room to occur on the critical path or a
  declared branch/loop;
- gates reference reachable dependencies;
- encounter intent reserves room capacity but does not compose stat blocks yet;
- traps are room/connection annotations with trigger/effect completeness;
- features reserve typed spatial demand and receive deterministic anchors;
- the guide is keyed to exact server IDs after geometry exists, but uses separate entry-first sequential presentation numbers;
- every room receives a concise read-aloud block and locally grouped actionable door state, checks, clues, scene pressure, triggers, consequences, features, puzzles, and objectives; ordinary map-visible connectivity and separate sensory/purpose repetition are omitted;
- read-aloud contains only player-observable information; setting terms resolve to concrete player-visible objects and operations; every interaction has one physical setup, trigger, effect, recovery, and repeated-failure result where relevant; traps distinguish visible warning, actual trigger, detection method, disable operation, and effect while code owns numeric difficulty; and any cross-room mechanism states its exact shared state plus whether an alarm has a responder;
- fixed-prompt DM rubrics measure progression, variety, clue logic, and prep usefulness.

Optional guide enrichment is separate from structural generation. Its failure leaves a
valid draft with explicit readiness blockers rather than deleting the map.

The fixed dungeon-guide review packet is the bridge between structural correctness and
actual DM usefulness. It freezes one synthetic prompt, plan, seed, exact guide, DM map,
and player map so human review can identify whether a technically valid draft is readable,
secret-safe, coherent, and runnable without inventing missing material at the table.
Worksheet findings become bounded code/content corrections and objective regression tests;
the packet itself is neither user campaign content nor a long-term publication format.
Passing it justifies proceeding to Tier B/C stress and later live-model canaries—it does
not claim universal dungeon quality.

## 9. Stress ladder

Do not jump from Tier A directly to arbitrary huge graphs.

### Tier A — dependable small dungeon

One floor, 4–8 rooms, bounded branches, one loop, one gate, one secret route, simple
encounter/feature demand. Target: 100% provider-free structural success over generated
plans/seeds and zero exceptions/leaks.

### Tier B — vertical composition

Two to four independently certified floors connected by stairs/ladders. Validate paired
endpoints, global entrance/objective reachability, directional concealment, and gate
progression across floors.

### Tier C — dense supported graphs

Exercise:

- a giant hub room with many branches;
- the maximum ports on each wall and forced room expansion;
- long critical paths;
- multiple disjoint and nested loops;
- high encounter/feature interior demand;
- narrow caller maximum bounds;
- many secret optional wings;
- gates whose dependencies sit on branches or loop bypasses.

### Tier D — general planar topology

Only if real use requires it, replace/extend the series-parallel grammar with a proven
planarity test, combinatorial embedding, vertex-box expansion for high degree, and a
known orthogonal drawing algorithm. This is where a mature graph library or solver may
be justified. Do not disguise unsupported nonplanar graphs as random routing failures.

### Tier E — limits and explicit impossibility

Test nonplanar requests, incompatible fixed room positions, impossible maximum bounds,
insufficient room perimeter, overfull encounters, and mutually blocked gates. Return
proof-oriented diagnostics or recommend another floor; never exhaust random retries.

## 10. Ordered implementation slices

### R0 — Architecture and characterization

- Adopt this plan and update the main architecture/status.
- Add active-path regressions for the observed assertion and out-of-bounds defects.
- Record current active-path success rates without live provider calls.

### R1 — Alpha V1 collapse and dead-code deletion

- Delete old model-generation orchestration and old generator/package dispatch.
- Rename active public contracts without numeric suffixes and pin all active roots to
  V1.
- Delete obsolete compatibility tests, known-bad baseline artifacts, and synthetic
  database assumptions; regenerate only useful V1 fixtures.
- Break the modeling/orchestration circular import.
- Restore a green package/unit baseline.

### R2 — `DungeonPlan` and topology certificate

- Introduce the small path/branch/loop creative contract.
- Build graph/certificate deterministically from the grammar.
- Add graph, gate, secret, degree, and demand properties.

### R3 — Constructive Tier A layout

- Materialize backbone columns, branch/loop bands, room sizing, ports, and reserved
  channels from the certificate.
- Keep optional seeded compaction separate from the guaranteed baseline.
- Require 100% success and zero exceptions across generated Tier A plans/seeds.

### R4 — Prompt and guide integration

- Expose only `submit_dungeon_plan`, with direct proposal fields at the tool root and no
  redundant proposal wrapper.
- Remove arbitrary edge authoring and topology repair from the model prompt.
- Build the exact guide after package generation; optional enrichment fails
  independently.
- Characterize schema failures against the actual model-visible root, preserve all valid
  prior content through the one repair, and fail before publication on measured output or
  cumulative token overage.
- Exercise CLI/web/faux-provider atomic publication.

### R5 — Quality and stress gate

- Add fixed prompt semantic/DM rubrics and the Tier B/C stress ladder.
- Resume opt-in live canaries only after provider-free and faux gates pass and the human
  review worksheet records explicit pass/fail decisions for every dimension. Ordinary
  rollout also requires evidence that requested output ceilings bound reported usage;
  the sole exception is one frozen, explicitly acknowledged, non-production Tier A
  canary that retains the measured cumulative ceiling and durable override lineage.
- Resume asset/print polish only after Tier A is dependable.

## 11. Stop/handoff rule

Every slice must leave `PROJECT_STATUS.md` with the exact completed/WIP item, changed
files, commands and results, known failures, working-tree state, and one next action.
Never leave both old and new generation paths half-supported. If a deletion slice cannot
finish, keep the old path intact and record the precise seam rather than committing a
mixed compatibility state.
