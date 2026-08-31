# Project Status and Handoff

> Read this bounded live handoff first. Completed milestones and superseded notes are in
> [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md); implementation detail remains available in
> Git. Do not infer the next task from historical V2/V3/V4 names.

## Current State

- **Updated:** 2026-08-31
- **Branch/HEAD:** `fast-track-prompt-to-dungeon` at `2d0e78a`, three commits ahead of
  `origin/fast-track-prompt-to-dungeon`, plus the uncommitted slice below.
- **Working tree:** **uncommitted P7-14f prompted approval and staged review-packet final-
  gate enforcement**. No migration, provider call, credential, canonical campaign path,
  chain dispatcher, or pure-package behavior is partially edited.
- **Current task:** **P7-14f — Staged Tier A authoring and anti-overfitting evaluation.**
- **Task state:** the final deterministic gate now blocks prompted preparation approval and
  staged review packets; all six cohesion dimensions require explicit hash-bound DM
  disposition. Broader resumed one-step coordinator coverage remains before repetition.
- **Schema head:** `0008_workbench_defaults`; no migration changed or is pending.
- **Retention gate:** **not crossed.** Active V1 contracts evolve in place; there is no
  retained real-user artifact, external consumer, non-disposable deployment, or promised
  replay requirement.

## Implemented This Slice

Prompted approval now:

- distinguishes prompted/staged specifications from provider-independent manually authored
  Studio artifacts;
- retains the existing preparation-readiness check for every artifact;
- reruns `validate_final_staged_dungeon()` before any prompted lifecycle transition;
- fails closed when continuity, sources, dependencies, required content, lineage, typed
  cross-task references, or player secrecy fail;
- requires a strict cohesion report plus DM-authored disposition bound to the exact
  specification, deterministic-result, continuity, and report hashes;
- requires disposition of all six dimensions and every exact finding; and
- blocks `targeted_regeneration` decisions while preserving the report's inability to edit,
  clear blockers, approve preparation, or write canon.

The JSON approval API can carry the strict report/disposition models. Existing CLI/browser
approval remains sufficient for provider-independent artifacts; a prompted artifact cannot
use those evidence-free adapters to bypass the gate.

The staged provider-free review-packet writer now:

- reruns the same final gate and refuses an invalid staged specification;
- validates the exact report/disposition binding without performing lifecycle or canonical
  operations;
- emits exact DM/player maps, guide, rubric, report, disposition JSON, and a readable DM
  disposition record; and
- persists only the deterministic result hash and seven body-free check summaries, never
  final-gate diagnostics or provider bodies.

The existing fixed synthetic archive packet remains a renderer/secrecy regression and the
provider-independent approval workflow retains its readiness-based path.

## Tests Added/Extended

Provider-free tests prove:

- a fully enriched prompted artifact with stale source lineage fails before the preparation
  transition even when supplied with a previously valid cohesion report/disposition;
- a valid prompted artifact cannot transition without all six DM dispositions;
- exact valid evidence reaches the lifecycle boundary;
- a report/disposition cannot clear a failed deterministic gate;
- staged review output contains all seven check families but no diagnostics or guide body in
  its deterministic summary; and
- the existing provider-independent workflow test still exercises readiness-based approval
  unchanged (integration is locally skipped without its database fixture).

## Active Boundaries and Known Issues

- Broader resumed feature/trap/objective/narrative coordinator coverage, automatic chain
  repetition, multi-case quality comparison, staged live result, Tier B/C, and resumed
  output/print work remain pending.
- There is no bounded cohesion-reviewer model call yet. Current strict report and disposition
  evidence is provider-free/human-constructible and non-authoritative.
- The browser/CLI do not yet collect prompted report/disposition documents; this fails closed
  rather than permitting evidence-free prompted approval. The authenticated JSON API accepts
  the strict evidence.
- Live provider use remains paused. Pinned `@earendil-works/pi-ai` Codex transport does not
  serialize the requested hard output limit; post-response checks protect publication but
  cannot prevent provider usage. The frozen-canary exception remains operator risk, not
  ordinary rollout permission.
- Package and root pytest suites must run separately because duplicate test module basenames
  cause an import-file-mismatch when collected in one process.
- Disposable-PostgreSQL integration is skipped locally because `DM_TEST_DATABASE_URL` is
  unset and Docker is unavailable.
- No provider was contacted. No credential, canon write, migration, queue, redaction system,
  second persistence store, or model-authored mechanics are present.

## Current Files and Verification

Uncommitted production/tests:

- `src/dm_assistant/orchestration/dungeons/{final_validation,review,service}.py`
- `src/dm_assistant/orchestration/dungeons/__init__.py`
- `src/dm_assistant/api/dungeons.py`
- `tests/unit/test_dungeon_staged_enrichment_plan.py`

Uncommitted documentation:

- `README.md`
- `dm-assistant-{implementation-plan,technical-architecture}.md`
- `dungeon-generation-recovery-plan.md`
- `PROJECT_HISTORY.md`
- `PROJECT_STATUS.md`

Recorded for this slice:

- `uv run pytest -q tests/unit tests/evals` -> **221 passed**.
- `uv run pytest -q packages/dungeon-engine/tests` -> **139 passed**.
- focused staged/review-packet tests -> **16 passed**.
- focused PostgreSQL workflow -> **2 skipped** (database fixture unavailable).
- strict mypy over every changed production Python file and focused test -> **passed**.
- Ruff lint/format over every changed Python file -> **passed**.
- `git diff --check` -> **passed** before documentation refresh.

Suggested commit subject: `P7-14f enforce final gate at prompted approval`

## Single Next Recommended Task

**Add provider-free resumed one-step coordinator coverage for feature, trap, objective, and
room-narrative targets before any automatic repetition/full-chain dispatcher.**

**First concrete action:** add a failing coordinator test for the exact next feature target
proving a matching trusted feature policy invokes only that one existing seam and replans the
accepted child, while a mismatched feature ID makes no provider call and writes no version.
Then repeat that established discriminated-policy pattern for trap, objective, and bounded
room narrative without adding a loop.

Do **not** add chain repetition, a live/holistic provider call, Tier B/C, a migration, queue,
model-authored mechanics, automatic preparation approval, or canon writes.

## Authoritative References

- [`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md), P7-14f
- [`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md),
  “Dungeon Generation Architecture” and “Dungeon Primitives and Model Tools”
- [`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md), R5
- [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md) for compact completed-milestone history
