# Project Status and Handoff

> Read this file for the current implementation resume point. Historical milestones,
> superseded handoffs, and older verification results are in
> [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md) and are not required to begin work.

## Current Snapshot

- **Last updated:** 2026-08-19
- **Branch:** `fast-track-prompt-to-dungeon` — ahead of `origin/fast-track-prompt-to-dungeon` by 21 commits.
- **Working tree:** uncommitted P7-13a/P7-13b/P7-13c work plus WIP P7-13d V3 creative/mechanics-contract work. No migration changed.
- **Current phase:** P7-13 — Dungeon output, map readability, asset UX, and print refresh (user-directed priority; P3 remains deferred, not partially started).
- **Last completed task:** **P7-13c — Renderer visual grammar and collision-free annotation.**
- **Current task:** **P7-13d — Doors, traps, puzzles, features, and a usable DM guide (WIP).**
- **First action:** completed retained-artifact-safe V3 creative/mechanics and exact package-contract slices; next, compile V3 intent into a V3 topology/layout request and make deterministic layout emit the new package without altering V2 or the immutable `1.1.0` reader.
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
- [x] **Propagate measured `pi-ai` usage through the private gateway.** The pinned `pi-ai` final-message contract uses `usage.input`/`usage.output`; the gateway now maps those fields to its normalized SSE event, and its faux-provider contract test requires that event. V2 repair coverage verifies a measured rejected submission gets one fresh request with a reduced token budget.
- [ ] **Make bounded repair usable with genuinely unavailable provider usage.** Requires an explicit architecture/budget-policy decision; do not treat unknown usage as zero.
- [x] **Add compact connection-validity guidance/example to the initial V2 prompt.** Instruction lineage `instructions-3` distinguishes same-floor passage/door links from cross-floor stairs/ladders and gives a compact one-sided hidden-ladder example using `from_hidden`/`to_hidden`.

## P7-13 Output Refresh Decisions

- The detailed baseline and ordered slices are in [`dungeon-output-refresh-plan.md`](dungeon-output-refresh-plan.md); the implementation plan owns stable task IDs P7-13a through P7-13g.
- The inspected screenshot is `Screenshot 2026-08-18 at 7.31.33 AM.png`. It confirms tiny endpoint doglegs/box-like corridor outlines plus overlapping raw room IDs and numbered room labels.
- There is no universal five-foot room gap: direct-door rooms share a wall, passage links use explicit corridor cells, and unrelated rooms retain one cell of rock clearance.
- Default maps use short keyed callouts and one grayscale-safe feature grammar. Opaque IDs remain in lineage/developer inspection only.
- New feature intent and composable door mechanics require retained-artifact-safe versioned contracts. Geometry/marker IDs stay in `dm_dungeon`; prose-heavy DM guide content stays in the Workbench.
- User-directed P7-13d clarification: freeze a connection-mechanics matrix. Same-floor passages carry no hidden/barrier/trap mechanics; same-floor doors may combine concealment, lock/puzzle gate, and trap; cross-floor stairs/ladders allow directional hidden endpoints plus optional explicitly located source/destination endpoint doors or hatches with those same mechanics. The task now explicitly requires deterministic endpoint anchor/traversal/dependency semantics, truthful repair diagnostics, no lost gate/trap during compilation, mechanics-matrix/prompt-repair coverage, and a terminal result distinct from a model abstention after bounded rejected submissions.
- P7-13a centrally disables new print generation. Historical PDFs remain readable; print re-enable requires the new PDF request/exporter version and P7-13f preflight gates.
- The redesigned print feature separates bounded reference maps from selected-region exact-scale tactical tiles and rejects excessive/sparse jobs during preflight.

## P7-12g Guardrails

- Keep all eval inputs and expected outputs synthetic.
- Measure V1 versus V2 without double-persisting artifacts or placing one provider response into another model's context.
- Do not make live provider calls part of CI; any live small-model evaluation is opt-in and follows faux/provider-contract coverage.
- Do not change the default profile or retire V1 generation until the documented P7-12g thresholds and CLI, web, cancellation, publication, logging, and replay gates pass.

## Handoff

- **Task completed:** P7-13c — Renderer visual grammar and collision-free annotation.
- **Implemented behavior:** `orthogonal-v3` uses the retained-artifact-safe `DungeonPackageV2` root schema `1.2.0`; its `PassageOpening` records pin each corridor's room-wall segment and outward approach direction. The reader dispatches `1.1.0` to the original model (legacy JSON still round-trips exactly) and `1.2.0` to the new model. V3 direct-door pairs share a wall, emit no synthetic corridor, and validate as corridor-free shared-wall openings. Passage routing enumerates valid exterior openings, reserves endpoint leads, ranks bends, length, unrelated-room clearance, and seeded ties, and emits two stable opening IDs per corridor. Compact placement ranks occupied bounds before local graph distance while unrelated rooms retain rock clearance. V3 geometry rejects room-interior corridors, invalid/missing openings, wrong endpoint approach, undeclared room-wall contact, and non-shared direct doors. SVG clips corridor outlines and erases room-wall strokes only at explicit V3 openings, leaving retained legacy SVG bytes/goldens unchanged. Locked V3 corridor paths recover/pin their opening records.
- **Files changed:** P7-13a files listed below remain uncommitted, plus `packages/dungeon-engine/src/dm_dungeon/{__init__.py,serialization.py,contracts/{__init__.py,package_v2.py},layout/{contracts,engine,placement,routing}.py,rendering/svg.py,validation/{geometry,geometry_contracts}.py}` and `packages/dungeon-engine/tests/{test_layout,test_routing,test_geometry_validation,test_rendering}.py`; no migration changed.
- **Implemented behavior:** `ExportDungeonWorkflow` now selects exactly one format. The centralized `DungeonStudioService` policy rejects `pdf` before reading/generating anything with stable `dungeon_print_export_disabled`; `roll20` creates only Roll20 bundles/manifests. CLI has `--format roll20|pdf`; the web only offers Roll20 and explains print is disabled; API/web/CLI tests exercise the same PDF rejection. Existing PDF asset reads/routes were untouched. The frozen synthetic retained-output fixture includes shared-wall direct-door intent, straight and deliberately one-bend connector geometry, secret/locked/trapped doors, a trap, puzzle room, clue/key, stairs, feature, and a sparse 56x56 upper floor. Its golden/metrics record 3 raw opaque IDs, 3 text collisions, 1 endpoint-clearance bend, 6 corridor/room interior-overlap cells, 3 missing keyed mechanics, and 73 PDF pages with 66/72 blank tiles.
- **Commands/tests run:** `uv run pytest -q packages/dungeon-engine/tests` → `124 passed`; `uv run pytest -q tests/unit/test_cli.py tests/integration/test_dungeon_studio_workflow.py tests/integration/test_dungeon_studio_cli.py tests/integration/test_dungeon_studio_web.py` → `18 passed, 6 skipped`; focused Ruff lint/format and strict mypy → passed; `make test-integration PYTEST_ARGS='tests/integration/test_dungeon_studio_workflow.py tests/integration/test_dungeon_studio_cli.py tests/integration/test_dungeon_studio_web.py'` → `6 passed`; `git diff --check` → passed.
- **Commands/tests run for P7-13b:** `uv run pytest -q packages/dungeon-engine/tests` → `128 passed`; `uv run ruff check packages/dungeon-engine/src/dm_dungeon packages/dungeon-engine/tests` → passed; `uv run ruff format --check packages/dungeon-engine/src/dm_dungeon packages/dungeon-engine/tests` → passed; `uv run mypy --strict packages/dungeon-engine/src/dm_dungeon` → passed; `git diff --check` → passed.
- **User-directed completed repair:** gateway final-usage normalization now follows pinned `@earendil-works/pi-ai`'s `Usage.input`/`Usage.output` contract rather than unsupported camel/snake-case provider fields. The Node faux stream contract now requires `usage`, and the V2 repair test records both request profiles and proves the second budget is reduced by first-call usage. Files: `model-gateway/src/server.ts`, `model-gateway/tests/gateway.test.ts`, and `tests/unit/test_prompted_dungeon_workflow.py`.
- **Repair verification:** `npm --prefix model-gateway run check && npm --prefix model-gateway test` → 7 passed; focused V2/Python client test selection → 2 passed; Ruff lint/format and strict mypy over changed Workbench source → passed; `git diff --check` → passed. Running the whole `tests/unit/test_model_gateway_client.py tests/unit/test_prompted_dungeon_workflow.py` selection yields 15 passed, 2 failed in unrelated V1 repair tests because the current P7-13b layout/preflight behavior consumes the V1 profile's remaining turn budget (`no budget remains for deterministic diagnostic repair`); do not fold that V1/P7-13 issue into the gateway repair.
- **User-directed planning clarification:** updated `dm-assistant-implementation-plan.md` and `dungeon-output-refresh-plan.md` to make P7-13d/g cover the complete connection-mechanics matrix, versioned composable-door implementation, explicitly located cross-floor endpoint doors/hatches for barriers/traps, preservation of every accepted mechanic, truthful prompt/repair diagnostics, renderer/DM-guide integration, matrix and prompt-repair evaluations, and correct terminal classification after exhausted rejected submissions. This was documentation-only; `git diff --check` passed and no test suite was needed.
- **Implemented behavior for P7-13c:** `MapKey`/`MapCallout` is a versioned (`1.0.0`) pure renderer projection. It deterministically allocates floor-local room numbers and `D`/`T`/`F`/`X` callouts only after audience filtering, then uses pinned text bounds and candidate/ring placement to guarantee non-overlapping boxes and leader lines when local placement is exhausted. `SvgAnnotationMode` makes `none`, `callouts`, and inspection-only `developer_ids` explicit. New `DungeonPackageV2` (`1.2.0`) default SVG/PNG/PDF/Workbench output uses callouts; retained `1.1.0` package output keeps its old unannotated/default and explicit developer-ID behavior. DM callouts show secret/trapped badges; player projections have no DM-only badge allocation. The SVG grammar has grayscale-safe circle/triangle/square/transition primitives, and Pillow draws the same trusted primitives.
- **Files changed for P7-13c:** `packages/dungeon-engine/src/dm_dungeon/{__init__.py,cli.py,export/{pdf,raster}.py,rendering/{__init__,annotations,contracts,svg,themes}.py}`, `packages/dungeon-engine/tests/test_rendering.py`, and `src/dm_assistant/orchestration/dungeons/service.py`; no migration changed.
- **Commands/tests run for P7-13c:** focused renderer/compiler/PNG/PDF tests → `37 passed`; strict package mypy → passed; focused Ruff lint/format → passed; `git diff --check` → passed. The full package suite currently reports `127 passed, 2 failed` in existing Hypothesis `orthogonal-v2` layout-property cases (seeds `10075227` and `2280218`, `geometry.walkable_region_disconnected`); renderer changes do not execute layout generation. The existing root prompted-workflow focus similarly reports `28 passed, 2 failed, 6 skipped` in the documented V1 remaining-repair-budget cases; do not fold either unrelated P7-13b/V1 failure into P7-13c.
- **P7-13d WIP implemented:** Added a separate strict `DungeonDesignSpecV3` (`3.0.0`) plus an independently versioned pure `dungeon-design-v3-compiler-1` mechanics-plan compiler. V3 retains V2 readers unchanged and models room tags/preparation notes/encounter-slot intent, features, complete room traps/puzzles, explicit loops/branches, composable same-floor door mechanics, and explicitly named vertical endpoint doors/hatches. The contract rejects hidden/barred/trapped passages and treats vertical locks/puzzles/traps as endpoint-door/hatch mechanics rather than transition mechanics. The pure compiler assigns stable V3 IDs and pinned `dungeon-mechanics-policy-1` difficulties, preserves a concealed gate-plus-trap as one record containing both IDs and its exact lock-versus-puzzle kind, and produces safe missing/duplicate dependency diagnostics. Added separately dispatched `DungeonPackageV3` (`1.3.0`) with `ComposableDoorMechanicsV3`, direct-door geometry, and exact directional `VerticalEndpointDoorLayoutV3` anchors. It validates layer/room/link/position/directional-side references and independently retains a gate plus trap. Concealment is now explicitly coupled to the appropriate directional endpoint in the creative contract, so a V3 compiler cannot emit a concealed same-floor door or endpoint hatch that the exact package would reject as ambiguously publishable. Existing readers remain exact; CLI canonicalizes V3 but explicitly fails validation/render/export closed until V3 validator/renderer support exists. V3 is still **not wired into the prompted workflow, V3 topology/layout, renderer, or DM guide**, so it creates no artifact.
- **P7-13d files changed:** `packages/dungeon-engine/src/dm_dungeon/{__init__.py,cli.py,compiler_v3.py,serialization.py,contracts/{__init__.py,design_v3.py,package_v3.py}}`, `packages/dungeon-engine/tests/{test_design_v3_compiler.py,test_package_v3.py}`, and this status file; no migration changed.
- **P7-13d verification:** focused V3 compiler/package tests after endpoint-concealment tightening → `9 passed`; prior V3 compiler/package/CLI focus → `19 passed`; Ruff check and format over changed package source/test → passed; strict package mypy → passed; full package suite → `136 passed, 2 failed` in the documented pre-existing `orthogonal-v2` Hypothesis cases (`geometry.walkable_region_disconnected`, seeds `10075227` and `2280218`); `git diff --check` → passed.
- **Working tree:** uncommitted P7-13a/P7-13b/P7-13c code, tests, status, planning changes, the user-directed gateway-usage repair, the P7-13d planning clarification, and WIP V3 creative/mechanics/package contracts; no migration changed.
- **Single next recommended task:** **Continue P7-13d.** **First concrete action:** define/compile a V3 topology that carries composable same-floor and vertical endpoint mechanics into a V3 layout request, then make deterministic layout emit `DungeonPackageV3` without dropping gates or traps.
- **Suggested commit subject:** `P7-13d add versioned dungeon mechanics intent`.
- Before changing code or schema: inspect `git status --short --branch`, read this file, read P7-13a and `dungeon-output-refresh-plan.md`, then follow the applicable architecture invariants.
