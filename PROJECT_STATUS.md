# Project Status and Handoff
> Only live resume point. Git supplies working-tree state; [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md)
> records durable milestones.

## Current Task
- **P7-15b — Reference-led authoring/presentation correction: planned, not implemented.**
- Reese confirmed **The Last Pay Chest** (Nell/Iona), not Bellglass/Neris, as the workable structural
  reference. Read `docs/p7-15a/last-pay-chest.md`; do not substitute an inferred preferred order.
- Updated P7-15b in the implementation plan, architecture §13, prototype README and history.
  No runtime/schema/prompt change, new call, adventure rewrite, approval/canon or phase advance.
- Seed selection remains open. No further full-adventure generation or editorial pass authorized.
- **Schema head:** `0008_workbench_defaults`. **Retention gate:** not crossed.

## Planned Behavior / Boundaries
- Follow the reference's pitch/assumptions/map access, **The job** (hook, essential DM truth, why
  the place matters and short route orientation), map-numbered local room keys, then **Settle up**.
  Use flexible information placement, not mandatory identical headings or the reference's plot,
  noncombat profile, 60–90-minute target or map geometry. Keep the supported validated-map boundary.
- Evolve ordinary room-local private prose separately from reserved mechanical features. Documents,
  clues, NPC reactions and play procedures stay where encountered; technical repairs cannot move
  them into unrelated rooms merely to satisfy typed slots. No new feature pipeline/story ontology.
- Code owns one map/guide numbering scheme and exact exit directions/destinations. Preserve required
  sensory/delivery material in rendering. Supply a readable resolved-map brief and pinned presentation
  example in model context, not just engineering JSON and general prose instructions.
- Prove note/clue placement, conditional delivery, content projection, references and player secrecy
  on small provider-free fixtures before live use. Do not make Reese reconstruct the failed draft.
- Before further diagnostic trials, define narrow private opt-in candidate/request/repair-input
  retention, including rejected creative submissions; no raw transport/reasoning, secrets or Git copies.

## Existing Evidence / Preserved Artifacts
- Sol/medium and Astra/medium produced four one-sentence seeds each from identical prompts, one call
  per model. Exact requests/answers/measurements: ignored `generated/p7-15b-seeds-medium-01/`.
  Sol: 156 input / 249 output, 9,575 ms; Astra: 156 / 150, 11,645 ms. No ranking/readiness inference.
- Failed full trial: Astra/high, two submissions (reference rejection then technical repair),
  321,752 ms gateway time, 30,069 input including cache / 8,241 output tokens; 2,987-word guide.
  Reese spent **28 minutes reviewing** and remained deeply confused. Editing/play time unknown;
  ten-minute/no-core-authoring target unmet. Do not call this minor polish or further lower the target.
- Human review: `docs/p7-15b/reviews/astra-high-reese-review.md`. Private prompt audit:
  `generated/p7-15b-astra-high-audit/prompts-and-responses.md`. First response/full repair request
  were not retained; only exact initial messages/schema, accepted response and diagnostics survive.
- Original packet untouched: `generated/p7-15b-astra-high-01/`; guide at `brass_orchard/on/dm-guide.md`.
  Guide SHA-256: `112e0cbc47dc65ee844806729ba63b748176c9129e6a913bfaf4e47c1f69f5ec`.
- Preserve `docs/p7-15a/` and `generated/p7-15a-reviewed/complete-read-34b83807/` and
  `nell-plan-8690fea9/`. The “at least 95% good” reference followed three human correction rounds;
  this is not first-pass reliability or tabletop evidence. Static reader is not the P7-16 workspace.

## Runtime / Intentional Uncommitted Work
- Existing fixture/live CLI remains runnable but not play-ready: restrictive prose slots and renderer
  defects are not fixed yet. No DB migration or partial domain write path. Gateway `pi-ai` 0.85.1
  remains deployed; SDK retries off, Codex SSE/no fallback, cached input accounted. Workbench image
  unchanged; prior disposable live script/source remain under `/tmp/p7-15b/` in its container.
- Preserve prior uncommitted prototype script/orchestration, Python gateway adapter, tests/fresh brief,
  gateway package/lock/runtime/contracts/server/tests/README, review/prototype docs, audit/history work.
- This planning session changes implementation plan, architecture, prototype README, history and this
  handoff only. All intentional; generated creative/audit/seed output stays ignored and unmodified.

## Verification
- Focused prototype/content/review-packet tests: **29 passed**; `git diff --check` passed.
- Reference section order and documentation links checked against actual Last Pay Chest text.
  Previous full baseline: root **287**, pure dungeon **139**, gateway **16** passed.

## Single Next Recommended Task
**P7-15b — Implement the small provider-free room-local content and presentation correction.**
First action: add a regression fixture with a room-local examinable note, its text and delivery cue,
plus consistent map numbering/exits; evolve the existing Workbench contract/projection until it renders
correctly using Last Pay Chest's structure. Keep exact map/mechanical/security checks, the failed
artifact and reference unchanged. Seed selection and explicit live authorization precede any new
full adventure; no extra editorial call, new framework or P7-16 implementation is implied.
