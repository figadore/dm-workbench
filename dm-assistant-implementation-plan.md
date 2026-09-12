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
Application-wide guidance (architecture §9) starts in P7-16; each later workflow consumes relevant
guidance as it is implemented, without adding feature-specific preference systems.

Model-made corrections are a core usefulness requirement, not merely late polish. After the safe
manual-edit/version boundary exists, use measured correction burden to reconsider whether a minimal
P7-18a/b slice should precede major map expansion. This is a priority decision to evaluate, not an
implicit reorder of the named phases or their dependencies; record any adopted change before coding.

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
- Collect lightweight chat feedback: first confusion, missing essentials and “would I run it?” No
  compulsory worksheet, scores, full reread or human editing assignment. Capture review/edit minutes
  and walkthrough findings when actually supplied; missing measurements remain unknown.

**Demo/gate:** Reese can review the target packet format and scope; baseline defects are explicit.
Human confirmation of this standard is required before claiming phase acceptance. A near-ready
reference reached through human-led corrections is a useful target, not a generator success rate.
Do not substitute continued reference polishing for fresh authoring evidence in P7-15b.

### P7-15b — Try Whole-Adventure Authoring

**Depends on:** P7-15a.

- Use a fixed/existing validated map and selected brief to prototype one complete content submission.
  Later production adds the outline pass; this experiment isolates authoring quality from layout.
- Invoke existing gateway/runners through a disposable CLI/file adapter, not a second production
  authoring engine. Keep exact mechanical/reference validation and bounded correction.
- **Test initial prompting independently first:** add causal and counterfactual consistency as an
  authoring objective, not an output section or an incident-specific question checklist. Behavior and
  consequences should follow from established motives, knowledge and circumstances as those change.
  Resolve inconsistencies by revising/simplifying the situation, not appending defensive explanations.
- Compare that instruction-only change within the same whole-adventure adapter against its baseline:
  hold brief, validated map, model/effort, presentation and technical-repair policy/budgets fixed.
  Neither arm adds an editorial model pass. Use fresh synthetic cases, including held-out cases after
  prompt tuning, rather than repeatedly repairing the reference adventure.
- **Only if initial prompting is insufficient:** test an additional bounded consistency review and
  revision against the prompt-only result. Budget/authorize it separately and measure its incremental
  benefit and cost. This optional editorial pass is not the later production outline/content pair,
  nor permission to remove required structural/mechanical validation or existing technical repairs.
- Any editorial revision replaces flawed prose, removes unnecessary elements and updates affected
  passages together within authorized scope. Preserve the brief, validated map and useful play detail
  at roughly the agreed guide length; no mandatory rationale appendix, silent invented justification,
  or deletion of essentials to meet a word count. Prose replacement does not overwrite immutable
  versions or protected human work. No new agent framework, universal story schema or eval service.
- Compare against existing packets where briefs/maps match; label unmatched comparisons and confounds.
  Also assess usefulness against chat-assisted authoring plus a good map, not only a blank-page task.
- Exercise provider-free fixtures first, varying guidance across the existing briefs. Any live
  generation/comparison needs explicit authorization; adding the objective to the roadmap makes no
  runtime prompt change and does not authorize a call.
- Record all attempts, failures/corrections, cumulative usage/latency, guide length, actual missing
  authoring work and human review/editing effort. Distinguish fewer causal repairs from mere added
  exposition; an AI's favorable critique is not human evidence. At least three materially different
  briefs and a human tabletop walkthrough inform the decision. Keep feedback lightweight, permit
  early stopping, and do not require a provider matrix or model-brand-specific promotion gate.

**Demo/gate:** complete independent one-shots, targeting about ten minutes' review without inventing
core play material. Look for fewer human causal repairs without verbosity or loss of useful content;
near-ready prose alone does not establish session length or tabletop usefulness. Adopt the simplest
measured authoring approach that meets the target, not an automatic extra review call. If repeated
human-led reconstruction persists, stop and revise the authoring approach or explicitly reconsider the
product promise as collaborative authoring before scaling infrastructure. Do not silently lower the
readiness target. If live authorization or human review is unavailable, stop at a runnable prototype.

**Investment boundary:** agree a bounded trial before larger pipeline/workspace investment. Initial
planning estimate: 1–2 focused engineering weeks, several hours of human feedback and a short tabletop
walkthrough, with early stopping rather than a review quota. Conditional on useful authoring evidence,
rough estimates were 6–12 additional engineering weeks for P7-16 and another 6–12 for maps/contextual
revision. These are unaudited planning ranges using the existing foundation, not deadlines or proof
that quality will converge; broader memory, encounter coverage and exact-scale print are excluded.
The suggested 15–30-minute assisted-prep allowance was an unmeasured contingency, not a replacement
for the ten-minute target. Quantify that tradeoff and obtain an explicit product decision rather than
assuming more code will solve it.

## Phase 2 — Prompt to Play

**References:** architecture §§3, 5, 8, 12, 13, 15, 17.

### P7-16a — One Cohesive Authoring Pipeline

**Depends on:** accepted P7-15 evidence.

- Evolve `DungeonPlan` in place for a whole-adventure outline with progression, clue/objective
  relationships, opposition, and bounded geometry-relevant affordances.
- Construct/validate the map with the existing pure engine; author the complete content with the whole
  small adventure and resolved map in context. Target two normal creative passes plus bounded repair,
  not six mandatory task families. Carry P7-15b's measured causal/counterfactual consistency objective
  into early outline/content prompting and any repairs as an authoring constraint, not extra guide
  prose. Prefer concise replacement over explanatory accumulation. Add an editorial model pass only
  if the prompt-first experiment justifies its incremental cost; it is not a third mandatory call.
  Freeze policy only after measuring realistic submissions.
- Define one cohesive content submission with typed references and mechanics where consumed; prose
  remains prose. Resolve IDs, supported numeric policy, terrain, and guide assembly in code.
- Carry relevant natural-language guidance through outline, content, repair and validation (§9).
  Resolve structural implications before construction; support omission/reuse/adaptation through
  existing domain services, not mandatory feature quotas or a subsystem per content type.
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

### P7-16d — Author Your Way

**Depends on:** P7-16a/b/c. **References:** architecture §§3, 9, 15, 17.

- Add scoped natural-language guidance and saved defaults; distinguish observations, desired direction
  and requirements. Show effective guidance/origins, request overrides and conflicts before dispatch.
- Reuse one resolver across task contexts; add structured controls only for actual code consumers.
  Pin applied guidance, protect existing work, and provide edit/disable/delete under §9's privacy policy.

**Demo/gate:** a new preference influences multiple content types without a new schema field. A request
can change the desired response to the same reported group tendency; a one-off override leaves saved
defaults unchanged. Test scope/pins/privacy; human review checks coherent application across content.

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

### P7-18c — Remember My Preferences

**Depends on:** P7-16d and P7-18b. **References:** architecture §§9, 15, 17.

- Suggest lasting guidance only from authorized conversations/edits, with supporting examples and
  proposed scope. Reuse P7-16d storage and separate human accept/edit/reject; Ask cannot activate it.
- Acceptance of an artifact edit is not consent to a preference. Preserve §9's origin, conflict,
  privacy and deletion boundaries; do not mine unrelated history or silently promote inferences.

**Demo/gate:** inspect, confirm and disable a suggestion; unconfirmed suggestions, stale updates and
other owners cannot change effective guidance or existing artifacts.

### P7-18d — Reuse a Proven Procedure

**Depends on:** P7-18c plus observed repeated authoring/review work. **References:** architecture §9.

- Let the assistant propose a small non-executable procedure for human review/save/selection (§9).
  Reuse guidance provenance/privacy; load relevant recipes under context budgets and pin their versions.
- Preserve task authority and protected inputs; no separate agent, recipe framework or eval service.

**Demo/gate:** reuse a reviewed procedure in another context and measure actual missing work/editing
effort. Preference suggestions and recipe capture are additive, not gates blocking P7-19.

## Phase 5 — Bring Your Campaign

**References:** architecture §§7, 9, 11–13, 15, 17.

### P7-19a — Attach Facts and Hooks

**Depends on:** P7-18b; P7-18c/d are not prerequisites. Full P3/P5 knowledge modeling is not required
for selected source grounding.

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
