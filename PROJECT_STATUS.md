# Project Status and Handoff
> Only live resume point. Git supplies working-tree state; [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md)
> records durable milestones.

## Current Task
- **P7-15b — Private opt-in diagnostic capture implemented and tested provider-free.**
- Added `--retain-creative-candidates` to the existing prototype; it does not enable live transport.
  No live call, new full-adventure authoring/editorial pass, human readiness evidence or P7-16 advance.
- **Schema head:** `0008_workbench_defaults`. **Retention gate:** not crossed.

## Completed Behavior
- Capture saves exact normalized messages, actual remaining-budget profile, allowed tools and schemas
  at the gateway-call boundary before contact, including full dispatched technical-repair context.
- Only `submit_whole_adventure` argument objects are captured before runner count/usage/schema/reference
  checks. Rejected candidates survive; unrelated tools, call IDs, commentary, opaque signatures and
  transport/debug envelopes are excluded. Environment/provider credentials are not read by capture.
- New private capture directories are 0700; atomic exclusive request/candidate files and pending files
  are 0600. Journal replacement is atomic; request/candidate overwrite and capture reuse are refused.
- Body-free journals expose opt-in, dispatch intent, capture states and dispositions. Write failure
  stops without retry/publication; time spent capturing cannot authorize dispatch after the deadline.
  Interruptions preserve unknown usage/missing candidates. Missing root manifest means incomplete packet.
- Capture stays off by default. Opted-in fixture packets, like live packets, retain incomplete output
  instead of cleaning evidence away. In-repo capture must live under ignored `generated/`; private
  directories also receive ignore-all markers. No DB, domain-write, gateway or deployment change.
- Policy/operation: `docs/p7-15b/README.md#private-diagnostic-capture-and-retention`. Opt-in acknowledges
  synthetic inputs reviewed secret-free; exact prose/profile capture is not an automatic secret scrubber.
  Live-call authorization and capture consent remain separate; neither has been obtained for a new trial.

## Runnable Output / Intentional Work
- Verified provider-free demo: `generated/p7-15b-private-capture-01/`. Each `*/on/creative-capture/` has
  consent, two exact requests, rejected/accepted candidates and a journal. Manifest hashes, 0700/0600
  permissions and ignored status checked; zero live calls. These are plumbing fixtures, not adventures.
- Intentional uncommitted files: new `src/dm_assistant/orchestration/dungeons/trial_capture.py` and capture tests;
  prototype orchestration/CLI hooks; architecture, prototype README, history and this handoff.
  All runnable; no partial migration or unsafe domain write path. Generated/private files stay ignored.

## Prior Correction / Preserved Evidence
- Room-local private prose/delivery pairs remain independent of mechanical slots. Shared map numbers,
  exact two-sided exits and explicit room links remain code-owned; sensory/local text survives projection.
  Prototype follows Reese's **The Last Pay Chest** structure: pitch/assumptions/maps, The job, numbered
  local keys, then Settle up. Read `docs/p7-15a/last-pay-chest.md`, not Bellglass/Neris, for the exemplar.
- Previous demo: `generated/p7-15b-room-local-correction-02/signal_house/on/dm-guide.md` (01 also kept).
  These short synthetic packets and static reader do not establish authoring quality or P7-16 delivery.
- Failed Astra/high: two submissions, 321,752 ms gateway time; 30,069 input including cache / 8,241
  output tokens; 2,987-word guide. Reese reviewed for **28 minutes** and remained deeply confused.
  Editing/play time unknown; ten-minute/no-core-authoring target unmet, not minor polish.
- Review: `docs/p7-15b/reviews/astra-high-reese-review.md`; audit:
  `generated/p7-15b-astra-high-audit/prompts-and-responses.md`. First candidate/full repair input missing;
  this implementation cannot recover them. Original failed packet remains unmodified.
- Original `generated/p7-15b-astra-high-01/brass_orchard/on/dm-guide.md` SHA-256 verified unchanged:
  `112e0cbc47dc65ee844806729ba63b748176c9129e6a913bfaf4e47c1f69f5ec`.
- Preserve `docs/p7-15a/`, `generated/p7-15a-reviewed/complete-read-34b83807/`, `nell-plan-8690fea9/`,
  and ignored Sol/Astra medium seed requests/results at `generated/p7-15b-seeds-medium-01/`.
  Human-corrected reference/seed comparisons do not establish first-pass reliability or readiness.

## Verification / Blockers
- Root unit/eval suite **322 passed**; pure dungeon suite **141 passed**. Changed-file Ruff, focused
  mypy and `git diff --check` pass. Capture/prototype focused suite includes no network/provider access.
- Known unrelated repository-wide Library/scope lint and Library/campaign-knowledge type defects remain
  untouched. PostgreSQL integration and human browser/visual/tabletop review were not run.
- Seed selection and explicit authorization for a new bounded live trial remain open.

## Single Next Recommended Task
**P7-15b — Agree the next bounded authoring trial; do not dispatch yet.**
First action: read the retained seed packet privately and ask Reese to choose a seed (or supply a fresh
one), then confirm brief/map, model/effort/condition, attempt/time and usage/spending limits, and separate
capture consent. Preserve the roughly 2,000-word/ten-minute-review objective. No editorial pass implied.
