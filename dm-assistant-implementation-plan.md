# DM Assistant Harness — Implementation Plan

## How to Use This Plan

This file defines stable task IDs, dependencies, scope, and acceptance gates. It is not a progress
journal. [`PROJECT_STATUS.md`](PROJECT_STATUS.md) alone selects the live task; completed outcomes are
summarized in [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md), and Git retains detailed implementation
history.

For a work session, read only the selected task plus its linked architecture sections. If this plan
conflicts with [`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md), the
architecture wins until both are reconciled.

Each task should remain independently testable. Models may propose, but no task may give them
preparation approval, canonical commit, arbitrary file/SQL access, scope expansion, deterministic
geometry, or trusted arithmetic.

## Delivery Strategy

The project follows a dungeon-first vertical path:

1. establish the reproducible Workbench, PostgreSQL, private model transport, and pure dungeon kernel;
2. prove provider-independent preparation generation, persistence, rendering, and approval;
3. make bounded prompted Tier A generation dependable before expanding topology or output polish;
4. complete Library ingestion/search and the canonical revision boundary;
5. add precise campaign knowledge, profiles, context compilation, and cited Ask;
6. build encounter preparation over pinned party/rules/dungeon inputs;
7. extract session outcomes into reviewed canonical change sets;
8. finish release security, backup/restore, operations, and acceptance.

The roadmap does not require numeric phase order. Follow explicit dependencies and project status.

## Established Foundation

The following task ranges have durable delivered outcomes and are not restated here in full:

| Tasks | Delivered capability |
| --- | --- |
| P0-01–P0-04 | Python/FastAPI/Typer foundation, configuration, auth/logging, PostgreSQL/Alembic, health and contributor gates |
| P1-01–P1-02 | Immutable Library persistence and safe source discovery/reconciliation |
| P2-01–P2-05 | Versioned embedding projections, resumable runs, hybrid retrieval, and eval records |
| P4-02–P4-03 | Private `pi-ai` gateway and bounded task-scope contracts |
| P5-01 | Entities, aliases, mentions, and merge-safe persistence |
| P7-01–P7-11 | Preparation lifecycle, pure dungeon kernel/exports, and provider-independent/shared Dungeon Studio |
| P7-12b–P7-12f | Atomic publication, bounded model runs, durable attempts, shared orchestration, and safe observability |
| P7-13a–P7-13d | Baseline geometry, renderer callouts, mechanics projection, and DM guide improvements |
| P7-14a–P7-14e | One alpha V1, proof-carrying topology, constructive Tier A layout, and structural prompt integration |
| P10-04 | Native/full-stack container deployment baseline |

See project history and Git for exact commits. Superseded V2/V3/V4 generation plans are intentionally
absent: the pre-retention alpha has one active V1 path.

---

## P7-14f — Staged Tier A Authoring and Anti-Overfitting Evaluation

### Goal

Produce a preparation-ready, human-usable Tier A dungeon through one compact structural model call
plus separately bounded exact-ID enrichment tasks, while preserving deterministic authority,
secrecy, bounded cost, and a valid map on partial failure.

The normative flow, proof boundary, and stress ladder are in
[`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md).

### Structural submission

- Expose only `submit_dungeon_plan` with proposal fields at the tool root and at most one schema
  repair.
- The model supplies room identity/purpose, critical path, bounded branches/loop, gate/dependency,
  named objective, and conservative content slots.
- Remove guide prose, canonical IDs, exact graph edges, dimensions, geometry, visibility, difficulty,
  lifecycle, and persistence from the model contract.
- Map each requested exploration challenge to exactly one `rooms[].encounter = "exploration"` slot
  at the requested location and require one room-local feature affordance; leave unrelated encounter
  slots null.
- Permit at most one nonempty room-content record per room and only one named objective room.
- Repair retains the complete original authorized instruction, bounded prior arguments, and safe
  actionable diagnostics.
- Check measured per-response and cumulative usage before validation/publication. No over-limit or
  unknown-usage result may publish under a policy that requires measured usage.

### Deterministic construction

- Compile the accepted `DungeonPlan` into a connected supported graph and independently recomputable
  `TopologyCertificate`.
- Derive stable IDs, graph edges, gate/secret witnesses, room/port/interior demand, side assignments,
  reserved channels, exact bounds, geometry, visibility, and numeric policy in code.
- Layout must construct every accepted Tier A certificate without random correctness retries.
- Topology, geometry, dependencies, readiness, and player secrecy are independently revalidated.

### Enrichment tasks

Use separate strict Workbench-owned calls for puzzle, exploration, feature, trap, objective, and
bounded room narrative work. Each task:

- receives only exact package/room/slot/marker IDs, local geometry, relevant accepted intent,
  approved facts/sources, and bounded prior summaries;
- has its own context schema, profile/effort, instruction/tool pins, monotonic deadline, output and
  cumulative budgets, and at most one budget-reserved repair;
- rejects foreign IDs, structural fields, cross-task mutation, model-authored numeric difficulty,
  approval, and canonical operations;
- publishes accepted DM-only content as one atomic child while preserving package/map bytes, prior
  enrichments, and unrelated blockers;
- leaves the parent current and stores only body-free diagnostics/measurements on rejection or
  publication failure.

A pure planner orders exact puzzle, exploration, feature, trap, objective, then narrative targets. A
one-step coordinator requires a matching trusted policy and invokes one existing task seam. A bounded
chain repeats only that primitive, advances only accepted children, and stops fail-closed without
approval or canonical writes.

### Continuity and final review

- Derive one bounded creative-continuity projection from the resolved dungeon context and accepted
  plan. Pin its version/hash and exact authorized sources to every task lineage.
- Context builders select only relevant facts and fail before dispatch on stale hashes, unauthorized
  facts, broader source visibility, unsupported citations, or standalone campaign lore.
- Before prompted approval, a pure final gate recomputes continuity/source inheritance, package and
  guide dependencies, required content, exact slot/lineage coverage, typed cross-task references, and
  player secrecy.
- A separate read-only cohesion report covers thematic reinforcement, history/environment causality,
  mechanic/objective unity, progression, intentional motif variation, and selected-lore consistency.
  It may report findings and recommend one targeted existing seam, but cannot edit or approve.
- Prompted approval requires a DM disposition bound to exact specification/report hashes and every
  dimension/finding; requested regeneration blocks transition.

### Evaluation

- Retain the fixed archive packet only as a renderer/secrecy/contract regression.
- Evaluate at least three materially different synthetic Tier A settings and interaction styles,
  including standalone and grounded contexts.
- Blind prompt/model/effort assignments behind stable opaque variants.
- Store only body-free assignment/artifact hashes, validity, repair count, latency, token usage, and
  1–5 human ratings. Never store provider bodies or excerpts as evidence.
- Rate all six cohesion dimensions plus clue logic, player agency, puzzle comprehensibility,
  exploration quality, and DM preparation usefulness; lore ratings apply only when grounded.
- Matrix validation requires exactly one valid run/review for every case/variant and matching hashes
  before aggregation.
- Do not promote a larger model or deeper effort without measured quality improvement.
- Use Luna as the default baseline and follow the recovery plan's matched, repeatable-failure gate
  before comparing Terra; never tune the contract around an isolated model-specific miss.

### Provider rules

- Provider capabilities reflect provider-free wire-contract tests. Codex subscription does not claim
  `hard_output_token_limit`; standard OpenAI API-key transport may claim it only while tests prove the
  exact supported field is serialized.
- All providers retain strict measured publication ceilings, timeout/cancellation, and repair
  reservation. There is no advisory publication bypass.
- Live calls and retries are manual, explicitly authorized, and never CI gates.

### Acceptance

- One staged live Tier A run produces an accepted structural plan, valid certified geometry,
  independently accepted required enrichments, preparation-ready guide, secrecy-clean assets, and
  bounded measured usage.
- Provider-free properties cover 4–8 rooms and seeds with zero exceptions, 100% topology/geometry
  validity, and zero leaks.
- Multi-case blinded evidence identifies a dependable prompt/model/effort profile without
  single-fixture overfitting.
- Every enrichment shares exact continuity/source lineage and cannot mutate the package or another
  task.
- Final deterministic validation and explicit DM disposition run before prompted approval.
- Tier B/C, output catalog, and print work remain outside this acceptance gate.

---

## Deferred P7 Follow-Up

### P7-13e–P7-13g — Output catalog and guarded print

After the P7-14 Tier A gate, resume the compact plan in
[`dungeon-output-refresh-plan.md`](dungeon-output-refresh-plan.md): purpose-oriented assets and
filenames, bounded reference/tactical print, then integrated browser/output evaluation. Revalidate
all old assumptions against the active V1 rather than restoring superseded contracts.

### Player-map reveal overlays

A later authenticated session workflow may publish stable player reveal units and aligned web/print
overlays. It must never send unrevealed geometry or secrets to the player client, mutate the original
package, or treat reveal state as canon. Add leak, registration, partial-reveal, and repeatability
coverage before release.

---

## P1 — Complete Immutable Library and Lexical Search

### P1-03 — Markdown parser and deterministic chunker

- Preserve exact source bytes and parse front matter only as metadata.
- Chunk by heading/semantic block with bounded size/overlap and exact half-open source offsets.
- Preserve heading path, tables, code fences, Unicode, links, and instruction-like untrusted text.
- Version parser/chunker behavior and derive deterministic identities.

**Gate:** every chunk maps to its immutable source span and repeated parsing is byte-equivalent.

### P1-04 — Atomic corpus snapshot activation

- Build a candidate from selected logical-document heads and activate only after all chunks/lexical
  indexes are ready.
- Preserve the prior active snapshot on failure.
- Pin ingestion/parser/chunker configuration and emit provenance-drift warnings without retracting
  canon.

**Gate:** no query sees a partial document set; a snapshot reproduces the exact revision membership.

### P1-05 — Filtered lexical retrieval

- Search by campaign, snapshot, corpus, authority, visibility, and ruleset before ranking.
- Support exact-name/heading boosts, bounded snippets, and stable citation IDs.
- Exclude plans from historical-fact defaults while permitting explicit preparation queries.

**Gate:** wrong-scope data never appears in candidates, snippets, counts, citations, or logs.

### P1-06 — Library CLI/API surface

Provide shared service-backed ingest, list, revision inspection, reconciliation, snapshot, and search
operations through CLI/API. Return resolved scope and exact citations.

**Phase gate:** repeated ingestion is idempotent; edits create immutable revisions/snapshots; lexical
search works without model or embedding credentials.

---

## P3 — Canonical Revisions, Review, and Change Logging

### P3-01 — Revision and change-set schema

Add campaign head/revision, draft/in-review/committed/abandoned change sets, versioned change items,
dependencies, source links, review state, idempotency, and origin metadata. Candidate local IDs must
not create placeholder canonical rows.

### P3-02 — Operation registry and validation

Define versioned typed operations and handlers that write only inside the commit transaction. Separate
hard structural/security errors from overridable semantic warnings; expose no ORM, SQL, or direct
canonical model write.

### P3-03 — Review workflow

Provide shared CLI/API/web services to create, inspect, accept, edit, reject, and validate grouped
change items with evidence, before/after state, warnings, and dependencies.

### P3-04 — Atomic commit

Revalidate against the base revision, reject/rebase stale sets, resolve local IDs, commit accepted
dependency closure, and advance the campaign head in one idempotent transaction. Fault injection must
prove there is no partial revision.

### P3-05 — Readable history and diff

Expose commit, history, revision inspection, and deterministic old/new diff. Every revision has an
editable readable summary plus complete accepted/rejected audit detail.

### P3-06 — Optional exporter

After the phase gate, an idempotent Markdown/JSONL projection may be rebuilt from PostgreSQL. Export
failure never rolls back a canonical commit; automatic Git commits remain optional.

**Phase gate:** no canonical change before commit, stale/failing commits are atomic, old revisions are
queryable, and every revision is explainable.

---

## P4 — Rules, Context Compilation, and General Ask

### P4-01 — Rules and creature source profiles

Add edition/book/section/page/extraction metadata, ordered campaign rules profiles, house-rule
precedence, and authorized creature collections through P3 operations. Cross-edition mixing requires
explicit comparison intent. Fixtures remain invented.

### P4-04 — Task-specific context packets

- Keep a small `GenerationContextEnvelope` for kind/version, resolved scope, visibility, source
  references, and canonical payload hash.
- Define narrow payloads only with their workflows: dungeon, encounter, Ask, extraction, and later
  scene contexts do not share unrelated optional fields.
- Apply hard authorization before selection, bounded per-section budgets, overlap deduplication,
  neighbor expansion, authority/rules labels, and untrusted-evidence delimiters.
- Persist the exact envelope/hash/source links with each run.

**Gate:** changing authorized context changes the hash; models cannot broaden scope; unknown fields or
versions fail explicitly.

### P4-05 — Task profiles and bounded model workflows

Add versioned model/task profiles for provider/model, observed capabilities, normalized effort,
context policy, tools, output schema/limits, fallbacks, and instruction version. Python owns tool
authorization, cumulative budgets, validation, citation checks, abstention, and durable state. No
profile includes approval, commit, arbitrary files, SQL, or scope expansion.

### P4-06 — Shared model settings and streaming UI

Extend the authenticated Workbench shell with gateway login/status, provider/model/effort selection,
SSE progress, cancellation, reconnectable durable runs, and safe errors. OAuth credentials never
reach browser/Python/campaign data. Contract-test with faux providers before live use.

### P4-07 — General Ask workflow

Add prompt/image input, streamed cited answers, cancellation/history, opaque content-addressed
attachments, and a small model-comparison harness. Reuse established gateway, profile, asset, auth,
and run services; keep preparation approval and canonical review distinct.

**Phase gate:** the DM can obtain a concise synthetic cited answer through the browser, inspect
resolved scope/profile, cancel/reconnect, and retain lexical operation when gateway or embedding
runtime is unavailable.

---

## P5 — Structured Campaign Knowledge

### P5-02 — Predicate catalog

Add versioned predicate semantics, type/value constraints, inverse/symmetric/transitive metadata,
functional/exclusivity rules, examples, and lifecycle. Seed a small vocabulary; additions and
retirement use P3 change sets. Derive safe inverse/symmetric/transitive projections rather than
copying canon.

### P5-03 — Events, participants, and evidence

Add revision-ranged canonical events, participant roles, typed many-to-many evidence, visibility, and
supersession/retraction. Plans and allegations remain sources/propositions, not occurred events.

### P5-04 — Sessions and basic time

Implement session provenance, one main timeline, event/scene-relative and table-session anchors,
unknown/approximate values, essential relative relations, strict-order cycle checks, and story
cursors. Preserve raw fictional dates; defer calendar arithmetic and branch inheritance.

### P5-05 — Propositions and perspectives

Add immutable typed proposition content and revision-ranged reality, knowledge, unaware, belief,
suspicion, claim, and public-record assertions. Separate content time, holder stance time, and system
revision time. Include visibility, provenance, derivation, certainty, supersession/retraction, and
optional explicit knowledge-completeness scope.

### P5-06 — Validation and projections

Enforce type/cardinality/exclusivity rules, overlapping explicit contradictions, stance-holder and
knowledge/unaware intervals, suspicious unsupported reveals, derivation cycles, and revision/cursor/
mode/holder-aware state queries. Any materialized state remains rebuildable.

### P5-07 — High-level queries

Provide entity resolution, state/event reads, holder knowledge, related threads, and provenance
explanation. Answers must distinguish reality from perspectives and unknown chronology from absence.

### P5-08 — Retrieval/context integration and evals

Prefer accepted structured state for facts, expand bounded evidence/narrative, expose conflicts, and
freeze synthetic perspective/retcon/time/alias/plan/knowledge evals.

**Phase gate:** a synthetic campaign supports correct current/historical state, belief, knowledge,
event, relative-time, and provenance queries; retcons preserve prior system history.

---

## P6 — Character Sheets and Important Items

### P6-01 — Versioned profile schemas

Add source-linked character-sheet and important-item snapshots with validated common 5e/2024 fields,
separate source/computed values, formula/rules pins, revision ranges, and no live tactical state.
Binary source assets are added only when a chosen adapter requires them.

### P6-02 — Adapter protocol and synthetic adapter

Define format detection, parse results, warnings, unknown/custom-field preservation, and source-span
provenance. Implement a synthetic JSON/Markdown adapter; unsupported formats fail explicitly.

### P6-03 — First real sheet adapter

After selecting an actual source format, add redacted/synthetic fixtures, parse its stable fields,
preserve unsupported data, and document limitations. External services require explicit credentials
and terms. This task does not block synthetic P8 inputs.

### P6-04 — Profile review

Generate grouped field-level diffs, propose updates through P3, flag conflicts with canonical
possession/location, and include readable revision summaries.

### P6-05 — Profile query/context integration

Answer mechanical sheet/item questions with source citations and distinguish profile data, computed
values, and temporal story state.

**Phase gate:** synthetic and selected real-format profiles can be ingested, reviewed, committed,
diffed, and queried without introducing combat tracking.

---

## P8 — Party-Aware Encounter Generation

### P8-01 — Creature profiles and adapters

Add complete edition-tagged stat blocks, source/variant lineage, synthetic adapters, and deterministic
completeness/challenge checks. Generated variants retain a full usable block and explicit parent diff.

### P8-02 — Party and playstyle snapshots

Pin sheet versions, party composition/level, rules profile, generation assumptions, DM-approved
optimization/risk/duration/rest/style/accessibility preferences, and optional one-run resource
overrides. Model suggestions never silently become permanent player traits.

### P8-03 — Difficulty evaluator

Implement cited edition-aware deterministic encounter budgets and report official baseline separately
from adjusted recommendation. Validate quantities, assumptions, variants, and scaling with golden and
property tests.

### P8-04 — Typed encounter packages and context

Define strict combat, social, exploration, puzzle, trap, hazard, and mixed packages with stakes,
objectives, room/zone IDs, participants, positions/waves, terrain, tactics, checks/DCs, clues/
solutions/counterplay, outcomes, rewards, variants, citations, and audience-safe content. Use a
separate `EncounterGenerationContext` for party/rules/creatures/geometry/pacing.

### P8-05 — Combat composition and map fit

Select authorized creatures/variants, validate footprints/movement/range/cover/objective space,
place anchors/waves deterministically, and provide tactics, morale, non-kill outcomes, and recalculated
variants rather than hit-point-only scaling.

### P8-06 — Noncombat validators

Require goals/leverage/multiple resolutions for social encounters; approaches/consequences for
exploration; warning/trigger/effect/counterplay for traps/hazards; and solution/clues/hints/alternate
handling/failure/reset for puzzles. Player output omits hidden solutions and difficulties.

### P8-07 — Constrained encounter tools

Use explicit task profiles and bounded tools over pinned encounter context. Models propose
composition/content; deterministic arithmetic, stat completeness, map fit, type validation,
persistence, approval, and canon remain authoritative outside the model.

### P8-08 — Dungeon-wide population

Assign stable room-linked encounters with varied pacing, attrition/rest, clues/gates, factions,
treasure, and optional routes. Regenerate or scale one encounter without rewriting the dungeon.

### P8-09 — Review, export, and extraction decision

Provide shared generate/inspect/validate/compare/scale/export/approve workflows and DM/player-safe
packets. Measure whether deterministic mechanics form a reusable package seam; retain them in the
Workbench unless evidence justifies extracting only `encounter-mechanics`.

**Phase gate:** complete combat/noncombat packages pass arithmetic, stat, map-fit, pacing, secrecy,
lineage, and reproducibility checks; approval/use changes no canon.

---

## P9 — Session-Close Extraction

### P9-01 — Run and stage contracts

Link immutable session notes, session/base revision, used preparation versions, exact profiles/tools,
and versioned stage outputs. Use stable candidate IDs and idempotent durable runs; create no canonical
placeholders.

### P9-02 — Entity/source-span resolution

Extract exact mentions, resolve confident aliases, surface ambiguity, and propose new entities/merges
for review while carrying stable candidates through later stages.

### P9-03 — Events and participants

Separate occurred events from plans, hypotheticals, recaps, and allegations. Propose participants,
roles, locations, approximate/relative anchors, and exact evidence in dependency-aware groups.

### P9-04 — State, perspective, time, and threads

Propose reality/state/relationship, knowledge/belief/claim/reveal, quest/thread, temporal, retcon, and
supported profile/item/preparation-outcome changes through bounded typed calls. Do not infer that a
prepared outcome occurred.

### P9-05 — Conflict and continuity review

Run deterministic validation first, then optional semantic warning review for impossible status/
location/knowledge, stale state, and source-authority confusion. Warnings cannot auto-reject or commit.

### P9-06 — Grouped human review

Show source, event group, before/after state, dependencies, explicit/inferred labels, and warnings.
Support group/item accept/edit/reject and revalidate edits; rejected content remains in source/run
history.

### P9-07 — End-to-end close session

Expose shared close-session, review, commit, and history services through CLI/API/web.

**Phase gate:** a synthetic note creates a cited reviewable change set; no query changes before commit;
accepted dependencies commit atomically; retries do not duplicate; rejected items do not pollute
canon.

---

## P10 — Security, Operations, and Release

### P10-01 — Auth and policy audit

Audit default-deny auth, private gateway reachability, and centralized campaign/visibility/source/
model-task policy across every route and workflow. Keep labels ready for future principals without
implementing player accounts or RLS prematurely.

### P10-02 — Adversarial and leakage tests

Cover prompt injection, traversal, malformed/oversized input, wrong campaign/authority/ruleset,
inaccessible snippets/counts/citations, player-map leaks, malicious specs, cross-domain context,
asset/attachment escape, model scope/approval/commit attempts, and OAuth/token exposure. Any secret or
cross-campaign leak blocks release.

### P10-03 — Backup, restore, and rebuild

Document and drill application-consistent PostgreSQL, source, and approved/non-rebuildable asset
backup. Keep OAuth credentials separate. Prove citations and lineage survive restore and that
embeddings/indexes/rendered derivatives rebuild from pinned sources/contracts.

### P10-05 — Durable jobs and observability

Make long-running ingestion, embedding, model, generation, export, and extraction work diagnosable and
retryable after restart. Add PostgreSQL leasing only when synchronous work is insufficient; add safe
latency/error/usage/cost/version metrics without a queue by default.

### P10-06 — Aggregate acceptance

Run frozen functional, retrieval, model-profile, extraction, dungeon, encounter, secrecy, operations,
and restore suites. Record objective baselines and a tested rollback/restore path.

**Release gate:** all domain phase gates pass; unauthorized leakage is zero; the deployed Workbench,
private gateway, database, sources, and retained assets can be backed up, restored, diagnosed, and
rolled back.

---

## Later Backlog

- Player accounts, explicit audiences, and database RLS defense in depth.
- Player/NPC-scoped interaction and player-map reveal overlays.
- Custom calendars, interval algebra, alternate-history inheritance/merging.
- Persistent scenes, transcript ingestion, and live character/combat resources.
- Reviewed Markdown projections and optional Git export commits.
- Local chat serving, illustration enhancement, regional/world maps.
- Direct Roll20 upload/dynamic lighting and live token state.
- Local/private MCP or Pi extension adapters.
- `pi-agent-core` only after measured open-ended tool-loop/steering needs.
- Queue, cache, dedicated vector/graph store, or domain service only after measured need.

## Test and Fixture Policy

Use separate layers for unit/property, PostgreSQL integration, API/CLI/web/gateway contracts,
golden/snapshot evals, adversarial security, and operational restore/retry tests.

All fixtures are synthetic. Include difficult perspective, plan/canon, retcon, alias, split-scene,
unknown-time, dungeon, encounter, and source-authority cases. Never commit real campaign/rules/
bestiary/sheet/provider material. Freeze time, random seeds, provider behavior, and stable fixture IDs
where reproducibility matters.

Package and root tests run separately while duplicate basenames remain. The pure dungeon dependency
test must reject Workbench, database, web, retrieval, and provider imports.

## Migration Discipline

- Never edit an applied/shared migration to accommodate later schema work.
- Prefer task IDs in migration names.
- Test upgrades; test downgrade/upgrade where reversible.
- Make backfills idempotent and resumable.
- Preserve canonical revision semantics or provide an explicit reviewed conversion report.
- Never run a model call from a migration.
- Alembic's `alembic_version` is the schema-version authority.

## Handoff Rule

Follow `AGENTS.md`: stop at a safe boundary, run focused checks plus `git diff --check`, and update the
bounded `PROJECT_STATUS.md` with semantic WIP state and one concrete next action. Do not copy Git's
branch/HEAD/status output into documentation, and do not turn this plan or architecture into a session
journal.
