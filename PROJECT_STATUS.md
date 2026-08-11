# Project Status and Handoff

> This is the concise implementation resume point. Update it at the end of each task.

## Snapshot

- **Last updated:** 2026-08-11
- **Lifecycle:** implementation underway; the provider-independent Dungeon Studio, deterministic dungeon kernel, PostgreSQL foundation, preparation lifecycle, and immutable Library source registry are complete.
- **Current phase:** P1 — Immutable campaign/rules sources and lexical grounding.
- **Current task:** **P1 — Immutable campaign/rules sources and lexical grounding** is complete.
- **Next task:** **P2-01 — Independent embedding runtime/model abstraction**.
- **Schema head:** `0003_library_sources`.
- **Public baseline:** history begins with the final architecture/roadmap snapshot, uses the public GitHub author identity, and is licensed `AGPL-3.0-only`.

Always inspect `git status --short --branch` and the latest log before changing files.

## Completed Implementation

- **P0-01 through P0-04:** Python 3.12/FastAPI/Typer scaffold, typed configuration, default-deny authentication, structured logging, PostgreSQL/pgvector, Alembic migrations, readiness, diagnostics, and isolated contributor gates.
- **P7-01:** immutable preparation artifacts, versions, lifecycle audit, generation runs, assets, and transactional preparation services.
- **P7-02 through P7-08:** independently packaged deterministic dungeon contracts, topology/layout/geometry validation, SVG/PNG/exact-scale PDF rendering, and Roll20-compatible export.
- **P7-11:** shared provider-independent Dungeon Studio workflows across CLI, JSON API, and signed-session/CSRF web interfaces, including comparison, regeneration locks, exports, and preparation approval.
- **P1-01:** immutable source documents, path history, exact revisions/chunks, ingestion runs, corpus snapshots, authority/ruleset/visibility constraints, and lexical vectors.
- **P1-02:** allowlisted source discovery, descriptor-relative no-symlink reads, and transactional unchanged/edit/reversion/move/duplicate/missing/restore/ambiguity reconciliation.

Migrations are `0001_foundation`, `0002_preparation`, and `0003_library_sources`.

The public history contains three reviewed snapshots: final architecture/roadmap, the first executable Python scaffold, and the aggregate implementation through P1-02. Earlier local planning history is intentionally outside public `main`.

## Non-Negotiable Invariants

- A model may write canonical proposals only; it cannot commit canonical state or approve preparation artifacts.
- Canonical writes use a validated change set and create one atomic campaign revision.
- Preparation approval or use never makes planned events canonical.
- The pure `dm_dungeon` package cannot import Workbench application, persistence, retrieval, web, or provider code.
- Deterministic code owns IDs, geometry, pathfinding, rules arithmetic, validation, rendering, and exports.
- Generation context uses a small common provenance envelope plus strict domain payloads, not a universal optional-field object.
- Chat-model and embedding runtimes remain separate; lexical retrieval works without model credentials.
- Source authorization and visibility filters run before retrieval and context construction.
- Existing source revisions, spans, chunks, and snapshot membership are immutable.
- Player-facing exports fail closed and omit DM-only data and fingerprints.
- Real campaign text, proprietary rules/bestiary content, character sheets, credentials, and provider responses are not fixtures.

## Next Exact Task — P2-01

1. Read P2-01 and the architecture runtime-boundary requirements for embeddings.
2. Define a provider-independent embedding profile/runtime contract separate from chat-model transport.
3. Keep lexical retrieval as the usable baseline without an embedding credential.
4. Add only synthetic/fake embedding providers and fixtures; do not add chat-model embeddings.

## Last Verification

P1 implementation checks passed:

- `pytest -q tests/unit/test_markdown_chunker.py` → `4 passed in 0.04s`
- `pytest -q tests/unit` → `104 passed in 3.19s`
- Docker-backed `pytest -q tests/integration` → `33 passed in 19.31s`
- strict mypy across `src/dm_assistant` → no issues
- Ruff across `src` and `tests` → all checks passed
- `git diff --check` → clean

The aggregate isolated gate from the prior public-history state also passed:

- frozen sync and both wheel builds;
- migration base/head round trips through `0003_library_sources`;
- 28 PostgreSQL integration tests;
- 100 root unit tests;
- 106 dungeon-package tests;
- ready `dm doctor`, CLI/fixture smoke tests, Ruff lint/format, strict mypy, and `git diff --check`;
- disposable database/container/network/volume cleanup;
- containerized Gitleaks scan of all three public commits with no findings;
- root and `dm-dungeon` wheel metadata/license-file verification for `AGPL-3.0-only`.

## Handoff

- **Status:** P1-01 through P1-06 complete.
- **Changed:** Workbench platform through P1-02, three migrations, pure dungeon package, web/API/CLI workflows, tests, public documentation, AGPL licensing, sanitized three-commit public history, deterministic Markdown parsing/chunking, chunk persistence, snapshot publication, filtered lexical retrieval, and shared Library CLI/API source/document/search adapters.
- **Checks:** Docker-backed full integration suite (`33 passed`), full root unit suite (`104 passed`), strict mypy across application code, Ruff across source/tests, diagnostics, and `git diff --check` passed.
- **Problems:** none unresolved in P1; model and embedding runtimes remain intentionally disabled by design.
- **Working tree:** local P1 changes remain uncommitted across Library modules, runtime, CLI/API adapters, integration/unit tests, and this handoff file.
- **Next:** P2-01; first read the embedding runtime architecture constraints and define the profile/runtime contract without adding a provider dependency.
- **Suggested commit:** `P1 complete immutable Library sources and lexical search surface`.
