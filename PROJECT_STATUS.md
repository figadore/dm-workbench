# Project Status and Handoff
> This is the only live resume point. Git supplies branch, HEAD, and working-tree details.
> Completed milestones are summarized in [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md).

## Current Task
- **Task:** P7-14f — staged Tier A authoring and anti-overfitting evaluation.
- **State:** fixed-case execution/evidence and blinded packets are implemented. Provider-free repair
  diagnostics now preserve the evidence that was missing from the case-01
  `repair_budget_exhausted` stop. No subsequent live retry was authorized or run.
- **Quality state:** case 02 and case 03 have complete selected chains; the fresh case-01 chain is
  blocked at puzzle enrichment. The three-case `variant_01` blinded review tranche remains red.
- **Schema head:** `0008_workbench_defaults`; no migration is involved.
- **Retention gate:** **not crossed**. Active V1 contracts and disposable alpha data evolve in place.

## Completed Behavior
- One shared structured-submission repair planner now owns the exact estimate and reserve calculation
  used by structural generation and all six enrichment seams.
- A repair that cannot be dispatched retains the initial call's measured tokens and duration without
  retaining its body, arguments, or provider text.
- Durable reports expose workflow and remaining request budgets, estimated complete repair input,
  signed output availability, configured/effective output ceiling, rounded charged time, remaining
  time, and whether token and/or time reserve blocked dispatch.
- Structural and staged application reports use task-specific public codes while preserving the
  allowlisted `repair_budget_exhausted` abstention code; no repair is reported as attempted.
- Existing strict measured publication ceilings, one-repair limit, shared deadline, exact replay
  pins, atomic child publication, and no-approval/no-canon boundaries are unchanged.

## Contract Assessment
- The historical case-01 task report retained only `repair_budget_exhausted`, so its initial usage and
  rejected arguments cannot be reconstructed safely after the fact.
- This remains one isolated Luna puzzle failure and does not meet the repeat/provider-specificity or
  measured-quality gates for changing budgets, schema, prompt, effort, or model.
- Keep the 2,048-output/6,000-cumulative puzzle contract unchanged. A newly authorized, instrumented
  exact resume is needed before any further contract decision.

## Live Evidence
- Case 02 artifact `b6569a3e-8a75-4fd6-a2a5-bc30a9cb29e3`, final version
  `8af0c7b8-f280-45fe-8e6a-06c879962006`, passed all seven checks: 17,658 input, 5,658 output,
  117,046 ms, one repair; structural wrapper reclassified.
- Case 03 artifact `cc4a8ed0-cfb2-4d86-8411-e21192c66f25`, final version
  `3a5f5434-a8d9-4b50-b7c6-49fb9806dda2`, passed all seven checks: 16,992 input, 6,369 output,
  130,149 ms, two repairs.
- Fresh case-01 artifact `444a4cd5-e3bd-4e0b-bc48-eebc701dc44a`, current version
  `c5910a93-47ea-4a97-892a-048c7a1f7ded`; failed wrapper
  `8c9beb8e-3742-42fc-b968-8c0b0e6c7f1e`, task attempt
  `c5ae16ce-80be-4298-bbfc-91cca11f6783`. No child was published.
- No Terra comparison, approval, campaign revision, canonical write, or new live model call occurred.

## Intentional Uncommitted Work
- Shared model-submission repair planning/reporting, all structural/staged prompt and application
  adapters, focused tests, and this handoff comprise the current provider-free diagnostic tranche.

## Verification
- Root unit/eval suite: **261 passed**.
- PostgreSQL integration: puzzle **2 passed**; staged coordinator **12 passed**.
- Changed-path Ruff/format, focused strict mypy, and `git diff --check` passed. Repository-wide mypy
  currently reports 11 pre-existing Library/campaign-knowledge errors outside this task.
- The work is runnable; there is no partial migration or unsafe write path.

## Single Next Recommended Task
**Run one explicitly authorized, instrumented exact case-01 puzzle resume.**
First action: rebuild the local Workbench with these changes, then obtain explicit authorization for
one Luna `variant_01` retry using failed wrapper `8c9beb8e-3742-42fc-b968-8c0b0e6c7f1e`; inspect the
new body-free reserve report before deciding whether to retry again or alter any contract.

## References
[`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md) P7-14f;
[`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md) §§8, 12–13, 17;
[`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md) R5.
