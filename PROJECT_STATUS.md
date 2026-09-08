# Project Status and Handoff

> This is the only live resume point. Git supplies branch, HEAD, and working-tree details.
> Completed milestones are summarized in [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md).

## Current Task
- **Task:** P7-14f — staged Tier A authoring and anti-overfitting evaluation.
- **Current work:** GPT-5.6 Luna is now the shared default dungeon-authoring baseline; one explicitly
  authorized Luna canary was run and stopped safely during staged enrichment.
- **Product state:** provider-free staged orchestration and final validation remain implemented. The
  Tier A quality gate is red because no preparation-ready live artifact or completed blinded human
  evidence matrix exists.
- **Schema head:** `0008_workbench_defaults`; no migration is involved.
- **Retention gate:** **not crossed**. Active V1 contracts and disposable alpha data evolve in place.

## Luna Default and Escalation Policy
- Shared policy selects `gpt-5.6-luna` first for GitHub Copilot and OpenAI Codex dungeon prompts;
  CLI, web fallback, and the transport-smoke default use the same model ID. An explicit or saved user
  selection still wins.
- Change code after a Luna failure only for a provider-independent contract, validation, or usability
  defect. Do not tune around an isolated model miss.
- A matched Terra comparison becomes eligible only when the same Luna failure mode occurs in at
  least two materially different fixed synthetic cases and another change would be model-specific,
  weaken the contract, or add fixture-shaped complexity. Match prompt, effort, and budgets; require
  measured quality improvement before promotion. Live comparisons remain explicitly authorized.

## Authorized Luna Canary
Exactly one `openai-codex/gpt-5.6-luna` fast-effort run used frozen seed `714000001`, without debug,
provider-contract diagnostics, retry, or Terra call.

- Structural authoring succeeded on the first submission and published a valid five-room draft.
- Puzzle enrichment succeeded and published one DM-only child.
- Exploration enrichment returned measured usage of 1,152 input and 2,510 output tokens, exceeding
  its 2,048-output-token publication ceiling. It failed closed with
  `dungeon_exploration_prompt_token_budget_exhausted`; no later tasks or final gate ran.
- Artifact `b1e12c05-7b79-4e9c-93b5-30edda9b25b4` remains a disposable draft at version
  `c065ce32-32cc-48fa-a090-3a3e9c1dcb8e`. No approval or canonical write occurred.

## Intentional Uncommitted Work
- Runtime/tests: `src/dm_assistant/cli/main.py`,
  `src/dm_assistant/orchestration/dungeons/model_selection.py`,
  `src/dm_assistant/orchestration/dungeons/web_prompt.py`, `tests/unit/test_cli.py`.
- Policy/handoff: `dm-assistant-implementation-plan.md`, `dungeon-generation-recovery-plan.md`, and
  this file.
- The changes are runnable; there is no partial migration or unsafe write path.

## Verification and Known Issues
- Root unit/eval suite: **236 passed**. Focused ruff format/check and mypy passed.
- Rebuilt/recreated Workbench is healthy; its running/tagged image IDs match and saved selection is Luna.
- Focused integration run: **2 passed, 1 failed**. The web-prompt test's stale
  `application-only output cap` page assertion fails identically at the unchanged repository HEAD;
  it is not caused by this task.
- Three unrelated Library/schema integration failures remain documented in project history.
- Root and dungeon-package pytest suites must run separately because duplicate test basenames cause
  import-file mismatch when collected together.
- No additional live call, retry, debug capture, or Terra comparison is authorized.

## Single Next Recommended Task
**Assess the Luna exploration overage provider-free without changing its limit from one result.**

First action: compare the exploration schema/instruction and 2,048-token profile against the three
existing fixed Tier A eval cases, then define the body-free evidence needed to recognize the same
failure across materially different cases before seeking authorization for more Luna runs or a
matched Terra comparison.

## References

[`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md) P7-14f;
[`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md) dungeon/model
sections; [`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md) R5.
