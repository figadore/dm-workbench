# Dungeon Generation Alpha Reset and Recovery Plan

> Status: active. This plan supersedes new P7-13 feature work until the Tier A gate
> passes. There are no retained user dungeons or external dungeon consumers. Synthetic
> and live-canary alpha artifacts are disposable. Collapse the implementation to one
> honest V1; do not preserve unused V1/V2/V3/V4 generation paths.

## 1. Product reset

The next milestone is not “support every dungeon primitive.” It is:

> One bounded structural model submission plus separately bounded, task-specific
> enrichments reliably become a coherent, connected, playable, secrecy-clean Tier A
> dungeon through deterministic construction.

Keep the pure `dm_dungeon` package, Workbench/preparation boundary, private model
transport, deterministic validation/rendering, and atomic publication. Replace the
model-authored arbitrary graph and place-then-route layout strategy.

Pause asset-catalog polish, print re-enable, additional mechanics, campaign grounding,
and broad live-provider suite execution until Tier A passes provider-free and
faux-provider gates. Do not compensate for a coupled or defective workflow with more
retries or an unmeasured larger model. Controlled model/effort comparisons are part of
the staged Tier A quality evaluation after structural and enrichment responsibilities are
separated.

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
DM prompt + authorized narrow structural context + server seed
    |
    v
one structural model tool call: submit_dungeon_plan(proposal fields at root)
    |
    v
validate the small progression/content-slot contract
    |
    v
deterministic topology compiler
    |-- build graph from critical path / branches / loop grammar
    |-- assign IDs and connection semantics
    |-- place gates, keys, secrets, and reserved content demand
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
independently bounded enrichment calls over exact package IDs
    |-- puzzle task with puzzle-only context and contract
    |-- exploration task with exploration-only context and contract
    |-- other requested interaction tasks
    `-- observable room narratives after mechanics are accepted
    |
    v
deterministic guide assembly and readiness validation
    |
    v
atomic preview/assets/specification publication as a draft
```

The accepted structural tool arguments are the first model result. The model is not asked
for a duplicate text answer. A schema-invalid structural call may receive at most one
bounded repair with the original request and safe diagnostics. A structurally accepted
plan is not sent back to the model for topology or geometry repair: code owns those
steps. Each enrichment has a separate typed task context, schema, budget, repair policy,
and lineage; it cannot alter topology or another accepted enrichment and may fail with a
truthful readiness blocker while preserving the valid map.

## 5. Model tool contract

The structural model expresses narrative identity, progression, and bounded content slots,
not an arbitrary edge list or complete guide. The structural
`DungeonGenerationProposal` fields are the `submit_dungeon_plan` tool arguments directly;
there is no additional `proposal` envelope and no prose-heavy `guide_content` field around
or beside them. Structural schema diagnostics and the one bounded repair therefore
operate on `/plan` and other actual structural root paths and must never tell the model to
delete a valid proposal merely because an adapter added an avoidable wrapper.

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
- read-aloud contains only player-observable information; puzzles and exploration scenes expose understandable clues or affordances, meaningful stakes/consequences, and room for reasonable approaches; interaction prose includes only the mechanism and reset/retry details needed to adjudicate that scene rather than defaulting to linked devices, alarms, or one prescribed manipulation; traps distinguish visible warning, actual trigger, detection method, disable operation, and effect while code owns numeric difficulty;
- fixed-prompt DM rubrics measure progression, variety, clue logic, and prep usefulness.

Guide enrichment is separate from structural generation and separated again by creative
responsibility. Puzzle and exploration design never share the structural call or each
other's broad context. Their failure leaves a valid draft with explicit readiness blockers
rather than deleting the map.

The fixed dungeon-guide review packet remains a renderer, secrecy, deterministic assembly,
and contract-expressiveness regression. It is no longer the quality oracle: repeated
human rewrites of one synthetic archive prove only that the contract can represent
hand-authored content and risk overfitting prompts and fields to one mechanism. Do not add
a prompt rule or schema field solely because that fixture needed it unless the rule is a
general invariant or reproduces in another independent case.

Actual generation quality is measured over at least three materially different synthetic
Tier A settings/interaction styles and at least one staged live Tier A artifact. Blinded
human review compares prompt variants, supported effort levels, and model sizes for clue
logic, player agency, puzzle comprehensibility, exploration quality, prep usefulness,
latency, token use, schema validity, and repair rate. A larger model or deeper effort is
selected only when those measurements justify it. Tier B/C test scalability and remain
deferred until this staged Tier A path produces a usable live artifact.

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

### R4 — Structural prompt integration

- Expose only structural `submit_dungeon_plan`, with direct proposal fields at the tool
  root, no redundant proposal wrapper, and no prose-heavy guide payload.
- Remove arbitrary edge authoring, detailed puzzle/exploration authoring, and topology
  repair from the structural model prompt.
- Characterize schema failures against the actual model-visible root, preserve all valid
  prior content through the one repair, and fail before publication on measured output or
  cumulative token overage.
- Exercise CLI/web/faux-provider structural publication with truthful readiness blockers.

### R5 — Task-specific enrichment and Tier A quality gate

Current staged seam: exact-package puzzle context slicing, exact-ID output validation,
and deterministic room-guide projection are implemented. One independently pinned faux-
provider puzzle task has its own effort/profile, schema, token/output budget, and one
budget-reserved repair. Accepted content is retained in a DM-only atomic child version;
failed attempts keep the parent/map and persist only compact diagnostics on the existing
run surface. Exploration separately has an exact-ID contract, trusted local-geometry/affordance
context builder, semantic validator, independently pinned faux-provider dispatch and one
budget-reserved repair, accepted-content lineage, deterministic guide projection, and
atomic DM-only child publication. Success preserves package/map hashes, accepted puzzle
content/lineage, and unrelated blockers; failure leaves the puzzle parent current and
persists only compact diagnostics. The separate feature-interaction contract joins one
exact package feature marker to its current guide entry and local room geometry, rejects
foreign package/room/feature IDs and cross-task mutation, and projects setup, multiple
affordances/consequences, and optional reset/retry guidance into only that feature. Its
independently pinned faux-provider dispatch has a task-specific profile, prompt/schema,
6,000-token cumulative and 2,048-output budget, and one budget-reserved repair. Accepted
content and lineage publish atomically in a DM-only child while preserving package/map
hashes, accepted puzzle/exploration content and lineage, other features, and unrelated
blockers; failure leaves the exploration parent current and stores no rejected body. The
trap seam joins one exact room-trap marker/current guide entry to local geometry and
deterministic detection/disable arithmetic, rejects foreign IDs plus structural/cross-task
mutation and numeric-DC authorship, and projects warning, trigger/effect,
detection/disable counterplay, consequences, and optional recovery into only the selected
trap. Its independently pinned faux-provider dispatch has a task-specific profile,
prompt/schema, 6,000-token cumulative and 2,048-output budget, and one budget-reserved
repair. Accepted content and lineage publish atomically in a DM-only child while
preserving package/map hashes, prior puzzle/exploration/feature content and lineage, other
traps, and unrelated blockers; failure leaves the parent current and stores no rejected
body. The objective seam joins one exact objective marker/current guide entry and local
geometry to bounded summaries copied from selected accepted puzzle, exploration, feature,
and trap mechanics. It rejects foreign exact IDs and structural or cross-task mutation,
then projects only observable goal, adjudication, multiple resolutions, and
setback/aftermath into the objective. Its independently pinned faux-provider dispatch has
a task-specific profile, prompt/schema, 6,000-token cumulative and 2,048-output budget,
and one budget-reserved repair. Accepted content and lineage publish atomically in a
DM-only child while preserving package/map state, prior content and lineage, other guide
entries, and unrelated blockers; rejection or publication failure leaves the trap parent
current and stores no rejected body. The provider-free homogeneous room-narrative seam
now slices up to eight exact rooms to local geometry, bounded existing room guide state,
tone/constraints, and only player-observable summaries copied from accepted puzzle,
exploration, feature, trap, and objective content. Its strict output contains only concise
read-aloud and observable framing. Validation rejects foreign, duplicate, or omitted
rooms, and projection fills only selected blank narratives and removes only their room
blockers while preserving all mechanics, objective content, package/map state, other
guide entries, and unrelated blockers. Its independently pinned faux-provider dispatch
has a task-specific profile, prompt/schema, 6,000-token cumulative and 2,048-output
budget, and one budget-reserved repair. Accepted content and lineage publish atomically in
a DM-only child while preserving package/map bytes, every prior enrichment and lineage,
unselected room state, and unrelated blockers; rejection or publication failure leaves
the objective parent current and stores no rejected body. A provider-free staged planner
now orders exact puzzle, exploration, feature, trap, objective, and bounded narrative
targets from package slots, current guide state, and accepted lineage; it skips completed
tasks and fails closed on inconsistent or unsupported state. A provider-free one-step
coordinator now requires an exact task-specific trusted policy, invokes only the selected
existing bounded seam, and replans an accepted current child; rejection preserves the
parent and cannot dispatch the next task. Resumed exploration policy includes the exact
planned encounter-slot ID: acceptance publishes one exploration child and replans the next
feature, while a slot mismatch makes no provider call and no version. Broader resumed
feature/trap/objective/narrative coverage and chain repetition remain pending. No live
provider was contacted, and no redaction/logging subsystem or new persistence store was
added.

The provider-free continuity foundation now derives and persists one bounded dungeon-only
self-hashed projection from the resolved `DungeonGenerationContext` and accepted structural
plan. Puzzle, exploration, feature-interaction, trap, and objective contexts inherit its
exact version/hash while selecting only relevant authorized lore, premise/themes, room/
progression/objective intent, history/environment facts, tone, motif-variation constraints,
and exact cited sources. Their accepted lineages and generation-run metadata pin the
shared hash. Deterministic objective projection rebuilds its exact room, selected facts,
accepted-mechanic summaries, plan, package, guide target, and continuity pin. Stale hashes,
unauthorized fact IDs, broader-visibility sources, and campaign lore in standalone mode fail
closed; absent standalone lore remains unknown.

Required before chain repetition or live Tier A: carry this same projection through
room-narrative contexts and lineages without turning it into a universal optional-field
context or unrestricted corpus/guide dump.

After required enrichment, run deterministic continuity/source/lineage/dependency/secrecy
validation and produce a DM-facing whole-dungeon cohesion report. A separately budgeted
read-only reviewer may diagnose thematic reinforcement, history/environment causality,
mechanic/objective unity, progression, motif variation, and selected-lore consistency, but
cannot edit, approve, clear blockers, or write canon. Findings are explicitly dispositioned
or sent to one targeted enrichment seam. Multi-case blinded human evidence remains the
quality authority.

- Add independently bounded puzzle, exploration, other interaction, and narrative tasks
  over exact package IDs; merge accepted output deterministically and preserve the map on
  partial failure.
- Replace single-archive prompt iteration with multi-case semantic/DM rubrics and blinded
  prompt/model/effort comparisons. Rate thematic reinforcement, history/environment
  causality, mechanic/objective unity, progression, intentional motif variation, and
  selected-lore consistency in addition to playability and preparation usefulness. Keep
  the archive packet only as a technical regression.
- Resolve hard provider output-cap behavior, then run the frozen staged Tier A canary after
  provider-free and faux gates pass. Ordinary rollout requires evidence that requested
  output ceilings bound reported usage; the sole exception remains one frozen, explicitly
  acknowledged, non-production Tier A canary that retains the measured cumulative ceiling
  and durable override lineage.
- Defer Tier B/C until the staged live Tier A path produces a usable preparation-ready
  artifact and the bounded Tier A evaluation set is dependable.
- Resume asset/print polish only after Tier A is dependable.

## 11. Stop/handoff rule

Every slice must leave `PROJECT_STATUS.md` with the exact completed/WIP item, changed
files, commands and results, known failures, working-tree state, and one next action.
Never leave both old and new generation paths half-supported. If a deletion slice cannot
finish, keep the old path intact and record the precise seam rather than committing a
mixed compatibility state.
