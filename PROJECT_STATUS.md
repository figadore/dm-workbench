# Project Status and Handoff

> Read this bounded live handoff first. Completed milestones and superseded notes are in
> [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md); implementation detail remains available in
> Git. Do not infer the next task from historical V2/V3/V4 names.

## Current State

- **Updated:** 2026-08-31
- **Branch/HEAD:** `fast-track-prompt-to-dungeon` at `814679d`, aligned with
  `origin/fast-track-prompt-to-dungeon`, plus the uncommitted slice below.
- **Current task:** **P7-14f — Staged Tier A authoring and anti-overfitting evaluation.**
- **Task state:** the hard Codex output-limit transport seam is implemented and the old
  advisory publication bypass is removed. A complete staged canary run, actual human
  ratings, and live Tier A evidence remain pending.
- **Schema head:** `0008_workbench_defaults`; no migration changed or is pending.
- **Retention gate:** **not crossed.** Active V1 contracts evolve in place; there is no
  retained real-user artifact, external consumer, non-disposable deployment, or promised
  replay requirement.

## Implemented This Slice

Pinned `@earendil-works/pi-ai` `0.84.1` accepts the gateway's generic `maxTokens` option but
omits `max_output_tokens` from its Codex Responses body. The private gateway now overlays the
exact Workbench-requested `max_output_tokens` value through pi-ai's `onPayload` boundary
after payload construction and before either SSE or WebSocket dispatch. The transform
overrides any stale adapter value and fails closed if the payload is not an object.

A provider-free gateway test uses a synthetic non-expiring OAuth JWT, forced SSE, and an
injected fetch. It captures and zstd-decompresses the actual outbound request and proves the
requested value is serialized. The body exists only in test memory and is not logged or
stored. Post-response measured output and cumulative checks remain defense in depth.

The pre-fix advisory-cap path was deleted in place under the pre-retention policy:

- the CLI no longer accepts `--acknowledge-advisory-output-cap` for prompt or canary runs;
- canary profiles no longer carry advisory policy overrides or durable bypass reports; and
- structured submissions always reject measured output above the pinned per-request limit,
  in addition to enforcing the cumulative limit.

The frozen prompt, seed, explicit provider/model selection, stop-on-failure message, and
body-free canary attempt surface remain unchanged.

## Active Boundaries and Known Issues

- `dm dungeon canary` still performs the structural prompt workflow only. It does not yet
  drive the accepted structural child through all independently bounded staged enrichment
  tasks and the final continuity/readiness gate.
- No live model generation was run, and there are no generated-artifact ratings or aggregate
  quality conclusions. Tier B/C and output/print work remain deferred.
- During the first failing transport-test setup, a synthetic OAuth credential with only a
  60-second future expiry fell inside pi-ai's refresh skew, causing one invalid synthetic
  refresh request to reach OpenAI's auth endpoint. It contained no real credential and made
  no model-generation request. The test now uses a non-expiring synthetic credential plus
  injected provider fetch; subsequent runs are provider-free.
- There is no bounded cohesion-reviewer model call. Current strict report/disposition
  evidence remains provider-free/human-constructible and non-authoritative.
- Package and root pytest suites must run separately because duplicate test module basenames
  cause import-file-mismatch when collected in one process.
- No canon write, preparation approval, migration, queue, redaction system, second
  persistence store, or model-authored mechanics were added.

## Current Files and Verification

Uncommitted gateway/runtime/tests:

- `model-gateway/{src/runtime.ts,tests/gateway.test.ts}`
- `src/dm_assistant/cli/main.py`
- `src/dm_assistant/orchestration/{dungeons,modeling}/` targeted output-cap/canary files
- `tests/{unit,integration}/` targeted output-cap/canary tests

Uncommitted documentation:

- `README.md`
- `dm-assistant-{implementation-plan,technical-architecture}.md`
- `dungeon-generation-recovery-plan.md`
- `PROJECT_HISTORY.md`
- `PROJECT_STATUS.md`

Recorded for this slice:

- `npm --prefix model-gateway run check` -> **passed**.
- `npm --prefix model-gateway test` -> **9 passed**.
- `npm --prefix model-gateway run build` -> **passed**.
- `uv run pytest -q tests/unit tests/evals` -> **228 passed**.
- `uv run pytest -q packages/dungeon-engine/tests` -> **139 passed**.
- `uv run pytest -q tests/integration/test_dungeon_studio_cli.py` -> **2 skipped**
  because the disposable integration database was unavailable.
- Ruff lint/format over changed Python -> **passed**.
- `uv run dm dungeon canary --help` check -> **retired advisory option absent**.
- Strict mypy over changed production modules and the canary test -> **passed**. A broader
  changed-test invocation still reports 40 existing typing errors in `test_cli.py` and
  `test_prompted_dungeon_workflow.py`; runtime tests for those files pass.
- `git diff --check` -> **passed**.

Suggested commit subject: `P7-14f enforce Codex output caps before dispatch`

## Single Next Recommended Task

**Wire the frozen canary to the complete staged enrichment path provider-free first.**

**First concrete action:** add a failing faux CLI/application test proving one frozen canary
structural child is resumed through the existing bounded one-step/chain coordinator with
independently resolved puzzle, exploration, feature, trap, objective, and narrative profiles,
then passes the final continuity/readiness gate. It must stop on the first rejected task,
leave the last accepted child current, never approve preparation or write canon, and retain
only body-free attempt diagnostics. Do not make a live provider call in that wiring slice.

Do **not** start Tier B/C, a migration, queue, model-authored mechanics, automatic preparation
approval, canon writes, or output/print work.

## Authoritative References

- [`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md), P7-14f
- [`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md),
  “Dungeon Generation Architecture” and “Dungeon Primitives and Model Tools”
- [`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md), R5
- [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md) for compact completed-milestone history
