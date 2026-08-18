# Project History

> This is an archival, consolidated record. It is intentionally not a coding
> resume point; use [`PROJECT_STATUS.md`](PROJECT_STATUS.md) for current work.
> Historical statements below describe their recorded milestone only. Current
> working-tree state, task priority, and verification are authoritative only in
> `PROJECT_STATUS.md`.

## Reconciliation Notes

The former status file mixed live handoff data with sequential WIP notes. That
made several old statements appear current even after later commits completed or
superseded them. This history resolves those conflicts as follows:

- The completed task is P7-12f (`ad1687d`, 2026-08-16); P7-12g is next. Older
  recommendations for P7-10b, P3-01, P7-12a–f, rebuilds, or live retries are
  superseded.
- The repository working tree was clean when this history was consolidated.
  Old “modified/uncommitted” descriptions were point-in-time handoffs, not
  current state.
- V2 is implemented through shared CLI/web durable-attempt integration. Its
  rollout and any V1 retirement remain undecided pending P7-12g evaluation.
- P3-01 and P5-02 remain unstarted. P3-01 is not a prerequisite for standalone
  preparation generation; it is required only for promotion to campaign canon.
- Historical live-provider IDs, failure details, and environment-specific test
  notes are omitted here because they are neither current operational guidance
  nor needed for implementation.

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

### Deployment baseline

- **P10-04:** Pinned non-root Workbench/gateway images, private Compose topology,
  migration-aware startup/readiness, isolated storage/credential volumes,
  managed source import, and native/full-stack workflow documentation.

## Historical Verification Summary

Milestone-specific focused Python, Node, formatting, type-checking, migration,
and disposable PostgreSQL/Compose checks were recorded as passing when their
respective tasks completed. Some older broad gates also recorded unrelated
Library/schema failures or local `.env` fixture conflicts. Those records are
not evidence about the current task; rerun the relevant P7-12g gates instead.

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
