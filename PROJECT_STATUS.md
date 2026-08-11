# Project Status and Handoff

> This is the concise implementation resume point. Update it at the end of each task.

## Snapshot

- **Last updated:** 2026-08-10
- **Lifecycle:** implementation underway; the first executable scaffold is complete.
- **Current phase:** P0 foundation is established and the dungeon-first path is ready.
- **Current task:** **P0-01 — Scaffold the Python package** is complete.
- **Next task:** **P7-02 — Pure dungeon package and versioned primitive vocabulary**.

Always inspect `git status --short --branch` and the latest log before changing files.

## Completed Work

- Planning documents define product scope, architecture, invariants, and incremental gates.
- P0-01 added the Python 3.12 root distribution with FastAPI, Typer, and Uvicorn.
- The `dm` CLI exposes `--help` and `version`.
- The FastAPI factory has metadata only and no business routes.
- Focused package, CLI, and HTTPX ASGI tests are configured with Ruff and strict mypy.
- `uv.lock` was generated and verified in an isolated pinned Python 3.12 container.

## Current Architecture Invariants

- Models may propose canonical changes but may never commit canonical state or approve preparation artifacts.
- Canonical writes use validated change sets and one atomic campaign revision.
- Preparation approval does not make planned events canonical.
- The pure `dm_dungeon` package must not depend on Workbench persistence, FastAPI, SQLAlchemy, retrieval, or model clients.
- Deterministic generation cannot call `uuid4()` internally; generated identities derive from pinned inputs and versions.
- Real campaign text, proprietary rules content, credentials, and provider responses are not test fixtures.

## Next Exact Task — P7-02

1. Clarify deterministic generated-component identity in the architecture and plan.
2. Add `packages/dungeon-engine` as an independently tested `uv` workspace member.
3. Define strict versioned dungeon brief, topology, geometry, visibility, and package contracts.
4. Add canonical JSON/file/CLI adapters using synthetic fixtures.
5. Enforce the package dependency boundary in tests.
6. Run root and package tests, Ruff, formatting, strict mypy, CLI smoke tests, and `git diff --check` in isolation.

Do not add topology algorithms, persistence, Workbench orchestration, or model integration during P7-02.

## Last Verification

The P0-01 gate passed: frozen dependency sync, `dm --help`, `dm version`, 4 unit tests, Ruff lint/format, strict mypy, and `git diff --check`.

## Handoff

- **Status:** P0-01 complete.
- **Changed:** Python packaging, lockfile, importable package, API factory, CLI, and focused tests.
- **Checks:** all P0-01 gates passed in an isolated Python 3.12 container.
- **Problems:** none unresolved; no database, migration, credential, or generated campaign data exists.
- **Working tree:** the public P0-01 snapshot is committed; always inspect local-only files before work.
- **Next:** P7-02; first record deterministic generated-ID rules, then create the pure workspace package.
