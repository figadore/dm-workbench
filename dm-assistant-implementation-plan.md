# DM Assistant Harness — Implementation Plan

## How to Use This Plan

This is the ordered delivery roadmap, not a progress journal. Only
[`PROJECT_STATUS.md`](PROJECT_STATUS.md) selects the live task and next action. Read that task and
its architecture references before implementation. Human-readable phase names describe the experience
Reese should be able to see or test. Use task IDs in work and commits.

The [goals](dm-assistant-project-goals.md) define product outcomes; the
[architecture](dm-assistant-technical-architecture.md) defines authority and technical boundaries.
Resolve conflicts there before implementation. Completed code is not proof of product acceptance.

## Delivery Map

| Phase | Task family | What Reese can try at its gate |
| --- | --- | --- |
| 1. A One-Shot Worth Running | P7-15 | Read and walk through a complete standalone adventure; report actual missing work. |
| 2. Prompt to Play | P7-16 | Sign in normally, generate, review map and guide together, edit text, save a draft, export. |
| 3. Maps Worth Exploring | P7-17 | Explore a compact, attractive map with real obstacle terrain and matching room keys. |
| 4. Revise with Your Assistant | P7-18 | Select a room/puzzle/dungeon, ask questions, preview scoped changes, accept or reject. |
| 5. Bring Your Campaign | P7-19 | Attach a captive, rumored relic, or other selected hook without changing canon. |
| 6. Remember What Happened | P1/P3/P4/P5/P6/P8/P9 | Ask sourced campaign questions and review actual session outcomes. |

Each task ends with a runnable demo or inspectable artifact, focused regression tests, and an updated
handoff. Do not start the next phase opportunistically. Shared implementation work within a phase
follows dependencies below. If a task cannot remain a focused, independently testable slice, split it
into named child tasks in this plan before coding; status selects one child, not a phase-long marathon.
No live model call is authorized merely by appearing in this plan.

### UX timing

Phase 1 needs a readable packet, not a new frontend. Phase 2 includes real information design, normal
browser authentication, and manual editing because poor review UX prevents useful feedback. Phase 3
adds map visual quality and spatial interaction. Phase 4 adds contextual LLM collaboration after safe
editing/versioning exists. Campaign integration and exact-scale print do not block this sequence.

### Established foundation and supersession

Reuse P0 platform/auth/database, P1/P2 sources/retrieval foundations, P4 gateway/bounded runners,
P5 entity persistence, P7 preparation/kernel/Studio, and P10 deployment. Verify actual code coverage
before assuming a historical task range is complete; see `PROJECT_HISTORY.md` and Git.

P7-14f's mandatory six-family enrichment/version chain and wrapper-matrix quality gate are superseded
as the product direction. Its three packets remain a useful observed baseline, not accepted playable
one-shots. P7-13e–g's outcomes move into P7-16/P7-17 and the later print gate below. Do not finish old
gates merely to unlock this roadmap. Do not expand old orchestration while replacing it.

## Phase 1 — A One-Shot Worth Running

**References:** architecture §§8, 9, 12, 13, 17. No production migration or layout rewrite required.

### P7-15a — Define “Ready to Run”

- Review the three existing local packets as DM deliverables, not as blinded human ratings by an AI.
  Record concrete absent clues/answers, repeated material, map mismatches, and required authoring work.
  If ignored packets are unavailable, report that gap and use existing synthetic fixtures; do not
  regenerate live provider outputs without authorization.
- Define the narrow one-shot brief: one floor, 5–7 rooms within supported 4–8, one explicit party and
  rules assumption, a session-length target, objective, route choice, opposition, and ending.
- Define an output checklist and a compact synthetic authored example with actual puzzle evidence and
  answer, obstacle procedure, consequence, and conclusion. Include only fields with a consumer.
- Choose a bounded combat policy/authorized source input if combat is included; never treat synthetic
  test stat blocks as proven official balance. Do not defer essential opposition behind full P8.
- Add a simple worksheet: missing essentials, review/edit minutes, map agreement, coherence/variety,
  walkthrough findings, and “would I run it?” Do not build another evaluation service.

**Demo/gate:** Reese can review the target packet format and scope; baseline defects are explicit.
Human confirmation of this standard is required before claiming phase acceptance.

### P7-15b — Try Whole-Adventure Authoring

**Depends on:** P7-15a.

- Use a fixed/existing validated map and selected brief to prototype one complete content submission.
  Later production adds the outline pass; this experiment isolates authoring quality from layout.
- Invoke existing gateway/runners through a disposable CLI/file adapter, not a second production
  authoring engine. Keep exact mechanical/reference validation and bounded correction.
- Compare against existing packets on matched briefs/maps where possible. Label unmatched comparisons;
  do not attribute layout, prompt, or model changes to the authoring strategy alone.
- Exercise provider-free fixtures first. Any live generation/comparison needs explicit authorization.
- Record total usage, latency, failures, actual missing work, and human editing time. At least three
  materially different briefs and a human tabletop walkthrough inform the decision; no provider matrix
  or model-brand-specific promotion gate is required.

**Demo/gate:** complete independent one-shots, with a target of about ten minutes' review and no need
to invent their core content. If they fail, fix the authoring approach before scaling infrastructure.
If live authorization or human review is unavailable, stop at a runnable prototype; do not invent evidence.

## Phase 2 — Prompt to Play

**References:** architecture §§3, 5, 8, 12, 13, 15, 17.

### P7-16a — One Cohesive Authoring Pipeline

**Depends on:** accepted P7-15 evidence.

- Evolve `DungeonPlan` in place for a whole-adventure outline with progression, clue/objective
  relationships, opposition, and bounded geometry-relevant affordances.
- Construct/validate the map with the existing pure engine; author the complete content with the whole
  small adventure and resolved map in context. Target two normal creative passes plus bounded repair,
  not six mandatory task families. Freeze policy only after measuring realistic submissions.
- Define one cohesive content submission with typed references and mechanics where consumed; prose
  remains prose. Resolve IDs, supported numeric policy, terrain, and guide assembly in code.
- Keep intermediates in a durable attempt; publish a complete draft atomically. A failure leaves prior
  artifacts intact and recoverable map/checkpoint state, clearly marked incomplete and unapprovable.
- Introduce the replacement behind shared application services, test it, switch the ordinary path,
  then delete obsolete alpha authoring/coordinator/eval paths and path-only fixtures/tests. Keep
  invariant tests. A short-lived transition is not permission to maintain parallel V2 implementations.
- Resume only validated checkpoints with matching pins; require explicit restart on incompatible
  inputs. Keep body-free diagnostics and cumulative limits without wrapper-per-feature bureaucracy.

**Demo/gate:** one CLI/API service produces coherent complete drafts; failures/cancellation/restart
cannot publish partial current versions. Actual authored completeness is separate from schema success.

### P7-16b — Welcome to the Workbench

**Depends on:** phase 1 gate; may be developed independently of P7-16a within this phase.

- Record the focused browser-auth design before implementing it: single-owner first-run enrollment,
  maintained password-hashing/session components, safe recovery, throttling, expiry/revocation, CSRF,
  and private/local versus remote deployment behavior. Routine login must not require the API token.
- Retain bearer auth for automation and private gateway auth; do not add unauthenticated convenience
  routes, credentials in URLs, browser token storage, or a new identity service.
- Establish a small visual system: typography, spacing, colors/contrast, components, responsive shell,
  navigation, empty/loading/error states, keyboard focus, and accessible forms.
- Show the actual feature state; unfinished Ask or faux model surfaces must not impersonate working
  campaign assistance. Provider setup belongs in Settings, not in the center of each adventure.

**Demo/gate:** Reese can enroll/sign in/sign out and find Dungeon Studio without copying an API token;
provider-free browser tests cover the journey and auth failures. Retention policy is explicit before
any intentionally retained real-user enrollment or artifact, not retroactively after it.

### P7-16c — Read, Edit, and Export

**Depends on:** P7-16a/b.

- Present a primary map, room list, inline guide, and inspector in one workspace; establish selection
  by stable IDs with consistent human-readable keys. Start with room selection; finer hit targets
  follow supported map features in P7-17.
- Provide explicit save/cancel for room prose and basic title/summary edits using typed patch services,
  expected base versions, and validation. Human-origin text is tracked and preserved by later AI edits.
- Save user-meaningful immutable draft versions; restore creates a child rather than rewriting history.
  Incomplete manual work may save as a draft with readiness blockers, never as approved preparation;
  integrity/security checks still apply. Show unsaved changes, validation blockers, provenance, and
  before/after differences in readable form.
- Group outputs by purpose/audience with meaningful filenames. JSON/manifests, hashes, storage roles,
  and opaque IDs are advanced inspection only. Put progress/cancel/retry actions next to the draft.
- Use explicit preparation approval against the exact reviewed version; no model-generated approval
  report or rubric form is a compulsory substitute for DM judgment.

**Demo/gate:** prompt → progress → readable draft → manual room edit → save → DM/player export works
through the browser, without JSON or a file-directory scavenger hunt. Test stale tabs, failed saves,
secrecy, keyboard navigation, and narrow/wide layouts; Reese reviews the rendered workspace.

## Phase 3 — Maps Worth Exploring

**References:** architecture §13 rendering/layout, §15, §17.

### P7-17a — Compact Places, Meaningful Terrain

**Depends on:** P7-16.

- Measure map footprint/occupied coverage, detours, readability, and guide/geometry mismatches across
  different briefs. Improve spacing and routing within supported construction first.
- Render a small code-owned vocabulary such as pools, crossings, barriers, cover, and fixtures with
  validated dimensions/clearance. Adventure content cannot silently require absent geometry.
- If compactness cannot be achieved economically, document evidence and replace only the layout
  implementation behind `dm_dungeon` with bounded templates/assembly. Update the proof boundary and
  properties before relying on it; do not retain competing generators without a measured need.
- Separate static geometry from described play states. Flooding, opened gates, alarms, or broken
  crossings may have concrete procedures without requiring a live simulator or a canonical write.

**Demo/gate:** the DM can explain spatial choices by pointing at the map, not drawing missing features;
loops/routes are usable and rooms form plausible compact places. Geometry/secrecy regressions pass.

### P7-17b — A Map You Want to Use

**Depends on:** P7-17a; visual prototypes can accompany that task.

- Add restrained wall/floor/terrain styling, grid control, legible symbols/labels, palette and low-ink
  treatment; protect geometry, scale, hit targets, and grayscale legibility.
- Provide zoom/pan, synchronized map/guide selection, and useful room/feature hit targets. No arbitrary
  drag-to-edit geometry is required. UI overlays are DM-only and absent from exported player bytes.
- Review actual rendered SVG/PNG and browser screenshots, not only manifests or DOM snapshots.
- Preserve purpose-based exports and safe headers. Do not introduce image-generation dependencies or
  let decorative textures determine tactical geometry.

**Demo/gate:** attractive, readable maps in the workspace and downloaded assets, with consistent
room keys and unambiguous DM/player modes. Human visual review is required.

## Phase 4 — Revise with Your Assistant

**References:** architecture §§8, 9, 12, 13 targeted revision, 15, 17.

### P7-18a — Ask About This

**Depends on:** P7-17 and the manual edit/version boundary in P7-16c.

- Add a component-scoped conversation panel for dungeon, room, puzzle, and supported obstacles.
  Display selected artifact version, target, readable context summary, and read-only Ask mode.
- Build context server-side from authorized content. The whole small adventure may be visible while
  the selection stays local. Source claims, inference, suggestions, and authored facts stay labelled.
- Persist useful user conversations privately under artifact ownership, separate from operational
  logs and provider-debug transcripts. Declare retention/access/deletion behavior before implementation.
- Handle version changes visibly; do not silently reinterpret an old conversation against new content.

**Demo/gate:** select a puzzle and ask for its solution or alternatives; select the dungeon and ask
about pacing. Answers cannot modify artifacts, approve preparation, or commit canon.

### P7-18b — Propose, Compare, Accept

**Depends on:** P7-18a.

- Add explicit Propose Change mode with server-owned write scope, exact base version/hash, typed
  patches, dependency impact, and a readable preview. Reuse manual edit services.
- Protect manual edits and unrelated rooms by default. Cross-room clues, geometry changes, and wider
  context require an explicit scope-expansion request and human authorization before generating the
  expanded patch; neither chat nor a model tool broadens authority silently.
- Accept/edit/reject proposals; human acceptance creates one validated draft child atomically, not
  approval for play. Stale proposals conflict rather than overwrite; retries are idempotent.
- Structural changes explicitly rebuild/revalidate affected map/content; a prose edit must not reroll
  geometry. Provide restore/undo as new versions and preserve conversation/proposal provenance.

**Demo/gate:** change one puzzle without losing edited room text; reject a suggestion; handle two
stale tabs; accept a cross-room change only after seeing its scope. Player exports remain clean.

## Phase 5 — Bring Your Campaign

**References:** architecture §§7, 9, 11–13, 15, 17.

### P7-19a — Attach Facts and Hooks

**Depends on:** P7-18. Full P3/P5 knowledge modeling is not required for selected source grounding.

- Add bounded DM-selected inputs for established facts, attributed claims, explicit unknowns, required
  placements/outcomes in preparation, and creative permissions, with immutable source/DM annotation
  references and visible authority labels. Keep standalone as an explicit no-lore mode.
- Reuse the same generator, editor, and conversation context builders. A rumor about a relic is not a
  requirement that it exists here; a captive placement instruction does not record a rescue or death.
- Require explicit permission to resolve an unknown creatively; mark the result preparation-only.
  Conflicting established inputs/requirements are surfaced before generation, not silently reconciled.

**Demo/gate:** generate and revise synthetic captive and rumored-relic adventures; show exactly what
was supplied versus invented. No campaign revision changes.

### P7-19b — Find Relevant Campaign Context

**Depends on:** P7-19a and the necessary P1 ingestion/snapshot/search capabilities.

- Retrieve only authorized, relevant evidence, labelled by source/authority/revision. Let the DM
  inspect/select it before generation. Implement only missing P1/P4 context services needed here.
- Keep bounded context and stable source references; wrong-campaign, secret, stale, disputed, or
  unsupported evidence cannot silently become constraints. Later canonical queries can enrich this
  adapter without replacing standalone authoring.

**Demo/gate:** find a villain/captive/item hook from synthetic notes and use it in the same Studio;
excluded sources never leak through context, counts, citations, answers, or exports.

## Phase 6 — Remember What Happened

These established task IDs remain backlog identities, not prerequisites for a standalone one-shot.
Activate a small named task in `PROJECT_STATUS.md` and refine its slice before implementation; do not
build the whole campaign ontology in one pass. Architecture §§7–11, 14, 16–18 govern these features.

| Task IDs | Human-readable outcome | Acceptance |
| --- | --- | --- |
| P1-03–06 | A Searchable Library | Exact source spans, atomic snapshots, filtered lexical search, shared ingest/search services. Audit existing implementation before adding missing pieces. |
| P3-01–05 | Review and Commit Campaign Changes | Typed operation registry and grouped review; one atomic revision, stale-base protection, readable history and old-revision queries. |
| P3-06 | Export Readable Campaign History | Optional rebuildable Markdown/JSONL; never a second authority or prerequisite for commit. |
| P4-01, P4-04–05 | Trusted Rules and Context | Selected authorized rules/creatures, precedence and narrow context; reuse existing profiles/runners, do not recreate them. |
| P4-06–07 | Ask Your Campaign | Real sourced browser answers, uncertainty, cancellation/reconnect and history; replace faux surfaces, no mandatory model-comparison UI. |
| P5-02–08 | Follow People, Secrets, and Threads | Grow predicates/events/time/perspectives from actual queries; distinguish reality, belief, claim, unknown and prepared plans; preserve retcon/history reads. |
| P6-01–05 | Bring Character Sheets and Items | Source-linked profiles/adapters and reviewed diffs; separate reported and computed mechanics, no live resource tracker. |
| P8-01–09 | Broader Party-Aware Encounters | Expand the MVP's bounded policy to authorized profiles, deterministic difficulty/map fit, varied combat/noncombat, scaling and review; reuse dungeon content rather than a second population pipeline. |
| P9-01–07 | Close a Session | Source-linked proposals for actual events/state/threads; grouped human edits and atomic P3 commit; prepared outcomes never auto-populate canon. |

## Release and Later Capability Gates

Security and persistence tests accompany every phase; they are not postponed to a final audit.

- **Standalone release:** P7-15–17 human gates plus auth/leakage audit, failure/recovery tests, and
  backup/restore of retained artifacts. P7-18 is the subsequent assisted-review milestone; campaign
  memory, arbitrary topology, full P8, and exact-scale print do not block standalone release.
- **Retention gate:** architecture and status must declare it crossed before intentionally retained
  real-user artifacts/campaigns, consumers, deployments, or replay promises. Decide migration/reader/
  replay/rollback policy before incompatible changes; do not treat a useful personal deployment as
  disposable simply because it is called alpha.
- **P10-01–03, P10-05–06 — Trust Your Workbench:** scope-appropriate auth/injection/leakage audit,
  backups/restores, durable diagnostics/retry, and release acceptance. Audit only enabled workflows;
  do not require every future domain gate before releasing the one-shot product.
- **P7-20 — Print at the Table:** separately implement bounded reference maps and selected-region
  tactical tiles with exact scale, coverage/page limits, registration, calibration, and rendered
  nonblank-page checks. Keep capability disabled until human print review and tests pass.
- **Later:** multi-floor/general geometry, freeform map editing, player reveal overlays/accounts,
  direct VTT upload/dynamic lighting, regional maps/illustration, transcript/combat tracking,
  calendar/alternate timelines, local/private adapters. Each needs demonstrated use and a scoped task.

## Test, Migration, and Handoff Discipline

- Unit/property, PostgreSQL integration, shared API/CLI/web contracts, rendered-output and browser
  interaction checks, human walkthroughs, adversarial leakage, and restore tests have distinct roles.
- Use synthetic fixtures only. Accepted local creative artifacts and private conversations are not
  permission to commit real campaign/rules/provider material or secrets.
- Keep reusable invariants while deleting tests whose only purpose was preserving superseded alpha
  orchestration. Root and package suites run separately while duplicate test basenames exist.
- Prefer Alembic migrations; never edit applied/shared migrations or invoke a model from a migration.
  Pure dungeon code must reject web/database/retrieval/provider imports.
- Do not add a service, universal context, agent framework, queue, database, or encounter package for
  symmetry. Share services between CLI, browser, and file adapters.
- Run focused checks and `git diff --check`; update the bounded status with semantic WIP state and
  one next action. Git supplies volatile status; history stores only durable outcomes.
