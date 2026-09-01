# Project Status and Handoff

> Read this bounded live handoff first. Completed milestones and superseded notes are in
> [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md); implementation detail remains available in
> Git. Do not infer the next task from historical V2/V3/V4 names.

## Current State

- **Updated:** 2026-08-31
- **Branch/HEAD:** `fast-track-prompt-to-dungeon` at `ade318c`, one commit ahead of
  `origin/fast-track-prompt-to-dungeon`, plus the uncommitted slice below.
- **Current task:** **P7-14f — Staged Tier A authoring and anti-overfitting evaluation.**
- **Task state:** the frozen canary is wired through the complete staged application path
  provider-free. Root/package tests pass; the new PostgreSQL-backed faux success/rejection
  tests are collected but skipped because no disposable integration database is configured.
  No live provider call or human quality rating has run.
- **Schema head:** `0008_workbench_defaults`; no migration changed or is pending.
- **Retention gate:** **not crossed.** Active V1 contracts evolve in place; there is no
  retained real-user artifact, external consumer, non-disposable deployment, or promised
  replay requirement.

## Implemented This Slice

`dm dungeon canary` no longer stops at structural publication. A shared canary application
service now:

1. enforces the exact frozen prompt, seed, and canary surface;
2. publishes one accepted structural draft through the existing application seam;
3. derives exact trusted puzzle, exploration, feature, trap, objective, and bounded
   narrative policies from that package;
4. resolves all six task profiles independently;
5. resumes the current child through the existing bounded one-step/chain coordinator; and
6. invokes the read-only final continuity/readiness gate only after chain completion.

A failed structural call performs no enrichment. A rejected enrichment stops the chain,
keeps the last accepted child current, and prevents all later provider seams. The CLI emits
only artifact/run IDs, stop/public codes, resolved selection, and body-free final-validation
evidence. It never approves preparation or calls a canonical service; every artifact remains
`draft`.

The Workbench runtime now composes all six existing task-specific application services over
the configured private gateway and exposes only the complete canary application to the CLI.
Each accepted task still creates its own atomic DM-only child with unchanged package/map
bytes and task-specific lineage/budget enforcement.

The provider-free faux application coverage uses an original five-room Windglass Shrine
plan matching the frozen Tier A structure: optional branch, secret loop, locked gate/key,
puzzle, exploration slot with local feature, moderate trap, and named objective. It covers:

- six accepted enrichments followed by a valid final deterministic gate; and
- output-cap rejection on the third enrichment, no later dispatch, last accepted child
  current, draft lifecycle, and a body-free durable usage report.

Because structural `guide_content` was removed, a named structural key/clue dependency no
longer requires a prose-heavy gate entry merely to enter staged authoring. Deterministic code
projects only the accepted dependency name and exact room as an ordinary-presence discovery
statement. It does not invent concealment, acquisition checks, consequences, or richer gate
interaction content.

## Active Boundaries and Known Issues

- The new complete faux application tests require `DM_TEST_DATABASE_URL` naming a disposable
  `*_test` PostgreSQL database. They were skipped in this environment and therefore still
  need one database-backed execution before a live canary.
- No live model generation was run. There are no generated-artifact ratings or aggregate
  quality conclusions; actual blinded human evidence remains pending.
- There is no bounded cohesion-reviewer model call. Current strict report/disposition
  evidence remains provider-free/human-constructible and non-authoritative.
- Package and root pytest suites must run separately because duplicate test module basenames
  cause import-file-mismatch when collected in one process.
- No canon write, preparation approval, migration, queue, redaction system, second
  persistence store, or model-authored mechanics was added.
- Tier B/C and output/print work remain deferred.

## Current Files and Verification

Uncommitted production code:

- `src/dm_assistant/cli/main.py`
- `src/dm_assistant/runtime.py`
- `src/dm_assistant/orchestration/dungeons/{__init__,canary_application,service}.py`

Uncommitted tests:

- `tests/unit/{test_cli,test_dungeon_canary,test_dungeon_puzzle_enrichment_contract}.py`
- `tests/integration/{test_dungeon_puzzle_prompt,test_dungeon_staged_enrichment_coordinator,test_dungeon_studio_cli}.py`

Uncommitted documentation:

- `dm-assistant-{implementation-plan,technical-architecture}.md`
- `dungeon-generation-recovery-plan.md`
- `PROJECT_STATUS.md`

Recorded for this slice:

- `uv run pytest -q tests/unit tests/evals` -> **229 passed**.
- `uv run pytest -q packages/dungeon-engine/tests` -> **139 passed**.
- Targeted integration collection -> **12 skipped** because `DM_TEST_DATABASE_URL` is absent.
- Targeted strict mypy over changed production and typed tests -> **passed**.
- Ruff lint/format over changed Python -> **passed**.
- Provider-free compile check for the exact five-room faux canary plan -> **accepted**.
- `git diff --check` -> **passed** after the final handoff update.

Suggested commit subject: `P7-14f wire frozen canary through staged enrichment`

## Single Next Recommended Task

**Execute the complete faux canary gates against disposable PostgreSQL, then fix only any
wiring defects they expose.**

**First concrete action:** set `DM_TEST_DATABASE_URL` to an empty `*_test` database and run
`uv run pytest -q tests/integration/test_dungeon_staged_enrichment_coordinator.py tests/integration/test_dungeon_studio_cli.py`. Confirm the complete six-task/final-gate case and
the third-task rejection case pass before making any live provider call.

After that gate is green, the next separate slice may run the frozen staged live canary once
with explicit provider/model selection and stop on its first failure. Do **not** start Tier
B/C, a migration, queue, automatic approval, canon writes, or output/print work.

## Authoritative References

- [`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md), P7-14f
- [`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md),
  “Dungeon Generation Architecture” and “Dungeon Primitives and Model Tools”
- [`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md), R5
- [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md) for compact completed-milestone history
