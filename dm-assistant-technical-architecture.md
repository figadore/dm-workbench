# DM Assistant Harness — Technical Architecture

## 1. System Shape

The product is a self-hosted DM Workbench for campaign memory, cited rules/campaign questions,
dungeon and encounter preparation, and reviewed session updates.

Initial deployment contains only:

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
7. **Explicit uncertainty:** missing, disputed, weakly sourced, or temporally incomparable information
   produces unknown/conflict rather than invention.
8. **Deterministic mechanics:** models express typed creative intent; code owns IDs, graph
   construction, geometry, pathfinding, rules arithmetic, validation, rendering, and exports.
9. **Reproducible generation:** every artifact pins scope, sources, context hash, seed, contracts,
   compiler/generator/renderer versions, model/tool lineage, validation, and parentage.
10. **Package purity:** `dm_dungeon` runs in the Workbench process but imports no Workbench, FastAPI,
    SQLAlchemy, retrieval, repository, or provider code.
11. **Task-specific context:** workflows share a small scope/provenance envelope, not one universal
    optional-field payload.
12. **Fail-closed publication:** player output omits secret/unclassified content before rendering;
    unsafe or incomplete preparation cannot be approved.
13. **Explainable commits:** every campaign revision has a readable summary and complete accepted-item
    and evidence history.
14. **Synthetic repository data:** no real campaign text, copyrighted rules/bestiary content, sheets,
    credentials, or provider responses enter fixtures.

## 3. Alpha Retention and Versioning

The retention gate is a product/data commitment, not a code milestone. Until both this architecture
and `PROJECT_STATUS.md` declare it crossed:

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
- **Dungeon Studio:** dungeon context, prompting, kernel invocation, review, export, approval.
- **Encounter Studio:** encounter composition plus deterministic arithmetic/completeness/map fit.
- **Session Desk:** notes, extraction, grouped review, and canonical change-set submission.
- **Assistant:** cited campaign/rules questions and other bounded model tasks.
- **Settings:** non-secret provider/model/profile configuration and authentication coordination.

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

Browser login creates a short-lived signed session containing only principal, expiry, and random CSRF
token; it never stores the API token. Browser writes require constant-time CSRF matching. Cookies are
HttpOnly and SameSite-strict, and Secure in production. Templates escape values and responses use a
restrictive CSP/nosniff policy. Bearer authentication remains available for CLI/API automation.

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
SVG/PNG/text/JSON/PDF may open under format-specific security policy; ZIP is download-only.

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
Transient full debug capture is explicit, local, sensitive, and not ordinary persistence.

### Agent framework policy

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

Standalone dungeon generation uses its campaign only as a preparation owner and contains no campaign
revision, corpus, rules profile, retrieval, or citations unless the DM explicitly enables grounding.
Missing lore remains unknown.

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

### Boundary and representations

The active alpha uses four distinct V1 representations:

1. **`DungeonPlan`:** compact human/model creative progression and content-slot intent using local
   refs.
2. **`TopologyCertificate`:** compiler-owned exact graph, supported grammar, IDs, mechanics/demand,
   reachability/loop/gate/secret witnesses, port assignments, and embedding bands.
3. **`LayoutRequest`:** certificate plus server seed, optional maximum bounds, and explicit locks.
4. **`DungeonPackage`:** exact renderer-neutral floors, rooms, openings, connections, mechanics,
   features/zones/markers, encounter demand, anchors, and audience layers.

Local refs are noncanonical relation handles. The compiler derives semantic IDs from the V1 compiler
pin and local semantic identity, independent of seed, prose, and array order. Established IDs enter
only explicit later edit/regeneration workflows. Deterministic package code never calls `uuid4()`.

Geometry-affecting mechanics and reserved demand belong in the package. Prose-heavy DM guidance stays
in the Workbench specification and references exact package IDs.

### Structural generation

Alpha V1 exposes one structural tool:

```text
submit_dungeon_plan(proposal_version, plan, ...)
```

Fields are direct root arguments; there is no redundant proposal wrapper or guide-content payload.
The model declares title/premise/themes, room identities/purposes, critical path, bounded branches/
loop, secrets, gate/dependency, objective, and requested content slots. Every non-null encounter
reserves a later task; unrequested slots stay null.

The tool validates the proposal, compiles/certifies topology, and performs constructive preflight. It
returns only accepted hash/count/certificate/warnings or bounded code/path/ref/repair diagnostics. It
neither persists nor approves. One schema-invalid proposal may receive one fresh bounded repair with
the original authorized task and prior arguments. Deterministic failures do not request a new model
graph.

The Workbench owns context, provider calls, attempts, persistence, and approval. `dm_dungeon` owns the
plan contract, ID policy, graph/certificate, layout, validation, rendering, and exports. A model cannot
select campaign scope, seed, IDs, exact sizes/coordinates, visibility, lifecycle, renderer syntax,
files, SQL, approval, or canon.

### Topology and constructive layout

Tier A is a one-floor 4–8 room series/parallel-with-spurs class:

- a critical-path backbone guarantees entrance-to-objective connection;
- up to two ordered branches attach to existing rooms;
- at most one supported bypass adds a loop;
- at most one gate has a dependency reachable before it;
- at most one secret route obeys explicit DM/player reachability policy.

Validators recompute connected components, cycle rank, branch/loop witnesses, gate fixed-point order,
secret/public reachability, degree, room/interior demand, side ports, channels, and embedding claims.

Layout assigns backbone columns, branch/loop bands, side-specific openings, and reserved noncrossing
channels; expands rooms for boundary and usable-interior demand; and calculates exact bounds before
emitting cells. An optional maximum must contain the proven bounds. Seeded compaction/mirroring may
vary a valid baseline but cannot provide correctness; failure falls back to construction.

Direct doors are shared-wall openings only when the embedding assigns compatible sides. Other links
use explicit corridors/openings because not every planar graph is a rectangle-contact graph.
Independent grid/path/capacity/secrecy validation catches implementation bugs and never triggers
random retries. Mathematical details live beside the validator in `TOPOLOGY_MATH.md`.

### Staged enrichment

After exact IDs and geometry, separate strict tasks author puzzle, exploration, feature, trap,
objective, and bounded room narrative content. Each task has its own payload, profile/effort,
instruction/schema, budget/repair, diagnostics, and lineage.

Trusted builders provide only exact local IDs/geometry, accepted relevant intent, authorized facts and
sources, and bounded summaries of prior accepted mechanics. Outputs may alter only their selected
guide entry. Models do not author numeric DCs or structural state. Accepted output creates one DM-only
child version and preserves package/map bytes and prior work; rejection keeps the parent and body-free
diagnostics.

A dungeon-specific creative-continuity projection carries premise/themes, room purposes, progression/
objective, selected history/environment/factions/hooks, tone, motif constraints, and source refs. It
is canonical-hashed and pinned to every task. Narrow payloads select from it; they do not copy the full
guide or corpus. Stale or unauthorized projection state fails before dispatch.

A pure planner compares package slots, guide state, blockers, and accepted lineage and chooses one
exact target in deterministic order. A matching one-step coordinator invokes only that task seam; a
bounded chain repeats it and advances only accepted children. Planning/coordination performs no
approval or canonical operation.

### Guide and approval gate

Guide assembly assigns entry-first presentation numbers independent of stable IDs. Each room has
concise player-observable read-aloud/framing and locally grouped actionable doors, checks, clues,
pressure, triggers, consequences, features, puzzles, and objectives. Ordinary map-visible
connectivity and repetitive sensory/purpose summaries are omitted. Missing required content remains a
readiness blocker.

Before prompted preparation approval, a pure gate recomputes continuity/source inheritance,
package/guide dependencies, exact slot/lineage coverage, typed cross-task references, readiness, and
player secrecy. It has no persistence/provider/approval/canonical operation.

A read-only cohesion report covers theme, history/environment causality, mechanic/objective unity,
progression, motif variation, and grounded-lore consistency. It can name evidence and recommend one
targeted existing seam but cannot edit or approve. A DM disposition binds exact report/specification
hashes and every finding; requested regeneration blocks approval. Provider-independent manually
created artifacts retain their ordinary readiness-based approval path.

### Rendering and exports

The package is renderer-neutral. SVG is the deterministic semantic vector layer; PNG is produced from
the same filtered geometry. Audience filtering occurs before XML or raster construction—CSS hiding is
not security.

DM maps use stable short callouts and a code-owned grayscale-safe grammar for rooms, start, ordinary/
secret/locked/trapped doors, traps/hazards, puzzles, clues/keys/treasure, features, objectives, and
transitions. Collision-aware placement measures complete symbol/text bounds and uses leader lines only
when needed. Opaque IDs and generic path anchors are not normal labels.

Player maps default to published geometry only. They omit keys/callouts, objectives, start/encounter
markers, secret doors/areas, traps, lock state, hidden DCs, and solutions. Player-safe physical
features may retain unlabelled shape. Filtered components leave no element, metadata, or full-package
hash fingerprint.

Roll20 bundles contain fixed safe names, grid/gridless PNG, dimensions/hashes, five-foot scale,
origin, visible walls/doors, and optional audience-filtered anchor metadata. They do not promise API
upload or dynamic-lighting import.

New print generation remains disabled until the output-refresh gate. The intended print architecture
separates bounded fit-to-paper reference maps from selected-region tactical tiles at exactly 72 points
per five-foot cell. Tactical preflight must bound pages and occupied coverage; pages require low-ink
grammar, overview/page IDs, crop/registration marks, overlap/alignment, safe margins, actual-size
instructions, and a one-inch calibration mark. Tests inspect both metadata and rendered nonblank
content.

## 14. Encounter Generation

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

The first-party web shell is thin server-rendered HTML with limited HTMX/vanilla JavaScript and SSE.
It supports login, prompts/images, provider/profile selection, streaming/cancellation/reconnect,
review, map preview, and assets. A large SPA is deferred.

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
- extraction evidence and dependency closure.

Structural/security errors block commit or preparation approval. Semantic concerns may be DM-
overridable warnings with recorded rationale. Authorization failures are never overridable through a
model proposal.

Frozen evals should cover structured state, perspective, temporal/retcon behavior, aliases, source
authority, hybrid retrieval, citations/abstention, model/task profiles, strict context contracts,
package isolation, extraction/review, dungeon topology/geometry/rendering/secrecy, creature and
encounter completeness, idempotency, backup/restore, and cost/latency. Leakage has zero tolerance;
other thresholds are set from measured baselines.

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
