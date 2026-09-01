# Project Status and Handoff

> Read this bounded live handoff first. Completed milestones and superseded notes are in
> [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md); implementation detail remains available in
> Git. Do not infer the next task from historical V2/V3/V4 names.

## Current State

- **Updated:** 2026-09-01
- **Branch/HEAD:** `fast-track-prompt-to-dungeon` at `894fe26`, six commits ahead of
  `origin/fast-track-prompt-to-dungeon`, with the post-canary P7-14f hardening below
  uncommitted.
- **Current task:** **P7-14f — Staged Tier A authoring and anti-overfitting evaluation.**
- **Task state:** one newly authorized frozen canary stopped safely before enrichment after
  structural content-slot overpopulation exposed a deterministic pre-dispatch assumption. The
  provider-free classification and prompt hardening are implemented and green; the Tier A quality
  gate remains red because no preparation-ready live artifact or human evidence exists.
- **Schema head:** `0008_workbench_defaults`; no migration changed or is pending.
- **Retention gate:** **not crossed.** Active V1 contracts evolve in place; all canary artifacts
  and the alpha database remain disposable/non-retained.

## Authorized Canary Result

Exactly one `openai-codex/gpt-5.4` standard-effort run used frozen seed `714000001`, without
`--debug` or provider-contract diagnostics, and was not retried.

- The initial structural submission was rejected with body-free code
  `plan.duplicate_room_content`; its one permitted repair was accepted. Workbench atomically
  published five-room draft version `e5ee9669-1265-43c9-968a-ad588373adb0` under structural
  attempt `9324758f-d4ff-48d0-9329-d142dd272b4e`.
- Both structural requests had measured usage: 5,240 input plus 2,372 output tokens total (7,612
  cumulative), with 46,391 ms combined request duration. The accepted repair stayed under the
  frozen cumulative publication ceiling.
- The proposal reserved an exploration task in all five rooms rather than only the requested
  branch. Only two rooms had exact feature markers, so deterministic dispatch construction found
  three exploration slots without the required room-local affordance.
- No puzzle, exploration, feature, trap, objective, or narrative provider call ran. There is no
  staged task attempt, final gate result, approval, or canonical write.
- Podman Compose had built a new Workbench image but left the prior healthy container running. The
  old image converted the safe `ConflictError` to generic `dungeon_execution_failed`, so the CLI
  omitted the structural artifact IDs even though the durable structural attempt correctly reports
  success. The running stack has since been explicitly recreated and its container/tag image IDs
  verified equal.

This is useful structural-contract and deployment evidence, not valid Tier A quality evidence.

## Uncommitted Provider-Free Hardening

- Structural guidance now says every non-null `rooms[].encounter` creates a separate later task,
  requires only the requested content-slot kinds/counts, and leaves unrelated encounters null.
- The frozen canary preflights exact room/branch/secret-loop/gate and required
  puzzle/exploration/feature/trap/objective semantics before any enrichment dispatch.
- Exactly one exploration slot and a room-local feature affordance are required for this frozen
  canary; overpopulation returns stable body-free validation codes and preserves the draft.
- An unexpected trusted-policy construction conflict is reduced to
  `canary.dispatch_policy_invalid` instead of escaping as a generic CLI execution failure.
- CLI canary output now includes `validation_codes` alongside IDs and stop codes.
- A synthetic PostgreSQL-backed regression reproduces overpopulated exploration slots without
  storing or replaying the provider response and proves no enrichment call/version occurs.
- Compose documentation now warns that a healthy Podman container may still reference the old
  image and requires explicit recreation plus image-ID verification before a canary.

No provider retry, prompt/body fixture, canon write, approval, migration, queue, second store, or
model-authored deterministic mechanic was added.

## Active Boundaries and Known Issues

- The previous authorized canary stopped at puzzle initial/repair schema rejection; this one stopped
  earlier on frozen structural semantics. Neither is preparation-ready or human quality evidence.
- Another live call requires renewed explicit authorization. Do not make a debug or retry call.
- Blinded human evidence and the frozen multi-case matrix remain pending.
- Tier B/C and output/print work remain deferred until Tier A is dependable.
- Three unrelated Library/schema integration failures remain: metadata constraint diffs, embedding
  client/database timestamp ordering, and a direct document-revision fixture that violates the
  source-history trigger.
- Package and root pytest suites must run separately because duplicate test basenames cause
  import-file-mismatch when collected together.

## Files and Verification

Current uncommitted production/tests:

- `src/dm_assistant/cli/main.py`
- `src/dm_assistant/orchestration/dungeons/{canary_application,prompting}.py`
- `tests/unit/test_prompted_dungeon_workflow.py`
- `tests/integration/test_dungeon_{staged_enrichment_coordinator,studio_cli}.py`

Current uncommitted documentation/handoff:

- `README.md`
- `dm-assistant-{implementation-plan,technical-architecture}.md`
- `dungeon-generation-recovery-plan.md`
- `PROJECT_{HISTORY,STATUS}.md`

Commands and results:

- `podman compose up -d --build` built a new Workbench tag but did **not** recreate its old
  container; explicit remove/up was required. The final rebuilt Workbench is healthy and its
  container image ID equals `localhost/dm-workbench:local`.
- Authorized canary command -> structural draft succeeded, deterministic pre-dispatch conflict,
  exit 1, no enrichment call; **not retried**.
- Provider-free inspection of the retained draft reproduced
  `The Tier A canary exploration slot requires an exact local feature.` and confirmed the initial
  `plan.duplicate_room_content` rejection, accepted repair, and body-free measured totals above.
- Focused unit/CLI tests -> **37 passed**.
- `uv run --frozen pytest -q tests/unit tests/evals` -> **234 passed**.
- `uv run --frozen pytest -q packages/dungeon-engine/tests` -> **139 passed**.
- `CONTAINER_ENGINE=podman ./scripts/test-integration.sh -q
  tests/integration/test_dungeon_staged_enrichment_coordinator.py` -> **9 passed**;
  focused Dungeon Studio CLI integration -> **2 passed**.
- Focused Ruff lint/format and strict mypy over three changed production modules -> passed.
- Final `git diff --check` -> passed.

Suggested commit subject: `P7-14f classify frozen structural slot overpopulation`

## Single Next Recommended Task

**Review and commit the provider-free canary semantic preflight; do not run another canary.**

**First concrete action:** inspect the uncommitted diff, rerun `git diff --check`, and commit it
with the suggested P7-14f subject. Any later live run must receive new explicit authorization and
must first rebuild/recreate the Workbench and verify the running/tag image IDs match.

Do not start P8, Tier B/C, print work, a migration, queue, approval, or canon writes.

## Authoritative References

- [`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md), P7-14f
- [`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md), model
  integration and “Dungeon Generation Architecture”
- [`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md), R5
- [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md) for completed-milestone history
