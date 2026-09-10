# Project Status and Handoff

> This is the only live resume point. Git supplies branch, HEAD, and working-tree details.
> Completed milestones are summarized in [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md).

## Current Task
- **Task:** P7-14f — staged Tier A authoring and anti-overfitting evaluation.
- **State:** fixed-case execution/evidence, blinded review packets, and safe abstention diagnostics
  are implemented. A post-change case-01 puzzle retry identified `repair_budget_exhausted`; no child
  was published.
- **Product state:** three live artifacts are preparation-ready drafts. The Tier A quality gate is
  still red because blinded human ratings and the remaining required case/variant matrix are absent.
- **Schema head:** `0008_workbench_defaults`; no migration is involved.
- **Retention gate:** **not crossed**. Active V1 contracts and disposable alpha data evolve in place.

## Completed Behavior
- The packaged manifest now owns each case's frozen seed, room count, standalone/synthetic-eval
  grounding, exact synthetic facts, and opaque variant assignments.
- `dm dungeon fixed-case-start` builds one structural proposal, validates manifest-specific topology
  and content witnesses, stores private replay context, and supports exact failed-run resumption.
- `dm dungeon fixed-case` still executes one exact enrichment task. All six task prompts receive the
  fixed-case context; puzzle clue anchors now include bounded adjacent rooms for distinct exact IDs.
- Successful model calls retain body-free measured tokens, latency, first-pass validity, and repairs;
  measured submission-over-limit reports retain duration and usage.
- Structural and all six staged seams now persist an allowlisted `abstention_code`; unknown values
  collapse to `model_run_abstained`, and provider/error text is never copied into durable reports.
- `dm dungeon fixed-case-evidence` accepts only an ordered contiguous structural/task wrapper chain,
  the exact current preparation-ready draft, and the final seven-check gate. It emits aggregate
  measurements plus a separately blinded fixed-rubric reviewer input.
- A historical structural false rejection may be reported as reclassified only when the immutable
  artifact passes the current structural semantics and complete final gate; run history is unchanged.
- The evidence command can atomically write a hash-bound blinded packet containing only reviewer
  input, DM guide, DM/player PNG maps, and the fixed 11-dimension worksheet. It recomputes the final
  gate and artifact hash and omits assignment, provider, lineage, specification, and run measurements.

## Live Evidence
- Case 02 artifact `b6569a3e-8a75-4fd6-a2a5-bc30a9cb29e3`, final version
  `8af0c7b8-f280-45fe-8e6a-06c879962006`, passed all seven final checks. Selected-chain evidence:
  17,658 input tokens, 5,658 output tokens, 117,046 ms, one repair; structural wrapper reclassified.
- Case 03 artifact `cc4a8ed0-cfb2-4d86-8411-e21192c66f25`, final version
  `3a5f5434-a8d9-4b50-b7c6-49fb9806dda2`, passed all seven checks. Selected-chain evidence: 16,992
  input tokens, 6,369 output tokens, 130,149 ms, two repairs.
- Fresh case-01 artifact `444a4cd5-e3bd-4e0b-bc48-eebc701dc44a`, current version
  `c5910a93-47ea-4a97-892a-048c7a1f7ded`, passed structural wrapper
  `6ceaed1b-f23d-410b-9136-a3f0ac32002c`. Two early puzzle wrappers abstained generically; retry
  wrapper `8c9beb8e-3742-42fc-b968-8c0b0e6c7f1e` and task attempt
  `c5ae16ce-80be-4298-bbfc-91cca11f6783` now persist `repair_budget_exhausted`. No child published.
- No Terra comparison, approval, campaign revision, or canonical write occurred.

## Intentional Uncommitted Work
- The review-packet CLI/writer/tests plus model-submission and dungeon application/prompting files
  comprise the provider-free packet and safe-diagnostic changes. No generated packet is tracked.

## Verification
- Root unit/eval suite: **255 passed**. Staged coordinator PostgreSQL integration remains **12 passed**
  from the preceding tranche; the rebuilt local stack is ready on the unchanged schema.
- Focused Ruff/format, strict mypy, and `git diff --check` passed. Repository-wide Ruff is blocked by
  pre-existing committed Library import/type/import-placement findings outside this task.
- The work is runnable; there is no partial migration or unsafe write path.

## Single Next Recommended Task
**Complete the three-case `variant_01` blinded review tranche.**

First action: provider-free retain the initial-call measurement and exact token/time repair-reserve
arithmetic for `repair_budget_exhausted`; then assess the contract before authorizing another retry.

## References
[`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md) P7-14f;
[`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md) dungeon/model
sections; [`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md) R5.
