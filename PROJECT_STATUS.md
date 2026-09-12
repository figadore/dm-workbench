# Project Status and Handoff
> Only live resume point. Git supplies working-tree state; [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md)
> records durable milestones.

## Current Task
- **P7-15b — Provider-free prompt-first whole-adventure prototype: complete and runnable.**
  Stopped at the authorized fixture boundary; the live/human authoring-quality gate is not crossed.
- **Schema head:** `0008_workbench_defaults`. **Retention gate:** not crossed.

## Completed Behavior
- `scripts/dungeon-whole-adventure-prototype.py` runs three adapted synthetic briefs against one
  supported validated five-room map, with consistency instruction on/off and otherwise matched inputs.
- Reuses the shared structured-submission runner, cumulative token/time repair reservation, existing
  guide contracts/reference checks/projection and pure map compiler/validators/renderers. Adds an
  experiment-only overview payload and requires the fixed gate's play-content entry.
- Exactly one initial submission plus at most one technical repair; no outline or editorial call.
  Repair retains the initial objective/brief/map. Missing usage prevents repair; overages reject.
- Local packets include DM guide, DM/player SVG maps, exact inputs/schema/map/plan/profile pins,
  hash manifest, guide word count, all-attempt diagnostics/counters and blank human worksheets.
  Failure scenarios retain reports without accepted guides; existing output folders are not overwritten.
- CLI exposes only fixture transport. No production prompts, DB schema, approval/canon, existing
  application workflow or immutable artifact versions changed. No partial migration/write path.
- Demo: `uv run --frozen python scripts/dungeon-whole-adventure-prototype.py --output generated/my-trial`
  (destination must be new). `--scenario reference-repair` or `rejected` exercises failures.
  `generated/p7-15b-prototype/` contains the ignored repair demo. See `docs/p7-15b/README.md`.

## Evidence / Limits
- Root unit/eval suite: **283 passed**. Pure dungeon suite: **139 passed**.
- Focused Ruff check/format and mypy passed; `git diff --check` passed. CLI success, repair, final
  rejection, matched inputs, usage/budget denial, transport failure, hashes and secrecy tested.
- Fixture prose is intentionally short; identical scripted answers in both conditions prove no
  consistency benefit. Token counters are synthetic, latency is local and cost/human effort are null.
- Three settings adapt existing Tier A briefs to one five-room map; comparisons to prior packets are
  unmatched. Gallery is reserved from live tuning, not unseen by fixture tests. Fresh held-out live
  cases must be selected after prompt freeze. No live call or live budget is authorized.
- Technical acceptance is not semantic completeness, causal correctness, map/prose agreement or
  session-length evidence. No human walkthrough/review time, readiness or phase-wide acceptance claimed.
- Ten-minute/no-core-authoring target remains. Test initial consistency prompting independently;
  add a separately budgeted/authorized editorial pass only if prompt-only evidence is insufficient.

## Preserved Earlier Work
- Reese's revised Last Pay Chest is “at least 95% good”; stop broad reference polishing. Three human
  correction rounds establish a target, not first-pass reliability. No measured edit minutes/playtest.
- Preserve `docs/p7-15a/` and ignored reviewed snapshots under `generated/p7-15a-reviewed/`:
  `complete-read-34b83807/` and `nell-plan-8690fea9/`. Licensed reference map is not this prototype's map.
- Earlier candidates remain unmerged; static reader is not the P7-16 workspace. Existing alpha runnable.

## Intentional Uncommitted Work
- Preserved pre-existing packet/roadmap work: `docs/p7-15a/`, `README.md`, `PROJECT_HISTORY.md`, this
  handoff, `dm-assistant-implementation-plan.md`, and `dm-assistant-technical-architecture.md`.
- Prototype: `scripts/dungeon-whole-adventure-prototype.py`,
  `src/dm_assistant/orchestration/dungeons/whole_adventure_prototype.py`,
  `tests/unit/test_whole_adventure_prototype.py`, `tests/evals/golden/whole_adventure/`,
  `docs/p7-15b/README.md`, plus README/architecture/history/handoff additions. All intentional/runnable.
- Generated packets remain ignored; no real campaign/rules material, credentials or provider responses.

## Single Next Recommended Task
**P7-15b — Agree the bounded live/human prompt-only trial.**
First action: show Reese the fixture packet and obtain explicit model/effort, cumulative attempt/token/
cost/time and human-feedback budgets plus provider authorization before adding or running live transport.
Pin fresh development/held-out briefs and roughly 2,000-word guide budget for matched on/off conditions;
no editorial pass or P7-16 pipeline/workspace investment is implied by fixture success.
