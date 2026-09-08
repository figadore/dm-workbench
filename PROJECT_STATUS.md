# Project Status and Handoff

> Read this bounded live handoff first. Completed milestones and superseded notes are in
> [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md); implementation detail remains available in
> Git. Do not infer the next task from historical V2/V3/V4 names.

## Current State

- **Updated:** 2026-09-08
- **Branch/HEAD:** `fast-track-prompt-to-dungeon` at `28f242f`, two commits ahead of
  `origin/fast-track-prompt-to-dungeon`, with the provider-free exploration-slot clarification and
  latest canary documentation below uncommitted.
- **Current task:** **P7-14f — Staged Tier A authoring and anti-overfitting evaluation.**
- **Task state:** provider-free diagnosis and general slot-mapping guidance are implemented and green.
  One authorized standard-effort canary stopped before content with `model_unavailable`; bounded
  smoke controls now isolate that condition to exact `openai-codex/gpt-5.4` availability. The Tier A
  quality gate remains red because no preparation-ready live artifact or human evidence exists.
- **Schema head:** `0008_workbench_defaults`; no migration changed or is pending.
- **Retention gate:** **not crossed.** Active V1 contracts evolve in place; all canary artifacts
  and the alpha database remain disposable/non-retained.

## Provider-Free Diagnosis and Change

Inspection of disposable version `57693064-8c51-427e-b650-e459b85aeedc` confirmed that the latest
fast-effort structural proposal created all five requested rooms and local feature affordances but set
every `rooms[].encounter` value to null. The complete server-authored instruction said encounters
reserve later tasks, but it did not explicitly map the DM's “exploration challenge” vocabulary to the
structural encounter field.

- General guidance now maps every requested exploration challenge one-to-one to
  `rooms[].encounter = "exploration"`, requires the count and requested room/branch placement to
  match, and requires one room-local feature affordance for the later task.
- The instruction still forbids structural challenge prose; the encounter value only reserves the
  independently bounded enrichment task.
- Unit coverage asserts this general mapping. No canary-specific room name, artifact prose, schema
  change, deterministic mechanic, provider body, approval path, or canonical operation was added.

## Authorized Standard-Effort Canary Result

Exactly one `openai-codex/gpt-5.4` **standard-effort** run used frozen seed `714000001`, without
`--debug`, provider-contract diagnostics, or retry.

- The Workbench was rebuilt and explicitly recreated. It became healthy, and its running image ID
  exactly matched `localhost/dm-workbench:local` at `3732f154ce76...` before the call.
- The structural provider submission stopped before content with the allowlisted body-free category
  `model_unavailable`.
- Durable attempt `6198ea11-558c-455a-88a1-0d3474882f6b` is failed at `model_submission` with only
  `transport_error_code: model_unavailable`.
- No proposal, measured usage, artifact/version, repair, staged task attempt, chain, final gate,
  approval, canonical write, debug call, or retry exists.

Follow-up confirms this was the **OpenAI Codex subscription backend**, not the standard OpenAI
API-key adapter. The gateway remains healthy, Codex OAuth reports authenticated, and its local catalog
contains `gpt-5.4`; pinned `pi-ai` 0.84.1 and registry-latest 0.85.1 both define that model. OpenAI's
public status API reported all systems operational with no unresolved incident. One authorized
minimal standard-effort smoke call reproduced `model_unavailable` for exact
`openai-codex/gpt-5.4` after about 1.1 seconds. Because that failed, authorized controls against
`openai-codex/gpt-5.4-mini` and `openai-codex/gpt-5.5` both succeeded at standard effort with
response `OK`; measured usage was 20 input/17 output tokens and 20 input/5 output tokens,
respectively. This proves the gateway, Codex backend, OAuth credential, and standard-effort transport
are functioning and isolates the failure to exact-model upstream routing or account entitlement. The safe classifier means model-not-found/unavailable/unsupported provider text or HTTP
404; exact status/text was intentionally not retained, so transient routing cannot be distinguished
from entitlement. The first smoke CLI surfaced a generic gateway-unavailable message, but gateway
logs retained the narrower safe `model_unavailable` category. One separately authorized retry about
15 minutes later again failed for exact `gpt-5.4` with `model_unavailable` after about 0.5 seconds;
no canary or debug capture ran. One later explicitly authorized `gpt-5.5` smoke control succeeded.

This is operational availability evidence only. It does not evaluate the clarified instruction,
standard-effort structural adherence, or model quality.

## Active Boundaries and Known Issues

- Another live call requires renewed explicit authorization. Do not retry this call or run debug.
- The earlier fast-effort draft remains disposable and readiness-blocked; it is not quality evidence.
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

- `dm-assistant-implementation-plan.md`
- `dm-assistant-technical-architecture.md`
- `dungeon-generation-recovery-plan.md`
- `PROJECT_HISTORY.md`
- `PROJECT_STATUS.md`

Commands and results:

- Focused prompted-workflow/canary unit tests -> **15 passed**.
- Focused Ruff lint/format and strict mypy over the changed module -> passed.
- `uv run --frozen pytest -q tests/unit tests/evals` -> **235 passed**.
- `uv run --frozen pytest -q packages/dungeon-engine/tests` -> **139 passed**.
- `CONTAINER_ENGINE=podman ./scripts/test-integration.sh -q` over staged coordinator and Dungeon
  Studio CLI integration -> **11 passed**.
- Workbench rebuild/recreate and health/image verification -> passed; image `3732f154ce76...`.
- Authorized standard-effort canary -> `model_unavailable`, exit 1, no content/artifact; **not
  retried**.
- Body-free run inspection confirmed only the safe model-submission failure above.
- Gateway logs/catalog/auth, pinned/latest `pi-ai` model data, and OpenAI public status were inspected
  as summarized above.
- Authorized minimal smoke: exact `openai-codex/gpt-5.4` -> `model_unavailable`; because it failed,
  bounded `openai-codex/gpt-5.4-mini` control -> `OK`, 20 input/17 output tokens. One later explicitly
  authorized `gpt-5.4` smoke retry again returned `model_unavailable`. One authorized `gpt-5.5`
  smoke then returned `OK`, 20 input/5 output tokens; no canary ran.
- `git diff --check` -> passed after the `gpt-5.5` update.

Suggested commit subject: `P7-14f map exploration requests to structural slots`

## Single Next Recommended Task

**Review and commit the provider-free exploration-slot clarification; do not run another canary.**

**First concrete action:** inspect the uncommitted production/test diff, rerun `git diff --check`,
and commit it with the suggested P7-14f subject. Any later live call needs new explicit authorization
and the same rebuild/recreate/image-verification procedure. The successful mini smoke proves transport
availability; the successful `gpt-5.5` smoke makes it a viable transport candidate but is not
Dungeon Tier A quality evidence. Any next canary model choice must remain explicit.

Do not start P8, Tier B/C, print work, a migration, queue, approval, or canon writes.

## Authoritative References

- [`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md), P7-14f
- [`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md), model
  integration and “Dungeon Generation Architecture”
- [`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md), R5
- [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md) for completed-milestone history
