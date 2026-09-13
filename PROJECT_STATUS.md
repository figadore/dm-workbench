# Project Status and Handoff
> Only live resume point. Git supplies working-tree state; [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md)
> records durable milestones.

## Current Task
- **P7-15b — Provider-free room-local content/presentation correction implemented and tested.**
- Follows Reese's selected **The Last Pay Chest** (Nell/Iona), not Bellglass/Neris. Reference remains
  `docs/p7-15a/last-pay-chest.md`; its plot, geometry and session target are not generation constraints.
- P7-15b authoring/readiness gate remains unmet. No live call, full-adventure rewrite, editorial pass,
  human visual/play evidence, approval/canon or P7-16 phase advance occurred.
- **Schema head:** `0008_workbench_defaults`. **Retention gate:** not crossed.

## Completed Behavior
- Active Workbench V1 room narratives carry bounded ordinary private `local_content`, independent of
  feature reservations, with paired conditional `delivery`/`revealed_text`. Mechanical target checks stay.
- A Gallery dispatch fixture retains its examinable text, trigger, sensory cues and local DM reaction;
  a scripted technical repair can remove an invalid feature target without moving that evidence.
- Shared pure map keys allocate entry-first numbers by public-route breadth-first traversal, stable-ID
  tie breaks, after audience filtering. Guide numbers match; exact opening directions/destinations and
  door state appear at both ends (including a bent secret bypass). No geometry change or guessed exits.
- Explicit `[[room:local_ref]]` links validate and resolve in code. Natural-language references, causal
  claims and model adherence still need human review; tests do not establish story correctness.
- Prototype renders one title, pitch/assumptions/map access, The job, numbered local rooms, Settle up.
  Sensory/delivery/feature text survives rendering; puzzle situation precedes solution. Existing detail
  template preserves local fields/exits and escapes prose; this is not the P7-16 review workspace.
- Inputs pin a readable resolved-map brief and short synthetic presentation example. Both consistency
  arms still differ only by the objective; repair remains technical, bounded and non-editorial.
- Private opt-in candidate/request/repair retention policy is defined in `docs/p7-15b/README.md`.
  Capture is **not implemented**; `--live` alone does not consent to it. No diagnostic trial before that
  boundary is implemented/tested or Reese explicitly revises the policy. Seed selection remains open.

## Runnable Output / Intentional Work
- Provider-free demo: `generated/p7-15b-room-local-correction-02/signal_house/on/dm-guide.md`, with shared
  maps, map brief, presentation example and hash manifest. Earlier `...correction-01/` also remains.
  These are short synthetic plumbing packets, not newly authored or play-ready full adventures.
- All uncommitted work belongs to this correction: Workbench contracts/projection/presentation helper,
  prototype orchestration/CLI, existing detail template, pure map-key allocation, focused unit/package/
  integration expectations and synthetic fixtures, architecture/prototype docs/history/this handoff.
- Runnable; no partial migration or domain write path. No DB, gateway, deployment or package-version
  change. Generated creative/audit/seed output stays ignored; existing failed/reference files untouched.

## Preserved Evidence
- Failed Astra/high trial: two submissions, 321,752 ms gateway time; 30,069 input including cache /
  8,241 output tokens; 2,987-word guide. Reese reviewed for **28 minutes** and remained deeply confused.
  Editing/play time unknown; ten-minute/no-core-authoring target unmet, not minor polish.
- Review: `docs/p7-15b/reviews/astra-high-reese-review.md`; private audit:
  `generated/p7-15b-astra-high-audit/prompts-and-responses.md`. First candidate/full repair input missing.
- Original `generated/p7-15b-astra-high-01/brass_orchard/on/dm-guide.md` SHA-256:
  `112e0cbc47dc65ee844806729ba63b748176c9129e6a913bfaf4e47c1f69f5ec`.
- Preserve `docs/p7-15a/`, `generated/p7-15a-reviewed/complete-read-34b83807/`, `nell-plan-8690fea9/`,
  and ignored Sol/Astra medium seed requests/results at `generated/p7-15b-seeds-medium-01/`.
  Human-corrected reference and seed comparisons do not establish first-pass reliability/readiness.

## Verification / Blockers
- Root unit/eval suite **301 passed**; pure dungeon suite **141 passed**. Focused mypy (Workbench changed
  modules plus pure package), changed-file Ruff checks and `git diff --check` pass.
- Full static checks fail on unrelated existing Library/scope lint and Library/campaign-knowledge type
  defects; left untouched. PostgreSQL integration suite and human browser/visual review were not run.
- No live authorization or human readiness evidence. The retained failed/reference packets remain evidence.

## Single Next Recommended Task
**P7-15b — Implement the narrow private opt-in diagnostic capture policy, provider-free first.**
First action: add fake-gateway tests proving opt-in capture preserves rejected creative arguments and
exact repair requests, journals before dispatch, excludes transport/reasoning/secrets, fails closed on
capture-write failure and is absent by default. Reuse this adapter; no new engine or live/editorial call.
