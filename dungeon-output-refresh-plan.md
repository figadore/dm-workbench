# Dungeon Output Refresh Plan

> Paused by P7-14 until the Tier A gate passes. This document records the remaining product outcome,
> not a current task. Revalidate every item against the active V1 implementation before resuming.

## Problem Summary

The original generated-output review found several coupled defects:

| Problem | Required behavior |
| --- | --- |
| Short links rendered as boxes or endpoint doglegs | Direct doors are shared-wall openings; corridors have perpendicular endpoint approaches and no near-door bends. |
| Corridors overlapped room interiors | Corridor interiors stop at validated wall openings and never enter rooms. |
| Every room had a five-foot gap | Only unrelated rooms require rock clearance; direct-door rooms share a wall. |
| Raw opaque IDs and labels collided | Maps use short deterministic callouts with collision-aware placement and a keyed DM guide. |
| Door/trap/puzzle state was unclear | One grayscale-safe symbol grammar identifies all DM mechanics while player output omits secrets. |
| Requested mechanics lacked usable guidance | Exact markers link to complete room-local DM adjudication; missing content remains a readiness blocker. |
| Assets exposed storage roles and UUID names | Outputs are grouped by purpose/floor/audience with meaningful filenames and explicit Open/Download actions. |
| Exact-scale export produced sparse blank pages | Print is preflighted, bounded, and split into reference-map and selected tactical-region modes. |

The screenshot and prior generated packets were diagnostic alpha artifacts, not retained compatibility
requirements.

## Stable Product Decisions

### Connection geometry

1. A direct door is one opening in a shared wall and has no synthetic corridor.
2. A passage consists of explicit traversable cells with openings at both room walls.
3. Unrelated rooms retain at least one cell of solid-rock clearance.
4. Routes prefer straight, then one-bend paths. A bend cannot occupy the opening or first clear cell
   outside a room.
5. Unsupported direct-door placement fails with a structured diagnostic; it never silently becomes a
   corridor.

### Map language

DM maps use deterministic numbered room callouts plus keyed symbols for ordinary/secret/locked/trapped
doors, traps/hazards, puzzles, clues/keys/treasure, objectives, physical features, and directional
transitions. Full descriptions live in the guide, not map geometry. Opaque IDs remain available only
in technical lineage/developer inspection.

Player maps contain only explicitly published geometry and physical features. They omit room/feature
keys, objective/start/encounter markers, secret routes, trap badges, hidden difficulties, and puzzle
solutions. Filtering occurs before SVG/PNG/PDF construction.

### DM guide

The floor key links every visible callout to readable room, door/transition, trap/hazard, puzzle,
clue/key, feature, and objective guidance. Models may propose bounded descriptions and relative
challenge; deterministic policy owns IDs, positions, visibility, and exact numeric difficulties.
Required missing mechanics remain unknown and block preparation readiness.

### Asset presentation

The normal output page groups immutable artifact-version roles as:

1. Maps, by floor and DM/player audience;
2. DM guide;
3. Virtual tabletop bundles;
4. Print;
5. collapsed technical lineage.

Images, trusted generated SVG, text, JSON, and PDF may open explicitly in-browser under safe headers.
ZIP is attachment-only. Downloads use purpose-derived sanitized filenames such as:

```text
<dungeon>-v<version>-<floor>-<audience>-<purpose>.<ext>
```

Blob hashes/UUIDs are storage identity, never primary filenames.

### Print

Print has two distinct modes:

- **Reference map:** bounded pages, fitted to paper, visibly labelled not miniature scale.
- **Tactical tiles:** exactly one inch per five-foot cell for an explicitly selected room, zone, or
  crop. Whole-floor output is allowed only when bounded preflight passes.

Preflight reports crop dimensions, paper, audience, scale, tile grid/page count, and occupied coverage.
It rejects excessive or mostly blank output before creating bytes. Tactical pages retain crop/
registration marks, overlap/alignment metadata, actual-size instructions, and a one-inch calibration
mark. The user chooses audience and mode; the system does not generate every variant automatically.

## Remaining Work After Tier A

### P7-13e — Output catalog and filenames

- Project immutable role links into the purpose/floor/audience catalog.
- Add artifact-version-scoped Open and Download routes with ownership checks, safe MIME/CSP/nosniff
  policy, and sanitized filenames.
- Render the primary map and DM guide inline; keep manifests and hashes under technical lineage.
- Preserve historical asset readability without making old UUID routes the primary interface.

**Gate:** normal pages show no persistence labels or UUID filenames; notes open/download as UTF-8
`.txt`; viewable formats open intentionally; ZIP always downloads.

### P7-13f — Guarded print redesign

- Implement versioned reference and tactical request contracts.
- Add occupied bounds, explicit crop/room/zone selection, and preflight limits.
- Add rasterized per-page nonblank checks in addition to page-box, scale, calibration, overlap, and
  adjacency tests.
- Manually review one sparse rejection and one compact tactical print before enabling the capability.

**Gate:** sparse whole-floor output fails before bytes; selected tactical output has no blank pages
and exact calibration; reference output is bounded and legible.

### P7-13g — Integrated UX and rollout

- Exercise prompt through DM/player preview, guide, VTT download, print preflight, and preparation
  review in one browser workflow.
- Preserve deterministic replay, topology/geometry validation, secrecy, atomic publication,
  cancellation, and retained-reader behavior.
- Evaluate maps and guides across synthetic cases plus one explicitly authorized live dungeon.
- Roll out only after objective and human review passes; distinguish model abstention from exhausted
  rejected submissions in every surface.

**Gate:** the DM can identify and adjudicate every requested component without opaque IDs; player
assets remain secrecy-clean; asset navigation and filenames remain useful outside the application;
print stays disabled unless all P7-13f gates pass.

## Required Coverage

- Direct/shared-wall doors, straight and obstacle-bent passages, endpoint clearance, no room overlap.
- Stable callout allocation, collision bounds, raster/SVG equivalence, grayscale distinction.
- Complete DM key, unknown handling, and zero protected IDs/metadata in every player role.
- Catalog grouping, ownership/CSRF, Open/Download policy, filenames, and content headers.
- Print sparse rejection, bounded reference mode, tactical crop, exact scale, calibration, stitching,
  and per-page visual content.
- End-to-end atomic assets and historical readability.

## Scope Exclusions

No illustration-first renderer, direct Roll20 API/dynamic lighting, encounter stat-block composition,
player-session reveal overlays, SPA, service, queue, database, or model-owned geometry belongs in this
refresh. Preparation work remains separate from canonical campaign revisions.
