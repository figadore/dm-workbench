# DM Assistant Harness — Technical Architecture

## 1. System Shape

The product is a self-hosted DM Workbench. Its first viable product is a standalone, runnable small
dungeon one-shot in a pleasant authoring/review workspace. Selected campaign grounding, then campaign
memory and reviewed session updates, extend that same experience.

This document is the normative target architecture, not a claim that every feature exists. Delivery
phases and task gates live in `dm-assistant-implementation-plan.md`; only `PROJECT_STATUS.md` records
the live task and implementation gaps. The whole-adventure authoring and contextual UI design below
supersedes the mandatory P7-14f six-family enrichment chain; replacement is incremental, not a mandate
to rewrite working storage, transport, or geometry.

Deployment contains only:

```text
browser / Typer CLI
        |
        v
Python 3.12 FastAPI Workbench
  |-- modular application/domain features
  |-- in-process pure dm_dungeon package
  |-- embedding adapters
  |-- PostgreSQL repositories
  |
  +--> private Node model gateway (@earendil-works/pi-ai)
  |
  `--> PostgreSQL 16 + pgvector
```

The Node process exists only because the selected provider transport/authentication library is Node.
It is a narrow runtime and credential boundary, not a domain service. Use package boundaries for pure
deterministic mechanics and feature-module boundaries for the rest. Do not add services, stores,
queues, caches, or agent frameworks without measured need.

The core principle is:

> PostgreSQL stores reviewed campaign state, preparation lineage, and durable workflow records;
> immutable sources preserve narrative and evidence; deterministic code compiles constrained intent
> into validated artifacts; retrieval supplies only authorized relevant context.

## 2. Non-Negotiable Invariants

1. **Human authority:** a model may create proposals, never approve preparation or commit canon.
2. **Atomic canon:** canonical writes pass through a validated change set and create one campaign
   revision atomically.
3. **Preparation is not canon:** ready/used dungeons and encounters do not establish that planned
   events occurred.
4. **Source integrity:** document revisions and cited spans are immutable; edits create revisions.
5. **Scope before ranking:** campaign, revision, audience, authority, corpus, timeline/cursor, and
   rules filters run before retrieval or context construction.
6. **Perspective:** reality, knowledge, unawareness, belief, suspicion, claims, and public record stay
   distinguishable.
7. **Explicit uncertainty:** missing, disputed, weakly sourced, or temporally incomparable campaign
   information produces unknown/conflict rather than asserted fact. Explicitly authorized creative
   invention belongs to labelled preparation; an unspecified DM puzzle answer is missing content,
   not epistemic caution.
8. **Deterministic mechanics:** models express typed creative intent; code owns IDs, graph
   construction, geometry, pathfinding, rules arithmetic, validation, rendering, and exports.
9. **Reproducible generation:** every artifact pins scope, sources, context hash, seed, contracts,
   compiler/generator/renderer versions, model/tool lineage, validation, and parentage.
10. **Package purity:** `dm_dungeon` runs in the Workbench process but imports no Workbench, FastAPI,
    SQLAlchemy, retrieval, repository, or provider code.
11. **Task-specific context:** workflows share a small scope/provenance envelope, not one universal
    optional-field payload.
12. **Fail-closed publication:** player output omits secret/unclassified content before rendering;
    unsafe or incomplete preparation cannot be approved. Model-created draft content is not human
    acceptance, and accepting a revision proposal is not approval for play.
13. **Explainable commits:** every campaign revision has a readable summary and complete accepted-item
    and evidence history.
14. **Synthetic repository data:** no real campaign text, copyrighted rules/bestiary content, sheets,
    credentials, or provider responses enter fixtures.

## 3. Alpha Retention and Versioning

**Retention gate: not crossed.** The gate is a product/data commitment, not a code milestone. Until
both this architecture and `PROJECT_STATUS.md` declare it crossed:

- active V1 schemas, prompts, compiler/generator/renderer/exporter pins, fixtures, and review packets
  evolve in place;
- synthetic fixtures, ignored review packets, disposable databases, and provider canaries do not
  require compatibility readers;
- obsolete alpha implementations may be deleted without parallel V2/V3/V4 dispatch.

Cross the gate no later than the first intentionally retained real-user campaign/artifact, external
consumer, non-disposable deployment, or promised replay requirement. Then freeze retained pins and
document read, migration, replay, rollback, and deprecation policy before incompatible changes.
Afterward, a version changes only when retained data or consumers need a distinguishable contract—not
merely because code changed.

## 4. Workbench Modules and Dependency Direction

The user sees one application with distinct workflows:

- **Library:** immutable campaign/rules/creature sources, ingestion, snapshots, retrieval, citations.
- **Chronicle:** canonical revisions, entities, events, temporal/perspective state, provenance.
- **Profiles:** character, item, creature, party, and playstyle snapshots.
- **Preparation:** generic artifact versions, generation runs, assets, and lifecycle.
- **Dungeon Studio:** cohesive adventure authoring, kernel invocation, map/guide workspace, scoped
  conversations, manual/proposed revisions, export, and separate preparation approval.
- **Encounter Studio:** encounter composition plus deterministic arithmetic/completeness/map fit.
- **Session Desk:** notes, extraction, grouped review, and canonical change-set submission.
- **Assistant:** cited campaign/rules questions and other bounded model tasks.
- **Settings:** non-secret provider/model/profile configuration, authentication coordination, and
  editable application-wide guidance; this is not campaign canon or developer policy.

The web and CLI call the same application services. Handlers contain no duplicate business logic.
Modules exchange typed contracts and opaque IDs, never each other's ORM objects.

```text
Library + Chronicle + Profiles
              |
              v
      task-specific context compilers
              |
              v
Dungeon / Encounter / Assistant / Session orchestration
       |                         |
       v                         v
private model gateway       deterministic mechanics
       \                         /
        v                       v
 answers / preparation versions / draft change sets
```

A context compiler is read-only. It is not a new authority or an engine-facing repository.

Dungeon authoring stays a Workbench feature, not a separate deployed tool/service or a new AI package.
A CLI/file adapter may run standalone authoring through the same services; a disposable phase-1
prototype must be consolidated or removed when integrated. `dm_dungeon` remains independently usable
for pure map work and never acquires model orchestration. Standalone means no campaign lore is
required, not duplicated provider credentials, storage, or application logic.

## 5. Deployment, Configuration, and Security

### Deployment

The supported installed topology is one non-root Workbench container, one non-root private gateway,
and PostgreSQL/pgvector. Only the authenticated Workbench is host-published. The gateway has private
Workbench ingress and separate un-published provider egress; PostgreSQL has no public ingress.
Native development may run Python and Node on loopback while Compose supplies PostgreSQL.

A modest hosted-inference baseline is about 2 vCPU/4 GB RAM; embedding runtime measurements may
require more. Local chat serving needs separate capacity planning.

Use separate durable volumes for PostgreSQL, gateway credentials, source trees, and generated assets.
Source volumes are read-only to Workbench. Scratch and content-addressed assets must share a filesystem
when atomic hard-link publication requires it. A VM is the simplest Proxmox deployment; LXC requires
an explicit nesting/security decision.

Backups combine an application-consistent database snapshot, immutable sources, and approved or
non-rebuildable assets. Gateway OAuth credentials remain outside ordinary campaign backups; re-login
is a supported recovery path. Restore must be drilled, not assumed.

### Typed configuration

Python loads one immutable validated `DM_*` settings object. Database URL, allowlisted source roots,
and a 32+ character DM API token are required. Model-gateway and embedding policies are separate so
chat credentials can never become embedding configuration. Errors name invalid fields but not values.
`.env.example` contains placeholders only.

Bootstrap may generate distinct database, API, browser-session, and internal-gateway secrets and
persist them in an ignored mode-`0600` file. It never generates provider credentials.

### Authentication

Default-deny middleware protects every route except the exact health and login allowlist. Bearer-token
comparison is constant-time and failures are generic.

Browser authentication must not require routine API-token pasting. P7-16b replaces that bootstrap-era
experience with single-owner enrollment and normal login using maintained password-hashing/session
components. Record the concrete design and threat model before implementation: first-run enrollment
is restricted to an explicitly bootstrapped owner, setup capability is short-lived/single-use, and
credentials/setup capabilities never travel in URLs, logs, or browser local storage. Do not add an
identity microservice or disable auth for convenience. Recovery/re-enrollment requires explicit
operator authority, not an unprotected reset endpoint.

Browser sessions carry only principal, expiry, CSRF and necessary revocation/session identity, never
API/provider credentials. Use short-lived sessions, logout/revocation, generic errors, login rate
limits, and secure credential verification. Browser writes require constant-time CSRF matching.
Cookies are HttpOnly and SameSite-strict, and Secure under production HTTPS. Document trusted-proxy,
TLS, local-development, enrollment and recovery behavior; remote use must not silently inherit local
exceptions. Templates escape values and responses use restrictive CSP/nosniff. Bearer authentication
remains available for CLI/API automation, independently of owner browser credentials.

### Health and logging

`/health/live` performs no dependency work. `/health/ready` checks PostgreSQL major version, exact
pgvector version, and Alembic head but returns only component states. `dm doctor` may expose safe
version/reason categories, never secrets or URLs.

Application logs are one JSON object per line with validated request IDs and relevant campaign,
revision, change-set, ingestion, embedding, model, attempt, and generation IDs. Logs use route
templates, not attacker-controlled paths. They omit request/response bodies, prompts, source/context
text, authorization values, credentials, provider bodies, and full generated specifications.
Recursive key redaction, configured-secret replacement, and credential-URL scrubbing occur in the
formatter.

Expected errors have stable API/CLI codes. Unexpected exceptions expose only correlation and stage;
stack text is limited to explicit local development diagnostics.

## 6. PostgreSQL and Assets

### Database

PostgreSQL is the sole canonical datastore and initially provides relational, temporal, graph-shaped,
full-text, JSONB, and vector storage. Generated binary assets live in a content-addressed volume;
metadata, role links, and lineage live in PostgreSQL.

SQLAlchemy 2 uses synchronous psycopg sessions with hidden parameters, pre-ping, and one explicit
unit-of-work boundary: success commits once, exceptions roll back, and sessions always close. Add
async database access only after measured concurrency requires it.

Alembic reads only validated `DM_DATABASE_URL`. Its `alembic_version` table is the schema authority;
there is no duplicate application schema-version table. Migration integration tests may be
destructive only against an explicitly configured database ending in `_test`.

Every campaign-owned row carries or is transitively constrained to `campaign_id`. Composite foreign
keys and service checks prevent cross-campaign references even while only one campaign is exposed.
Global rules records are explicitly global rather than campaign-null by accident.

### Content-addressed asset store

One platform `AssetStore` serves prompt attachments and generated outputs. It records SHA-256, media
type, size, safe locator, input/run ownership, and artifact-version role separately.

Writes stream to scratch, hash and `fsync`, then atomically publish without overwrite. Existing blobs
are verified by type, size, and hash. Reads accept only validated hash-derived locators and reverify
the file. Duplicate bytes share blob identity, while authorization and presentation remain attached
to role/ownership links.

The browser resolves assets through an authorized artifact-version link, never a global blob UUID.
Purpose-oriented catalog entries carry floor, audience, format, label, and safe filename. Trusted
SVG/PNG/text/JSON/PDF may open under format-specific security policy; ZIP is download-only. Normal
review is an inline map/guide workspace, not an asset directory; JSON, manifests, UUIDs, raw roles and
hashes belong under advanced inspection. Filenames describe dungeon/version/floor/audience/purpose.

## 7. Immutable Sources and Retrieval

### Source model

A path is a mutable locator, not evidence. The source layer uses:

```text
document
  id, owner/corpus, logical_key, active_path, retirement

document_path_history
  document_id, path, content_hash, event/reason

document_revision
  document_id, revision_number, exact UTF-8 content/hash,
  document_type, authority, ruleset, visibility, source metadata, parser version

document_chunk
  revision_id, ordinal, heading_path, half-open offsets, exact content/hash,
  page metadata, visibility override, FTS vector, chunker version

ingestion_run
  source scope/configuration, terminal state, diagnostics

corpus_snapshot + corpus_snapshot_document
  immutable selected document revisions and order
```

Database guards enforce owner/corpus scope, unique logical keys/paths (including global rules), exact
SHA-256 identity, immutable revisions/chunks, source-span equality, child visibility no broader than
its parent, and closed membership after snapshot activation.

Source discovery uses a named allowlisted root and normalized relative POSIX paths. It rejects
absolute paths, traversal, backslashes, unknown roots, symlinks, non-regular files, and root escapes.
Reads are bounded, no-follow, and strict UTF-8.

A scope advisory lock serializes identity decisions:

- same path/hash reuses the revision;
- new content at the same path creates one revision;
- returning to an old hash reuses that immutable revision while recording the path event;
- a unique exact-hash move whose old path is absent retains identity;
- a copy whose original remains creates a distinct document with duplicate linkage;
- ambiguous moved/edited matches require review and do not mutate identity;
- retirement occurs only through explicit reconciliation and never deletes revisions.

Parsing/chunking, snapshot activation, and search remain separate stages. Editing or deleting source
may create provenance-drift warnings but never automatically retract canon.

### Authority classification

Document type and authority are separate. Initial document types include canon notes, raw session
records, plans/adventures, reference lore, player handouts, character sheets, important items,
creature/bestiary sources, dungeon/encounter briefs, and house rules/rulings.

Authority includes canonical claim, raw record, preparation, reference, official rules, and
user-authored rules. A canonical-claim source still does not bypass reviewed canonical commit. Plans
may support preparation but do not answer what happened. Mixed sections may narrow authority or
visibility; ambiguity chooses the conservative classification.

Rules and creature sources preserve edition, book, chapter/section, page, and extraction revision.
Campaign and rules corpora remain independently filterable.

### Embeddings

Embeddings are rebuildable semantic projections, not evidence or canonical truth:

```text
embedding_profile
  runtime/provider/model/revision/license, dimensions, metric, normalization,
  preprocessing version, config hash, enabled

chunk_embedding
  chunk_id, exact chunk hash, profile_id, vector

embedding_run
  snapshot/profile pins, items, retry/cancel state, resource/usage measurements
```

`pi-ai` and Codex OAuth do not provide embeddings. Python embedding adapters have separate profiles,
credentials, batching, and retention policy. A small local CPU/ONNX adapter is preferred only if eval
and memory/latency measurements justify it; hosted adapters remain possible.

Profiles of different dimensions/normalization never share an index. A serving generation pins one
compatible profile. Query-embedding failure falls back to filtered lexical search.

### Retrieval

```text
question + authenticated principal + explicit/default scope
    -> resolve campaign revision, snapshot/index, timeline/cursor, audience, rules profile
    -> intent/entity/term analysis
    -> authorization, authority, corpus, edition filters
    -> accepted structured lookup + lexical search + vector search
    -> rank fusion, deduplication, optional reranking
    -> bounded provenance/neighbor expansion
    -> task-specific context or deterministic answer
```

Reciprocal rank fusion is the baseline because lexical and vector scores are not calibrated. Exact
names and rule terms receive lexical boosts. Reranking occurs only after hard filters and only when
evals justify it.

Retrieval records pin scope, revisions/index/profile versions, candidate IDs/scores, selected chunks,
latency, and final citations without source bodies in ordinary audit output. Excluded content cannot
leak through snippets, counts, citations, metadata, caches, or errors.

Accepted structured state has priority for factual questions; narrative sources explain or fill
unstructured gaps with authority labels. Conflicts are surfaced. Insufficient evidence or order
returns unknown.

## 8. Model Gateway and Bounded Workflows

### Gateway responsibilities

The private Node gateway uses exactly pinned `@earendil-works/pi-ai` (the active baseline is lockfile
resolved) for:

- allowlisted provider factories and model/capability catalogs;
- GitHub Copilot and OpenAI Codex subscription OAuth, selected API-key providers, and faux tests;
- serialized credential login/refresh/logout and atomic mode-`0600` storage;
- normalized text, thinking, tool-call, usage, cancellation, and image-input transport;
- provider-specific effort, context, continuity signatures, and request serialization.

It owns no campaign documents, retrieval policy, workflow authority, preparation/canonical state,
approval, tool loop, or arbitrary filesystem access. Every endpoint, including health, requires the
internal Workbench bearer token. The browser never calls it directly or receives provider tokens.

OAuth status may expose only verification URL/code, progress, and bounded non-secret prompt events.
Provider terms, model availability, and workload permission are operational checks; successful login
does not authorize unattended or high-volume use.

### Normalized request and transcript

Python sends resolved provider/model/effort, typed messages, allowed tool schemas, output limits,
run/cache ID, and validated attachment references. Messages are a discriminated union of `user`,
`assistant`, and `tool_result` preserving call ID/name, `isError`, bounded content, and required opaque
continuity signatures. Malformed combinations fail before transport.

The gateway returns normalized streams and final usage. On provider failure it may transiently inspect
status/text only to classify an allowlisted safe category such as rate/usage, authentication/access,
model/provider unavailable, rejected request contract, or generic provider error. Provider text/body
is not returned, logged, or persisted.

### Workflow authority and budgets

Python owns scope, task profiles, tool authorization/execution, cumulative monotonic deadline, turns,
tool count, output/cumulative tokens, repair policy, validation, idempotency, cancellation, and durable
run state. Before each request it passes only the remaining time/budget. Missing usage is unknown, not
zero.

A versioned model profile records adapter, provider/model ID, observed capabilities and limits. A
versioned task profile records task kind, model profile, normalized effort, context policy/budgets,
allowed tools, output schema/limit, fallback order, and instruction version. Every run pins the exact
resolved snapshot and overrides. Model branding never substitutes for task-specific evals.

A provider advertises `hard_output_token_limit` only when a provider-free wire-contract test proves it
serializes a supported pre-consumption limit. Codex subscription omits unsupported output-limit fields
and therefore does not advertise that capability; strict measured post-response publication ceilings,
timeout, cancellation, and repair reservation still apply. An over-cap result cannot publish, but
already consumed subscription quota cannot be recovered. There is no advisory bypass.

Expected provider, submission, compile, deterministic, asset, persistence, cancellation, rate, usage,
and timeout failures map to stable safe stages/codes. A durable prompt attempt starts before provider
contact and remains separate from the final artifact generation run, linked only when a package is
successfully published. Routine attempt inspection contains IDs, pins, timing, hashes, counts, usage,
stages, and bounded diagnostics—not prompts, source text, provider responses, or reasoning.

Accepted creative content belongs in the authorized artifact where it can be reviewed and rendered.
User-facing component conversations and proposed patches are private domain records (§15), not
operational logs. Persist their useful answer text and provenance under an explicit retention policy,
not raw provider transport envelopes or reasoning. Transient full debug capture is explicit, local,
sensitive, and not ordinary persistence.

Pins reproduce accepted inputs and deterministic compilation/rendering, not identical future model
outputs. Evaluation samples the ordinary workflow through a small adapter; reproducibility does not
require a wrapper-version chain or a database artifact for every creative subtask.

### Agent framework policy

A user-facing multi-turn conversation is not automatically an autonomous agent loop. Each Ask or
Propose Change turn uses existing bounded task services with server-resolved scope. No tool gains
accept/approve/commit authority merely because the UI is conversational.

Do not add `@earendil-works/pi-agent-core` for bounded ask, extraction, dungeon, or encounter flows.
Reconsider only if measured open-ended multi-turn steering/tool behavior exceeds simple Python-owned
workflows. If adopted, PostgreSQL/application services remain authoritative and no agent gains approve
or commit tools.

Pi extensions and local/private MCP are optional later adapters over authenticated Python services,
not the primary UI or internal transport.

## 9. Context Compilation

The harness decides what enters a model call. Retrieved text is untrusted labelled evidence and cannot
change principal, scope, tool policy, or approval rules.

Preparation workflows may use:

```text
GenerationContextEnvelope<T>
  schema_version
  context_kind
  payload_schema_version
  resolved campaign/revision/snapshot/rules scope as applicable
  visibility_scope
  immutable source references with authority labels
  payload_hash over canonical payload bytes
  payload: T
```

The envelope is small and persisted/content-addressed with lineage. Each workflow defines its own
strict payload only when implemented:

- `DungeonGenerationContext`: selected location lore/geography, themes, factions, hooks, tone,
  constraints, and coarse party/capacity information;
- `EncounterGenerationContext`: pinned party/playstyle, rules assumptions, authorized creatures,
  difficulty, dungeon geometry, pacing, and resource pressure;
- Ask packets: exact structured/narrative/rules evidence and answer/citation contract;
- session preparation/extraction or NPC scene packets: only their relevant participants, events,
  perspectives, and permissions.

These are not subclasses of an all-purpose optional object. Dungeon context never accumulates
encounter mechanics merely because both are preparation.

Compilers apply hard filters, per-section budgets, overlap deduplication, bounded provenance hops, and
enough neighboring text to prevent misleading fragments. Plans are absent from historical-fact
packets unless explicitly requested. DM secrets appear only for an authorized DM task and only when
relevant. Generated factual claims cite supplied packet IDs; post-checks verify citation presence and
authorization, while semantic support remains an eval concern.

Standalone dungeon generation uses its campaign only as a preparation owner. It reads no campaign
lore/revision/corpus implicitly. Explicitly selected rules, party assumptions, guidance and preparation
material may support authoring without enabling campaign-lore grounding. Selected material remains
revision-pinned and authority-labelled, not implicitly canonical. Standalone, selected campaign
grounding and `synthetic_eval` have strict payloads; synthetic facts cite packaged fixtures.

Selected campaign grounding distinguishes established facts, attributed claims, unknowns, required
preparation placements, and creative permissions. Inputs cite immutable evidence or an explicit DM
annotation/instruction; instructions are not evidence of canonical reality. For example, “the captive
must be alive here” is a preparation constraint; “the relic is reportedly here” is not proof of its
presence. Resolving an unknown creatively requires explicit permission and produces preparation-only
content. Conflicting established facts and requirements are surfaced before dispatch. The first
adapter accepts DM-selected evidence; filtered retrieval later suggests sources for inspection and
selection. Full temporal/perspective canon is not a dependency for this bounded adapter.

For a 4–8-room adventure, whole-artifact context is appropriate. Component conversations distinguish
read context (possibly the whole authorized adventure) from write scope (only selected targets/fields).
The server pins artifact/base version, selection, authorized sources, permissions, and context hash;
the client or model cannot expand them by supplying IDs. Context changes require visible confirmation.

### Application-wide guidance

Guidance applies to every model-facing workflow as it is implemented: planning, component generation,
encounters, NPCs/dialogue, revision, session preparation and assistant responses. P7-16 introduces it
through the standalone workflow; P7-18 adds confirmed learning and reusable procedures.

Natural-language guidance is first-class, not a fixed catalogue of feature settings. Distinguish
reported observations about the group, desired experiences/strategies, creative preferences and binding
requirements. An observation does not imply a desired response: "the party attacks first" could inform
either combat-forward play or believable consequences, depending on the DM's direction. None of these
asserts that a prepared event occurred or permits changing factual answers to suit a preference.

The Workbench stores guidance with minimal owner, scope, origin and revision metadata. Resolve product
and personal defaults, selected group/campaign guidance and request overrides; show effective guidance
and origins. Surface contradictory requirements or ambiguous intent instead of silently choosing.
New preferences need no new schema field unless deterministic code actually consumes one.

A shared resolver supplies relevant guidance to each strict task-specific context compiler, not a
universal payload or the entire memory in every prompt. Pin the selected guidance per attempt; preserve
its applicable intent across outline, generation, repair and revision. Maintained task templates
assemble it alongside authorized evidence and task contracts. Users edit guidance, not raw system/tool
prompts. Security, source authority, write scope and supported mechanical policy remain code-owned.

Keep general seams for including/omitting optional content, using authorized existing material, and
preserving or explicitly adapting it. Apply structural implications before construction; exclusions
must not leave broken dependencies or missing essentials. Reuse source selection and revision services,
not a subsystem for each content type. A new preference is not necessarily a new capability: disclose
unsupported operations and conflicts rather than silently ignoring them or inventing substitutes.

Requirements can be expressed in prose without claiming deterministic enforcement. Check what code
can prove; use semantic review for meaning and adherence. Known requirement violations block readiness
until corrected or the human explicitly revises the brief. Guidance must shape content, not merely be
repeated in it, and personalization must not conceal defects in enabled generation.

### Remembering guidance and procedures

Changes to defaults affect future requests, not in-flight attempts or existing artifacts. Revisions
inherit their base context; applying new guidance requires explicit scope and dependency review (§12).
The human can inspect, edit, override, disable or delete saved guidance. Learning from authorized
conversations/edits produces suggestions with supporting examples and proposed scope; promotion needs
separate human confirmation. Ask may display suggestions, never activate them. Accepting an artifact
edit is not consent to a lasting preference; unrelated history and silence are not evidence of consent.

When repeated work justifies it, the same review boundary can save a versioned, non-executable recipe
for a reusable procedure. Load human-selected relevant recipes under context budgets; they cannot
override requirements or grant tools/authority. No agent framework or model-weight training is needed.

Guidance and recipes are private application data, not canon or repository `AGENTS.md` edits. Exclude
them from player assets and generic retrieval. Define access/export/deletion/backup and minimal retained
artifact provenance before persistence; real retained use triggers §3. No separate memory service.

## 10. Core Campaign Data Model

The model is an extensible temporal property graph implemented relationally, with cohesive JSONB
aggregates where decomposition would harm usability. Sequential IDs never encode story chronology.

### Campaign and revisions

```text
campaign
  id, name, head_revision_id, active_corpus_snapshot_id,
  default_timeline_id, default_story_cursor_id, default_rules_profile_id,
  default_visibility_policy_id, metadata

campaign_revision
  id, campaign_id, parent_id, sequence_number, committed_change_set_id,
  summary/origin, committed_by/at
```

The head pointer advances in the same transaction as commit. Defaults are inspectable and every query
returns its resolved scope. One Workbench campaign may be marked active for convenience; a model
cannot select another campaign or turn that marker into authority.

### Entities, aliases, and mentions

```text
entity
  id, campaign_id, type, canonical_name, descriptive properties,
  visibility, system revision range

entity_alias
  entity_id, normalized/display alias, optional source and valid-time range

entity_mention
  exact chunk/span/surface text, optional resolved entity, resolution status
```

Entity properties contain low-risk description, not temporal, perspective-sensitive, provenance-
sensitive, or secret state. Ambiguous names do not auto-merge. Merge/split/alias operations are
reviewed and preserve redirects/audit history.

Entity types may include people, PCs/NPCs, groups, factions, places, items, deities, organizations,
spells, concepts, secrets, and quests/threads without a rigid inheritance tree.

### Predicates

Predicates are versioned data rather than columns:

```text
predicate
  namespace/name/version/description
  subject/object constraints and value kind
  symmetric/transitive/inverse, functional/exclusivity semantics
  examples/properties/lifecycle
```

New relationships normally add reviewed catalog data. Similar-but-wrong predicates are not reused to
make validation pass. Inverse, symmetric, and safe transitive facts are rebuildable derivations unless
explicit evidence justifies independent canonical rows.

### Propositions and perspective assertions

A proposition describes content without asserting truth:

```text
proposition
  id, campaign, content timeline
  subject + predicate + exactly one entity/event/typed-literal object
  explicit polarity, content-valid anchors, qualifiers, content hash
```

An assertion records a stance toward that proposition:

```text
assertion
  id, campaign, proposition
  mode: reality | knowledge | unaware | belief | suspicion | claim | public_record
  holder when required
  stance timeline/start/end
  semantic certainty, visibility, derivation
  system revision range, supersession, recorded_at
```

Content time, stance/reveal time, and system/canonical revision time are independent. Proposition
objects are immutable interned content and are never returned alone; an authorized assertion provides
perspective, visibility, and revision semantics.

Workflow state and extraction confidence do not become truth flags. Proposed/accepted/rejected belong
to change items; active/superseded/retracted use revision ranges; explicit/derived/inferred describe
derivation; disputes are represented by incompatible accepted assertions and evidence.

Knowledge is open-world. Missing `knowledge` means no recorded knowledge, not proven unawareness.
Important secrets may opt into explicit tracked-holder completeness. NPC/player context remains
conservative: unrecorded secrets are not supplied.

### Sessions, events, and time

A table session is provenance, not fictional chronology:

```text
session
  campaign, display/title/played_at, planned/open/closed state,
  opening/closing campaign revisions, metadata

session_document
  session, immutable revision, role: prep/raw_notes/summary/transcript
```

Events represent occurrences in accepted reality; plans and allegations do not:

```text
event
  campaign/timeline/type/title/description
  start/end anchors, optional location, certainty, visibility, properties
  system revision range, optional superseded event, recorded_at

event_participant
  event, entity, role, properties
```

Events preserve narrative occurrences; propositions/assertions make consequences and perspectives
queryable. Review groups events with dependent consequences but never silently accepts all inferred
items.

Temporal anchors support story or table/session domains, exact/bounded/approximate/event-relative/
session-marker/unknown kinds, optional raw calendar components, precision, and reference offsets.
Calendar adapters may later derive sortable ordinals but never replace the original representation or
invent missing dates.

Relative relations initially include BEFORE, AFTER, DURING, OVERLAPS, STARTS, FINISHES, and
SIMULTANEOUS_WITH where semantics are defined. Safe closure is rebuildable; strict-order cycles block
or warn. Partial order remains partial.

A story cursor selects timeline and anchor, optionally participants. “Current” is always relative to a
cursor. If two facts cannot be ordered, insertion time does not decide them.

Concurrent scenes use one timeline with overlapping anchors and separate cursors. Literal alternate
histories use explicit parent/branch timeline records, but inheritance/merging is deferred; the MVP
queries only explicit timeline data plus a deliberately defined shared-history rule.

A story-state change closes/opens content-valid intervals. A retcon supersedes the system-valid
canonical assertion/event. Both preserve old revision reads. Canonical rows are immutable except for
controlled system-ending metadata; ordinary correction never destructively deletes history.

### Profiles

Character sheets and important items are cohesive source-linked snapshots rather than one assertion
per cell:

```text
character_sheet_snapshot
  campaign/character/ruleset/source/schema
  reported sheet data, computed data with formula/rules pins
  visibility and system revision range

item_profile_snapshot
  campaign/item/optional ruleset/source/schema
  mechanics/lore/charges/restrictions data
  visibility and system revision range
```

Story ownership, location, attunement, knowledge, and history still use temporal assertions/events.
Imports produce reviewed field-level diffs. Rapid tactical state—current HP, slots, conditions,
initiative, positions—is deferred.

Binary original sources use immutable content-addressed source-asset revisions only when a real
adapter requires them. Formats remain adapter-based rather than guessed in architecture.

### Evidence and derivation

Evidence is many-to-many and uses typed links rather than unconstrained polymorphic foreign keys:

```text
source_reference
  exactly one immutable chunk/span, source asset revision,
  accepted event/assertion, or DM annotation
  optional quote hash

assertion_evidence / event_evidence
  target, source_reference, role: direct/supporting/conflicting/context

derivation_edge
  derived record, accepted dependency, versioned derivation kind
```

A model interaction is lineage, not sufficient evidence. Accepted claims point to campaign/rules
sources the model interpreted. This supports “why?” queries and impact analysis after a retcon.

## 11. Canonical Change Sets

All manual, imported, extracted, and model-assisted canonical changes use the same boundary:

```text
change_set
  campaign, base_revision, draft/in_review/committed/abandoned,
  origin/run, idempotency, created_by/at

change_item
  versioned operation and candidate payload
  local IDs, source references, dependencies
  pending/accepted/edited/rejected review
  extraction confidence, validation, review note

change_set_source
  immutable source revision and role
```

Model-facing canonical tools are explicitly named `propose_*` and write only to a draft change set.
There is no model-facing `record_event`, `assert_fact`, direct ORM/SQL write, artifact approval, or
commit.

Commit revalidates the accepted dependency closure against the base revision, rejects or rebases stale
work explicitly, resolves local IDs, inserts immutable records, creates exactly one child campaign
revision, and advances the head in one transaction. Idempotency prevents retry duplication. Partial
approval is allowed only when dependencies remain valid.

Historical reads target any campaign revision. The readable summary is editable, while full accepted/
rejected items, before/after values, evidence, validation, reviewer, and time remain auditable.
Markdown/JSONL/Git logs, if added, are rebuildable projections and never a second canonical write path.

## 12. Preparation Artifacts and Runs

Dungeons, maps, puzzles, generated creatures, and encounters use a separate lifecycle:

```text
prep_artifact
  campaign, type, title, draft/approved_for_play/used/retired,
  current_version, visibility, created_at

prep_artifact_version
  artifact, parent, schema, immutable specification/validation,
  readable summary, pinned campaign/corpus/rules/party inputs,
  generation run, creator/time

artifact_asset
  version, asset, role, audience, ordinal

generation_run
  campaign/kind/seed, exact input scope and context hash,
  schema/generator/model pins, status/stages/timing, safe diagnostics
```

Versions and role links are immutable. A child of approved/used preparation returns to draft; retired
is terminal. Every lifecycle change records actor, reason, and exact version. No table has an implicit
canonical-write relationship.

An ordinary generation attempt holds outline, validated map, content candidate, diagnostics, and
checkpoint pins until complete draft publication. Do not require an artifact child for each feature
or model call. A failed/cancelled authoring attempt preserves any prior artifact and may retain a
validated map/checkpoint privately; it is not a preparation-ready current version. Checkpoints resume
only after scope/input/schema/generator pins are revalidated; incompatible state requires an explicit
restart. Routine diagnostics remain body-free. Accepted checkpoint content is private domain work,
not permission to persist raw provider transcripts.

Publish user-meaningful versions: initial complete draft, saved manual revision, accepted proposed
revision, or explicit layout regeneration. Changes use typed patches with expected base version/hash,
server-owned write scope, author origin, dependency validation, idempotency, and atomic publication.
Unrelated content/manual edits are protected by default. Rejected or stale proposals cannot advance
current state. Restore/undo creates a child; it never rewrites history. A model can persist a proposed
patch but only the human acceptance service applies that patch as a revised draft. Approval for play
and canonical commit remain separate operations. Incomplete manual authoring may be saved with visible
readiness blockers; integrity/security validation still applies and approval remains unavailable.
Initial automatic generation aims to publish a complete draft rather than label a partial attempt done.

Complete package publication is all-or-nothing:

1. compile, generate, validate, and render every required byte;
2. validate asset role, audience, media, size, and hash contracts;
3. stage content-addressed blobs;
4. in one database unit of work create artifact if needed, immutable version, role links, current
   pointer, and terminal successful run.

Any failure produces a failed run and no partial current version. Unreferenced deduplicated staged
bytes may remain harmlessly. A successful response, current version, complete role set, and terminal
run are one observable outcome.

Promoting selected prepared facts into campaign reality creates an ordinary reviewed P3 change set
referencing the artifact. Marking an artifact used never infers outcomes.

## 13. Dungeon Generation

### Product boundary and representations

The first viable dungeon is a standalone one-shot: one floor, roughly 5–7 rooms within the supported
4–8-room class, one explicit party/rules assumption, a session-length target, a hook, opposition,
meaningful route choice, and a concrete ending. Puzzles are appropriate content, not mandatory filler.
The map and guide must let the DM run it without inventing missing core evidence or mechanics.

Retain the pure package's four alpha V1 representations:

1. **`DungeonPlan`:** bounded creative outline using local refs; evolve it to carry geometry-relevant
   adventure needs rather than a mandatory queue of enrichment slots.
2. **`TopologyCertificate`:** code-owned graph, IDs, demand, progression/secret witnesses and embedding
   constraints for the supported constructor.
3. **`LayoutRequest`:** certified intent plus server seed, optional bounds, and explicit locks.
4. **`DungeonPackage`:** exact renderer-neutral rooms, connections, openings, geometry, mechanics,
   terrain/markers, anchors, and audience layers.

Whole-adventure prose/content and authoring orchestration belong in the Workbench. Pure plan fields
exist only when consumed by construction/validation; do not import Workbench story/context models
into `dm_dungeon`. Evolve the Workbench specification for coherent adventure content and typed links
rather than a universal optional-field object. Structure what code consumes, not every sentence.

Local refs are noncanonical handles. Code derives stable IDs from semantic identity/compiler policy,
independent of seed, prose, and array order. Established IDs enter revision workflows explicitly;
deterministic package code never calls `uuid4()`. Display numbering is separate and shared by map,
guide, and inspector. Geometry-affecting demand belongs in the package, not invisible prose.

### Whole-adventure authoring

```text
resolved brief + relevant guidance + authorized rules/party/source inputs
    -> bounded whole-adventure outline
    -> deterministic map construction and validation
    -> bounded whole-adventure content submission over the resolved map
    -> structural/mechanical/source checks
    -> optional bounded correction; editorial review/revision only when justified
    -> atomic complete draft publication
```

Target two ordinary creative calls, not a mandatory six-task sequence. Phase 1 can isolate content
quality with one existing map before integrating the outline pass. Reuse shared bounded runners;
measure actual input/output requirements before selecting production ceilings. Corrections, including
schema repairs, count against one explicit cumulative attempt policy; no hidden retry loops. A
model-based editorial pass is optional, separately authorized/budgeted, and never proves readiness.
Test a consistency objective in initial prompting independently before introducing such a pass; add it
only if prompt-only results are insufficient and measure its incremental benefit (§17).

The disposable P7-15b file prototype wraps the existing Workbench `DungeonGuideContentPlan` with
bounded overview prose, reusing the structured-submission runner, cumulative technical-repair
reservation, guide validators/projection and pure map tools. Its fixture CLI has no live transport,
editorial call, database publication or approval path. Three adapted synthetic briefs share one
validated five-room map; paired inputs differ only by the consistency instruction. Short scripted
responses and synthetic accounting counters are plumbing checks, not authoring-quality evidence or
production ceilings. This experimental payload is not a new persistent story schema or a second
production pipeline; production V1 evolution remains governed by §3.

Causal and counterfactual consistency is an authoring objective: behavior and consequences should
follow from established motives, knowledge and circumstances, including when circumstances change.
Apply it from the earliest creative prompt and preserve it across outline, content and any repair.
It is neither a new guide section nor a growing checklist of incidents from one reviewed adventure.
Characters may be mistaken or irrational; their behavior must still be intelligible from the supplied
situation. Natural-language instructions do not establish deterministic proof of this quality.

Prefer revising/simplifying the underlying situation and replacing inconsistent prose over appending
justifications. A conditional editorial pass produces a revised candidate, updating affected passages
within authorized scope and retaining roughly the agreed guide length. Preserve useful play detail;
necessary missing procedures may require words, but neither padding nor deleting essentials is a fix.
An explanation invented by a reviewer is a proposed repair, not evidence that the old draft worked.
This is editorial replacement, not permission to overwrite immutable versions, protected human text,
source facts or validated geometry (§12). It requires no story-state ontology or additional framework.

The outline designs premise/history, objective/opposition, room purposes, clue relationships,
progression, and spatial affordances together. It requests bounded terrain/room needs without exact
coordinates, graph edges, numeric policy, visibility, lifecycle, or canonical authority. The existing
structural submission/compiler boundary can evolve in place. Deterministic failures are engine
errors, not invitations for repeated random model graphs.

The content pass sees the whole small adventure, resolved map and references, selected sources, and
supported mechanical policies. It authors the actual hook/ending, keyed rooms, inhabitants/reactions,
clues/answers, obstacles/consequences, and meaningful rewards or resolutions. Different content types
may have distinct typed records without becoming independent calls or child artifact versions.

If content requires unsupported terrain or contradicts the outline/map, reject or surface the
mismatch. Do not silently describe absent geometry. A correction may fit the existing map; structural
revision must be explicit and rerun construction/validation within the authorized attempt budget.
Model suggestions of severity, timer, resource cost, or composition use bounded intent; code owns
numeric resolution under pinned supported policy. Unsupported mechanics stay flagged, not invented
as official rules. Full character import or general encounter balancing is not required for MVP.

### Layout quality and the proof boundary

The existing Tier A constructor supports a critical-path backbone, up to two ordered branches, at most
one bypass/loop, one gate with a reachable dependency, and one secret route. Reuse it while proving
content quality. Independent validators check topology, fixed-point gate reachability, capacities,
ports/channels, geometry, paths, and secrecy. Accepted plans must stay within the constructor's stated
supported grammar. Mathematical details live in the package's `TOPOLOGY_MATH.md`.

Proof of connectivity is not proof of a convincing place. Measure occupied coverage, room spacing,
corridor detours, and guide/terrain agreement. Prefer compactness improvements and bounded, authored
layout families before arbitrary geometry. If replacing the constructor with templates/assembly is
justified, update this boundary and package proofs/properties before switching; do not require the
old embedding certificate to dictate a new algorithm, nor discard independent validation.

Direct doors require shared-wall geometry. Other links use explicit corridors/openings with valid
wall approaches. A small supported terrain vocabulary (crossings, pools, barriers, cover, fixtures)
gets deterministic dimensions, collision/clearance checks, and real rendered shapes. General
furnishing placement, multi-floor graphs, unrestricted packing, and freeform drawing are deferred.

Static geometry, designed play states, and actual session state are different. Alarms, flooding,
opened gates, damaged bridges, or lost evidence may have concrete DM procedures and consequences.
Their existence does not require dynamic simulation, automatic map mutation, or canonical writes.
Avoid accidental softlocks without requiring every setback to leave the adventure unchanged.

### Guide, completeness, and approval

Assemble an adventure overview (hook, assumptions, stakes, background, progression, ending) followed
by concise room keys. Supply concrete puzzle inscriptions/objects/evidence, a definite answer,
observable feedback, hints/alternatives, and failure/retry behavior where applicable. Place clues in
their keyed rooms, not only in a remote solution paragraph. Mystery for players must have a DM answer.

Keep arrival read-aloud, private DM guidance and conditionally revealed text/dialogue distinct, with
explicit delivery triggers where needed. Group actionable room content without repeating the same
feature as separate exploration/puzzle/objective prose. Internal policy text such as “make this a
meaningful room-local expression” or “do not invalidate progression” is never final guide content.
No JSON, opaque IDs, or duplicate solution paragraphs are normal reading requirements.

Validation has separate outcomes:

- **Hard integrity/security:** unauthorized scope, secrets, malformed references, invalid geometry,
  stale bases, unsupported mechanical claims, or corrupt publication cannot be bypassed by a model.
- **Required authored completeness:** actual clue/answer/obstacle/opposition/ending material must be
  supplied when required by the brief. Missing essentials block readiness; nonempty fields do not
  prove semantic completeness. Human review can identify gaps that deterministic checks cannot.
- **Editorial quality:** coherence, variety, agency, clarity, attractiveness and prep usefulness need
  human judgment; optional model critique provides suggestions, not certification.

Approval records the human and exact reviewed specification/version after integrity/readiness
validation. Do not require a provider-written cohesion report, hash-bound rubric for every dimension,
or a successful evaluation-wrapper chain in the ordinary approval workflow. A known missing essential
is resolved by supplying it or explicitly revising the brief, not silently checking “approved.”

### Manual and proposed revision

Manual and AI-assisted changes share typed patch/validation/publication services (§12). Text-only
patches preserve geometry and unrelated content. Reference/mechanic changes validate dependencies;
structural edits explicitly rebuild affected outputs. Protect manual edits by default and identify
human versus generated origin without forcing prose into a field-level campaign ontology.

A selected component controls write scope, not necessarily all read context. Ask is read-only;
Propose Change returns a previewable patch against an exact base. Changed clues in other rooms,
layout, source constraints, or protected prose require a visible impact/scope expansion and human
authorization. Stale proposals must be rejected or explicitly rebased and re-reviewed. No model tool
accepts its own patch, approves preparation, or commits canon. Focused puzzle/room revision calls are
introduced here only as justified by preserving valuable work, not as mandatory initial enrichment.

### Rendering, workspace maps, and exports

SVG is the semantic vector layer; PNG uses the same audience-filtered geometry. Filtering occurs
before XML/raster construction, never by CSS hiding. Style is code-owned: restrained wall/floor/terrain
appearance, grid control, clear labels, accessible contrast and a grayscale/low-ink treatment. Do not
use illustration to invent geometry or add a live image-model dependency for MVP.

DM maps use short consistent room/feature callouts and a legible symbol grammar for doors, secrets,
traps, puzzles, clues, objectives and terrain. Collision-aware labels and bounded leader lines retain
readability under zoom and export. Browser hit targets resolve stable IDs server-side. Selection and
conversation overlays are presentation-only, DM-only, and absent from player export bytes.

Player assets contain only explicitly published geometry and physical features. Omit keys/callouts,
objectives, start/encounter markers, secret doors/areas, trap/lock state, hidden DCs, solutions, private
conversations and proposal history. Filtered components leave no element, metadata, or full-package
hash fingerprint. DM/player preview switches do not turn private inspector data into a player asset.

Purpose-based assets include inline/downloadable DM guide, DM/player maps, and optional Roll20 bundles
with grid/gridless PNG, dimensions/hashes, five-foot scale, origin, and filtered wall/door metadata.
No direct upload or dynamic-lighting promise. Human visual checks inspect actual rendered outputs.

New print generation stays disabled until P7-20. Reference maps fit bounded pages and are visibly
not miniature-scale. Tactical tiles cover selected regions at 72 points per five-foot cell with
page/coverage limits, crop/registration marks, overlap/alignment, safe margins, actual-size guidance,
and a one-inch calibration mark. Validate metadata and rendered nonblank pages before enabling it.

## 14. Encounter Generation

For the one-shot MVP, use an explicit party-size/level/rules assumption and a small selected authorized
creature/profile set with deterministic supported difficulty and hazard policies. Standalone may use
these inputs without campaign grounding. Do not claim balance from invented fixture creatures or leave
essential opposition unspecified while waiting for full P8. Reuse a narrow mechanical evaluator in the
Workbench; the broader profiles/scaling workflows below are subsequent capabilities, not prerequisites
for coherent dungeon authoring. A single whole-adventure content submission can contain combat and
noncombat records without a second mandatory population pipeline.

Creature profiles are complete edition-tagged source projections:

```text
creature_profile_snapshot
  campaign/global owner, creature entity, ruleset/source/schema
  complete stat block, lineage parent/kind, visibility, revision range

party_generation_snapshot
  campaign, exact character-sheet versions, level/composition,
  DM-approved playstyle, optional resource overrides, rules profile, assumptions
```

Complete stat blocks include normal identity, defense, movement, abilities, saves/skills, damage and
condition traits, senses/languages, challenge metadata, traits, spellcasting, actions, reactions, and
optional legendary/mythic/lair sections. Generated variants store the full result and parent diff;
unsupported challenge estimates remain provisional for DM review.

Encounter packages are typed `combat`, `social`, `exploration`, `puzzle`, `trap`, `hazard`, or `mixed`
preparation artifacts. They may include purpose/stakes/objectives, exact room/zone IDs, party snapshot,
participants, positions/waves/triggers, terrain, tactics, checks/DCs, clues/hints/solutions/counterplay,
outcomes/rewards/consequences, variants, audience-safe handouts, and citations.

An edition-aware deterministic Workbench evaluator owns official difficulty/budget arithmetic and
reports baseline separately from playstyle adjustment. Deterministic mechanics also validate stat
completeness, footprints/movement/range/cover/objective room fit, and type-specific completeness.
Models propose composition, tactics, and experience; they cannot mark arithmetic valid.

Dungeon-wide generation considers pacing, attrition/rest, variety, clues/gates, optional routes,
factions, and treasure rather than optimizing rooms independently. Stable room/marker IDs permit one
encounter to regenerate without rewriting the dungeon.

Encounter orchestration begins in the Workbench. Extract only a measured cohesive deterministic
`encounter-mechanics` package after P8 evidence; never create a full `encounter-engine` for symmetry.

## 15. Model-Facing and Human Interfaces

Raw tables are not model tools. Every operation uses strict versioned schemas, server-supplied scope,
bounded counts, and opaque IDs.

Read tools may resolve entities, query state/events/provenance, search authorized memory/rules/
creatures, retrieve pinned party data, or inspect preparation. Canonical writes are named proposals
into a draft change set. Preparation tools create or validate drafts only. No model tool approves,
commits, runs SQL, writes arbitrary files, or broadens scope.

Human APIs separately support review, preparation approval, and `commit_change_set`. Idempotency
protects retries. TypeBox/tool schemas sent through the gateway are generated from or contract-tested
against authoritative Python JSON schemas.

### Review workspace and visual delivery

Use the existing server-rendered shell with focused HTMX/JavaScript/SSE unless measured interaction
needs justify a richer client. Thin handlers are a dependency boundary, not an instruction to deliver
unstyled forms. Phase 2 supplies normal owner sign-in (§5), a small visual system (typography, spacing,
contrast, reusable components), coherent navigation, readable status/errors, and a responsive
map-and-guide workspace. Model/provider setup is secondary Settings UI. JSON and artifact storage
internals are advanced details, not the product surface. Do not misrepresent faux/unfinished features
as operational tools.

The workspace consists of a dungeon overview, map, room/component navigator, keyed guide and inspector.
Shared stable selection links map and text. Manual room prose editing has explicit save/cancel,
unsaved-change warnings, validation feedback, version history/restore and stale-tab conflict handling.
No raw JSON editing or automatic campaign write is required. Phase 3 supplies map styling, terrain,
zoom/pan and fine component hit targets; screenshot/render inspection and human review complement
browser interaction tests. Keyboard operation, visible focus, sufficient contrast, and narrow/wide
layouts are acceptance criteria. A large SPA, freeform geometry editor and illustration pipeline are
not prerequisites; any client-framework decision needs a scoped rationale rather than a rewrite for
its own sake.

Expose applicable guidance, its origin and overrides (§9); distinguish "use for this request" from
"save my default". Show conflicts before dispatch and require separate confirmation of learned guidance.

### Component conversations and proposed changes

Phase 4 adds an inspector conversation for the whole dungeon or a selected room, puzzle, or obstacle.
The visible context header shows artifact/version, selected component, source summary, permitted read
context and proposed write scope. Context is constructed and authorized by the server, never trusted
from client-supplied text or IDs. Selecting another target or advancing the artifact makes context
changes explicit; an old discussion does not silently inherit a new base.

- **Ask / Explain:** read-only bounded answers grounded in the selected artifact, with inferred or
  suggested additions labelled. No mutation tool. Explaining an absent puzzle answer must surface the
  gap, not silently turn a newly invented answer into authored content.
- **Propose Change:** a strict patch proposal against an exact base version/hash. Show before/after,
  dependencies, protected manual edits, and structural/source impacts. Wider scope requires human
  authorization. Acceptance/edit/rejection is a human API action; acceptance creates one validated
  draft version. Preparation approval and canonical commit remain distinct.

A conversation/turn belongs to the authorized preparation owner and pins artifact version, target IDs,
mode, context/source refs and origin/run. Store user messages and useful assistant answers privately;
store proposed patch, base and disposition separately from an applied artifact. Never store provider
reasoning/authentication/transport bodies as chat history. These records are not canonical facts and
are excluded from player assets, ordinary operational logs and generic retrieval by default.

Before adding persistence, declare access, export/deletion, backup, size limits and retention rules.
Deleting conversation text must not corrupt an accepted version's necessary patch/source provenance;
preserve the minimal authoritative lineage under the retained-artifact policy. Resume/reconnect and
cancellation preserve base/scope and cannot apply a partial proposal. Use existing durable run and
session boundaries; conversational UI does not require an agent framework or a queue.

## 16. Session-End Extraction

Session close is a bounded pipeline, not autonomous agents:

```text
immutable note + selected base revision + used preparation
  -> source classification and entity/alias candidates
  -> occurred events and participants
  -> state/relationship/thread proposals
  -> temporal normalization
  -> knowledge/belief/claim/reveal proposals
  -> retcon/conflict/continuity analysis
  -> evidence-linked draft change set
  -> deterministic validation
  -> grouped DM review/edit
  -> atomic canonical commit
```

Stages may combine only when evals show shared context is safe. Outputs carry exact source spans and
stable candidate IDs. Confidence sorts review but never auto-canonizes. Rejected content remains in
immutable source/run history. Prepared artifacts inform extraction but never prepopulate outcomes.

The same note revision, base revision, and extraction configuration resolve idempotently unless the DM
explicitly requests another run. Bootstrap imports still create reviewed canonical revisions rather
than treating every source sentence as fact.

## 17. Validation and Evaluation

Deterministic validation covers, where applicable:

- campaign/revision/timeline/visibility ownership and stale bases;
- entity/alias ambiguity and predicate type/cardinality/exclusivity;
- proposition object/polarity, stance holders, intervals, contradictions, and derivation cycles;
- temporal strict-order cycles and unsupported chronology;
- source authority, evidence accessibility, rules edition/profile, and citation validity;
- profile schema/computed-value lineage;
- preparation schema/version/lineage and exact input pins;
- dungeon connectivity, witnesses, gates, geometry, paths, capacity, scale, and stable IDs;
- player secrecy and asset hash/media/dimension contracts;
- creature completeness, encounter arithmetic/map fit, and puzzle/trap/noncombat completeness;
- extraction evidence and dependency closure;
- guidance scope, overrides, attempt pins, human confirmation, privacy and authority boundaries.

Structural/security errors block commit or preparation approval. Semantic concerns may be DM-
overridable warnings with recorded rationale. Authorization failures are never overridable through a
model proposal. Known missing required play material is a readiness blocker, not an aesthetic warning.
Deterministic completeness checks establish required structure, not semantic solvability; human review
must identify absent or circular evidence and unusable consequences that pass shape validation.

Evaluate enabled workflows at distinct levels:

- Unit/property and integration tests prove references, geometry, secrecy, atomic persistence, scope,
  source integrity, conflict handling, cancellation and replay/checkpoint boundaries.
- Browser interaction tests exercise ordinary sign-in, generation, selection, editing, proposed
  changes, exports and error recovery. Inspect screenshots and actual SVG/PNG, not only metadata.
- Human packet review/tabletop walkthroughs measure missing essentials, coherence/variety, agency,
  puzzle comprehension, map/content agreement, appearance, and actual DM review/editing minutes.
  Record “would I run it?” and unresolved work. AI critique is not blinded human review or play evidence.
- A small evaluation adapter samples the ordinary service on at least three materially different
  synthetic briefs. Pin inputs/profile/versions and report usage, latency, failures and corrections;
  compare matched conditions where possible and label confounds. Do not require provider matrices,
  model-brand-specific gates, or exact wrapper chains in production approval.

For the consistency experiment, first compare initial whole-adventure prompting with and without the
causal/counterfactual objective, keeping brief, validated map, model/effort, rendering and technical-
repair policy/budgets matched. Neither condition includes an added editorial model call. Use fresh
synthetic briefs and held-out cases after tuning. Only if prompt-only quality is insufficient, compare
an additional bounded editorial review/revision with that prompt-only baseline; do not attribute the
benefit of extra calls to the initial instruction. Report guide length, causal repairs still needed,
all attempts/corrections, cumulative cost/latency and actual human effort. The desired improvement is
less missing work without explanatory bloat or lost play content, not higher self-assigned scores.
A repeatedly human-revised reference establishes a target, not first-pass reliability. Compare practical
value with chat-assisted authoring plus a map as well as prior packets, labelling unmatched conditions.

Test guidance across different content types and workflow stages: unfamiliar prose preferences,
observations versus desired responses, exclusions, protected inputs and conflicting scopes. Check
code-owned guarantees deterministically and meaning/adherence through human review. Measure actual
missing work and editing time; do not add feature-specific eval machinery or equate saved memory with
improvement.

The target one-shot requires roughly ten minutes' review without inventing central play material;
measure this with the DM rather than declaring it from tests. The first release is scoped to standalone
authoring/review/maps plus security/restore. Campaign grounding/memory, broader encounter profiles and
print each earn later gates; they do not postpone standalone usability. Extend frozen perspective,
retcon, retrieval/citation, extraction and operations cases as those capabilities are enabled. Leakage
has zero tolerance; other thresholds come from measured baselines.

## 18. Explicit Deferrals

Do not add initially:

- LangChain/LangGraph or autonomous/multiple named agents;
- `pi-agent-core` without measured open-ended-loop need;
- a universal generation context;
- a full encounter-engine package;
- Neo4j, a dedicated vector database, another canonical store, or a broker;
- local chat serving without separate capacity/privacy/cost justification;
- public gateway or MCP exposure;
- a combat simulator/live HP/initiative/token tracker;
- regional/world or illustration-first maps;
- automatic rewriting of human-authored Markdown;
- continuous transcript ingestion;
- queues, caches, or domain microservices before synchronous/PostgreSQL run records prove inadequate.

Optional later work includes custom calendars, alternate-history inheritance, player accounts/RLS,
player/NPC-scoped interfaces, map reveal overlays, direct Roll20 integration, local/private MCP or Pi
adapters, and richer real-time campaign assistance. Every addition inherits the same authority,
provenance, scope, and fail-closed boundaries.
