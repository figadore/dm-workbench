# DM Assistant Harness — Incremental Implementation Plan

## How to Use This Plan

This plan turns the product goals and architecture into small, resumable tasks. It is intentionally ordered so that each phase leaves a working capability and does not require the entire campaign ontology to be complete. The active priority is the standalone prompt-to-dungeon-package vertical slice described below; task IDs remain stable even when execution order changes.

- `PROJECT_STATUS.md` identifies the current task and is the live source of handoff state.
- Task IDs in this document are stable. Use them in handoffs and, when applicable, commit subjects.
- Task IDs group work by domain; numeric order is not the execution order across or within phases. Follow explicit dependencies and the current status file. P7-11 was added without renumbering stable P7 IDs and intentionally runs before P7-09/P7-10.
- When a design detail here conflicts with `dm-assistant-technical-architecture.md`, the architecture wins until the documents are reconciled explicitly.

## Delivery Strategy

Use a dungeon-first vertical path so the primary capability appears before the entire campaign-memory model is complete:

1. scaffold the reproducible Python Workbench package/test foundation (P0-01; the remaining P0 platform tasks can continue in parallel);
2. add an independently packaged, in-process pure dungeon kernel from typed synthetic specs—topology, seeded layout, geometry validation, deterministic SVG, PNG, low-ink tiled PDF, and Roll20 exports (P7-02 through P7-08);
3. complete preparation persistence and the model-independent Dungeon Studio so a human-authored brief/spec can be versioned, previewed, regenerated, exported, and approved without a provider (P7-01 and P7-11, after the required P0 platform tasks);
4. add immutable sources, filtered lexical grounding, and the common generation-context envelope with a narrow `DungeonGenerationContext` (P1/P2 and P4-03/P4-04); campaign grounding stays optional and eval-driven rather than becoming a prerequisite for the first prompted dungeon;
5. prioritize the standalone prompt-to-dungeon-package path: private `pi-ai` transport, standalone scope/context, a bounded dungeon task profile, constrained intent/repair, then stream/settings integration in the existing Studio (P4-02 through P4-06 and P7-09/P7-10);
6. build P3's canonical revision/change-set boundary separately before any generated fact, rules/profile operation, or session outcome can become campaign canon;
7. add synthetic normalized party/creature inputs and the Encounter Studio as a Workbench feature, then real adapters when formats are chosen (P4-01, P6, and P8); decide only after P8 whether a narrow `encounter-mechanics` package is justified;
8. extend the established revision boundary with precise campaign-memory state and the general Ask web workflow in parallel where useful (P5 and P4-07);
9. add session-close extraction from what actually happened (P9);
10. harden, back up, and deploy the Python app, in-process dungeon package, private model gateway, and PostgreSQL system (P10), while moving security, secrecy, eval, and backup checks into every earlier persisted slice.

The early dungeon kernel is deliberately pure and file/fixture driven: it does not need PostgreSQL, an LLM, or copyrighted data to prove that code—not the model—can create valid practical grids. It is a Python package boundary inside the same Workbench deployment, not a service. Persistence, domain-specific context, and prompted generation are integrated afterward. The canonical approval boundary must exist before generated material can promote facts into campaign state; until P3 is complete, that promotion path remains unavailable.

### Priority: Standalone Prompt-to-Dungeon Package

The next product milestone is a bounded workflow:

```text
DM prompt
    -> versioned typed dungeon intent
    -> deterministic DungeonPackage generation and validation
    -> preview, targeted regeneration, export, and preparation approval
```

This path is independent of campaign **facts**. A campaign remains the private Workbench ownership container required by the existing preparation-artifact, asset, approval, and audit schema, but a standalone request does not require a campaign revision, corpus snapshot, retrieval query, citations, rules profile, or canonical write. Its `DungeonGenerationContext` records explicit standalone provenance plus the prompt/input hash and requested constraints; it contains no campaign lore by default. The DM may opt into campaign grounding later through the existing Library/context path, but grounding is never implicit.

The model may author only strict high-level intent such as theme, room roles, connections, gates, features, and constraints. The Workbench and pure `dm_dungeon` package own IDs, geometry, connectivity, validation, rendering, exports, and all preparation persistence. The model cannot approve artifacts, commit canon, write arbitrary files, or emit renderer syntax. A first-class ownership container independent of even a campaign record is explicitly out of this milestone and requires a separate architecture decision; do not make preparation ownership nullable as incidental prompt-work scope.

## Confirmed Scope

### Included in the initial release

- One exposed campaign and one DM principal.
- Python/FastAPI modular monolith and shared CLI application services, with one independently packaged in-process pure dungeon kernel.
- PostgreSQL 16 with pgvector in the same instance.
- Immutable source revisions, chunks, corpus snapshots, and exact citations.
- Campaign and rules source classification.
- Lexical plus vector retrieval.
- Independent first-party web/CLI interaction with a private Node gateway using pinned `@earendil-works/pi-ai` for model auth/catalog/transport.
- Canonical revisions, readable summaries, detailed audit history, and human review.
- Entities, predicates, events, propositions/assertions, basic relative time, knowledge, belief, and provenance.
- Complete supplied character-sheet and important-item profiles once a source format is selected.
- Practical seeded square-grid dungeon generation with deterministic topology, geometry, validation, and targeted regeneration.
- Deterministic internal/optional SVG, DM/clean PNG, low-ink exact-scale tiled Letter/A4 PDF, and Roll20-compatible image/grid exports.
- Complete authorized/generated creature stat blocks and party/playstyle-aware combat encounters.
- Social, exploration, puzzle, trap, hazard, and mixed encounter packages.
- Session-note extraction into proposals only.
- A small common generation-context envelope with separate versioned dungeon, encounter, and later task payloads.

### Explicitly deferred

- Player accounts or player-facing API routes.
- Custom-calendar calculations and date arithmetic.
- Alternate timeline inheritance/merging.
- Live combat state such as current HP, slots, initiative, tactical positioning, or token synchronization.
- Regional/world map generation and illustration-first dungeon maps.
- Direct Roll20 API/dynamic-lighting automation and live shared token/cursor state.
- `@earendil-works/pi-agent-core`, Pi extensions, and MCP integration until a measured open-ended-loop or external-client use case requires them.
- Streaming transcript ingestion.
- Autonomous agents or autonomous canonical writes.
- Automatic rewriting of human-authored Markdown.
- Git as a canonical data store; optional log export may come later.
- Local chat-model infrastructure and image-model enhancement. A small local embedding runtime is an initial P2 candidate, not this deferred item.
- Neo4j, a dedicated vector database, a message broker, or additional/domain microservices beyond the documented private model-runtime gateway.
- A preemptive `encounter-engine` package; begin in the Workbench and extract only cohesive deterministic mechanics if P8 evidence justifies it.
- A universal all-purpose generation-context payload; each workflow owns a narrow versioned context schema inside the common envelope.

## Recommended Implementation Defaults

These defaults remove avoidable setup decisions. Change them only with a documented reason.

| Concern | Default |
| --- | --- |
| Runtime | Python 3.12 managed by `uv` |
| Packaging | Root Workbench `pyproject.toml`/`src/` distribution plus a `uv` workspace member for `packages/dungeon-engine` when P7-02 begins; no empty future packages |
| API | FastAPI |
| CLI | Typer, calling the same services as the API |
| Validation/config | Pydantic 2 and `pydantic-settings` |
| Database | PostgreSQL + pgvector |
| SQL/migrations | SQLAlchemy 2 synchronous sessions, psycopg 3, Alembic |
| Model transport/auth | Private Node 22.19+ gateway with an exactly pinned `@earendil-works/pi-ai`; npm lockfile |
| Agent workflow | Bounded Python task workflows initially; `pi-agent-core` deferred pending measured need |
| User interface | Typer CLI plus thin FastAPI templates/HTMX-or-vanilla-JS web UI with SSE |
| Internal transport | Private/loopback HTTP + SSE between Python and the Node gateway; `httpx` client |
| Tests | pytest; unit, PostgreSQL integration, and golden eval suites |
| Quality | Ruff formatting/linting and mypy (or Pyright if deliberately substituted) |
| IDs | UUID4 opaque IDs for application/database aggregates; input-provided or deterministically derived opaque IDs inside generated packages |
| Content hashes | SHA-256 over exact source bytes; keep any normalized rename fingerprint separate |
| Generated assets | Platform-owned content-addressed local volume behind an `AssetStore` interface reused by preparation artifacts and prompt attachments |
| Generation context | Small `GenerationContextEnvelope` for shared scope/provenance plus separate strict payload schemas such as `DungeonGenerationContext` and `EncounterGenerationContext` |
| Dungeon boundary | In-process pure `dm-dungeon` workspace package; no FastAPI, SQLAlchemy, retrieval, Workbench, or provider imports |
| Encounter boundary | Workbench feature/module initially; consider extracting only `encounter-mechanics` after P8 measurements |
| Initial map representation | Versioned square-grid dungeon package; deterministic SVG as primary renderer |
| Logging | Structured application logs with request/run/revision IDs; no secret/context bodies by default |

Synchronous database access is the simpler initial choice for a small deployment and CLI/API transaction sharing. Do not introduce async SQLAlchemy unless measured concurrency requires it. Python owns bounded workflows and durable run state; the Node gateway owns only chat-provider credentials and normalized `pi-ai` transport. Embedding providers remain separate Python adapters and never reuse Codex OAuth.

## Target Repository Shape

Create this incrementally; do not generate empty modules for distant phases.

```text
.
├── AGENTS.md
├── README.md
├── PROJECT_STATUS.md
├── dm-assistant-project-goals.md
├── dm-assistant-technical-architecture.md
├── dm-assistant-implementation-plan.md
├── pyproject.toml       # Workbench distribution; becomes uv workspace root in P7-02
├── uv.lock
├── .gitignore
├── .env.example
├── compose.yaml
├── alembic.ini
├── migrations/         # one database and one ordered Alembic history
├── packages/
│   └── dungeon-engine/ # added in P7-02; loaded in-process, never a service
│       ├── pyproject.toml
│       ├── src/dm_dungeon/
│       │   ├── contracts/
│       │   ├── topology/
│       │   ├── layout/
│       │   ├── validation/
│       │   ├── rendering/
│       │   └── export/
│       └── tests/
├── model-gateway/       # added in P4, not during P0 scaffold
│   ├── package.json
│   ├── package-lock.json
│   ├── tsconfig.json
│   └── src/
├── src/dm_assistant/
│   ├── api/
│   ├── web/             # shared shell starts with P7-11; P4/P9 extend it
│   ├── cli/
│   ├── config.py
│   ├── db/
│   ├── modules/         # feature-owned application/domain/repository ports
│   │   ├── library/
│   │   ├── chronicle/
│   │   ├── profiles/
│   │   ├── preparation/
│   │   ├── sessions/
│   │   └── assistant/
│   ├── orchestration/
│   │   ├── context/     # envelope plus task-specific compiler policies
│   │   ├── dungeons/    # Workbench workflow around dm_dungeon
│   │   └── encounters/  # remains app-local unless P8 proves an extraction seam
│   └── adapters/
│       ├── assets/
│       ├── embeddings/
│       └── model_gateway/
└── tests/
    ├── unit/
    ├── integration/
    ├── evals/
    └── fixtures/        # synthetic content only
```

The tree describes ownership, not directories to create during P0-01. Add each feature only with its first working task. In particular, do not create an `encounter-engine` workspace member speculatively.

## Dependency Map and Dungeon-First Fast Path

```text
P0-01 Python Workbench package/test scaffold
    |
    +--> P7-02..P7-08 pure dm_dungeon workspace package (synthetic specs)
    |          |
    |          +--> remaining required P0 + P7-01 prep/assets + P7-11 model-independent Studio
    |                         |
    |                         +--> P4-02 private pi-ai gateway
    |                                      |
    |                                      +--> P4-03 standalone scope + P4-04 DungeonGenerationContext
    |                                                    |
    |                                                    +--> P4-05 bounded dungeon task profile
    |                                                                  |
    |                                                                  +--> P7-09 prompt-to-intent/repair
    |                                                                                |
    |                                                                                +--> P4-06 stream/settings UI + P7-10 Studio integration
    |
    +--> P1/P2 Library grounding and retrieval (optional explicit context for prompted dungeons)
    |
    +--> P3 canonical revisions/review -> P5 structured campaign knowledge
                 |                             |
                 |                             +--> P9 session-close extraction
                 +--> canonical P4 rules/profile operations + reviewed P6 profiles

P3 revision boundary + P6 normalized party/item inputs + P4 rules/creature access + P7 dungeon package
    |
    v
P8 Encounter Studio + EncounterGenerationContext + app-local deterministic mechanics
    |
    +--> optional post-eval encounter-mechanics extraction decision
    +--> P9 session-close extraction

All persisted/user-visible slices -> incremental security/secrecy/backup/eval gates
All release paths -> P10 aggregate hardening/deployment gate
```

P7-02 through P7-08 initially read/write fixture JSON and temporary output directories from the isolated `dm_dungeon` package. P7-01 and P7-11 then give those immutable packages durable artifact/asset lineage and a provider-independent Workbench workflow. The priority P4/P7 path adds a pinned standalone `GenerationContextEnvelope<DungeonGenerationContext>` before model-assisted generation; P1/P2 grounding becomes an explicit opt-in augmentation rather than a dependency. P6/P8 use synthetic profiles until real formats are selected. P9 requires P5 plus the prepared-artifact contracts from P7/P8. `PROJECT_STATUS.md` must always name the single next task rather than asking an agent to infer a branch.

---

## P0 — Foundation and Reproducible Development

### Goal

Create the smallest executable application and migration/test environment. Do not implement campaign behavior yet.

### P0-01 — Scaffold the Python package

**Work**

- Add root `pyproject.toml` with Python 3.12, runtime dependencies, and dev groups. Keep the Workbench as the root distribution and make later conversion to a `uv` workspace straightforward, but do not create `packages/dungeon-engine` until P7-02.
- Add `.gitignore` for virtual environments, caches, `.env`, local database/data mounts, and generated provider/export artifacts without broadly ignoring future source directories.
- Add the `src/dm_assistant` package.
- Add a Typer entry point named `dm` with `dm --help` and `dm version`.
- Add a minimal FastAPI app factory with no business routes.
- Add one unit test proving package/CLI/API imports work.
- Configure Ruff and static type checking.
- Generate and commit/update `uv.lock` when repository workflow permits.

**Done when**

```text
uv sync --all-groups
uv run dm --help
uv run pytest tests/unit
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

all pass on a Python 3.12 environment.

**Dungeon-first handoff:** P7-02 may begin immediately after P0-01 because the typed dungeon kernel needs no database, provider, or source corpus. P0-02 through P0-04 can continue before persistence/API integration.

### P0-02 — Configuration and structured logging

**Work**

- Add typed settings for environment, database URL, log level, source roots, single-DM API token, private model-gateway URL/policy, and separate embedding-runtime/provider policy.
- Add a reusable single-DM authentication dependency/middleware; all future non-health API routes must opt in by default rather than remembering to add auth individually.
- Add `.env.example` with placeholders only.
- Add structured logs carrying request ID, ingestion/embedding/model/generation-run ID, change-set ID, and campaign revision where available.
- Add secret-field redaction and tests.
- Establish domain error types that API and CLI can render consistently.

**Done when**

- Invalid/missing required settings fail with a concise message.
- Logs do not print database passwords, API tokens, or source text.
- Non-health test routes reject missing/invalid DM credentials without echoing them.
- Unit tests cover config precedence and redaction.

### P0-03 — PostgreSQL/pgvector and migrations

**Work**

- Add `compose.yaml` for PostgreSQL with pgvector; pin an explicit image version.
- Add health checks and a named local development volume.
- Add SQLAlchemy session/transaction helpers.
- Configure Alembic and create a foundation migration enabling required extensions.
- Add minimal `campaign` and schema-version tables only if needed to prove migrations.
- Add PostgreSQL integration-test markers/fixtures.

**Done when**

```text
docker compose up -d postgres
uv run alembic upgrade head
uv run pytest tests/integration
uv run alembic downgrade base
uv run alembic upgrade head
```

passes in an environment with Docker/PostgreSQL.

### P0-04 — Health endpoints and contributor loop

**Work**

- Add `/health/live` without database dependency.
- Add `/health/ready` that checks schema/database readiness without leaking config.
- Add `dm doctor` to report safe environment readiness.
- Document local commands in `README.md` once they exist.
- Add a single aggregate check command or script used by humans and CI.

**Phase gate P0**

- Fresh checkout can install, lint, test, migrate, start the API, and run `dm doctor` using documented commands.
- A failed database connection is distinguishable from a dead API process.
- `PROJECT_STATUS.md` records whether the P7-02 dungeon fast path is underway/complete and identifies the next platform integration task with actual command results.

---

## P1 — Immutable Documents, Corpus Snapshots, and Lexical Search

### Goal

Ingest Markdown safely and answer search queries with exact, immutable citations—without embeddings or an LLM.

### P1-01 — Document/source schema

**Work**

Create and migrate the architecture's source layer:

- logical document and path-history/source-registry records;
- immutable document revision;
- authority class, document type, corpus, ruleset metadata, and visibility policy;
- document chunk with heading path, ordinal, character offsets, page metadata, and full-text vector;
- ingestion run;
- corpus snapshot and snapshot-document membership.

Add database constraints for campaign/corpus ownership, revision uniqueness, source hash identity, and immutable revision content.

**Done when**

- Migration round-trip passes.
- Database tests reject invalid corpus/visibility combinations and mutation of immutable revision content through application services.

### P1-02 — Source registry and idempotent revision ingestion

**Work**

- Assign a document UUID on first ingestion.
- Store current path plus path history and content hash.
- Re-ingesting unchanged content returns the existing revision.
- Editing creates one new revision.
- Exact-content move/rename retains logical identity.
- Ambiguous moved-and-edited files produce a review/error state rather than silent duplication/merge.
- Missing files retire the path/document only through an explicit reconciliation action; they do not delete revisions.

Use an allowlisted source root and reject path traversal/symlink escapes.

**Done when**

Integration tests cover unchanged, edited, moved, duplicated, missing, disallowed, and ambiguous sources.

### P1-03 — Markdown parser and deterministic chunker

**Work**

- Preserve the exact source snapshot.
- Parse front matter as metadata without making Obsidian syntax mandatory.
- Chunk by heading and semantic block with bounded size/overlap.
- Preserve heading path and exact source offsets for every chunk.
- Label code blocks/tables safely rather than losing them.
- Version parser/chunker behavior.

Create synthetic fixtures containing headings, lists, tables, code fences, Unicode names, links, and instruction-like malicious text.

**Done when**

- Re-running the same parser/chunker version produces the same chunk identities/content.
- Every chunk maps back to the expected source span.
- No test fixture source instructions affect application control flow.

### P1-04 — Atomic corpus snapshot activation

**Work**

- Build a candidate snapshot from selected logical-document heads.
- Activate it only after all chunks/full-text indexes are ready.
- Preserve the prior active snapshot on failure.
- Record ingestion configuration and parser/chunker versions.
- Add provenance-drift detection when accepted evidence text changes or disappears; emit a warning/proposal later, never an automatic canonical retraction.

**Done when**

- Queries never see a half-ingested document set.
- A failed ingestion leaves the previous snapshot queryable.
- Snapshot IDs reproduce the exact revision set.

### P1-05 — Filtered PostgreSQL lexical retrieval

**Work**

- Implement lexical search scoped by campaign, corpus snapshot, corpus, authority class, visibility, and ruleset.
- Boost headings/exact names without relying solely on English stemming.
- Return bounded snippets and stable citation IDs.
- Exclude plans from historical-fact search by default while allowing an explicit DM preparation query.
- Keep campaign and rules corpora separate.

**Done when**

- Exact D&D-like names and natural prose terms are both retrievable in synthetic fixtures.
- Unauthorized/wrong-authority/wrong-ruleset chunks never enter candidates or counts.

### P1-06 — CLI/API source and search surface

**Work**

Add shared services and thin interfaces resembling:

```text
dm ingest <path> --authority <class> --visibility dm_only
dm documents
dm show-document <id> [--revision <id>]
dm search <query> [scope options]
```

Add equivalent versioned API routes. Include resolved query scope and citations in results.

**Phase gate P1**

- A synthetic campaign vault can be ingested twice without duplicates.
- An edited note creates a new immutable revision and snapshot.
- `dm search` returns exact source spans and never treats a plan as an occurred fact by default.
- No LLM or embedding credential is required.

---

## P2 — Embeddings, Hybrid Retrieval, and Retrieval Evals

### Goal

Add semantic retrieval without changing source identity or treating vectors as truth.

### P2-01 — Independent embedding runtime/model abstraction

**Work**

- Document in code/config that `pi-ai` and ChatGPT Codex OAuth are not embedding services.
- Add embedding-profile metadata: runtime kind (`local`/`hosted`), provider, exact model/revision/license, dimensions, distance metric, normalization/preprocessing version, config hash, and enabled status.
- Add chunk embeddings keyed by exact chunk content hash and embedding model/profile.
- Define a narrow Python embedding protocol for document batches and query text; keep credentials/config separate from the Node chat-model gateway.
- Implement a deterministic fake provider for tests.
- Add a benchmark/eval spike for a small local CPU/ONNX adapter first; do not select the permanent model until retrieval quality, memory, latency, dimensions, and license are recorded.
- Preserve a hosted adapter seam whose API key/retention policy must be configured explicitly.
- Prevent mixed vector dimensions or incompatible normalization/distance profiles in an index/partition.

**Done when**

- Two embedding profiles/model versions can coexist without overwriting one another.
- Tests require no network calls.

### P2-02 — Resumable embedding runs

**Work**

- Add synchronous/batched embedding execution with durable run/item state and bounded local memory/batch size.
- Skip already-computed content-hash/profile pairs.
- Retry bounded transient failures and make cancellation/restart safe.
- Activate a vector-ready corpus generation only after required embeddings exist.
- Record runtime/model revision, batch size, dimensions, latency, memory observations, and cost/token metadata when applicable.

**Done when**

An interrupted synthetic run resumes without duplicate calls or partial serving state.

### P2-03 — Scope-safe vector retrieval

**Work**

- Apply campaign/snapshot/authority/visibility/rules filters before candidate material can enter model context.
- Add bounded nearest-neighbor search for the active embedding model.
- Ensure snippets/citations resolve to immutable chunks.
- Verify that excluded chunks cannot leak through metadata, result counts, or logs.

### P2-04 — Hybrid fusion baseline

**Work**

- Combine lexical and vector rankings with reciprocal rank fusion.
- Deduplicate overlapping chunks/revisions.
- Add exact-name boosts and bounded neighboring-context expansion.
- Do not add a learned reranker until baseline evals demonstrate need.

### P2-05 — Retrieval run records and eval harness

**Work**

- Persist query scope, snapshot, retrieval versions, candidates/scores, selected chunks, timing, and citations.
- Build synthetic golden cases for exact names, vague recollections, plans versus canon, rules edition filters, and DM-only exclusion.
- Report source recall and latency; make eval output diffable.

**Phase gate P2**

- Hybrid retrieval improves at least one semantic fixture without regressing exact-name/security fixtures.
- Re-running an eval against pinned versions is reproducible.
- There is still a useful lexical-only fallback when the local/hosted embedding runtime or query embedding fails.
- The selected first embedding profile has a recorded quality/resource comparison; it was not chosen merely because `pi-ai` supplies chat models.

---

## P3 — Canonical Revisions, Review, and Change Logging

### Goal

Build the authority boundary before any model can propose structured campaign facts.

### P3-01 — Campaign revision and change-set schema

**Work**

Implement:

- campaign head revision;
- immutable campaign revision with parent, sequence, summary, origin, reviewer, and timestamp;
- draft/in-review/committed/abandoned change set;
- versioned, schema-validated change item payload;
- item dependencies and review state;
- change-set source links and idempotency key;
- extraction/manual origin metadata.

Do not add model extraction yet.

### P3-02 — Operation registry and validation boundary

**Work**

- Define a versioned operation registry and payload schemas.
- Start with safe foundation operations such as campaign metadata and no-op/test fixtures.
- Separate hard structural errors from overridable semantic warnings.
- Ensure operation handlers can write only inside the commit transaction.
- Ensure direct ORM calls are not exposed through API/model surfaces.

### P3-03 — Review/edit/reject workflow

**Work**

Add shared services and CLI/API operations:

```text
dm changes create
dm review <change-set-id>
dm changes accept|edit|reject <item-id>
dm validate <change-set-id>
```

Review output includes source, proposed before/after state, warnings, and dependencies.

### P3-04 — Atomic commit and optimistic concurrency

**Work**

- Revalidate against the base campaign revision.
- Reject/rebase stale change sets explicitly.
- Resolve change-set-local IDs.
- Commit accepted dependency closure atomically.
- Advance the campaign head in the same transaction.
- Make commit idempotent.
- Keep old revisions queryable.

Test injected failure at several points to prove no partial canonical revision is visible.

### P3-05 — Human-readable history and diff

**Work**

Implement:

```text
dm commit <change-set-id> --summary <optional-edit>
dm history
dm show-revision <revision-id>
dm diff <old-revision> <new-revision>
```

A deterministic or model-drafted summary can be edited by the DM. Detailed accepted/rejected item history remains available regardless of summary wording.

### P3-06 — Optional append-only exporter

**Work (optional after the phase gate)**

- Export revision summaries/details as idempotent Markdown and/or JSONL.
- Make export rebuildable from PostgreSQL.
- Do not roll back canonical commits if export fails.
- Leave automatic Git commits disabled/configurable.

**Phase gate P3**

- No canonical state changes before `commit`.
- A stale or failing commit creates no partial revision.
- Every revision has a readable summary and full audit details.
- `dm diff` and historical revision reads are deterministic.

---

## P4 — Rules/Creature Retrieval, `pi-ai` Model Gateway, Context Compilation, and First-Party Ask

### Goal

Provide reusable scope resolution, task-specific context compilation, and private model transport. The active P4/P7 priority is the standalone prompted Dungeon Studio; the general cited Ask workflow remains a later consumer. These tasks are capability tracks rather than one prerequisite block: P4-02 through P4-05 establish the bounded prompt-to-intent path, P4-06 and P7-10 integrate it into Studio, and P4-07 follows that milestone.

### P4-01 — Rules/creature source metadata and profile operations

**Work**

- Add official/authorized rules and creature-source metadata, edition, book, chapter, section, page, and extraction provenance.
- Add campaign rules profiles, creature collections, and ordered sources through P3 change-set operations.
- Add house-rule/table-ruling source classification and precedence.
- Require explicit comparison intent before mixing editions.

Real copyrighted rule/bestiary text stays outside Git; use synthetic mechanics and creatures in tests.

### P4-02 — Private Node `pi-ai` model gateway and credential boundary

**Work**

- Add `model-gateway/` as a small TypeScript/Node 22.19+ package with an npm lockfile and an exactly pinned `@earendil-works/pi-ai` version (0.84.1 was the evaluated baseline; deliberately re-verify if newer at implementation).
- Use the current provider/`Models` API. Do not copy older `@mariozechner/pi-ai` `getOAuthApiKey()` examples or read Pi's normal auth file.
- Register only configured/allowlisted providers: GitHub Copilot subscription OAuth, OpenAI Codex OAuth, the deterministic faux provider, and one selected API-key fallback before release; add others through the same provider-factory boundary without changing Python workflows.
- Implement a dedicated persistent `CredentialStore` with per-provider serialized modify/refresh, atomic restrictive-permission writes, and no token-returning endpoint.
- Expose internal health, non-secret auth status, provider/model/capability listing, login-event/prompt coordination, logout, normalized stream, and cancellation contracts.
- Prefer device-code ChatGPT login for headless Proxmox; browser/manual-code login may remain an explicitly tested alternative.
- Document/verify applicable provider subscription terms and usage limits; do not assume OAuth permits arbitrary unattended workloads.
- Normalize text/thinking/tool-call/usage/error events and propagate cancellation; enforce request/output/attachment limits.
- Bind the gateway to loopback/private container networking and allow only the Python service to call model endpoints.
- Use `pi-ai`'s faux provider for automated contract tests; live OAuth/model tests are manual/opt-in and never run in CI.
- Do **not** add `@earendil-works/pi-agent-core` in this task.

### P4-03 — Task scope and intent analysis

**Work**

- Resolve campaign revision, corpus snapshot, DM principal, timeline/cursor defaults, authority intent, rules profile, and explicit task type before retrieval/model selection.
- Implement deterministic intent/scope defaults in Python; a selected model/tool call can never broaden scope.
- Reject attempts to broaden campaign, principal, source authority, rules profile, or visibility through prompt/tool input.
- For the prioritized standalone dungeon task, resolve only the authenticated DM, preparation-artifact campaign owner, explicit task type, and standalone provenance. Campaign revision, corpus snapshot, rules profile, and retrieval are absent unless the DM explicitly enables grounded generation.

### P4-04 — Context envelope and task-specific context packets

**Work**

- Define a small versioned `GenerationContextEnvelope[T]` containing only common provenance/scope fields: context kind and payload version, campaign revision, corpus snapshot, optional rules profile, visibility scope, immutable source references/citations, and canonical payload hash.
- Define strict domain payloads only as workflows need them. The first preparation payload is `DungeonGenerationContext`; campaign/rules answers use their own question packet schemas rather than growing the generation payload.
- Implement the first `DungeonGenerationContext` as a standalone packet: explicit standalone provenance, prompt/input hash, requested constraints, and the preparation owner. It contains no campaign revision, corpus snapshot, rules profile, or citations unless a later explicit grounding selection adds them.
- Keep dungeon fields focused on selected location lore/geography, themes, factions, hooks, tone, and coarse party/capacity constraints. Do not add encounter mechanics or speculative future fields.
- Make unknown envelope/payload versions and unknown fields fail explicitly; round-trip canonical serialization and hash tests.
- Build task-specific typed sections for applicable narrative evidence, rules/creature evidence, conflicts/unknowns, and answer schema.
- Apply per-section token budgets, overlap deduplication, and bounded neighbor expansion.
- Label every excerpt with authority, edition/profile, visibility, and citation ID, and delimit retrieved text as untrusted evidence.
- Persist the resolved envelope or its content-addressed canonical payload plus source links with each generation/model run for replay and inspection.

**Done when**

- A dungeon context and a campaign/rules answer packet can share scope/provenance value objects without sharing unrelated payload fields.
- Tests prove that a model cannot broaden envelope scope and that changing selected context changes the payload hash.
- There is no universal optional-field `GenerationContext` model.

### P4-05 — Model/task profiles, bounded ask loop, citation checks, and abstention

**Work**

- Add versioned model-endpoint/profile and task-profile records/configuration: runtime adapter, provider/model ID, observed capabilities, normalized effort, context policy/budgets, tools, output schema/token limit, prompt/instruction version, and fallback order.
- Validate profiles against the gateway catalog; map `fast`/`standard`/`deep` only to reasoning levels supported by the selected model and preserve explicit per-run overrides in lineage.
- Add a Python gateway client and bounded tool loop. Python validates completed arguments against server-owned schemas, executes application services, appends bounded results, and enforces a per-task turn/tool/cost/time budget.
- Prioritize a `dungeon_intent_v1` task profile that produces only strict typed dungeon intent and may invoke only server-owned Dungeon Studio operations. It has no source-retrieval tool by default and no approval, commit, file, SQL, or renderer-syntax access.
- Defer the text-first `dm ask` and its authenticated API service to P4-07; preserve direct retrieval/debug output independent of any model.
- Require supplied citation IDs for factual/rules claims and verify each was authorized and present in the packet.
- Label official rules versus house-rule overrides and return explicit unknown/conflict diagnostics when evidence is inadequate.
- Exclude approval/commit and arbitrary file/SQL access from all model tools.
- Record exact package/provider/model/task-profile/instruction/schema versions, structured inputs/results, usage, timing, and tool interactions without credentials or unrestricted hidden reasoning.

### P4-06 — Shared model settings, login, and stream UI foundation

**Work**

- Extend the shared server-rendered Workbench shell established by the model-independent Dungeon Studio with small HTMX/vanilla-JavaScript behavior and SSE; do not replace it or start a large SPA.
- Reuse the P7-11 single-DM Workbench login/session shell; add model-provider settings, OAuth device-code progress, non-secret auth status, model/task-profile/effort selection, and logout/re-auth behavior without creating a parallel authentication flow.
- Add reusable streamed/cancellable/reconnectable durable model-run status components that Dungeon Studio and later Ask workflows can call through shared application services.
- Show capability/profile validation and safe provider errors without returning credentials, source context bodies, or unrestricted provider responses to the browser.
- Contract-test the shell/settings/run components against the faux provider; first integrate them with the standalone Dungeon Studio workflow and do not add a generic chat page in this task.

**Done when**

- The DM can complete device-code setup, inspect non-secret auth/model/profile status, select a supported effort, start/cancel a synthetic bounded run, and reconnect to its durable status.
- P7-09/P7-10 can reuse the settings and stream components without depending on the general Ask workflow.

### P4-07 — General Ask web workflow and comparison baseline

**Work**

This task intentionally follows the standalone prompt-to-dungeon-package milestone. It must reuse the established gateway, profile, and stream components rather than delaying P7-09/P7-10.

- Add prompt entry, pasted/dragged image upload, streamed cited response, cancellation, reconnectable durable run status, errors/unknowns, and conversation/run history using P4-05/P4-06 services; extend the shared CLI/API ask service with validated attachment IDs.
- Reuse the platform-owned content-addressed `AssetStore` introduced with P7-01; add input-attachment ownership, MIME/size/retention policy, and opaque-ID metadata without creating a second blob store.
- Send only validated attachment IDs to the gateway and provide authenticated preview/download routes.
- Keep preparation review, canonical review/commit, and model output visually and operationally distinct.
- Add a small model-comparison harness: fixed synthetic tasks, capability/schema/tool checks, latency/usage, objective answer checks, and blinded DM ratings. Do not assign Luna/Terra/Sol roles based on names alone.

**Phase gate P4**

- In the first-party web UI, the DM can complete device-code login, select an available model/task profile and supported effort, ask a synthetic narrative/rules question, see a streamed concise cited answer, cancel it, and resume/inspect the durable run.
- An optional pasted image reaches a vision-capable model through a content-addressed attachment without exposing arbitrary paths.
- Switching model/task profile changes no Python domain semantics, and the exact resolved profile is recorded.
- Context inspection shows the resolved common envelope and the task-specific payload version; unrelated dungeon/encounter/session fields are absent rather than null-filled.
- Edition, creature-source collection, and house-rule precedence is visible; authorized creature records have exact citations before stat normalization.
- Plans are not reported as events, and no complete vault dump is sent to the gateway/provider.
- OAuth tokens are absent from the browser, Python payloads, PostgreSQL campaign data, logs, and normal backups.
- CLI lexical retrieval remains usable when the gateway/model or embedding runtime is unavailable.
- The initial model-comparison report exists; model defaults are not justified by branding alone.

---

## P5 — Structured Campaign Knowledge and Provenance

### Goal

Add precise answers for identity, state, events, perspectives, and relative history through the revision engine.

### P5-01 — Entities, aliases, mentions, and merge history

**Work**

- Migrate entities, aliases, source mentions, and merge redirects.
- Add operation handlers for create, alias, merge, split/review correction, and archive.
- Keep secret/temporal state out of generic entity properties.
- Add exact and fuzzy candidate resolution with no automatic ambiguous merge.

### P5-02 — Predicate catalog

**Work**

- Add versioned predicate definitions, type/value constraints, inverse/symmetric/transitive metadata, functional/exclusivity rules, examples, and status.
- Seed a small tested vocabulary only.
- Add find/propose/deprecate operations through change sets.
- Derive inverse/symmetric edges in query logic rather than duplicating canon.

### P5-03 — Events, participants, and evidence

**Work**

- Add canonical events, participants/roles, visibility, and revision ranges.
- Add typed source references and many-to-many event evidence.
- Treat plans/allegations as source/proposition content, not canonical events.
- Add event supersession/retraction operations.

### P5-04 — Sessions, basic temporal anchors, and relations

**Work**

Implement only:

- session provenance containers and session-document links, with display numbers that do not imply story chronology;
- main timeline;
- event/scene-relative anchors;
- table-session markers for player knowledge;
- unknown/approximate values;
- BEFORE/AFTER/DURING/OVERLAPS/SIMULTANEOUS relations needed by fixtures;
- strict-order cycle detection;
- story cursor/default cursor.

Preserve raw fictional date text, but do not implement a calendar adapter or date arithmetic.

### P5-05 — Propositions and perspective assertions

**Work**

- Add immutable proposition content with typed entity/event/literal object and explicit polarity.
- Add reality, knowledge, unaware, belief, suspicion, claim, and public-record assertion modes.
- Separate proposition content time, holder stance time, and campaign revision time.
- Add visibility, provenance, derivation, semantic certainty, supersession, and retraction.
- Add optional tracked-knowledge completeness for important secrets.

### P5-06 — Deterministic validation and projections

**Work**

- Enforce type/object/cardinality/exclusivity rules.
- Detect explicit overlapping contradictions at the same perspective/time.
- Validate knowledge/unaware intervals and suspicious unsupported reveals.
- Add derivation-cycle checks.
- Build revision/cursor/mode/holder-aware active-state queries.
- Keep any materialized projection rebuildable and revision-keyed.

### P5-07 — High-level query services

Implement and test services resembling:

```text
resolve_entity
get_state
get_event
get_holder_knowledge
explain_provenance
find_related_threads
```

Cover questions such as:

- Is Deren dead at the current cursor?
- What does Mira believe?
- Who is recorded as knowing the killer's identity?
- Why does Mira distrust Rowan?
- Where was the seal last seen?
- Is the chronology genuinely unknown?

### P5-08 — Structured retrieval/context integration and evals

**Work**

- Prefer accepted structured state for factual questions.
- Expand only bounded provenance and supporting narrative.
- Surface conflicts rather than letting narrative silently override structure.
- Add frozen evals for perspective, retcon, relative time, entity collisions, plans, and knowledge incompleteness.

**Phase gate P5**

- Manual change sets can establish and revise a small synthetic campaign.
- State, belief, knowledge, event, relative-time, and provenance questions are correct at old and current campaign revisions.
- Unsupported chronology/knowledge is reported as unknown/no recorded knowledge.
- A retcon preserves the prior system history.

---

## P6 — Character Sheets and Important Story Items

### Goal

Give the DM precise access to supplied mechanical profiles without forcing every sheet cell into the ontology.

### P6-01 — Versioned normalized profile schemas

**Work**

- Add schema-versioned character-sheet and item-profile snapshots with revision ranges and source provenance.
- If the selected format is binary, add a content-addressed immutable source-asset revision and link derived text/parsed output to it; do not force binary support into P1 preemptively.
- Define validated internal Pydantic shapes for common 5e/2024 fields.
- Separate source-reported and computed fields.
- Store formula/rules-profile version for computed values.
- Do not include live tactical tracking tables.

### P6-02 — Adapter protocol and synthetic reference adapter

**Work**

- Define adapter discovery, source-type detection, parse result, warnings, and provenance-span behavior.
- Implement a small internal JSON/Markdown fixture adapter solely to exercise the pipeline.
- Keep raw text/JSON source as a P1 document revision; use the P6 binary source-asset extension only if the chosen adapter requires it.
- Make unsupported formats fail with a clear message rather than best-effort hallucination.

### P6-03 — First real character-sheet adapter

**Blocked input:** the real source format has not been chosen.

When known:

- add representative redacted/synthetic fixtures for that format;
- parse all stable fields available from the source;
- preserve unknown/custom fields;
- identify source limitations (for example, static PDF text order);
- never call an external character service without explicit credentials/terms.

This task may be skipped temporarily without blocking P7/P8 if normalized synthetic party/creature fixtures exist.

### P6-04 — Profile diff/review operations

**Work**

- Produce field-level diffs between snapshots.
- Propose sheet/item updates through P3 change sets.
- Group noisy list changes such as spells/inventory.
- Flag conflicts between sheet inventory and canonical possession/location assertions.
- Include a concise profile-change summary in the campaign revision.

### P6-05 — Profile query and context integration

**Work**

Support questions such as:

- What is Rowan's passive Perception and how was it computed?
- Which saving throws is Mira proficient in?
- Which prepared/known spells are relevant to this scene?
- Who carries the seal, what does its profile say, and who knows its true function?

Return source snapshot citations and distinguish sheet data from accepted story state.

**Phase gate P6**

- A synthetic and, when available, real-format sheet can be ingested, reviewed, committed, diffed, and queried.
- Important item mechanics and temporal possession/location remain distinct but answerable together.
- No live-combat state was accidentally introduced.

---

## P7 — Dungeon Primitives, Layout, Rendering, and Export

### Goal

Deliver a reproducible practical dungeon capability in three boundaries: an independently packaged pure `dm_dungeon` kernel, a model-independent Workbench Dungeon Studio, and later grounded model orchestration. Build deterministic geometry/rendering and the usable human workflow before adding LLM orchestration.

### P7-01 — Preparation artifacts, generation runs, and asset store

**Work**

- Migrate preparation artifact, immutable artifact version, generation run, generated asset, and artifact-asset role records.
- Implement `draft`, `approved_for_play`, `used`, and `retired` lifecycles without conflating them with campaign canon.
- Add readable artifact-version summaries and parent lineage.
- Define the platform-owned `AssetStore` port and implement the first SHA-256 local-volume adapter for generated assets, using temporary files plus atomic rename. Keep generic blob identity/storage metadata separate from dungeon-specific asset roles; P4 prompt attachments reuse this port later.
- Pin campaign/corpus/rules/party inputs, generation-context envelope kind/payload version/hash and source links, seed, schema versions, generator/renderer versions, model task-profile/tool runs, and validation report.

**Done when**

- Repeated asset writes deduplicate safely.
- Artifact approval cannot mutate canonical campaign state.
- An immutable version and its assets remain reconstructable/auditable after newer versions exist.

### P7-02 — Pure dungeon package and versioned primitive vocabulary

**Work**

- Add `packages/dungeon-engine` as the first `uv` workspace member, with import package `dm_dungeon`; do not turn it into a process or network API.
- Establish package dependency tests that prohibit imports from `dm_assistant`, FastAPI, SQLAlchemy, provider/model clients, retrieval, or Workbench repositories.
- Keep fixture/file adapters and canonical JSON serialization inside the package test/CLI boundary so the kernel runs without PostgreSQL or provider configuration.

Define typed Pydantic/JSON schemas for:

- `DungeonBrief`;
- floor and room-role/topology graph;
- room capacity/size constraints;
- corridors, normal/locked/trapped/secret doors, stairs, and vertical links;
- gates, keys, clues, loops, branches, and secret bypasses;
- features, terrain, hazards, zones, labels, encounter slots, and position anchors;
- DM/player/render layers;
- exact renderer-neutral `DungeonPackage`.

Default to orthogonal square cells and five feet per cell. Use stable opaque IDs. IDs inside deterministic packages must be retained from input specifications or derived reproducibly from pinned input, seed, and generator version; never call `uuid4()` in deterministic generation. Do not represent every tile as a canonical ontology assertion.

**Done when**

- Hand-authored synthetic packages round-trip through JSON without information loss.
- Unknown schema versions fail explicitly.
- DM-only fields require an explicit visibility/layer classification.
- The package imports and test suite run independently of the Workbench application, database, and model gateway.

### P7-03 — Topology, gating, and puzzle-dependency validator

**Work**

- Validate required-room reachability from entrances/exits.
- Verify requested loops, branches, chokepoints, secret routes, and floor transitions.
- Model lock/key and clue/gate dependencies and reject impossible acquisition order/cycles.
- Return structured diagnostic codes, affected IDs, severity, and repair hints.
- Add Hypothesis (or an explicitly justified equivalent) as a dev dependency and property-based tests over generated topology graphs.

### P7-04 — Seeded orthogonal layout engine

**Work**

- Select/document a deterministic first algorithm (for example, graph-guided room placement plus orthogonal corridor routing).
- Place constrained rooms on per-floor grids without requiring LLM coordinates.
- Route corridors and align doors/stairs.
- Support fixed/locked components and targeted regeneration.
- Record every random choice through one explicit seed/random source.
- Fail with diagnostics rather than silently dropping requested topology.

**Done when**

- Identical spec/seed/generator version yields byte-equivalent structured layout.
- Different seeds produce valid alternatives.
- Regenerating one unlocked component preserves all locked IDs/geometry.

### P7-05 — Geometry, pathfinding, and capacity validation

**Work**

- Detect overlapping rooms, invalid walls/doors/stairs, out-of-bounds cells, disconnected walkable regions, and blocked transitions.
- Validate minimum corridor/door widths and requested room capacities.
- Expose pathfinding between required anchors.
- Validate floor-transition pairs and grid scale.
- Add encounter-fit hooks for creature footprints, starting anchors, ranges, cover, and objectives; P8 supplies encounter details.

### P7-06 — Deterministic SVG renderer and secrecy layers

**Work**

- Render walls, doors, secret doors, stairs, grid, terrain/features, labels, and markers from exact geometry.
- Produce separate DM and player variants.
- Keep stable element IDs/data attributes for deterministic tests, targeted regeneration, and future Roll20 wall/door adapters.
- Define style themes as code/configuration, not model-authored SVG/CSS.
- Add deterministic SVG snapshot tests and explicit player-export leak checks.

### P7-07 — PNG and low-ink stitchable PDF exporters

**Work**

- Rasterize grid-on/gridless PNG at configurable pixels per cell/DPI without changing geometry.
- Print each five-foot cell at exactly one inch.
- Export Letter and A4 one-sheet/tiled PDFs without content rescaling.
- Use a low-ink default theme: white floors, bold wall outlines, light-gray grid, sparse grayscale-safe symbols/hatching, and no large dark fills/textures.
- Include an assembly overview, floor/map/version ID, page row/column IDs, crop/cut and registration marks, configurable overlap strips, adjacent-page alignment marks, safe printer margins, and actual-size instructions.
- Include a one-inch calibration square/ruler on appropriate pages.
- Support both trim-and-butt and overlap-and-tape assembly workflows.
- Test PDF page boxes, physical grid scale, overlap geometry, adjacency alignment, ink-coverage proxy/budget, and DM/clean secrecy variants.
- Keep renderer/export version metadata in each asset.

### P7-08 — Roll20-compatible exporter

**Work**

- Export correctly sized Roll20 grid-on and gridless PNG maps plus grid width/height, pixels per cell, scale/origin, floor metadata, and an optional token-placement manifest.
- Preserve wall/door geometry for future dynamic-lighting adapters without promising direct Roll20 import/API support now.
- Validate file paths/hashes/dimensions and prevent DM-only metadata from entering clean exports.

### P7-11 — Model-independent Dungeon Studio vertical slice

Task IDs group work by domain rather than execution order; this task runs after P7-01/P7-02..P7-08 and before P7-09/P7-10.

**Work**

- Add shared Workbench application services plus CLI/API operations to import or create a hand-authored brief/spec, generate, inspect, validate, render, compare versions, lock components, regenerate a component, export, and approve for play.
- Add the first thin server-rendered Workbench shell, minimal single-DM browser login/session over the centralized P0 auth policy, and Dungeon Studio views for diagnostics, DM/clean previews, version comparison, context/input lineage, downloads, and explicit human approval.
- Persist package inputs/outputs through P7-01 repositories without exposing ORM models to `dm_dungeon`.
- Build fixed-seed golden/property fixtures and a provider-independent end-to-end test from brief/spec through approved preparation artifact.
- Keep all generation and review usable when the model gateway is absent.

**Done when**

- A DM can complete the deterministic dungeon workflow through CLI and web without PostgreSQL objects or model/provider concerns entering the pure package.
- Preparation approval changes no canonical campaign state.
- The shared shell is reusable by P4 model settings/Ask and P9 review rather than being a dungeon-only application.

### P7-09 — Constrained LLM dungeon tools and repair loop

**Work**

- Add Python-owned bounded model tools for brief/topology intent, room/connection/features, generation, validation, and targeted regeneration, transported through the P4 `pi-ai` gateway under a pinned dungeon task profile.
- Start with the standalone path: compile the DM prompt/input hash and requested constraints into `GenerationContextEnvelope<DungeonGenerationContext>` with explicit standalone provenance and no retrieved campaign source. A campaign owns the resulting preparation artifact but contributes no facts by default.
- Add authorized campaign hooks/lore only after an explicit grounding selection; reject unrelated encounter/session fields and pin the resulting payload version/hash/source links.
- Let code assign IDs, calculate geometry, validate, and render.
- Feed structured diagnostics—not raw renderer internals—into bounded repair calls with explicit turn/time/usage limits.
- Record structured model outputs and generator inputs for replay.
- Never let the model write arbitrary files, SVG, or approved artifacts.

### P7-10 — Grounded Dungeon Studio integration and final eval gate

Keep the stable P7-10 task ID, but deliver it as two ordered, independently testable slices. P7-10a proves the real private-gateway path headlessly before P7-10b adds browser behavior.

#### P7-10a — Headless/CLI prompt-to-package integration

- Extend the Python gateway adapter with display-safe provider/model catalog and gateway-owned login/status/prompt-response/logout operations; access/refresh tokens never enter Python, PostgreSQL, CLI output, or shell arguments, and short-lived coordination responses are read without shell-history exposure.
- Resolve the pinned `dungeon_generation_intent_v1` task profile against actual gateway model IDs/capabilities, including provider/model IDs containing transport-safe hyphens.
- Compose `DungeonPromptService` with `PiGatewayClient.from_settings` in the shared Workbench runtime and add `dm model ...` setup/inspection commands plus synchronous `dm dungeon prompt`.
- Keep a campaign record only as the preparation ownership container; standalone runs have no campaign revision, corpus snapshot, rules profile, retrieval, citations, or canonical write.
- Add a faux-gateway CLI-to-persisted-package integration case and document an explicit opt-in live-provider smoke flow over the Compose network.
- Preserve safe failure: unavailable/unauthenticated gateways do not affect hand-authored inspect/validate/render/export/manual-regeneration operations.

**P7-10a done when**

- A running Workbench can list the private gateway catalog, coordinate provider login without exposing credentials, select a compatible model/effort, and create an inspectable draft artifact through `dm dungeon prompt`.
- Automated tests prove the same CLI/application path with a scripted faux gateway and PostgreSQL, while live-provider checks remain manual and opt-in.

#### P7-10a.1 — Default resolution and first-run onboarding

- Add one inspectable active campaign selection. The first campaign becomes active; if a prompt runs before any campaign exists, create one empty ownership campaign. Allow `dm campaign use` and make `--campaign` an optional override across Dungeon Studio CLI commands.
- Persist a non-secret task-specific provider/model/effort default. If no compatible selection exists, choose through a versioned capability/capacity policy; exclude the faux provider outside tests.
- When the selected/default provider is unauthenticated, start and poll gateway-owned OAuth inline, display device-code events, answer short-lived prompts without shell-history exposure, then resume the original dungeon request.
- Make title and seed optional. Persist the validated model-authored `DungeonBrief.title`, generate and pin a seed when absent, and retain all explicit flags as reproducibility/debug overrides.
- Keep defaults inspectable and code-resolved. A prompt/model can never select another campaign, broaden visibility, or silently enable campaign grounding.

**P7-10a.1 done when**

- On an empty migrated Workbench, `dm dungeon prompt "..."` can bootstrap its ownership campaign, complete login when required, select and save a compatible model, derive a title, pin a generated seed, and persist a draft without UUID/model/seed/title flags.
- Switching the active campaign changes omitted-scope resolution; explicit `--campaign`, `--provider`, `--model`, `--effort`, `--seed`, and `--title` remain available and are pinned in lineage.

#### P7-10b — Web streaming and final UX/eval gate

- Add the authenticated Dungeon Studio prompt form over the P7-10a application service, with real provider/model/effort selection, OAuth/device-code progress, streamed/cancellable/reconnectable durable run status, and comparison against hand-authored or prior versions. Campaign-grounded generation is an explicit later mode, not the default.
- Add a context inspector showing the resolved common envelope, `DungeonGenerationContext` payload version, selected citations/authority labels, and payload hash without exposing secret credentials or unrestricted source bodies.
- Preserve the fully model-independent path and make gateway failure degrade to inspect/validate/render/export/manual-regeneration behavior.
- Extend fixed-seed golden and property-based fixtures with faux-provider browser/stream contract cases.
- Measure first-pass validity, repair count, targeted-edit preservation, render/export correctness, context relevance, and DM edits.

Example flow:

```text
dm dungeon prompt "A flooded archive beneath a lighthouse"
dm dungeon generate --brief crypt.md --seed 1842
dm dungeon validate <version-id>
dm dungeon render <version-id> --variants dm,player
dm dungeon regenerate <version-id> --component room:<id> --lock-rest
dm dungeon export <version-id> --format print-pdf
dm dungeon export <version-id> --format roll20
dm prep approve <version-id>
```

### P7-12 — Dungeon model-interface V2 and run-integrity hardening

This is a post-P7-10 reliability program prompted by live-provider evidence. The high-level authority boundary remains correct, but `DungeonGenerationIntentV1` exposes too much kernel detail, the shared gateway does not yet preserve native assistant/tool-result message roles, nominal cumulative deadlines are passed to each provider turn in full, INFO logs contain complete dungeon bodies, expected model/compile failures still collapse into generic execution errors, and artifact generation can be marked successful before all required assets are linked. Complete these slices in order before making the V2 profile the default. Do not rewrite immutable V1 artifacts or conflate this work with P3 canonical revisions.

#### Target V2 boundary

```text
DM request + resolved DungeonGenerationContext + server-pinned seed
    |
    v
model-authored DungeonGenerationProposalV2
    `-- compact DungeonDesignSpecV2 using temporary local refs
    |
    v
submit_dungeon_intent_v2 (one structured submission, no commit/approval)
    |
    v
versioned deterministic design compiler
    |-- validate local refs and bounded enums
    |-- derive stable opaque IDs, counts, visibility, sizes, capacities, gates
    `-- emit exact DungeonBrief + DungeonTopology
    |
    v
existing deterministic preflight/layout/geometry pipeline
    |-- accepted -> atomically persist complete draft package/assets
    `-- rejected -> compact semantic diagnostics -> at most one fresh repair submission
```

The V2 model contract is intentionally not the kernel topology contract. The model may use bounded, human-readable local references such as `upper`, `archive`, or `sanctum` solely to relate submitted elements. Deterministic code maps those references to canonical package IDs using a pinned compiler/ID-derivation version. Semantic IDs must not depend on layout seed or array order; duplicate/ambiguous local references fail explicitly. Existing established opaque IDs may be supplied only by later explicit regeneration/edit workflows, never invented by the initial model submission.

`DungeonDesignSpecV2` should require only creative decisions:

- title, premise, purpose, themes, tones, pacing, and bounded prose constraints;
- floors with names and relative scale bands;
- rooms nested under floors with local ref, readable name, role, required/optional intent, relative size band, tags, and optional bounded preparation prose;
- connections by local room ref with semantic passage type plus independent concealment/barrier/hazard intent;
- requested branches, loops, secret routes, clues/keys/puzzles, encounter-slot intent, and final objectives by local ref;
- explicit unknown/conflict/abstention fields in the Workbench proposal wrapper.

The model must not supply schema-derived floor/room counts, canonical component IDs, package IDs, seeds, exact coordinates, numeric room dimensions/capacities, renderer layers, exact player/DM visibility, generated gate/trap IDs, validation status, asset metadata, lifecycle state, or canonical campaign operations. The compiler derives exact counts; maps relative floor/room size and occupancy bands through pinned tables; applies fail-closed visibility for secret/trapped routes and DM-only rooms; creates gate/key/clue references; and emits the strict existing kernel contracts. It may apply documented mechanical defaults but must return a warning or error rather than inventing missing narrative dependencies.

`submit_dungeon_intent_v2` is a proposal-validation tool, not a persistence or generation authority. It accepts exactly one `DungeonGenerationProposalV2`, validates it, invokes the deterministic compiler and preflight, and returns one of:

```text
accepted: true
candidate_hash
compiler_version
summary: floor/room/connection/secret-route counts plus entry/exit names
warnings: bounded stable diagnostics
```

or:

```text
accepted: false
diagnostics: at most 8 stable code/path/repair records
```

The accepted tool arguments are the structured model result; do not ask the model to echo the full proposal as final text. Do not return exact geometry, renderer output, source bodies, or the complete generated package to the model. A rejected submission may receive one fresh explicit repair request containing the previous compact proposal plus bounded diagnostics. It uses the same single submit tool and a newly calculated remaining budget; it is not represented as a fake user-message tool continuation.

#### P7-12a — Architecture decision, contracts, and compatibility boundary

**Work**

- Update the technical architecture before implementation to distinguish `DungeonGenerationProposalV2`, model-independent `DungeonDesignSpecV2`, compiled kernel intent, exact `LayoutRequest`, and `DungeonPackage`.
- Amend the model-tool section so initial generation uses one structured submission boundary. Keep incremental add/connect/regenerate tools as possible later DM-edit operations rather than exposing five overlapping full-intent tools in the initial task profile.
- Record that local refs are noncanonical relation handles and specify deterministic, versioned ID derivation independent of layout seed and array position.
- Define compiler ownership: the independently testable pure dungeon package owns `DungeonDesignSpecV2`, deterministic ID/default/policy compilation, and compile diagnostics; the Workbench owns the proposal wrapper, context, provider calls, attempt state, persistence, and approval boundaries.
- Define V1 compatibility: existing `dungeon_generation_intent_v1`, specifications, lineage, artifacts, versions, and exports remain immutable/readable. V2 gets new schema/profile/instruction/compiler versions and does not rewrite V1 JSONB.
- Decide explicitly whether existing `generation_run` JSONB fields can hold all safe prompt-attempt pins. Add a migration only if a concrete required query/constraint cannot be represented without one; do not add a second run database or queue.
- Specify terminal run stages and error taxonomy: `model_transport`, `model_submission`, `intent_compile`, `deterministic_preflight`, `render`, `asset_stage`, `persistence`, `completed`.

**Deliverables**

- Updated `dm-assistant-technical-architecture.md` and this implementation plan.
- JSON examples for a minimal one-floor dungeon, the two-floor Flooded Archive, one abstention, and one rejected local-reference case; examples remain synthetic and contain no real campaign text.
- A compatibility table mapping V1 fields to V2 model fields, compiler-derived fields, or deliberately removed fields.

**Frozen illustrative V2 examples (P7-12a)**

These are proposal/design-shape examples, not kernel JSON or provider prompts. Exact enum spelling, bounds, canonical serialization, and compile diagnostics are frozen by P7-12d; the ownership boundary below is normative now.

Minimal one-floor design:

```json
{
  "proposal_version": "2",
  "design": {
    "title": "The Salt Cellar",
    "premise": "A tide-worn cache protects a sealed ledger.",
    "floors": [{
      "local_ref": "cellar",
      "name": "Salt Cellar",
      "floor_scale": "small",
      "rooms": [
        {"local_ref": "entry", "name": "Wet Steps", "role": "entrance", "room_size": "small"},
        {"local_ref": "vault", "name": "Ledger Vault", "role": "objective", "room_size": "medium"}
      ]
    }],
    "connections": [{"from": "entry", "to": "vault", "passage": "door", "barrier": "none"}],
    "objectives": [{"room_ref": "vault", "kind": "final_objective"}]
  },
  "unknowns": [],
  "conflicts": []
}
```

Two-floor synthetic Flooded Archive design:

```json
{
  "proposal_version": "2",
  "design": {
    "title": "Flooded Archive",
    "themes": ["flooded records", "lighthouse"],
    "floors": [
      {"local_ref": "upper", "name": "Keeper Level", "floor_scale": "small", "rooms": [
        {"local_ref": "landing", "name": "Lantern Landing", "role": "entrance", "room_size": "small"},
        {"local_ref": "lift", "name": "Archive Lift", "role": "transition", "room_size": "small"}
      ]},
      {"local_ref": "archive", "name": "Flooded Archive", "floor_scale": "medium", "rooms": [
        {"local_ref": "stacks", "name": "Drowned Stacks", "role": "exploration", "room_size": "medium"},
        {"local_ref": "reliquary", "name": "Seal Reliquary", "role": "objective", "room_size": "small"}
      ]}
    ],
    "connections": [
      {"from": "landing", "to": "lift", "passage": "door"},
      {"from": "lift", "to": "stacks", "passage": "stairs"},
      {"from": "stacks", "to": "reliquary", "passage": "passage", "concealment": "secret"}
    ],
    "objectives": [{"room_ref": "reliquary", "kind": "final_objective"}]
  }
}
```

Explicit safe abstention (no design is compiled or persisted):

```json
{
  "proposal_version": "2",
  "abstention": {"kind": "insufficient_creative_direction"},
  "unknowns": ["desired dungeon purpose"],
  "conflicts": []
}
```

Rejected duplicate local reference (the compiler returns a bounded diagnostic):

```json
{
  "proposal_version": "2",
  "design": {"floors": [
    {"local_ref": "upper", "rooms": [{"local_ref": "archive", "role": "entrance"}]},
    {"local_ref": "lower", "rooms": [{"local_ref": "archive", "role": "objective"}]}
  ]}
}
```

```json
{"accepted": false, "diagnostics": [{"code": "design.duplicate_local_ref", "path": "/design/floors/1/rooms/0/local_ref", "affected_refs": ["archive"], "repair": "use a unique room local ref"}]}
```

| V1 field/category | V2 disposition | Owner / compatibility |
| --- | --- | --- |
| V1 brief title, premise, theme, tone, hooks | compact design prose | model may propose; V1 stored value remains readable unchanged |
| V1 floors/rooms/connections and role intent | local-ref design elements | model proposes relations; compiler resolves refs and exact kernel forms |
| V1 package/component IDs | compiler-derived | V2 model cannot supply them; old V1 IDs remain historical data |
| V1 floor/room counts, dimensions, capacities | compiler-derived | V2 uses relative scale/size/occupancy bands only |
| V1 seed, layout/generator inputs, locks | server-owned `LayoutRequest` | never accepted in initial V2 submission |
| V1 visibility/layers, gates/traps/clues/dependencies | compiler-derived policy | compiler fails closed and reports missing required dependencies |
| V1 coordinates, geometry, renderer/export/asset metadata | deliberately removed from model contract | deterministic layout/rendering and atomic publication own them |
| V1 validation/lifecycle/approval/campaign operations | deliberately removed from model contract | deterministic validation and authenticated human workflows own them |
| V1 specification, lineage, artifacts, versions, exports | immutable read compatibility | V2 adds new version pins; it never rewrites V1 JSONB |

**Done when**

- Review can identify exactly which process owns every field and transition.
- No V2 field lets a model select scope, seed, canonical ID, publication visibility, lifecycle, renderer syntax, arbitrary file/SQL access, approval, or canonical commit.
- The first implementation task can begin without inventing contract behavior in code.

#### P7-12b — Atomic generated-package completion and asset fault containment

Fix persistence correctness before routing another profile through it.

**Work**

- Split deterministic preparation from database publication: compile/generate/validate/render all required specification, validation, DM-notes, DM/player preview, and manifest bytes before creating a current artifact version.
- Validate every pending asset role, ordinal, MIME type, byte size, and audience policy before database publication. Keep clean exports fail-closed.
- Stage content-addressed blobs before the relational transaction. A staged unreferenced hash may remain deduplicated after rollback; no artifact/version/run may claim success unless every required metadata/link row commits.
- Add one repository/application operation that, in one PostgreSQL unit of work, creates the draft artifact when needed, creates its immutable version, links all required generated assets, advances `current_version_id`, and transitions the deterministic generation run to `succeeded`.
- Keep a durable generation run `running` while deterministic work executes. On generation/render/staging/publication failure, transition it once to `failed` with stable stage/codes and create no current artifact version. Never finish a run as succeeded before asset links exist.
- Delay initial artifact creation until a complete package is ready so model, compile, layout, and preview failures do not leave empty artifacts. Regeneration continues to create a child only on complete success.
- Preserve the content-addressed store's no-overwrite/hash verification. Do not attempt to mutate or fill missing assets on historical immutable versions; retire an incomplete artifact through its lifecycle if necessary.

**Tests**

- PostgreSQL integration fault injection before version creation, during the Nth asset stage/link, during `current_version_id` update, and during run finish.
- Assert each fault leaves a failed run, no partially current version, no partial artifact-asset rows, and no success response.
- Assert a successful package has exactly the required role/ordinal set and that all MIME contracts validate before transaction entry.
- Regression for the DM-notes MIME failure that previously produced a succeeded run/current version followed by CLI exit `1`.
- Existing hand-authored Studio create/regenerate/export/approval behavior remains green.

**Done when**

- `success=true`, terminal run status `succeeded`, a current immutable version, and the complete required asset set become one observable outcome.
- Any expected asset/persistence fault has a stable stage/code and cannot masquerade as model rejection or leave a playable incomplete draft.

#### P7-12c — Shared model-run budgets, transcript contracts, and safe error taxonomy

**Work**

- Separate a one-shot `StructuredSubmissionRunner` from the general `BoundedToolLoop`; do not make the compact dungeon submission inherit open-ended agent behavior.
- Enforce a truly cumulative monotonic time budget. Before each provider request, derive a request profile with `ceil(deadline-now)` seconds, bounded to the gateway contract; never pass the original full duration to every turn. Apply the same approach to remaining turn, tool-invocation, and token budgets across outer deterministic repair calls.
- Treat missing usage as unknown rather than zero-cost success. Retain the provider output-token cap and bounded message/body character limits; record whether usage was measured or unavailable.
- Reject duplicate tool-call IDs, unknown tool names, duplicate single-submit calls, and calls after the remaining budget is zero with stable model-run errors.
- Route invalid tool arguments through bounded submission/schema diagnostics. Do not turn expected model argument mistakes into `ValueError`/`dungeon_execution_failed`.
- Expand the normalized Python/Node gateway message contract to a discriminated union for `user`, `assistant`, and `tool_result`, matching `pi-ai`'s `AssistantMessage`/`ToolResultMessage` semantics including call ID/name, `isError`, content, and required opaque continuity signatures. Reject malformed role/content combinations.
- Preserve Python/PostgreSQL as the durable authority. The gateway may translate normalized messages for transport but must not own campaign/domain state or an authoritative tool loop.
- For V2 rejection repair, deliberately start a fresh bounded submission request with previous compact proposal and diagnostics. Reserve native assistant/tool-result continuation for workflows that truly execute iterative tools, and contract-test it independently.
- Map provider, submission, compile, deterministic, asset, persistence, cancellation, rate-limit, usage-limit, and timeout failures to stable public codes. Keep tracebacks/provider text/model-authored abstention text out of public responses.

**Tests**

- Fake monotonic clock proves two/three turns cannot exceed the total deadline and that the gateway receives decreasing limits.
- Python/Node contract tests round-trip user, assistant tool-call, and tool-result messages through the faux provider without converting them into plain user JSON.
- Tool argument/schema failures enter one bounded repair path and preserve only safe diagnostics.
- Cancellation works during every provider turn and no later turn starts.
- Public CLI/API/web errors are stable and response-safe; unexpected exceptions retain a correlation/stage record without exposing values.

**Done when**

- A nominal 300-second profile cannot consume more than 300 seconds of provider request budget.
- The code no longer claims native tool continuation while transporting only user messages.
- Every expected failure maps to an actionable category rather than a generic internal typed-input failure.

#### P7-12d — Compact `DungeonDesignSpecV2` and deterministic compiler

**Work**

- Add strict versioned model-independent contracts to `dm_dungeon` for floor, room, connection, objective, dependency, and preparation-prose intent using bounded enums/text/counts and `extra=forbid`.
- Keep nesting shallow and defaults explicit for small-model reliability. Prefer omission/defaults over nullable fields, but do not create a universal optional-field context DTO.
- Use orthogonal semantic connection fields so concealment, barrier, and hazard intent are not overloaded into one fragile enum. Examples: passage type (`passage`, `door`, `stairs`, `ladder`), concealment (`open`, `secret`), barrier (`none`, `locked`, `puzzle`), hazard (`none`, `trapped`).
- Define relative `floor_scale`, `room_size`, and optional occupancy bands. Add pinned deterministic mappings to existing numeric kernel constraints; models never emit exact cells or occupant arithmetic.
- Compile local refs into stable opaque IDs with a documented hash/slug algorithm and collision diagnostics. Keep IDs stable when unrelated arrays reorder or prose changes; change IDs only when the local semantic identity or compiler version changes.
- Derive brief/floor/room counts, publication visibility, layers, gate/trap/clue IDs, dependency references, capacity ranges, and kernel defaults. Secret/trapped elements and connections to DM-only rooms become DM-only deterministically.
- Require explicit entrance/final objective semantics or return a compact diagnostic; do not infer chronology or a final objective from unrelated prose. Apply only documented unambiguous defaults.
- Return `DungeonDesignCompileResult` containing either exact `DungeonBrief`/`DungeonTopology` plus warnings and a canonical input/output hash, or bounded stable diagnostics with paths/local refs.
- Keep compiler functions pure and independently testable with no Workbench/provider/database imports.

**Tests**

- Canonical JSON and schema-version round trips; unknown fields/versions fail.
- Golden compilation for minimal, multi-floor, branch, loop, secret route, locked clue/key, trapped route, optional room, and final relic cases.
- Property tests for deterministic IDs, reorder stability, unique references, count derivation, fail-closed visibility, gate solvability, and compile replay.
- Dependency-isolation tests continue to prohibit Workbench/FastAPI/SQLAlchemy/provider imports.
- The compiled Flooded Archive reaches the existing kernel without model-authored canonical IDs, counts, numeric dimensions/capacities, or visibility fields.

**Done when**

- A hand-authored compact V2 spec deterministically compiles into the existing strict kernel contracts and passes/fails existing validators with structured diagnostics.
- Recompiling the same canonical V2 spec and compiler version produces byte-equivalent compiled intent.

#### P7-12e — `submit_dungeon_intent_v2` and bounded submission repair

**Work**

- Add Workbench `DungeonGenerationProposalV2` around `DungeonDesignSpecV2` with intent summary, requested constraints, citations/rules fields for future grounded mode, unknowns/conflicts, and abstention. Standalone defaults still contain no retrieval/citations.
- Define one server-owned `submit_dungeon_intent_v2` schema. Its input contains the proposal only; scope, campaign owner, seed, context, profile, compiler/generator versions, authorization, and publication policy remain server-supplied.
- Add a `StructuredSubmissionRunner` that accepts exactly one valid submit call as the structured result. It validates arguments, runs the compiler and deterministic preflight, records the exact accepted proposal/compiled request in restricted lineage, and does not request a duplicate text response.
- If syntax/reference/compile/preflight fails, return at most eight `code`, `path`, `affected_refs`, and `repair` records. Start at most one fresh repair submission with the complete compact prior proposal and diagnostics.
- Do not expose review-brief, review-topology, generate-layout, validate-intent, or targeted-regeneration tools in the initial V2 profile. Those operations remain deterministic orchestration or later explicit edit workflows.
- Create a new task-profile UUID/version, prompt/instruction version, output/tool schema version, and selection-policy version. Never reinterpret stored V1 profile lineage as V2.
- Keep provider capability checks explicit: V2 requires reliable tool calls; provider-specific constrained argument generation may be enabled only when advertised and contract-tested. Preserve strict server validation for every provider.
- Bound the proposal by floor/room/connection/text limits suitable for the product and gateway. Reject oversized designs with an actionable suggestion to split the task; do not silently truncate topology.

**Tests**

- Faux provider submits a valid proposal in one call and receives no second request.
- Invalid JSON/tool arguments, duplicate submits, unknown refs, compile errors, and deterministic preflight failures use one repair at most and pin preservation/replacement lineage.
- A model cannot submit seed, canonical IDs, scope, visibility policy, lifecycle, approval, SQL/file paths, renderer syntax, or campaign grounding.
- Accepted output stores exact proposal hash, compiler input/output hash, profile/schema/compiler/generator versions, and semantic diagnostics without hidden reasoning.
- Abstention is explicit and safe; arbitrary model-authored abstention text is not echoed publicly.

**Done when**

- The model expresses only compact creative intent, Python accepts the submit call as the final structured response, and deterministic code owns every exact/authoritative field.

#### P7-12f — Shared CLI/web integration, durable attempts, and observability

**Work**

- Add one shared `DungeonPromptApplicationService` used by CLI and web. It resolves campaign/default model/effort/seed/context once, starts durable attempt state, invokes V2 submission/repair, invokes atomic package publication, and returns one common result.
- Start a durable prompt-attempt `generation_run` before contacting the gateway for every surface, including native/Compose CLI. Use its UUID as caller run ID for cancellation and correlation; keep the final artifact package generation run separate and link both IDs in input scope/lineage.
- Bind `attempt_run_id`, optional artifact `generation_run_id`, provider/model, profile version, and stage in Workbench logs. Have the gateway log both caller run ID and private gateway stream ID so one attempt is traceable across processes.
- Replace full INFO-level `layout_request`/model body logging with hashes, schema/compiler/generator versions, seed, component counts, elapsed time, result, and stable diagnostic codes. Exact accepted proposal/compiled request remains in restricted immutable artifact lineage or an explicit authenticated diagnostic export, never ordinary logs.
- Log Pydantic locations/types and stable application diagnostic codes, not raw Pydantic/custom messages containing model-authored IDs/text. Repair prompts may receive bounded safe messages independently of logs.
- Add stage-specific terminal events and public errors for model transport, missing submit call, schema invalid, compile/reference invalid, topology/layout invalid, preview failure, asset stage failure, persistence failure, cancellation, and unexpected internal failure.
- For unexpected exceptions, log correlation ID, stable stage, and exception class. Add an explicit local development/debug path for a redacted traceback; do not expose stack/provider/model bodies through normal CLI/API/web output.
- Add `dm dungeon run inspect <attempt-run-id>` (or extend an existing run inspector) to show safe profile, timing, stages, hashes, counts, and diagnostics. It must not show credentials, prompts, raw provider responses, or unrestricted context/source bodies.
- Ensure web SSE reconnect/cancel reads the same durable attempt state rather than maintaining a divergent error taxonomy.

**Tests**

- CLI and web faux-provider tests assert the same attempt ID, stage sequence, public code, and final artifact link.
- Cross-process log capture proves caller run ID correlation and absence of prompts, source text, provider payloads, full layout requests, credentials, and secret URLs.
- Failed pre-topology attempts are durably inspectable; successful attempts link to the final package generation run/version.
- Structured log redaction tests include malicious IDs/messages that resemble credentials or log fields.
- Existing hand-authored workflows remain fully operational with the gateway disabled.

**Done when**

- Every prompt attempt is durable and correlatable before provider contact.
- Ordinary logs answer where and why a run stopped without containing dungeon/context bodies.
- CLI and web cannot disagree about whether a draft exists or which failure category occurred.

#### P7-12g — Small-model eval, rollout, and V1 retirement decision

**Work**

- Extend the synthetic eval set with compact one-floor, two-floor, secret lower level, branch/loop, clue/key gate, trap, optional room, hidden area, final relic, and intentionally impossible prompts. Do not include copyrighted or real campaign content.
- Measure V1 versus V2 on tool compliance, first-pass schema validity, first-pass compile/preflight validity, success after one repair, preservation of requested semantics, deterministic package validity, player-output leakage, input/output tokens, latency, and DM edits.
- Evaluate models by observed capability rather than branding. Include an opt-in live run for a measured smaller candidate such as Luna only after faux/provider contracts pass; never make live provider calls part of CI.
- Set a candidate default only after documented thresholds. Initial target gates: 100% faux contract compliance; zero player-secret leaks; 100% deterministic replay for accepted proposals; at least 90% syntactically valid first submissions and 95% valid after one repair on the fixed synthetic suite; no generic internal error for expected model/compile failures. Record measured latency/token thresholds before enforcing them.
- Add an inspectable opt-in `dungeon-intent-v2-eval` selection policy. Run V1/V2 comparisons without double-persisting artifacts or sending one provider response into another model's context.
- Cut the default to V2 only after CLI, web, cancellation, atomic publication, logs, and eval gates pass. Retain V1 readers/replay fixtures; disable new V1 generation first, then decide separately whether obsolete V1 orchestration code can be removed.
- Update operator/developer documentation with the compact boundary, safe live smoke procedure, run inspection, failure categories, and rollback to the prior profile selection.

**Phase gate P7-12**

- A small capable tool-calling model can submit the synthetic Flooded Archive through one compact call without canonical IDs, repeated counts, exact dimensions/capacities, seed, or visibility fields.
- Deterministic compilation and existing kernel validation own all exact mechanics and fail closed.
- One bounded repair is sufficient for expected model mistakes; cumulative time/turn/tool/token limits are real.
- Every CLI/web attempt is durable, correlated, safely inspectable, and body-free in ordinary logs.
- Successful status/current artifact version/required asset links are atomic; injected faults cannot leave a succeeded incomplete package.
- Existing V1 artifacts remain readable and immutable, and gateway-disabled hand-authored Studio workflows remain green.
- Objective V2 evals justify any default-model/profile change; model names alone do not.

### P7-13 — Dungeon output, map readability, asset UX, and print refresh

This user-directed post-P7-12 program is specified in detail in
[`dungeon-output-refresh-plan.md`](dungeon-output-refresh-plan.md). The latest generated
output exposed coupled geometry, renderer, feature-content, asset-presentation, and
print failures. No user dungeon or external dungeon consumer currently requires
backward compatibility, so advance the active V2 contracts and synthetic fixtures in
place instead of creating a parallel V3 stack. Complete these slices in order; do not
fold them into P3 canonical revision work. Once a dungeon is retained or an external
consumer exists, the normal immutable reader/replay policy applies.

#### P7-13a — Output quality baseline and print fail-closed switch

- Freeze a synthetic output regression fixture and objective geometry, collision,
  feature-completeness, asset-presentation, and print-sparsity metrics.
- Split PDF and Roll20 export selection at the shared application boundary.
- Centrally disable new exact-scale PDF generation with stable CLI/API/web behavior;
  retain historical PDF access and keep Roll20 export operational.

#### P7-13b — Connection semantics, compact placement, and geometry validation

- Remove the universal room gap: direct-door rooms share a wall, passage links use
  explicit corridor cells, and unrelated rooms retain one cell of rock clearance.
- Version connection geometry so direct doors are not synthetic corridors; route
  passages straight-first with endpoint approach/lead constraints and deterministic
  bend/length/clearance scoring.
- Prohibit corridor interior overlap with rooms, endpoint doglegs, undeclared openings,
  and doors not located on a shared wall.

#### P7-13c — Renderer visual grammar and collision-free annotation

- Replace raw room IDs with stable short callouts linked to a DM key.
- Add one code-owned grayscale-safe grammar for rooms, ordinary/secret/locked/trapped
  doors, traps, puzzles, clues/keys, transitions, objectives, and physical features.
- Add deterministic text-bound collision avoidance and preserve fail-closed player
  filtering before XML/PNG/PDF construction.

#### P7-13d — Doors, traps, puzzles, features, and a usable DM guide

- Extend the active V2 creative/proposal/compiler contract in place. Advance its
  schema/compiler pins and update synthetic fixtures rather than preserving an unused
  pre-P7-13d V2 reader or creating parallel V3 classes. Include tones, room
  tags/preparation prose, explicit branch/loop requirements, encounter-slot intent,
  features, composable door mechanics, traps, hazards, and puzzles.
- Continue from the committed P7-13d scaffolding rather than resetting or reverting
  its commit: port its useful intent shapes, mechanics policy, diagnostics, and tests
  into V2, then remove the temporary V3-only files and dispatch after equivalent V2
  coverage passes. Do not discard completed P7-13a/P7-13b/P7-13c work.
- Freeze and enforce a connection-mechanics capability matrix in the advanced V2 contract:
  same-floor passages carry no hidden, barrier, or trap mechanics; same-floor doors
  support independent concealment, lock/puzzle gate, and trap mechanics in documented
  combinations; cross-floor stairs/ladders support directional hidden endpoints and
  optional, explicitly located source and/or destination endpoint-door/hatch mechanics.
  Those endpoint mechanics may independently carry concealment, lock/puzzle gate, and
  trap intent. Do not silently treat the vertical transition itself as a door.
- Define the endpoint-door/hatch intent shape, deterministic source/destination anchor
  geometry, directional traversal and unlock semantics, and dependency references for
  cross-floor barriers/traps. Reject only ambiguous or unsupported endpoint placement,
  never a valid explicitly located vertical barrier merely because it crosses floors.
- Let the model propose bounded creative descriptions and relative challenge bands;
  deterministic pinned policy owns stable IDs, exact marker placement, visibility,
  numeric difficulty values, dependency validation, and completeness diagnostics.
  Compile each supported door or vertical endpoint-door/hatch mechanic independently
  so concealment never discards a requested gate or trap.
- Keep geometry/markers in `dm_dungeon`; keep prose-heavy keyed notes in the Workbench.
  A missing trap effect or puzzle solution is unknown/incomplete, never invented.
- Make initial prompt guidance and bounded repair diagnostics capability-specific:
  say that hidden stairs/ladders are valid and show the explicit endpoint-door/hatch
  shape for vertical locks, puzzles, and traps. Diagnose an omitted or ambiguous
  endpoint rather than rejecting a valid cross-floor barrier merely for being vertical;
  never claim that all secret vertical links require a door.

#### P7-13d.1 — Prompt-contract reliability and bounded-cost recovery

This is a blocking continuation of P7-13d, prompted by live GPT-5.4 evidence after
its contract expansion. Do not begin P7-13e merely because the pure compiler and
renderer suites pass: basic prompt-to-draft generation must first be reliable and
cost-bounded. Keep exactly one initial submission and at most one repair; adding
retries or selecting a more expensive model is not an acceptable substitute.

**Work**

- Freeze provider-free regressions equivalent to the failed synthetic Flooded Archive
  submissions without storing provider responses. Cover the invalid `set_piece`
  encounter slot, a concealed door with omitted challenge, a concealed door whose
  duplicated concealment disagrees with its endpoints, and a repair that otherwise
  loses the lighthouse request.
- Audit every runtime `model_validator` affecting model-controlled proposal fields
  against the JSON Schema actually sent through the gateway. A first-pass requirement
  must either be machine-visible in the supported provider schema or cease to reject
  submission. Do not rely on prose instructions to repair an invisible contract.
- Simplify the connection contract rather than adding more coupled fields:
  derive physical door/hatch concealment from `from_hidden`/`to_hidden` and the named
  vertical endpoint instead of asking the model to repeat `concealed`; allow the model
  to omit an active mechanic's relative challenge and apply one documented pinned
  default (`moderate`) before exact policy mapping. Preserve an explicitly supplied
  valid challenge.
- Separate draft generation validity from preparation readiness. Missing trap
  trigger/effect, puzzle solution, or lock/puzzle dependency remains explicit unknown
  preparation data and blocks approval for play, but does not discard an otherwise
  connected map draft. Unknown data must remain visible in the DM guide/readiness
  report; deterministic code must not invent prose, silently remove the mechanic, or
  mark the artifact ready. Unknown refs, contradictory endpoint placement, impossible
  floor/link types, duplicate identities, and invalid topology remain hard submission
  errors.
- Make the default instruction request the smallest design that satisfies the DM's
  prompt. Optional branches, loops, encounter slots, traps, puzzles, and features are
  omitted unless requested or necessary to the stated premise; schema breadth is not
  an instruction to populate every collection.
- Repair schema-invalid submissions with the original DM prompt, authorized context
  envelope, a size-bounded canonical copy of the prior tool arguments, and stable
  actionable diagnostics. Diagnostics must state allowed enum values or the violated
  capability rule without echoing arbitrary model prose. Tell the model to preserve
  the requested dungeon and valid prior content while changing only invalid fields.
  Keep these bodies out of ordinary logs.
- Extend the Python/Node tool contract to request `pi-ai` JSON-schema constrained
  sampling when the resolved provider advertises and passes that capability. Start
  with `prefer`; use `require` only after provider-contract coverage proves the active
  schema subset is supported. Server-side validation remains authoritative.
- Lower the V2 request output cap from 16,384 to an eval-justified basic-generation
  limit, initially at most 4,096 output tokens, and cap cumulative initial-plus-repair
  usage, initially at most 12,000 measured tokens. If a frozen required case cannot fit,
  raise the smallest limit justified by its measurements rather than restoring the
  endpoint maximum. Missing usage remains unknown and follows the existing fail-closed
  repair policy.
- Add a staged opt-in live gate rather than more manual retries: provider/faux tests
  first, then the exact Flooded Archive as a stop-on-failure canary, then the fixed
  synthetic suite only if the canary passes. Record body-free validity, semantic,
  latency, token, and estimated/available cost observations. The canary must retain a
  small upper floor, larger lower floor, secret descent, Flooded Archive identity, and
  final Stone of Redemption objective.
- Do not add a second model call in this task. After the contract/repair fixes, measure
  whether one compact submission still couples basic topology to optional enrichment.
  If the live gate remains below P7-12g thresholds, add a separately reviewed
  P7-13d.2 architecture slice for core topology first and optional DM-guide enrichment
  second; it must reuse the accepted package IDs, be independently skippable, and have
  a lower measured total failure/cost rate than the one-call design.

**Tests**

- JSON-schema/gateway contract tests for visible enum and required-field behavior plus
  server tests proving no schema-advertised payload is rejected solely by an invisible
  connection-mechanics invariant.
- Submission tests proving schema-invalid repair retains bounded original task/prior
  arguments, returns actionable diagnostics, preserves valid content, and never emits
  a third provider request.
- Compiler/readiness/guide tests proving incomplete optional mechanics produce a valid
  draft with blocking unknowns, while topology/reference contradictions still reject.
- Prompt tests proving an unrequested basic dungeon does not gratuitously populate all
  advanced collections.
- Node faux-provider coverage for constrained-sampling translation and explicit
  unsupported-capability fallback.

**Done when**

- The exact Flooded Archive canary succeeds within the frozen cost/token ceiling and
  preserves every requested semantic, without hand-editing or repeated manual runs.
- The fixed live suite meets the existing P7-12g target of at least 90% first-pass
  schema validity and at least 95% acceptance after one repair; with ten cases, the
  latter means all ten must succeed.
- Every repair has enough bounded context to repair the original dungeon, and every
  diagnostic tells the model what rule or value to change.
- A malformed optional enhancement cannot erase an otherwise valid basic map; the DM
  receives a draft with truthful readiness blockers instead.
- No profile gains additional repair turns, no provider response becomes a fixture,
  and no model is promoted merely to compensate for a defective contract.

#### P7-13e — Asset catalog, inline viewing, and meaningful filenames

- Project immutable role/ordinal links into floor/audience/purpose groups: Maps, DM
  guide, Virtual tabletop, Print, and Advanced technical lineage.
- Add artifact-version-scoped Open and Download routes with safe purpose-derived
  filenames. Images, trusted SVG, text, JSON, and PDFs can open in-browser; ZIP remains
  attachment-only; DM notes download as UTF-8 `.txt`.
- Stop presenting persistence labels such as `manifest #0` and UUID blob names as the
  primary user interface.

#### P7-13f — Print redesign and guarded re-enable

- Add separate bounded reference-map and selected-region exact-scale tactical modes.
- Preflight crop dimensions, page count, occupied coverage, paper, audience, and scale;
  reject excessive or mostly blank output before generating bytes.
- Re-enable print only after sparse-map rejection, per-page visual-content checks,
  exact calibration, and stitch/alignment gates pass.

#### P7-13g — Integrated UX/eval gate and rollout

- Exercise prompt through floor preview, DM/player switch, keyed guide, VTT download,
  print preflight, and preparation review in one browser workflow.
- Preserve topology/geometry validity, deterministic replay, secrecy, atomic
  publication, cancellation, and package isolation. Keep reader gates for artifacts
  that actually exist; update synthetic pre-P7-13d V2 fixtures in place rather than
  carrying dormant compatibility branches.
- Roll out new profile/generator/renderer pins only after synthetic metrics and manual
  DM review pass; retain rollback to the prior generation path. Add prompt/repair evals
  for hidden vertical access, secret locked/puzzle doors, secret trapped doors, and
  locked/puzzle/trapped endpoint doors or hatches on cross-floor transitions.
- Distinguish an explicit model abstention from exhaustion after rejected structured
  submissions in CLI/API/web/public-safe errors and durable attempt records; report
  the latter as no accepted proposal after bounded repair, with safe diagnostics rather
  than saying the model abstained.

**Phase gate P7-13**

- The bounded Flooded Archive live canary succeeds within the frozen token ceiling;
  schema-invalid repair retains the original task, and the fixed live suite meets the
  P7-12g first-pass/after-repair thresholds before further rollout.
- Direct doors are shared-wall openings; valid corridor bends never occur at room
  endpoints or overlap room interiors.
- Default maps contain no opaque IDs or colliding labels and use one consistent keyed
  feature grammar.
- The DM can identify secret/locked/trapped doors and difficulty plus every trap,
  puzzle, clue/key, transition, objective, and feature; player assets leak none of it.
- Assets are organized by purpose/floor/audience, common formats open inline, downloads
  have meaningful names, and notes are `.txt`.
- New print output remains disabled until reference/tactical preflight and nonblank-page
  gates pass; historical assets remain immutable/readable.

### P7-14 — Dungeon generation alpha reset and constructive V1

This user-directed recovery supersedes P7-13e through P7-13g until its Tier A gate
passes. The complete model contract, topology proof, constructive layout, stress ladder,
and resumable slices are in
[`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md).

#### P7-14a — Architecture, characterization, and green baseline

- Freeze Tier A as one floor, 4–8 rooms, one critical path, bounded branches/loop,
  bounded gate/secret/trap/feature/encounter intent, and DM/player SVG/PNG.
- Add active-generator properties for simple plans and the observed assertion/out-of-
  bounds failures. No active supported plan may throw an exception.
- Pause live calls and P7-13 output/print work.

#### P7-14b — One alpha V1 and dead-code deletion

- Collapse proposal/design/compiler/topology/package/generator names and pins to one V1;
  remove numeric suffixes from active public Python names.
- Delete old model generation, generator branches, readers, known-bad baseline fixtures,
  and compatibility tests because no user artifact or external consumer exists.
- Recreate only useful synthetic V1 fixtures, break circular imports, and require a green
  package/unit gate. Do not rewrite Git history.
- Update active V1 labels in place until the architecture/status explicitly declare the
  retention gate crossed. Synthetic fixtures, ignored review packets, disposable alpha
  rows, and provider canaries do not trigger version bumps or compatibility readers; the
  gate must be declared no later than first retained real-user data, external use,
  non-disposable deployment, or a promised replay obligation.

#### P7-14c — Creative plan and topology certificate

- Replace the arbitrary model-authored edge list with `DungeonPlan`: room purposes,
  critical path, branches, supported loops, gates/secrets, and bounded content intent.
- Construct a connected series/parallel-with-spurs graph and emit independently checked
  connectivity, cycle, branch, gate-order, public/secret reachability, room-demand,
  port-demand, and embedding witnesses.

#### P7-14d — Constructive Tier A geometry

- Allocate backbone columns, branch/loop bands, room dimensions, side ports, and
  corridor channels from the certificate; compute exact required bounds before cells.
- Keep seeded compaction/variation optional and fall back to the guaranteed baseline.
- Reach 100% valid output, zero exceptions, and zero leaks over generated Tier A
  plans/seeds.

#### P7-14e — Prompt/guide integration and stress ladder

- Expose only `submit_dungeon_plan`; one accepted tool call is the structural result.
  Put `DungeonGenerationProposal` fields directly at the tool-argument root rather than
  behind a redundant `proposal` envelope. Schema diagnostics and repair paths must refer
  to the actual root and preserve every valid prior field.
- Before a repair, estimate its complete canonical message plus tool-schema input and
  reduce the output allowance from the measured remaining cumulative budget. Check every
  completed structured response against both its pinned output ceiling and measured total
  request budget before validation/publication; persist only body-free overage metadata.
  Do not resume ordinary use of a provider whose reported usage exceeds the requested
  transport cap until that behavior is resolved or the budget policy is explicitly
  remeasured and revised. Freeze one current one-floor Tier A canary prompt and seed. Its
  non-production CLI-only acknowledged override may make only the output-cap acceptance
  check advisory for one stop-on-failure `openai-codex` canary; retain the requested cap,
  measured 12,000-token cumulative publication ceiling, repair reservation, body-free
  attempt policy, and accepted model lineage.
- Build exact keyed guide content after geometry; use separate entry-first sequential
  presentation numbers and concise valid Markdown/HTML with useful read-aloud text plus
  locally grouped actionable state, checks, clues, triggers, and consequences. Omit
  ordinary map-visible connectivity and separate sensory/purpose repetition; limit
  read-aloud to observable information. Puzzle and exploration guidance emphasizes clear
  player-observable clues and affordances, meaningful stakes/consequences, and reasonable
  approaches rather than requiring one prescribed physical manipulation. Describe only
  the mechanism and reset/retry behavior needed to adjudicate the particular scene; do
  not default unrelated content to linked machinery or alarm systems. Trap intent still
  distinguishes warning, trigger, detection, disable operation, and effect while code
  owns numeric difficulties. Optional enrichment fails independently and cannot erase a
  valid draft.
- Pass CLI/web/faux structural publication and use the fixed review packet to characterize
  renderer, secrecy, guide assembly, and contract expressiveness. Do not treat repeated
  rewrites or a passing worksheet for one synthetic archive as evidence that a model can
  generate fun, coherent content. The committed one-call guide path is characterization
  for the staged split below, not the final live Tier A authoring workflow.

#### P7-14f — Staged Tier A authoring and anti-overfitting evaluation

The one-call experiment has now supplied the measurement anticipated by P7-13d.1: asking
one model submission to choose progression while also writing every room narrative,
puzzle, exploration challenge, trap/feature interaction, and objective couples distinct
creative tasks and encourages verbose contract compliance rather than coherent play.
Implement the architecture's independently failable enrichment boundary before expanding
the topology stress ladder.

Current staged slices: the model-visible structural root no longer contains
`guide_content`; its accepted tool result reports typed content-slot counts and structural
publication leaves truthful readiness blockers. Strict exact-ID puzzle and exploration
input/output and semantic validation contracts exist. Trusted puzzle context construction
slices one accepted package down to its selected room geometry and explicitly approved
clue/objective/dependency IDs. One independently pinned faux-provider puzzle task now has
its own effort, prompt/schema, 6,000-token cumulative/2,048-output budget, and one budget-
reserved repair. Accepted puzzle content is projected into that exact room and atomically
published in a DM-only child version without changing package/map bytes or clearing
unrelated blockers; failure leaves the parent unchanged with safe durable diagnostics.
The exploration seam separately slices one exploration-role room to its local geometry,
exact exploration slot, approved local feature affordances, pacing role, stakes, and
constraints. One independently pinned faux-provider task now validates exact output IDs,
uses its own profile/effort/prompt/schema and 6,000-token cumulative/2,048-output budget
with one budget-reserved repair, retains accepted content/lineage, and atomically publishes
a DM-only child. Deterministic projection adds observable cues, multiple approaches/
consequences, and escalation/recovery without replacing accepted puzzle content, changing
package/map bytes, or clearing unrelated blockers. Rejection leaves the puzzle parent
current with body-free diagnostics. Other interactions, narrative, automatic staged
orchestration, and live calls remain later slices.

- Keep one compact structural `submit_dungeon_plan` call plus at most one schema repair.
  Its model-visible proposal contains room identity/purpose, critical path, bounded
  branches/loop, gate/dependency placement, named objective, and typed content slots with
  conservative spatial demand. Remove prose-heavy `guide_content` from this structural
  root in place under the pre-retention V1 policy. The structural model does not write a
  complete puzzle, exploration encounter, trap/feature interaction, and room prose in the
  same response.
- Compile, certify, lay out, and independently validate that structural result before any
  enrichment. Deterministic code owns exact topology, IDs, geometry, visibility, room
  demand, map references, DC policy, rendering, and publication. An enrichment failure
  must never request another random topology or erase a valid map.
- Add separate Workbench-owned typed enrichment tasks over exact package IDs. At minimum,
  puzzle generation and exploration-challenge generation are different model calls with
  different task profiles and strict domain contexts:
  - a puzzle call receives only the relevant room geometry, approved dependency/objective
    relationship, nearby approved clue locations, tone, and puzzle constraints, and
    proposes a solution model, clue path, bounded hints/alternate handling, failure/reset
    behavior, and player-observable elements;
  - an exploration call receives only its local geometry, approved environmental
    affordances, pacing role, stakes, and constraints, and proposes observable cues,
    multiple approaches, consequences, and escalation/recovery;
  - trap, feature, objective, and narrative work use similarly narrow typed tasks when
    model authorship is required. A homogeneous narrative task may cover the bounded room
    set only after accepted mechanics exist; it cannot invent or change those mechanics.
- Give every enrichment task its own prompt/instruction pin, model/effort selection,
  output and cumulative token budget, bounded repair policy, diagnostics, and durable
  lineage. Keep this proportionate: accepted content belongs in the authorized DM artifact;
  routine logs and attempt reports need only IDs/hashes, pins, usage, status/stage, and
  bounded code/path/repair facts, with raw transport bodies limited to explicit transient
  local debugging. Reuse the existing artifact specification and `generation_run`; do not
  add a redaction service or second audit store. Reuse only the small common scope/
  provenance/visibility/citation/hash envelope; do not create a universal optional-field
  guide context. Enrichment proposals cannot alter topology, geometry, another task's
  accepted content, deterministic arithmetic, preparation approval, or canon.
- Merge accepted enrichments deterministically into the exact room-centric guide. Missing,
  invalid, or human-rejected content leaves explicit preparation-readiness blockers while
  preserving the structurally valid draft and secrecy-clean maps. Subjective evaluation
  remains evidence, not a model or code approval operation.
- Retain the current Synthetic Constructive Archive packet as a renderer/secrecy/contract
  regression, not the quality oracle. Stop adding prompt rules or schema fields solely to
  repair that fixture. A new rule must express a general invariant or reproduce across at
  least two independent cases.
- Replace single-fixture iteration with a small synthetic evaluation set spanning at least
  three materially different, non-copyrighted settings and interaction styles. Compare
  prompt variants, supported effort levels, and model sizes with blinded human ratings for
  progression, clue logic, player agency, puzzle comprehensibility, exploration quality,
  prep usefulness, latency, token use, first-pass schema validity, and repair rate. Do not
  promote a larger model or deeper effort without measured quality improvement.
- Fix or replace the live transport so requested output limits are enforced before
  ordinary provider use. Then run the frozen staged Tier A canary before Tier B/C. Tier A
  must produce one accepted structural plan, valid topology/geometry, independently
  accepted required enrichments, a preparation-ready guide, secrecy-clean assets, bounded
  usage, and one atomic draft. The existing advisory Codex exception remains a narrowly
  recorded operator-risk escape hatch, not a substitute for the transport fix.
- Defer Tier B vertical composition and Tier C dense graphs until the staged live Tier A
  path has produced a usable artifact and the bounded Tier A evaluation set demonstrates
  dependable generation. B/C test scalability; they are not prerequisites for proving
  Tier A generation quality.

**Tests**

- Model-visible schema tests prove `submit_dungeon_plan` has no `guide_content` field and
  that no one request schema combines structural planning, puzzle design, and exploration
  design.
- Provider-free/faux orchestration tests prove exact-ID context slicing, independent task
  budgets/repairs/lineage, deterministic merge, no cross-task mutation, readiness blockers
  on partial enrichment, and atomic publication on complete enrichment.
- Puzzle and exploration contract tests use positive and negative cases that are not
  derived from the archive fixture. Eval reports preserve scores and safe measurements,
  never provider response bodies or copyrighted content.

**Done when**

- A DM prompt is not sent to one model call that must simultaneously solve structural
  planning and all detailed guide-content responsibilities.
- At least one frozen live Tier A run on the staged path produces a preparation-ready,
  human-usable artifact within the enforced workflow budget; failure is still safe and
  body-free.
- The multi-case Tier A evaluation shows which prompt/model/effort profile improves
  puzzle and exploration quality without relying on repeated edits to one fixture.
- Tier B/C remain deferred until these Tier A conditions hold.

**Phase gate P7-14 Tier A**

- Every generated supported topology is connected by construction and carries a
  recomputable certificate; every requested loop/gate/secret has a witness.
- Every supported certificate has a deterministic constructive orthogonal layout under
  its computed bounds. Validator failures are regressions, never normal random misses.
- Active properties cover 4–8 rooms across seeds with zero exceptions and 100% valid
  topology/geometry; clean output has zero DM-only leaks.
- One bounded structural `submit_dungeon_plan` call preserves fixed-prompt semantics and
  produces a valid certified package without also authoring detailed puzzles,
  exploration challenges, and room prose. Separately bounded typed enrichments over exact
  package IDs produce the runnable guide and cannot mutate the package.
- Human quality evidence comes from materially different Tier A cases, including at least
  one staged live artifact, rather than repeated rewrites of one fixed archive fixture.
  Every evaluated case records explicit decisions and ratings for the required dimensions.
- Measured output or cumulative usage over each task's pinned ceiling cannot publish its
  result, and no repair starts when its estimated complete input cannot fit the measured
  remaining budget.
- There is one V1 path and no dormant V2/V3/V4 generation or package dispatch.

**Phase gate P7**

- The independently runnable `dm_dungeon` package turns a constrained brief into a connected, non-overlapping, multi-floor practical grid with reproducible seed behavior and passes dependency-isolation tests.
- The model-independent Dungeon Studio completes import/create through preview/export/approval with no gateway credential.
- Required topology/gating/path/capacity validations pass or block approval with actionable diagnostics.
- DM/clean SVG and PNG plus Roll20-compatible image/metadata validate.
- Letter/A4 PDF pages print at one inch per five-foot cell, use the low-ink theme, and can be assembled reliably using overview/page IDs/cut/registration/overlap/alignment marks.
- Clean artifacts contain no secret doors, traps, encounter markers, or puzzle solutions.
- Targeted regeneration preserves locked components.
- No regional/world or illustration-first renderer has been introduced.
- Model-assisted runs pin a narrow `DungeonGenerationContext`; there is no universal optional-field generation payload.

### Deferred follow-up — Player-map reveal overlays

This is deliberately **not** part of P7-10b's first web streaming/eval scope. Add a later Dungeon Studio/session-play workflow for discoveries such as a secret door opening a previously hidden wing:

- Model a stable, independently publishable player-map reveal unit (an area/room/corridor group or renderer layer) with exact component IDs and an explicit initial publication state; it must not be inferred merely from adjacency or a room's `player_safe` classification.
- Produce separately printable SVG/PNG/PDF overlay sections that register against the base floor grid, scale, origin, and page-calibration metadata, so a DM can physically place a newly discovered room/wing over or beside the existing player map.
- Support a web-map equivalent that can reveal the same approved overlay layer without sending unrevealed geometry, secret-door markers, traps, creature starts, hidden DCs, or puzzle solutions to the player client.
- Treat each reveal/publication action as durable preparation/session state with actor/time/package-version provenance, never as canonical campaign truth; preserve the original immutable dungeon package and pin any derived player-publication artifact/version.
- Add leak, registration/alignment, partial-reveal, and repeatable-print tests. A hidden section must remain absent rather than appear as an unexplained disconnected player-safe room before its explicit reveal.

---

## P8 — Creature Profiles and Party-Aware Encounter Generation

### Goal

Populate dungeon spaces with complete, rules-grounded combat and noncombat encounters adapted to a pinned party/playstyle snapshot. Begin as a Workbench feature: isolate deterministic mechanics in cohesive modules, but do not assume the creative/orchestration workflow is a reusable engine package.

### P8-01 — Complete creature profile schema and source adapters

**Work**

- Define/migrate complete edition-tagged creature profile snapshots and lineage.
- Cover all normal 5e/2024 stat-block sections, including optional legendary/mythic/lair/spellcasting sections.
- Implement synthetic fixture and adapter contracts for authorized bestiary sources.
- Preserve source citations and prohibit real copyrighted fixtures in Git.
- Require generated/rescaled variants to store a complete stat block plus parent/diff rationale.
- Validate declared challenge/XP against edition-specific monster-building guidance where available; otherwise mark it provisional for explicit DM review.

### P8-02 — Party generation and playstyle snapshots

**Work**

- Pin character-sheet versions, party level/composition, rules profile, and generation assumptions.
- Add DM-approved playstyle inputs: optimization/tactical skill, risk/lethality preference, desired duration, rest cadence, strengths/weaknesses, favored/avoided mechanics, and accessibility needs.
- Allow one-off current-resource overrides without creating live combat state.
- Make permanent inferred playstyle changes reviewable rather than automatic.

### P8-03 — Edition-aware deterministic difficulty evaluator

**Work**

- Implement the selected official encounter budget/threshold calculation from cited rules/profile data as deterministic, side-effect-free Workbench mechanics with no model/provider dependency.
- Report official baseline separately from playstyle/party-adjusted recommendation.
- Validate creature quantities, multipliers/assumptions, generated-variant challenge estimates, and scaling changes.
- Use golden arithmetic fixtures and boundary/property tests.
- Do not let an LLM mark unsupported arithmetic as valid.

### P8-04 — Typed encounter package schemas

**Work**

Define common fields plus type-specific schemas for:

- combat;
- social;
- exploration/skill challenge;
- puzzle;
- trap;
- environmental hazard;
- mixed encounters.

Include stakes/objectives, dungeon room/zone IDs, complete participants, triggers, positions/waves, terrain interactions, tactics, checks/DCs, clues/hints/solutions/counterplay, outcomes, rewards/consequences, scaling variants, citations, and DM/player-safe content.

Define a strict versioned `EncounterGenerationContext` carried by `GenerationContextEnvelope`. It contains pinned party mechanics/playstyle, rules assumptions, authorized creature candidates, difficulty/experience targets, dungeon room geometry, pacing/resource pressure, and selected lore. It is not a subclass or null-filled variant of `DungeonGenerationContext`.

### P8-05 — Combat composition, map fit, and tactics

**Work**

- Select authorized creatures/variants that satisfy theme, difficulty target, and party inputs.
- Validate creature footprint/movement/range against room geometry, corridors, cover, chokepoints, and objective space.
- Place starting anchors/waves deterministically within allowed zones.
- Generate tactics, morale, surrender/retreat, reinforcement triggers, and non-kill resolutions.
- Produce easier/harder variants by changing composition/objectives/terrain/tactics with recalculated metrics—not merely adding HP.

### P8-06 — Noncombat, trap, hazard, and puzzle validators

**Work**

- Social encounters require actor goals, leverage, escalation, and multiple resolutions.
- Exploration/skill challenges require obstacles, approaches, consequences, and anti-single-roll structure where appropriate.
- Traps/hazards require detection, trigger, effect, counterplay, disable/bypass, and consequences.
- Puzzles require an explicit solution model, clue path, hint ladder, alternate reasonable handling, failure behavior, and reset/recovery.
- Player exports omit solutions, hidden DCs, and DM-only triggers unless explicitly published.

### P8-07 — Constrained LLM encounter/custom-creature tools

**Work**

- Compile party, playstyle, dungeon geometry, selected campaign lore, rules, and authorized creature candidates into `GenerationContextEnvelope<EncounterGenerationContext>` and pin its version/hash/source links.
- Add tools to propose/scale/validate encounters and full custom creature variants through an explicit pinned encounter task profile and bounded `pi-ai` gateway loop.
- Keep deterministic budget/map-fit/stat-block validators authoritative.
- Record citations, model outputs, diagnostics, and repair lineage.
- Ensure generated encounters remain preparation artifacts, never canonical events.

### P8-08 — Dungeon-wide population and pacing

**Work**

- Assign encounter slots across rooms/floors while considering variety, difficulty curve, expected attrition, rest opportunities, clues/keys, factions, treasure, and optional/bypass routes.
- Avoid treating every room as isolated or requiring combat.
- Link encounters to stable dungeon room/zone/marker IDs.
- Allow regeneration/scaling of one encounter without rewriting the dungeon.

### P8-09 — Encounter review, export, and eval gate

**Work**

- Add CLI/API generation, inspect, validate, compare, scale, export, and approve operations.
- Render complete DM packets and player-safe handouts/package components.
- Test arithmetic, stat completeness, room fit, puzzle completeness, secrecy, artifact lineage, and reproducibility.
- Track DM acceptance/edit rate by encounter type and difficulty target.
- Measure whether deterministic difficulty/stat/map-fit/type validators form a stable independently reusable boundary. At the phase gate, record a retain-in-Workbench or extract-`encounter-mechanics` decision; do not create an `encounter-engine` package by default.

Example flow:

```text
dm encounter generate --dungeon <id> --party main --difficulty hard
dm encounter validate <version-id>
dm encounter scale <version-id> --difficulty deadly
dm encounter export <version-id> --include-map
dm prep approve <version-id>
```

**Phase gate P8**

- Combat packages include complete stat blocks, source/variant lineage, deterministic baseline/adjusted difficulty, map-fit validation, tactics, objectives, and recalculated scaling options.
- Noncombat/puzzle/trap/hazard packages satisfy their type-specific completeness validators.
- Dungeon-wide population demonstrates varied pacing and preserves stable room links.
- Player outputs reveal no DM-only solution, hidden trigger, or secret map data.
- Artifact approval/usage does not alter campaign canon.
- The encounter workflow uses its own narrow context payload. Any package extraction is supported by measured cohesion/reuse and is limited to deterministic mechanics rather than assumed for the whole workflow.

---

## P9 — Session-Close Extraction and Review

### Goal

Turn prose session notes into an evidence-linked draft change set while preserving full DM control.

### P9-01 — Extraction runs and stage contracts

**Work**

- Link/create the session provenance record and its note/summary document revisions.
- Add extraction-run records linked to session, note revision, base campaign revision, any used dungeon/encounter artifact versions, gateway/package/task-profile/tool-schema/instruction versions, and multiple model/tool interactions.
- Define versioned structured outputs and stable change-set-local IDs.
- Make retry/idempotency behavior explicit.
- Never insert placeholder canonical rows during extraction.

### P9-02 — Entity and source-span resolution

**Work**

- Extract mentions with exact note spans.
- Resolve confident aliases, surface ambiguous candidates, and propose new entities.
- Carry stable candidate IDs through all later stages.
- Require review for merges/new aliases with collisions.

### P9-03 — Event/participant extraction

**Work**

- Extract occurred events separately from plans, hypotheticals, recaps, and in-world allegations.
- Add participants, roles, location, and approximate/relative anchors.
- Link every explicit item to source evidence.
- Group event and dependent consequences for review.

### P9-04 — State, perspective, temporal, and thread extraction

**Work**

Extract candidate:

- propositions and reality assertions;
- status/location/relationship changes;
- knowledge, belief, suspicion, claims, and reveals;
- quests/unresolved-thread changes;
- temporal relations;
- retcons/supersessions/retractions;
- character/item changes only when supported by notes/profile sources;
- rooms/encounters reached, revealed, altered, bypassed, resolved, or left active, without assuming the prepared outcome occurred.

Use several bounded structured calls under pinned extraction task profiles only where evals show one call is insufficient; do not create named autonomous agents or require `pi-agent-core`.

### P9-05 — Conflict and continuity analysis

**Work**

- Run deterministic validation first.
- Add a model-assisted reviewer only for semantic warnings that deterministic rules cannot express.
- Detect likely dead-character appearances, impossible location overlap, knowledge leakage, stale functional state, and source authority confusion.
- Treat warnings as review aids, not automatic rejection/canon.

### P9-06 — Grouped review ergonomics

**Work**

- Implement the primary grouped review in the first-party web UI while preserving equivalent CLI/API services.
- Show session source excerpt, event group, before/after state, dependencies, explicit/inferred labels, and warnings.
- Support accept/edit/reject at group and item levels.
- Revalidate after edits.
- Keep rejected content available in the source/run history.
- Measure DM edits/rejections to improve extraction precision.

### P9-07 — End-to-end close-session command

Implement:

```text
dm close-session <notes.md>
dm review <change-set-id>
dm commit <change-set-id>
dm history
```

Closing a session must not change any canonical answer before commit.

**Phase gate P9**

- A synthetic session note produces a reviewable, cited change set.
- No proposal becomes canonical before explicit commit.
- Approved changes update state atomically and produce a readable log summary.
- Rejected changes do not pollute canonical queries.
- Re-running the same extraction configuration does not duplicate the run/change set.
- Prepared dungeon/encounter usage informs extraction but never pre-populates canonical outcomes.

---

## P10 — Security, Operations, Deployment, and Release Gate

### Goal

Make the Python domain service, private Node model gateway, PostgreSQL store, and thin web UI dependable on the intended Proxmox deployment.

### P10-01 — Single-DM authentication and centralized policy enforcement audit

**Work**

- Audit the P0 single-DM credential enforcement across every non-health route and fail deployment readiness if it is unset.
- Bind/route the authenticated Python web/API service according to the home-network policy; prove the Node gateway is reachable only from the Python service/private container network.
- Enforce centralized campaign/visibility/source/model-task policy in all search and generation paths.
- Keep labels ready for future principals without implementing player accounts/RLS yet.

### P10-02 — Adversarial and leakage tests

**Work**

- Add prompt-injection source fixtures.
- Test path traversal, oversized/malformed input, wrong campaign, wrong authority, wrong rules edition, inaccessible snippets/citations/counts, player-map/handout secret leakage, malicious generation specs, wrong/unknown context payload kinds or cross-domain fields, asset-store escapes, attachment-ID/path abuse, model attempts to broaden scope/approve/commit, and OAuth/token leakage across browser/Python/log/error boundaries.
- Treat any secret/cross-campaign leakage as release blocking.

### P10-03 — Backup, restore, and rebuild

**Work**

- Document application-consistent PostgreSQL backup plus source and approved generated-asset backup; keep gateway OAuth credentials outside ordinary campaign backups and document safe re-login or separately encrypted secret recovery.
- Add restore drill instructions.
- Prove document/corpus citations and artifact lineage survive restore.
- Prove lexical/vector projections and rebuildable rendered assets can be rebuilt from source/spec revisions and pinned generator/renderer metadata.
- Do not rely solely on a Proxmox snapshot.

### P10-04 — Container image and Proxmox deployment

**Work**

- Add pinned non-root Python Workbench and Node model-gateway images; the Workbench image installs the locked in-process `dm_dungeon` workspace package and does not expose a separate dungeon service.
- Add production Compose/environment examples without fixed secrets; expose only the authenticated Python application, keep gateway ingress on a private internal network with no published port, and give only the gateway a separate un-published egress network for provider OAuth/model HTTPS. Provide an idempotent local bootstrap that generates and persists distinct missing database/API/session/internal-gateway secrets without generating provider credentials.
- Add migration/startup procedure, health checks, resource limits, and separate database/source/content-addressed-asset/scratch-volume guidance. Default source storage to empty managed volumes with no host-path prerequisite, plus an explicit symlink-rejecting atomic source import command; copying source files remains separate from immutable Library ingestion.
- Prefer a VM for Docker Compose unless the chosen LXC deployment explicitly accepts nesting/security tradeoffs.

### P10-05 — Durable jobs and observability

**Work**

- Ensure ingestion/embedding/dungeon/encounter/render/export/extraction runs can be diagnosed/retried after restart.
- Add bounded job leasing only if synchronous commands are no longer adequate; keep PostgreSQL as the first durable mechanism.
- Add safe metrics/logs for latency, error rate, `pi-ai` model usage/cost where available, embedding runtime/cost, queue/run state, and active task-profile/schema/generator/index versions.

### P10-06 — Full eval and operational acceptance

Run the complete frozen suites and a restore/rebuild drill. Record baseline:

- answer correctness and citation precision;
- per-task model/profile capability, schema/tool success, blinded DM preference, fallback behavior, and effort/cost/latency;
- retrieval source recall plus embedding-profile quality/memory/index/query latency against lexical-only;
- extraction precision/recall and DM review burden;
- dungeon package dependency isolation, model-independent Studio operation, first-pass validity, repair count, targeted-regeneration preservation, context relevance, and render/export correctness;
- encounter arithmetic/stat completeness/map fit and DM acceptance by type/difficulty;
- leakage failures, including player map/puzzle packages (must be zero);
- mid-session query latency;
- model/embedding cost;
- backup/restore duration.

**Release gate P10**

The first release satisfies all milestone acceptance criteria in the architecture document and has a tested rollback/restore path.

---

## Later Backlog (Do Not Pull Forward Casually)

- `B-01`: Markdown/JSONL revision-log exporter enhancements and optional Git commits.
- `B-02`: Player accounts, explicit audience management, and PostgreSQL RLS defense in depth.
- `B-03`: Player-safe/NPC-scoped context and direct interaction.
- `B-04`: Custom calendar adapters and interval algebra expansion.
- `B-05`: Persistent scenes and live transcript ingestion.
- `B-06`: Live character/combat resources.
- `B-07`: Automated Markdown view generation with reviewed diffs.
- `B-08`: Alternate timeline inheritance and branch semantics.
- `B-09`: Local chat-LLM serving; a small local embedding adapter is evaluated in P2.
- `B-10`: Dedicated queue/vector/graph infrastructure, only after measurements justify it.
- `B-11`: Polished illustrated dungeon textures/image-model enhancement.
- `B-12`: Direct Roll20 upload, dynamic-lighting, walls/doors, and token automation where supported.
- `B-13`: Optional local/private MCP adapter.
- `B-14`: Optional Pi extension or another external agent-host adapter.
- `B-15`: Regional/world map generation.
- `B-16`: Adopt `@earendil-works/pi-agent-core` only if open-ended multi-turn/steering needs justify moving the bounded loop into the gateway.
- `B-17`: Extract a standalone `encounter-mechanics` package only if the P8 decision records a stable reusable deterministic boundary; never extract the full encounter workflow merely for symmetry with dungeons.

## Test and Fixture Policy

### Test layers

1. **Unit/property tests:** parsers, hashing, scope resolution, strict task-specific context schemas/hashes, validation, rank fusion, diff logic, topology/gating, geometry/pathfinding, print tiling/ink budgets, encounter arithmetic, secrecy transforms, model/task-profile routing, `pi-ai` faux-provider contracts, and fake embedding providers. Add an import/dependency test proving `dm_dungeon` cannot depend on Workbench, database, web, retrieval, or provider modules.
2. **Database integration tests:** migrations, constraints, transaction failure, temporal queries, FTS/vector filtering, revision/artifact history, and asset metadata.
3. **API/CLI/web/gateway contract tests:** shared service behavior, platform `AssetStore` reuse, context-envelope/domain-payload contracts, OAuth-event/token boundaries, normalized model streams, image attachments, cancellation/reconnect, and safe error rendering.
4. **Golden/snapshot evals:** pinned corpus/campaign/artifact inputs with expected answers/source IDs, dungeon packages, SVG exports, and encounter metrics.
5. **Security/adversarial tests:** prompt injection, source authority, visibility, cross-campaign, path, and model tool boundaries.
6. **Operational tests:** idempotent retries, backup/restore, and index rebuilds.

### Fixture rules

- Use a small synthetic campaign with deliberately conflicting beliefs, plans, retcons, aliases, split scenes, and important items.
- Use invented rules text rather than copyrighted sourcebook excerpts.
- Use synthetic character sheets with no real player data.
- Use invented creature stat blocks, fixed-seed dungeon briefs/packages, and combat/noncombat/puzzle fixtures.
- Keep separate dungeon and encounter context fixtures with only their relevant fields; tests must not normalize them into one universal optional-field payload.
- Give fixture entities/rooms/artifacts stable IDs only inside fixture loaders; tests should not depend on production UUID values.
- Freeze clock/provider behavior where reproducibility matters.

## Migration Discipline

- Never edit an applied/shared migration merely to make a later schema change easier; create a new migration.
- Migration names should include the task ID where practical.
- Every migration receives an upgrade test; reversible migrations receive downgrade coverage.
- Data backfills are idempotent and resumable.
- Canonical-history migrations preserve old revision semantics or include an explicit, reviewed conversion report.
- Do not put model calls in a database migration.

A likely migration sequence is:

```text
0001_p0_foundation
0002_p1_documents_and_snapshots
0003_p2_embeddings_and_retrieval_runs
0004_p3_campaign_revisions_and_change_sets
0005_p4_rules_model_task_profiles_and_runs
0006_p5_knowledge_core
0007_p6_character_and_item_profiles
0008_p7_prep_artifacts_dungeons_and_assets
0009_p8_creatures_parties_and_encounters
0010_p9_extraction_runs
```

The exact grouping may change, but dependency order should not.

## Credit-Aware Stop and Handoff Procedure

When remaining context/credits look low, do not start another task. Leave the repository in a state another agent can understand in minutes.

1. Stop at the nearest safe transaction/migration boundary.
2. Run the task's focused tests plus `git diff --check`.
3. Run `git status --short --branch`.
4. Update `PROJECT_STATUS.md` with the exact task state, files, migrations, tests, errors, assumptions, and next first action.
5. If work is incomplete, mark it **WIP** and say whether the current code is runnable/safe.
6. If commits are expected, use the task ID in the subject; otherwise record a suggested subject.
7. Do not leave generated credentials, real campaign data, temporary provider output, or unexplained database state.

A good final handoff sentence is concrete:

> Next: P1-03. Start by adding `MarkdownChunker` tests for heading paths and exact offsets in `tests/unit/documents/test_chunker.py`; P1-01/P1-02 migrations and ingestion tests pass with `uv run pytest tests/integration/documents`.

A bad handoff is:

> Continue ingestion work.
