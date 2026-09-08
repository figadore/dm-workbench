# Project History

> Durable milestone summary only. Use [`PROJECT_STATUS.md`](PROJECT_STATUS.md) for current work and
> Git for exact diffs, commits, old handoffs, verification logs, and run-by-run investigations.

## Foundations and Platform

- **P0-01–P0-04:** established the Python 3.12/FastAPI/Typer project, typed configuration,
  default-deny authentication, structured secret-safe logging, PostgreSQL/pgvector, Alembic,
  readiness diagnostics, and contributor quality gates.
- **P10-04:** added pinned non-root Workbench and model-gateway images, private Compose networking,
  migration-aware startup, managed source/asset/credential volumes, source import, and native/full
  stack workflows.
- The public baseline uses `AGPL-3.0-only`, synthetic fixtures, and no bundled campaign, rules,
  bestiary, sheet, credential, or provider-response data.

## Library, Retrieval, and Campaign Knowledge

- **P1-01–P1-02:** delivered immutable source documents, path history, exact revisions/chunks,
  candidate/active corpus snapshots, and safe idempotent filesystem discovery/reconciliation.
- **P2-01–P2-05:** delivered separate embedding profiles and resumable derivations, filtered vector
  retrieval with lexical fallback, deterministic fusion/context selection, and source-body-free
  retrieval audit/evaluation.
- **P5-01:** added campaign entities, aliases, mentions, and merge-safe persistence.
- P3 canonical revisions remain unnecessary for standalone preparation generation but are required
  before generated facts, imports, or session outcomes can become campaign canon.

## Model Gateway and Prompting

- **P4-02:** delivered the private Node `pi-ai` gateway with allowlisted providers, isolated
  credentials, internal bearer authentication, normalized HTTP/SSE contracts, login coordination,
  usage reporting, and cancellation.
- **P4-03:** delivered bounded task-scope contracts and rejection of implicit campaign grounding for
  standalone dungeon generation.
- **P7-10a/P7-10a.1:** added gateway-backed CLI prompting, campaign/default resolution, OAuth
  coordination, pinned provider/model/effort/seed/title lineage, and safe transport failures.
- **P7-10b/P7-11:** unified CLI/API/web Dungeon Studio services, durable web prompt status and
  cancellation, browser/provider-free integration, compare/regenerate/export, and preparation
  approval without granting the model approval or canonical authority.

## Dungeon Kernel and Preparation Lifecycle

- **P7-01–P7-08:** delivered immutable preparation artifacts/versions/runs/assets and the independent
  pure `dm_dungeon` topology, layout, geometry validation, SVG/PNG/PDF, and Roll20 kernel.
- **P7-12b–P7-12f:** hardened atomic package publication, staged assets, cumulative model budgets,
  normalized transcript roles, stable safe errors, durable prompt attempts, shared CLI/web
  orchestration, and body-free observability.
- Output review identified geometry, annotation, guide, asset-catalog, and sparse-print defects.
  P7-13a–P7-13d corrected the baseline geometry/renderer/guide contracts; later catalog and print
  work was paused by the alpha reset.

## P7-14 Alpha Reset

- **P7-14a:** adopted a proof-carrying constructive Tier A architecture, added topology mathematics
  and active-path safety/property regressions, and removed the known-bad output baseline.
- **P7-14b:** collapsed disposable V1/V2/V3/V4 generation paths to one active suffix-free V1 and
  deleted obsolete readers, dispatch, tests, and fixtures.
- **P7-14c:** replaced arbitrary model-authored edges with `DungeonPlan`, deterministic graph
  construction, stable semantic IDs, and an independently recomputed topology/gate/demand/
  embedding certificate.
- **P7-14d:** replaced random place-and-route correctness with certificate-driven rooms, side ports,
  reserved channels, exact bounds, and provider-free 4–8 room branch/loop/secret properties.
- **P7-14e:** established one structural `submit_dungeon_plan` call, one bounded schema repair,
  measured token enforcement, concise keyed guide assembly, renderer/secrecy review packets, and a
  frozen Tier A canary. Repeated single-fixture review demonstrated contract expressiveness but not
  general content quality.
- **P7-14f:** removed guide prose from the structural proposal and added independently bounded,
  exact-ID puzzle, exploration, feature, trap, objective, and room-narrative tasks. Each task has its
  own strict context/profile/budget/repair and atomically publishes only an accepted DM-only child;
  failures preserve the prior map and readiness blockers.
- A pure planner, exact-policy one-step coordinator, bounded chain, shared creative-continuity pin,
  final source/dependency/lineage/secrecy gate, non-authoritative cohesion report, and hash-bound DM
  disposition now cover the complete staged workflow without approval or canonical operations.
- The anti-overfitting foundation contains three materially different synthetic Tier A cases, opaque
  variants, body-free run evidence, blinded ratings, and fail-closed matrix aggregation. Synthetic
  arithmetic validates the evaluator but is not human quality evidence.
- Provider-contract work proved that Codex subscription does not support a pre-consumption output
  token field, while the standard OpenAI API-key adapter does. All providers retain strict measured
  publication ceilings; Codex cannot claim a hard-output-cap capability.
- Successive disposable canaries exposed general schema/repair/slot-mapping gaps that were repaired
  provider-free. The latest guidance maps requested exploration challenges one-to-one to structural
  exploration slots with local affordances.
- Exact Codex `gpt-5.4` later returned normalized `model_unavailable`, while bounded `gpt-5.4-mini`
  and `gpt-5.5` controls succeeded. This isolated an exact-model availability/entitlement condition;
  it did not provide Tier A quality evidence.

## Persistent Decisions

- Models propose; humans approve preparation and commit canon.
- Canonical writes require a validated change set and one atomic revision; preparation use never
  implies an event occurred.
- `dm_dungeon` remains pure and owns deterministic mechanics and exports.
- Source authorization precedes retrieval/context construction; revisions and cited spans are
  immutable.
- Player-facing output fails closed, and tests/fixtures contain synthetic authorized material only.
- Until the retention gate is explicitly crossed, disposable active V1 contracts evolve in place.
