# DM Assistant Harness — Project Goals and Product Direction

## Purpose

The goal of this project is to build an AI-assisted campaign harness for Dungeons & Dragons 5e / 5.5 that helps a human Dungeon Master run a coherent, persistent campaign with much less prep and bookkeeping. A primary preparation capability is generating playable dungeons and party-appropriate encounters, not merely remembering campaign notes.

The near-term system is **not an autonomous AI Dungeon Master**. The human DM remains responsible for adjudication, pacing, improvisation, tone, and the actual table experience. The harness exists to make the campaign easier to remember, prepare, query, and evolve.

The long-term design should nevertheless leave room for more active real-time participation by the system. That future state might include live continuity assistance, rules lookup, NPC context retrieval, scene preparation, player-facing interactions, or eventually some degree of autonomous scene or side-character operation. The architecture should make those possibilities feasible without requiring the project to become an autonomous-DM system today.

## Core Problem

Large campaigns accumulate more information than either a human or an LLM can reliably keep in working memory.

A campaign may contain:

- hundreds of NPCs, locations, items, factions, and organizations;
- relationships that change over time;
- secrets, lies, mistaken beliefs, rumors, and competing versions of events;
- long-running plot threads and unresolved promises;
- historical events whose significance becomes clear much later;
- facts established retroactively;
- simultaneous events occurring in different places;
- ambiguous chronology;
- rules information from multiple editions or sourcebooks;
- dungeon layouts that must be connected, navigable, printable, and tactically usable;
- encounters that must fit the party, location, campaign, and intended style of play;
- rich narrative details that are important but difficult to reduce to structured data.

A naive "give the model all the notes" approach does not solve this reliably. Long contexts become noisy, retrieval becomes inconsistent, and a model can confuse plans with canon, belief with truth, or old state with current state.

The harness should therefore act as a persistent campaign memory, context compiler, and constrained preparation compiler that turns creative intent into validated dungeons and encounters. It should feel like one DM Workbench while preserving clear internal boundaries between campaign sources, canonical history, preparation artifacts, dungeon mechanics, encounter design, and session review.

## Product Philosophy

### The human DM remains authoritative

The DM decides what is canon.

The system may propose:

- new facts;
- relationship changes;
- inferred consequences;
- timeline relationships;
- newly identified entities;
- new ontology predicates;
- session summaries;
- plot implications.

Those proposals should not silently become canonical campaign state.

In the initial system, meaningful updates should be reviewed and approved by the DM, particularly at the end of a session.

### The system should reduce cognitive load, not create clerical work

A successful harness should not require the DM to manually fill out dozens of structured forms after each session.

The DM should be able to provide ordinary prose such as:

> The party confronted Deren at the Silver Stag. Rowan killed him. Mira escaped. They learned that the magistrate had been poisoned, and Bran agreed to help them recover the seal.

The harness should extract candidate events, facts, relationships, knowledge changes, and unresolved threads, then present those changes for review.

The structured representation should exist primarily for the benefit of the software.

### The model should express intent; code should enforce mechanics

For generated dungeons and encounters, the LLM should select themes, purposes, room roles, relationships, encounter goals, and other creative intent through a constrained vocabulary. It should not repeatedly invent pixel coordinates, SVG syntax, pathfinding rules, encounter arithmetic, export formats, or rendering details.

Deterministic code should own geometry, connectivity, grid alignment, validation, rendering, rules calculations, asset packaging, and reproducibility. Invalid generated specifications should produce actionable diagnostics that the model or DM can repair. The dungeon kernel should be independently testable and usable without campaign storage or a model provider, while the Workbench supplies context, orchestration, persistence, and human review.

### Narrative richness must not depend on perfect formalization

The campaign should retain a lossless prose record in Markdown.

Not everything meaningful in fiction should need to become a database fact.

For example:

> Mira was unusually quiet when Rowan mentioned her father, and for a moment she seemed almost relieved.

That may never deserve a formal predicate. It should still be retrievable later through semantic and lexical search.

The system should therefore maintain both:

1. **structured knowledge** for precise facts, relationships, state, time, belief, and provenance; and
2. **narrative memory** for nuance, descriptions, conversations, foreshadowing, and other material that is difficult or unnecessary to formalize.

Neither replaces the other.

## Initial Workflow

The product remains one web/CLI Workbench rather than a collection of separately deployed tools. Its user-facing areas should be understandable as a Library, Chronicle, Preparation workspace with Dungeon and Encounter Studios, Session Desk, Assistant, and Settings. Preparation approval and canonical commit remain visibly separate actions.

### Before a campaign or session

The harness should be able to ingest:

- campaign Markdown;
- NPC notes;
- locations;
- factions;
- adventure material;
- previous session summaries;
- player-character sheets and backstories;
- descriptions and mechanics for important story items;
- creature/bestiary records with complete stat blocks;
- dungeon briefs, generation constraints, and prior generated artifacts;
- house rules;
- D&D 5e / 5.5 rules extracted from PDFs into Markdown.

The rules corpus should remain distinct from campaign material and should be tagged by rules edition.

The DM should be able to ask questions such as:

- Who currently knows that Aldric murdered the king?
- Why does Mira distrust Rowan?
- When did the party first encounter the black candles?
- Which unresolved plot threads involve Salazar?
- What do the players know about the missing prince?
- What is Rowan's passive Perception, and which features affect it?
- Who currently carries the seal, and what does it do?
- Generate a two-level crypt dungeon with a loop, a secret route, and encounters suitable for this party.
- Scale the guardian encounter up one difficulty step without simply adding hit points.
- Produce printable player and DM maps plus a Roll20-compatible map image.
- What are the 2024 hiding rules?
- Is this ruling different under the 2014 rules?

The answer should be assembled from the smallest relevant context rather than from a giant dump of campaign notes.

### During a session

The initial version should be usable for occasional queries rather than as the primary game runner.

Useful mid-session interactions include:

- fast rules lookup;
- recalling an NPC's motivations and history;
- determining what an NPC knows;
- finding a previously encountered character, object, clue, or location;
- checking relevant character-sheet abilities, spells, proficiencies, or inventory;
- recalling the narrative and mechanical properties of important story items;
- checking continuity;
- retrieving unresolved plot threads associated with the current scene;
- retrieving the DM/player map variants, room details, creature stats, puzzle solution, or scaling option for a prepared dungeon;
- generating optional names, descriptions, or incidental content while remaining grounded in campaign state.

The system should be optimized for fast, trustworthy answers rather than extended autonomous narration.

### After a session

The DM provides notes or a summary.

The harness performs a structured extraction process and proposes changes such as:

- new events;
- newly introduced entities;
- status changes;
- location changes;
- reviewed character-sheet or important-item changes when supported by the supplied sources;
- relationship changes;
- new or changed beliefs;
- newly acquired knowledge;
- secrets revealed;
- quests started, advanced, failed, or completed;
- new temporal relationships;
- retcons or superseded assertions;
- unresolved plot threads;
- which prepared dungeon rooms/encounters were reached, changed, bypassed, or resolved.

The DM approves or edits those changes before they become canonical structured state.

The original session notes remain available as narrative source material regardless of which facts are structured.

## Desired System Qualities

### Coherence

The system should make it difficult for the assistant to casually contradict established campaign state.

Examples:

- a dead character should not appear without explanation;
- an NPC should not act on a secret they have never learned;
- a faction should not be described as allied with the party if the relationship ended months ago;
- the assistant should distinguish what is true from what a character merely believes.

### Provenance

Important facts should be traceable.

If the harness says:

> Mira distrusts Rowan because she believed he killed Deren.

the DM should be able to trace that conclusion back to the relevant event or session notes.

### Temporal awareness

The campaign is not just a collection of current facts.

The system should understand:

- when something was true;
- when it stopped being true;
- when an event occurred;
- uncertain or relative chronology;
- simultaneous events;
- facts established retroactively;
- when the DM established a fact versus when it was true in the fictional world;
- when particular characters or players learned something.

Sequential event numbers should be identifiers at most, never the campaign's temporal model.

### Multiple perspectives

A rich story can contain multiple incompatible but simultaneously valid knowledge states.

For example:

- Salazar actually killed Deren.
- Mira believes Rowan killed Deren.
- the City Watch officially blames Mira.
- Rowan thinks Deren committed suicide.
- the players have not yet learned the truth.

The harness should preserve these distinctions rather than flattening them into one "fact."

### Extensibility

The campaign ontology should be able to grow with the story.

A campaign may eventually need relationships such as:

- sibling_of;
- owes_money_to;
- infiltrates;
- pretends_allegiance_to;
- knows_true_name_of;
- is_reincarnation_of;
- magically_bound_to;
- witnessed;
- suspects;
- worships;
- blackmails.

Adding a new relationship type should normally add data, not require a database migration.

### Graceful incompleteness

The system should not fail because a concept has not yet been formally modeled.

If the harness encounters a relationship it cannot represent cleanly, it should be able to:

- leave the material in narrative memory;
- create a provisional unstructured claim;
- propose a new relationship/predicate for DM approval.

This prevents the ontology from becoming a mandatory upfront design exercise.

## Dungeon and Encounter Generation

Dungeon generation is a primary initial use case. Regional and world-map generation are out of scope for now.

In this project, a **battlemap** means a top-down, scaled grid on which tokens can be positioned and movement, distance, terrain, and line-of-effect can be adjudicated. A generated dungeon floor plan should be tactically usable as one or more such maps; a separate illustration-only battlemap system is not required.

### Structured dungeon generation

The harness should provide an LLM with high-level primitives for describing:

- dungeon purpose, theme, history, inhabitants, and intended tone;
- floors, entrances, exits, stairs, and vertical connections;
- room roles and approximate size/capacity constraints;
- room-to-room topology, loops, branches, chokepoints, and optional routes;
- normal, locked, trapped, and secret doors;
- keys, gates, clues, secrets, puzzles, traps, hazards, terrain, and interactable features;
- encounter slots, rest opportunities, treasure, and narrative discoveries;
- player-visible versus DM-only information.

Code should transform that specification into exact grid geometry, validate it, and render it. Initial geometry can favor practical orthogonal square-grid dungeons over arbitrary artistic shapes. Multiple floors should be representable as connected floor layers.

Validation should catch at least:

- disconnected required areas;
- overlapping rooms or invalid wall/door placement;
- blocked entrances, stairs, or corridors;
- impossible lock/key or clue/gate dependencies;
- spaces too small for their intended creatures or encounter behavior;
- missing grid scale or inconsistent export dimensions.

Generation should be seed/version based so the same inputs are reproducible. The DM should be able to regenerate or edit one room, connection, encounter, or rendering layer without discarding the entire dungeon.

Campaign influence should arrive through a versioned `GenerationContextEnvelope` carrying common scope/provenance plus a narrow `DungeonGenerationContext`. Dungeon context may include selected location lore, geography, themes, factions, plot hooks, tone, and coarse party constraints; it should not become a universal object containing every field needed by encounters, session extraction, or future NPC scenes.

### Map outputs

Practical grids are required; polished illustration is optional future enhancement.

The canonical map representation should be renderer-neutral. Initial outputs should include:

- grid-on and gridless PNG maps for Roll20 and ordinary web viewing;
- deterministic SVG as an internal/optional vector rendering format;
- separate DM and player exports so secret doors, traps, solutions, and encounter markers are not leaked;
- Roll20-compatible map images with grid dimensions/scale metadata;
- low-ink printable PDF maps at the standard miniature scale of one inch per five-foot square.

Printable dungeons should tile across Letter and/or A4 pages without rescaling. Pages should include a floor/page overview, row/column identifiers, cut/registration marks, configurable overlap strips, alignment marks, and a calibration ruler/test square so they can be trimmed and stitched reliably on a table. The default print style should use white floors, strong wall outlines, a light grid, grayscale-safe symbols/hatching, and little or no solid dark fill. A visually richer web renderer is optional future work.

Direct Roll20 API automation and dynamic-lighting import are not required initially.

### Encounter generation

The harness should generate combat, social, exploration, puzzle, trap, hazard, and mixed encounters. An encounter package may include:

- purpose, stakes, objectives, and possible resolutions;
- location/room and terrain interactions;
- complete creature stat blocks and source/edition provenance;
- starting positions, waves, reinforcements, behavior, and tactics;
- checks, DCs, clues, hints, solutions, counterplay, and failure consequences;
- rewards, discoveries, resource pressure, and downstream consequences;
- easier/harder variants and guidance for adjusting during preparation.

Combat difficulty should use deterministic edition-aware calculations plus the actual party snapshot. The LLM may adapt composition and tactics using party makeup, optimization, available abilities, stated playstyle, desired difficulty, and explicit DM inputs. It should not be trusted to perform encounter-budget arithmetic or silently alter creature numbers without validation.

Encounter generation should receive its own `EncounterGenerationContext`, emphasizing party mechanics and playstyle, authorized creature sources, requested difficulty, room geometry, pacing, and resource pressure. It shares the envelope/reproducibility mechanism with dungeon generation but not the same payload schema. Whether the deterministic encounter mechanics later merit a separate package should be decided from implementation evidence rather than assumed up front.

Customized creatures should produce complete, usable stat blocks and retain lineage to their source or generated base. The project should not bundle copyrighted bestiary content; it should ingest user-supplied/authorized sources and clearly label generated variants.

Puzzle packages should retain the solution, clue structure, hints, alternate reasonable solutions, failure behavior, and reset/recovery path. Player-facing map/package exports must omit DM-only solutions.

### Preparation is not canon

Generated dungeons, maps, creatures, and encounters are versioned preparation artifacts. DM approval makes an artifact ready for play, but does not assert that every room, inhabitant, or planned event has appeared in canonical reality. After play, the ordinary session-close workflow records what was discovered, changed, defeated, bypassed, or left unresolved.

## Character Sheets and Important Story Items

The initial interface is DM-only. It should be able to use the complete supplied player-character sheets, backstories, and important-item records when answering the DM, rather than treating characters only as names in the narrative graph.

The system should preserve each original sheet/item source and also normalize commonly queried information such as:

- ancestry, background, class, subclass, and level;
- ability scores, saves, skills, senses, speeds, armor class, and maximum hit points;
- proficiencies, languages, features, feats, spells, and other limited-use abilities;
- inventory, currency, attunement, and important carried items;
- item mechanics, charges, restrictions, lore, ownership, and last known location.

A cohesive sheet or item profile does not need to be decomposed into dozens of ontology assertions. Structured snapshots can support mechanical queries, while ownership, location, knowledge, history, and other story-changing facts remain temporal assertions/events with provenance.

The initial goal is campaign memory, not a live virtual tabletop or combat resource tracker. Current hit points, expended spell slots, conditions, and other rapidly changing tactical state need not be tracked unless later usage shows that it is valuable.

## Rules Knowledge

The project will target D&D 5e and 5.5 / 2024-era rules.

Rules sourcebooks and authorized creature/bestiary sources will be extracted or imported for indexing and structured profile creation. Complete creature statistics must retain source, edition, and revision provenance.

The harness should treat rules editions as separate corpora rather than mixing them.

A campaign should have an explicit default ruleset, while allowing deliberate cross-edition queries.

Rules retrieval should use a combination of:

- exact/lexical search for named spells, feats, conditions, and rule terms;
- semantic search for natural-language questions;
- metadata filters for sourcebook and rules edition.

The system should cite or identify the source material used for an answer.

## Model Runtime and User Interaction

The DM assistant is an independent harness with its own thin web interface and CLI. The web interface is a shared Workbench shell with distinct Library, Chronicle, Dungeon Studio, Encounter Studio, Session Desk, Assistant, and Settings workflows. It is the normal place to enter prompts, paste/attach images, select or override task/model profiles, inspect streaming results and diagnostics, review drafts, preview maps, and download PNG/PDF assets. The CLI uses the same Python application services for automation, administration, debugging, deterministic generation, review, and recovery when no model is available.

A narrow private Node gateway should use pinned `@earendil-works/pi-ai` for provider OAuth/API-key resolution, model discovery/capability metadata, chat/image-input streaming, reasoning controls, tool-call serialization, cancellation, and usage reporting. The gateway is a replaceable model-transport adapter, not the product UI or a second source of campaign state. In particular, it permits ChatGPT Plus/Pro Codex OAuth without copying Pi's credentials or making the Pi coding-agent harness the application.

Provider credentials remain in a dedicated gateway credential store and never enter browser state, campaign documents, ordinary application logs, or model-run payloads. The browser and Python service receive only non-secret provider/model/auth-status metadata. The gateway is bound to loopback or a private container network and is not exposed directly to the LAN or internet.

Model choice should be explicit and versioned by task profile rather than hidden behind one global model. A profile pins provider/model, normalized effort, context policy/budget, allowed tools, output schema/token limit, and fallbacks; a run records the exact resolved profile. Plot ideation, scene-context compilation, rules answers, extraction, dungeon intent, and encounter generation may use different profiles or multi-stage model combinations. Candidate assignments such as Luna versus Terra must be selected through task-specific evals and DM preference rather than inferred from model names.

`@earendil-works/pi-agent-core` is a possible later implementation aid for open-ended multi-turn tool loops, steering, and parallel tool execution. It is not initially required: bounded Python workflows should own context compilation, tool authorization/execution, retries, idempotency, and durable state. If adopted later, it runs behind the same gateway boundary and cannot approve artifacts or commit canon.

The same core CLI/API contracts should permit optional Pi-extension and MCP adapters later. MCP may expose selected tools to external agent hosts over local stdio, loopback, SSH, or a private network; it is not the internal web transport and does not require a publicly reachable server.

Embedding/vector generation is a separate subsystem. `pi-ai` handles tool-capable chat/image-input models, not embeddings, and ChatGPT Codex subscription OAuth must not be assumed to authorize an embedding endpoint. The initial lexical search works without embeddings; P2 evaluates a small local CPU embedding adapter first, while retaining a narrow interface for hosted embedding APIs with separate credentials. Embeddings remain rebuildable, versioned pgvector projections rather than canonical evidence.

## Future Direction: Real-Time Campaign Interaction

The project should leave room for a more active live-session role without making that a prerequisite for the first useful version.

Potential future capabilities include:

### Scene-context compilation

Given the current location, participants, recent events, and player intent, the harness could automatically assemble a compact scene packet containing:

- current local state;
- relevant NPCs;
- NPC goals and knowledge;
- applicable relationships;
- recent relevant events;
- unresolved plot threads;
- secrets relevant to the DM;
- likely rules references;
- semantically related campaign memories.

This could support either the human DM or a future real-time model.

### Continuity checking

Before presenting or generating something, the system could flag:

- characters who are dead or elsewhere;
- impossible knowledge;
- contradictions with established facts;
- anachronistic events;
- conflicts with the active timeline;
- accidental revelation of DM-only information.

### NPC assistance

The harness could provide an NPC-specific context package containing:

- personality;
- current goals;
- fears;
- loyalties;
- known information;
- incorrect beliefs;
- recent experiences;
- current relationships;
- private secrets;
- public persona.

A model could then help the DM portray that NPC consistently without needing the full campaign context.

### Live transcript ingestion

A future version might ingest a session transcript and extract candidate events or state changes continuously.

This should remain provisional until explicitly committed to canon.

### Player-facing interaction

Eventually, some parts of the harness might safely interact directly with players.

Examples could include:

- an in-world NPC;
- a downtime contact;
- a rules assistant;
- an asynchronous faction or patron;
- an automatically generated handout or correspondence.

The knowledge model would allow such an agent to receive only what that character or role is allowed to know.

### More autonomous campaign machinery

Possible later experiments include:

- proactive session preparation;
- plot-thread tracking;
- consequence generation;
- faction simulation;
- NPC goal progression;
- side-scene operation;
- autonomous downtime interactions.

These should be built on top of reliable state, provenance, retrieval, and temporal reasoning rather than used as substitutes for them.

## What Success Looks Like

The first successful version does not need to feel magical.

It should make the following workflow dependable:

1. Write campaign material and session notes normally.
2. Ingest them, the party sheets, rules, and authorized creature records.
3. Describe a dungeon's purpose, constraints, tone, and intended challenge.
4. Receive a validated, reproducible dungeon with practical gridded DM/player maps and linked room content.
5. Populate it with party-aware combat and noncombat encounters, complete creature statistics, puzzles, and scaling options.
6. Export low-ink, exact-scale, stitchable print pages or Roll20-compatible grid-on/gridless images.
7. Ask a question about the campaign, dungeon, encounter, or rules and receive a concise grounded answer.
8. Finish a session and feed the results to the harness.
9. Review and commit what actually became canonical.
10. Repeat for months without campaign memory or prepared content gradually becoming less trustworthy.

If that foundation works, increasingly sophisticated real-time behavior can be layered on top without asking an LLM to become the sole keeper of campaign reality.
