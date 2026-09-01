# Project Status and Handoff

> Read this bounded live handoff first. Completed milestones and superseded notes are in
> [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md); implementation detail remains available in
> Git. Do not infer the next task from historical V2/V3/V4 names.

## Current State

- **Updated:** 2026-08-31
- **Branch/HEAD:** `fast-track-prompt-to-dungeon` at `8f5fd98`, five commits ahead of
  `origin/fast-track-prompt-to-dungeon`, plus the uncommitted slice below.
- **Current task:** **P7-14f — Staged Tier A authoring and anti-overfitting evaluation.**
- **Task state:** bounded provider-free chain repetition is implemented over the proven
  one-step staged-enrichment boundary. Multi-case quality evidence and live staged Tier A
  remain pending.
- **Schema head:** `0008_workbench_defaults`; no migration changed or is pending.
- **Retention gate:** **not crossed.** Active V1 contracts evolve in place; there is no
  retained real-user artifact, external consumer, non-disposable deployment, or promised
  replay requirement.

## Implemented This Slice

`DungeonStagedEnrichmentChainCoordinator` now consumes an ordered set of trusted exact
policy/profile pairs and repeats only `DungeonStagedEnrichmentCoordinator.execute`:

- every accepted child version becomes the next current parent;
- rejection stops immediately and leaves the last accepted parent current;
- blocked and complete replans stop without another dispatch;
- policy exhaustion and the explicit 32-task hard ceiling are distinct outcomes; and
- the boundary has no preparation-approval or canonical operation.

Provider-free unit coverage proves two accepted fake children followed by a rejected third
never invoke the fourth dispatch, a complete accepted child ends the chain, and the task
ceiling is never exceeded. The faux-provider PostgreSQL scenario supplies puzzle,
exploration, feature, and trap policies: puzzle and exploration publish, the feature call
fails its hard output check, and the trap provider is never contacted. The artifact remains
`draft`, only the two accepted children exist, and the exploration child remains current.

## Active Boundaries and Known Issues

- There is still no multi-case quality comparison, staged live result, Tier B/C work, or
  resumed output/print work.
- There is no bounded cohesion-reviewer model call. Current strict report/disposition
  evidence is provider-free/human-constructible and non-authoritative.
- The browser/CLI do not collect prompted cohesion report/disposition documents; this fails
  closed. The authenticated JSON API accepts the strict evidence.
- Live provider use remains paused. Pinned `@earendil-works/pi-ai` Codex transport does not
  serialize the requested hard output limit; post-response checks protect publication but
  cannot prevent provider usage.
- Package and root pytest suites must run separately because duplicate test module basenames
  cause import-file-mismatch when collected in one process.
- Disposable-PostgreSQL integration is skipped locally because `DM_TEST_DATABASE_URL` is
  unset and Docker/PostgreSQL are unavailable. The chain integration test collected but did
  not execute against PostgreSQL in this environment.
- No provider was contacted. No credential, canon write, preparation approval, migration,
  queue, redaction system, second persistence store, or model-authored mechanics were added.

## Current Files and Verification

Uncommitted production/tests:

- `src/dm_assistant/orchestration/dungeons/{__init__,staged_enrichment_coordinator}.py`
- `tests/unit/test_dungeon_staged_enrichment_chain.py`
- `tests/integration/test_dungeon_staged_enrichment_coordinator.py`

Uncommitted documentation:

- `dm-assistant-{implementation-plan,technical-architecture}.md`
- `dungeon-generation-recovery-plan.md`
- `PROJECT_HISTORY.md`
- `PROJECT_STATUS.md`

Recorded for this slice:

- `uv run pytest -q tests/unit tests/evals` -> **224 passed**.
- `uv run pytest -q packages/dungeon-engine/tests` -> **139 passed**.
- `uv run pytest -q tests/integration/test_dungeon_staged_enrichment_coordinator.py` ->
  **6 skipped** (database fixture unavailable).
- strict mypy with `MYPYPATH=src:packages/dungeon-engine/src` over the coordinator and its
  changed tests -> **passed**.
- Ruff lint/format over the changed Python files -> **passed**.
- `git diff --check` -> **passed** after the final documentation refresh.

Suggested commit subject: `P7-14f bound repeated staged enrichment dispatch`

## Single Next Recommended Task

**Start the small multi-case Tier A anti-overfitting evaluation set.**

**First concrete action:** add a failing provider-free eval test for a manifest of at least
three materially different synthetic, non-copyrighted settings/interaction styles. Require
stable blinded case/variant IDs and the documented semantic, DM-usefulness, latency, usage,
first-pass validity, and repair-rate rating fields without storing provider bodies. Keep the
Synthetic Constructive Archive only as a technical renderer/secrecy regression.

Do **not** start a live provider call, Tier B/C, a migration, queue, model-authored mechanics,
automatic preparation approval, canon writes, or output/print work.

## Authoritative References

- [`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md), P7-14f
- [`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md),
  “Dungeon Generation Architecture” and “Dungeon Primitives and Model Tools”
- [`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md), R5
- [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md) for compact completed-milestone history
