# Project Status and Handoff

> This is the concise implementation resume point. Update it at the end of each task.

## Snapshot

- **Last updated:** 2026-08-10
- **Lifecycle:** planning complete; application implementation has not started.
- **Current phase:** P0 — Foundation and Reproducible Development.
- **Current task:** none in progress.
- **Next task:** **P0-01 — Scaffold the Python package**.

Always inspect `git status --short --branch` and the latest log before changing files.

## Completed Planning Work

- Product scope and boundaries are in `dm-assistant-project-goals.md`.
- Architecture and accepted invariants are in `dm-assistant-technical-architecture.md`.
- Incremental tasks and phase gates are in `dm-assistant-implementation-plan.md`.
- `README.md` provides the public project overview.
- `AGENTS.md` defines implementation and handoff discipline.
- DOC-06 established one modular Python Workbench, a separately packaged in-process dungeon kernel, a private model gateway, and narrow domain-specific generation-context payloads.

## Current Architecture Invariants

- Models may propose canonical changes but may never commit canonical state or approve preparation artifacts.
- Canonical writes use validated change sets and one atomic campaign revision.
- Preparation approval does not make planned events canonical.
- Deterministic code owns generated IDs, exact geometry, validation, rendering, and exports.
- Campaign sources, revisions, citations, and generated artifacts retain immutable provenance.
- Authorization and visibility filtering happen before retrieval or model-context construction.
- Real campaign text, proprietary rules content, credentials, and provider responses are not test fixtures.

## Next Exact Task — P0-01

Create the smallest Python 3.12 Workbench scaffold:

1. Add the root `pyproject.toml`, `.gitignore`, and `src/dm_assistant` package.
2. Add a minimal FastAPI application factory and Typer CLI with `--help` and `version`.
3. Add focused package, CLI, and ASGI tests.
4. Generate a frozen `uv.lock` in an isolated Python 3.12 environment.
5. Run pytest, Ruff, formatting, strict mypy, CLI smoke tests, and `git diff --check`.

Do not add database, model-provider, document-schema, or dungeon-workspace implementation during P0-01.

## Last Verification

The planning gate passed: Markdown fences and local links were checked, implementation task IDs were unique, architecture/plan consistency checks passed, and `git diff --check` reported no errors.

## Handoff

- **Status:** DOC-06 complete.
- **Changed:** planning, architecture, implementation roadmap, README, and agent instructions.
- **Checks:** documentation consistency and diff checks passed.
- **Problems:** no implementation blocker; real source/provider/deployment inputs remain deliberately open.
- **Working tree:** the public planning snapshot is committed; always inspect local-only files before work.
- **Next:** P0-01; begin with `pyproject.toml` and the smallest importable CLI/API tests.
