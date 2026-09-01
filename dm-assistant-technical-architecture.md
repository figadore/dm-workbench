# DM Assistant Harness — Technical Architecture and Data Model

## Overview

The proposed system is a self-hosted DM-assistant harness intended to run on a home Proxmox environment.

The initial architecture should remain intentionally small:

- one Python DM Workbench domain/application service organized as a modular monolith;
- one independently packaged pure Python dungeon engine loaded in that same process;
- one narrow private Node model-gateway process using `@earendil-works/pi-ai`;
- one PostgreSQL database;
- pgvector in the same PostgreSQL instance;
- versioned Markdown campaign material;
- versioned Markdown rules and authorized creature corpora;
- structured dungeon/encounter generation and deterministic renderers;
- a platform-owned content-addressed writable volume for attachments and generated assets;
- a first-party thin web UI plus a shared administrative/automation CLI;
- a human approval step for every canonical state change.

Use process boundaries only where runtime or credential isolation requires them, package boundaries for deterministic kernels with a coherent contract, and feature-module boundaries for the rest of the Workbench. The dungeon engine is a package boundary, not a network service: it has no database, web, retrieval, campaign-knowledge, or model-runtime dependency. Encounter design should begin as a Workbench feature with deterministic mechanics isolated internally; extract a narrower package such as `encounter-mechanics` only if implementation and reuse demonstrate a stable boundary. Do not assume that an entire encounter workflow belongs in a reusable engine.

The system should avoid prematurely introducing agent frameworks, graph databases, dedicated vector databases, queues, plugin frameworks, or domain microservices. The Node model gateway is a deliberate runtime-adapter exception because the selected `pi-ai` package is TypeScript/Node; it owns no campaign state or domain rules.

The main architectural principle is:

> PostgreSQL stores approved campaign knowledge, generation specifications, and history; immutable source revisions preserve narrative and evidence; deterministic code turns constrained dungeon/encounter specifications into validated assets; retrieval compiles only the relevant, authorized subset into model context.

This is a good fit for the product goals. PostgreSQL can express the required graph-shaped, temporal, and provenance-aware data at campaign scale, while Markdown prevents formalization from becoming a prerequisite for remembering the story. The main risks are semantic and correctness-related rather than scale-related: confusing a proposal with canon, a prepared encounter with an event that occurred, a belief with reality, or model-invented geometry/rules arithmetic with validated output. The invariants below address those risks.

## Goal Fit and Architectural Invariants

| Product goal | Architectural mechanism |
| --- | --- |
| Human DM remains authoritative | Models create change sets only; a human-only commit operation creates a new canonical campaign revision. |
| Low clerical overhead | Prose-first ingestion, entity resolution, extraction, grouped review, and reusable predicate suggestions. |
| Narrative richness | Immutable document revisions plus lexical and semantic retrieval; unstructured details do not have to become assertions. |
| Coherence over time | Events, temporal propositions, perspective-aware assertions, explicit `as_of` queries, and deterministic validation. |
| Provenance | Many-to-many evidence links point to exact source revisions and spans; answers cite those sources. |
| Rules accuracy | Rules/creature corpora, editions, campaign rules profiles, and house-rule precedence remain explicit. |
| Practical dungeon generation | A DM or LLM authors constrained briefs/topology; the pure dungeon package owns deterministic layout, validation, rendering, and exact geometry. |
| Party-aware encounters | Complete creature profiles, pinned party snapshots, edition-aware calculators, and typed combat/noncombat encounter packages. |
| Print and virtual-tabletop use | One renderer-neutral map package produces low-ink, exact-scale tiled PDFs plus grid-on/gridless PNG and Roll20 metadata; SVG is the deterministic vector renderer. |
| Future live/player use | A compact context compiler and hard audience filters expose the same core safely through different interfaces. |

The following are non-negotiable invariants:

1. **The DM is the authority.** Accepted structured records are the machine-queryable canonical projection. Markdown revisions remain the lossless narrative record and evidence. If they disagree, the system surfaces the conflict for the DM; it does not silently choose or rewrite either side.
2. **Proposal storage is separate from canonical storage.** No model-facing operation can directly create, edit, supersede, or retract canon.
3. **Source material is classified.** Canon notes, raw session notes, plans, imported adventures, player handouts, official rules, and house rules are not interchangeable retrieval sources.
4. **Perspective is part of the model.** Reality, belief, knowledge, suspicion, claims, and official records are not flattened into one edge.
5. **Every state query has a scope.** At minimum this is campaign, canonical revision, active corpus snapshot/index generation, timeline, story-time anchor, audience, and rules profile where applicable. Defaults may be supplied by the active campaign/scene, but they must be inspectable.
6. **Authorization happens before retrieval.** Prompt instructions are not a security boundary. Inaccessible chunks and facts must be excluded in SQL/query code before ranking or model invocation.
7. **The system may abstain.** Missing, disputed, weakly sourced, or temporally incomparable information should produce an explicit uncertainty rather than an invented answer.
8. **Every commit is explainable.** Each canonical revision has a concise human-readable summary plus the complete accepted-item/evidence audit trail.
9. **The LLM expresses intent; code owns mechanics.** Models may choose themes, room roles, topology constraints, encounter goals, and tactics. They do not author raw SVG, pixel geometry, pathfinding, export packages, or trusted difficulty arithmetic.
10. **Preparation is not canon.** Approving a dungeon or encounter as ready for play does not assert that its planned inhabitants/events occurred. Played outcomes enter canon only through the normal change-set workflow.
11. **Generation is reproducible and inspectable.** Every artifact version pins its input scope, seed, schemas, compiler/generator/renderer versions, rules profile, party snapshot, model/tool runs, validation report, and parent lineage. Application/database aggregate IDs may use UUID4, but deterministic package generation must never call `uuid4()`. For initial V2 dungeon generation, semantic component IDs derive only from compiler version plus canonical local semantic identity—not layout seed, prose, or array position—while seed-created auxiliary layout IDs may additionally use the pinned seed.
12. **Context contracts remain task-specific.** A small common generation-context envelope carries scope, provenance, visibility, citations, and a payload hash; dungeon, encounter, session-preparation, and future scene contexts use separate versioned payload schemas rather than one universal optional-field object.
13. **Package separation does not imply service separation.** The pure dungeon package runs in the Python Workbench process and cannot import Workbench persistence, HTTP, retrieval, or model orchestration. Encounter package extraction remains a measured later decision.

## Deployment

A reasonable first deployment is a small Debian LXC or VM under Proxmox.

Example starting resources:

- 2 vCPU;
- 4 GB RAM;
- 20–30 GB disk;
- Docker Compose or an equivalent container deployment.

Initial services:

```text
dm-workbench           # Python/FastAPI domain app, in-process dungeon package, CLI, and web UI
model-gateway           # private Node process using pinned @earendil-works/pi-ai
postgres + pgvector
```

The contributor inner loop and installed topology deliberately differ without
changing application behavior. Contributors run Python/Node natively with only
PostgreSQL in Compose for fast reloads and focused AI-assisted work. Local
full-stack validation and Proxmox installation use the same Compose topology:
separate non-root Workbench, gateway, and PostgreSQL containers; only the
authenticated Workbench is host-published; the gateway uses private service DNS
and a dedicated writable credential volume. Environment-specific URL and
mount-path configuration is the only runtime distinction; the Python/gateway
credential and authorization boundaries do not change.

The 2-vCPU/4-GB baseline assumes hosted chat inference and lexical retrieval. A small local CPU embedding model may still fit, but P2 must benchmark model/runtime memory and batch behavior; plan roughly 6–8 GB if the selected embedding runtime must stay resident beside PostgreSQL and both application processes. Local chat-model serving requires separate capacity planning.

The PostgreSQL data volume should live on reliable local/block storage rather than a network filesystem where possible. Full-stack Compose defaults campaign and rules sources to separate empty managed volumes mounted read-only into Workbench, so standalone first run has no host-path prerequisite. An explicit host-side import operation rejects symlinks and atomically replaces a managed volume's current tree; immutable Library ingestion remains a separate deliberate application operation, so copying files never makes them canonical or silently indexed. Native development may configure absolute source roots directly. A separate platform-owned writable asset volume stores content-addressed prompt attachments and generated SVG/PNG/PDF/map-package files; temporary upload/generation files use another scratch path and are never mistaken for approved assets.

A VM is the simplest place to run Docker Compose. An LXC is also reasonable if the application runs directly under systemd or the host's container-nesting/security tradeoffs are understood; the database should not require a privileged guest merely for convenience.

Operational requirements for the first useful deployment are modest but important:

- schema migrations run explicitly and are backed up before destructive changes;
- PostgreSQL, immutable source snapshots, and non-rebuildable/approved generated assets are backed up together using an application-consistent database backup; a Proxmox snapshot alone is not the backup strategy;
- restoration is tested, not merely configured;
- database/embedding API credentials use secrets/environment configuration; chat-provider API/OAuth credentials live only in a dedicated gateway credential store with restrictive permissions and never in campaign documents, browser storage, ordinary logs, or normal campaign backups;
- ingestion, embedding, model, generation, and extraction runs have durable database records so a process restart can be diagnosed or retried without requiring a message broker;
- derived indexes/embeddings can be rebuilt from document revisions, and rendered outputs can be rebuilt from pinned preparation specifications/generator versions.

### Runtime Configuration, Authentication, and Logs

The Python process loads one immutable typed `DM_*` settings object. PostgreSQL URL, absolute allowlisted source roots, and a 32-or-more-character single-DM API token are required; model-gateway enablement/URL and embedding runtime/provider policy are separate fields so Codex/chat credentials can never be mistaken for embedding configuration. Startup configuration errors expose invalid field names, not supplied values. `.env.example` contains placeholders only.

The initial API security boundary is default-deny middleware: every path, including documentation/schema routes, requires an exact Bearer token except the explicit `/health/live` and `/health/ready` allowlist added by P0-04. Comparison is constant-time and all failures use one generic response. Later browser sessions must enter through this same centralized policy rather than creating unprotected feature routers.

Application logs are one-object-per-line JSON and carry a validated request ID plus ingestion, embedding, model, generation-run, change-set, and campaign-revision IDs when bound. They log route templates rather than attacker-controlled paths and never request/response bodies, prompts, source/context text, authorization values, or provider payloads. Recursive key redaction, configured-secret replacement, and credential-URL scrubbing happen in the formatter. Expected domain errors expose the same stable safe code/message through API and CLI adapters; unexpected exception text/stacks are not public responses or ordinary structured-log fields.

P0-04 makes only exact health routes public. `/health/live` performs no dependency work. `/health/ready` checks PostgreSQL major version, exact pgvector version, and exact Alembic head but publishes only component states—not versions, reason codes, URLs, SQL, or exceptions. The local `dm doctor` reuses the same readiness report and may show safe component versions/reason categories; it never shows configuration values. The repository's container gate creates only a disposable `*_test` database, runs migration round trips and all quality gates, and removes its volume/network on exit.

P7-11 adds a signed single-DM browser session without putting the API token in the cookie. A separate 32+ character session secret signs short-lived HMAC-SHA256 claims containing only principal, expiry, and random CSRF token; API and session secrets must differ. Browser writes require a constant-time CSRF match, while authenticated Bearer API writes remain suitable for CLI clients. Cookies are HttpOnly/SameSite-strict (and Secure in production); templates escape data and responses apply a restrictive no-script CSP. Only login and exact health paths bypass authentication.

## Proposed Technology Stack

### Application

Python with FastAPI is a good initial choice.

The application should be a modular monolith with clear internal boundaries for:

- source ingestion and revisioning;
- chunking, lexical indexing, and embeddings;
- entity resolution and ontology management;
- canonical knowledge and temporal queries;
- retrieval and context compilation;
- preparation-artifact and generation-run management;
- Dungeon Studio orchestration around the independently packaged graph/layout/validation/render/export kernel;
- creature profiles, party snapshots, and combat/noncombat encounter generation;
- model task profiles, gateway contracts, bounded tool orchestration, and run provenance;
- first-party prompt/review/artifact web workflows;
- session-close extraction;
- validation, review, and atomic commit;
- authorization, audit, and evaluation logging.

These boundaries are code modules and transaction boundaries, not domain microservices. The CLI and first-party web UI call the same Python application services. The private Node gateway is limited to provider authentication, model catalogs/capabilities, normalized streaming/tool-call transport, and usage metadata.

The model should interact through purpose-built, schema-validated application tools rather than arbitrary SQL or shell access to internals. Canonical model-facing writes target a draft change set; preparation writes target a draft artifact version. Only an authenticated human workflow may approve an artifact or commit canon.

### Workbench Domains and Dependency Direction

The user experiences one DM Workbench, but its feature areas have distinct data and approval semantics:

- **Library:** immutable campaign/rules/creature sources, ingestion, retrieval, and citations;
- **Chronicle:** canonical revisions, entities, events, temporal/perspective state, and provenance;
- **Profiles:** character, item, creature, party, and playstyle snapshots;
- **Preparation:** generic artifact versions, generation runs, assets, and the `approved_for_play` lifecycle;
- **Dungeon Studio:** context selection, model/DM-authored intent, engine invocation, preview, regeneration, export, and preparation review;
- **Encounter Studio:** composition workflow plus deterministic rules arithmetic, package validation, and dungeon-fit checks;
- **Session Desk:** notes, extraction, grouped review, and change-set submission to the Chronicle;
- **Assistant:** cited campaign/rules questions and other bounded model tasks.

The shell may share navigation and visual components, but preparation approval and canonical review use separate routes, action names, and confirmation language. A generic ambiguous “Approve” action must not blur `approved_for_play` with `commit_change_set`.

A read-only context compiler is the integration seam between Library/Chronicle/Profiles and task workflows. It emits immutable task-specific packets; it is not another authority or a database abstraction exposed to engines. Application orchestrators may call several modules inside one transaction or durable run, but modules exchange versioned contracts and opaque IDs rather than each other's ORM objects.

The dependency direction is:

```text
Library + Chronicle + Profiles
              |
              v
      task-specific context compiler
              |
              v
Dungeon/Encounter/Assistant orchestration
        |                 |
        v                 v
private model gateway   deterministic mechanics
        \                 /
         v               v
       preparation versions / answers / draft change sets
```

The separately packaged dungeon kernel owns its brief/topology/layout/package schemas, topology and geometry algorithms, diagnostics, renderers, and exporters. The Workbench owns context compilation, model calls, repositories, artifact lifecycle, and human review. Dependency tests should fail if the dungeon package imports FastAPI, SQLAlchemy, Workbench modules, provider clients, or campaign repositories.

The provider-independent P7-11 `DungeonStudioService` is the first concrete orchestrator across those boundaries. It accepts a strict `LayoutRequest`, records a pin-complete run, invokes generation plus topology/geometry validation, produces DM/player SVG/PNG previews, and persists a `dungeon-studio-v1` specification containing both exact request and resulting `DungeonPackage`. Regeneration reconstructs that request and copies only explicitly selected exact lock components; PostgreSQL parent lineage remains authoritative even though the pure package has no repository concept. PDF/Roll20 export, asset download, comparison, and approval all call the same service from JSON API, CLI, and server-rendered routes. No model gateway or source retrieval is consulted.

Encounter composition is less clearly separable. Initially, keep its orchestration and contracts in the Workbench while isolating deterministic difficulty, stat-block, puzzle-completeness, and map-fit functions. After P8 evals reveal the actual seam, either retain that module or extract only a cohesive `encounter-mechanics` package. Do not pre-create an empty `encounter-engine` package.

### Database

PostgreSQL should initially serve several roles:

- relational storage;
- event/history storage;
- temporal assertions;
- graph-like entity relationships;
- JSONB qualifiers;
- full-text search;
- vector search through pgvector.

Generated artifact specifications, lineage, validation reports, and asset metadata also live in PostgreSQL. Large rendered binaries live on the content-addressed asset volume rather than being duplicated in hot relational tables.

This avoids maintaining separate relational and vector systems initially.

P0-03 pins `pgvector/pgvector:0.8.1-pg16-bookworm` and binds its development port only to loopback. The Workbench uses SQLAlchemy 2 synchronous sessions over psycopg 3 (`postgresql+psycopg`), with hidden SQL parameters, pre-ping, and an explicit unit-of-work context: success commits once, every exception rolls back, and the session always closes. Connection probes map driver failures to one secret-safe domain error.

Alembic reads only validated `DM_DATABASE_URL`; no URL or credential is stored in `alembic.ini`. Its ordered `alembic_version` table is the schema-version authority, so a duplicate application schema-version table is not added. The foundation revision installs `vector` and creates only the minimal `campaign` aggregate. Integration migrations are destructive only against an explicitly configured database whose name ends in `_test`, and the gate proves upgrade/downgrade/upgrade, model/migration drift, constraints, extension version, and transaction behavior.

### Markdown

Markdown remains the human-facing representation for:

- campaign notes;
- NPC prose;
- locations;
- factions;
- lore;
- adventure material;
- session summaries;
- extracted D&D rules.

Obsidian can remain the editing interface, but the architecture should not depend on Obsidian-specific behavior.

### Content-Addressed Attachment and Generated-Asset Storage

The initial blob store can be a local mounted directory addressed by SHA-256 content hash. It is a platform-owned `AssetStore` port rather than a facility owned by prompt upload or dungeon code; the first consumer implements the narrow interface and later consumers reuse it. PostgreSQL records media type, byte size, hash, logical role, storage locator, and either input-attachment/run ownership or renderer/export/artifact-version metadata. Writes use temporary files plus atomic rename; duplicate content is reused. Prompt uploads enforce MIME/size limits and retention, are retrieved only by opaque attachment ID, and never grant the model gateway arbitrary path access.

The canonical dungeon/map specification is the source for rebuildable outputs. SVG/PNG/PDF exports can be regenerated when renderer versions remain available, but approved exports should still be retained/backed up when exact visual reproducibility matters. An S3-compatible object store can replace the directory later through a narrow interface without changing artifact identity.

Content-addressed blob identity is deliberately not a user-facing filename. Dungeon Studio projects immutable artifact-version role links into a purpose-oriented output catalog containing floor, audience, format, safe display label, and a title/version/floor/audience-derived filename. Images, trusted generated SVG, text, JSON, and PDF may have explicit safe Open actions; ZIP remains attachment-only and every format has a separate explicit Download action. Manifests/hashes remain inspectable under technical lineage rather than appearing as primary `role #ordinal` output. The route must resolve the requested artifact-version link under campaign authorization instead of guessing presentation from a globally deduplicated blob UUID.

The P7-01 local adapter streams to a configurable scratch root on the same filesystem (the Compose deployment uses sibling asset/scratch directories inside its one asset volume, not separate mounts), hashes and `fsync`s the complete temporary file, then publishes through an atomic no-overwrite hard link at `sha256/<prefix>/<hash>`. An existing destination is byte-size/hash verified rather than replaced. Reads accept only a validated hash-derived locator and reverify regular-file type, size, and hash. PostgreSQL blob metadata is globally deduplicated by SHA-256 while ownership/presentation remains in separate artifact-version role rows.

### Vector Retrieval and Embedding Runtime

Embeddings are used for fuzzy semantic retrieval over:

- session notes;
- lore;
- descriptions;
- rule chunks;
- dialogue/history where retained;
- other prose that is not worth fully structuring.

Vector retrieval should not be treated as canonical truth. Embeddings live in a separate versioned table keyed by chunk, embedding provider/model, dimensions, normalization/preprocessing version, and exact source-content hash. This permits a model migration or re-embedding run without overwriting the currently serving index or changing source identity.

`@earendil-works/pi-ai` is a chat/image-input and tool-calling model library; it does not provide an embedding API. The ChatGPT Codex subscription endpoint must not be treated as an embedding service. Embedding execution therefore remains a narrow Python-side adapter with its own model profile, batching, retries, resource/cost metadata, and credentials where applicable.

P1 remains lexical-only and useful with no model credential. In P2, evaluate a small local CPU/ONNX embedding runtime first because it keeps bulk campaign/rules text local and avoids a second paid provider. Do not lock a model name before retrieval evals and Proxmox memory/latency measurements. Preserve a hosted embedding adapter option for quality or operations needs; it uses a separate API key and retention policy, never the Codex OAuth credential.

Each serving corpus snapshot pins one active compatible embedding profile. Old/new profiles may coexist, but one pgvector index/partition must never mix dimensions. Query-embedding failure degrades to filtered lexical retrieval rather than making source access unavailable. Chat models receive only the bounded excerpts selected after hard filters and hybrid ranking, not the embedding vectors or bulk corpus.

### Lexical Retrieval

PostgreSQL full-text search or similar lexical retrieval should complement embeddings.

Hybrid retrieval is important because D&D queries include both:

- semantically vague recollections, such as "the wizard who cared about the obelisk";
- exact named terms, such as "Booming Blade" or "Sneak Attack."

### Model Gateway, OAuth, and Task Routing

The DM assistant is the agentic application. Its first-party web UI and CLI submit explicit task requests to Python application services; the Python harness resolves scope, compiles context, selects a versioned task profile, authorizes/executes tools, validates outputs, and persists durable run state.

A small private Node gateway uses a pinned release of **`@earendil-works/pi-ai`** as the model transport/authentication library:

```text
browser (prompt/image/review UI)       Typer CLI
                 \                       /
                  v                     v
        Python/FastAPI DM harness + bounded workflow code
                  |   ^
  normalized model|   |stream/tool-call events
        request   v   |
       private Node model gateway (@earendil-works/pi-ai)
                  |
                  +--> GitHub Copilot subscription OAuth
                  +--> ChatGPT Codex OAuth endpoint
                  +--> direct API-key providers
                  +--> optional local OpenAI-compatible model later
```

The initial subscription allowlist includes GitHub Copilot OAuth and OpenAI Codex OAuth; first-use setup presents compatible unauthenticated subscription providers rather than silently privileging one brand, then persists the task-specific selection. The linked Mintlify examples describe an older `@mariozechner/pi-ai` global OAuth API. The evaluated local package is the newer `@earendil-works/pi-ai` provider/`Models` API (0.84.1 at this decision); implementation must pin and lock the exact selected version and use provider-owned `Models.login()`/`stream*()` semantics rather than copying old `getOAuthApiKey()` examples. Upgrades are deliberate and run provider contract/eval tests. The package is MIT, but provider subscription terms and endpoint availability remain separate operational constraints and must be verified before relying on unattended use.

The gateway responsibilities are deliberately narrow:

- provider registration, model catalogs, and capability metadata;
- ChatGPT Plus/Pro Codex OAuth plus supported API-key/provider auth;
- secure serialized credential refresh/storage;
- normalized text/thinking/tool-call/image-input streams;
- provider-specific reasoning, context, transport, cancellation, and usage behavior;
- health/auth-status/model-list endpoints and a streaming request endpoint.

It owns no campaign documents, retrieval policy, canonical/preparation state, approval operation, or arbitrary filesystem access. Native operation binds to loopback. In Compose it has no published host port, accepts authenticated Workbench traffic on an internal transport network, and alone also joins an un-published egress bridge so provider OAuth/model HTTPS can reach the internet; PostgreSQL and Workbench remain on the internal network only. Python may reference content-addressed image attachments through a tightly scoped internal loader; the gateway never accepts arbitrary user/model paths.

OAuth credentials live in a dedicated gateway secret file/volume, separate from Pi's normal auth file and from PostgreSQL. The first web setup should prefer OpenAI's device-code flow for a headless Proxmox gateway; the UI displays verification events but never receives access/refresh tokens. Re-login is an operational recovery path, so ordinary campaign backup/restore does not depend on copying OAuth credentials. For local/full-stack setup, an idempotent host bootstrap creates an ignored mode-`0600` environment file and generates distinct missing database, API, session-signing, and Workbench-to-gateway secrets; it preserves existing values and never generates provider credentials. The internal gateway token is the shared bearer credential only for Python-to-gateway calls and is injected into both services by Compose.

Python sends a normalized request containing the resolved provider/model, supported effort level, context/messages, allowed tool schemas, output/token limits, run/session cache ID, and attachment references. Message contracts are a discriminated union of `user`, `assistant`, and `tool_result`, preserving tool call ID/name, error flag, bounded content, and provider-required opaque continuity signatures; malformed role/content combinations are rejected. The gateway returns normalized streaming events and final usage. Python validates every completed tool call against its own versioned schema and server-supplied scope, executes it through application services, records the result, and decides whether another bounded model turn is allowed. A task profile may request `pi-ai` JSON-schema constrained sampling only when the resolved provider advertises it and the exact schema translation is contract-tested; use `prefer` before `require`, retain authoritative Python validation, and fail explicitly rather than silently dropping a required mode.

Python owns cumulative monotonic deadline, turn, tool-invocation, and token budgets. Before every provider request it calculates the remaining budget and passes only that decreasing time limit to the gateway; missing provider usage is recorded as unknown, never zero-cost success. Task-specific output and cumulative token ceilings are set from fixed eval measurements rather than inheriting a provider's maximum. The active alpha dungeon submission is a one-shot structured workflow whose `submit_dungeon_plan` arguments are the `DungeonGenerationProposal` fields directly at the tool root—there is no redundant `proposal` envelope. Its one permitted repair starts a fresh request with the original authorized task/context, size-bounded prior arguments, and actionable static diagnostics. Before that repair, a conservative estimate over the complete canonical repair message and tool schema must leave at least one output token inside the measured remaining budget; the repair output cap is reduced by that estimate. Every completed structured response is then checked against both its pinned output ceiling and total measured request budget before schema validation or publication. An exceeded ceiling fails with body-free durable usage metadata and cannot publish a draft. A provider/request cap is not considered a hard cost control until provider-contract or live-canary evidence proves that the provider honors it; post-response rejection prevents publication but cannot undo already consumed provider usage, so a provider that reports more output than requested remains blocked from ordinary live rollout until that transport behavior is resolved or the budget policy is explicitly revised. The sole pre-retention exception is the frozen non-production `tier-a-live-canary-v1` prompt/seed: its dedicated CLI command may, after an explicit `--acknowledge-advisory-output-cap`, treat only the per-request output check as advisory for one stop-on-failure run. It still requests the pinned output cap, enforces the 12,000 measured cumulative publication ceiling and repair reservation, records the canary ID/policy in the attempt report and accepted model lineage, and cannot approve preparation or canon. It is forbidden in production and restricted to the known `openai-codex` transport; already-consumed overage remains an acknowledged operator risk. Repair must preserve the original requested dungeon and valid prior content; none of these bodies enter ordinary logs. Native assistant/tool-result continuation is reserved for workflows that actually execute iterative tools. No model-facing tool can approve an artifact or commit canon.

A versioned **model endpoint/profile** records runtime adapter, provider/model ID, observed capabilities/context limits, and availability metadata. A versioned **task profile** records task type, model profile, normalized effort (`fast`/`standard`/`deep`, mapped only to supported provider levels), context policy/budgets, allowed tools, output schema/token limit, fallback order, and prompt/instruction version. Each run pins the resolved snapshot and any per-run override. Model names such as Luna/Terra/Sol do not imply suitability; task-specific objective checks and blinded DM comparisons choose defaults.

`@earendil-works/pi-agent-core` is **not an initial dependency**. Its stateful agent loop, parallel tools, steering/follow-up queues, and event stream may become useful for a genuinely open-ended conversational mode. Initial ask, extraction, dungeon, and encounter workflows are bounded and easier to audit in Python; adopting agent-core now would split session/tool state across runtimes. Reassess it only when measured custom-loop complexity justifies it. If adopted, it runs inside the gateway as a replaceable loop engine, treats PostgreSQL/run records as authoritative, invokes only authenticated Python APIs, and still cannot approve or commit.

A Pi extension and a local/private MCP server remain optional external adapters over the Python API. Neither is the first-party UI, the internal browser transport, or a reason to expose the harness publicly.

## Core Data Model

The model should be closer to an extensible temporal property graph than a conventional application schema with one table per D&D concept.

The core primitives are:

- Campaign and canonical campaign revision
- Session and scene/story cursor
- Entity, alias, and mention
- Character-sheet, creature, and important-item profile snapshot
- Preparation artifact, artifact version, generation run, and generated asset
- Dungeon brief, topology graph, exact layout, and floor/layer package
- Party generation snapshot and combat/noncombat encounter package
- Predicate
- Proposition and perspective-aware assertion
- Event, participant, temporal anchor, and temporal relation
- Timeline
- Logical document, immutable document revision, document chunk, and corpus snapshot
- Evidence and derivation link
- Generation-context envelope with task-specific payload, model endpoint/profile, task profile, model run, and tool interaction
- Change set, change item, and ingestion run

Specialized campaign-memory concepts such as quests, secrets, unresolved threads, NPC profiles, and current location can initially be implemented as typed entities plus assertions. Dungeon geometry, complete stat blocks, and encounter packages are cohesive validated aggregates instead; forcing every grid cell or ability into ontology assertions would make generation and rendering harder without improving narrative queries.

Every campaign-owned row should carry or be transitively constrained to a `campaign_id`. Composite foreign keys or equivalent service-level guards must prevent cross-campaign references. The first release may expose only one campaign, but campaign isolation should be tested from the beginning. Rules documents may be global and selected through an explicit campaign rules profile.

A campaign record holds inspectable defaults, not hidden prompt state:

```text
campaign
--------
id UUID
name
head_campaign_revision_id NULL
active_campaign_corpus_snapshot_id NULL
default_timeline_id NULL
default_story_cursor_id NULL
default_rules_profile_id NULL
default_visibility_policy_id
metadata JSONB
```

The head pointer advances in the same transaction that commits a change set. Defaults can be overridden by an authorized request and the resolved scope is always included in query/audit records.

P7-10a.1 adds an inspectable single-DM Workbench selection without making preparation ownership nullable: exactly zero or one campaign row is marked active by a partial unique index. The first created campaign becomes active, and a first prompt with no campaigns lazily creates an empty `My Campaign` ownership root. `dm campaign use` switches the marker transactionally; explicit campaign IDs remain overrides and every run pins the resolved campaign. This active marker is a convenience scope default, not campaign canon and not permission for a model to choose another campaign.

The same slice stores a non-secret task-specific provider/model/effort selection in PostgreSQL. Code resolves it against the live private-gateway catalog, falls back through a versioned compatibility/capacity policy, and coordinates gateway-owned OAuth when needed. Access/refresh tokens remain only in the gateway credential store. Generated seeds and model-authored validated brief titles are defaults, while explicit values remain reproducibility overrides. These conveniences do not implicitly enable source retrieval: the standalone dungeon profile still carries no campaign revision, corpus snapshot, rules profile, or citations until the grounded-context policy is implemented and reviewed separately.

## Entities

An entity represents something that can participate in relationships, perspectives, or events.

Examples:

- person;
- player character;
- NPC;
- player or character group;
- faction;
- place;
- item;
- deity;
- organization;
- spell;
- concept;
- secret;
- quest or unresolved thread.

Possible shape:

```text
entity
------
id UUID
campaign_id
type
canonical_name
properties JSONB
visibility_policy_id
system_start_revision
system_end_revision NULL
created_at
```

Entity types should be useful for validation and retrieval but should not require rigid inheritance trees at the beginning. `properties` is for low-risk descriptive metadata; temporal, perspective-dependent, provenance-sensitive, or secret state belongs in assertions so it can be versioned and filtered independently.

Aliases and source mentions should be represented separately:

```text
entity_alias
------------
id UUID
campaign_id
entity_id
alias
normalized_alias
source_revision_id NULL
valid_start_anchor_id NULL
valid_end_anchor_id NULL

entity_mention
--------------
id UUID
chunk_id
start_offset
end_offset
surface_text
resolved_entity_id NULL
resolution_status
```

This allows "Lord Voss," "the Baron," and "Alaric Voss" to resolve to the same entity without assuming that every shared name denotes the same character. Entity creation, alias assignment, merge, and split are reviewable change items. A merge should preserve redirect/audit records rather than deleting the losing entity and breaking old citations.

## Character Sheets and Important Story Items

The DM-only assistant should have access to complete supplied character sheets and important-item records. These are cohesive, frequently queried aggregates and should not be decomposed into one proposition per ability score, proficiency, spell, or item field.

The original source is retained immutably. Markdown/JSON can use a document revision directly; if the selected format is binary (for example, a PDF), store a content-addressed source-asset revision and link any extracted text/parsed rendition to it. Binary-asset support can be added with the first adapter that needs it rather than burdening the initial Markdown ingestion slice. A format adapter can propose a normalized, schema-versioned snapshot:

```text
character_sheet_snapshot
------------------------
id UUID
campaign_id
character_entity_id
ruleset
source_document_revision_id NULL
source_asset_revision_id NULL
schema_version
sheet_data JSONB
computed_data JSONB
visibility_policy_id
system_start_revision
system_end_revision NULL

item_profile_snapshot
---------------------
id UUID
campaign_id
item_entity_id
ruleset NULL
source_document_revision_id NULL
source_asset_revision_id NULL
schema_version
profile_data JSONB
visibility_policy_id
system_start_revision
system_end_revision NULL
```

Validated `sheet_data` can include ancestry/background, class and level, abilities, saves, skills, senses, movement, AC, maximum HP, proficiencies, languages, features, feats, spells, inventory, currency, and attunement. `profile_data` can include an important item's mechanics, charges, restrictions, lore, and attunement requirements. Source-reported and harness-computed values remain distinguishable; computed values record their formula/rules-profile version and are rebuildable.

The snapshots answer questions such as "What is Rowan's passive Perception?" without graph traversal. Story-changing information still uses the temporal knowledge model:

- who owns, carries, or is attuned to an item;
- where an item was last seen;
- who knows an item's true function;
- when a character gained a feature or possession in the fiction;
- conflicts between a sheet's inventory and accepted campaign state.

A sheet/profile update produces a concise field-level diff in a change set and campaign revision summary. Approved source adapters may make bulk review easy, but imports do not bypass the canonical audit path.

Rapid tactical state—current HP, expended spell slots, short-duration conditions, initiative, and position—is outside the initial scope unless later play demonstrates a need for a live tracker.

The source format is intentionally adapter-based; the first adapter should be selected from the actual character-sheet files rather than guessed in the architecture.

## Preparation Artifacts and Generation Runs

Dungeons, maps, puzzles, generated creatures, and encounters belong to a versioned **preparation workspace**, not directly to canonical campaign state.

```text
prep_artifact
-------------
id UUID
campaign_id
artifact_type                 -- dungeon, map_package, encounter, puzzle, etc.
title
lifecycle                     -- draft, approved_for_play, used, retired
current_version_id NULL
visibility_policy_id
created_at

prep_artifact_version
---------------------
id UUID
artifact_id
parent_version_id NULL
schema_version
specification JSONB
validation_report JSONB
change_summary
input_campaign_revision_id
input_corpus_snapshot_id
input_rules_profile_id NULL
input_party_snapshot_id NULL
generation_run_id NULL
created_by
created_at

artifact_asset
--------------
artifact_version_id
asset_id
role                          -- dm_svg, player_png, print_pdf, manifest, etc.
```

Artifact versions are immutable and carry a readable change summary. Editing/regenerating creates a child version and can preserve stable floor/room/encounter IDs for unchanged parts. Approval moves an artifact version into a DM preparation lifecycle; it is not a canonical campaign revision.

If the DM decides that selected generated facts are established world reality—such as the existence/location of a dungeon or an NPC who inhabits it—the application creates an ordinary reviewed campaign change set referencing the artifact version. Marking an encounter `used` likewise does not infer victory, deaths, discoveries, or loot; session close records those outcomes.

```text
generation_run
--------------
id UUID
campaign_id
generation_kind
seed
input_scope JSONB
generation_context_envelope JSONB NULL   -- common envelope + strict domain payload
generation_context_payload_hash NULL
schema_versions JSONB
generator_versions JSONB
model_run_ids
status
started_at
finished_at NULL
```

A generation run records deterministic stages and model-gateway/tool interactions separately. Its generation-context envelope is validated against the named domain payload schema; it is not an untyped dumping ground for all possible context. Safe attempt/profile/schema/compiler/hash/count/diagnostic pins may remain in the existing versioned JSONB fields unless a concrete query or constraint requires a migration; no second run database or queue is introduced. Replaying the same pinned inputs and versions should reproduce the structured layout; a model call may require replaying its recorded structured output unless the provider guarantees deterministic inference.

Prompted dungeon attempts use the terminal stage taxonomy `model_transport`, `model_submission`, `intent_compile`, `deterministic_preflight`, `render`, `asset_stage`, `persistence`, and `completed`. Each terminal outcome records a stable public-safe code and body-free diagnostics; unexpected failures additionally retain only correlation, stage, and exception class in ordinary logs. A prompt-attempt run starts before provider contact. It is distinct from, and links to, the final artifact generation run so a failed pre-package attempt is durable without implying an artifact exists.

P7-01 adds monotonically numbered immutable versions with a canonical specification hash, same-artifact parent constraints, same-campaign artifact/run constraints, and immutable asset-role rows. Database triggers reject version/asset/lifecycle-event mutation and allow a generation run to change exactly once from `running` to a terminal status while preserving all input/version/model/tool pins. Every artifact lifecycle change has an immutable actor/reason/version event. Creating a child of approved/used preparation returns it to `draft`; `retired` is terminal. These tables have no relationship to a canonical change set or campaign revision write. Input revision/snapshot UUIDs remain opaque pins until their owning schemas are added, at which point later migrations add ownership foreign keys without rewriting preparation history.

## Dungeon Generation Architecture

The alpha reset replaces model-authored arbitrary topology and place-then-route search with a proof-carrying constructive pipeline:

```text
DM request + GenerationContextEnvelope<DungeonGenerationContext> + server seed
    |
    v
one structural model tool call: submit_dungeon_plan(structural proposal V1 root)
    |
    v
pure topology compiler
    |-- critical path -> connected backbone
    |-- branches -> attached paths
    |-- loops -> supported series/parallel bypasses
    |-- gates/secrets/content slots -> typed annotations and reserved demand
    `-- TopologyCertificate V1
    |
    v
constructive orthogonal layout
    |-- room interior and wall-port arithmetic
    |-- backbone columns + branch/loop bands + reserved channels
    `-- exact required bounds and DungeonPackage V1
    |
    v
independent topology/geometry/secrecy validation
    |
    v
separately bounded Workbench enrichment tasks over exact package IDs
    |-- puzzle design
    |-- exploration challenge design
    |-- other requested interaction kinds
    `-- player-observable room narrative after mechanics are accepted
    |
    v
deterministic guide assembly + SVG / PNG + readiness validation
    |
    `--> atomic Workbench draft publication; failed enrichment leaves explicit blockers
```

The normative staged design and stress ladder are in [`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md). P7-13 output/print work is paused until its Tier A gate passes.

`DungeonGenerationContext` remains narrow: authorized location lore, themes, factions, plot hooks, geography, tone, and coarse party constraints. It never becomes an all-purpose encounter/session payload. The Workbench owns context, provider calls, run state, persistence, and human approval. The pure package owns `DungeonPlan`, deterministic IDs and policies, topology construction/certification, layout, validation, rendering, and export. The model cannot select scope, seed, canonical IDs, coordinates, dimensions, visibility policy, lifecycle, renderer syntax, files, SQL, approval, or canonical operations.

The staged calls must not lose the initial creative and factual foundation merely because their domain payloads are narrow. After structural acceptance, trusted Workbench code derives one bounded dungeon-only **creative-continuity projection** from the resolved `DungeonGenerationContext` plus accepted `DungeonPlan`: premise, themes, room purposes, progression and objective intent, selected authorized history/environment facts, factions/hooks, tone, motif-variation constraints, and source/citation references. The projection, its version, hash, visibility decisions, and sources are pinned to the artifact and every enrichment lineage. Each puzzle, exploration, feature, trap, objective, or narrative context receives only its relevant fields and bounded accepted-mechanic summaries while carrying the same projection hash. This is a required dungeon-specific continuity boundary, not a universal optional-field `GenerationContext`, retrieval dump, or permission for one task to rewrite another. Standalone generation has no campaign facts unless the DM explicitly selects grounding; missing history or lore remains unknown.

The model-visible schema and runtime contract must use the provider-supported JSON Schema subset and stay small enough to inspect. The model supplies room identity/purpose and progression primitives—critical path, branches, bounded loops, secrets, gates, and content intent—not an arbitrary complete edge list. Code constructs the graph. A schema-invalid submission may receive one bounded repair; deterministic topology or geometry bugs never trigger a request for another random model graph.

There are no retained user dungeons or external consumers. The alpha therefore collapses proposal/design/compiler/topology/package/generator history to one V1, removes numeric suffixes from public names, deletes old generation and compatibility dispatch, and recreates synthetic fixtures. This does not rewrite Git history.

**Retention-gate version policy:** until `PROJECT_STATUS.md` and this architecture explicitly declare the retention gate crossed, active V1 schema, prompt, compiler, generator, renderer, exporter, fixture, and review-packet labels are updated in place. Synthetic fixtures, ignored review packets, disposable alpha database rows, and provider canaries do not justify a version bump or compatibility reader. The gate must be declared no later than the first intentionally retained real-user artifact/campaign, external consumer, non-disposable deployment, or promised replay requirement. At that point the retained pins are frozen and reader/migration/rollback policy must be documented before incompatible changes. After the gate, a version changes only when retained data or consumers need a distinguishable implementation for correct reading, replay, migration, or rollback—not merely because code changed.

Geometry-affecting features, exact markers, door mechanics, content slots, and encounter-space demand belong in `DungeonPackage`; prose-heavy guide content remains in the Workbench and references exact IDs. The structural submission reserves only the requested content kind and spatial demand. It does not author complete puzzle mechanics, exploration scenes, traps, features, objectives, and room narratives in the same call that chooses room progression.

After exact IDs and geometry exist, the Workbench dispatches separately bounded, task-specific enrichment calls only for requested content slots. A puzzle task receives the local room geometry, its approved gate/objective relationship, nearby approved clue locations, tone, and puzzle-specific constraints; it returns only a typed solution model, success state, clue path, hint/alternate handling, failure/reset behavior, and player-observable elements. The active puzzle slice defines these as strict `DungeonPuzzleEnrichmentInput` and `DungeonPuzzleEnrichmentOutput` contracts, constructs the input only from a trusted exact package plus explicit server approvals, validates output IDs semantically, and dispatches one independently pinned puzzle tool call with at most one separately budgeted repair. An accepted result is stored in the DM-only artifact specification, projected deterministically into the exact room-centric guide, and published as one atomic child version without regenerating package geometry; map assets remain byte-identical. Projection cannot replace accepted puzzle content or clear unrelated readiness blockers. A rejected task persists only bounded attempt metadata and leaves the parent draft unchanged. The exploration slice separately defines strict `DungeonExplorationEnrichmentInput` and `DungeonExplorationEnrichmentOutput` contracts. Trusted code selects one exploration-role room's local geometry and exact exploration slot plus explicitly approved room-local feature affordances, pacing role, stakes, and constraints. Semantic validation rejects foreign package, room, slot, or affordance IDs. One independently pinned exploration tool call has its own profile, effort, prompt/schema pins, 6,000-token cumulative and 2,048-output budget, and one budget-reserved repair. Accepted content and final model record are retained in the authorized DM-only specification, projected as observable cues, multiple approaches/consequences, and escalation/recovery, and atomically published as one child version. The package and map assets, accepted puzzle content/lineage, and unrelated blockers remain unchanged; rejection persists only compact diagnostics and leaves the parent current. The feature-interaction slice defines another strict exact-ID payload built from one package marker, its current guide entry, and local room geometry. It rejects foreign IDs plus structural/cross-task fields and projects only observable setup, bounded affordances/consequences, and optional reset/retry guidance into that feature. One independently pinned feature tool call has its own profile, effort, prompt/schema pins, 6,000-token cumulative and 2,048-output budget, and one budget-reserved repair. Accepted content and final model record are retained in the authorized DM-only specification and atomically published as one child version. The package and map assets, accepted puzzle/exploration content and lineage, other feature entries, and unrelated blockers remain unchanged; rejection persists only compact diagnostics and leaves the exploration parent current. The trap slice defines an exact-ID payload joining one package room-trap marker and current guide entry to local room geometry plus code-owned detection and disable difficulties. Its output contains only an observable warning, actual trigger/effect narration, detection and disable counterplay, consequences, and optional reset/recovery; foreign IDs, structural/cross-task fields, and model-authored numeric DCs are rejected. One independently pinned trap tool call has its own profile, effort, prompt/schema pins, 6,000-token cumulative and 2,048-output budget, and one budget-reserved repair. Accepted content and final model record are retained in the authorized DM-only specification, projected only into that trap beside unchanged code-owned difficulties, and atomically published as one child version. Package/map state, all prior task content and lineage, other traps, and unrelated blockers remain unchanged; rejection persists only compact diagnostics and leaves the parent current. The objective seam similarly joins one exact objective marker/current guide entry and local geometry to a bounded selection of summaries copied from already accepted puzzle, exploration, feature, and trap guide content. Its strict output can propose only the observable goal, adjudication, multiple resolutions referencing those accepted mechanic IDs, and setback/aftermath; deterministic projection updates only the selected objective and its readiness blocker without renaming the objective or changing package/map state or prior content. One independently pinned objective tool call has its own profile, effort, prompt/schema pins, 6,000-token cumulative and 2,048-output budget, and one budget-reserved repair. Accepted objective content and final model record are retained in the authorized DM-only specification and atomically published as one child version. Package/map state, prior puzzle/exploration/feature/trap content and lineage, other guide entries, and unrelated blockers remain unchanged; rejection or publication failure persists only compact diagnostics and leaves the trap parent current. Other interaction kinds use equally narrow contracts. The homogeneous room-narrative seam receives a bounded exact-room set only after local mechanics exist: trusted code joins exact geometry and bounded existing room guide state to player-observable summaries copied from accepted puzzle, exploration, feature, trap, and objective content. Its strict output supplies only concise read-aloud and observable framing keyed to the exact selected room IDs. Validation rejects foreign, duplicate, or omitted rooms; deterministic projection fills only blank selected narratives and removes only their room-readiness blockers without changing accepted mechanics, objective content, package/map state, other guide entries, or unrelated blockers. One independently pinned narrative call has its own profile, prompt/schema pins, 6,000-token cumulative and 2,048-output budget, one budget-reserved repair, accepted-content lineage, and atomic DM-only child publication. Package/map bytes, every prior enrichment and lineage, unselected room state, and unrelated blockers remain unchanged; rejection or publication failure stores only compact diagnostics and leaves the objective parent current. These payloads use the common generation-context envelope, inherit the same pinned dungeon creative-continuity hash, and remain strict domain contexts; they never become one universal optional-field guide context. Context construction fails closed when the projection is stale, source visibility is broader than the task scope, a citation is no longer authorized, or accepted structural intent conflicts with the requested local task.

Operational data handling stays proportionate to a DM-operated application: accepted enrichment content is intentionally retained with the authorized DM-only artifact so it can be rendered, reviewed, and audited. Ordinary logs and attempt reports keep only run/artifact IDs, hashes, profile/schema pins, budgets and measured usage, status/stage, and bounded diagnostic code/path/repair facts. Raw prompts, context, accepted or rejected provider bodies, and reasoning are available only through the authorized artifact where applicable or an explicit transient local debug callback; they are not copied into routine logs. This uses the existing artifact specification and `generation_run` JSONB surfaces—no redaction service, second audit database, or new logging subsystem.

The Workbench validates every enrichment against exact package IDs and the accepted structural slots. No enrichment may change topology, geometry, visibility, deterministic DCs, reserved demand, or another task's accepted content. The rendered guide assigns entry-first sequential presentation numbers independent of stable package/map IDs, then emits concise valid Markdown/HTML with one useful read-aloud block and locally grouped actionable door state, checks, clues, scene pressure, triggers, consequences, features, puzzles, and objectives. It omits ordinary map-visible connectivity plus separate sensory/purpose repetition; read-aloud is limited to player-observable information, while hidden operation stays in DM adjudication. Missing, invalid, or subjectively rejected enrichment blocks preparation readiness without invalidating proven geometry or asking the structural model to try another topology. On success, deterministic preparation renders and validates every required asset, stages blobs, and atomically publishes the artifact/version/assets/run.

Before preparation approval, a final continuity/readiness gate recomputes projection-hash and authorized-source inheritance, exact dependencies, required content, lineage, secrecy, and typed cross-task consistency. The provider-free gate is a pure Workbench function over one immutable `DungeonStudioSpecification`: it rebuilds the structural continuity projection, compares exact selected fact/source IDs retained by each accepted enrichment lineage, revalidates package dependencies and staged slot coverage, and renders player SVGs to fail closed on protected IDs. It returns only bounded body-free diagnostics and performs no persistence, provider, approval, or canonical operation. The service now invokes it before any prompted lifecycle transition, while provider-independent manually authored artifacts retain their readiness-based path. A staged review-packet boundary also invokes it and records only the exact result hash and seven check summaries rather than diagnostics or content bodies.

Whole-dungeon qualities that cannot be proven mechanically are evaluated separately. The strict read-only cohesion-report contract covers thematic reinforcement across rooms, history-to-environment causality, mechanic/objective unity, progression, intentional motif variation, and consistency with selected campaign lore. It permits bounded findings, exact evidence component IDs, and at most a targeted recommendation to an existing enrichment seam; it has no artifact-edit, blocker-clearing, approval, or canonical field. The DM disposition contract binds the exact report/specification hashes, covers all six dimensions and every finding, and records acceptance, explicit risk acceptance, not-applicable treatment, or targeted regeneration. Targeted-regeneration dispositions block approval. The staged DM-facing review packet records that evidence, and prompted approval validates it again after deterministic validation. Accepted fixes use targeted regeneration of one exact enrichment seam rather than a silent whole-guide rewrite. No model can approve the result or make it canon.

The active provider-free Tier A evaluation manifest is separate from the Synthetic Constructive Archive regression. It freezes three materially different original synthetic settings/interaction styles, standalone and synthetic-grounded cases, and opaque stable variant IDs whose prompt/model/effort assignments remain hidden from reviewers. Strict body-free run evidence records only assignment/artifact hashes, latency, measured token usage, first-pass validity, bounded repair count, and final validity. Strict blinded human evidence records only case/variant/artifact/reviewer IDs and 1–5 ratings for the six cohesion dimensions, clue logic, player agency, puzzle comprehensibility, exploration quality, and DM preparation usefulness; lore consistency is not rated for standalone cases. Provider prompts, responses, excerpts, and reasoning do not belong in these evidence records. The evaluator-side matrix fails closed unless every manifest case/variant pair has exactly one run and one review, each variant keeps one assignment hash across cases, the reviewed hash names its final-valid artifact, and lore ratings match grounding applicability. Only then can a body-free aggregate expose rating means, the applicable lore denominator, latency/token means, first-pass-validity rate, and repair rate grouped by opaque variant ID. Synthetic arithmetic fixtures prove this boundary but are not quality evidence.

### Dungeon Specification Layers

Keep four V1 representations distinct:

1. **`DungeonPlan`** — the one small creative model/human contract. Local refs relate rooms only within the plan. Progression uses critical-path, branch, and loop primitives.
2. **`TopologyCertificate`** — compiler-owned graph, mechanics/demand projection, supported-grammar parse tree, reachability/loop/gate witnesses, room degree/port demand, and constructive embedding order. Validators recompute its claims.
3. **`LayoutRequest`** — certificate plus server seed, optional maximum bounds, and later explicit regeneration locks.
4. **`DungeonPackage`** — exact renderer-neutral geometry, openings, mechanics, markers, encounter demand, and audience layers.

Local refs such as `archive` are noncanonical relation handles. The compiler derives stable opaque IDs from the V1 compiler pin and semantic identity, independent of seed, prose, and array order. Exact established IDs may enter only later explicit edit/regeneration operations.

Directional discovery, gates, traps, features, and encounter intent are annotations on the constructed graph and room demand. They do not create competing topology representations. A one-sided secret physical link may retain ordinary player geometry only under an explicit publication rule; otherwise filtered components are absent before rendering. In-play reveal state remains a later Workbench concern.

A conceptual package can be stored as one versioned aggregate rather than one relational row per tile:

```text
DungeonPackage
---------------
schema_version
grid_type                      -- square initially
cell_scale_feet                 -- default 5
floors[]
rooms[]
connections[]                  -- corridor, door, secret, stair, etc.
gates_and_dependencies[]
features[]                     -- pillar, pit, altar, difficult terrain, etc.
zones[]
markers[]                      -- encounter/start/treasure/clue anchors
layers[]                       -- base, player, dm_secret, labels, grid
metadata
```

Initial generation should favor orthogonal square-grid geometry. Each floor is laid out independently but stairs/vertical connections must pair and validate. Regional/world maps and arbitrary illustration-first geometry are out of scope.

#### Constructive Deterministic Layout Algorithm

Tier A supports a deliberately bounded series/parallel-with-spurs graph class. The compiler creates a connected critical-path backbone, attaches branches, and adds only loop intervals that preserve the supported embedding. For a connected floor, validators recompute `cycle_rank = edges - rooms + 1` and require witnesses for every requested loop. Gate progression is solved by repeated reachability with closed gate edges; dependencies must be reachable before their gates.

Layout consumes the certificate rather than discovering feasibility through random retries. Critical-path rooms receive ordered columns; branches receive dedicated upper/lower bands; loop bypasses receive reserved nonintersecting interval bands; and each connection receives a channel. Room dimensions expand deterministically to satisfy side-specific opening demand and usable interior demand from encounters/features. The required floor bounds are computed before geometry is emitted. An optional caller maximum is accepted only when it contains those proven bounds.

Direct shared-wall doors are used only when the constructive embedding assigns compatible adjacent room sides. An arbitrary connection remains a corridor with explicit openings because not every planar graph is a rectangle-contact graph. Seeded optimization may compact, mirror, rotate, or vary a proven layout, but failure falls back to the constructive baseline. Backtracking is never the correctness mechanism.

Independent topology, raster geometry, pathfinding, capacity, and secrecy validators remain mandatory. Their purpose is to catch implementation bugs—off-by-one bounds, bad openings, overlaps, disconnected cells, or leaks—not to discover whether the supported input happened to have a solution.

### Dungeon Primitives and Model Tools

Alpha V1 exposes exactly one **structural** submission tool:

```text
submit_dungeon_plan(proposal_version, plan, ...)
```

Those fields are one structural `DungeonGenerationProposal` at the tool-argument root; there is no nested `proposal` property and no prose-heavy `guide_content` payload. The tool validates that proposal, invokes pure `DungeonPlan` topology compilation/certification and constructive preflight, and returns a compact accepted plan hash, graph counts, cycle rank, certificate version, content-slot summary, and warnings—or at most eight stable code/path/ref/repair diagnostics. The accepted arguments are the structural model result; no duplicate final text is requested. The tool neither persists nor approves anything.

The structural model declares room purposes plus critical path, branches, bounded loops, secrets, gates, a named objective, and bounded content slots/demand. It does not design the complete puzzle, exploration challenge, trap interaction, feature interaction, and room prose concurrently. Code computes the realizable graph and exact layout. One schema-invalid structural plan may receive one bounded repair. Deterministic topology or geometry bugs never trigger another model topology.

After geometry succeeds, Workbench-owned task-specific tools accept typed puzzle, exploration, interaction, and narrative proposals keyed to exact server IDs. Each enrichment call has its own narrow context, schema, effort/profile pin, output and cumulative budget, repair policy, diagnostics, and durable lineage. The puzzle task is the first dispatched example: accepted content and its final model record live in the authorized child specification, while ordinary attempt/run reports retain only compact operational metadata and safe diagnostics. Exploration has its own exact-ID contract, trusted context builder, validator, independently bounded dispatch/repair policy, accepted-content lineage, guide projection, and atomic child publication. Its success and failure invariants match the task boundary without sharing puzzle context or output schemas. Feature interactions use another strict payload that joins one exact package marker to its current guide entry and local geometry, then proposes only observable setup, bounded affordances/consequences, and reset/retry guidance when useful. Its independently bounded dispatch/repair, accepted-content lineage, deterministic projection, and atomic DM-only child publication preserve all prior task content and package/map bytes; failure leaves its parent unchanged with body-free diagnostics. Room traps have a strict exact-ID context/validation/projection seam over one marker, current guide entry, local geometry, and deterministic detection/disable arithmetic. Their independently bounded dispatch and one budget-reserved repair retain accepted-content lineage and atomically publish a DM-only child. The trap output has no numeric difficulty field and cannot mutate structure or prior task content; accepted warning, trigger/effect, counterplay, consequences, and recovery update only the selected trap, while rejection leaves its parent unchanged with body-free diagnostics. Objectives have a strict exact-ID context/validation/projection seam over one marker, its current guide entry, local geometry, bounded stakes/constraints, and selected summaries copied from accepted mechanics. The output cannot rename or reclassify the objective or mutate those mechanics; accepted goal, adjudication, resolutions, and setback/aftermath update only the objective. Independently bounded dispatch with one budget-reserved repair retains accepted-content lineage and atomically publishes a DM-only child while preserving package/map bytes and every prior enrichment; failure leaves the trap parent unchanged with body-free diagnostics. A call may cover one homogeneous bounded responsibility. The active room-narrative task covers at most eight exact rooms and exposes only geometry, bounded existing room guide state, tone/constraints, and player-observable summaries of accepted local mechanics. Its output cannot carry mechanics or structural fields and can fill only concise read-aloud and observable framing in blank selected rooms. Its independently bounded dispatch and one repair retain accepted-content lineage and atomically publish a DM-only child without changing package/map bytes, prior enrichments, unselected rooms, or unrelated blockers; failure leaves its parent unchanged with body-free diagnostics. It must not combine structural planning with puzzle and exploration authoring. Accepted enrichment is merged deterministically; a failed or missing task leaves a structurally valid readiness-blocked draft and cannot erase another accepted task. Before dispatch, a pure Workbench planner compares exact package slots, current guide projection, and retained successful lineage. It selects one deterministic puzzle, exploration, feature, trap, or objective target at a time, then one bounded homogeneous narrative room set only when every selected room's local mechanics are accepted. Missing/mismatched guide state, unsupported blockers, stale/duplicate lineage, or projected content without matching accepted lineage produce a body-free blocked plan rather than replacement or dispatch. Planning itself performs no provider, persistence, geometry, topology, approval, or canonical operation. The provider-free one-step coordinator consumes that plan only for the current immutable parent, requires one discriminated task-specific trusted policy whose exact IDs match the selected target, invokes exactly one existing bounded application seam, and replans only an accepted current child. Exploration policy carries the planner-selected encounter-slot ID separately from its room-local context selection so a mismatched slot fails before context construction, provider dispatch, or publication. Resumed one-step coverage spans exploration, feature, trap, objective, and bounded room narrative: every matching policy invokes only its existing task-specific seam and replans the one accepted child, while a mismatched exact target makes no provider call and creates no version. A rejection leaves the parent current and never advances to another staged task. The provider-free chain boundary repeats only this one-step primitive over an ordered, bounded set of trusted exact policy/profile pairs. It advances the parent ID only after an accepted child, stops immediately on rejection or a blocked/complete replan, distinguishes policy exhaustion from its explicit 32-task ceiling, and performs no preparation approval or canonical operation.

Targeted editing/regeneration remains a later authenticated DM operation. Initial structural generation remains one model call plus at most one schema repair; enrichment calls are independently skippable/failable and occur only after exact geometry exists.

### Deterministic Dungeon Validation

At minimum validate:

- required-room connectivity and entrance/exit reachability;
- room/corridor overlap and map bounds;
- wall, door, secret-door, and stair alignment;
- matching floor transitions;
- minimum corridor width and creature/encounter capacity;
- walkable paths and unusable isolated cells;
- lock/key, clue/gate, and puzzle dependency solvability before readiness/approval, with incomplete draft dependencies reported explicitly rather than invented;
- requested loop/branch/secret-route properties;
- player versus DM layer leakage;
- grid scale, page/export dimensions, and stable identifiers.

Graph and geometry diagnostics should be structured (`code`, affected IDs, severity, repair hints) so a model can repair a specification without receiving renderer internals.

The P7-05 square-grid validator rasterizes room polygons using half-open cell bounds, expands orthogonal corridor centerlines to their declared widths, subtracts explicit blocking terrain/features, and connects paired vertical endpoints. Deterministic breadth-first search is authoritative for anchor-to-anchor reachability. Creature footprints are axis-aligned cell rectangles whose query point is the top-left occupied cell. Encounter-fit hooks report conservative spatial facts—usable cells, footprint placement, anchor/objective reachability, open range, and cover-feature IDs—without composing encounters or performing rules/difficulty arithmetic.

## Map Rendering and Export

The exact dungeon package is renderer-neutral. SVG is the first deterministic rendering layer because it preserves grids, semantic layers/IDs, labels, and exact geometry at any scale. It is primarily an implementation/intermediate format and optional download, not something the DM must edit. PNG is rasterized from the same package for Roll20 and ordinary web viewing.

Render at least two information variants:

- **DM map:** secrets, traps, encounter markers, short room callouts, puzzle annotations, and all connections;
- **clean/player-safe map:** geometry only by default—published rooms/corridors, ordinary visible door geometry, stairs, terrain, and explicitly player-safe physical feature shapes; no room/door/feature keys, objective/start/encounter markers, secret doors, hidden areas, traps, lock state, hidden difficulty values, or puzzle solutions. Visible doors use an explicit heavy slab stroke that remains distinct from both room walls and the background grid in every trusted drawing adapter.

Default maps never print opaque package/component IDs as human labels. P7-13 uses one code-owned, grayscale-safe DM grammar: numbered room circles; a distinct start flag projected from the single entrance; standard door openings with keyed `S`, `L`, and `T` badges for secret, locked, and trapped mechanics; triangle trap/hazard callouts; diamond puzzle callouts; keyed clue/key/treasure and feature markers; double-ring objective callouts; and distinct directional transition symbols. Short stable callouts resolve bijectively to a per-floor DM key containing names and mechanics. Long descriptions stay out of map geometry. Deterministic annotation layout measures complete text, symbol, and mechanics-badge bounds, reserves start/encounter symbols, selects noncolliding candidate positions, and uses a leader line only when no local candidate fits. Technical `PositionAnchor` points support pathfinding, spatial validation, and explicitly requested VTT metadata. Ordinary maps never show their generic circle glyph: the entrance anchor is projected as a DM-facing start flag, while generated exit/objective path endpoints remain map-internal. DM callout maps include a compact code-owned symbol key placed in the least-occupied map corner. Player projections omit the legend and every keyed callout; player-safe physical features may retain an unlabelled shape, never an `F*` key. Color may reinforce a distinction but can never be its only encoding.

The P7-06 SVG renderer filters components against both mandatory visibility and render-layer export policy **before** constructing XML; CSS hiding is never a secrecy mechanism. SVG element IDs and `data-*` attributes are deterministic and stable, but player output contains no element or metadata record for a filtered component. Initial presentation is selected only from code-owned `low_ink` and `draft` themes; model-authored SVG/CSS is not accepted.

### Low-Ink Table Printing

The print exporter is a core intended output, but retained output demonstrated unbounded blank/sparse whole-floor tiling. P7-13a therefore centrally disables new print generation; until that slice lands, current code still generates PDFs and must be treated as known-bad experimental behavior. Hiding one web button is insufficient: shared CLI/API/web application policy must reject new print jobs with one stable disabled-capability diagnostic while historical immutable PDFs remain accessible. Print is re-enabled only through a new exporter/request version after P7-13's preflight and visual page gates pass.

The redesigned exporter separates a bounded fit-to-paper **reference map** (explicitly not miniature scale) from **tactical tiles**. A tactical export keeps a standard five-foot dungeon cell at exactly one inch for common 28–32 mm miniatures, but normally targets an explicitly selected room, encounter zone, or crop. Whole-floor tactical output is allowed only when preflight reports acceptable crop dimensions, tile rows/columns, page count, and occupied-cell coverage. Excessive or mostly blank output fails before bytes are generated. The UI presents the estimate and audience/mode selection and never automatically generates both DM and player PDFs.

The default print theme should minimize ink:

- white/unfilled walkable floors;
- bold black wall/door outlines;
- thin light-gray grid lines;
- grayscale-safe line symbols and sparse hatching for terrain/hazards;
- no textures, full-page dark backgrounds, heavy shadows, or large solid fills;
- configurable label/secret layers and an even lighter draft mode.

Each tiled PDF should include:

- a one-page assembly overview with page grid/order;
- floor/map/version identifiers and page coordinates such as `B3`;
- crop/cut and registration marks;
- configurable overlap strips and matching alignment marks on adjacent pages;
- a one-inch test square and ruler for detecting printer scaling;
- safe margins for common printers;
- explicit instructions to print at 100%/actual size.

The exporter should support trim-and-butt and overlap-and-tape workflows. Tests must inspect PDF page boxes and rendered calibration geometry so "fit to page" mistakes are detectable before a session.

P7-07 uses Pillow to rasterize the already-filtered trusted `svg-v1` subset into deterministic PNG bytes and ReportLab's invariant vector canvas for PDF pages; `pypdf` is test-only inspection tooling. Corridor footprints and white passage-opening cuts are emitted as the same rectangle/line primitives and class semantics consumed by browser SVG, Pillow, and ReportLab—never as SVG-only path or stroke behavior that a raster adapter can silently omit. Text adapters honor SVG baseline coordinates rather than reinterpreting them as vertical centers. Door segments likewise carry an explicit heavy stroke width instead of relying on browser-only CSS, preserving their distinction from grid and wall lines in SVG, PNG, and PDF. This avoids a native Cairo runtime while preserving one secrecy boundary. Tile drawing uses the SVG's 72-pixels-per-cell coordinate system directly as PDF points—no tile-page content scaling—so every five-foot cell remains exactly 72 points/one inch. Export manifests record source SVG/asset hashes, audience/theme/grid settings, page boxes, source viewports, actual overlap and adjacency, calibration size, and an ink-coverage proxy. Before the retention gate, the active visual pins remain `svg-v1`, `png-v1`, `pdf-v1`, and `roll20-v1` while their disposable alpha implementations evolve in place.

### Roll20 and Web Output

The first Roll20 adapter should guarantee correctly sized grid-on and gridless PNG variants plus grid width/height, pixels per cell, scale/origin, floor metadata, and an optional token-placement manifest. Direct Roll20 API upload and dynamic-lighting automation depend on the available Roll20 integration surface and can come later; wall/door geometry should be retained so those exports remain possible.

The P7-08 bundle is a deterministic ZIP with fixed safe basenames, paired PNG asset/source hashes and dimensions, five-foot square setup metadata, visible room-wall polygons and door segments, and optional explicitly requested anchor placements. Anchors are published metadata, not map glyphs, and still pass the same audience filter before inclusion. The bundle is setup metadata—not an API uploader or dynamic-lighting import format. Player filtering happens before every asset and metadata projection; clean manifests omit full-package hashes so changes to DM-only source fields cannot create a hidden-data fingerprint. Adapters revalidate PNG dimensions/hashes, canonical manifest bytes, ZIP paths/content, grid consistency, and bundle hashes before writing.

A richer web presentation is a later rendering concern, not a separate geometry source. Polished artwork must never replace or distort validated tactical geometry.

## Creature Profiles and Encounter Generation

Authorized bestiary material should be normalized into complete, edition-tagged creature profile snapshots rather than retrieved only as prose.

```text
creature_profile_snapshot
-------------------------
id UUID
campaign_id NULL
creature_entity_id
ruleset
source_document_revision_id NULL
source_asset_revision_id NULL
schema_version
stat_block JSONB
lineage_parent_id NULL
lineage_kind                  -- source, reskin, scaled_variant, generated
visibility_policy_id
system_start_revision NULL
system_end_revision NULL
```

A complete `stat_block` should support identity/type/size, AC, HP/hit dice, speed/movement modes, ability scores, saves, skills, vulnerabilities/resistances/immunities, condition immunities, senses, languages, proficiency/challenge metadata, traits, spellcasting, actions, bonus actions, reactions, legendary/mythic/lair actions where applicable, and source notes. Generated/custom variants store a full usable stat block plus a diff/lineage explanation; they do not depend on the model remembering an unstated base creature. Their declared challenge/XP is validated against edition-specific monster-building guidance where available, or marked provisional for DM review rather than accepted from model judgment alone. Source profiles are structured corpus projections, while encounter-specific variants live under the preparation artifact/version that generated them unless the DM explicitly promotes one into reusable campaign material.

The project should not distribute copyrighted bestiary data. It imports user-supplied/authorized sources and keeps their edition/source provenance and visibility.

### Pinned Party and Playstyle Input

Each generated encounter pins a party-generation snapshot:

```text
party_generation_snapshot
-------------------------
id UUID
campaign_id
character_sheet_snapshot_ids
party_level_summary
playstyle_profile JSONB
resource_overrides JSONB NULL
rules_profile_id
generation_assumptions JSONB
created_at
```

The playstyle profile can capture DM-approved inputs such as optimization, tactical skill, risk appetite, preferred combat length, rest cadence, desired lethality, favored/avoided mechanics, accessibility needs, and observed strengths/weaknesses. The model may suggest updates, but should not silently infer permanent player traits from one session. Current resources can be supplied as generation-time overrides without creating a live combat tracker.

### Encounter Package

Encounters are typed preparation artifacts: `combat`, `social`, `exploration`, `puzzle`, `trap`, `hazard`, or `mixed`.

A package may contain:

```text
purpose / stakes / objectives
location and dungeon room/zone IDs
party snapshot and target difficulty
complete participant stat blocks or NPC profiles
starting positions, waves, reinforcements, and triggers
terrain/feature interactions
tactics and behavior, including retreat/surrender
checks, DCs, clues, hints, solutions, and counterplay
success, partial-success, failure, and bypass outcomes
rewards, discoveries, resource pressure, and consequences
scaling variants with reasons and recalculated metrics
DM-only and player-safe handout content
rules/source citations
```

Combat encounter arithmetic belongs to an edition-aware deterministic evaluator selected by the rules profile. It computes official budgets/thresholds where available and reports assumptions. The LLM chooses coherent opponents, objectives, tactics, and variants using those results; it cannot mark its own arithmetic valid. Difficulty evaluation should consider party composition and explicit playstyle modifiers while reporting both the rules baseline and adjusted recommendation.

Dungeon-wide encounter generation should consider pacing, attrition/rest assumptions, variety, clue/key dependencies, and room geometry—not optimize each room in isolation. Creature sizes, movement modes, ranges, cover, chokepoints, and objective space must fit the linked layout.

Noncombat generators use type-specific validators. A puzzle, for example, needs an explicit solution model, clue path, hint ladder, alternate reasonable handling, failure/reset behavior, and player-safe output. A social encounter needs actor goals, leverage, likely approaches, escalation, and multiple resolutions rather than one mandatory skill check.

Encounter orchestration consumes a dedicated `EncounterGenerationContext` carried by the common generation envelope. That payload emphasizes pinned party mechanics and playstyle, authorized creature sources, difficulty preference, room geometry, resource pressure, and pacing. Campaign lore may be included when selected by the encounter context policy, but fields useful only to dungeon layout or session extraction do not become optional encounter fields. The model proposes composition and experience; deterministic Workbench mechanics validate difficulty, stat completeness, map fit, and type-specific completeness.

Whether those deterministic mechanics deserve a separate Python distribution is intentionally undecided. Start with a cohesive Workbench module. Extract a package only when P8 demonstrates a stable API, meaningful independent tests/reuse, or dependency isolation benefits; if extracted, `encounter-mechanics` is a more likely boundary than the entire creative encounter workflow.

## Predicates

Predicates describe the meaning of proposition content.

Examples:

```text
sibling_of
member_of
located_in
owns
acquainted_with
hostile_to
allied_with
owes_money_to
infiltrates
pretends_allegiance_to
```

Belief, knowledge, suspicion, and claims are assertion modes over a proposition, not ordinary predicates. Keeping those modes separate avoids ambiguous structures such as `Mira knows Salazar` when the intended object is the proposition "Salazar killed Deren."

A predicate is data, not a database column.

Possible shape:

```text
predicate
---------
id UUID
namespace
name
version
description
subject_type_constraints
object_type_constraints
value_kind
symmetric BOOLEAN
transitive BOOLEAN
inverse_predicate_id NULL
functional BOOLEAN
exclusivity_group NULL
properties JSONB
lifecycle_status
```

This is the basis of a lightweight campaign ontology. `functional` and `exclusivity_group` allow selected state predicates, such as a single physical location at a given time, to receive stronger validation without treating every graph edge as exclusive.

Adding a new relationship should normally insert a predicate row rather than require a schema migration. The model may search the catalog and propose a predicate, but approval is required before it becomes available to canonical assertions. Published predicate semantics should be versioned or superseded rather than edited in a way that silently reinterprets historical data.

Symmetric, inverse, or transitive facts should generally be derived in query logic or a rebuildable projection. They should not be copied into independent canonical rows unless each row has explicit derivation provenance. Transitivity must be opt-in because most narrative relationships are not safely transitive.

## Propositions and Assertions

The central structured primitive has two layers:

1. a **proposition** describes graph-shaped content without declaring that content true; and
2. an **assertion** records that reality or a particular holder has a stance toward that proposition.

This small amount of reification prevents a false belief from being stored as a true world fact and makes "who knows this?" a direct query.

Possible shape:

```text
proposition
-----------
id UUID
campaign_id
content_timeline_id
subject_entity_id
predicate_id
object_entity_id NULL
object_event_id NULL
literal_value JSONB NULL
polarity                         -- positive or explicit negative
content_start_anchor_id NULL     -- when the proposition says the state holds
content_end_anchor_id NULL
qualifiers JSONB
content_hash

CHECK exactly one of object_entity_id, object_event_id, and literal_value is populated
```

Literal values should carry an explicit type/unit shape rather than relying on arbitrary JSON conventions. Event objects support relations such as `witnessed`; proposition-as-object/nested epistemics can be added later if usage justifies it. Explicit negative propositions are supported, but the database follows an open-world model: absence of a positive assertion does not imply a negative assertion.

```text
assertion
---------
id UUID
campaign_id
stance_timeline_id
proposition_id
mode                             -- reality, belief, knowledge, unaware,
                                 -- suspicion, claim, public_record
holder_entity_id NULL            -- null only where the mode permits it
stance_start_anchor_id NULL       -- when the holder acquired/held the stance
stance_end_anchor_id NULL
semantic_certainty NULL
visibility_policy_id
qualifiers JSONB

derivation_kind                  -- explicit, deterministic_derived, inferred
system_start_revision
system_end_revision NULL
supersedes_assertion_id NULL
recorded_at
```

Proposition time and stance time are deliberately separate. Mira can believe in session 10 that an event occurred before session 1; the proposition describes the alleged event time, while the assertion describes when Mira held the belief. Propositions are immutable interned content and are never returned on their own: an authorized assertion supplies truth/perspective, canonical revision, and visibility.

Workflow status and model extraction confidence do **not** belong in the same field as semantic truth:

- `proposed`, `accepted`, and `rejected` belong to change items;
- `active`, `superseded`, and `retracted` are represented by canonical revision/system-time fields;
- `explicit`, `derived`, and `inferred` describe derivation;
- extraction confidence stays on the model output/change item;
- `disputed` is normally represented by incompatible accepted assertions plus evidence, not by overwriting one fact with a status flag.

Evidence is many-to-many and is described separately below. An assertion may have several source chunks and events; it should not be limited to one nullable source of each kind.

## Truth, Belief, Knowledge, Claims, and Public Record

A story frequently contains multiple incompatible but canonically valid perspective assertions.

For example:

```text
P1: Salazar killed Deren.
    assertion(mode=reality, holder=null, proposition=P1)

P2: Rowan killed Deren.
    assertion(mode=belief, holder=Mira, proposition=P2)

P3: Mira killed Deren.
    assertion(mode=public_record, holder=City Watch, proposition=P3)

P4: Deren was murdered.
    assertion(mode=knowledge, holder=Player Group, proposition=P4)
```

"Party," "players," individual players, player characters, and factions should be ordinary group/person entities rather than hard-coded perspective types. This preserves the distinction between what the players know and what their characters know. Group membership can itself vary over time.

The mode vocabulary should begin small and controlled:

- `reality` means the DM has accepted the proposition as the canonical world account and normally has no holder;
- `knowledge` is factive within the selected campaign revision and records that a holder has access to accepted reality;
- `unaware` explicitly records lack of access for an important tracked proposition/holder and ends when a reveal occurs;
- `belief` may be false but records what the holder treats as true;
- `suspicion` records a possibility rather than commitment;
- `claim` records what a holder communicated, not what they believe;
- `public_record` is an institutional claim with an owning entity.

Someone who confidently "knows" a false rumor should normally receive a `belief`, plus evidence of the rumor/claim. Campaign-specific narrative relationships still grow through predicates; epistemic modes should grow only when their query semantics are clear.

The knowledge model is open-world by default. Missing `knowledge` does not prove that a holder is unaware, so a DM-facing answer says "no recorded knowledge" unless the proposition/secret has an explicitly complete tracked-holder scope or an accepted `unaware` stance. Important secrets can opt into such tracking at a baseline event and close/open holder intervals as reveals occur. For NPC/player context compilation, the conservative rule is simpler: do not provide an unrecorded secret to that holder, even when completeness is unknown.

This model allows the harness to answer:

- What really happened?
- What does Mira believe happened, and when did she begin believing it?
- What do the players currently know?
- What is the City Watch's official story?
- Which holders have a `knowledge` assertion matching the accepted `reality` proposition?

Nested statements such as "Mira believes that Rowan suspects Salazar" can remain in narrative memory initially. If they become common, propositions can later support a proposition/assertion reference as an object without changing the basic stance model.

## Sessions and Scenes

A table session is an operational/provenance container, not a fictional timestamp or event sequence.

```text
session
-------
id UUID
campaign_id
display_number NULL
title
played_at NULL
workflow_state             -- planned, open, closed
opened_campaign_revision_id NULL
closed_campaign_revision_id NULL
metadata JSONB

session_document
----------------
session_id
document_revision_id
role                       -- prep, raw_notes, summary, transcript
```

A session can portray events from several fictional dates, establish a retroactive fact, or alternate between concurrent scenes. Session numbers therefore support display, source grouping, and queries such as "what did we establish in session 15," but never replace temporal anchors.

A `scene` can later group a location, participants, a story cursor, and relevant events for live context compilation. It need not be canonical or fully modeled in the first slice; a lightweight scene request can supply those fields directly. If persistent scenes become useful, they should use opaque IDs and explicit event/anchor links rather than deriving chronology from creation order.

## Temporal Model

Event identity must be separate from chronology. Events use UUIDs or other opaque identifiers; sequential display numbers never encode temporal meaning.

### Story Time and Temporal Anchors

PostgreSQL timestamps are unsuitable as the only fictional-time representation because campaigns use custom calendars, vague phrases, and relative chronology. Events and propositions should refer to temporal anchors.

A possible conceptual shape is:

```text
temporal_anchor
---------------
id UUID
campaign_id
domain                 -- story or table/session
timeline_id NULL       -- required for story-domain anchors
session_id NULL        -- available for table/session anchors
kind                   -- exact, bounded, approximate, event_relative,
                       -- session_marker, unknown
calendar_id NULL
value JSONB             -- calendar components and/or lower/upper bounds
precision               -- year, month, day, watch, scene, etc.
reference_event_id NULL
offset JSONB NULL
qualifiers JSONB
```

Example exact-ish value:

```text
calendar: Dale Reckoning
year: 1492
month: Eleint
day: 17
time_of_day: evening
precision: time_of_day
```

A calendar adapter may compute a sortable ordinal when enough components are known. The original structured components and precision remain authoritative; an ordinal is only an optimization. Unknown or approximate time must remain representable without fabricating a date.

No custom-calendar adapter or date arithmetic is required initially. The MVP should implement event/scene-relative ordering, session markers for table knowledge, and unknown/approximate anchors. If a note contains a fictional date, preserve its raw structured/text value for future use without promising calendar calculations.

Proposition content anchors and story cursors require the story domain. Character stance changes normally use story anchors; player knowledge may instead use a table/session anchor when "learned in session 22" is all that is known. Canonical/system time still uses campaign revisions rather than either anchor domain.

### Relative Temporal Relations

Campaign chronology is often only partially known. The system should support reviewed relations such as:

```text
BEFORE
AFTER
DURING
OVERLAPS
STARTS
FINISHES
SIMULTANEOUS_WITH
```

Possible shape:

```text
temporal_relation
-----------------
id UUID
campaign_id
timeline_id
subject_event_id
relation_type
object_event_id
semantic_certainty NULL
derivation_kind
visibility_policy_id
system_start_revision
system_end_revision NULL
```

Evidence is attached through the normal provenance links. These relations create a partial ordering rather than forcing all events onto one artificial sequence.

The harness may derive safe closure such as `A BEFORE B` and `B BEFORE C`, therefore `A BEFORE C`, without inventing exact dates. Only relation types with defined algebra should participate, derived closure should be rebuildable, and contradictory strict-order cycles should block or flag a change set. Vague ordering remains vague.

### Story Cursors and "Current" State

"Current" is not a global database constant. A state query is evaluated relative to a timeline and a story cursor, usually an event/scene anchor. A campaign may maintain a default cursor for convenience and additional cursors for a split party or concurrent scenes.

```text
story_cursor
------------
id UUID
campaign_id
timeline_id
name
anchor_id
participants JSONB NULL
is_default
```

If a proposition cannot be proven active or inactive at the selected cursor because the partial order is insufficient, the answer should say so. It must not choose whichever assertion was inserted most recently.

### Multitemporal Knowledge

The model distinguishes three independent questions:

1. **content/valid time** — when the proposition says a state is true or an event occurred in the fictional world;
2. **stance/reveal time** — when a character, group, or institution believed, knew, suspected, or claimed that proposition;
3. **system/canonical time** — in which campaign revisions the accepted record existed.

For example, "Mira works for the Cult" can be content-valid since before session 1, established by the DM in canonical revision after session 15, learned by Rowan in session 19, and learned by the player group in session 22. The latter two are separate `knowledge` assertions with their own stance starts.

Operational timestamps such as `recorded_at` are retained for audit, but canonical revision ranges make historical queries reproducible even if several changes are committed close together.

## Retroactive Assertions, State Changes, and Retcons

A fact may be introduced long after the fictional time when it became true. In session 15, for example, the DM may establish that Mira has secretly worked for the cult since before session 1. Its proposition receives the old content-valid start; its accepted assertion begins at the new canonical campaign revision.

Two operations must not be conflated:

- **A story-state change** closes a proposition's fictional validity and begins another state, while both remain part of current canon.
- **A correction or retcon** system-ends/supersedes the old accepted assertion and inserts the replacement, possibly changing the canonical account of old story time.

For example, a revision after session 20 may supersede the reality assertion `Mira member_of Cult` with `Mira infiltrates Cult`, both content-valid before campaign start. Queries against the latest campaign revision return the infiltration; an `as_known_by_system_after_session_15` audit query can still reconstruct the prior accepted account.

Canonical rows should therefore be immutable after commit except for controlled system-ending metadata. Retraction, supersession, and interval correction are explicit change-set operations with reasons and evidence; destructive deletion is reserved for legally or operationally necessary data removal, not ordinary retcons.

## Timelines

Two concepts should be distinguished.

### Concurrent Story Threads

Events occurring simultaneously in different locations do not require separate timelines. They use overlapping anchors, partial-order relationships, and separate scene/story cursors on the same timeline.

### Alternate Histories / Branches

Literal alternate histories or time-travel branches should use explicit timeline records.

```text
timeline
--------
id UUID
campaign_id
name
parent_timeline_id NULL
branch_event_id NULL
properties JSONB
```

The schema preserves a parent and branch point, but inheritance and branch merging are intentionally outside the first release. Until inheritance semantics are implemented and tested, every accepted assertion/event is queried only from its explicit timeline plus an explicitly defined shared-history rule. The MVP should use one main timeline rather than pretend that branch behavior is complete.

## Events

Events are the narrative/history backbone. An accepted event describes something that happened in canonical reality; an adventure plan or an in-world allegation is a classified source/proposition, not a canonical event.

Possible shape:

```text
event
-----
id UUID
campaign_id
timeline_id
type
title
description
start_anchor_id NULL
end_anchor_id NULL
location_entity_id NULL
semantic_certainty NULL
visibility_policy_id
properties JSONB
system_start_revision
system_end_revision NULL
supersedes_event_id NULL
recorded_at
```

Event evidence is many-to-many, so singular source columns do not appear here. Event participants should be represented separately:

```text
event_participant
-----------------
event_id
entity_id
role
properties JSONB
```

Initial roles might include `actor`, `victim`, `witness`, `target`, `beneficiary`, `owner`, and `recipient`. Roles may later become a small validated catalog if query behavior requires it.

Example event:

> Rowan kills Deren in the Silver Stag while Mira watches.

Related propositions/assertions could capture:

```text
Rowan killed Deren
Deren has_status dead
Mira witnessed <event>
Deren located_in Silver Stag at the event
```

The event preserves the richer historical occurrence while assertions make important consequences easy to query. Extracted events and consequences should be presented as one dependency-aware review group. Accepting the event does not silently accept every model-inferred consequence; deterministic consequences may be auto-selected only under an explicit, tested policy and still appear in the committed change set.

## State Versus History

The database should preserve historical propositions/assertions rather than repeatedly overwriting mutable fields.

```text
Mira trusts Rowan      content-valid during interval A
Mira suspects Rowan    content-valid during interval B
Mira hates Rowan       content-valid during interval C
```

An `active_state(campaign_revision, timeline, story_cursor, mode, holder)` query/view computes the applicable assertions. A materialized current-state table may later cache that result, but it is rebuildable and never the sole source of truth.

This supports both "How does Mira feel about Rowan at this scene?" and "Why did Mira stop trusting Rowan?" If a split party has two incomparable scene cursors, the caller must select one; the insertion order of rows is not a substitute for story time.

## Relationship Qualifiers

Relationships often require nuance beyond a triple. `Mira --hates--> Rowan`, for example, may include an intensity and a human-readable note. JSONB is suitable for uncommon or evolving qualifiers.

Qualifiers are not an authorization mechanism. Visibility uses a typed policy, not a convention such as `{"public": false}`. Likewise, a frequently queried reason should become an evidence/derivation link to the relevant belief or event rather than remain only a stale prose string.

Fields that become heavily queried, validated, security-sensitive, or semantically important can later graduate into typed columns without requiring every possible story property to be anticipated.

## Provenance and Derivation

Every accepted assertion and event should retain one or more evidence links when evidence exists. Potential sources include an exact session/campaign document revision and span, another accepted event/assertion, a DM annotation, or a rules source. Imported adventure material can support a plan but must not support a claim that the plan occurred unless the DM explicitly promotes it.

A relational design should prefer typed link tables over an unconstrained polymorphic foreign key:

```text
source_reference
----------------
id UUID
document_chunk_id NULL
source_asset_revision_id NULL
event_id NULL
assertion_id NULL
dm_annotation_id NULL
start_offset NULL
end_offset NULL
quoted_text_hash NULL

CHECK exactly one source foreign key is populated

assertion_evidence             event_evidence
------------------             --------------
assertion_id                   event_id
source_reference_id            source_reference_id
role                            role
```

Roles can distinguish `direct`, `supporting`, `conflicting`, and `context`. A separate derivation edge records that an assertion was computed or inferred from other accepted records.

A model interaction is lineage, not sufficient evidence by itself. Store gateway/package version, provider/model, resolved task-profile/instruction/schema versions, structured inputs/results, source IDs/hashes, usage/cost/latency where available, and seed/parameters. Never store OAuth/API credentials or require hidden gateway state to interpret an accepted record. Accepted records still point to the campaign evidence the model interpreted.

This structure lets the harness answer both "Why does it say this?" and "Which conclusions depend on this retconned fact?" Evidence remains resolvable against immutable revisions even after the live Markdown file changes.

## Documents, Revisions, and Chunks

A file path is a mutable locator, not durable evidence. All imported Markdown/text should therefore be represented as a logical document with immutable revisions and revision-specific chunks. Optional binary source assets follow the same content-addressed revision principle but need not be implemented until a real adapter requires them.

```text
document
--------
id UUID
campaign_id NULL
corpus                         -- campaign or rules
logical_key
source_path
created_at
retired_at NULL

document_revision
-----------------
id UUID
document_id
content_hash
content_snapshot
title
document_type
authority_class
ruleset NULL
visibility_policy_id
source_path_at_ingest
source_metadata JSONB
parser_version
ingested_at
```

```text
document_chunk
--------------
id UUID
document_revision_id
ordinal
heading_path
start_offset
end_offset
page_start NULL
page_end NULL
content
search_vector
fts_config
chunker_version
metadata JSONB

embedding_profile
-----------------
id UUID
runtime_kind                   -- local or hosted
provider
model_name
model_revision
model_license NULL
dimensions
distance_metric
normalization
preprocessing_version
config_hash
enabled

chunk_embedding
---------------
chunk_id
chunk_content_hash
embedding_profile_id
embedding
created_at
```

An unchanged content hash makes ingestion idempotent. An edit creates a revision; it never mutates chunks cited by old assertions. Vector indexes contain only embeddings with compatible dimensions/distance/normalization profiles (for example through profile/dimension-specific partitions or indexes). A profile change creates a new projection rather than rewriting old vectors.

A serving corpus snapshot pins the selected head revision of every included logical document:

```text
corpus_snapshot
---------------
id UUID
campaign_id NULL
corpus
parent_snapshot_id NULL
ingestion_run_id
created_at

corpus_snapshot_document
------------------------
corpus_snapshot_id
document_id
document_revision_id
ordinal
```

The initial P1 relational boundary enforces these details in PostgreSQL rather than relying on callers:

- `campaign` corpus rows always have a campaign owner; `rules` rows may be global or campaign-owned for later house-rule/profile use. Scope is copied onto revisions, chunks, runs, snapshots, and membership rows so cross-campaign/cross-corpus links can be rejected before retrieval.
- Source paths are normalized, safe relative locators. A logical key and active path are unique within an owner/corpus scope, including the global-rules `NULL` owner case. Path-history rows retain old locators while the document identity remains stable.
- Revision numbers and exact UTF-8 SHA-256 content hashes are unique per logical document. PostgreSQL verifies the hash against the stored source snapshot, and database triggers reject revision update/delete attempts.
- Chunk offsets are zero-based, half-open character offsets into that exact revision. PostgreSQL verifies the copied chunk text and SHA-256 against the source span, derives a stored `tsvector`, and rejects update/delete attempts. Chunk authority/ruleset inherit the revision; a chunk visibility override may only narrow the parent policy.
- Snapshot membership pins one revision and ordinal per logical document, is append-only while the snapshot is a candidate, and becomes closed when activated. Candidate/active/superseded transitions and ingestion-run pins are constrained independently of any later vector index.

P1-01 defines these persistence guards only. P1-02 adds one transactional Library reconciliation service over a narrow read-only filesystem port:

- Callers select a configured **named source root** plus a normalized relative POSIX locator; absolute paths, traversal, backslashes, unknown roots, non-regular files, symbolic-link components, and files outside the opened root are rejected. The local adapter performs bounded descriptor-relative no-follow reads and exact strict UTF-8 decoding before persistence.
- A per-campaign/corpus PostgreSQL advisory lock serializes the bounded filesystem read and identity decision. Every attempt has a durable ingestion run; expected access/decoding failures terminate it safely without creating a document.
- Same-path/same-hash input reuses the exact revision. Novel same-path content records a `content_changed` path event and one revision. Returning to an already-known hash reuses that immutable revision while the path event records the new current content.
- A unique exact-hash source whose old locator is missing is an exact move and retains identity. If the original remains present, the copy becomes a distinct document with explicit duplicate IDs. Multiple exact missing candidates, or any missing active candidate for novel content, return `review_required` with stable candidate IDs and make no document/path/revision mutation.
- Files become retired only through the explicit root-scoped missing reconciliation command. Retirement retains the current locator/hash and every revision; a later same-path return restores identity and appends a revision only for genuinely new content.

P1-02 still does not parse Markdown, create chunks, activate serving snapshots, search, embed, invoke a model, or modify canonical campaign state. Those remain later P1/P2/P3 responsibilities rather than being hidden in source adapters.

A completed ingestion run may activate a corpus snapshot as soon as immutable chunks and lexical indexes are ready; P1 must not wait for an embedding runtime. A separate retrieval-index generation links that snapshot to an embedding profile and becomes `vector_ready` only after all required vectors exist. Queries/evals pin the snapshot plus retrieval-index generation (or explicit lexical-only mode), so narrative answers remain reproducible while sources are edited or vectors are rebuilt.

By default, the application assigns a logical document UUID on first ingestion and keeps a source registry in PostgreSQL containing path history and content hashes. An exact-content rename/move can therefore retain identity without modifying the Markdown. If a file is both moved and substantially edited and the match is ambiguous, ingestion asks for review rather than creating or merging documents silently. Optional front-matter IDs or an exportable sidecar manifest can be supported later for vault portability, but neither is required from the user.

A missing source marks the logical document retired but does not erase revisions or canonical facts derived from it. If edited/removed text was evidence for accepted state, ingestion emits a provenance-drift warning or proposed supersession; it never retracts canon automatically.

The snapshot can initially live in PostgreSQL because the expected Markdown corpus is small. It can later move to content-addressed object storage without changing revision identity. Chunk boundaries should follow headings and semantic blocks where practical, with a bounded overlap; exact offsets/page metadata preserve citation quality.

### Source Authority Classification

At minimum, campaign source revisions should distinguish:

```text
canon_note
raw_session_record
plan_or_adventure
reference_lore
player_handout
character_sheet
important_item_record
creature_or_bestiary_record
dungeon_or_encounter_brief
house_rule_or_ruling
```

Revision authority is typed separately from document shape: `canonical_claim`, `raw_record`, `preparation`, `reference`, `official_rules`, and `user_authored_rules`. `canonical_claim` means only that the source presents a claim about canon; it does not bypass the canonical change-set approval boundary. Initial ruleset labels are `dnd_5e_2014`, `dnd_5e_2024`, `system_agnostic`, and `other`.

Rules and bestiary sources should distinguish official/user-authored source, edition, book, and extraction provenance. Classification controls retrieval defaults, not automatic canonization. Even a `canon_note` produces structured changes only through approval; conversely, unstructured details in an approved narrative note remain retrievable without having to become propositions.

Plans and imported adventures are useful for preparation queries but are excluded from answers about what has actually happened unless explicitly requested. Mixed documents may apply a more restrictive authority/visibility override at section or chunk level; when uncertain, ingestion chooses the conservative classification and asks for review.

Campaign and rules corpora remain physically/logically filterable so an identically named campaign item and rules term cannot contaminate each other's result set.

## Information Classification and Access Control

Each request has an authenticated principal and an execution scope such as `dm`, `player:<id>`, or `npc:<id>`. Documents, accepted events, entities, assertions, generated artifacts, and saved model/tool runs carry or inherit a typed visibility policy. Initial policies can be simple:

```text
dm_only
all_campaign_players
explicit_audience
public
```

The MVP exposes one DM principal. That scope may retrieve all accepted campaign facts, character/creature/item profiles, preparation artifacts, DM-only map layers, puzzle solutions, and narrative needed for the request. It should still assign visibility labels now so future player/NPC access adds policy evaluation rather than retrofitting secrecy onto unlabelled data.

Authorization filters run through one centralized policy layer before full-text search, vector search, graph expansion, reranking, and context construction. Before enabling non-DM accounts, PostgreSQL row-level security or an equivalently tested database access boundary should provide defense in depth rather than relying on filters scattered across handlers. More restrictive child records override inherited visibility. Counts, snippets, citations, model logs, caches, and error messages must not reveal excluded material. NPC semantic knowledge is an additional assertion filter, not a replacement for access control. New extracted/generated records inherit the most restrictive relevant source policy by default. Player map/handout exports are produced by an explicit visibility transformation and must fail closed if an unknown feature/layer lacks a safe classification. Deliberately revealing a fact is an explicit human declassification/publication change, and a lower-scope answer may cite only evidence available at that scope.

Retrieved Markdown is untrusted data, including text that resembles model instructions. It is delimited and labelled as evidence, never allowed to redefine the tool policy, principal, or approval rules. Model tools remain read-only or proposal-only, file/URL ingestion is path-allowlisted, and any future PDF/HTML parser runs with bounded resources.

## Rules, Creature Corpus, and House-Rule Precedence

The rules and creature corpora should explicitly distinguish editions such as `5e2014` and `5e2024`. A campaign selects a rules profile rather than relying on a prompt default.

```text
rules_profile
-------------
id UUID
campaign_id
name
default_ruleset
system_start_revision
system_end_revision NULL

rules_profile_source
--------------------
rules_profile_id
document_or_collection_id
precedence
enabled
system_start_revision
system_end_revision NULL
```

A profile can place accepted campaign house rules/rulings above selected official books while retaining both sources. It also selects authorized creature collections used for stat-block lookup and encounter generation; a generated variant pins the exact source profile/version it extends. Retrieval filters to the profile before ranking unless the user explicitly requests a cross-edition comparison. An answer states whether it is quoting an official rule, applying a house-rule override, reporting a prior table ruling, or comparing editions; it cites each source rather than silently blending text.

Each rule or creature chunk should preserve `book`, `chapter`, `section`, `heading_path`, `ruleset`, source path, PDF page where available, and extraction revision. Complete creature profiles are structured projections over those immutable sources, not uncited model memory. Named mechanics favor lexical retrieval, while natural-language questions also use semantic retrieval. Access policies still apply to copyrighted/user-provided source material, including generated excerpts and player-facing answers.

## Retrieval Architecture

Retrieval should be hybrid, scope-aware, and authority-aware rather than vector-only.

```text
question + authenticated principal + explicit/default query scope
    |
    v
resolve campaign revision, corpus snapshot/index generation,
timeline/cursor, principal, corpus, and rules profile
    |
    v
query analysis and entity/term/intent resolution
    |
    v
construct bounded scope; apply authorization / authority / edition filters
    |
    +--> accepted structured state / graph lookup
    |
    +--> lexical full-text search
    |
    +--> vector similarity search
    |
    v
candidate fusion, deduplication, optional reranking
    |
    v
provenance and temporal expansion
    |
    v
context compiler
    |
    v
deterministic response or LLM answer with citations / explicit abstention
```

The caller may omit scope fields only when the campaign has visible defaults; the resolved values are returned with the answer. The model never chooses a broader audience, another campaign, or additional rules corpus by itself.

A simple rank-fusion method such as reciprocal rank fusion is a better baseline than assuming lexical and vector scores are calibrated. Reranking is optional and occurs only after hard filters. Exact aliases, named rules, and identifiers receive lexical boosts. Retrieval logs preserve query scope, campaign revision, index/model versions, candidate IDs/scores, selected context, latency, and final citations for evaluation and debugging.

Examples:

```text
"Is Deren dead?"
-> accepted reality state at the selected story cursor

"Who was the wizard interested in black candles?"
-> entity resolution + lexical/semantic campaign evidence

"How does Booming Blade work?"
-> lexical-heavy retrieval within the active rules profile

"Why does Mira distrust Rowan?"
-> perspective assertion + derivation/evidence event + selected narrative chunks

"What is Rowan's passive Perception, and who carries the seal?"
-> character-sheet snapshot + accepted possession state + item profile

"Generate a crypt dungeon and hard guardian encounter for this party."
-> grounded preparation context + constrained dungeon/encounter specs + deterministic generators/validators
```

For factual campaign questions, accepted structured state has priority; narrative evidence explains and fills unstructured gaps but is labelled by authority class. A plan is not evidence that an event occurred. Conflicting accepted assertions or source text are surfaced. The system returns "unknown" or "not ordered precisely enough" when the authorized evidence cannot support a concise answer.

## Context Compilation

The harness, rather than the model, determines what information enters a model call. Context is typed, authorized, labelled, and task-specific rather than one undifferentiated text blob or one universal DTO with every field every workflow might need.

Preparation workflows share only a small provenance/scope wrapper:

```text
GenerationContextEnvelope<T>
----------------------------
schema_version
context_kind
payload_schema_version
campaign_revision_id
corpus_snapshot_id
rules_profile_id NULL
visibility_scope
source_references[]            -- immutable citations and authority labels
payload_hash                   -- hash of canonical payload representation
payload T
```

The envelope is persisted or content-addressed with the generation run and artifact lineage. Its fields answer which authorized state and sources influenced a run; they do not attempt to represent all possible domain inputs. Unknown envelope or payload versions fail explicitly.

Each workflow owns a narrow payload schema and context-selection policy. Initial and future examples include:

- **`DungeonGenerationContext`:** relevant location lore/geography, themes, factions, plot hooks, requested tone, coarse party level/capacity constraints, and selected prior artifact references;
- **`EncounterGenerationContext`:** pinned party mechanics/playstyle, rules assumptions, authorized creature candidates, requested difficulty/experience, dungeon room geometry, pacing/resource pressure, and selected lore;
- **`SessionPrepContext`:** current location/participants, recent accepted events, unresolved threads, prepared artifacts, and likely rules;
- **`NPCSceneContext`:** that NPC's goals, relationships, knowledge, beliefs, public persona, relevant events, and permitted secrets.

Create a payload only when its workflow is implemented. Do not make these subclasses of a growing all-purpose field set, and do not put encounter-only mechanics into dungeon context merely because both are preparation. Question answering and session extraction likewise use their own task packet contracts; they may compose the same small scope/provenance value objects but are not forced into `GenerationContextEnvelope`.

The available source material can include accepted reality at a selected cursor, holder-specific beliefs/knowledge/claims, events and temporal relations, profile fields, preparation artifacts, narrative excerpts, rules excerpts, conflicts, and unknowns. A task-specific compiler selects only the applicable subset, applies per-section token budgets, deduplicates overlap, expands provenance by a bounded number of hops, and preserves enough neighboring text to avoid misleading fragments. Plans and adventure material are omitted from historical-fact packets unless the intent asks for preparation or comparison.

DM-only secrets are included only for a DM principal and only when relevant; they are not a default dump. The model receives the compact task packet instead of unrestricted database or vault access. Generated factual claims cite supplied packet IDs, and post-generation checks verify that citations existed and were authorized. Semantic entailment still requires evaluation rather than a citation-presence check alone.

## LLM-Friendly Interface

The raw schema should not be the API exposed to a model. All operations use versioned JSON schemas, server-supplied campaign/principal scope, bounded result counts, and opaque IDs.

Read operations may include:

```text
resolve_entity(...)
get_state(... timeline, as_of, mode, holder ...)
get_event(...)
search_campaign_memory(... authority_classes ...)
search_rules(... rules_profile ...)
explain_provenance(...)
find_predicate(...)
get_party_generation_snapshot(...)
search_creature_profiles(...)
get_prep_artifact(...)
```

Model write operations are deliberately named and implemented as proposals:

```text
propose_entity(...)
propose_event(...)
propose_assertion(...)
propose_temporal_relation(...)
propose_predicate(...)
propose_supersession(...)
propose_retraction(...)
```

Canonical proposal tools can write only to the current draft change set. Generation tools operate in a separate draft preparation workspace:

```text
set_dungeon_brief(...)
add_room(...)
connect_rooms(...)
add_dungeon_feature(...)
generate_layout(...)
validate_dungeon(...)
regenerate_component(...)
propose_encounter(...)
scale_encounter(...)
validate_encounter(...)
```

The model supplies constrained intent to these tools; the server performs geometry, IDs, rules arithmetic, validation, rendering, and asset writes. Draft/approved preparation artifacts still cannot mutate campaign canon. There is no model-facing `record_event`, `assert_fact`, arbitrary SQL/file write, artifact approval, or `commit` tool. The server ignores any model-supplied attempt to widen campaign, audience, source, or rules scope.

A separate authenticated human API supports item review, validation, and `commit_change_set`. The harness converts accepted operations into immutable relational records, revision ranges, provenance links, and projections in one transaction. Idempotency keys prevent retries from duplicating proposals or commits.

The initial model adapter is the private `pi-ai` gateway described above. TypeBox schemas sent through `pi-ai` are generated from or contract-tested against the Python service's versioned JSON schemas. The gateway propagates cancellation and bounded streams; the Python harness owns scope, tool authorization/execution, output truncation, retries at the workflow boundary, idempotency, durable run state, and deterministic validation. Optional Pi/MCP adapters call the same application API and gain no additional authority.

## Session-End Extraction Pipeline

A single giant extraction prompt is unlikely to be comprehensive or reviewable enough. The close-session workflow should be decomposed conceptually:

```text
immutable session-note revision + selected base campaign revision
    |
    v
source classification and entity/alias resolution candidates
    |
    v
event and participant extraction
    |
    v
proposition / state / relationship / thread extraction
    |
    v
temporal anchor and relation normalization
    |
    v
knowledge / belief / claim / reveal extraction
    |
    v
retcon, conflict, and continuity analysis
    |
    v
evidence-linked draft change set
    |
    v
deterministic validation
    |
    v
grouped DM review and edits
    |
    v
atomic canonical commit
```

These stages are not autonomous agents. They can be several structured model calls plus deterministic code, and early versions may combine stages that share context. Each output references source spans and stable candidate IDs so later stages do not resolve the same name independently.

The review should be organized around human-sized event groups, not a flat list of triples. It should show before/after state, source evidence, inferred versus explicit items, dependencies, conflicts, and ontology additions. Extraction confidence can sort the review queue but never auto-canonize an item. Rejected facts remain available in the immutable narrative source without polluting accepted state.

Initial campaign bootstrap may use large, source-grouped batches and expedited approval for trusted DM-authored notes, but it still produces an explicit canonical revision and audit trail rather than treating every imported sentence as fact.

The same note revision and extraction configuration should resolve to an existing run/change set unless the DM explicitly requests a new run. This makes retries safe and lets different model/prompt versions be compared.

## Change Sets and Canonical Revisions

The approval boundary deserves first-class records.

```text
campaign_revision
-----------------
id UUID
campaign_id
parent_revision_id NULL
sequence_number
committed_change_set_id
summary
summary_origin             -- human, model_draft_edited, deterministic
committed_by
committed_at

change_set
----------
id UUID
campaign_id
base_campaign_revision_id
state                    -- draft, in_review, committed, abandoned
created_by
extraction_run_id NULL
idempotency_key
created_at

change_item
-----------
id UUID
change_set_id
operation
candidate_payload
source_references
extraction_confidence NULL
depends_on_item_ids
review_state             -- pending, accepted, edited, rejected
validation_messages
review_note NULL

change_set_source
-----------------
change_set_id
document_revision_id
role
```

An extraction run may contain several model/tool interactions, each linked to its exact structured inputs and stage; a change set may likewise use several source revisions. Candidate payloads may use change-set-local IDs so a proposed event, entity, and related assertions can be reviewed together without inserting placeholder canonical rows. Schemas are versioned and validated before review and again before commit.

A commit uses optimistic concurrency against `base_campaign_revision_id`, revalidates accepted dependencies, and atomically creates exactly one child campaign revision. If the base is stale, the change set is rebased/revalidated rather than silently applied. Partial approval is allowed only when dependencies remain valid. Manual edits and imports use the same revision path, optionally with an expedited review, so the audit history has no privileged side door.

Canonical queries default to the campaign head but can target an older revision. This provides reproducible answers and clearly separates "what was true in the story" from "what the harness accepted at that point in its own history."

### Canonical Change Log

PostgreSQL is the default authoritative change log. Every committed revision stores a concise summary—drafted deterministically or by a model and editable by the DM—while the linked change set preserves the complete accepted/rejected item history, before/after payloads, evidence, validation messages, reviewer, and timestamps.

The CLI/API should expose at least:

```text
dm history
dm show-revision <revision-id>
dm diff <old-revision> <new-revision>
```

Optional exporters may render committed revisions as append-only Markdown or JSONL. A repository integration may also commit that generated log to Git. Export is a rebuildable, idempotent projection from PostgreSQL—not a second canonical write path—and an export failure does not roll back a valid database commit.

## Validation

The deterministic layer should validate proposals wherever semantics are defined. Checks include:

- campaign, timeline, canonical revision, and visibility-policy integrity;
- exactly one typed entity/event/literal proposition object;
- predicate subject/object, cardinality, inverse, symmetry, and exclusivity rules;
- duplicate or ambiguous entity/alias candidates;
- invalid intervals and strict temporal-order cycles;
- event/assertion references to unaccepted dependencies and cyclic derivation chains;
- overlapping incompatible values for predicates explicitly marked functional/exclusive;
- explicit positive/negative contradictions at overlapping story times and the same perspective;
- source authority mismatch, such as treating a plan as an occurred event;
- stance-holder requirements, overlapping `knowledge`/`unaware` intervals, and suspicious knowledge before any supported reveal;
- inaccessible evidence or attempted audience broadening;
- stale base campaign revisions and duplicate idempotency keys;
- rules-profile, sourcebook, and edition mismatch;
- character-sheet/item schema, entity-type, and ruleset mismatch;
- stale or unexplained computed sheet values;
- preparation-artifact schema/version/lineage and missing pinned generation inputs;
- disconnected dungeon areas, invalid transitions, overlaps, blocked paths, or unsatisfied topology constraints;
- unsolvable lock/key, clue/gate, secret-route, or puzzle dependencies;
- DM-only map/puzzle/encounter data leaking into player exports;
- generated-asset hash/media/dimension mismatch;
- incomplete or ruleset-incompatible creature stat blocks;
- encounter-budget arithmetic, party-snapshot, room-capacity, creature-size, and terrain mismatch;
- missing puzzle solution/clue/failure/reset data;
- missing evidence for an extraction presented as explicit.

The knowledge store is open-world and narrative predicates do not all have formal negations, so "contradiction" is not a generic string comparison. Hard canonical structural/security errors block commit; hard dungeon/encounter errors block artifact approval/export as ready-for-play. Semantic concerns can be warnings that the DM overrides with a recorded rationale. Authorization failures cannot be overridden through a model proposal.

The model proposes meaning; the harness enforces the consistency it can define and makes the remaining uncertainty visible.

## Ontology Growth

The project should avoid designing a giant ontology before real campaign data exists. Start with a modest, documented predicate vocabulary.

When a new concept appears, the harness can:

1. search existing predicates and show their definitions;
2. reuse a semantically correct predicate;
3. preserve the idea only in narrative memory;
4. keep an uncommitted free-form candidate in the change set; or
5. propose a versioned predicate and dependent assertions for DM approval.

A merely similar predicate should not be reused to make validation pass. Usage examples and counterexamples can be stored with predicate definitions and included during extraction. Periodic ontology cleanup uses explicit merge/deprecation change sets so old assertions remain interpretable.

## What Not to Add Initially

The first version should avoid several technologies until an observed problem justifies them.

### LangChain / LangGraph

Useful later for complex branching workflows, retries, checkpoints, and human-in-the-loop orchestration.

Initially, direct Python code will be easier to understand and debug.

### `@earendil-works/pi-agent-core`

This package is a credible later replacement for custom open-ended agent-loop code: it provides stateful message/tool execution, parallel/sequential tools, streaming events, cancellation, steering, and follow-ups on top of `pi-ai`. Do not add it to the initial gateway. The first workflows are explicit bounded pipelines, and keeping orchestration/durable state in Python avoids split-brain sessions. Reconsider when a general conversational mode demonstrably needs repeated dynamic tool turns or steering; adoption requires contract tests, a clear state-persistence boundary, and no direct approval/commit tools.

### Autonomous agents

Useful only when the system begins proactively preparing or operating parts of the campaign.

They add nondeterminism and are unnecessary for explicit query, constrained generation, review, and session-close workflows. A deterministic layout engine plus bounded model calls is not an autonomous agent.

### Multiple specialized agents

Potential future roles include:

- rules specialist;
- continuity reviewer;
- NPC portrayal assistant;
- campaign planner.

Do not introduce them merely because roles can be named. Add them when evaluations show one model/context cannot perform the necessary tasks reliably.

### Universal Generation Context DTO

Do not create one `GenerationContext` with optional fields for every current and imagined workflow. It would become a high-churn coupling point and make authorization, validation, and reproducibility harder to reason about. Reuse only the small envelope/provenance values; dungeon, encounter, session-preparation, and future scene workflows own strict versioned payload contracts.

### Full Encounter Engine Package

Dungeon compilation already has a clear pure transformation boundary. Encounter design may not: model composition, campaign tone, party data, rules sources, and preparation workflow surround a smaller deterministic mechanics core. Keep it in the Workbench initially and extract only a measured cohesive `encounter-mechanics` package if P8 demonstrates value.

### Neo4j or Another Graph Database

PostgreSQL can store graph-shaped proposition content and perspective assertions and can perform recursive graph queries at campaign scale.

A dedicated graph database becomes attractive only if measured multi-hop traversal becomes central and SQL/projections become awkward or slow. Entities and events can later become projected nodes, with propositions/assertions becoming labelled edges or reified stance nodes. That projection is derived from PostgreSQL rather than a second canonical write path.

### Dedicated vector database

pgvector should be adequate for an individual campaign and rules corpus.

Qdrant or similar can be added if vector search scale, filtering, reranking, or latency becomes a demonstrated limitation.

### Local Chat-LLM Infrastructure

Can be introduced for privacy, cost, offline use, or latency, but should not block the initial architecture. This deferral does not include P2's small local CPU embedding candidate, which is a separate retrieval runtime rather than a conversational model server.

### Large SPA or Polished UI

A thin first-party server-rendered web UI is initial scope because prompt entry, image paste/upload, streaming/cancellation, model/task-profile selection, review, map preview, and downloads are materially easier there than in a CLI. Start with FastAPI templates plus small HTMX/vanilla-JavaScript behavior and SSE; defer a large SPA, mobile polish, and elaborate visual design until workflows stabilize.

### Public or MCP Service Exposure

The browser reaches only the authenticated Python application on the intended private network; the Node model gateway is internal-only. No MCP listener is needed. Add a local/private MCP or Pi-extension adapter only when an external host benefits from it; never expose approval/commit tools or publish the model gateway merely to support an integration.

### Combat Simulator

Encounter design, complete stat blocks, map placement, tactics, and party-aware difficulty are core initial capabilities. A live simulator/tracker for initiative, movement, current HP, conditions, and turn-by-turn automation is not needed while the human DM remains the game runner.

### Regional/World and Illustration-First Maps

Regional/world maps are out of scope. Polished illustrated dungeon textures are optional later enhancements. The initial renderer must prioritize valid, readable, reproducible tactical grids and must never let generated artwork redefine wall/door geometry.

### Automatic Markdown rewriting

Initially, the system should propose rather than silently rewrite human-authored campaign material.

Later, approved changes can be reflected into Markdown with diffs and version control.

### Continuous transcript ingestion

Potentially valuable for future real-time assistance.

Initially, end-of-session ingestion avoids noise and sharply reduces the problem of determining what is canon.

### Queues, Caches, and Microservices

Do not introduce operational infrastructure before workloads require it. One Python domain process, the narrow Node model gateway, and one database are preferable while the domain model is evolving. Long-running ingestion/model work can first use synchronous commands or a PostgreSQL-backed run/job record with leasing and retries; a separate broker is justified only by demonstrated concurrency or reliability needs. Any cache is a revision-keyed, rebuildable projection.

## Evals

An evaluation suite should appear before retrieval and extraction behavior becomes difficult to change. Fixtures pin a document-revision set, campaign revision, query scope, rules profile, and expected answer/source set.

Representative suites should cover:

- **structured state:** current location/status, functional-predicate changes, character-sheet fields, and important-item possession/profiles;
- **perspective:** reality versus belief, claims, player knowledge, and character knowledge;
- **temporal:** exact, relative, simultaneous, retroactive, retconned, and genuinely incomparable facts;
- **entity resolution:** aliases, collisions, renamed entities, and merge history;
- **hybrid retrieval:** exact mechanics/names and vague narrative recollections, compared across pinned local/hosted embedding profiles and against lexical-only fallback;
- **model/task profiles:** capability validation, schema/tool success, latency/usage, objective task checks, fallback behavior, and blinded DM preference across candidate models/effort levels;
- **context contracts:** envelope scope/provenance/hash stability, strict domain payloads, rejection of unrelated/unknown fields, context relevance, and no model-driven scope broadening;
- **package boundaries:** independent `dm_dungeon` tests plus a dependency rule forbidding Workbench/database/web/retrieval/provider imports; encounter extraction requires measured evidence rather than symmetry;
- **source authority:** plans versus occurred events, canon notes versus rumors, and official versus house rules;
- **extraction/review:** event, assertion, reveal, thread, retcon, and evidence-span precision/recall;
- **security:** DM-only facts, unauthorized snippets/citations/counts, prompt injection in documents, and cross-campaign isolation;
- **answer behavior:** citation correctness, unsupported-claim rate, conflict disclosure, and appropriate abstention;
- **dungeon topology:** required connectivity, loops/branches, vertical links, gating solvability, stable targeted regeneration, and deterministic seeds;
- **dungeon geometry:** non-overlap, aligned walls/doors/stairs, pathfinding, room/corridor capacity, grid scale, and bounds;
- **render/export:** deterministic SVG snapshots, PNG/Roll20 dimensions, exact one-inch PDF scale, Letter/A4 tiling/overlap/registration, low-ink style budgets, and DM/player-layer secrecy;
- **creature profiles:** complete stat blocks, source/edition provenance, generated-variant lineage, and schema validation;
- **encounters:** official difficulty baseline, party/playstyle adjustments, map fit, scaling variants, pacing, and complete combat/noncombat packages;
- **puzzles/noncombat:** solution/clue/hint/failure/reset completeness and player-safe output;
- **operations:** idempotent ingestion/extraction/generation, stale change-set handling, index/asset rebuilds, and backup restoration.

Example questions include:

```text
Who currently knows the identity of the killer?
What did Mira believe before and after session 19?
When did Mira begin working with the cult, and when did the DM establish it?
Why does Bran distrust Salazar?
Where was the seal last seen on this story thread?
Was the planned ambush ever actually carried out?
What are the 2024 hiding rules under this campaign's house rules?
How does that differ from 2014, and which sources support each answer?
Generate a seeded two-floor crypt with a loop, a gated objective, and a secret bypass.
Can every required room be reached, and can the key be obtained before its lock?
Render player/DM maps, prove the clean output contains no secret-door metadata, and verify tiled print pages align at one-inch grid scale.
Generate and then scale a hard guardian encounter for this pinned party snapshot.
Does every creature have a complete stat block, and does the encounter fit its room?
```

Track retrieval source recall, embedding/index/query latency and memory, answer correctness, citation precision, unsupported-claim rate, per-task model/schema/tool success, blinded DM preference, extraction precision/recall, average DM edits/rejections per accepted change, dungeon-generation success/repair rate, property-validation failures, encounter arithmetic accuracy, artifact approval/edit rate, export correctness, leakage failures, latency, and model/embedding cost. Security leakage has a zero-tolerance acceptance target; other quality/latency targets can be set after a baseline on real material.

Retrieval, schema, prompt, model, chunking, or embedding changes run against the frozen suite. This is more valuable to reliability than adding model or agent complexity.

## Suggested Delivery Slices and Initial Milestone

Build the system as vertical slices rather than implementing the entire ontology before a question can be answered. The first usable product is a model-independent Dungeon Studio; grounding, model assistance, encounters, and campaign-memory precision layer onto the same Workbench afterward. Canonical revision work may proceed in parallel, but no structured canonical write can ship before that boundary exists.

### Slice 0: Workbench Foundation and Boundary Scaffold

- scaffold the Python application/CLI/test environment and leave room for a later `uv` workspace member;
- establish the single-process modular-monolith composition root and feature-module dependency rules;
- add PostgreSQL, authentication, structured logging, and health/contributor workflows;
- do not create empty future feature or encounter packages.

### Slice 1: Pure Dungeon Engine

- add an independently packaged in-process dungeon workspace member;
- define versioned dungeon brief/topology/layout schemas using synthetic fixtures;
- validate topology, gating, geometry, pathfinding, scale, and visibility;
- generate seeded orthogonal layouts without an LLM or database;
- render deterministic DM/clean SVG/PNG, low-ink exact-scale tiled PDF, and Roll20 image/grid metadata;
- prove targeted regeneration while preserving locked components and enforce dependency-isolation tests.

### Slice 2: Model-Independent Dungeon Studio

- add the platform-owned content-addressed `AssetStore` and generic preparation-artifact lifecycle;
- persist immutable dungeon versions, generation inputs, diagnostics, assets, lineage, and human approval-for-play;
- add shared CLI/API services and a thin authenticated Dungeon Studio for import/create, validate, preview, compare, lock/regenerate, export, and approve;
- make the full deterministic workflow useful without a model provider or campaign ontology.

### Slice 3: Campaign Library, Revision Boundary, and Domain-Specific Context Bridge

- ingest classified campaign/rules/creature material into immutable documents/revisions/chunks;
- provide filtered lexical retrieval and exact citations before adding embeddings;
- establish campaign revisions, draft change sets, human review, and atomic commit before any structured profile/rules/generated fact can enter canon;
- define the small `GenerationContextEnvelope` plus the first narrow `DungeonGenerationContext` payload and context inspector;
- pin selected source authority, visibility, campaign/corpus/rules scope, citations, and payload hash with each run;
- add semantic retrieval only when evals demonstrate improvement over lexical fallback.

### Slice 4: Grounded Model-Assisted Dungeon Studio

- add the private pinned-`pi-ai` gateway, credentials boundary, task profiles, and model settings;
- compile authorized campaign context into `DungeonGenerationContext` rather than a universal generation DTO;
- let the model propose typed brief/topology intent and bounded repairs while the pure package owns mechanics;
- integrate streaming, cancellation, durable model lineage, diagnostics, and model-assisted regeneration into the existing Dungeon Studio.

### Slice 5: Party-Aware Encounter Studio

- normalize authorized creature sources and synthetic/selected party profiles into pinned inputs;
- define a separate `EncounterGenerationContext` focused on party mechanics, creature sources, difficulty, geometry, and resource pressure;
- generate combat, social, exploration, puzzle, trap, hazard, and mixed packages;
- calculate/validate difficulty, stat completeness, type-specific completeness, and dungeon fit deterministically;
- begin as a Workbench feature and decide after measured P8 work whether only a narrow `encounter-mechanics` package merits extraction.

### Slice 6: Structured Chronicle and General Ask

- extend the existing revision/review boundary with entities/aliases, predicates, propositions/assertions, events, basic anchors, evidence, and profile review;
- support reality/belief/knowledge/claim and sheet/item questions at a selected cursor;
- extend task-specific context compilation and the shared web shell for general cited campaign/rules questions.

### Slice 7: Session-Close Assistance

- generate evidence-linked change sets from a session-note revision and prepared-artifact usage;
- group proposed events, consequences, reveals, thread/dungeon changes, and retcons;
- support model-run comparison, deterministic validation, and atomic human commit;
- expand the eval suite with real review and generation outcomes.

Security, secrecy, eval, backup, and restore checks move left into every persisted/user-visible slice; the final operations phase remains an aggregate release gate rather than the first time those concerns are tested.

A useful first release should support a flow resembling:

```text
dm campaign init

dm ingest ./campaign --authority canon_note --visibility dm_only
dm ingest ./characters --type character_sheet --visibility dm_only
dm ingest ./important-items --type important_item_record --visibility dm_only
dm ingest ./bestiary --type creature_or_bestiary_record --ruleset 5e2024
dm ingest-rules ./rules --ruleset 5e2024

dm dungeon generate --brief crypt-brief.md --seed 1842
dm dungeon validate <dungeon-version-id>
dm dungeon render <dungeon-version-id> --variants dm,player
dm dungeon export <dungeon-version-id> --format print-pdf
dm dungeon export <dungeon-version-id> --format roll20
dm encounter generate --dungeon <id> --party main --difficulty hard
dm prep approve <artifact-version-id>

dm serve  # exposes the authenticated first-party UI on the configured private interface
# In the browser: connect ChatGPT Codex by device code, choose task profile, then ask:
#   Who knows that Aldric murdered the king as of the current scene?
#   What are the hiding rules under the main campaign rules profile?

# Direct/model-assisted CLI paths remain available:
dm search "Aldric murdered the king" --as-of current
dm ask "What are the hiding rules?" --task-profile rules_answer

dm close-session session-12.md          # returns a draft change-set ID
dm review <change-set-id>
dm commit <change-set-id>
dm history
```

Initial scope limits should be explicit:

- one exposed campaign and one main timeline, while retaining campaign/timeline keys;
- a DM principal only, while storing/enforcing visibility labels;
- event/scene-relative chronology and table-session markers only; no custom-calendar adapter, date arithmetic, branch inheritance, or complete temporal algebra;
- a small controlled assertion-mode and predicate vocabulary;
- square-grid, practical orthogonal dungeon floors with a default five-foot cell; regional/world maps and illustration-first generation are excluded;
- renderer-neutral dungeon packages with deterministic SVG, DM/clean PNG, low-ink exact-scale tiled PDF, and Roll20-compatible exports; no direct Roll20 automation;
- complete creature stats and combat/noncombat encounter preparation, but no live initiative/HP/token synchronization;
- no nested epistemics, transcript stream, automatic Markdown rewriting, or autonomous actions;
- a thin authenticated web UI plus CLI, with synchronous/API-triggered work and durable run records but no external queue;
- a private Node `pi-ai` gateway, but no initial `pi-agent-core`, Pi-extension, or MCP dependency.

The milestone is acceptable when:

1. repeated ingestion creates no duplicate revisions/chunks and every quoted answer resolves to an immutable source span;
2. plans cannot answer "what happened," DM-only data cannot enter a lower-scope packet, and rule editions/overrides are labelled;
3. structured questions distinguish reality from holder knowledge/belief and evaluate state at an explicit/default story cursor;
4. insufficient temporal order or evidence yields a clear unknown/conflict rather than a guess;
5. closing a session changes no canonical query result before commit;
6. approved items commit atomically, every revision has a readable summary and detailed audit record, rejected items remain only in narrative/run history, and an old campaign revision remains queryable;
7. character-sheet, creature, and important-item queries identify the source snapshot and distinguish source-reported from computed/generated/story state;
8. the independently runnable `dm_dungeon` package reproduces a connected, non-overlapping, tactically usable multi-floor layout from the same pinned brief/seed/version, and targeted regeneration preserves locked component IDs;
9. lock/key, clue/gate, secret-route, stair, and pathfinding validations block unusable dungeon approval;
10. DM/clean PNG and Roll20 exports have correct grid metadata; Letter/A4 PDFs print at one inch per five-foot square with low-ink styling, calibration, page overview, overlap/cut/registration marks, and stitchable alignment; clean assets contain no DM-only secrets or puzzle solutions;
11. combat encounters use a pinned party/playstyle snapshot, deterministic rules baseline, complete creature stat blocks, room-fit checks, and explainable scaling variants;
12. social/exploration/puzzle/trap/hazard packages contain type-appropriate goals, clues/counterplay, outcomes, and player-safe material;
13. approving/using preparation artifacts changes no canonical campaign result until session outcomes are reviewed and committed;
14. indexes and rebuildable render assets can be regenerated, and a database/source/approved-asset backup can be restored without losing citations or artifact lineage;
15. the web UI can authenticate the DM, complete device-code model login without exposing tokens, select a versioned task profile, stream/cancel a cited answer with an optional pasted image, and remain usable for deterministic Dungeon Studio plus lexical/administrative operations when the gateway or embedding runtime is unavailable;
16. dungeon and encounter runs pin the same small envelope mechanism but distinct strict payload schemas, and no all-purpose context object or speculative encounter-engine package has been introduced.

If this foundation remains reliable over several real sessions, scene compilation, proactive continuity checking, player-safe views, NPC interaction, live transcript support, and more autonomous campaign machinery can be added without replacing the core model.

## Confirmed Initial Product Decisions

1. **Canonical boundary and logging:** approved PostgreSQL records are the structured canonical projection; Markdown remains lossless narrative/evidence and is not automatically rewritten. PostgreSQL revision/change-set history is the default log, including a readable summary for every commit. Optional Markdown/JSONL export and optional Git integration are derived outputs.
2. **Access timing:** the initial product is DM-only. It can use complete supplied character sheets, backstories, important-item profiles, and DM-only campaign knowledge. Visibility labels remain in the schema for later player/NPC views, but multi-user authentication is not an MVP requirement.
3. **Campaign time:** no custom calendar or date arithmetic is needed initially. Event/scene-relative order, session markers, and unknown/approximate chronology are sufficient; raw fictional dates are preserved for future interpretation.
4. **Model integration and UI:** the DM assistant is the independent host with a first-party thin web UI and CLI. A private Node gateway uses pinned `@earendil-works/pi-ai` for ChatGPT Codex OAuth and other provider/model transports; credentials never leave its dedicated store. Python owns task profiles, bounded workflows, tools, context policy, validation, and durable state. `pi-agent-core`, Pi extensions, and MCP are deferred until a measured external/open-ended-loop need.
5. **Embeddings:** `pi-ai` is not an embedding runtime. Lexical retrieval is independently useful; P2 evaluates a versioned local CPU embedding adapter first and keeps hosted embeddings behind separate credentials/profiles. Vectors remain rebuildable pgvector projections.
6. **Source identity:** users do not need to add IDs to Markdown. The default PostgreSQL source registry assigns IDs and tracks path/hash history. Optional front-matter IDs or a sidecar export can be added later if vault portability requires them.
7. **Dungeon-first map scope:** practical square-grid dungeon/floor generation is a primary capability. Regional/world maps are excluded. The LLM authors briefs/topology through primitives; deterministic code owns exact layout, validation, and rendering.
8. **Map outputs:** canonical geometry is renderer-neutral; SVG is the deterministic internal/optional vector renderer, PNG is the primary web/Roll20 output, and low-ink tiled Letter/A4 PDF at one inch per five-foot square is the core print output.
9. **Encounter scope:** combat and noncombat/puzzle encounters are first class. They include complete authorized/generated creature stat blocks and deterministic party/playstyle-aware difficulty evaluation. Live combat tracking remains excluded.
10. **Workbench organization:** users get one web/CLI Workbench organized into Library, Chronicle, Profiles, Preparation/Dungeon Studio/Encounter Studio, Session Desk, and Assistant feature areas. These are module and workflow boundaries, not services.
11. **Dungeon package boundary:** the deterministic dungeon kernel is an independently tested Python workspace package loaded in the Workbench process. It owns schemas, topology/layout, validation, rendering, and export, and cannot depend on Workbench persistence, retrieval, UI, or model orchestration.
12. **Context contracts:** generation shares a small versioned envelope for scope/provenance/visibility/citations/hash, while `DungeonGenerationContext`, `EncounterGenerationContext`, and future task payloads remain separate narrow schemas. There is no universal all-purpose `GenerationContext` payload.
13. **Encounter extraction:** encounter orchestration starts inside the Workbench. Extracting a narrower `encounter-mechanics` package is conditional on measured cohesion/reuse during P8; an `encounter-engine` package is not an initial commitment.
14. **Shared assets and UI:** the content-addressed `AssetStore` and thin authenticated web shell are Workbench platform facilities. Dungeon Studio uses them before the generic Ask workflow; prompt attachments and later studios reuse the same boundaries.

## Remaining Implementation Inputs

These do not change the architecture, but they determine the first adapters and fixtures:

1. Which character-sheet source format should be supported first: Markdown, fillable/static PDF, D&D Beyond export, Foundry/Roll20 export, another JSON format, or something else?
2. Which official rules and authorized bestiary books/editions are in the first corpus, and how will house rules or prior one-off rulings be authored?
3. Which first real embedding model/runtime passes retrieval quality plus Proxmox memory/latency tests? A small local CPU/ONNX adapter is preferred first; any hosted fallback needs separate credentials and a retention policy.
4. Which initial model/task-profile candidates and effort levels should enter the comparison evals (including Luna/Terra/Sol where available)?
5. Do the current ChatGPT Codex subscription terms/limits cover the intended interactive DM use, and which API-key provider/profile is the unattended fallback?
6. Which Roll20 capabilities beyond a correctly scaled image/grid manifest are worth targeting after the baseline exporter?
7. Which optional external clients eventually justify a Pi extension or MCP adapter? (No image-generation provider is required for the practical renderer.)
