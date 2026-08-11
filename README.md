# DM Assistant Harness

A self-hosted, AI-assisted dungeon/encounter generator, campaign memory, and context compiler for a human Dungeon Master running D&D 5e/2024-era campaigns.

The project is in early implementation. The Python 3.12 Workbench, provider-independent Dungeon Studio, deterministic dungeon/export kernel, PostgreSQL preparation lifecycle, and immutable allowlisted Library source registry are in place.

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

## Isolated Development

Project dependencies are installed only in a container-managed project virtual environment. Copy `.env.example` to ignored `.env`, replace every placeholder—including different random 32+ character `DM_API_TOKEN` and `DM_SESSION_SECRET` values—and leave model/embedding policies disabled while those runtimes are absent.

Start the pinned PostgreSQL 16/pgvector service, migrate, and run the API on the private Compose network:

```bash
cp .env.example .env
podman compose up -d postgres
podman run --rm -it \
  --network dm-assistant_default \
  -p 127.0.0.1:8000:8000 \
  -e UV_LINK_MODE=copy \
  -v "$PWD:/workspace" \
  -v dm-assistant-dev-venv:/workspace/.venv \
  -w /workspace \
  ghcr.io/astral-sh/uv:0.9.5-python3.12-bookworm-slim \
  sh -lc 'uv sync --all-packages --all-groups --frozen && \
    uv run --frozen alembic upgrade head && \
    uv run --frozen dm doctor && \
    exec uv run --frozen uvicorn dm_assistant.api.app:create_app \
      --factory --host 0.0.0.0 --port 8000'
```

Liveness has no database dependency; readiness verifies PostgreSQL 16, pgvector 0.8.1, and exact Alembic head. Every other path—including docs/schema—is authenticated:

```bash
curl http://127.0.0.1:8000/health/live
curl http://127.0.0.1:8000/health/ready
curl -H 'Authorization: Bearer <DM_API_TOKEN>' \
  http://127.0.0.1:8000/openapi.json
```

Run the complete frozen gate—including a disposable safety-named test database, migration round trip, `dm doctor`, all tests, lint, formatting, mypy, and diff checks—with one command. It removes its database volume/network even on failure:

```bash
./scripts/check-container.sh
# Docker alternative:
CONTAINER_ENGINE=docker ./scripts/check-container.sh
```

Stop the development database with `podman compose down`; add `-v` only when intentionally deleting local development data.

## Provider-Independent Dungeon Studio

After migration, create the workspace root with `uv run --frozen dm campaign create "My Campaign"` (or the first-login web form), then log in at `http://127.0.0.1:8000/login` with `DM_API_TOKEN`. The signed browser session contains no API token; all browser writes require CSRF. Dungeon Studio can ingest a versioned `LayoutRequest` JSON, generate and validate exact geometry, inspect run/input/version lineage, compare/regenerate with locks, preview DM/player maps, create PDF/Roll20 exports, download assets, and explicitly approve preparation for play without a model gateway.

The same application workflow is available through authenticated `/api/dungeons` routes and CLI commands:

```bash
uv run --frozen dm dungeon generate /data/campaign/layout-request.json \
  --campaign <campaign-uuid> --title "Sunken Archive"
uv run --frozen dm dungeon inspect <artifact-uuid> --campaign <campaign-uuid>
uv run --frozen dm dungeon compare <left-version> <right-version> \
  --campaign <campaign-uuid>
uv run --frozen dm dungeon regenerate <artifact-uuid> <parent-version> \
  --campaign <campaign-uuid> --seed 888888 --lock room_entrance \
  --summary "Regenerate unlocked geometry."
uv run --frozen dm dungeon export <version-uuid> --campaign <campaign-uuid>
uv run --frozen dm dungeon approve <artifact-uuid> <version-uuid> \
  --campaign <campaign-uuid> --reason "Reviewed for play."
```

`approved_for_play` is preparation state only. It does not make planned encounters, discoveries, deaths, treasure, or any other event canonical.

## Immutable Library Foundation

Alembic revision `0003_library_sources` defines campaign/global-rules source scopes, stable logical documents and safe relative path history, exact immutable UTF-8 revisions with verified SHA-256 identity, typed authority/document/ruleset/visibility metadata, exact-span chunks with PostgreSQL full-text vectors, terminal ingestion-run pins, and candidate/active corpus snapshots. Database guards reject cross-scope membership, broader child visibility, source/chunk mutation, and membership changes after activation.

The internal P1-02 Library service now ingests bounded strict-UTF-8 files through named allowlisted roots, rejects traversal/symlinks/non-files, reuses unchanged revisions, appends novel edits, retains identity across exact moves, records explicit duplicates, returns review-required ambiguity without mutation, and retires missing files only through an explicit reconciliation call. Public CLI/API ingestion remains deferred to P1-06; no Markdown parser, chunks, search, embeddings, model calls, or canonical writes are involved yet.

## Current Next Step

Begin **P1-03** on the grounding path: implement the versioned deterministic Markdown parser/chunker with exact heading/block offsets and adversarial synthetic fixtures. [`PROJECT_STATUS.md`](PROJECT_STATUS.md) contains the exact handoff.

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
