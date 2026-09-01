# Project Status and Handoff

> Read this bounded live handoff first. Completed milestones and superseded notes are in
> [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md); implementation detail remains available in
> Git. Do not infer the next task from historical V2/V3/V4 names.

## Current State

- **Updated:** 2026-09-01
- **Branch/HEAD:** `fast-track-prompt-to-dungeon` at `e13510e`, five commits ahead of
  `origin/fast-track-prompt-to-dungeon`, with the P7-14f provider-free hardening below
  uncommitted.
- **Current task:** **P7-14f — Staged Tier A authoring and anti-overfitting evaluation.**
- **Task state:** rejected puzzle-request usage/duration is now durable and body-free, and the
  two previously indistinguishable puzzle model-validator invariants have stable diagnostics.
  The Tier A quality gate remains red pending another explicitly authorized canary and human
  evidence.
- **Schema head:** `0008_workbench_defaults`; no migration changed or is pending.
- **Retention gate:** **not crossed.** Active V1 contracts evolve in place; the canary artifact
  and disposable alpha database remain non-retained.

## Completed Provider-Free Hardening

The prior authorized `openai-codex/gpt-5.4` standard-effort canary at frozen seed `714000001`
published a valid structural draft, then stopped when the puzzle initial submission and its one
repair both failed schema validation. No later staged task ran and no retry was made.

This slice resolves the provider-free evidence gaps exposed by that result:

- `DungeonPuzzleSubmissionFailure` reduces each rejected `ModelRunRecord` to only attempt/stage,
  bounded diagnostics, duration, measured/unknown status, and input/output token totals;
- the durable puzzle attempt report now retains both initial and repair usage without prompts,
  arguments, outputs, provider bodies, reasoning, timestamps, or full model records;
- missing usage remains explicit `null`/unmeasured rather than zero;
- duplicate puzzle clue locations emit `submission.puzzle_clue_location_duplicate` at
  `/clue_path` with an actionable repair;
- an overlong assembled puzzle guide projection emits
  `submission.puzzle_guide_projection_too_long`, distinct from generic root schema failure;
- both diagnostics are allowlisted and body-free, and the first is included in the bounded
  repair request;
- model-visible prose bounds were not narrowed from one canary failure. Multi-case evidence is
  required before changing the general contract.

No provider call, canon write, approval, migration, queue, second store, or model-authored
mechanics was added.

## Active Boundaries and Known Issues

- There is still no preparation-ready staged artifact, final gate result, human rating, or valid
  live Tier A quality evidence. The prior structural draft is first-stage evidence only.
- Another live call requires renewed explicit authorization. Do not make a debug/retry call.
- Blinded human evidence and the frozen multi-case matrix remain pending.
- Tier B/C and output/print work remain deferred until Tier A is dependable.
- Three unrelated Library/schema integration failures remain: metadata constraint diffs,
  embedding client/database timestamp ordering, and a direct document-revision fixture that
  violates the source-history trigger.
- Package and root pytest suites must run separately because duplicate test basenames cause
  import-file-mismatch when collected together.

## Files and Verification

Current uncommitted production/tests:

- `src/dm_assistant/orchestration/dungeons/{contracts,puzzle_prompting}.py`
- `src/dm_assistant/orchestration/modeling/submission.py`
- `tests/unit/test_dungeon_puzzle_enrichment_contract.py`
- `tests/integration/test_dungeon_puzzle_prompt.py`

Current uncommitted documentation/handoff:

- `dm-assistant-technical-architecture.md`
- `dm-assistant-implementation-plan.md`
- `dungeon-generation-recovery-plan.md`
- `PROJECT_HISTORY.md`
- `PROJECT_STATUS.md`

Commands and results:

- `uv run --frozen pytest -q tests/unit/test_dungeon_puzzle_enrichment_contract.py
  tests/unit/test_prompted_dungeon_workflow.py` -> **17 passed**.
- `uv run --frozen pytest -q tests/unit tests/evals` -> **234 passed**.
- `uv run --frozen pytest -q packages/dungeon-engine/tests` -> **139 passed**.
- Direct focused integration invocation -> **2 skipped** without a configured database;
  `CONTAINER_ENGINE=podman ./scripts/test-integration.sh -q
  tests/integration/test_dungeon_puzzle_prompt.py` -> **2 passed** against disposable PostgreSQL.
- Focused Ruff lint and format checks -> passed.
- Strict mypy over the three changed production modules -> passed.
- Final `git diff --check` -> passed.

Suggested commit subject: `P7-14f retain body-free puzzle rejection usage`

## Single Next Recommended Task

**Review and commit this provider-free P7-14f hardening, then obtain renewed explicit
authorization for exactly one frozen Codex Tier A canary.**

**First concrete action:** inspect the uncommitted diff and commit it with the suggested P7-14f
subject. Rebuild the stack from that HEAD and confirm readiness. If and only if a new canary is
explicitly authorized, run the same `openai-codex/gpt-5.4`, standard-effort, seed-`714000001`
canary once without debug or provider-contract diagnostics, then stop on its first result.

Do not start P8, Tier B/C, print work, a migration, queue, approval, or canon writes.

## Authoritative References

- [`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md), P7-14f
- [`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md), model
  integration and “Dungeon Generation Architecture”
- [`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md), R5
- [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md) for completed-milestone history
