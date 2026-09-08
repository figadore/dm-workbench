# Project Status and Handoff

> This is the only live resume point. Git supplies branch, HEAD, and working-tree details.
> Completed milestones are summarized in [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md).

## Current Task
- **Task:** P7-14f — staged Tier A authoring and anti-overfitting evaluation.
- **Current work:** the exploration-overage protocol and puzzle budget-attempt reporting are
  implemented but uncommitted.
- **Product state:** staged orchestration and final validation remain implemented. The Tier A quality
  gate is red because no preparation-ready live artifact or completed blinded human matrix exists.
- **Schema head:** `0008_workbench_defaults`; no migration is involved.
- **Retention gate:** **not crossed**. Active V1 contracts and disposable alpha data evolve in place.

## Provider-Free Puzzle Repair Assessment
- Repair budgeting is deterministic: subtract initial measured input/output from the 6,000-token
  workflow budget, estimate the complete repair request input, then cap repair output at the lesser
  of 2,048 and the remaining amount.
- The historical case-01 report's 790-token ceiling proves that initial measured usage plus estimated
  repair input totaled 5,210 tokens. Their individual historical values cannot be recovered because
  the old durable report omitted both the initial attempt and repair-reserve arithmetic.
- Puzzle submission now wraps measured budget overages with `initial` or `repair` identity. Durable
  body-free reports retain prior rejection diagnostics/usage, final measured usage, workflow and
  request budgets, estimated repair input, and effective ceiling.
- A synthetic regression recreates the exact arithmetic: 6,000 minus 3,066 initial measured tokens
  minus 2,144 estimated repair-input tokens produces the 790-token ceiling; a 2,126-input/871-output
  repair then fails closed and publishes nothing.
- Initial overages are separately identified and cannot be reported as repairs. No 2,048/6,000
  budget, prompt, schema, effort, or publication rule changed.

## Live Evidence State
- The frozen canary remains the only qualifying exploration overage: Luna-fast produced 2,510 output
  tokens over the 2,048 ceiling while staying within 6,000; no repair or artifact publication ran.
- The repeat gate remains **1 of 2** materially distinct fixed cases. No Terra comparison or limit
  change is justified.
- Authorized fixed case 01 stopped safely at puzzle repair before exploration. Disposable artifact
  `35ec4e9b-cbc5-416b-9ff7-3fade7865044` remains at version
  `caa6952f-9460-4c99-b4b1-3b06229ec1ad`; no puzzle child, approval, or canonical write occurred.

## Intentional Uncommitted Work
- Existing exploration protocol: `src/dm_assistant/orchestration/dungeons/{__init__,evals,
  exploration_prompting}.py` and `tests/evals/test_dungeon_evals.py`.
- Puzzle assessment: `src/dm_assistant/orchestration/dungeons/{puzzle_prompting,
  puzzle_application}.py` and `tests/unit/test_dungeon_puzzle_enrichment_contract.py`.
- Policy/handoff: `dm-assistant-implementation-plan.md`, `dungeon-generation-recovery-plan.md`, and
  this file. The changes are runnable; there is no partial migration or unsafe write path.

## Verification and Known Issues
- Root unit/eval suite: **241 passed**.
- Focused puzzle contract: **7 passed**; focused Ruff check/format and strict mypy passed.
- Puzzle integration collection: **2 skipped** without configured PostgreSQL.
- `git diff --check` passed before this handoff update.
- Repository-wide Ruff and mypy remain red on unrelated existing Library/scope/campaign-knowledge
  findings; three unrelated Library/schema integration failures remain documented in history.
- Root and dungeon-package pytest suites must run separately due duplicate test basenames.
- No retry, further Luna call, debug capture, effort change, or Terra comparison is authorized.

## Single Next Recommended Task
**Obtain explicit owner authorization before collecting another fixed-case Luna observation.**

First action: review the body-free puzzle assessment and choose an exact bounded scope—either resume
case 01 from its unchanged structural parent or run another fixed case—then record explicit live-call
authorization before provider contact. Keep Luna-fast and the existing task budgets/contracts pinned.

## References
[`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md) P7-14f;
[`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md) dungeon/model
sections; [`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md) R5.
