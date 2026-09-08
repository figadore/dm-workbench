# DM Assistant Harness — Product Goals

## Purpose

Build a self-hosted assistant that helps a human Dungeon Master prepare and run a coherent,
persistent D&D 5e/2024-era campaign with less bookkeeping. The first major preparation capability is
playable dungeon and encounter generation; campaign memory, retrieval, and session review make that
preparation trustworthy over time.

This is not an autonomous DM. The human controls canon, adjudication, pacing, improvisation, tone,
and what reaches players. Future live assistance should grow from reliable state and explicit
permissions rather than replacing them.

## Problem

Long campaigns contain more information than a human or one model context can safely hold:

- changing NPC, faction, location, item, and quest state;
- truth, beliefs, rumors, lies, public claims, and secrets;
- uncertain, relative, concurrent, and retroactively established chronology;
- plans and adventure material that may never occur;
- narrative details that matter without deserving database fields;
- multiple rules editions, house rules, character sheets, and creature sources;
- dungeons that must be connected, navigable, reproducible, printable, and secrecy-safe;
- encounters that must fit party, place, pacing, and play style.

A giant prompt containing all campaign notes is noisy and unsafe. The harness should instead preserve
lossless sources, maintain reviewed structured state, retrieve only authorized relevant evidence, and
compile creative intent into deterministic preparation artifacts.

## Product Principles

### The DM remains authoritative

Models may propose facts, relationships, events, chronology, entities, summaries, consequences,
dungeons, and encounters. They never silently update canonical campaign state or approve preparation.
Every canonical change is reviewed and committed atomically by the DM.

### Preparation is not canon

A generated dungeon, creature, puzzle, or encounter is a versioned preparation artifact. Approval
means ready for play, not that its planned inhabitants, discoveries, deaths, or treasure occurred.
Session review records what actually happened.

### Prose first, structure where useful

The system keeps immutable Markdown or other source revisions as narrative memory. Structured
knowledge supports precise questions about identity, state, time, perspective, and provenance, but
nuance may remain searchable prose. Formalization must reduce work, not create forms the DM must
maintain manually.

### Models express intent; code enforces mechanics

Models choose themes, purposes, room roles, progression, encounter goals, tactics, and bounded
creative content through typed contracts. Deterministic code owns IDs, topology, exact geometry,
pathfinding, rules arithmetic, validation, rendering, exports, and reproducibility. Unknown or invalid
input produces explicit diagnostics rather than invented mechanics.

### Answers remain scoped and explainable

Campaign, revision, timeline/cursor, audience, source authority, corpus snapshot, and rules profile
are explicit or inspectable defaults. Authorization filters run before retrieval. Answers cite
immutable evidence and say unknown, disputed, or not precisely ordered when support is inadequate.

### Truth and perspective stay distinct

The system must represent reality separately from knowledge, belief, suspicion, claims, and public
record. What players know may differ from what characters know. Missing knowledge is not proof of
unawareness unless the campaign deliberately tracks completeness for that secret.

### Boundaries remain small

Use one Workbench, one PostgreSQL database, one pure in-process dungeon package, and one narrow
private model-transport gateway. Add services, frameworks, stores, or generalized context objects only
when measured needs justify them.

## Core Workflows

### Before a session

The DM can ingest campaign notes, prior sessions, locations, factions, character sheets, important
items, authorized rules/creature sources, and dungeon briefs. The Workbench should:

- retrieve relevant lore and rules with exact provenance;
- generate a constrained, reproducible dungeon with valid progression and practical grids;
- create linked room guidance and party-aware combat or noncombat encounters;
- provide DM and player-safe maps, VTT assets, and guarded print output;
- compare or regenerate a selected component without discarding accepted work;
- keep every artifact a draft until explicit preparation approval.

Representative questions include:

- Who knows that Aldric murdered the king?
- Why does Mira distrust Rowan?
- Where was the seal last seen, and what does it do?
- What are the 2024 hiding rules, and does the campaign override them?
- Generate a small crypt with a loop, secret route, gated objective, and encounters for this party.

### During a session

The initial product supports fast occasional assistance rather than running the game:

- rules lookup;
- NPC motivation, history, and knowledge;
- character abilities and important-item mechanics;
- continuity and unresolved-thread checks;
- prepared maps, room details, creature statistics, puzzle solutions, and scaling options;
- grounded incidental names or descriptions.

Answers should be concise, fast, and trustworthy. Live combat resources, initiative, and token state
are not initial requirements.

### After a session

The DM supplies notes or a summary. The harness proposes evidence-linked events, entities, state and
relationship changes, knowledge/reveals, quest progress, chronology, retcons, and prepared-artifact
outcomes. The DM accepts, edits, or rejects grouped changes before one atomic canonical commit. The
original source remains available regardless of what becomes structured.

## Required Capabilities

### Campaign memory

- Immutable documents, revisions, chunks, and corpus snapshots.
- Lexical retrieval plus versioned semantic projections with lexical fallback.
- Entities, aliases, events, propositions, perspectives, temporal relations, and evidence.
- Historical queries against old canonical revisions and explicit story cursors.
- Readable revision summaries and detailed audit history.

### Dungeons and maps

- Practical orthogonal square-grid floors with five-foot cells.
- Typed room/progression/gate/secret/feature/encounter intent.
- Constructed connectivity and independently validated topology, geometry, and secrecy.
- Stable IDs, seeds, versions, lineage, and targeted regeneration.
- Renderer-neutral packages producing DM/player SVG and PNG plus Roll20-compatible metadata.
- Exact-scale low-ink print only when bounded preflight, calibration, and stitching checks pass.

### Encounters and profiles

- Complete supplied character, item, and authorized creature profiles with source/version lineage.
- Combat, social, exploration, puzzle, trap, hazard, and mixed encounter packages.
- Deterministic edition-aware difficulty, stat completeness, room fit, and puzzle/trap checks.
- Separate `DungeonGenerationContext` and `EncounterGenerationContext` payloads inside a small common
  provenance envelope.

### Interaction and runtime

- One DM-only Workbench with a thin web UI and shared CLI services.
- A private Node gateway for provider authentication/catalog/transport; credentials never reach the
  browser or campaign data.
- Task-specific model/profile selection, bounded calls, cancellation, usage reporting, and durable
  safe run state.
- Provider-independent deterministic workflows when model or embedding services are unavailable.

## Initial Scope Limits

Included initially:

- one exposed DM principal and campaign-oriented ownership;
- PostgreSQL/pgvector, immutable source and revision history;
- practical dungeon/encounter preparation;
- campaign/rules questions and reviewed session-close extraction;
- user-supplied or authorized source material only.

Explicitly deferred until evidence justifies them:

- player accounts and direct player-facing agents;
- autonomous canonical writes or autonomous campaign operation;
- live transcript ingestion and combat/resource tracking;
- custom-calendar arithmetic and alternate-timeline merging;
- regional/world maps and illustration-first tactical geometry;
- direct Roll20 upload/dynamic lighting;
- automatic rewriting of human-authored sources;
- local chat-model infrastructure, domain microservices, another database, queue, graph/vector store,
  broad agent framework, or speculative encounter-engine package.

## Success

A successful first release lets the DM repeatedly:

1. ingest ordinary campaign, rules, profile, and creature material;
2. generate and review a valid, coherent, reproducible dungeon and linked encounters;
3. obtain secrecy-clean practical map/export assets;
4. ask scoped questions and receive concise cited answers or explicit uncertainty;
5. record a session and review what actually changed;
6. commit one explainable canonical revision;
7. continue for months without plans becoming facts, beliefs becoming truth, sources becoming
   untraceable, or generated mechanics becoming irreproducible.

If that foundation remains dependable, richer live scene context, NPC assistance, player-safe views,
transcript support, and more autonomous experiments can be layered on without replacing it.
