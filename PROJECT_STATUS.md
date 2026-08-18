# Project Status and Handoff

> Read this file for the current implementation resume point. Historical milestones,
> superseded handoffs, and older verification results are in
> [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md) and are not required to begin work.

## Current Snapshot

- **Last updated:** 2026-08-18
- **Branch:** `fast-track-prompt-to-dungeon` — ahead of `origin/fast-track-prompt-to-dungeon` by 18 commits.
- **Working tree:** documentation-only user-directed dungeon-output refresh plan: `dungeon-output-refresh-plan.md`, P7-13 task slices in the implementation plan, architecture decisions, and this handoff. No code or migration changed.
- **Current phase:** P7-13 — Dungeon output, map readability, asset UX, and print refresh (user-directed priority; P3 remains deferred, not partially started).
- **Last completed task:** P7-13 planning baseline.
- **Current task:** **P7-13a — Output quality baseline and print fail-closed switch** (not started).
- **First action:** add the synthetic retained-output regression fixture and focused tests that measure current connector geometry, raw/colliding labels, missing keyed features, sparse print pages, and raw asset presentation before changing behavior.
- **Schema head:** `0008_workbench_defaults`.

## Current Implementation State

- V2 is the active new-generation path: a Workbench-only structured proposal is compiled by the pure `dm_dungeon` V2 compiler into deterministic kernel input, then published atomically.
- CLI and web both use `DungeonPromptApplicationService`. Each prompt starts one durable `dungeon_prompt_v2` attempt before provider contact; its UUID is the gateway caller-run ID and it safely links to the separate artifact generation run/version on completion.
- V2 has one structured submission and at most one bounded fresh repair. Shared time/token budgets, cancellation, transcript role handling, safe diagnostics, and body-free ordinary logging are enforced.
- V1 artifacts remain readable and immutable. New V1 generation has **not** been retired: P7-12g retained it because no opt-in live small-model comparison has been recorded.
- Standalone prompt-to-package preparation work is not blocked by P3-01. P3-01 is only needed to promote generated dungeon facts to campaign canon. P5-02 remains deferred.

## Latest Verification

From completed P7-12g:

- `uv run pytest -q tests/evals/test_dungeon_evals.py tests/unit/test_prompted_dungeon_workflow.py tests/unit/test_cli.py` → `29 passed`
- `uv run ruff check src/dm_assistant/orchestration/dungeons/evals.py tests/evals/test_dungeon_evals.py` → passed.
- `uv run ruff format --check src/dm_assistant/orchestration/dungeons/evals.py tests/evals/test_dungeon_evals.py` → passed.
- `uv run mypy --strict src/dm_assistant/orchestration/dungeons/evals.py` → passed.
- `git diff --check` → passed.

Post-completion P7 V2 review verification:

- `uv run pytest -q packages/dungeon-engine/tests` → `118 passed`.
- Focused V2 compiler/eval/prompt/model/CLI suites → `45 passed` before the final provenance pin, then `44 passed` across the final root focus (the package compiler cases are included in the separate 118-test package gate).
- `make test-integration PYTEST_ARGS=tests/integration/test_dungeon_studio_web_prompt.py` → `1 passed` against a disposable pgvector PostgreSQL container.
- P7/preparation PostgreSQL integration focus → `20 passed`.
- Full root unit/eval suite → `171 passed`; repository tests now ignore developer-local `.env` values explicitly.
- Focused Ruff and strict mypy over all reviewed source/test files → passed.
- `npm --prefix model-gateway run check && npm --prefix model-gateway test` → passed (`7` Node tests).
- A combined package-plus-root pytest invocation cannot collect both `packages/dungeon-engine/tests/test_cli.py` and `tests/unit/test_cli.py` in one process because they share the module basename; running the package and root gates separately passes.
- Full `make test-integration` now runs rather than skipping and reports `44 passed, 3 failed`; the remaining failures are pre-existing Library/schema issues: SQLAlchemy metadata/check-constraint drift, duplicate vector result behavior, and an embedding-resume fixture missing required document path history.
- `git diff --check` → passed.

CLI debug enhancement verification:

- `uv run pytest -q tests/unit/test_model_gateway_client.py tests/unit/test_prompted_dungeon_workflow.py tests/unit/test_cli.py` → `32 passed`.
- Focused Ruff format/lint and strict mypy over the changed CLI/model adapter/orchestration files → passed.
- `uv run dm dungeon prompt --help` confirms `--debug` is exposed.
- `git diff --check` → passed.

User-directed repair-usage diagnostic verification:

- `uv run pytest -q tests/unit/test_cli.py tests/unit/test_prompted_dungeon_workflow.py` → `29 passed`.
- `uv run ruff check` and `uv run ruff format --check` over the changed application/CLI/tests → passed.
- `uv run mypy --strict src/dm_assistant/orchestration/dungeons/application.py src/dm_assistant/cli/main.py` → passed.

User-directed V2 connection-guidance verification:

- `uv run pytest -q tests/unit/test_prompted_dungeon_workflow.py tests/unit/test_cli.py` → `30 passed`.
- `uv run ruff check` and `uv run ruff format --check src/dm_assistant/orchestration/dungeons/prompting.py tests/unit/test_prompted_dungeon_workflow.py` → passed.
- `uv run mypy --strict src/dm_assistant/orchestration/dungeons/prompting.py` → passed.
- `git diff --check` → passed.

Last-two-commit review verification:

- `uv run pytest -q packages/dungeon-engine/tests` → `120 passed`.
- `uv run pytest -q tests/unit/test_prompted_dungeon_workflow.py tests/unit/test_cli.py` → `30 passed`.
- `uv run pytest -q tests/unit tests/evals` → `177 passed`.
- Focused Ruff lint and format checks over all reviewed files → passed.
- Strict mypy over all reviewed source files → passed.
- `git diff --check` → passed.

Directional endpoint concealment verification:

- `uv run pytest -q packages/dungeon-engine/tests` → `122 passed`.
- `uv run pytest -q tests/unit tests/evals` → `177 passed`.
- `make test-integration PYTEST_ARGS='tests/integration/test_dungeon_studio_cli.py tests/integration/test_dungeon_studio_web_prompt.py tests/integration/test_preparation_persistence.py'` → `16 passed`.
- Focused Ruff lint/format and strict mypy over changed source/tests → passed after formatting.
- `git diff --check` → passed.

The frozen suite contains ten synthetic compact V2 cases: one/two floor, secret lower level, actual branch plus loop, clue gate, trap, optional hidden area, final relic, invalid-reference repair, and safe impossible-request abstention. It now enforces the declared first-pass outcomes and requested semantics, compiler/layout validity, deterministic replay, and omission of all compiler-classified DM-only components from player SVG. A body-free comparison contract records independent V1/V2 observations for tool/schema/compile/repair/semantic/package/secrecy, token, latency, and optional DM-edit metrics; it cannot accept provider response bodies or pass one response into the other run. `dungeon-intent-v2-eval` is explicitly documented as an opt-in comparison policy.

**P7-12g rollout decision:** retain the existing V2 new-generation path and V1 immutable readers/replay compatibility, but do **not** retire V1 orchestration or make an additional default/profile change. No opt-in live small-model comparison has been recorded; the synthetic suite alone cannot supply that evidence. Live calls remain excluded from CI.

## P7 V2 Review Repairs and Deferred Notes

Review fixes completed:

- Rooms reachable only through secret access are compiler-derived `dm_only`; clean player rendering no longer exposes hidden-wing room geometry. Traps/barriers retain visible destination geometry while their mechanics remain DM-only. Directional concealment is pinned as `dungeon-design-v2-compiler-3`, and final artifact generation runs record the active compiler version.
- Multiple dependencies targeting one barred connection now fail with a stable compiler diagnostic instead of silently selecting the last dependency.
- A schema-invalid V2 submit call now consumes the one bounded fresh repair path with safe location-only diagnostics and measured remaining budgets. Failed and repaired submissions preserve their own exact lineage rather than associating every run with the final proposal.
- Web no longer attempts to terminally finish an application-owned prompt run a second time, and non-cancellation `ModelRunAbstained` failures are no longer mislabeled as cancelled.
- PostgreSQL CLI/browser integration fixtures now exercise the V2 tool-call contract rather than returning obsolete V1 text. `make test-integration` provides an isolated, automatically port-assigned pgvector database and guaranteed cleanup; tests cannot inherit provider/settings policy from the ignored developer `.env`.
- `attempt_run_id` is now an allowlisted structured logging correlation field; the previously skipped browser test exposed and fixed that runtime failure.

Deferred review notes (do not fold into P3-01 opportunistically):

- Prompt-attempt inspection still does not durably pin the resolved provider/model/profile. The run begins correctly before catalog/provider contact, but the existing immutable start fields have no later safe metadata-enrichment operation. Design an explicit constrained attempt-metadata update or stage-event projection before claiming full P7-12f inspection coverage.
- Browser reconnect state is still process-local in `DungeonPromptWorkbenchService._runs`; the durable generation run survives, but a Workbench restart cannot reconstruct SSE/UI events or the final artifact link. A future P7 observability slice should project web state from durable attempt records.
- The application boundary still collapses most non-cancellation transport/submission/compile failures to `dungeon_prompt_failed`. Extend the public-safe stage/code taxonomy without exposing provider/model text.
- The implemented compact V2 schema still omits some target-boundary creative fields from P7-12 (room tags/preparation prose, tones, explicit branch/loop requests, and encounter-slot intent). P7-13d now combines that work with door/trap/puzzle/feature completeness. Add it only with synthetic small-model evidence and a new design/schema/compiler version; retained output now exists, so replacing the active V2 contract in place is prohibited.
- The frozen V2 evaluator directly checks SVG component secrecy; PNG/PDF/Roll20 secrecy remains covered by lower-level exporter tests rather than this cross-version comparison. A future eval revision should aggregate all clean package roles before using leakage as rollout evidence.

## User-Directed V2 Follow-up Tracker

- [x] **Explain a skipped V2 repair when gateway usage is unavailable.** The application now emits stable `dungeon_prompt_repair_usage_unavailable`, and the CLI explains that deterministic validation failed but safe automatic repair could not start because the gateway did not report token usage. This is not presented as a model abstention. Covered by focused CLI/application classification tests.
- [x] **Enable secret vertical links** (stairs/ladders). Design `2.1.0` accepts directional or symmetric hidden endpoints; compiler-3 derives directed discovery and endpoint publication.
- [x] **Add directional endpoint concealment/discovery semantics** for connections. Doors, stairs, and ladders support independent `from_hidden`/`to_hidden`; layout combines endpoint concealment with room publication, player output normalizes a publishable one-sided secret door, and DM output retains the secret classification. Durable in-play reveal/overlay state remains deferred.
- [x] **Bounded fresh V2 repair exists.** It remains one fresh request containing the prior compact proposal and safe diagnostics, subject to cumulative time/token budgets.
- [ ] **Make bounded repair usable with unavailable provider usage.** Requires an explicit architecture/budget-policy decision; do not treat unknown usage as zero.
- [x] **Add compact connection-validity guidance/example to the initial V2 prompt.** Instruction lineage `instructions-3` distinguishes same-floor passage/door links from cross-floor stairs/ladders and gives a compact one-sided hidden-ladder example using `from_hidden`/`to_hidden`.

## P7-13 Output Refresh Decisions

- The detailed baseline and ordered slices are in [`dungeon-output-refresh-plan.md`](dungeon-output-refresh-plan.md); the implementation plan owns stable task IDs P7-13a through P7-13g.
- The inspected screenshot is `Screenshot 2026-08-18 at 7.31.33 AM.png`. It confirms tiny endpoint doglegs/box-like corridor outlines plus overlapping raw room IDs and numbered room labels.
- There is no universal five-foot room gap: direct-door rooms share a wall, passage links use explicit corridor cells, and unrelated rooms retain one cell of rock clearance.
- Default maps use short keyed callouts and one grayscale-safe feature grammar. Opaque IDs remain in lineage/developer inspection only.
- New feature intent and composable door mechanics require retained-artifact-safe versioned contracts. Geometry/marker IDs stay in `dm_dungeon`; prose-heavy DM guide content stays in the Workbench.
- Print is planned to fail closed in P7-13a. **Current code still generates PDFs** until that slice is implemented. Historical PDFs must remain readable.
- The redesigned print feature separates bounded reference maps from selected-region exact-scale tactical tiles and rejects excessive/sparse jobs during preflight.

## P7-12g Guardrails

- Keep all eval inputs and expected outputs synthetic.
- Measure V1 versus V2 without double-persisting artifacts or placing one provider response into another model's context.
- Do not make live provider calls part of CI; any live small-model evaluation is opt-in and follows faux/provider-contract coverage.
- Do not change the default profile or retire V1 generation until the documented P7-12g thresholds and CLI, web, cancellation, publication, logging, and replay gates pass.

## Handoff

- **Task completed:** P7-13 planning baseline only; implementation has not started.
- **Files changed:** added `dungeon-output-refresh-plan.md`; added P7-13a..g and its phase gate to `dm-assistant-implementation-plan.md`; updated connection geometry, feature/DM-guide, renderer grammar, asset catalog, and guarded print decisions in `dm-assistant-technical-architecture.md`; updated this handoff. No code, tests, schema, or migration changed.
- **Commands run:** latest screenshot helper and image inspection; targeted source/contract/template/test inspection; `git diff --check` (passed). No test suite was run because this handoff changes documentation only.
- **Important current behavior:** print has been marked for centralized disabling in P7-13a, but the existing UI/service still creates PDF and Roll20 exports together. Do not claim print is disabled until tests and shared application policy prove it.
- **Compatibility decision:** retained dungeon output now exists. P7-13 geometry, renderer, creative intent, package, and PDF changes receive new version pins/readers and never rewrite historical specifications or asset links.
- **Working tree:** documentation changes listed above are uncommitted; no pre-existing uncommitted code was present when planning began.
- **Single next recommended task:** P7-13a — Output quality baseline and print fail-closed switch. **First concrete action:** add the synthetic retained-output regression fixture and focused metric tests before splitting PDF/Roll20 export selection or changing behavior.
- **Suggested commit subject:** `P7-13 plan dungeon output refresh`.
- Before changing code or schema: inspect `git status --short --branch`, read this file, read P7-13a and `dungeon-output-refresh-plan.md`, then follow the applicable architecture invariants.
