# Project Status and Handoff

> This is the concise implementation resume point. Update it at the end of each task.

## Snapshot

- **Last updated:** 2026-08-11
- **Lifecycle:** implementation underway; the provider-independent Dungeon Studio, deterministic dungeon kernel, PostgreSQL foundation, preparation lifecycle, immutable Library source registry, and P2's independent embeddings, hybrid retrieval, retrieval audit, and eval baseline are complete. The active priority is standalone prompt-to-dungeon-package generation.
- **Current phase:** P4/P7 — Standalone prompted Dungeon Studio vertical slice.
- **Current task:** P4-07 in progress; roadmap remains reprioritized from P3 canonical revisions to the standalone prompt-to-dungeon-package path.
- **Next task:** **P5-01 — Entities, aliases, mentions, and merge history**.
- **Schema head:** `0006_library_retrieval_runs`.
- **Public baseline:** history begins with the final architecture/roadmap snapshot, uses the public GitHub author identity, and is licensed `AGPL-3.0-only`.

Always inspect `git status --short --branch` and the latest log before changing files.

## Completed Implementation

- **P0-01 through P0-04:** Python 3.12/FastAPI/Typer scaffold, typed configuration, default-deny authentication, structured logging, PostgreSQL/pgvector, Alembic migrations, readiness, diagnostics, and isolated contributor gates.
- **P7-01:** immutable preparation artifacts, versions, lifecycle audit, generation runs, assets, and transactional preparation services.
- **P7-02 through P7-08:** independently packaged deterministic dungeon contracts, topology/layout/geometry validation, SVG/PNG/exact-scale PDF rendering, and Roll20-compatible export.
- **P7-11:** shared provider-independent Dungeon Studio workflows across CLI, JSON API, and signed-session/CSRF web interfaces, including comparison, regeneration locks, exports, and preparation approval.
- **P1-01:** immutable source documents, path history, exact revisions/chunks, ingestion runs, corpus snapshots, authority/ruleset/visibility constraints, and lexical vectors.
- **P1-02:** allowlisted source discovery, descriptor-relative no-symlink reads, and transactional unchanged/edit/reversion/move/duplicate/missing/restore/ambiguity reconciliation.
- **P2-01:** provider-independent Python embedding contracts, separate hosted credential/retention configuration, immutable embedding-profile and exact chunk-embedding persistence, deterministic network-free fake provider, and a local-runtime benchmark probe.
- **P2-02:** durable profile/snapshot-pinned embedding runs and chunk-item lifecycle records, bounded synchronous fake-provider batches, exact derivation reuse, bounded transient retries, restart recovery, and completion guards that prevent partial vector-ready runs.
- **P2-03:** vector search that requires an explicit active snapshot and compatible completed run, applies the exact lexical authorization filters before nearest-neighbor ranking, returns only immutable chunk citations/snippets, and falls back to filtered lexical retrieval when vectors are unavailable.
- **P2-04:** deterministic versioned reciprocal-rank fusion over bounded authorized lexical/vector results, exact-name boosts, citation/span deduplication, and bounded authorized neighboring-source context without a learned reranker.
- **P2-05:** immutable source-body-free retrieval audit records with scope/version/citation/score/timing pins, synthetic diffable golden retrieval cases, and deterministic source-recall/latency evaluation reporting.
- **P4-02:** private Node 22.19+ `pi-ai` gateway package with a lockfile-pinned `0.84.1` provider/`Models` integration, allowlisted OpenAI Codex OAuth/OpenAI API-key/faux providers, restrictive serialized credential persistence, internal-token-protected HTTP/SSE contracts, display-safe login events, normalized streams, and cancellation.
- **P4-03:** bounded task-scope contract in Python with explicit DM-only defaults, standalone-dungeon rejection of grounding fields, and a typed `TaskScope`/`TaskType` resolution helper that prevents prompt-level scope broadening.

Migrations are `0001_foundation`, `0002_preparation`, `0003_library_sources`, `0004_library_embeddings`, `0005_library_embedding_runs`, and `0006_library_retrieval_runs`.

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

## Next Exact Task — P4-04

1. Define a strict versioned `GenerationContextEnvelope[T]` and first `DungeonGenerationContext` payload without growing a universal optional-field model.
2. Keep scope/provenance fields narrow, hashed, and replayable while rejecting unknown envelope fields or payload versions.
3. Add synthetic hash round-trip and scope-change tests before any dungeon-generation model/tool loop is introduced.

## Last Verification

P1 implementation checks passed:

- `pytest -q tests/unit/test_markdown_chunker.py` → `4 passed in 0.04s`
- `pytest -q tests/unit` → `104 passed in 3.19s`
- Docker-backed `pytest -q tests/integration` → `33 passed in 19.31s`
- strict mypy across `src/dm_assistant` → no issues
- Ruff across `src` and `tests` → all checks passed
- `git diff --check` → clean

P2-01 static diagnostics passed:

- focused editor diagnostics for embedding contracts/fake/benchmark, Library models/migration/schema test, and embedding settings/config tests → no errors.
- The terminal wrapper could not start any command because its `rg` dependency is absent, so focused `pytest`, Alembic migration round-trip, and `git diff --check` remain pending.

P2-02 static diagnostics passed:

- focused editor diagnostics for embedding run models/migration, runner, contracts, package exports, and integration coverage → no errors.
- The terminal wrapper remains blocked before command execution because `rg` is absent, so the new focused PostgreSQL test, migration round-trip, and `git diff --check` remain pending.

P2-03 static diagnostics passed:

- focused editor diagnostics for vector contracts, Library exports, retrieval service, and unit/integration coverage → no errors.
- The terminal wrapper remains blocked before command execution because `rg` is absent, so the new focused PostgreSQL test, migration round-trip, and `git diff --check` remain pending.

P2-04 static diagnostics passed:

- focused editor diagnostics for hybrid contracts, exports, fusion/context service, and unit/integration coverage → no errors.
- The terminal wrapper remains blocked before command execution because `rg` is absent, so the new focused PostgreSQL test, migration round-trip, and `git diff --check` remain pending.

P2-05 static diagnostics passed:

- focused editor diagnostics for retrieval audit contracts/models/migration/service, synthetic eval harness/golden suite, Library exports, and audit integration coverage → no errors.
- The terminal wrapper remains blocked before command execution because `rg` is absent, so the focused unit/eval/PostgreSQL tests, migration round-trip, and `git diff --check` remain pending.

P4-02 checks passed:

- `npm --prefix model-gateway run check` → passed.
- `npm --prefix model-gateway run build` → passed.
- `npm --prefix model-gateway test` → `4 passed` using only Pi's deterministic faux provider plus an in-memory login runtime.
- `git diff --check` → clean.
- `npm --prefix model-gateway audit --omit=dev --audit-level=low` could not query npm's advisory endpoint because the sandbox network allowlist blocked it; repeat from a network-permitted review environment.

P4-03 checks passed:

- `PYTHONPATH=src /home/codespace/.python/current/bin/python -m pytest -q tests/unit/test_task_scope_contracts.py tests/unit/test_preparation_contracts.py` → `8 passed in 0.38s`.
- `git diff --check` → clean.

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

- **Status:** P1-01 through P1-06, P2-01 through P2-05, and P4-02 through P4-06 are complete; P4-07 is now underway for the standalone prompt-to-dungeon-package path.
- **Changed:** P4-02 adds the independent `model-gateway/` Node package (`@earendil-works/pi-ai` exactly pinned to `0.84.1` with an npm lockfile), private host validation, internal-token-protected health/catalog/auth/login/stream/cancellation endpoints, a `0600` atomic credential store, normalized SSE events, deterministic faux-provider tests, and the matching root ignore rules. P4-03 adds the bounded Python `TaskScope`/`TaskType` contract in [src/dm_assistant/modules/scope.py](src/dm_assistant/modules/scope.py) and focused synthetic tests in [tests/unit/test_task_scope_contracts.py](tests/unit/test_task_scope_contracts.py). P4-04 adds strict generation-context envelope and standalone dungeon context contracts in [src/dm_assistant/modules/preparation/contracts.py](src/dm_assistant/modules/preparation/contracts.py) plus focused round-trip coverage in [tests/unit/test_preparation_contracts.py](tests/unit/test_preparation_contracts.py). P4-05 adds versioned model/task profile contracts, catalog validation, strict dungeon intent output, and bounded tool-loop orchestration in [src/dm_assistant/modules/modeling/contracts.py](src/dm_assistant/modules/modeling/contracts.py) and [src/dm_assistant/orchestration/modeling/service.py](src/dm_assistant/orchestration/modeling/service.py), with focused tests in [tests/unit/test_modeling_contracts.py](tests/unit/test_modeling_contracts.py) and [tests/unit/test_modeling_service.py](tests/unit/test_modeling_service.py). P4-06 adds the shared model-workbench UI/state foundation, device-code login flow, provider/model/task/effort selection, and cancellable/reconnectable bounded-run streaming in [src/dm_assistant/modules/modeling/workbench.py](src/dm_assistant/modules/modeling/workbench.py), [src/dm_assistant/web/routes.py](src/dm_assistant/web/routes.py), [src/dm_assistant/web/templates/model_panel.html](src/dm_assistant/web/templates/model_panel.html), and [tests/unit/test_web_auth.py](tests/unit/test_web_auth.py). P4-07 adds the Ask page, attachment upload/download, ask-history/comparison baseline state, and SSE-backed ask run controls in [src/dm_assistant/web/routes.py](src/dm_assistant/web/routes.py), [src/dm_assistant/web/templates/ask.html](src/dm_assistant/web/templates/ask.html), [src/dm_assistant/web/templates/base.html](src/dm_assistant/web/templates/base.html), [src/dm_assistant/modules/modeling/workbench.py](src/dm_assistant/modules/modeling/workbench.py), and [tests/unit/test_web_auth.py](tests/unit/test_web_auth.py).
- **Checks:** `uv run pytest -q tests/unit/test_web_auth.py tests/unit/test_modeling_contracts.py tests/unit/test_modeling_service.py tests/unit/test_preparation_contracts.py tests/unit/test_task_scope_contracts.py` passed (`18 passed`). `git diff --check` passed. The sandbox blocked npm's advisory endpoint during `npm audit`; rerun that command from a network-permitted dependency-review environment. Earlier P2 executable checks remain outstanding despite terminal recovery.
- **Problems:** No P4-02 or P4-03 application-code failures remain. The P2 phase gate still needs executable retrieval-eval evidence, including a real local runtime/profile quality-resource comparison, before selecting an ONNX model.
- **Working tree:** `PROJECT_STATUS.md`, `src/dm_assistant/api/app.py`, `src/dm_assistant/modules/__init__.py`, `src/dm_assistant/modules/modeling/__init__.py`, `src/dm_assistant/modules/modeling/contracts.py`, `src/dm_assistant/modules/modeling/workbench.py`, `src/dm_assistant/modules/preparation/__init__.py`, `src/dm_assistant/modules/preparation/contracts.py`, `src/dm_assistant/orchestration/__init__.py`, `src/dm_assistant/orchestration/modeling/__init__.py`, `src/dm_assistant/orchestration/modeling/service.py`, `src/dm_assistant/web/routes.py`, `src/dm_assistant/web/templates/ask.html`, `src/dm_assistant/web/templates/base.html`, `src/dm_assistant/web/templates/dungeons.html`, `src/dm_assistant/web/templates/model_panel.html`, `tests/unit/test_modeling_contracts.py`, `tests/unit/test_modeling_service.py`, and `tests/unit/test_web_auth.py` are modified. No user changes were reverted.
- **Next:** P5-01; add entities, aliases, mentions, and merge history.
- **Suggested commit:** `P4-07 add ask workflow and comparison baseline`.
