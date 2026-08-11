# Project Status and Handoff

> This is the concise implementation resume point. Update it at the end of each task.

## Snapshot

- **Last updated:** 2026-08-11
- **Lifecycle:** implementation underway; the provider-independent Dungeon Studio, deterministic dungeon kernel, PostgreSQL foundation, preparation lifecycle, and immutable Library source registry are complete.
- **Current phase:** P1 — Immutable campaign/rules sources and lexical grounding.
- **Current task:** **P1-02 — Source registry and idempotent revision ingestion** is complete.
- **Next task:** **P1-03 — Markdown parser and deterministic chunker**.
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

## Next Exact Task — P1-03

1. Read P1-03 and the architecture sections for document revisions/chunks, source authority, and untrusted evidence.
2. Define strict versioned Markdown parser/chunker contracts for front matter, headings, semantic block kinds, exact source spans, page metadata, bounded size/overlap, diagnostics, and deterministic identities.
3. Preserve exact revision text and treat headings, lists, tables, fenced code, Unicode, links, and hostile instruction-like text as untrusted data.
4. Emit zero-based half-open offsets and verify every chunk maps exactly to its immutable revision text.
5. Persist chunks only for novel revisions; unchanged and move-only outcomes must not duplicate them.
6. Add synthetic deterministic/adversarial unit and PostgreSQL integration coverage.

Do not activate snapshots, search, embed, call a model, or write canonical campaign state during P1-03.

## Last Verification

The aggregate isolated gate passed:

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

- **Status:** P1-02 complete.
- **Changed:** Workbench platform through P1-02, three migrations, pure dungeon package, web/API/CLI workflows, tests, public documentation, AGPL licensing, and sanitized three-commit public history.
- **Checks:** the complete aggregate gate, public-history secret scan, license packaging verification, and Git object-graph checks passed.
- **Problems:** none unresolved; model and embedding runtimes remain intentionally disabled.
- **Working tree:** public `main` is committed and clean; local-only exclusions remain outside public history.
- **Next:** P1-03; begin with strict parser/chunker contracts and one adversarial synthetic Markdown fixture.
- **Suggested commit:** `P1-03 parse and deterministically chunk Markdown sources`.
