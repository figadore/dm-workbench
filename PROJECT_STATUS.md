# Project Status and Handoff

> Read this bounded live handoff first. Completed milestones and superseded notes are in
> [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md); implementation detail remains available in
> Git. Do not infer the next task from historical V2/V3/V4 names.

## Current State

- **Updated:** 2026-09-01
- **Branch/HEAD:** `fast-track-prompt-to-dungeon` at `983d5dc`, equal to
  `origin/fast-track-prompt-to-dungeon`, with the post-canary P7-14f hardening below
  uncommitted.
- **Current task:** **P7-14f — Staged Tier A authoring and anti-overfitting evaluation.**
- **Task state:** one newly authorized frozen canary stopped safely after its initial and one
  repair both failed structural submission. Provider-free repair-context, content-slot guidance,
  and body-free usage-retention hardening are implemented and green. The Tier A quality gate
  remains red because no preparation-ready live artifact or human evidence exists.
- **Schema head:** `0008_workbench_defaults`; no migration changed or is pending.
- **Retention gate:** **not crossed.** Active V1 contracts evolve in place; all canary artifacts
  and the alpha database remain disposable/non-retained.

## Authorized Canary Result

Exactly one `openai-codex/gpt-5.4` standard-effort run used frozen seed `714000001`, without
`--debug` or provider-contract diagnostics, and was not retried.

- A host-side CLI invocation first failed local configuration validation before provider/model
  resolution; it made no live request. The configured Workbench container then ran the canary.
- The initial submission was schema-invalid at two `room_contents[].objective` paths. Its one
  permitted repair passed schema validation but failed deterministic compilation with
  `plan.duplicate_room_content` for `chime_hall` and
  `plan.final_objective_content_required` because `chime_hall`, `gust_walk`, and
  `seed_sanctum` all carried objective content.
- Durable attempt `4279eb06-09da-44fb-b136-797bf2418b91` reports only those body-free codes,
  paths, refs, and repair hints. The pre-hardening report did not retain the rejected requests'
  measured usage/duration; the new code fixes future structural rejection reports but cannot
  reconstruct this run's discarded totals.
- No structural artifact/version, staged task attempt, enrichment provider call, final gate,
  approval, or canonical write exists.

This is useful structural-contract evidence, not valid Tier A quality evidence.

## Uncommitted Provider-Free Hardening

- Structural guidance now permits at most one nonempty `room_contents` record per room, omits
  placeholder records, and requires non-objective values to be null or omitted rather than empty.
- The one structural repair carries the complete original server-authored instruction in addition
  to the original prompt/context, prior arguments, and bounded diagnostics.
- Rejected structural submissions now retain duration and measured input/output usage in the
  body-free attempt report, matching the existing puzzle rejection boundary.
- Unit coverage proves original-instruction retention, the new general slot guidance, and
  body-free measured usage for both schema and deterministic compile rejection paths.

No provider retry, prompt/body fixture, canon write, approval, migration, queue, second store, or
model-authored deterministic mechanic was added.

## Active Boundaries and Known Issues

- The newest canary stopped at structural initial/repair rejection; earlier authorized runs stopped
  at frozen semantic preflight and puzzle rejection. None is preparation-ready or human quality
  evidence.
- Another live call requires renewed explicit authorization. Do not make a debug or retry call.
- Blinded human evidence and the frozen multi-case matrix remain pending.
- Tier B/C and output/print work remain deferred until Tier A is dependable.
- Three unrelated Library/schema integration failures remain: metadata constraint diffs, embedding
  client/database timestamp ordering, and a direct document-revision fixture that violates the
  source-history trigger.
- Package and root pytest suites must run separately because duplicate test basenames cause
  import-file-mismatch when collected together.

## Files and Verification

Current uncommitted production/test files:

- `src/dm_assistant/orchestration/dungeons/prompting.py`
- `tests/unit/test_prompted_dungeon_workflow.py`

Current uncommitted documentation/handoff:

- `dm-assistant-{implementation-plan,technical-architecture}.md`
- `dungeon-generation-recovery-plan.md`
- `PROJECT_{HISTORY,STATUS}.md`

Commands and results:

- `uv run --frozen pytest -q tests/unit tests/evals` -> **235 passed**.
- `uv run --frozen pytest -q packages/dungeon-engine/tests` -> **139 passed**.
- `CONTAINER_ENGINE=podman ./scripts/test-integration.sh -q` over staged coordinator and
  Dungeon Studio CLI integration -> **11 passed**.
- Focused Ruff lint/format and strict mypy over the changed production module -> passed.
- Workbench image rebuilt, container explicitly removed/recreated, health became healthy, and its
  image ID matched `localhost/dm-workbench:local` (`66e0487747eb...`).
- Authorized canary command -> structural initial/repair rejection, exit 1, no artifact or
  enrichment call; **not retried**.
- Body-free run inspection confirmed the four diagnostics above.
- `git diff --check` -> passed before this handoff rewrite; rerun before commit.

Suggested commit subject: `P7-14f retain structural repair constraints and usage`

## Single Next Recommended Task

**Review and commit the provider-free structural repair hardening; do not run another canary.**

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
