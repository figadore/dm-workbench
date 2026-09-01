# Project Status and Handoff

> Read this bounded live handoff first. Completed milestones and superseded notes are in
> [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md); implementation detail remains available in
> Git. Do not infer the next task from historical V2/V3/V4 names.

## Current State

- **Updated:** 2026-09-01
- **Branch/HEAD:** `fast-track-prompt-to-dungeon` at `7eeb977`, three commits ahead of
  `origin/fast-track-prompt-to-dungeon`, plus the uncommitted provider-diagnosis repair below.
- **Current task:** **P7-14f — Staged Tier A authoring and anti-overfitting evaluation.**
- **Task state:** the frozen faux canary passes. The first authorized live Tier A canary
  stopped at its initial structural provider stream and was not retried. Its exact cause
  cannot be recovered from retained evidence, but the body-free classification gap that
  made it generic is repaired, tested provider-free, and active in the rebuilt local stack.
- **Schema head:** `0008_workbench_defaults`; no migration changed or is pending.
- **Retention gate:** **not crossed.** Active V1 contracts evolve in place; there is no
  retained real-user artifact, external consumer, non-disposable deployment, or promised
  replay requirement.

## Live Canary Evidence

The one non-debug call used `openai-codex/gpt-5.4`, standard effort, seed `714000001`, and
campaign `f9d6dcac-2376-45a8-b47a-5db3204c74a6`:

```text
structural attempt: f8652e6a-afd8-4e0c-86ce-05fba8b78e3c
public code: dungeon_prompt_failed
stage: model_submission
exception class: ModelGatewayTransportError
gateway category: provider_error
```

The stream terminated after about 1.5 seconds with one error event, zero text/thinking/tool
content, no measured usage, no artifact/version, and no final deterministic gate. Usage is
unknown, not zero. There was no retry, model switch, repair call, smoke call, or enrichment
dispatch.

## Diagnosis and Repair

The gateway catalog's `authenticated` flag proves only that `pi-ai` can resolve a stored
credential (and refresh it when needed). It does not prove current quota, model entitlement,
or endpoint/request acceptance. Existing transient text classification already recognized
known usage-limit, rate-limit, and authentication phrases. Because the failed text matched
none, the retained evidence cannot distinguish a 400/403-style contract/access rejection
from another opaque provider failure.

The code trace found a concrete observability defect: pinned `pi-ai` exposes safe numeric
HTTP response status through `onResponse`, but the gateway discarded it before `pi-ai`
reduced the failure to its final assistant error. The repair:

- combines transient provider error patterns with response status in one gateway classifier;
- emits only allowlisted categories: usage/rate limit, authentication/access, unavailable
  model/provider, rejected request contract, or generic provider error;
- never returns, logs, or persists provider text/body or arbitrary error codes;
- carries the category through Python's typed model-transport error;
- stores only `transport_error_code` in a failed prompt-attempt report and structured log;
- preserves the tested Codex `max_output_tokens` overlay unchanged.

Synthetic Codex OAuth/injected-fetch coverage now proves an HTTP 400 becomes
`provider_request_rejected` while the private response text remains absent. Separate tests
cover text classification, safe Python SSE mapping, durable failure-report projection, and
sanitization of unknown transport codes. This repair improves a future attempt but cannot
retroactively classify attempt `f8652e6a-afd8-4e0c-86ce-05fba8b78e3c`.

## Active Boundaries and Known Issues

- The live Tier A quality gate remains red; no valid live artifact or human rating exists.
- A replacement canary still requires renewed explicit authorization. Do not run it merely
  because the stack is rebuilt or the prior failure may have been transient.
- If a replacement reports `provider_request_rejected`, investigate the Codex hard-cap
  request contract provider-free before another call; do not remove strict caps ad hoc.
- Blinded human evidence and the frozen multi-case matrix remain pending.
- Three unrelated Library/schema integration failures remain: metadata constraint diffs,
  embedding client/database timestamp ordering, and a direct document-revision fixture that
  violates the source-history trigger.
- Package and root pytest suites must run separately because duplicate test basenames cause
  import-file-mismatch when collected together.
- No canon write, preparation approval, migration, queue, second store, or model-authored
  mechanics was added. Tier B/C and output/print work remain deferred.

## Files and Verification

Uncommitted production code:

- `model-gateway/src/provider-errors.ts`
- `model-gateway/src/runtime.ts`
- `model-gateway/src/server.ts`
- `src/dm_assistant/adapters/model_gateway.py`
- `src/dm_assistant/orchestration/modeling/{__init__,service}.py`
- `src/dm_assistant/orchestration/dungeons/application.py`

Uncommitted tests:

- `model-gateway/tests/gateway.test.ts`
- `tests/unit/test_model_gateway_client.py`
- `tests/unit/test_prompted_dungeon_workflow.py`

Uncommitted documentation:

- `dm-assistant-technical-architecture.md`
- `dm-assistant-implementation-plan.md`
- `dungeon-generation-recovery-plan.md`
- `PROJECT_STATUS.md`

Verification:

- `npm --prefix model-gateway run check` -> passed.
- `npm --prefix model-gateway test` -> **11 passed**.
- `uv run --frozen pytest -q tests/unit tests/evals` -> **231 passed**.
- `uv run --frozen pytest -q packages/dungeon-engine/tests` -> **139 passed**.
- Focused Ruff lint/format -> passed.
- Strict mypy over four changed production modules -> passed.
- Adding the two older changed test modules to strict mypy exposes 46 pre-existing typing
  errors in their legacy fixtures/JSON indexing; production typing is green.
- `make stack-up` -> rebuilt/recreated both code-bearing containers. The immediate smoke
  raced Workbench startup once (`empty reply`); after eight seconds `make stack-smoke` ->
  ready and every container is healthy.
- No live model/provider call was made during diagnosis or repair.
- `git diff --check` -> passed.

Suggested commit subject: `P7-14f retain body-free provider failure categories`

## Single Next Recommended Task

**Review and commit this provider-free diagnostic repair, then obtain renewed explicit user
authorization before exactly one replacement live canary.**

**First concrete action:** inspect this diff and commit it with the suggested P7-14f subject.
After commit, rebuild from that HEAD and confirm readiness. Do not run `dm model smoke` or the
canary until the user explicitly authorizes the replacement call.

If authorized, use the same `openai-codex/gpt-5.4` standard-effort frozen command once, without
`--debug`, and stop on its first result. Record its safe category, IDs, usage, final gate, and
artifact readiness. A request-contract rejection blocks further live calls pending a
provider-free transport review; a valid artifact proceeds to human review and the blinded
matrix. Do not start P8, Tier B/C, print work, a migration, queue, approval, or canon writes.

## Authoritative References

- [`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md), P7-14f
- [`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md),
  model integration and “Dungeon Generation Architecture”
- [`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md), R5
- [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md) for completed-milestone history
