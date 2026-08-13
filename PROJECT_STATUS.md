# Project Status and Handoff

> This is the concise implementation resume point. Update it at the end of each task.

## Snapshot

- **Last updated:** 2026-08-12
- **Lifecycle:** P7-10a.1 is complete. A normal headless request is now just `dm dungeon prompt "..."`: the Workbench bootstraps/uses an inspectable active campaign, resolves and saves a compatible task-specific model default, runs gateway-owned OAuth inline when needed, generates and pins a seed, uses the validated model-authored brief title, and returns all resolved defaults. P7-10b remains next for the equivalent real web experience.
- **Current phase:** P7 — Dungeon and Map Generation.
- **Current task:** P7-10b starting — web streaming and final Dungeon Studio eval gate.
- **Validated status:** P3-01 is unstarted: no P3 migration, implementation, or commit exists. P5-01 is complete in committed `eea08a4`; P5-02 is unstarted: no predicate schema, migration, operation, or commit exists.
- **Fast-track note:** P3 is required only to promote generated dungeon facts to campaign canon. It does not block standalone prompt-to-package preparation work; P5-02 remains deferred until explicit campaign grounding needs it.
- **Next task:** **P7-10b — add the gateway-backed Dungeon Studio prompt web workflow.**
- **Schema head:** `0008_workbench_defaults`.
- **Public baseline:** history begins with the final architecture/roadmap snapshot, uses the public GitHub author identity, and is licensed `AGPL-3.0-only`.

Always inspect `git status --short --branch` and the latest log before changing files.

## Completed Implementation

- **P0-01 through P0-04:** Python 3.12/FastAPI/Typer scaffold, typed configuration, default-deny authentication, structured logging, PostgreSQL/pgvector, Alembic migrations, readiness, diagnostics, and isolated contributor gates.
- **P7-01:** immutable preparation artifacts, versions, lifecycle audit, generation runs, assets, and transactional preparation services.
- **P7-02 through P7-08:** independently packaged deterministic dungeon contracts, topology/layout/geometry validation, SVG/PNG/exact-scale PDF rendering, and Roll20-compatible export.
- **P7-11:** shared provider-independent Dungeon Studio workflows across CLI, JSON API, and signed-session/CSRF web interfaces, including comparison, regeneration locks, exports, and preparation approval.
- **P7-10a:** real private-gateway provider/model catalog and login coordination in Python, hyphen-safe transport model IDs, pinned live dungeon-profile resolution, shared runtime composition, `dm model` operations, synchronous `dm dungeon prompt`, Compose/live-provider documentation, and a scripted faux-gateway CLI-to-PostgreSQL package test.
- **P7-10a.1:** active-campaign bootstrap/switching and optional campaign overrides across Dungeon Studio CLI commands; persisted non-secret task model defaults; inline OAuth continuation; optional generated seed and model-authored title; resolved-default output; and empty-workspace CLI-to-package integration coverage.
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
- **P10-04 deployment baseline:** pinned non-root Workbench and model-gateway images, a full private Compose topology with PostgreSQL, a one-shot volume-permission initializer, migration-aware Workbench startup, readiness health checks, conservative resource/restart policy, separate database/gateway-credential/asset/scratch/source volumes, idempotent local secret bootstrap, explicit atomic managed-source import, and documented native versus full-stack workflows. P10's later security, backup, observability, and release gates remain unstarted.

Migrations are `0001_foundation`, `0002_preparation`, `0003_library_sources`, `0004_library_embeddings`, `0005_library_embedding_runs`, `0006_library_retrieval_runs`, `0007_campaign_knowledge_entities`, and `0008_workbench_defaults`.

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

## Next Exact Task — P7-10b

1. Replace the synthetic-only Dungeon Studio model panel path with the P7-10a gateway-backed application service and add the standalone prompt form.
2. Stream/cancel/reconnect durable prompt-run status while preserving gateway-unavailable manual Studio operations.
3. Add context inspection, faux-provider browser cases, and first-pass/repair/preservation evaluation reporting.

## Last Verification

P7-10a.1 onboarding follow-up checks:

- Full root unit suite → `141 passed in 2.18s`.
- Bootstrap tests prove distinct mode-`0600` secrets, idempotent persistence, placeholder replacement, and no token echo on later runs.
- Managed-source import rejects symlinks before container access; an isolated Podman smoke imported a synthetic file into a temporary managed volume and verified `current/note.md`, then removed the volume.
- Focused Ruff/format and strict mypy → passed; shell syntax and `git diff --check` → passed.
- `podman compose config --quiet` with synthetic secrets → passed. Docker was unavailable in this environment; Make auto-detection selected Podman.

P7-10a.1 checks:

- Full root unit suite → `138 passed in 1.85s`.
- Focused Ruff lint/format and strict mypy over migration/default-selection/campaign/prompt/CLI/web changes → passed.
- Node gateway TypeScript checks and faux tests → passed (`4` tests).
- The disposable Podman gate built both distributions, completed the `0008_workbench_defaults` migration round trip, and ran `40` integration tests. Both Dungeon Studio CLI tests passed, including empty-campaign bootstrap, omitted campaign/provider/model/seed/title, scripted faux completion, derived title, saved model default, and persisted package. The aggregate gate remains red only on the same three unrelated pre-existing Library/schema failures documented below (`37 passed, 3 failed`).
- `sh -n scripts/check-container.sh` and `git diff --check` → passed.
- Live OAuth/model execution remains manual and was not run.

P7-10a focused checks passed:

- Focused Ruff lint/format over all changed Python and test files → passed.
- `uv run mypy` over the changed gateway/model/prompt/runtime/CLI modules → passed.
- `uv run pytest -q tests/unit/test_cli.py tests/unit/test_model_gateway_client.py tests/unit/test_prompted_dungeon_workflow.py tests/unit/test_preparation_contracts.py tests/unit/test_task_scope_contracts.py` → `22 passed in 0.57s`.
- `npm --prefix model-gateway run check` and `npm --prefix model-gateway test` → passed (`4` Node tests).
- The disposable Podman gate built both wheels, migrated to head, and ran all `40` PostgreSQL integration tests; both Dungeon Studio CLI tests passed, including scripted faux gateway → persisted prompted package. The aggregate gate then stopped on three pre-existing unrelated Library/schema failures: metadata drift for P5-01 checks, duplicate vector result behavior, and an embedding-resume fixture missing required document path history.
- The first gate attempt exposed stale Compose assumptions in `scripts/check-container.sh`; it now supplies required synthetic parse-time secrets and gives the temporary test runner an ephemeral outbound network plus a `postgres` alias. Cleanup removes the database stack, volumes, and runner network.
- Full-tree Ruff and mypy still report pre-existing unrelated failures in Library/web/model-workbench files; focused changed-file checks pass.
- `sh -n scripts/check-container.sh` and `git diff --check` → passed.
- Live OAuth/model execution remains manual and was not run.

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

- **Status:** P7-10a and P7-10a.1 are complete; P7-10b is next. P3-01 and P5-02 remain unstarted and do not block standalone preparation generation.
- **Changed:** In addition to `0008` and streamlined prompt defaults, full Compose no longer requires host source directories. Campaign/rules sources use empty managed volumes mounted read-only in Workbench; explicit `make import-campaign-sources SOURCE=...` / `make import-rules-sources SOURCE=...` operations reject symlinks and atomically replace the current source tree, while immutable Library ingestion remains separate. `make stack-up` now auto-detects Docker/Podman and idempotently creates an ignored mode-`0600` `.env` with distinct missing database/API/session/internal-gateway secrets; provider credentials remain gateway-owned OAuth data. Campaign Library ingestion resolves the active campaign when omitted.
- **Checks:** Full root unit suite (`141 passed`), focused Ruff/format, focused strict mypy, 4 Node tests, migration/build execution, bootstrap/import unit and Podman smoke tests, Compose static config, shell syntax, and diff checks passed. The earlier Podman aggregate run passed all new/default-resolution Dungeon Studio integration coverage and remains red on the same three unrelated Library/schema tests (`37 passed, 3 failed`). Live OAuth/model execution was not run.
- **Problems:** the browser model workbench still uses synthetic in-process behavior; P7-10b must connect it to this gateway-backed default resolver. Automatic active-campaign grounding is intentionally not enabled by these convenience defaults. The gateway's default faux response is not a complete dungeon intent, so automated end-to-end coverage scripts the faux transport. Existing full-tree Ruff/mypy and three Library/schema integration failures remain outside this task.
- **Working tree:** P7-10a.1 onboarding follow-up changes to Compose, Make/bootstrap/import scripts, docs, active-campaign Library defaulting, tests, and this handoff are modified and uncommitted. No unrelated work was overwritten.
- **Next:** P7-10b; first replace the synthetic Dungeon Studio model-panel start path with a call to the shared gateway-backed prompt/default-resolution application service.
- **Suggested commit:** `P7-10a.1 automate stack bootstrap and source import`.
