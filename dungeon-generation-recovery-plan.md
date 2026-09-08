# Dungeon Generation Alpha Reset and Recovery Plan

> Active focused plan for P7-14. It supersedes new P7-13 output/print work until the Tier A gate
> passes. Current execution state belongs only in [`PROJECT_STATUS.md`](PROJECT_STATUS.md).

## 1. Recovery Goal

Reliably turn one bounded structural proposal plus separately bounded task-specific enrichments into a
coherent, connected, playable, secrecy-clean Tier A dungeon through deterministic construction.

Retain the pure `dm_dungeon` package, Workbench preparation lifecycle, private model transport,
validation/rendering, and atomic publication. Do not restore arbitrary model-authored graphs,
place-and-route correctness retries, a monolithic guide-writing call, or parallel legacy contracts.

## 2. Alpha V1 and Retention

Before retained user data or external consumers:

- the structural tool is `submit_dungeon_plan` V1;
- `DungeonPlan`, `TopologyCertificate`, `LayoutRequest`, and `DungeonPackage` are the only active
  generation layers;
- public names and dispatch have no V2/V3/V4 variants;
- obsolete synthetic fixtures and disposable database artifacts are regenerated rather than read
  through compatibility branches;
- active V1 schema, prompt, compiler, generator, renderer, exporter, and review-packet pins evolve in
  place.

Declare the retention gate in both project status and architecture no later than the first
intentionally retained real-user artifact/campaign, external consumer, non-disposable deployment, or
promised replay requirement. After that point, incompatible changes require explicit reader,
migration, replay, and rollback policy.

## 3. Tier A Scope

A Tier A dungeon contains:

- one floor and 4–8 rooms;
- exactly one entrance and one final objective;
- one ordered critical path;
- zero to two branch paths and at most one loop/bypass;
- ordinary doors/passages and at most one secret route;
- at most one gate with its key/clue reachable before the gate;
- bounded room-local traps, features, and encounter slots;
- rectangular rooms, one-cell openings, and orthogonal one-cell corridors;
- a concise runnable DM guide and secrecy-clean DM/player SVG and PNG.

Excluded from this gate: multiple floors, arbitrary graph edges/polygons, encounter stat-block
composition, exact-scale print, and unconstrained feature packing.

## 4. End-to-End Boundary

```text
DM prompt + authorized DungeonGenerationContext + server seed
    -> submit_dungeon_plan (one structural call, at most one schema repair)
    -> validate progression and content slots
    -> deterministic graph construction and TopologyCertificate
    -> constructive orthogonal layout and exact DungeonPackage
    -> independent topology, geometry, dependency, and secrecy validation
    -> separate exact-ID enrichment tasks
    -> deterministic guide assembly and final readiness/cohesion review
    -> atomic draft publication
```

A structural plan does not contain complete puzzle, exploration, trap, feature, objective, or room
narrative prose. Deterministic bugs never trigger a request for a different random topology. Failed
enrichment preserves the accepted map and prior content with truthful readiness blockers.

## 5. Structural Tool Contract

The model supplies narrative identity, room purposes, critical path, bounded branches/loop, gate and
secret intent, named objective, and conservative content slots. Proposal fields are direct tool
arguments; there is no nested `proposal` wrapper or `guide_content` field.

Rules:

- local refs relate plan elements but are not canonical IDs;
- code derives stable IDs, exact graph edges, room demand, dimensions, visibility, and geometry;
- every non-null `rooms[].encounter` reserves one later authoring task;
- requested exploration challenges map one-to-one to `encounter = "exploration"` in the requested
  room/branch and include one local feature affordance;
- unrelated encounter slots remain null;
- each room has at most one nonempty room-content record;
- only the named objective room has a non-null objective;
- one rejected schema submission may receive one repair containing the complete original instruction,
  bounded prior arguments, and safe actionable diagnostics;
- accepted tool arguments are the structured result; no duplicate final prose response is requested.

The compact result reports only acceptance, hashes, graph/content counts, certificate version,
warnings, or at most eight stable diagnostics. It never returns provider bodies or exact geometry.

## 6. Budgets and Provider Transport

Each structural or enrichment task has its own profile, effort, instruction/schema pins, monotonic
deadline, output and cumulative token ceilings, and at most one budget-reserved repair. A repair starts
only when its complete estimated input leaves output room inside measured remaining budget. Its
effective output ceiling is the lesser of the task ceiling and the workflow budget remaining after
initial measured usage and estimated complete repair input. Body-free overage reports identify the
initial or repair submission and retain prior measured usage, request budget, estimated repair input,
and effective ceiling so that arithmetic is inspectable without provider bodies. Unknown or over-limit
usage fails closed before publication.

Codex subscription does not currently expose a supported pre-consumption output-token field, so the
gateway omits `max_output_tokens`, `max_tokens`, and `max_completion_tokens` and does not advertise
`hard_output_token_limit`. Standard OpenAI API-key transport advertises that capability only because
provider-free payload tests prove it sends the supported limit. Every transport still obeys strict
measured publication ceilings; there is no advisory bypass. Live calls require explicit authorization.

## 7. Topology and Constructive Layout

Tier A constructs a connected series/parallel-with-spurs graph:

1. The critical path forms the entrance-to-objective backbone.
2. Each branch attaches one ordered path to an existing backbone room.
3. One optional loop adds a supported bypass interval.

For a connected floor, validators recompute:

```text
cycle_rank = edge_count - room_count + 1
```

Every requested branch, loop, gate, and secret route has a concrete witness. Gate progression uses
repeated reachability with closed gates and requires each dependency before its gate.

Layout consumes the certificate rather than searching for correctness:

- backbone rooms receive ordered columns;
- branches and loops receive reserved nonintersecting bands;
- connections receive side-specific ports and channels;
- rooms expand to satisfy boundary-port and usable-interior demand;
- required bounds are computed before cells are emitted;
- optional seeded compaction may vary a proven layout but falls back to the baseline.

Validator failure is an engine regression, not normal random failure. The detailed proof and code map
live in [`packages/dungeon-engine/src/dm_dungeon/validation/TOPOLOGY_MATH.md`](packages/dungeon-engine/src/dm_dungeon/validation/TOPOLOGY_MATH.md).

## 8. Staged Enrichment and Continuity

After exact geometry exists, Workbench-owned tasks independently author:

1. puzzle mechanics;
2. exploration challenges;
3. feature interactions;
4. traps;
5. objective adjudication;
6. bounded room narratives after local mechanics are accepted.

Every task receives only its exact package/room/slot IDs, local geometry, relevant approved intent,
and bounded prior summaries. It cannot change topology, geometry, visibility, numeric difficulties,
another task's accepted content, approval state, or canon.

Trusted code derives one bounded creative-continuity projection from the accepted structural plan and
resolved dungeon context. Every task pins the same version/hash but sees only relevant authorized
facts and sources. Stale hashes, unauthorized facts, broader-visibility sources, unsupported
citations, or campaign lore in standalone mode fail before dispatch.

A pure planner selects the next exact target in deterministic order. A one-step coordinator accepts
only a matching trusted task policy; a bounded chain repeats that primitive, advances only accepted
children, and stops on completion, blocking, rejection, policy exhaustion, or its hard task limit.
No coordinator approves preparation or commits canon.

## 9. Final Gate and Quality Evidence

Before prompted preparation approval, a pure final gate recomputes:

- creative-continuity and exact source inheritance;
- topology, geometry, gate, and guide dependencies;
- required content/readiness and exact slot/lineage coverage;
- typed cross-task references;
- player-map secrecy.

A separate non-authoritative cohesion report covers thematic reinforcement, history/environment
causality, mechanic/objective unity, progression, intentional motif variation, and selected-lore
consistency. It may identify exact evidence and recommend one existing targeted seam; it cannot edit,
clear blockers, approve, or write canon. The DM disposition binds exact report/specification hashes,
covers every dimension/finding, and blocks approval when regeneration remains requested.

The fixed archive review packet is a technical regression, not the quality oracle. Quality evidence
must cover at least three materially different synthetic settings and interaction styles, opaque
prompt/model/effort variants, body-free run measurements, and blinded human ratings for cohesion,
clue logic, agency, puzzle comprehensibility, exploration quality, and preparation usefulness. At
least one staged live artifact must be preparation-ready. Synthetic evaluator arithmetic is not
quality evidence.

Use GPT-5.6 Luna as the default dungeon-authoring baseline. Change code after a Luna failure only
when the fix expresses a provider-independent contract, validation, or usability requirement. A
matched GPT-5.6 Terra comparison becomes eligible when the same Luna failure mode appears in at least
two materially different fixed synthetic cases and the existing general contract already expresses
the requirement, so another change would be model-specific, weaken the contract, or add
fixture-shaped complexity. Keep prompt, effort, budgets, and case assignment matched; do not add an
automatic fallback or promote Terra without measured quality improvement. Every live comparison
still requires explicit authorization.

The provider-free exploration-overage protocol binds the frozen canary and all three materially
different Tier A eval cases to one hash of the exact exploration instruction, tool/schema, fast-effort
profile, 2,048-output ceiling, 6,000-token cumulative budget, and one-repair policy. The schema has
the same bounded shape for every case—2–6 observable cues, 2–4 approaches, escalation, and
recovery—and no case adds output fields or cardinality, so one 2,510-token result does not establish a
provider-independent contract defect or justify raising the ceiling.

A second result counts as the same failure only when body-free evidence matches the fixed case hash,
Luna variant-assignment hash, and task-contract hash; reports the exact exploration output-budget
code at model submission with measured output above 2,048 while total measured usage remains within
6,000; and confirms no repair or artifact publication. Two distinct curated case IDs meet only the
repeat gate for considering a matched comparison; the provider-specificity judgment, measured quality
requirement, and explicit live authorization remain separate. The current canary supplies one such
observation, so the repeat gate remains at one of two.

Fixed-case task execution is reproducible rather than ad hoc. For all six staged seams, deterministic
code derives the trusted policy from the packaged frozen manifest and exact current parent, persists
the complete policy/profile in a private eval-run context envelope, and retains body-free case,
parent, policy, context, profile, assignment, and contract hashes. The operator command runs exactly
one next task. Only a failed wrapper with every pin unchanged may resume; pre-boundary attempts that
lack these pins are not silently treated as replayable.

## 10. Stress Ladder

- **Tier A:** dependable one-floor 4–8 room dungeon; 100% provider-free structural validity, zero
  exceptions, and zero player leaks.
- **Tier B:** two to four independently certified floors with paired vertical transitions and global
  progression.
- **Tier C:** high port/interior demand, longer paths, multiple supported loops, constrained bounds,
  secret wings, and branch dependencies.
- **Tier D:** general planar topology only if real use justifies a proven planarity/orthogonal drawing
  algorithm or solver.
- **Tier E:** explicit impossibility diagnostics for nonplanarity, incompatible locks, insufficient
  bounds/perimeter, overfull rooms, and mutually blocked gates.

Do not begin Tier B/C until Tier A has a preparation-ready live artifact and dependable multi-case
human evidence.

## 11. Ordered Slices

- **R0 complete:** architecture, characterization, and active-path regressions.
- **R1 complete:** one suffix-free alpha V1 and dead-code deletion.
- **R2 complete:** `DungeonPlan`, graph construction, and topology certificate.
- **R3 complete:** constructive Tier A layout and property coverage.
- **R4 complete:** structural prompt integration, bounded repair, and readiness-blocked publication.
- **R5 active:** staged enrichments, continuity/final gates, multi-case evidence, and preparation-ready
  live Tier A quality proof.

Current R5 state and the single next action live only in `PROJECT_STATUS.md`. Resume output catalog
and print work only after the Tier A gate passes.
