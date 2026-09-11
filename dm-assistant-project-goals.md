# DM Assistant Harness — Product Goals

## Purpose

Build a self-hosted workbench that helps a human Dungeon Master prepare and run a coherent campaign
with less authoring and bookkeeping. Dungeons are the first product, not a diversion: much of this
DM's play happens in them. Campaign memory should subsequently make those adventures fit an ongoing
story without confusing preparation with what actually happened.

**The first viable product is a complete, attractive, independently runnable small dungeon one-shot
from a prompt—not merely a valid map with populated content slots.**

The human controls canon, adjudication, pacing, improvisation, and what reaches players. This is not
an autonomous DM or a combat simulator.

## Delivery Outcomes

The ordered phases and task IDs live in
[`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md). Only
[`PROJECT_STATUS.md`](PROJECT_STATUS.md) selects the live task.

1. **A One-Shot Worth Running:** prove complete adventure authoring against actual DM preparation work.
2. **Prompt to Play:** integrate cohesive authoring into a pleasant, secure browser workspace, with
   readable output, direct text editing, meaningful draft versions, and explicit authoring preferences.
3. **Maps Worth Exploring:** make layout, terrain, and visual presentation support the adventure.
4. **Revise with Your Assistant:** discuss or revise a room, puzzle, obstacle, or whole dungeon in
   visibly scoped conversations; preview and accept changes without losing unrelated work. Separately
   confirm remembered preferences and, when repeated work justifies it, reusable authoring recipes.
5. **Bring Your Campaign:** supply selected facts, claims, and requirements, then retrieve relevant
   campaign evidence into the same generation and revision workflows.
6. **Remember What Happened:** connect notes, questions, unresolved threads, and reviewed session
   outcomes to persistent campaign memory.

Usability is not a final coat of paint. Browser review begins in phase 2, map aesthetics and tactical
legibility in phase 3, and contextual interaction in phase 4. Campaign integration must not delay
those experiences. Elaborate illustration and unrestricted map editing are not first-release gates.

## The Standalone One-Shot

Start with one floor, approximately 5–7 rooms within the existing 4–8-room supported class, one
explicit party-size/level/rules assumption, and a chosen session-length target. It contains:

- a usable hook, clear objective, history explaining the location, and a concrete ending;
- coherent but varied rooms, opposition or environmental pressure, and a meaningful route choice;
- puzzles only when allowed and appropriate, never a mandatory quota per floor; when present, actual
  clues, inscriptions/objects, answers, feedback, hints, alternate approaches, and failure consequences
  are supplied—not instructions to invent them;
- obstacles with visible affordances, actionable procedures, and concrete stakes;
- inhabitants with motivations, tactics or reactions, and non-kill resolutions where appropriate;
- readable keyed room guidance, a matching map, and secrecy-clean player exports;
- explicit supported mechanics and source assumptions, without invented official rules or unsupported
  balance claims.

Combat can use a small authorized creature/profile selection and deterministic encounter policies;
a comprehensive encounter engine or character-sheet importer is not a prerequisite. Synthetic test
creatures prove software behavior, not official game balance. Missing required play material blocks
readiness; deliberate mystery for players is not an excuse for an unspecified DM answer.

The target is review in roughly ten minutes without writing missing central clues, opposition,
mechanics, or endings. Measure actual review/editing minutes and a tabletop walkthrough; this is a
product target to prove, not an existing guarantee. A capable DM's improvisation is welcome, but must
not conceal unfinished generation.

## A Workspace, Not a File Dump

The normal browser journey is: sign in, describe the adventure, inspect progress, open a map-and-guide
workspace, revise, approve for play, and export a useful packet.

- Routine sign-in does not require locating and pasting an API token. Automation credentials and
  browser authentication remain separate; convenience does not mean disabling authentication.
- Clear typography, spacing, navigation, restrained color, visible status, and readable error states
  belong in the first integrated workspace. Plain server-rendered HTML can still be well designed.
- Map and room selection stay synchronized. A component inspector makes the selected dungeon version,
  room/puzzle/obstacle, and editing scope obvious.
- Manual edits have explicit save/cancel and before/after review where consequential. No JSON editing
  is required for ordinary authoring. Storage roles, UUIDs, manifests, and diagnostics belong under
  advanced details, not in the primary interface.
- Maps have an intentional visual language and useful terrain, not merely decorative art. DM/player
  modes are unmistakable; a DM inspector is never packaged into a player export.
- Downloads have recognizable names and purpose: DM guide, player map, DM map, VTT bundle. Exact-scale
  print remains disabled until its separate calibration/tiling gate passes.

## Contextual Conversation and Editing

Selecting a component can open a conversation with two explicit intentions:

- **Ask / Explain:** clarify how the puzzle works, discuss alternatives, ask what a creature wants,
  or identify a contradiction. Answers do not mutate the artifact or silently become authored facts.
- **Propose a Change:** request a scoped revision, see the affected content and dependencies, then
  accept, edit, or reject it. Accepting a draft change is not preparation approval or canonical commit.

The whole small adventure may be relevant context even when only one room is editable. The interface
must distinguish **what the assistant can read** from **what it may propose changing**. Existing manual
edits are protected by default. Changes that need new geometry, clues elsewhere, or altered campaign
facts require a visible scope-expansion proposal, never silent spillover.

Conversations are bound to artifact version and selected components. Stale proposals cannot overwrite
new edits. Useful conversations may be saved privately as user-facing work, separate from body-free
operational logs and never included in player assets by default.

## Adaptation Across the Application

DM guidance should shape every relevant workflow, from adventure planning and encounters to NPCs,
dialogue, revision and session preparation. Natural-language preferences, reported group tendencies,
desired experiences and requirements are distinct inputs—not a fixed menu of feature switches.
A tendency does not tell the assistant whether to embrace or counter it; that direction belongs to
the DM. Guidance shapes preparation and presentation, never rewrites canonical reality.

Phase 2 introduces scoped defaults and request overrides; phase 4 adds separately confirmed preference
suggestions and, when useful, reviewed reusable procedures. The DM can inspect, change or remove them.
Novel preferences should not require new schema fields. General seams for omitting optional content,
using existing material and controlling adaptation replace feature-specific subsystems. Examples
illustrate flexibility, not additional product commitments. Judge success by coherent application and
reduced editing effort, not accumulated memories; personalization must not conceal generator defects.
See architecture §9 for the shared contract.

## Campaign Grounding Without a Second Generator

Standalone generation needs no campaign lore; an internal preparation owner does not imply grounding.
Later, an explicit context packet supplies selected facts and creative permissions:

- **Established fact:** the villain holds a named captive.
- **Required placement:** place that captive in this dungeon, alive.
- **Reported claim:** an informant says the relic is here.
- **Unknown:** whether that report is true.
- **Creative permission:** invent local guards and rooms, but do not change established motivations.

A requirement is a DM instruction about preparation, not evidence of a canonical fact. A report is
not truth. The DM may explicitly authorize inventing a preparation-only answer to an unknown; it
remains labelled proposed preparation. Retrieval suggests relevant authorized sources; it cannot
silently expand scope or promote claims into reality.

Start with DM-selected facts and source references, then add retrieval. The complete temporal and
perspective model is a later memory capability, not a prerequisite for this bounded integration.

## Product Principles

- **Human authority:** models propose; humans accept draft edits, approve preparation, and separately
  commit canonical changes. Canonical writes use one validated atomic campaign revision.
- **Preparation is not canon:** approved/used adventures do not establish deaths, discoveries, item
  ownership, rescues, or other events. Session review records actual outcomes.
- **Prose first:** preserve immutable narrative sources. Structure only what validation, references,
  mechanics, rendering, or actual queries consume; do not formalize every sentence.
- **Cohesive authorship:** design a small adventure together. Typed content categories do not imply
  independent model calls. Targeted calls earn their complexity when revising useful accepted work.
- **Deterministic execution:** code owns IDs, exact graph/geometry, arithmetic, validation, rendering,
  exports, and supported mechanical policy. Models supply typed intent and proposed prose.
- **Appropriate checks:** secrets, authorization, invalid references, and corrupt geometry are hard
  failures. Authored completeness and semantic quality need distinct checks and human judgment;
  filled fields do not prove a puzzle works.
- **Small boundaries:** one Workbench, one PostgreSQL database, one pure dungeon package, one narrow
  private model gateway. A standalone CLI/file adapter calls shared services; no second authoring
  implementation or dungeon microservice is required.
- **Honest evidence:** track failure rate, usage/latency, missing essentials, DM editing time, and
  willingness to run the result. Do not substitute a passing schema or model's self-rating for play.

## Campaign Memory After the One-Shot

Preserve original notes and immutable evidence; answer relevant campaign/rules questions with sources
or uncertainty; prepare session briefs and unresolved-thread reminders; propose grouped session
updates for review. Add precise entity, perspective, temporal, and historical queries as those
workflows require them. Keep beliefs, rumors, plans, rules, and canonical events distinguishable.

## Scope Limits and Success

Defer player accounts, autonomous canon, live transcript ingestion, initiative/resource tracking,
arbitrary/multi-floor geometry, regional maps, illustration-first rendering, direct VTT automation,
and speculative frameworks/services until measured need. User-supplied/authorized material only;
repository fixtures remain synthetic and credential-free.

The first success is a one-shot the DM wants to run, presented in a workspace they want to use. The
next is attaching campaign hooks without breaking that experience. Long-term success is repeating
this for months while sources remain traceable, secrets stay private, and prepared possibilities
never silently turn into campaign history.
