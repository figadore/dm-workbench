# Project Status and Handoff

> Read this bounded live handoff first. Completed milestones and superseded notes are in
> [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md); implementation detail remains available in
> Git. Do not infer the next task from historical V2/V3/V4 names.

## Current State

- **Updated:** 2026-09-01
- **Branch/HEAD:** `fast-track-prompt-to-dungeon` at `ff4aaab`, four commits ahead of
  `origin/fast-track-prompt-to-dungeon`, plus the uncommitted P7-14f provider-policy slice.
- **Current task:** **P7-14f — Staged Tier A authoring and anti-overfitting evaluation.**
- **Task state:** provider-aware output limits are implemented and active in the rebuilt local
  stack. Codex subscription is usable again without the rejected hard-cap overlay; the live
  Tier A quality gate still needs one newly authorized canary and human evidence.
- **Schema head:** `0008_workbench_defaults`; no migration changed or is pending.
- **Retention gate:** **not crossed.** Active V1 contracts evolve in place; there is no
  retained real-user artifact, external consumer, non-disposable deployment, or promised
  replay requirement.

## Evidence and Decision

Two authorized `openai-codex/gpt-5.4` standard-effort canaries stopped at the initial
structural stream before output:

- replacement attempt `03595071-0d8a-40cf-806a-f2a9b483ace2` safely classified the failure
  as `provider_request_rejected`;
- diagnostic attempt `11dc1e1a-a834-4dad-ab89-03c266abb8ce` emitted only a transient no-store
  fingerprint confirming that `max_output_tokens` was the rejected parameter.

Neither attempt produced measured usage, an artifact/version, a staged task, or a final gate.
Their usage is unknown, not zero. The fingerprint/provider body was absent from ordinary logs
and durable attempt evidence. No provider/model call was made after the diagnostic attempt.

Provider-free research found no alternate hard-cap field for ChatGPT/Codex subscription:

- official OpenAI Codex source at `bc39b0e` exposes none of `max_output_tokens`, `max_tokens`,
  or `max_completion_tokens` in its model Responses request/config path;
- open enhancement <https://github.com/openai/codex/issues/36180> confirms that gap;
- pinned `pi-ai` 0.84.1 and registry-latest 0.84.4 both omit those fields for Codex;
- OpenAI's separate public API `CreateResponse` contract supports `max_output_tokens`.

The user explicitly revised the alpha policy so subscription backends remain usable. Gateway
capability `hard_output_token_limit` now distinguishes transports with a documented provider
ceiling. `openai-codex` omits unsupported output-limit fields and does not advertise it;
standard API-key `openai` serializes the requested `max_output_tokens` and does advertise it.

For every provider, Workbench per-response and cumulative measured ceilings remain strict.
Timeout/cancellation, repair reservation, missing-usage failure, and fail-before-publication
behavior remain unchanged. Codex can consume subscription quota before an over-limit result is
rejected; CLI and web selection now disclose that application-only enforcement. No advisory
publication bypass was restored.

## Active Boundaries and Known Issues

- No valid live Tier A artifact or human rating exists; the P7-14f quality gate remains red.
- A new live canary requires renewed explicit authorization; this change did not make one.
- Blinded human evidence and the frozen multi-case matrix remain pending.
- Tier B/C and output/print work remain deferred until Tier A is dependable.
- Three unrelated Library/schema integration failures remain: metadata constraint diffs,
  embedding client/database timestamp ordering, and a direct document-revision fixture that
  violates the source-history trigger.
- Package and root pytest suites must run separately because duplicate test basenames cause
  import-file-mismatch when collected together.
- No canon write, preparation approval, migration, queue, second store, or model-authored
  mechanics was added.

## Files and Verification

Uncommitted production/test slice:

- `model-gateway/src/{contracts,provider-errors,runtime,server}.ts`
- `model-gateway/tests/gateway.test.ts`
- `src/dm_assistant/adapters/model_gateway.py`
- `src/dm_assistant/cli/main.py`
- `src/dm_assistant/web/templates/model_panel.html`
- `tests/unit/{test_cli,test_model_gateway_client}.py`
- `tests/integration/test_dungeon_studio_web_prompt.py`

Uncommitted documentation:

- `README.md`
- `dm-assistant-technical-architecture.md`
- `dm-assistant-implementation-plan.md`
- `dungeon-generation-recovery-plan.md`
- `PROJECT_STATUS.md`

Verification:

- `npm --prefix model-gateway run check` -> passed.
- `npm --prefix model-gateway test` -> **14 passed**; injected fetch proves Codex omits all
  unsupported fields and standard OpenAI serializes `max_output_tokens: 654`.
- `uv run --frozen pytest -q tests/unit tests/evals` -> **233 passed**.
- `uv run --frozen pytest -q packages/dungeon-engine/tests` -> **139 passed**.
- Focused Python tests -> **29 passed**.
- Focused web integration test -> skipped because integration PostgreSQL was not configured.
- Focused Ruff lint/format -> passed.
- Strict mypy over changed Python production modules -> passed.
- `make stack-up` -> rebuilt/recreated both code-bearing services.
- Immediate `make stack-smoke` raced Workbench startup once; after eight seconds -> ready with
  configuration, database, pgvector, and schema checks passing.
- `git diff --check` -> passed.

Suggested commit subject: `P7-14f support application-capped Codex subscription runs`

## Single Next Recommended Task

**Review and commit this provider-aware policy slice, then obtain renewed explicit authorization
for exactly one frozen Codex Tier A canary.**

**First concrete action:** inspect the uncommitted diff and commit it with the suggested P7-14f
subject. Rebuild from that HEAD and confirm readiness. If a canary is then authorized, use the
same `openai-codex/gpt-5.4`, standard-effort, seed-`714000001` command once without `--debug` or
contract diagnostics, and stop on its first result.

A valid staged artifact proceeds to human review and the frozen blinded matrix. Do not start
P8, Tier B/C, print work, a migration, queue, approval, or canon writes.

## Authoritative References

- [`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md), P7-14f
- [`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md), model
  integration and “Dungeon Generation Architecture”
- [`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md), R5
- [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md) for completed-milestone history
