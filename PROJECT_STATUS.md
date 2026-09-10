# Project Status and Handoff

> This is the only live resume point. Git supplies branch, HEAD, and working-tree details.
> Completed milestones are summarized in [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md).

## Current Task
- **Task:** P7-14f — staged Tier A authoring and anti-overfitting evaluation.
- **State:** fixed-case structural startup, one-step enrichment, and whole-artifact evidence are
  implemented. Authorized Luna-fast `variant_01` canaries completed all three frozen cases.
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
- Successful model calls retain body-free measured tokens, latency, first-pass schema/semantic state,
  and repairs. Budget rejection reports now retain measured duration as well as usage.
- `dm dungeon fixed-case-evidence` accepts only an ordered contiguous structural/task wrapper chain,
  the exact current preparation-ready draft, and the final seven-check gate. It emits aggregate
  measurements plus a separately blinded fixed-rubric reviewer input.
- A historical structural false rejection may be reported as reclassified only when the immutable
  artifact passes the current structural semantics and complete final gate; run history is unchanged.

## Live Evidence
- Case 02 artifact `b6569a3e-8a75-4fd6-a2a5-bc30a9cb29e3`, final version
  `8af0c7b8-f280-45fe-8e6a-06c879962006`, passed all seven final checks. Selected-chain evidence:
  17,658 input tokens, 5,658 output tokens, 117,046 ms, one repair; structural wrapper reclassified.
- Case 03 artifact `cc4a8ed0-cfb2-4d86-8411-e21192c66f25`, final version
  `3a5f5434-a8d9-4b50-b7c6-49fb9806dda2`, passed all seven checks. Selected-chain evidence: 16,992
  input tokens, 6,369 output tokens, 130,149 ms, two repairs.
- Case 01 artifact `35ec4e9b-cbc5-416b-9ff7-3fade7865044` remains preparation-ready, but its structural,
  puzzle, and exploration calls predate the wrapper and cannot form comparable whole-run evidence.
- Initial case-02/03 puzzle attempts repeatedly reused one clue location and then exhausted repair
  output allowance. The provider-independent adjacent-anchor contract fixed both subsequent runs.
- A separate case-02 structural attempt omitted the required exploration affordance and stopped.
  Both selected case-02/03 explorations succeeded, so the frozen exploration repeat gate remains
  **1 of 2**. No Terra comparison, approval, campaign revision, or canonical write occurred.

## Verification
- Root unit/eval suite: **244 passed**. Staged coordinator PostgreSQL integration: **12 passed**.
- Focused Ruff/format, strict mypy, wheel package-data check, and `git diff --check` passed.
- The work is runnable; there is no partial migration or unsafe write path.

## Single Next Recommended Task
**Complete the three-case `variant_01` blinded review tranche.**

First action: provider-free test and add a review-packet writer that combines each blinded reviewer
input with only the final artifact material reviewers need, excluding assignment/provider identity.
Then obtain a fresh wrapper-bound case-01 run and collect human ratings before deciding whether the
remaining opaque variants require live execution.

## References
[`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md) P7-14f;
[`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md) dungeon/model
sections; [`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md) R5.
