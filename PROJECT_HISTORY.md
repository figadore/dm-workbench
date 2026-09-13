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

## Standalone One-Shot Product Realignment

- Adopted a unified dungeon-first roadmap: prove a runnable standalone one-shot, integrate cohesive
  authoring and an early usable review workspace, improve maps, add scoped assistant revision, then
  selected campaign grounding and broader memory. Superseded recovery/output plans are pointers.
- Inspection of three technically passing packets found missing concrete puzzle evidence/answers,
  repetitive policy-like guide text, and sparse schematic maps. This was a product/code assessment,
  not a completed blinded human review or playtest; the packets do not establish play readiness.
- The target replaces mandatory six-family enrichment/per-feature publication with whole-adventure
  outline and content passes, bounded correction, attempt checkpoints, and meaningful draft versions.
  Existing transport, storage, pure geometry, security, and reusable tests remain valuable foundations.
- Browser usability is an early product gate: normal owner sign-in, inline map/guide review, manual
  editing and purpose-based exports precede campaign integration. Contextual Ask is read-only;
  proposed revisions require visible scope, human acceptance and stale-base protection.
- Documentation realignment does not implement the new authoring pipeline, authentication, editor,
  or conversations. Alpha retention remains uncrossed; real retained use triggers the existing gate.

## Application-Wide Guidance Design

- Specified scoped natural-language guidance across model-facing workflows, separating reported
  tendencies, desired direction and requirements. Structure only what code consumes; feature examples
  do not establish dedicated subsystems. Architecture §9 owns the shared contract.
- P7-16 introduces explicit guidance; P7-18 adds human-confirmed preferences and demand-driven reusable
  procedures. These are planned capabilities, not implemented behavior or changes to model authority.

## P7-15a Fresh Reference Packet

- Following review of the two unaccepted candidates, authored a separate synthetic five-room caper
  using explicitly licensed Dyson Logos cartography and published presentation/design references.
  Added a static map-and-guide reading copy and lightweight stop-at-first-confusion feedback prompts.
- This is a documentation target, not generated pipeline output, a kernel-validated map, a browser
  application feature, or phase acceptance. Neither candidate was merged.
- Reese completed a read-through, preferred model-made corrections, and after three feedback rounds
  described the reference as “at least 95% good,” with only minor edits left. Findings covered delivery
  cues, map callouts and causal gaps. This establishes a useful revised target, not first-pass generator
  reliability, measured review/editing time, or tabletop acceptance.
- Post-review P7-15b roadmap decision: test causal/counterfactual consistency in initial prompting
  independently first; try an additional bounded editorial pass only if that is insufficient. Prefer
  concise replacement over accumulated explanations and measure fresh-case human repair burden,
  guide length and cost before larger investment. This changes the roadmap, not runtime prompts.

## P7-15b Provider-Free Whole-Adventure Prototype

- Added a disposable file adapter over the existing structured-submission runner, technical-repair
  reservation, guide contracts/validators and pure map tools. Three adapted synthetic briefs share
  one validated five-room map; on/off inputs differ only by the general consistency objective.
- Fixture packets provide exact DM guides, audience-filtered SVG maps, input/hash pins, all-attempt
  accounting and blank human worksheets. Schema/reference rejection, one cumulative repair, unknown
  usage, overages, transport failures and no-overwrite output are covered without providers or DB writes.
- Short scripted content and synthetic counters establish plumbing only. No editorial pass, production
  authoring integration, live consistency benefit, human effort/readiness evidence or retention crossing.

## P7-15b Astra/High Feasibility Sample

- Reese authorized the current session model (`openai-codex/gpt-6-astra`, high reasoning), up to two
  submissions and ten minutes of cumulative model-run time, measuring usage without a financial cap.
  Updated the pinned gateway to `pi-ai` 0.85.1; disabled hidden SDK retries/Codex fallback submissions,
  retained technical ceilings and included cached input in normalized usage. Added explicit single-case
  live CLI opt-in with pre-contact attempt journals; production publication/approval remains absent.
- One fresh consistency-on sample used both calls: unsupported feature-reference rejection followed
  by accepted technical repair. Gateway time was 321,752 ms; cumulative usage 30,069 input and 8,241
  output tokens. Accepted guide was 2,987 words, 49.35% over the approximately 2,000-word objective.
- Exact unedited creative output and pins are ignored under `generated/p7-15b-astra-high-01/`.
  No third/editorial call, matched comparison, dollar-charge estimate, human readiness result,
  tabletop evidence or retention crossing is implied. Technical repair exposed a content-slot
  constraint; human review must judge the resulting play material and organization.

- Reese's subsequent review took **28 minutes** and found substantial confusion, weak scene setup,
  an unfamiliar/uncompelling theme, misplaced document/clue content and poor map/guide navigation.
  This is a failed readiness result, not minor polish. Audit confirmed restrictive content slots,
  code-imposed overview order, dual numbering and missing directional/sensory projection. Initial
  request/final submission are retained; first-response/full-repair-prompt bodies are not. The private
  audit labels those gaps; no new call or rewrite was made. Human review is recorded in
  `docs/p7-15b/reviews/astra-high-reese-review.md`; editing time and tabletop evidence remain unknown.

## P7-15b Reference-Led Authoring Correction

- Reese explicitly selected **The Last Pay Chest** (Nell/Iona) as the workable structural reference,
  not Bellglass/Neris or an inferred preferred section order. Plan/architecture now specify its short
  job/DM context, map-numbered local room keys and concluding settlement pattern without copying its
  plot, noncombat scope, session-length assumption or unsupported reference-map geometry.
- Planned correction separates ordinary room-local private prose from mechanical feature reservations,
  preserves local clue/document/conditional-delivery content, and gives code one numbering/exit scheme.
  Provider-free projection/secrecy checks precede further full trials; private diagnostic retention
  must cover creative candidates/repair inputs without blanket transport capture. Documentation only:
  no implementation, seed selection, live authorization, readiness result or phase advance is implied.

## Persistent Decisions

- Models propose; humans approve preparation and commit canon.
- Canonical writes require a validated change set and one atomic revision; preparation use never
  implies an event occurred.
- `dm_dungeon` remains pure and owns deterministic mechanics and exports.
- Source authorization precedes retrieval/context construction; revisions and cited spans are
  immutable.
- Player-facing output fails closed, and tests/fixtures contain synthetic authorized material only.
- Until the retention gate is explicitly crossed, disposable active V1 contracts evolve in place.
