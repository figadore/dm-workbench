# Project History

> This is an archival, consolidated record. It is intentionally not a coding
> resume point; use [`PROJECT_STATUS.md`](PROJECT_STATUS.md) for current work.
> Historical statements below describe their recorded milestone only. Current
> working-tree state, task priority, and verification are authoritative only in
> `PROJECT_STATUS.md`.

## Reconciliation Notes

The former status file mixed live handoff data with sequential WIP notes. That
made old next-task, working-tree, and test statements appear current after later
commits superseded them. This file preserves only compact milestone history:

- Current task priority, working-tree state, and verification live exclusively in
  `PROJECT_STATUS.md`; no statement below is a resume instruction.
- Old recommendations for P7-10b, P7-12, P3-01, rebuilds, or live retries are
  superseded. P7-14b later removed the disposable V2/V3/V4 generation paths and
  restored one active alpha V1 path.
- P3-01 remains unnecessary for standalone preparation generation; it is required
  only before promotion into campaign canon.
- Historical provider IDs, response bodies, detailed review chronology, and
  environment-specific logs are omitted. Git retains the original handoffs when
  archaeology is necessary.

## Delivered Milestones

### Foundations, sources, retrieval, and gateway

- **P0-01–P0-04:** Python/FastAPI/Typer foundation, typed configuration,
  default-deny auth, structured logging, PostgreSQL/pgvector, Alembic,
  readiness, diagnostics, and contributor gates.
- **P1-01–P1-02:** Immutable source documents/revisions/chunks/snapshots and
  safe managed-source discovery/reconciliation.
- **P2-01–P2-05:** Separate embedding runtime, pinned derivations/runs, filtered
  vector retrieval with lexical fallback, deterministic fusion/context, and
  source-body-free retrieval audit/evaluation.
- **P4-02:** Private Node `pi-ai` gateway with allowlisted providers, credential
  isolation, internal-token HTTP/SSE, display-safe login coordination,
  normalized streams, and cancellation.
- **P4-03:** Bounded task-scope contracts with standalone-dungeon grounding
  rejection.
- **P5-01:** Campaign-knowledge entity/alias/mention persistence (`eea08a4`).

### Dungeon Studio and preparation lifecycle

- **P7-01–P7-08:** Immutable preparation artifacts/versions/runs/assets and the
  independently packaged deterministic dungeon topology, layout, validation,
  SVG/PNG/PDF, and Roll20 exports.
- **P7-10a / P7-10a.1:** Gateway-backed CLI prompting, model/default resolution,
  campaign bootstrap/switching, private OAuth coordination, bounded transport
  failures, and Compose/runtime hardening.
- **P7-10b / P7-11:** Shared CLI/API/web Dungeon Studio workflows, durable web
  prompt status/cancellation, provider-free browser integration coverage,
  artifact comparison/regeneration, exports, preparation approval, and
  DM-only notes/callouts.
- **P7-12a:** V2 ownership and compatibility boundary documented: Workbench owns
  provider/attempt/persistence; pure `dm_dungeon` owns strict design contracts,
  compilation, diagnostics, and deterministic kernel work.
- **P7-12b:** Atomic complete-package publication with staged assets, immutable
  version creation, current-version update, and terminal run state in one
  transaction.
- **P7-12c:** Shared model-run budgets/deadlines, cancellation, native transcript
  roles, safe tool diagnostics, and measured-usage handling.
- **P7-12d:** Strict compact `DungeonDesignSpecV2` and pure deterministic V2
  compiler. Models cannot provide canonical IDs, exact dimensions/capacities,
  seed, visibility, or lifecycle fields.
- **P7-12e:** One-submit structured V2 proposal flow with bounded abstention and
  at most one fresh repair.
- **P7-12f:** Shared `DungeonPromptApplicationService` for CLI and web; durable
  `dungeon_prompt_v2` attempts begin before provider contact and link safely to
  the separate generated-artifact run/version. Ordinary logs are body-free and
  run inspection exposes safe metadata only.
- **P7-14a:** Adopted the proof-carrying constructive Tier A recovery architecture,
  added topology-math guidance and active-path safety/property regressions, and
  deleted the known-bad output baseline (`25c031e`).
- **P7-14b:** Collapsed model orchestration, proposal/compiler/mechanics/package,
  layout dispatch, rendering, and exports to one suffix-free alpha V1; deleted
  disposable V2/V3/V4 paths/readers/tests and restored green focused gates
  (`1bad985`, `dd54b4e`).
- **P7-14c:** Replaced arbitrary edge authoring with the bounded `DungeonPlan`,
  deterministic series/parallel-with-spurs graph construction, stable semantic IDs,
  and an independently recomputed topology/reachability/gate/demand/embedding
  certificate (`cc02441`).
- **P7-14d:** Replaced active random room placement/routing with a certificate-driven
  Tier A baseline: side-specific ports, reserved noncrossing channels, demand-expanded
  rooms, exact precomputed bounds, corridor-realized door openings, and 4–8 room
  branch/loop/secret property coverage. Seeds now pin a zero-draw proven baseline for
  future optional compaction rather than supply correctness retries.
- **P7-14e:** Characterized the one-call structural/guide workflow through shared
  CLI, browser, faux-provider, review-packet, renderer, and secrecy gates. Repeated
  human review made the fixed synthetic guide runnable but exposed fixture-specific
  overfitting and the need to separate creative responsibilities. The direct-root
  `submit_dungeon_plan` contract, measured token enforcement, bounded repair input
  reservation, durable body-free diagnostics, and frozen Tier A canary policy were
  established. Codex ordinary live use remained paused because the pinned transport
  did not send a hard output limit.
- **P7-14f staged enrichment through feature dispatch:** Removed prose-heavy guide
  content from the structural proposal and retained truthful readiness blockers
  (`ae6d406`). Added exact-package puzzle context/projection (`088568d`) and bounded
  puzzle dispatch (`edc6245`); exact-ID exploration contracts and bounded atomic child
  publication (`edc6245`, `6667148`); and exact-ID feature-interaction contracts plus
  bounded dispatch/publication (`95af1c2`, `7387d29`). Every accepted child preserves
  package/map bytes and prior task content; rejection leaves its parent current with
  compact body-free diagnostics. The anti-overfitting prompt/canary cleanup is at
  `ea812d6`. Trap, narrative, automatic staged orchestration, and staged live evaluation
  remained incomplete at this milestone.

### Deployment baseline

- **P10-04:** Pinned non-root Workbench/gateway images, private Compose topology,
  migration-aware startup/readiness, isolated storage/credential volumes,
  managed source import, and native/full-stack workflow documentation.

## Historical Verification Summary

Milestone-specific focused Python, Node, formatting, type-checking, migration,
and disposable PostgreSQL/Compose checks were recorded as passing when their
respective tasks completed. Some older broad gates also recorded unrelated
Library/schema failures or local `.env` fixture conflicts. Those records are
not evidence about the current task; use and rerun the gates named in
`PROJECT_STATUS.md`.

## Persistent Design Decisions

- Models propose; they never commit canon or approve preparation artifacts.
- Canonical writes require a validated change set and one atomic campaign
  revision. Preparation approval/use never makes planned events canonical.
- `dm_dungeon` remains pure and owns deterministic IDs, geometry, pathfinding,
  validation, rendering, and exports.
- Source authorization/visibility filtering precedes retrieval and model context
  construction; source revisions and cited spans are immutable.
- Player-facing exports fail closed for unreleased information.
- Synthetic fixtures only: no campaign text, copyrighted rules/bestiary content,
  sheets, credentials, or provider responses.

## Historical Public Baseline

The public baseline uses the GitHub author identity and `AGPL-3.0-only`.
Historical public snapshots cover the final architecture/roadmap, initial
Python scaffold, and aggregate implementation through P1-02. Earlier local
planning history is outside public `main`.
