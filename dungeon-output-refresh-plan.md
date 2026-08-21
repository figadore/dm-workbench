# Dungeon Output Refresh Plan

> Status: active planning baseline for the user-directed Dungeon Studio refresh.
> No user dungeon or external dungeon consumer currently requires backward
> compatibility. Until one exists, active V2 contracts may advance in place with new
> version pins and updated synthetic fixtures; retained artifacts, once created, remain
> immutable and readable under their pinned readers.

## 1. Problem statement and confirmed causes

The screenshot inspected for this plan was:

`/Users/reese/Screenshots/Screenshot 2026-08-18 at 7.31.33 AM.png`

It shows several different defects superimposed: a short bent connection rendered as
an outlined box, corridor footprint overlap at room boundaries, a numbered room-name
label, and a raw opaque room ID occupying nearly the same position.

| Symptom | Confirmed implementation cause | Required correction |
| --- | --- | --- |
| Short room links look like `L` shapes or boxes | The baseline router chooses room-center boundary anchors, then breadth-first routes the shortest orthogonal centerline. It does not penalize bends near an endpoint or distinguish a direct door from a corridor. The renderer outlines the rasterized corridor cells, making a one-cell dogleg look like a small room. | Give direct doors and passages different geometry. Score bends and endpoint approach direction explicitly. |
| A connection appears to enter/intersect a room | Corridor rasterization includes boundary endpoints and the geometry validator deliberately permits overlap with either connected room. A door is emitted only on the source-room end of a routed “door corridor.” | Model explicit endpoint openings, clip corridor wall outlines at room boundaries, and prohibit corridor interior overlap except for validated openings. |
| Rooms all appear separated by a five-foot sliver | Placement currently applies one cell of padding to every room pair, including rooms connected by a direct door. | Remove the universal gap. Direct-door rooms share a wall; passage-linked rooms have explicit corridor space; unrelated rooms retain one cell of solid-rock clearance. |
| Text overlaps and raw values such as `v2-room-cf3018dc2acee8f03031` are visible | DM previews enable `show_room_ids`, while the Workbench also adds numbered room-note labels at room centers. Label placement has no collision handling. | Never show opaque IDs by default. Use short stable callouts and collision-aware placement linked to a DM key. |
| Doors do not communicate secret/locked/trapped state or difficulty | `DoorType` is one exclusive enum; lock gates have dependencies but no display mechanics or difficulty; secret/trapped symbols are only `S`/`!`; ordinary and locked doors share the same visual class. | Add composable door mechanics, deterministic difficulty policy, consistent glyphs/badges, and keyed DM details. |
| Traps, puzzles, and other requested features have no map markers or useful descriptions | V2 can create a topology trap ID, gate, key, or clue, but generated `DungeonPackage.features`, `hazards`, `zones`, `labels`, and `encounter_slots` are initialized empty. The compact design contract has no bounded trap/puzzle/feature description shape. | Add a new versioned creative contract, deterministic marker placement, and Workbench-owned prose/key entries. |
| Assets are an unorganized list such as `manifest #0` and `dm_png #0` | The detail template loops raw artifact-role records and exposes persistence role/ordinal values directly. | Build a presentation projection grouped by floor, audience, and purpose; hide technical manifests under an advanced section. |
| Most assets download instead of opening in the browser | The asset route uses `inline` only for `image/*`; PDF, text, SVG-document handling, and JSON inspection are not purpose-specific. | Add explicit Open, Preview, and Download actions with safe media-specific response policy. |
| Downloads have UUID filenames | The generic asset route knows only the content-addressed blob ID and synthesizes `asset-<uuid>.<ext>`. | Address assets through artifact-version role links and derive safe names from dungeon title, version, floor, audience, and purpose. |
| DM notes download as `.bin` | Notes correctly use `text/plain`, but the web extension map has no `text/plain` entry. | Serve notes as a named `.txt` asset and test MIME/disposition/filename together. |
| Exact-scale print produces dozens of blank or sparse pages | The exporter tiles the full declared floor bounds (V2 bands are 28, 40, or 56 cells square) at exactly one inch per cell. It neither crops to occupied bounds nor estimates useful-content coverage. Whole-floor exact-scale output is generated automatically for both audiences. | Disable new print export first. Redesign around a reference-map mode and selected tactical regions with page estimates, crop bounds, coverage checks, and hard limits. |

## 2. Product and architecture decisions

### 2.1 Room spacing and connection geometry

There is **no universal five-foot gap between every room**.

The rule is semantic:

1. **Direct door:** the connected rooms share a wall. The door occupies one opening in
   that common wall. There is no synthetic corridor and no five-foot void.
2. **Passage/corridor:** the rooms are separated by explicit traversable corridor
   cells. Each endpoint approaches its room wall perpendicularly and terminates at a
   validated opening.
3. **Unrelated rooms:** retain at least one five-foot cell of solid-rock clearance so
   separate walls do not read as an undeclared opening and corridor routing remains
   unambiguous.
4. **L-shaped corridors:** allowed when geometry requires them, but a straight route is
   preferred, then a one-bend route. A bend may not occur in the doorway/opening cell
   or in the first clear corridor cell outside a room. Tiny endpoint doglegs are a
   validation failure, not an acceptable random style variation.
5. **Doors are not corridors:** if a requested direct door cannot be placed on a
   shared wall, placement retries or fails with a structured diagnostic. It must not
   silently become a hallway with a door at only one end.

### 2.2 Common visual language

Maps use short, stable, grayscale-safe callouts; full descriptions live in a keyed DM
panel/document.

| Component | DM-map token/symbol | Player map |
| --- | --- | --- |
| Room | Number in circle, e.g. `1` | Optional room number only when explicitly published |
| Door | Standard door break/leaf; optional `D1` key | Standard visible door geometry |
| Secret door | `D1` plus `S` badge / dashed concealed-wall mark | Omitted, or normalized to an ordinary door only under the existing one-sided publication rule |
| Locked door | `D2` plus padlock/`L` badge | Ordinary visible door; no lock DC unless deliberately published |
| Trapped door | Door callout plus `T` badge | No trap badge or trap metadata |
| Trap/hazard | Triangle callout `T1` | Omitted unless explicitly published |
| Puzzle/control | Diamond callout `P1` | Only the visible physical control, never the solution |
| Clue/key/treasure | `C1`, `K1`, or `$1` keyed marker | Only deliberately player-visible objects |
| Stair/ladder/portal | Distinct directional symbol plus paired endpoint key | Visible endpoint only under publication policy |
| Generic physical feature | Small shape-specific glyph plus `F1` when details exist | Visible geometry without DM-only details |

Map text is limited to callouts and deliberately published short names. Opaque package
IDs remain available in structured lineage and developer inspectors, never as default
map labels.

### 2.3 DM key and mechanics

The DM receives one organized map key per floor:

- **Rooms:** callout, readable name, role, dimensions/capacity, and room notes.
- **Doors and transitions:** endpoint rooms, visible type, secret-discovery difficulty,
  lock state, unlock/bypass difficulty, required key/clue, trap reference, and direction.
- **Traps/hazards:** marker, trigger, detection difficulty, disable difficulty, effect,
  consequence, and visibility.
- **Puzzles:** marker, presented mechanism, clues, solution, failure/consequence, and
  blocked connection/objective.
- **Features/objectives:** marker, readable description, interaction, and referenced
  room/zone.

The model may propose bounded creative descriptions and relative challenge bands.
Deterministic code maps bands through a pinned mechanics policy to exact displayed
values. Unknown details stay `unknown` and block “ready for play” when mechanically
required; code must not manufacture a missing trap effect or puzzle solution.

Geometry and marker IDs remain in `dm_dungeon`. Prose-heavy room, trap, puzzle, and
feature notes remain in the Workbench preparation specification and reference those
stable IDs.

### 2.4 Asset presentation and browser behavior

The page presents assets by user purpose, not storage role:

1. **Maps** — floor tabs/cards, DM and Player switch, inline primary PNG, Open full
   size, optional SVG under Advanced.
2. **DM guide** — inline readable map key/notes and Download `.txt`.
3. **Virtual tabletop** — Player Roll20 bundle as the primary download; DM bundle is
   clearly marked as containing secrets.
4. **Print** — Disabled/experimental until P7-13f passes; historical files stay
   downloadable with a warning.
5. **Technical lineage** — specification, validation report, manifests, hashes, and
   renderer pins in a collapsed Advanced section.

Safe filenames follow this shape:

`<dungeon-slug>-v<version>-<floor-slug>-<audience>-<purpose>.<ext>`

Examples:

- `flooded-archive-v2-keeper-level-dm-map.png`
- `flooded-archive-v2-keeper-level-player-map.svg`
- `flooded-archive-v2-dm-guide.txt`
- `flooded-archive-v2-flooded-archive-player-roll20.zip`

Images, trusted generated SVG, plain text, JSON inspectors, and PDFs get an explicit
**Open** action. Downloads use an explicit **Download** action. ZIP is always an
attachment. Responses retain `nosniff`; generated SVG/PDF inline handling receives a
restrictive content security policy.

### 2.5 Print policy

P7-13a will disable new exact-scale print generation until the redesign gate passes.
This is a centralized application capability policy, not merely a hidden button.
**Until P7-13a is implemented, current code still generates PDFs.** Historical PDF
assets are immutable and remain accessible.

The redesigned feature has two separate modes:

- **Reference map PDF:** one page (or intentionally bounded pages), fit to paper,
  clearly labeled “not miniature scale.”
- **Tactical tiles:** exact one inch per five-foot cell, but only for a selected room,
  encounter zone, or explicit crop. Whole-floor tactical export is available only
  when its preflight estimate is below the configured page and sparsity limits.

Before creating bytes, the UI shows crop dimensions, paper, audience, estimated tile
rows/columns/pages, and occupied-cell coverage. Export rejects excessive or mostly
blank output with a stable actionable diagnostic. It never silently creates dozens of
pages.

## 3. Version and compatibility policy

The screenshot is a generated quality baseline, not evidence of a retained user
artifact. There are currently no user dungeons or external dungeon consumers that
justify a parallel compatibility stack.

- Advance the active V2 design/proposal/compiler/package contracts and their version
  pins in place; update synthetic fixtures and tests rather than preserving unused
  pre-P7-13d V2 readers.
- Do not create parallel V3 design, topology, package, layout, renderer, or Workbench
  paths solely for compatibility. The useful temporary V3 WIP is migration scaffolding:
  port its intent shapes, mechanics policy, diagnostics, and tests into V2, then remove
  the V3-only files and dispatch.
- Preserve V1 orchestration only where its documented rollout/evaluation policy still
  requires it, not as retained-dungeon compatibility. Do not add new historical-reader
  branches without an artifact or consumer that needs them.
- Introduce new package/generator/renderer pins for changed connection geometry and
  map symbols. Exact version numbers are frozen in P7-13b/P7-13d before code lands.
- Introduce a new PDF request/exporter version before print is re-enabled.
- During this alpha development round, no user artifact or external consumer exists:
  patch active contracts/pins in place and discard/recreate synthetic local artifacts
  as needed. Once the first user artifact or consumer is explicitly declared,
  refreshing it creates a new immutable artifact version or a new artifact; it never
  mutates an existing version’s role links.
- Content-addressed blobs remain generic. Human filenames and grouping are a
  presentation projection over artifact-version links, not blob identity.

## 4. Implementation slices

### P7-13a — Output quality baseline and print fail-closed switch

**Goal:** make the current failure measurable and stop producing known-bad print jobs.

**Work**

- Add one synthetic retained-output regression fixture containing:
  - adjacent direct-door rooms;
  - a straight passage and an obstacle-forced one-bend passage;
  - secret, locked, and trapped access;
  - a trap, puzzle, clue/key, stairs, and generic feature;
  - a deliberately sparse large floor for print testing.
- Add renderer golden images/SVG assertions and an HTML asset-page snapshot/contract.
- Record objective presentation metrics: raw opaque IDs displayed, text collisions,
  corridor bends within endpoint clearance, corridor/room interior overlap, missing
  keyed mechanics, page count, blank-tile ratio, and inline/open/download behavior.
- Split the current all-at-once “PDF and Roll20 exports” command into explicit format
  selection at the application boundary.
- Add a centralized print capability state (`disabled`, reason, future capability
  metadata). Web, API, and CLI new-print requests fail with the same stable
  `dungeon_print_export_disabled` result. Roll20 export remains available.
- Show “Exact-scale print maps are temporarily disabled while sparse-page output is
  redesigned.” Historical PDF rows show “legacy/experimental” rather than vanishing.

**Likely files**

- `src/dm_assistant/orchestration/dungeons/contracts.py`
- `src/dm_assistant/orchestration/dungeons/service.py`
- `src/dm_assistant/web/routes.py`
- `src/dm_assistant/web/templates/dungeon_detail.html`
- focused package/unit/integration fixture and browser tests

**Done when**

- No supported surface can start a new PDF export while the capability is disabled.
- Roll20 export no longer depends on also generating two PDFs.
- Existing PDFs remain readable.
- The synthetic fixture reproduces and counts the current output defects.

### P7-13b — Connection semantics, compact placement, and geometry validation

**Goal:** make doors, passages, and room spacing geometrically intentional.

**Work**

- Freeze a new generator/package contract with explicit connection endpoint openings
  and approach direction.
- Make graph-guided placement connection-aware:
  - direct doors prioritize/shared-wall adjacency;
  - passage connections reserve routable exterior space;
  - unrelated rooms retain one-cell rock clearance;
  - scoring favors compact occupied bounds, not arbitrary floor-band spread.
- Replace unweighted endpoint BFS selection with deterministic multi-criteria routing:
  valid endpoint direction, endpoint lead clearance, fewest bends, shortest path,
  unrelated-room clearance, then seeded tie-break.
- Clip corridor fill/outline at room boundaries and cut explicit wall openings.
- For direct doors, emit no auxiliary corridor. For passages, emit openings at both
  endpoints; add endpoint doors only when the typed intent says an endpoint is a door.
- Strengthen validation:
  - no corridor interior overlaps any room interior;
  - every endpoint opening belongs to the intended room wall;
  - first/last segment is perpendicular to that wall;
  - no bend in the endpoint-clearance zone;
  - direct doors lie on one shared wall;
  - no undeclared opening or corridor-wall flush contact.
- Preserve deterministic replay and targeted-lock behavior under the new version.

**Likely files**

- `packages/dungeon-engine/src/dm_dungeon/layout/{placement,routing,engine}.py`
- `packages/dungeon-engine/src/dm_dungeon/contracts/{geometry,package}.py`
- `packages/dungeon-engine/src/dm_dungeon/validation/{geometry,grid}.py`
- package routing/layout/property/golden tests

**Done when**

- The regression fixture has no tiny endpoint doglegs or box-like direct doors.
- A direct door is one opening in a common wall.
- Passage bends are explainable by obstacles and are never adjacent to room endpoints.
- Occupied bounds and average connector length improve against the frozen baseline
  without reducing topology validity.

### P7-13c — Renderer visual grammar and collision-free annotation

**Goal:** make a map understandable at a glance without exposing internal IDs.

**Work**

- Implement the symbol/callout table in section 2.2 as code-owned theme primitives.
- Replace `show_room_ids` with explicit annotation modes:
  `none`, `callouts`, and authenticated developer IDs. Production DM previews use
  `callouts`; player previews use `none` unless publication says otherwise.
- Allocate stable short callouts deterministically by floor and component kind.
- Add deterministic label layout using candidate positions, measured text bounds,
  symbol/door exclusion zones, and leader lines only when needed.
- Keep long names and mechanics out of map geometry. Generate a legend/key projection
  that uses the same callout allocator as SVG/PNG.
- Ensure raster and PDF drawing support every trusted symbol identically.
- Add accessibility checks: grayscale distinction, minimum rendered size, no reliance
  on color alone, and text alternatives in web presentation.

**Likely files**

- `packages/dungeon-engine/src/dm_dungeon/rendering/{contracts,svg,themes}.py`
- `packages/dungeon-engine/src/dm_dungeon/export/{raster,pdf_drawing}.py`
- `src/dm_assistant/orchestration/dungeons/service.py`
- rendering snapshots and DM/player leak tests

**Done when**

- Default maps contain no `v2-room-*` text.
- The golden fixture reports zero annotation bounding-box collisions.
- Secret/locked/trapped states are distinguishable on the DM map and leak nothing to
  the player map.
- Every visible callout resolves to exactly one key entry.

### P7-13d — Doors, traps, puzzles, features, and a usable DM guide

**Goal:** carry requested preparation intent through to exact markers and readable DM
content.

**Work**

- Extend the active strict V2 design/proposal/compiler in place and advance its pins;
  do not create a parallel V3 path or retain an unused pre-P7-13d V2 reader.
- Continue from the committed scaffolding rather than resetting or reverting its
  commit: port the useful V3-shaped contracts, mechanics compiler logic, and tests into
  V2 first, then remove temporary V3-only modules/dispatch after equivalent V2 coverage
  passes.
- Add bounded creative intent for:
  - room tags and preparation notes;
  - physical features/objectives;
  - composable door concealment, lock, and trap intent;
  - traps/hazards with placement, trigger/effect concepts, and challenge band;
  - puzzles with mechanism, clue references, solution, and consequence;
  - explicit branch/loop requests and encounter-slot intent from the existing deferred
    V2 follow-up.
- Keep the model out of canonical IDs, exact coordinates, numeric dimensions,
  visibility policy, and trusted arithmetic.
- Freeze a capability matrix in the new version: same-floor passages have no hidden,
  barrier, or trap mechanics; same-floor doors support documented combinations of
  concealment, lock/puzzle gate, and trap; cross-floor stairs/ladders may have
  directional hidden endpoints and optional explicitly located source and/or destination
  endpoint-door/hatch mechanics. Those endpoint mechanics support the same documented
  concealment, lock/puzzle gate, and trap combinations; do not implicitly reinterpret
  the vertical transition itself as a door.
- Define the endpoint-door/hatch intent shape, deterministic endpoint anchor geometry,
  directional traversal/unlock semantics, and dependency references. Reject ambiguous
  placement, not a valid explicitly located cross-floor barrier or trap.
- Add a pinned deterministic mechanics policy mapping relative challenge bands to
  displayed discovery/unlock/disable values. Persist the policy/version in lineage.
- Evolve exact package contracts so door properties are composable rather than one
  exclusive enum and marker geometry has stable IDs. Include endpoint-door/hatch
  records for vertical links. Compile each supported mechanic independently;
  concealment must never cause a requested gate or trap to be dropped.
- Make the initial model instruction and bounded repair diagnostics capability-specific:
  hidden vertical links are valid, and vertical locks/puzzles/traps require the explicit
  endpoint-door/hatch shape. Diagnose omitted or ambiguous placement rather than reject
  a valid vertical barrier; never generically say secret stairs/ladders require a door.
- Deterministically place marker anchors inside the referenced room/zone or at the
  referenced connection endpoint; validate bounds, uniqueness, and reachability.
- Expand Workbench DM notes into a versioned DM-guide model with room, connection,
  trap/hazard, puzzle, clue/key, and feature sections. Store prose here, keyed to exact
  package IDs/callouts. Update the P7-13c symbol grammar as necessary so each compiled
  secret, gate, and trap mechanic is distinct on DM maps and absent from player maps.
- Fail preparation readiness when a requested lock lacks a bypass/key policy, a trap
  lacks an effect, or a puzzle lacks a solution. Report unknown rather than inventing.
- Render the guide inline and produce a portable UTF-8 `.txt` download.

**Likely files**

- `packages/dungeon-engine/src/dm_dungeon/contracts/design_v*.py`
- `packages/dungeon-engine/src/dm_dungeon/compiler.py` or a new versioned compiler
- package topology/geometry/package contracts and validators
- `src/dm_assistant/orchestration/dungeons/{contracts,service,prompting}.py`
- synthetic compiler, prompt, eval, and Studio tests

**Done when**

- The synthetic request’s lock difficulty, secret discovery, trap trigger/effect/DCs,
  puzzle clues/solution, and feature descriptions are visible in the DM guide.
- Stable map markers point to those entries.
- Player assets contain none of the DM-only mechanics, solutions, or hidden markers.
- Contract/compiler tests cover the entire capability matrix, including hidden
  stairs/ladders, secret locked/puzzle doors, secret trapped doors, and endpoint
  locks/puzzles/traps on vertical links; every accepted combination retains all
  requested gate/trap mechanics through compilation.
- The updated active V2 contract round-trips and the synthetic pre-P7-13d fixtures are
  deliberately migrated; future retained artifacts remain pinned and immutable.

### P7-13d.1 — Prompt-contract reliability and bounded-cost recovery

**Goal:** restore a cheap, reliable basic prompt-to-draft path after P7-13d expanded
its model-facing contract.

Live GPT-5.4 evidence exposed a boundary failure rather than a geometry failure: some
runtime cross-field rules were absent from the model-visible JSON Schema, schema
repair received neither the original prompt nor prior arguments, and optional advanced
content could invalidate the whole map. This task blocks P7-13e.

**Work**

- Remove duplicated concealment intent and derive it from directional hidden endpoints;
  deterministically default an omitted active-mechanic challenge to `moderate`.
- Move absent trap/puzzle prose and gate dependencies to truthful preparation-readiness
  blockers while retaining the requested mechanic and valid draft. Continue to reject
  contradictory refs, endpoint/floor semantics, duplicate identities, and invalid
  topology.
- Make basic prompts produce the smallest sufficient core design and omit unrequested
  advanced collections.
- Send schema repair the original prompt/context, bounded prior arguments, and
  actionable static diagnostics; require preservation of valid prior content and keep
  all bodies out of ordinary logs.
- Enable `pi-ai` JSON-schema constrained sampling as `prefer` only for contract-tested
  providers, retaining authoritative Python validation.
- Start with a 4,096 output-token and 12,000 cumulative measured-token ceiling; raise
  only the smallest amount justified by a required frozen case.
- Gate live use in stages: faux/provider contracts, one stop-on-failure Flooded Archive
  canary, then the fixed suite. Store metrics/hashes, never provider bodies.
- Keep one submission plus at most one repair. Consider a separately reviewed
  P7-13d.2 core-topology/optional-enrichment split only if the repaired one-call design
  still misses the P7-12g live thresholds at a worse measured total cost.

**Done when**

- The Flooded Archive canary preserves its small upper floor, larger hidden lower
  archive, secret descent, title/premise, and final Stone objective within the cap.
- The fixed live suite reaches at least 90% first-pass schema validity and 95% success
  after one repair; every repair remains about the original dungeon.
- Optional incomplete mechanics create a draft with explicit approval blockers rather
  than causing whole-dungeon loss, while hard topology contradictions still reject.
- No extra retry, larger default model, or provider response fixture masks a contract
  defect.

### P7-13e — Asset catalog, inline viewing, and meaningful filenames

**Goal:** replace the persistence-shaped asset dump with a task-oriented output page.

**Work**

- Add a Workbench `DungeonOutputCatalog`/presentation projection over immutable
  artifact-version links. It resolves floor name, audience, purpose, media type,
  ordinal, availability, safe filename, and whether Open/Preview/Download is allowed.
- Add artifact-version-scoped asset routes. Keep the old UUID route as a compatibility
  fallback, not the primary UI.
- Group the page into Maps, DM guide, Virtual tabletop, Print, and Advanced technical
  lineage. Use floor and DM/Player controls instead of role ordinals.
- Make the primary PNG visible inline at a useful size with Open full size in a new
  tab. Offer generated SVG as an advanced vector option.
- Open trusted SVG, PNG, plain text, JSON, and historical PDF safely in-browser. Keep
  ZIP attachment-only. Add explicit `?download=1` behavior rather than guessing from
  MIME alone.
- Derive safe filenames from title/version/floor/audience/purpose. Handle duplicate
  content hashes without losing role-specific filenames.
- Add `text/plain -> txt`; use UTF-8; sanitize CR/LF, quotes, slashes, Unicode edge
  cases, reserved names, and excessive length in `Content-Disposition`.
- Hide manifests and raw hashes by default, but retain them in Advanced for audit.

**Likely files**

- `src/dm_assistant/modules/preparation/{contracts,repository,service}.py`
- `src/dm_assistant/orchestration/dungeons/service.py` or a focused presentation module
- `src/dm_assistant/web/{routes,templates/dungeon_detail.html,templates/base.html}`
- web integration tests for disposition, filenames, grouping, inline behavior, and
  authorization

**Done when**

- No normal page shows `manifest #0`, `dm_png #0`, or a UUID download name.
- DM notes download as `.txt` and also open inline.
- Maps/PDFs can open in a browser tab; ZIP downloads intentionally.
- Every route still enforces campaign ownership and safe content headers.

### P7-13f — Print redesign and guarded re-enable

**Goal:** provide useful print output without unbounded blank pages.

**Work**

- Freeze PDF request/exporter v2 with `reference` and `tactical_tiles` modes.
- Add occupied-geometry bounds and explicit crop/room/zone selection. Preserve source
  grid origin and calibration metadata after cropping.
- Add a print preflight result containing map/crop cells, paper, exact scale, tile
  rows/columns, page count, estimated nonblank coverage per page, and rejection codes.
- Reference mode fits a low-ink map to a bounded page count and labels it not to scale.
- Tactical mode keeps 72 points per cell and exact stitching metadata, but requires a
  selected tactical region unless whole-floor output passes limits.
- Reject output above configured page count or below useful-content coverage. Never
  auto-generate both audiences; the DM selects audience and mode.
- Add visual PDF regression tests that rasterize every tile and assert meaningful
  content, in addition to page-box/calibration/adjacency metadata tests.
- Run the sparse regression fixture and at least one compact multi-room fixture through
  manual print preview before changing capability state from disabled to enabled.

**Done when**

- The previous sparse large floor is rejected before bytes are generated, with a
  recommendation to select a room/zone or reference mode.
- A selected encounter room produces a small exact-scale stitchable set with no blank
  pages and a correct one-inch calibration square.
- Reference mode produces a readable bounded overview.
- The UI displays the estimate and requires explicit confirmation before export.

### P7-13g — Integrated UX/eval gate and rollout

**Goal:** prove the refreshed output is usable, secure, and stable before making it the
new default.

**Work**

- Add a browser workflow from prompt through floor map, DM/player toggle, keyed notes,
  Roll20 download, print preflight, and approval review.
- Extend dungeon evals with presentation metrics: direct-door correctness, connector
  bend count, occupied-bounds density, callout collisions, key completeness, feature
  realization, print page/coverage limits, asset naming, and inline behavior.
- Preserve existing semantic, deterministic replay, topology, geometry, secrecy,
  atomic publication, cancellation, and reader gates for artifact formats that
  actually exist; do not carry unused pre-P7-13d V2 compatibility.
- Perform one manual DM review of the synthetic fixture and one opt-in live generated
  dungeon. Record remaining edits; never put provider responses or real campaign text
  in fixtures.
- Change the active generation/profile/render pins only after the synthetic gate and
  manual review pass. Keep a documented rollback to the prior profile/generator.
- Add prompt and bounded-repair evaluations for hidden vertical access, secret
  locked/puzzle doors, secret trapped doors, and explicitly located locked/puzzle/
  trapped endpoint doors or hatches on vertical links. Terminal public/durable outcomes must
  distinguish explicit model abstention from exhaustion after rejected structured
  submissions; the latter reports no accepted proposal after bounded repair with safe
  diagnostics.

**Done when**

- A DM can identify every room, special door, trap, puzzle, clue/key, transition, and
  feature without reading opaque IDs.
- DM and player outputs are visually coherent and secrecy-clean.
- Asset navigation is purpose-oriented and filenames are recognizable off-site.
- Print remains disabled unless all P7-13f gates pass.

## 5. Required test matrix

| Boundary | Minimum coverage |
| --- | --- |
| Pure contracts/compiler | Advanced V2 round trip, unknown-version failure, stable IDs, composable door mechanics, schema/runtime invariant audit, readiness handling for incomplete optional mechanics, and deliberate synthetic-fixture migration |
| Placement/routing | direct shared-wall doors, straight-first routing, obstacle bend, endpoint lead, no room overlap, unrelated clearance, deterministic seed, locked regeneration |
| Geometry/pathfinding | explicit openings, connected walkable cells, no undeclared openings, marker bounds/reachability, multi-floor endpoints |
| Rendering | SVG goldens, raster equivalence, collision boxes, symbol grammar, no opaque IDs, grayscale, DM/player leakage |
| DM guide | callout bijection, readable lock/trap/puzzle details, unknown handling, UTF-8 text export |
| Assets/web | grouped catalog, floor/audience labels, inline/open/download matrix, safe filenames, `.txt`, CSP/nosniff, ownership/CSRF |
| Print | disabled-policy tests first; later preflight limits, sparse rejection, reference mode, tactical crop, page raster nonblank, exact scale/calibration/stitching |
| Integration/evals | prompt-to-package-to-output page, atomic assets, historical artifact readability, no secret metadata in every clean role, bounded-context repair, constrained-sampling contract, token ceiling, and staged live Flooded Archive canary |

## 6. Ordering, dependencies, and scope control

Implement in this order: **P7-13a → P7-13b → P7-13c → P7-13d → P7-13d.1 →
P7-13e → P7-13f → P7-13g**.

- P7-13a through P7-13d are complete; P7-13d.1 is the immediate recovery task.
- P7-13c may build symbols against synthetic exact packages while P7-13d evolves the
  model contract, but do not expose incomplete generated challenge content as ready.
- P7-13d.1 is a blocking reliability recovery prompted by live evidence; do not spend
  more provider tokens on ad hoc retries or begin P7-13e before its canary passes.
- P7-13e may begin after P7-13d.1 and after the output catalog contract is known; it
  must not wait for print re-enable.
- P7-13f cannot re-enable print before compact geometry from P7-13b and catalog/UI
  preflight from P7-13e exist.
- P3 canonical revisions remain separate. Nothing in this refresh commits generated
  dungeon plans as canon.

Out of scope for this refresh:

- polished illustration-first maps or textures;
- direct Roll20 API upload/dynamic lighting;
- encounter composition/stat blocks;
- player-session reveal overlays (retain the existing deferred plan);
- a SPA, new service, queue, database, or model-owned renderer geometry.

## 7. Final acceptance checklist

- [ ] Direct doors are shared-wall openings, not tiny corridors.
- [ ] Corridors do not intersect room interiors and endpoint bends are rejected.
- [ ] Room spacing follows the semantic policy rather than a universal five-foot gap.
- [ ] Default maps contain no opaque component IDs and no overlapping text.
- [ ] One consistent symbol/callout grammar covers common dungeon features.
- [ ] Secret, locked, and trapped door state plus difficulty is usable by the DM.
- [ ] Traps, puzzles, clues/keys, objectives, transitions, and features have map markers
      and keyed descriptions.
- [ ] Player output contains no hidden markers, DCs, traps, or puzzle solutions.
- [ ] Assets are grouped by purpose/floor/audience; technical manifests are secondary.
- [ ] Viewable formats open inline/new-tab; downloads are explicit.
- [ ] Download names are meaningful and DM notes are UTF-8 `.txt`.
- [ ] New print export stays disabled until guarded reference/tactical modes pass.
- [ ] Historical artifacts/assets remain immutable, readable, and downloadable.
- [ ] Package purity, deterministic replay, atomic publication, and preparation/canon
      boundaries remain intact.
