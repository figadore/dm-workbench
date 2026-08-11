# DM Assistant Harness

A self-hosted, AI-assisted dungeon/encounter generator, campaign memory, and context compiler for a human Dungeon Master running D&D 5e/2024-era campaigns.

The project is currently in the planning stage. Application code has not been scaffolded yet.

## Start Here

For a first-time architecture review:

1. [`dm-assistant-project-goals.md`](dm-assistant-project-goals.md) — product goals and boundaries.
2. [`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md) — architecture, data semantics, and accepted decisions.
3. [`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md) — phased tasks and acceptance gates.

For an implementation session or return after a break, conserve context:

1. Run `git status`.
2. Read [`PROJECT_STATUS.md`](PROJECT_STATUS.md) — the live handoff and next exact task.
3. Read [`AGENTS.md`](AGENTS.md).
4. Read only the current task/phase and relevant architecture sections, not every planning document again.

## Architectural Summary

- One Python/FastAPI DM Workbench modular monolith plus a narrow private Node model-gateway process.
- One independently packaged pure `dm_dungeon` kernel loaded in the Python process; it has no database, UI, retrieval, or model-runtime dependency.
- The gateway uses pinned `@earendil-works/pi-ai` for provider OAuth/API-key auth, model catalogs, streaming, tool-call transport, and reasoning controls.
- A first-party thin web UI is the normal conversational/review interface; the Typer CLI remains the automation, administration, and recovery interface.
- One PostgreSQL database with pgvector; embeddings use a separate Python-side runtime because `pi-ai` does not provide embeddings.
- Immutable, versioned campaign/rules source documents.
- Hybrid lexical and semantic retrieval.
- Perspective-aware, provenance-aware campaign state.
- Seeded dungeon generation: Workbench/model-authored intent compiled by the deterministic `dm_dungeon` topology, geometry, validation, rendering, and export package.
- Practical grids rendered through deterministic SVG, exported as DM/clean PNG, low-ink stitchable one-inch-scale PDF, and Roll20-compatible images/metadata.
- Party/playstyle-aware combat and noncombat encounters with complete creature statistics. Encounter orchestration starts in the Workbench; only a proven deterministic `encounter-mechanics` seam may be extracted later.
- Models create proposals/preparation drafts; only the DM approves artifacts or commits canon.
- PostgreSQL stores canonical revision history, artifact lineage, and readable change summaries.
- Generation runs share a small scope/provenance envelope but use separate strict payloads such as `DungeonGenerationContext` and `EncounterGenerationContext`; there is no universal all-purpose generation payload.
- The web shell is organized into Library, Chronicle, Dungeon/Encounter Studios, Session Desk, Assistant, and Settings while retaining separate preparation-approval and canonical-commit workflows.
- DM-only interface initially, including supplied character sheets and important story items.

## Current Next Step

Begin **P0-01**: scaffold the root Python Workbench package, CLI, tests, and development tooling. Do not add the dungeon workspace package or Node/`pi-ai` gateway during this scaffold. As soon as P0-01 passes, the dungeon-first fast path moves to **P7-02**, which adds `packages/dungeon-engine` as an in-process `uv` workspace member. The model-independent Dungeon Studio follows before grounded model orchestration. [`PROJECT_STATUS.md`](PROJECT_STATUS.md) contains the exact handoff.

## License and Third-Party Marks

Copyright (C) 2026 Reese Wilson.

Except where otherwise noted, original code and documentation in this repository
are licensed under the [GNU Affero General Public License version 3.0
only](LICENSE). Third-party dependencies and referenced platforms remain subject
to their own licenses and terms.

This repository does not include proprietary game-rule text, published
adventures, artwork, maps, or character data. Users are responsible for having
the rights to any content they import.

Dungeons & Dragons, D&D, and Roll20 are trademarks of their respective owners.
Their descriptive use does not imply affiliation, sponsorship, or endorsement.
