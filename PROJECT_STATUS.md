# Project Status and Handoff

> This is the concise implementation resume point. Update it at the end of each task.

## Snapshot

- **Last updated:** 2026-08-12
- **Lifecycle:** P7-09 is complete. Standalone model-authored brief/topology intent now travels through the private token-authenticated Node gateway, uses only schema-bound deterministic review/layout/regeneration-preview tools, performs bounded diagnostic repair, and persists standalone context plus model/tool lineage. The P10-04 container/Compose baseline is also complete early: native development remains fast, while the same repository provides a complete local/Proxmox Compose stack.
- **Current phase:** P7 — Dungeon and Map Generation.
- **Current task:** P7-10 starting — grounded Dungeon Studio integration and final eval gate.
- **Validated status:** P3-01 is unstarted: no P3 migration, implementation, or commit exists. P5-01 is complete in committed `eea08a4`; P5-02 is unstarted: no predicate schema, migration, operation, or commit exists.
- **Fast-track note:** P3 is required only to promote generated dungeon facts to campaign canon. It does not block standalone prompt-to-package preparation work; P5-02 remains deferred until explicit campaign grounding needs it.
- **Next task:** **P7-10 — add standalone prompt-to-dungeon CLI/API/web integration.**
- **Schema head:** `0007_campaign_knowledge_entities`.
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
- **P5-01:** campaign-knowledge entity, alias, mention, merge, split, archive, and candidate-resolution persistence in committed `eea08a4`.
- **P10-04 deployment baseline:** pinned non-root Workbench and model-gateway images, a full private Compose topology with PostgreSQL, a one-shot volume-permission initializer, migration-aware Workbench startup, readiness health checks, conservative resource/restart policy, separate database/gateway-credential/asset/scratch volumes, configurable read-only source mounts, and documented native versus full-stack workflows. P10's later security, backup, observability, and release gates remain unstarted.

Migrations are `0001_foundation`, `0002_preparation`, `0003_library_sources`, `0004_library_embeddings`, `0005_library_embedding_runs`, `0006_library_retrieval_runs`, and `0007_campaign_knowledge_entities`.

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

## Next Exact Task — P7-10

1. Add `dm dungeon prompt` plus authenticated API/web controls that compose `DungeonPromptService` with `PiGatewayClient.from_settings`.
2. Stream/cancel/reconnect durable prompt-run status through the existing shared model components while preserving gateway-unavailable manual Studio operations.
3. Add context inspection, faux-provider integration cases, and first-pass/repair/preservation evaluation reporting.

## Last Verification

P7-09 completion checks passed:

- `uv run ruff check` across the changed Python client/config/model/dungeon modules and focused tests → passed.
- `uv run mypy src/dm_assistant/config.py src/dm_assistant/adapters/model_gateway.py src/dm_assistant/orchestration/modeling/service.py src/dm_assistant/orchestration/dungeons/prompting.py` → passed.
- `uv run pytest -q tests/unit/test_config.py tests/unit/test_model_gateway_client.py tests/unit/test_modeling_contracts.py tests/unit/test_modeling_service.py tests/unit/test_prompted_dungeon_workflow.py tests/unit/test_preparation_contracts.py tests/unit/test_task_scope_contracts.py` → `39 passed in 0.48s`.
- `uv run pytest -q tests/unit/test_web_auth.py tests/unit/test_api.py tests/unit/test_doctor.py` → `18 passed in 1.72s`.
- `npm --prefix model-gateway run check` and `npm --prefix model-gateway test` → passed (`4` Node tests).
- The PostgreSQL prompted-lineage integration test remains unexecuted because `DM_TEST_DATABASE_URL` is unset.

P10-04 deployment-baseline checks passed:

- `podman compose config --quiet` with synthetic required environment values → passed.
- Both production images built successfully with `podman compose build`; their configured runtime users are `workbench` and `gateway`, not root.
- An isolated Podman Compose stack on alternate localhost ports started the volume initializer, PostgreSQL, private model gateway, and Workbench. All service health checks became healthy; `GET /health/ready` returned `{"status":"ready", ...}` after the Workbench migration.
- `npm --prefix model-gateway run check` and `npm --prefix model-gateway test` → passed (`4` tests).
- The temporary stack, network, and named volumes were removed; `git diff --check` → clean.

P7-09 backend slice checks passed:

- `uv run ruff check` across the changed prompt/model/dungeon modules and focused tests → passed.
- `uv run mypy src/dm_assistant/modules/modeling/contracts.py src/dm_assistant/orchestration/modeling/service.py src/dm_assistant/orchestration/dungeons/contracts.py src/dm_assistant/orchestration/dungeons/prompting.py src/dm_assistant/orchestration/dungeons/service.py` → passed.
- `uv run pytest -q tests/unit/test_prompted_dungeon_workflow.py tests/unit/test_modeling_contracts.py tests/unit/test_modeling_service.py tests/unit/test_preparation_contracts.py tests/unit/test_task_scope_contracts.py tests/unit/test_web_auth.py tests/unit/test_api.py tests/unit/test_doctor.py` → `36 passed in 1.75s`.
- `tests/integration/test_dungeon_studio_workflow.py` has prompted-lineage coverage but could not run because `DM_TEST_DATABASE_URL` is unset.

P5-01 focused checks passed:

- `uv run pytest -q tests/integration/test_campaign_knowledge.py tests/unit/test_readiness.py tests/unit/test_api.py tests/unit/test_doctor.py` → `20 passed, 2 skipped in 0.75s`.
- `uv run python -m py_compile src/dm_assistant/modules/campaign_knowledge/contracts.py src/dm_assistant/modules/campaign_knowledge/models.py src/dm_assistant/modules/campaign_knowledge/service.py src/dm_assistant/modules/campaign_knowledge/__init__.py migrations/versions/0007_campaign_knowledge_entities.py src/dm_assistant/modules/__init__.py src/dm_assistant/readiness.py` → passed.
- `uv run ruff check src/dm_assistant/modules/campaign_knowledge src/dm_assistant/modules/__init__.py src/dm_assistant/readiness.py tests/integration/test_campaign_knowledge.py migrations/versions/0007_campaign_knowledge_entities.py` → passed.
- `git diff --check` → clean.
- PostgreSQL migration round-trip was not run here because `DM_TEST_DATABASE_URL` is unset in this environment; the new migration remains unexecuted until a test database is available.

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

- **Status:** P3-01 and P5-02 are unstarted. P5-01 is committed. P7-09 is complete; the P10-04 deployment baseline is complete early; P7-10 remains next for user-facing Studio integration.
- **Changed:** `PiGatewayClient` uses the configured private URL/shared internal token to send profile-bound user messages and server-generated tool schemas to `/v1/streams`, then strictly decodes normalized SSE text/tool/usage/completion events without provider-error leakage. Gateway usage events are normalized. The standalone prompt workflow now offers only typed brief/topology review, layout generation/validation, and code-owned targeted-regeneration preview tools; no model tool writes files, SVG, approved artifacts, or canonical state. Gateway configuration requires a private internal token whenever enabled. The deployment baseline adds non-root Workbench/gateway images, private full-stack Compose with volume initialization and health/resource controls, Make targets for native and full-stack loops, and macOS/Proxmox workflow documentation.
- **Checks:** Ruff, strict mypy, 39 focused prompt/config/model tests, 18 web/API/doctor tests, Node TypeScript/faux-gateway tests, Compose static configuration, two image builds, and an isolated healthy full-stack Podman smoke test passed. The smoke database/network/volumes were removed. The PostgreSQL prompted-lineage integration test remains unexecuted because `DM_TEST_DATABASE_URL` is unset. Final `git diff --check` still needs its post-handoff run.
- **Problems:** no known application-code failure. Live-provider verification remains a manual operator action: configure the shared gateway token locally without sharing credentials. P3 continues to block promotion of generated facts to canon, not generation or preparation approval. P10-01/02/03/05/06 release work remains unstarted; this baseline intentionally does not claim backup/restore, adversarial, metrics, or production acceptance coverage.
- **Working tree:** P7-09 prompt/gateway changes remain modified or untracked. Deployment changes add `Dockerfile`, `model-gateway/Dockerfile`, Compose, non-root startup support, Docker ignore files, Make targets, and native/full-stack/Proxmox documentation in `README.md`, `.env.example`, and the technical architecture. No unrelated user changes were reverted.
- **Next:** P7-10; add the standalone prompt CLI/API/web command and route as the first concrete action.
- **Suggested commit:** `P7-09 add bounded private-gateway dungeon tools`.
