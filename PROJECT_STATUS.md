# Project Status and Handoff

> Read this file first. Historical milestones and superseded handoffs belong in
> [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md). Do not infer the next task from old
> V2/V3/V4 names in Git history or implementation-plan history.

## Current Snapshot

- **Last updated:** 2026-09-08
- **Branch:** `fast-track-prompt-to-dungeon`; P7-14d is at `a816d6a`, followed by the
  committed P7-14e guide/canary slice described here.
- **Current task:** **P7-14e — Prompt/guide integration and stress ladder.**
- **Task state:** **WIP; the bounded sixth guide correction is implemented and a fresh
  human-review packet is ready. The Annex now has one drawable shelf pivot/support/wire
  sequence, while the Hall has one wall-mounted button/drum/bell/ink/lockout assembly and
  a concealed threshold plate with concrete detect/disable methods. The frozen one-floor
  `tier-a-live-canary-v1` prompt/seed and a non-production Codex-only advisory output-cap
  acknowledgement are implemented with durable attempt/model lineage and tests. All
  package, unit/eval, focused integration, Ruff, strict source-mypy, packet, and diff gates
  pass. Tier B/C stress work and any actual live call remain blocked until Reese completes
  the sixth worksheet and it explicitly meets the quality gate.**
- **Schema head:** `0008_workbench_defaults`; no migration changed.
- **Retention gate:** **not crossed.** There is no retained real-user artifact, external
  consumer, non-disposable deployment, or promised replay requirement; active V1 labels
  evolve in place and disposable alpha outputs receive no compatibility readers.
- **Live providers:** a local opt-in Flooded Observatory attempt on 2026-08-29 exposed
  the direct-root/repair and token-enforcement defects. Its accepted draft was
  preparation-blocked; body content remains only in restricted disposable lineage and was
  not copied into fixtures. Provider-reported usage was 19,467 measured tokens across two
  requests against a 12,000 cumulative ceiling, and the initial/repair output reports
  exceeded their requested caps. No provider call was made in this slice. Keep live use
  paused until the sixth human review passes and provider-free Tier B/C gates pass. After
  those gates, the documented non-production `openai-codex` exception permits at most one
  stop-on-failure frozen canary with explicit acknowledgement: output-cap acceptance is
  advisory, but the requested cap, 12,000 measured cumulative publication ceiling, repair
  reservation, validation, and durable policy lineage remain enforced.

## Active Direction

P7-13 feature/polish work remains paused. The active recovery is defined by
[`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md):

```text
one submit_dungeon_plan V1 model call
    -> deterministic critical-path/branch/loop topology compiler
    -> independently checked TopologyCertificate
    -> certificate-driven constructive orthogonal layout
    -> independent geometry/secrecy validation
    -> optional independently-failable guide enrichment
    -> atomic draft publication
```

P7-14d is committed at `a816d6a`. P7-14e now proves that the accepted model-shaped
submission reaches exact guide construction, deterministic previews, and atomic draft
publication through the CLI and browser adapters. Its model-facing contract is the
proposal itself at the `submit_dungeon_plan` argument root, matching the recovery plan;
there is no `SubmitDungeonPlanInput {proposal: ...}` envelope. Live provider calls and
P7-13 output/print work remain paused.

## P7-14e Work Completed So Far

### Provider-free and faux-provider publication gates

- Expanded the shared synthetic Tier A plan to cover a branch, secret loop, reachable
  locked-gate dependency, encounter intent, complete room trap, feature, and named final
  objective.
- Reused that exact model-shaped proposal through both CLI and browser faux-gateway
  paths, exercising `submit_dungeon_plan` -> compiler/certificate -> constructive layout
  -> Workbench draft publication.
- Verified one accepted pinned tool run, a succeeded generation run, one immutable
  current draft version, exact keyed guide references, preparation readiness, and nine
  atomically published initial assets.
- Required specification, validation report, DM guide/notes, DM/player SVG, DM/player
  PNG, and both PNG manifests. DM projections contain secret door/channel IDs while
  player SVG, PNG manifest, and Roll20 manifest projections omit them.
- Corrected obsolete two-floor asset/export counts and historical hard-coded secrecy
  IDs in the provider-free workflow and CLI tests.
- Replaced an invalid certificate/topology mutation regression with a valid request whose
  caller maximum bounds are provably too small, preserving the failed-run/no-partial-
  version assertion.
- Updated regeneration expectations for the current zero-draw constructive baseline:
  changing only the seed preserves all components until optional compaction/variation
  exists.

### Fixed-prompt automated DM-guide rubric

- Added `dungeon-guide-quality-rubric-v1` provider-free checks for:
  - critical-path progression and room-purpose completeness;
  - room-role, content-mode, and purpose variety;
  - exact gate/dependency projection and pre-gate reachability;
  - preparation readiness, objective presence, keyed connection references, and complete
    traps.
- The report contains no prompt/guide body and explicitly says that human DM review is
  still required; automated checks do not claim subjective playability.
- Added positive coverage over the rich fixed faux prompt and negative coverage showing
  that missing dependency/trap details fail clue logic and prep usefulness.

### Provider-free human review packet

- Added `make dungeon-review-packet`, which requires neither PostgreSQL nor a model
  provider and atomically writes an ignored local packet without overwriting an existing
  review directory.
- Moved the exact fixed synthetic plan into one committed JSON fixture reused by the
  review command and CLI/web/provider-free gates.
- The packet includes DM/player SVG and PNG, both PNG manifests, exact guide,
  specification, plan, body-free automated rubric, hash manifest, and a blank review
  worksheet. The worksheet explicitly records quality evidence only and cannot approve
  preparation or write canon.
- Generated the current local packet at `generated/dungeon-guide-review/`; the directory
  is ignored and is not part of the working tree.

### Review-map legibility blocker fixed

- Replaced corridor-only SVG path commands with exact rectangle-fill and line-boundary
  primitives consumed identically by browser SVG, Pillow PNG, and ReportLab drawing.
  Corridor floors remain low-ink white, but their parallel black boundaries now remain
  visible between both room openings in the review PNG.
- Expanded annotation collision accounting from token text alone to complete rendered
  callout shapes plus separately placed `S`/`L`/`T` badge boxes. Encounter symbols are
  reserved before callout placement, and duplicate room-mechanic underlays are omitted
  in callout mode.
- Added a compact collision-aware DM-map key for room, start, door, lock/secret, trap,
  feature, objective, and encounter symbols. It is omitted from the player projection.
- Follow-up screenshot review found that the legend's double-ring objective did not match
  the map's single-ring `O1`, and that generated entrance/exit `PositionAnchor` circles
  looked like unlabeled room callouts with no table-facing use. Objective callouts now
  use the promised double ring. The single entrance anchor is projected as a distinct
  start flag; generated exit/objective endpoints remain exact package inputs for
  pathfinding/spatial validation and optional explicitly requested VTT metadata, not
  generic circles on ordinary maps.
- A second SVG/PNG screenshot comparison found two remaining trusted-adapter defects:
  Pillow interpreted SVG baseline coordinates as vertical centers, sinking `F1`/other
  text, and both Pillow and ReportLab ignored the white `passage-opening` class semantics,
  drawing opening cuts black and closing both corridor ends. Raster text now uses the SVG
  baseline anchor, and PNG/PDF adapters explicitly draw passage-opening cuts white. The
  SVG was correct in that comparison: the passage has one open end and one typed door end.
- Player-map review then found that even player-safe room/door/feature/objective keys and
  the start flag made the clean map read like a DM map. Player rendering now forces the
  no-callout/no-label projection: rooms, corridors, visible ordinary door geometry,
  stairs/terrain, and explicitly player-safe physical feature shapes remain, while room
  numbers, `D*`/`F*`/`O*` keys, objective/start/encounter markers, and lock state are
  absent. Deliberate future publication needs an explicit projection contract rather
  than reusing the DM callout mode.
- Follow-up player-map review found that ordinary door segments still blended into the
  grid. The SVG stylesheet declared a three-pixel door stroke, but the Pillow and
  ReportLab adapters consume element attributes rather than CSS and therefore rendered
  those doors at their one-pixel fallback. Door segments now carry an explicit
  six-pixel low-ink/five-pixel draft slab width consumed identically by SVG, PNG, and
  PDF; the clean player map shows unmistakable heavy bars at typed door endpoints while
  open passage endpoints remain white.
- Added fixed-packet regressions requiring a public corridor PNG crop with two dark
  parallel boundaries, a light interior, and a visibly open non-door endpoint; disjoint
  D5/`S` badge boxes; all eight table-facing DM legend entries; a DM start flag; a
  two-ring `O1`; no generic position-anchor glyph; baseline-correct raster text; and a
  geometry-only player SVG/PNG whose unlabelled player-safe feature remains while its
  objective and every keyed callout are absent, plus a player-safe door cross-section at
  least six dark pixels wide.
- Kept the active `svg-v1`, `png-v1`, `pdf-v1`, and `roll20-v1` labels while updating
  their disposable alpha implementations in place; Workbench publication records those
  constants rather than stale hard-coded values. There are no retained user alpha
  dungeons requiring an old renderer or compatibility dispatch.
- Regenerated `generated/dungeon-guide-review/` and inspected the DM/player PNGs. The DM
  map preserves corridor connectivity/openings, D5/`S` separation, centered feature
  text, the start flag, double-ring `O1`, encounter separation, and the table-facing
  symbol key; technical exit-anchor circles are gone. The player PNG contains only safe
  geometry and one unlabelled physical feature shape, and its ordinary door slabs are
  now visibly heavier than the background grid. This removes the render blocker but does
  not constitute human DM quality approval; the worksheet remains blank.
- Human-review feedback exposed two ambiguous DM-facing labels. DM encounter markers now
  contain `E`, the map key calls them **Encounter slot**, and the guide/web detail states
  the intent plus **not yet populated**; no encounter package is implied. Door guidance
  now says `unlock DC 13`, while secret guidance says `discovery DC 13; check method is
  DM-adjudicated`. These values remain the fixed P7 mechanics-policy moderate DCs, not
  party-aware encounter/rules adjudication. The blank prior ignored packet was preserved
  as `generated/dungeon-guide-review.before-dm-label-clarification/`, then the current
  default packet was regenerated and its DM PNG inspected: `E` is legible in the slot and
  the legend reads **Encounter slot**.
- Reese completed the current packet’s human DM review on 2026-08-27. The player-map
  secrecy check passed and clue logic passed (4/5) under the intentional optional,
  exhaustive-search secret-bonus standard. Progression (2/5), variety (2/5), and prep
  usefulness (2/5) need work: room labels and topology are present, but the guide leaves
  the Cache/key interaction, encounter, puzzle, feature, vault objective, and most
  outcomes to DM improvisation. The filled ignored worksheet is at
  `generated/dungeon-guide-review/review-worksheet.md`; it records **Revise and review
  again**, not a preparation approval or canonical action.

### Runnable guide-content revision complete; second human review recorded

- Documented the alpha retention gate in `AGENTS.md`, the implementation/recovery plans,
  and the architecture. Until that gate is explicitly crossed, active V1 labels update
  in place; synthetic fixtures, ignored review packets, disposable alpha rows, and
  canaries do not trigger bumps/readers. The gate must be declared no later than first
  retained real-user data, external use, non-disposable deployment, or promised replay.
- Added versioned Workbench-owned `DungeonGuideContentPlan` contracts without changing
  pure `DungeonPlan` or package geometry. Discriminated gate-dependency, encounter,
  puzzle, feature, and objective entries are keyed to plan-local refs; every entry
  requires a bounded situation, explicit adjudication guidance, and two to four player
  action/outcome pairs. Gate discovery and puzzle solution are explicit typed fields.
- Provider-free semantic validation checks room/gate refs, encounter intent, puzzle room
  role, feature name, and final objective. Valid entries project onto exact package/map
  IDs only after geometry succeeds. Missing/mismatched content records readiness blockers
  and cannot erase or regenerate a structurally valid map draft.
- Added the optional typed content plan to the one-call proposal wrapper while keeping
  the active Workbench proposal/profile/prompt/instruction labels at
  `1.0.0`/`prompt-1`/`instructions-1`, updated in place under the alpha retention policy.
  The pure plan/package/compiler pins remain V1. The fixed faux proposal carries the same
  runnable content through CLI and browser atomic publication.
- Exact guides now order each critical-path room with an attached branch immediately
  after its junction, name door endpoint rooms, resolve the key to exact door `D1` and
  its alternative unlock DC, and render situations/adjudication/choices in text and web.
  Encounter prose remains explicitly a runnable exploration pressure for an unpopulated
  slot, not an Encounter Studio package.
- Added a companion synthetic content fixture covering the Cache/key interaction,
  Cache exploration pressure, Sealed Hall puzzle, Indexing Dais, and vault objective.
  The fixed plan now telegraphs the Gallery’s north/east choice while preserving the
  optional exhaustive-search secret-bonus policy.
- Updated `dungeon-guide-review-packet-v1` in place; it now includes
  `guide-content.json`. The previous filled packet is preserved under
  `generated/dungeon-guide-review.before-runnable-guide-content/`. Automated progression,
  variety, clue-logic, and prep-usefulness checks all pass, but do not substitute for the
  required human review.
- The regenerated DM/player PNG bytes are exactly identical to the prior reviewed maps,
  confirming that the prose/guide revision changed neither geometry nor player secrecy.
- Reese completed the second human DM review on 2026-08-27. Player-map secrecy still
  passes, and the optional secret bypass remains acceptable as an exhaustive-search
  bonus. The review rates progression 3/5, variety 2/5, clue logic 3/5, and prep
  usefulness 2/5, with **Revise and review again**. The entrance-to-objective order is
  coherent, but presentation numbering starts at 2 and ends at 1; rooms lack sensory
  narrative/read-aloud text; the Cache shelf collapse and warning bell lack meaningful
  consequences; `Key Storage` is over-explicit and ambiguous; the indexing puzzle is not
  understandable in the current presentation; and category-separated mechanics are hard
  to use during room-by-room exploration. The completed ignored worksheet is at
  `generated/dungeon-guide-review/review-worksheet.md`.

### Room-centric guide correction and third human review completed

- Added one bounded `DungeonGuideRoomNarrative` per plan room with required read-aloud
  text and two to four sensory details. Provider-free semantic validation projects valid
  narratives onto exact package room IDs and reports missing/mismatched narratives as
  readiness blockers without invalidating geometry.
- Added deterministic entry-first `presentation_number` values independent of stable
  package IDs and map tokens. The exact text guide and browser now render one exploration-
  ordered section per room containing local passages, encounter pressure, key/clue,
  trap trigger/effect, puzzle, feature, objective, adjudication, and player outcomes.
  Category output is reduced to a supplementary map cross-reference.
- Updated the fixed guide so the former Cache is the naturally signposted **Flooded
  Cataloguing Annex**; an east-seal stamp connects its key to exact door D1 without an
  out-of-world `Key Storage` label.
- Added sensory arrival text for all five rooms. The shelf collapse now rings the warning
  bell and pins the key cabinet until players brace or lift it. The Bell Ward and wrong
  puzzle order tip archival ink over the tab labels, requiring the visible dais record,
  a copy, memory, or cleanup before another attempt. The tab labels, carved processing
  instruction, solution, success state, and failure state are presented together in the
  Sealed Hall section.
- Extended the automated prep rubric to require complete room narratives and added fixed-
  packet/contract regressions for presentation order, sensory prose, local grouping, and
  the corrected stakes/signposting.
- Preserved the filled second-review packet at
  `generated/dungeon-guide-review.before-room-centric-guide/` and generated a fresh
  ignored packet at `generated/dungeon-guide-review/`. DM/player PNG SHA-256 hashes are
  byte-identical to the prior reviewed maps, proving this correction changed guide
  presentation/content rather than geometry or secrecy.
- Updated the architecture, implementation/recovery plans, README, and prompt guidance
  in place under the pre-retention V1 policy. No schema pin was bumped, no compatibility
  reader was added, and no model provider was called.
- Reese completed the third human DM review on 2026-08-28. Progression and variety pass
  at 5/5, while clue logic (3/5) and prep usefulness (2/5) need work; the overall decision
  remains **Revise and review again**. The coherent route, mandatory-room purposes,
  optional key branch, room identities, unchanged player secrecy, and exhaustive-search
  secret bonus are acceptable. The guide must become concise, correctly formatted
  Markdown focused on actionable clues, checks, triggers, and consequences. It must
  define or replace `index`, `tab`, `holding`, and `east-seal stamp`, explain the physical
  puzzle and cross-room bell state, remove redundant map connectivity and unactionable
  sensory repetition, and stop calling the runnable environmental challenge an
  unpopulated encounter. The completed ignored worksheet is at
  `generated/dungeon-guide-review/review-worksheet.md`.

### Concise actionable guide correction ready for fourth human review

- Added failing-first review-packet/renderer regressions for real `.md` output, valid
  block boundaries, a 1,000-word ceiling, omission of ordinary map-visible passages and
  separate sensory/purpose repetition, retention of actionable door state/DCs, and
  absence of the third review's undefined archive terms and contradictory encounter
  label.
- Reworked the deterministic text renderer into concise CommonMark: each room retains one
  read-aloud block; only locks, secrets, traps, transitions, clues, scene pressure,
  puzzles, features, and objectives appear below it. Runnable entries use explicit
  Situation, Run it, and numbered Choices and consequences blocks. Ordinary doors and
  the duplicate map cross-reference are omitted.
- Reworked the browser projection to match the concise renderer. Runnable environmental
  content is now an **Exploration challenge**, while missing non-exploration content is a
  truthful preparation blocker rather than the contradictory `not yet populated` label.
- Replaced `east-seal`, `index`, `tab`, and `holding` jargon in the fixed fixture with a
  physical three-wave key/door match, three symbol buttons, and an instruction pedestal.
  The guide now defines the shared bell state exactly: the first Annex-shelf, threshold,
  or wrong-sequence trigger rings the bell and dumps the one full ink tray; later triggers
  ring it with the tray empty, and cleaning reveals the symbols again.
- Tightened in-place prompt guidance to require ordinary concrete terms, exact cross-room
  state, concise actionable clues/triggers/consequences, and no map-connectivity
  repetition. Updated the architecture, implementation/recovery plans, and README under
  the pre-retention V1 policy; no label, migration, compatibility reader, or provider call
  was added.
- Preserved the filled third-review packet at
  `generated/dungeon-guide-review.before-concise-guide/` and generated a fresh ignored
  packet at `generated/dungeon-guide-review/`. Its CommonMark parses successfully, the
  guide is 751 words, the worksheet is blank, and automated rubric/readiness checks pass.
  DM/player PNG hashes are byte-identical to the third-review packet, so the correction
  did not alter reviewed map geometry or player secrecy.

### Physical-causality correction and fifth human review

- Replaced the Annex's immediately displayed key with a closed wave-marked cabinet hidden
  behind one concrete setup: a waterlogged crate props up a freestanding shelf's broken
  foot; the shelf blocks the cabinet; and a brass pull-wire joins its rear brace to the
  Sealed Hall bell. Bracing, crate removal, shelf pivot, failure, two-person/lever
  recovery, and key discovery/use now form one causal sequence.
- Renamed the opaque **Three-Button Filing Lock** to **Three-Button Vault Lock** and made
  its operation exact: buttons remain down, the third press evaluates the sequence, the
  correct order opens the vault, and a wrong order resets the buttons and rings the bell.
  The Entry diagram and F1 inscription now explain the physical doorway-shelves-chest
  order in plain language.
- Defined all three visible bell pull-wires (Annex shelf, threshold T1, and button lock),
  first-ring ink state, every-ring ten-minute lockout, cleanup/retry procedure, and later
  empty-cup state. The guide explicitly says no guard or creature responds; ink and
  lockout are the complete consequences.
- Removed hidden latch operation from Vault read-aloud. Only DM adjudication states that
  solving the Hall lock released the cradle's hidden catch.
- Tightened provider guidance and architecture/plan documentation so read-aloud is
  observable, each interaction has one setup/trigger/effect/recovery/repeated-failure
  sequence, cross-room alarms identify responders or their absence, and entries do not
  duplicate one interaction.
- Added failing-first renderer/prompt/browser regressions for the physical sequence,
  timed repeated-failure result, no-responder state, observable Annex/Vault read-aloud,
  and an 850-word maximum. The generated guide is 752 words.
- Preserved the filled fourth-review packet at
  `generated/dungeon-guide-review.before-physical-causality/` and regenerated the ignored
  default packet with a blank fifth-review worksheet. DM/player PNG hashes remain
  byte-identical to the fourth-review maps.
- No schema label, migration, compatibility reader, provider call, geometry, renderer,
  approval operation, or canon operation changed.
- Reese completed the fifth human review on 2026-09-08. Progression and variety pass at
  4/5: the hidden key correction, route, distinct play modes, player secrecy, optional
  exhaustive-search secret, and objective remain acceptable. Clue logic and prep
  usefulness remain 2/5, so the overall decision is **Revise and review again**.
- The current prose names causal parts but still makes the DM invent their spatial
  arrangement: shelf lean/support/pivot and wire motion in the Annex; button panel, bell
  hammer, ink cup, timed lockout, and vault-door linkage in the Hall. Read-aloud plus F1
  also reveals three wires and their sources while T1 still lists DC 13 detection, with no
  separately described concealed trigger.
- The filled ignored worksheet is at
  `generated/dungeon-guide-review/review-worksheet.md`. The next bounded correction must
  make both mechanisms diagrammable and separate visible telegraphing from the concealed
  trigger/disable operation; it must not redesign accepted topology, variety, maps, or
  objective.

### Diagrammable-mechanism correction ready for sixth human review

- Preserved the completed fifth packet at
  `generated/dungeon-guide-review.before-diagrammable-mechanisms/` and generated a fresh
  ignored packet with a blank sixth worksheet. DM/player PNG hashes are byte-identical to
  the fifth packet, so accepted geometry and player secrecy did not change.
- Replaced the abstract freestanding-shelf prose with one fixed arrangement: the shelf's
  rear-right upright turns on a floor pivot, a crate supports its broken front-left foot,
  and a removable wire clips to its upper-left corner. The safe sequence is support,
  unclip, remove crate, and rotate 90 degrees; the failure drops the shelf over the
  cabinet, rings the bell, and has an exact two-person/lever reset.
- Consolidated the Hall into one visible wall panel immediately left of the vault door.
  Three buttons advance a three-step drum; one two-armed hammer rings the bell and flips
  the ink cup; one clockwork bolt creates the ten-minute lockout; covered conduits conceal
  the three wire origins.
- Extended disposable alpha V1 trap intent/guide content in place with optional concrete
  detection and disable descriptions. Missing methods truthfully block readiness. T1 now
  distinguishes visible apparatus from a concealed pivoting threshold plate, names the
  DC 13 hairline-seam detection and coupling-pin disable operations, and states that F1
  automatically identifies the plate but not how to disable it. Deterministic mechanics
  policy still owns both numeric DCs.
- Tightened prompt guidance and browser/text rendering around the same distinction. The
  guide is 876 words under the revised 900-word correction ceiling; maps are unchanged.

### Frozen Tier A canary and narrow manual budget policy

- Added committed `tier-a-live-canary-v1`: one exact synthetic one-floor/five-room prompt,
  named **Lantern Ledger** objective, Tier A branch/gate/secret-loop/content demands, and
  fixed seed `714000001`. A hash regression freezes the prompt text.
- Added `dm dungeon canary --provider ... --model ...`. The command always supplies that
  exact prompt/seed, defaults to fast effort, marks the durable attempt surface with the
  canary ID, and tells the operator to stop on the first result.
- `--acknowledge-advisory-output-cap` is accepted only for this exact canary in
  non-production with `openai-codex`. It leaves `output_token_limit=4096` in the transport
  profile but skips only post-response rejection for that per-request output overage.
  The measured 12,000-token cumulative ceiling, repair reservation, one-repair bound,
  deterministic validation, secrecy, readiness, and atomic publication remain intact.
- Successful model lineage stores `canary_id` and `output_cap_enforcement`; success or
  failure attempt reports store the same bounded run policy plus requested output and
  cumulative limits. Faux integration proves a 7,747-output/11,632-total response can pass
  under acknowledgement while a 12,500-total response still fails cumulative enforcement.
- This is an explicit one-run operator-risk exception, not evidence that Codex honors the
  cap and not permission for ordinary provider rollout. No live provider was contacted.

### Direct model contract and measured-budget correction

- Reviewed the latest disposable Flooded Observatory run. The first model call supplied
  proposal fields at the tool root and contained substantial creative guide material, but
  the server expected an extra `proposal` envelope. Eight generic extra-field diagnostics
  told repair to remove valid content; the replacement was structurally accepted without
  guide content and published a truthfully preparation-blocked draft.
- Removed the redundant Workbench-only `SubmitDungeonPlanInput` wrapper. The sole
  `submit_dungeon_plan` JSON Schema now exposes `proposal_version`, `plan`, optional
  `guide_content`, and the other bounded proposal fields directly. Prompt guidance says
  not to add an envelope; lineage validates the accepted direct proposal.
- Added a characterization regression for malformed guide grouping. Its repair sees
  `/guide_content/room_narratives`, retains the complete prior root proposal, and receives
  no false `/proposal` or remove-valid-root diagnostics.
- Before repair, Workbench now estimates input from the complete canonical repair message
  and tool schema, reserves that estimate from measured remaining tokens, lowers the
  repair output cap accordingly, and does not start a request that has no estimated output
  room.
- `StructuredSubmissionRunner` now checks measured provider usage before schema
  validation/tool handling. Output above the pinned request cap or input-plus-output above
  the request's remaining cumulative budget raises a typed failure, cannot publish, and
  persists only limit kind and safe token counts under
  `dungeon_prompt_token_budget_exhausted`.
- Inspection of pinned `@earendil-works/pi-ai` 0.84.1 found that its OpenAI Codex Responses
  request builder does not serialize `maxTokens` to `max_output_tokens`; 0.84.4 has the
  same omission. No dependency patch or speculative upgrade was added. Post-response
  rejection restores publication correctness but cannot recover consumed provider usage,
  so Codex remains blocked from another live canary pending a transport fix or explicit
  remeasurement/policy decision.
- The 12,000 cumulative ceiling remains unchanged. It originated as an initial P7-13d.1
  guardrail and must not be raised to mask the avoidable wrapper/repair failure; remeasure
  the corrected current contract on frozen cases first.

### Durable prompt-failure diagnostics

- Preserved both the initial and one permitted repair rejection as bounded
  server-authored diagnostics on `DungeonProposalRejectedAfterRepair`, with the exact
  safe terminal stage (`model_submission`, `intent_compile`, or
  `deterministic_preflight`).
- Prompt-attempt completion now writes those diagnostics into the existing
  `generation_run.validation_report`; no migration or second log store was added. A
  failed CLI prompt prints its durable attempt UUID and exact inspector command, and
  `dm dungeon run inspect <attempt-run-id>` shows attempt order, stable codes, JSON paths,
  and deterministic repair hints after process/container restart.
- Ordinary structured logs receive only diagnostic codes, stage, public failure code,
  and exception class. Prompt text, submitted proposals, model/provider responses,
  reasoning, and the rejected model-authored value remain absent. Existing failed rows
  cannot be enriched retroactively; the behavior applies to future attempts.
- Added unit coverage for repeated compiler and schema rejection, plus an integration
  regression that performs two schema-invalid faux submissions, reads the failed run
  through the CLI inspector, and proves the invalid model-authored value was not stored.

## Files Changed

No migration changed. Current changes are in:

- `AGENTS.md`
- `Makefile`
- `README.md`
- `scripts/dungeon-guide-review-packet.py`
- `src/dm_assistant/cli/main.py`
- `src/dm_assistant/orchestration/dungeons/__init__.py`
- `src/dm_assistant/orchestration/dungeons/application.py`
- `src/dm_assistant/orchestration/dungeons/canary.py`
- `src/dm_assistant/orchestration/dungeons/contracts.py`
- `src/dm_assistant/orchestration/dungeons/evals.py`
- `src/dm_assistant/orchestration/dungeons/prompting.py`
- `src/dm_assistant/orchestration/dungeons/review.py`
- `src/dm_assistant/orchestration/dungeons/service.py`
- `src/dm_assistant/orchestration/modeling/__init__.py`
- `src/dm_assistant/orchestration/modeling/submission.py`
- `src/dm_assistant/web/templates/dungeon_detail.html`
- `tests/evals/golden/dungeon_guide_quality_content.json`
- `tests/evals/golden/dungeon_guide_quality_plan.json`
- `tests/integration/dungeon_fixtures.py`
- `tests/integration/test_dungeon_studio_cli.py`
- `tests/integration/test_dungeon_studio_web_prompt.py`
- `tests/integration/test_dungeon_studio_workflow.py`
- `tests/unit/test_dungeon_canary.py`
- `tests/unit/test_dungeon_guide_content_contract.py`
- `tests/unit/test_dungeon_review_packet.py`
- `tests/unit/test_prompted_dungeon_workflow.py`
- `packages/dungeon-engine/src/dm_dungeon/__init__.py`
- `packages/dungeon-engine/src/dm_dungeon/contracts/plan.py`
- `packages/dungeon-engine/src/dm_dungeon/export/pdf_drawing.py`
- `packages/dungeon-engine/src/dm_dungeon/export/raster.py`
- `packages/dungeon-engine/src/dm_dungeon/export/roll20.py`
- `packages/dungeon-engine/src/dm_dungeon/export/roll20_contracts.py`
- `packages/dungeon-engine/src/dm_dungeon/rendering/__init__.py`
- `packages/dungeon-engine/src/dm_dungeon/rendering/annotations.py`
- `packages/dungeon-engine/src/dm_dungeon/rendering/svg.py`
- `packages/dungeon-engine/src/dm_dungeon/rendering/themes.py`
- `packages/dungeon-engine/tests/golden/sunken_archive.upper.dm.svg`
- `packages/dungeon-engine/tests/golden/sunken_archive.upper.player.svg`
- `packages/dungeon-engine/tests/golden/sunken_archive.upper.player.grid.png`
- `packages/dungeon-engine/tests/golden/sunken_archive.upper.player.gridless.png`
- `packages/dungeon-engine/tests/test_png_export.py`
- `packages/dungeon-engine/tests/test_rendering.py`
- `packages/dungeon-engine/tests/test_roll20_export.py`
- `dm-assistant-implementation-plan.md`
- `dm-assistant-technical-architecture.md`
- `dungeon-generation-recovery-plan.md`
- `PROJECT_STATUS.md`

## Verification

- Recovered the stale local Podman connection by restarting `podman-machine-default`.
- `make test-integration PYTEST_ARGS='-q tests/integration/test_dungeon_studio_cli.py tests/integration/test_dungeon_studio_workflow.py tests/integration/test_dungeon_studio_web_prompt.py'`
  -> **5 passed** against disposable PostgreSQL.
- `uv run pytest -q packages/dungeon-engine/tests` -> **139 passed**, including
  explicit player-door thickness plus SVG/PNG/PDF/Roll20 pin and adapter coverage.
- `uv run pytest -q tests/unit tests/evals` -> **177 passed**, including the fixed-packet
  corridor/open-end parity, player-door thickness, D5 badge, DM start flag, double-ring
  objective, hidden technical exit anchor, geometry-only player projection, centered
  raster text, legend, secrecy, guide, and manifest regressions.
- `uv run pytest -q tests/unit/test_prompted_dungeon_workflow.py tests/unit/test_dungeon_review_packet.py`
  -> **9 passed**, including encounter-slot status, discovery/check-method, unlock-DC,
  and DM-only `E` marker coverage.
- `make test-integration PYTEST_ARGS='-q tests/integration/test_dungeon_studio_web_prompt.py'`
  -> **1 passed** against disposable PostgreSQL, including the rendered guide labels.
- `make dungeon-review-packet` -> passed after preserving the blank earlier ignored
  packet under its label-clarification archive name; current DM PNG was inspected.
- Focused Ruff format/lint and strict mypy over the modified dungeon guide/SVG sources
  -> passed; `git diff --check` -> passed.
- `uv run mypy --strict packages/dungeon-engine/src/dm_dungeon/rendering/{annotations,contracts,svg,themes}.py packages/dungeon-engine/src/dm_dungeon/export/{contracts,pdf_drawing,raster,roll20,roll20_contracts}.py src/dm_assistant/orchestration/dungeons/{evals,review,service}.py scripts/dungeon-guide-review-packet.py`
  -> passed.
- `make dungeon-review-packet REVIEW_OUTPUT=<temporary-path>` -> passed and produced the
  complete packet; the default packet was then regenerated successfully and its DM/player
  PNGs were inspected.
- Focused Ruff check and format check over the renderer/export/review changes -> passed.
- `uv run pytest -q tests/unit/test_dungeon_guide_content_contract.py tests/unit/test_prompted_dungeon_workflow.py tests/unit/test_dungeon_review_packet.py`
  -> **12 passed** after semantic projection/readiness coverage was added.
- Focused Ruff format/lint over the guide-content contracts, orchestration, adapters, and
  tests -> passed.
- Strict mypy over the modified dungeon contracts/service/evals/review/prompting/
  application exports, review script, and integration fixture -> passed.
- Focused CLI/workflow/web integration gate -> **5 passed** against disposable PostgreSQL,
  including in-place proposal pin `1.0.0`, exact runnable content persistence, browser rendering,
  readiness, rubric, and atomic publication.
- `make dungeon-review-packet` -> passed and produced in-place packet `v1` with 12 hashed files;
  all four automated rubric dimensions pass and human review remains required.
- SHA-256 and byte comparisons confirm both regenerated map PNGs are identical to the
  prior reviewed packet.
- `git diff --check` -> passed, including after recording the second human review; no
  tests were rerun for the ignored worksheet and handoff-only update.
- Added the room-centric correction with tests first, then ran
  `uv run pytest -q tests/unit/test_dungeon_guide_content_contract.py tests/unit/test_dungeon_review_packet.py tests/unit/test_prompted_dungeon_workflow.py`
  -> **12 passed** after correcting the expected blocked-guide narrative projection.
- `uv run pytest -q tests/unit tests/evals` -> **177 passed** with sequential
  presentation, complete room narratives, local guide grouping, and narrative-readiness
  coverage.
- Focused Ruff format/lint over the modified orchestration and test files -> passed;
  strict mypy over the modified dungeon orchestration modules -> passed.
- Focused CLI/workflow/web integration gate -> **5 passed** against disposable
  PostgreSQL after the final synthetic trap consequence and browser expectation changes.
- `make dungeon-review-packet` -> passed for the fresh third-review packet; automated
  rubric passes and the worksheet is blank. SHA-256 comparison confirms DM and player
  PNG bytes are identical to the filled second-review packet.
- Full `tests/integration` run -> **43 passed, 3 failed** outside the focused dungeon
  files:
  - `test_database_foundation.py` reports 18 SQLAlchemy/Alembic metadata diffs;
  - `test_library_retrieval.py` returns one duplicate document result;
  - `test_library_schema.py` hits the document-history trigger in its direct fixture.
  These failures were not investigated or modified under P7-14e.
- Recorded the third human review in the ignored worksheet; no code or tests changed for
  the review-only update. `git diff --check` was rerun for handoff.
- Added concise-guide tests first; the focused unit command initially failed on the old
  `.txt` packet and verbose renderer, then
  `uv run pytest -q tests/unit/test_dungeon_guide_content_contract.py tests/unit/test_dungeon_review_packet.py tests/unit/test_prompted_dungeon_workflow.py`
  -> **12 passed** after implementation.
- `uv run pytest -q tests/unit tests/evals` -> **177 passed**.
- Focused CLI/workflow/web integration gate -> **5 passed** against disposable
  PostgreSQL; the web guide asserts the concise labels and omission of contradictory and
  repetitive sections.
- Focused Ruff format/lint and strict mypy over the modified guide/review/prompting sources
  and tests -> passed.
- `make dungeon-review-packet` -> passed for the fresh fourth-review packet; CommonMark
  parsing produced 269 tokens, 20 headings, and 5 read-aloud blockquotes. Automated
  rubric and readiness pass; human review remains required.
- SHA-256 comparison confirms both regenerated map PNGs are byte-identical to the filled
  third-review packet. `git diff --check` -> passed.
- Reese completed the fourth human DM review on 2026-09-08. The unchanged DM/player maps
  remain fine, including player secrecy; the optional secret bypass, mandatory-room arc,
  and final objective remain acceptable. Variety passes (4/5), but progression (3/5),
  clue logic (2/5), and prep usefulness (2/5) require revision, so the decision remains
  **Revise and review again**. The key/door symbol match is useful, but the guide must
  make the key display, shelf/crate/cabinet interaction, cross-room bell mechanism,
  filing-lock clue/operation, repeated-error consequence, and Vault player-facing
  information physically and causally clear. The filled ignored worksheet was preserved
  at `generated/dungeon-guide-review.before-physical-causality/review-worksheet.md`.
- Added physical-causality regressions first; the focused packet test failed on the old
  filing-lock name/content and the prompt-guidance test failed before the new causal
  instructions were implemented.
- `uv run pytest -q tests/unit/test_dungeon_guide_content_contract.py tests/unit/test_dungeon_review_packet.py tests/unit/test_prompted_dungeon_workflow.py`
  -> **12 passed** after the fixture/prompt correction.
- `uv run pytest -q tests/unit tests/evals` -> **177 passed**.
- Focused Ruff lint/format and strict mypy over the changed prompt and renderer-test
  sources -> passed.
- Focused CLI/workflow/web integration gate -> **5 passed** against disposable
  PostgreSQL, including the corrected Vault-lock, shelf causality, bell lockout, and
  no-responder browser projection.
- `make dungeon-review-packet` -> passed for the fresh fifth-review packet. The guide is
  752 words and CommonMark parsing produced 269 tokens, 20 headings, and 5 blockquotes;
  automated rubric/readiness pass and the worksheet is blank.
- SHA-256 comparison confirms both regenerated map PNGs are byte-identical to the filled
  fourth-review packet. `git diff --check` -> passed.
- Added failing-first durable-diagnostics coverage; the focused unit test initially
  failed because `_failure_report` did not exist. After implementation,
  `uv run pytest -q tests/unit/test_prompted_dungeon_workflow.py` -> **8 passed**;
  `uv run pytest -q tests/unit/test_cli.py tests/unit/test_prompted_dungeon_workflow.py`
  -> **27 passed**; `uv run pytest -q tests/unit tests/evals` -> **177 passed**.
- `make test-integration PYTEST_ARGS='-q tests/integration/test_dungeon_studio_cli.py'`
  -> **2 passed**, including durable initial/repair schema diagnostics through
  `dm dungeon run inspect` and absence of the rejected model-authored value.
- Focused Ruff lint/format and strict mypy over the changed prompt/application sources
  -> passed; `git diff --check` -> passed.
- Rebuilt and recreated the local Compose stack with
  `podman compose up --build -d --force-recreate workbench`; PostgreSQL, model gateway,
  and Workbench are healthy, and the existing failed attempt row remains present.
- Direct-root and budget regressions: `uv run pytest -q
  tests/unit/test_prompted_dungeon_workflow.py` -> **11 passed**. The exact model-visible
  schema has no `proposal` property; malformed nested guide content retains the prior root
  through repair; measured output/total overages fail; and a repair with insufficient
  estimated input budget makes no second gateway request.
- `uv run pytest -q tests/unit tests/evals` -> **181 passed** after the direct-root,
  measured-budget, and public token-error correction.
- `make test-integration PYTEST_ARGS='-q tests/integration/test_dungeon_studio_cli.py
  tests/integration/test_dungeon_studio_web_prompt.py
  tests/integration/test_dungeon_studio_workflow.py'` -> **5 passed** against disposable
  PostgreSQL with direct-root CLI/browser faux tool calls.
- Focused Ruff lint/format and strict mypy over the changed modeling/dungeon sources and
  tests -> passed.
- Recorded Reese's fifth human review in the ignored worksheet and updated this handoff;
  no code, fixture, map, guide, or test changed for that review-only closeout.
- Added failing-first sixth-correction assertions; the focused packet/prompt command first
  failed on the old physical prose and absent trap methods, then
  `uv run pytest -q tests/unit/test_dungeon_review_packet.py tests/unit/test_prompted_dungeon_workflow.py`
  -> **12 passed**.
- Preserved the filled fifth packet and ran `make dungeon-review-packet` -> passed for the
  blank sixth packet. The guide is 876 words; automated rubric/readiness pass; DM/player
  PNG hashes are byte-identical to the fifth packet.
- `uv run pytest -q tests/unit/test_dungeon_canary.py tests/unit/test_cli.py
  tests/unit/test_prompted_dungeon_workflow.py tests/unit/test_dungeon_review_packet.py`
  -> **36 passed** for the frozen prompt/seed, narrow override, cumulative enforcement,
  durable policy projection, CLI command, and guide correction.
- Focused integration initially failed on a nonexistent `generation_run.created_at`
  ordering assumption and one stale trap-effect expectation. After querying the exact
  canary surface and updating the expected in-place V1 text,
  `make test-integration PYTEST_ARGS='-q tests/integration/test_dungeon_studio_cli.py
  tests/integration/test_dungeon_studio_web_prompt.py
  tests/integration/test_dungeon_studio_workflow.py'` -> **5 passed**. The faux canary
  proves 7,747 output / 11,632 total is accepted only under acknowledgement and records
  durable attempt plus accepted-model policy lineage.
- `uv run pytest -q tests/unit tests/evals` -> **185 passed**.
- `uv run pytest -q packages/dungeon-engine/tests` -> **139 passed**.
- Focused Ruff format/lint and strict mypy over the changed source modules -> passed;
  `git diff --check` -> passed.

Package and root tests must continue to run as separate pytest invocations: combining
both test roots in one process causes pytest's existing duplicate module basenames to
produce an import-file-mismatch collection error.

## Working Tree

P7-14d is committed at `a816d6a`; the P7-14e guide/canary slice is committed after it.
The generated review directories remain ignored. The filled fifth packet is preserved at
`generated/dungeon-guide-review.before-diagrammable-mechanisms/`; the current packet has
a blank sixth worksheet. No migration, real campaign content, provider response,
credential, canonical campaign write, preparation approval, or live provider call was
added. The local historical live failure remains disposable and was not copied into
fixtures. The alpha V1 trap schema evolved in place before the retention gate; missing
concrete trap methods now block readiness rather than invalidating geometry. Atomic draft
publication and lifecycle behavior remain unchanged. The committed canary and faux
integration contain synthetic content only. Quality worksheets are evidence, not
preparation approval or canon.

Commit subject:

`P7-14e add reviewed guides and bounded Tier A canary`

## Single Next Recommended Task

**Complete the sixth human DM quality review; only an explicit pass unlocks provider-free
Tier B/C stress work.**

**First concrete action:** Reese should open
`generated/dungeon-guide-review/dm-guide.md`, `dm-map.png`, and `player-map.png`, then
fill every decision/rating plus the overall decision in
`generated/dungeon-guide-review/review-worksheet.md`. Check especially whether the shelf
pivot/reset, wall panel, concealed threshold plate, F1 interaction, and DC 13 methods are
now physically understandable without DM invention. If and only if the worksheet meets
the quality gate, preserve it and implement the provider-free Tier B vertical-composition
characterization before Tier C dense supported-graph cases. Run no live provider first;
after Tier B/C and faux gates pass, use the frozen acknowledged canary for at most one
stop-on-failure non-production run.
