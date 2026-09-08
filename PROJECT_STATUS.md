# Project Status and Handoff

> Read this bounded live handoff first. Completed milestones and superseded notes are in
> [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md); implementation detail remains available in
> Git. Do not infer the next task from historical V2/V3/V4 names.

## Current State

- **Updated:** 2026-09-02
- **Branch/HEAD:** `fast-track-prompt-to-dungeon` at `5842492`, one commit ahead of
  `origin/fast-track-prompt-to-dungeon`, with only the canary documentation below uncommitted.
- **Current task:** **P7-14f — Staged Tier A authoring and anti-overfitting evaluation.**
- **Task state:** one newly authorized frozen canary safely published a valid structural draft,
  then stopped at frozen semantic preflight because the model omitted the required exploration
  slot. No enrichment task ran. The Tier A quality gate remains red because no preparation-ready
  live artifact or human evidence exists.
- **Schema head:** `0008_workbench_defaults`; no migration changed or is pending.
- **Retention gate:** **not crossed.** Active V1 contracts evolve in place; all canary artifacts
  and the alpha database remain disposable/non-retained.

## Authorized Canary Result

Exactly one `openai-codex/gpt-5.4` run used frozen seed `714000001`, without `--debug`, provider-
contract diagnostics, or retry. No `--effort` override was supplied, so the documented CLI default
selected **fast** effort.

- The Workbench image was rebuilt, the old container was explicitly removed, and the replacement
  became healthy. Its running image ID exactly matched `localhost/dm-workbench:local` at
  `c98293d8c8d9...` before the call.
- The first structural submission succeeded without repair: 26,299 ms, 2,436 measured input tokens,
  1,342 measured output tokens, one turn, and one retained structural lineage record.
- Deterministic compilation/publication produced a valid five-room draft, valid topology and
  geometry, artifact `e74cce7d-639c-4cb2-9177-9043db9ed687`, and version
  `57693064-8c51-427e-b650-e459b85aeedc`.
- The package had zero exploration slots rather than the frozen canary's required one. Semantic
  preflight returned only `canary.structural_exploration_count_mismatch`, preserved the draft, and
  stopped before dispatching any enrichment provider call.
- Structural attempt `c1ea161c-02e2-475a-b598-625c1b70fd7b` and artifact generation run
  `00494099-786a-4732-9981-873b9bc7b883` both completed successfully. There are no staged task
  attempt IDs, chain result, or final-gate result.
- The artifact remains `draft`; no approval, canonical write, provider retry, or second live call
  occurred.

This is structural-contract evidence, not valid Tier A quality evidence.

## Active Boundaries and Known Issues

- The newest run confirms that the structural contract can publish a clean five-room topology on its
  first fast-effort submission, but explicit requested-slot adherence is still not dependable.
- Another live call requires renewed explicit authorization. Do not make a debug or retry call.
- Diagnose the omitted exploration slot provider-free before changing guidance; do not add a
  fixture-specific rule from one result.
- Blinded human evidence and the frozen multi-case matrix remain pending.
- Tier B/C and output/print work remain deferred until Tier A is dependable.
- Three unrelated Library/schema integration failures remain: metadata constraint diffs, embedding
  client/database timestamp ordering, and a direct document-revision fixture that violates the
  source-history trigger.
- Package and root pytest suites must run separately because duplicate test basenames cause
  import-file-mismatch when collected together.

## Files and Verification

Current uncommitted files are documentation/handoff only:

- `dm-assistant-implementation-plan.md`
- `dm-assistant-technical-architecture.md`
- `dungeon-generation-recovery-plan.md`
- `PROJECT_HISTORY.md`
- `PROJECT_STATUS.md`

Commands and results:

- `podman compose build workbench` -> passed; image `c98293d8c8d9...`.
- `podman compose rm -sf workbench` -> unsupported by local `podman-compose`; no container change.
  `podman compose ps -q workbench` was also unsupported. Explicit `podman rm -f` by container name
  followed by `podman compose up -d workbench` succeeded.
- Health/image verification -> healthy; running and tagged image IDs matched exactly.
- `podman exec ... dm dungeon canary --provider openai-codex --model gpt-5.4` -> exit 1 after the
  safe structural semantic-preflight stop above; **not retried**.
- Body-free run inspection confirmed structural and artifact generation runs succeeded, topology and
  geometry were valid, and no staged attempt existed.
- A read-only metadata script first used a wrong runtime import, then strict `model_validate` rather
  than the repository's JSON validation path; both failed without state mutation. The corrected
  `model_validate_json` inspection reported the usage, duration, lineage, room, and zero-slot counts
  above without printing provider bodies.
- No tests were rerun because no production or test code changed during this canary-only task.
- `git diff --check` -> passed after the handoff rewrite.

Suggested commit subject: `P7-14f record frozen fast-effort canary`

## Single Next Recommended Task

**Diagnose the omitted exploration slot provider-free; do not run another canary.**

**First concrete action:** compare the complete server-authored structural instruction and frozen
prompt with the accepted proposal retained in disposable version
`57693064-8c51-427e-b650-e459b85aeedc`, then determine whether a general contradictory/ambiguous
instruction exists. Add or change guidance only with a provider-free regression expressing a general
requested-slot invariant, not this artifact's prose.

Do not start P8, Tier B/C, print work, a migration, queue, approval, or canon writes.

## Authoritative References

- [`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md), P7-14f
- [`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md), model
  integration and “Dungeon Generation Architecture”
- [`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md), R5
- [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md) for completed-milestone history
