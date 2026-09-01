# Project Status and Handoff

> Read this bounded live handoff first. Completed milestones and superseded notes are in
> [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md); implementation detail remains available in
> Git. Do not infer the next task from historical V2/V3/V4 names.

## Current State

- **Updated:** 2026-08-31
- **Branch/HEAD:** `fast-track-prompt-to-dungeon` at `223211d`, four commits ahead of
  `origin/fast-track-prompt-to-dungeon`, plus the uncommitted slice below.
- **Current task:** **P7-14f — Staged Tier A authoring and anti-overfitting evaluation.**
- **Task state:** resumed one-step coordinator coverage now spans every staged enrichment
  kind. Automatic repetition/full-chain dispatch remains deliberately unimplemented.
- **Schema head:** `0008_workbench_defaults`; no migration changed or is pending.
- **Retention gate:** **not crossed.** Active V1 contracts evolve in place; there is no
  retained real-user artifact, external consumer, non-disposable deployment, or promised
  replay requirement.

## Implemented This Slice

The faux-provider coordinator scenario now resumes from an accepted puzzle child and covers
exploration, feature interaction, trap, objective, and one bounded room-narrative set through
the existing task-specific application seams.

For feature, trap, objective, and room narrative it proves that:

- the trusted discriminated policy must match the planner's exact room and target IDs;
- mismatched IDs/room sets fail before provider contact and create no artifact version;
- a matching policy invokes only the selected task tool;
- one accepted child becomes current and is replanned exactly once;
- the expected deterministic next kind is selected without automatic dispatch; and
- completing narratives leaves the plan complete while package bytes remain unchanged.

The synthetic coordinator proposal now includes one trap so the resumed scenario covers the
full puzzle/exploration/feature/trap/objective/narrative order. No coordinator production
branch changed; this slice supplies the missing end-to-end evidence for branches already
present behind the discriminated policy boundary.

## Active Boundaries and Known Issues

- There is still no automatic chain repetition/full-chain dispatcher, multi-case quality
  comparison, staged live result, Tier B/C work, or resumed output/print work.
- There is no bounded cohesion-reviewer model call. Current strict report/disposition evidence
  is provider-free/human-constructible and non-authoritative.
- The browser/CLI do not collect prompted cohesion report/disposition documents; this fails
  closed. The authenticated JSON API accepts the strict evidence.
- Live provider use remains paused. Pinned `@earendil-works/pi-ai` Codex transport does not
  serialize the requested hard output limit; post-response checks protect publication but
  cannot prevent provider usage.
- Package and root pytest suites must run separately because duplicate test module basenames
  cause import-file-mismatch when collected in one process.
- Disposable-PostgreSQL integration is skipped locally because `DM_TEST_DATABASE_URL` is
  unset and Docker/PostgreSQL are unavailable. The expanded coordinator test therefore
  collected but did not execute against PostgreSQL in this environment.
- No provider was contacted. No credential, canon write, migration, queue, redaction system,
  second persistence store, or model-authored mechanics were added.

## Current Files and Verification

Uncommitted test:

- `tests/integration/test_dungeon_staged_enrichment_coordinator.py`

Uncommitted documentation:

- `dm-assistant-{implementation-plan,technical-architecture}.md`
- `dungeon-generation-recovery-plan.md`
- `PROJECT_HISTORY.md`
- `PROJECT_STATUS.md`

Recorded for this slice:

- `uv run pytest -q tests/unit tests/evals` -> **221 passed**.
- `uv run pytest -q packages/dungeon-engine/tests` -> **139 passed**.
- `uv run pytest -q tests/integration/test_dungeon_staged_enrichment_coordinator.py` ->
  **5 skipped** (database fixture unavailable).
- strict mypy with `MYPYPATH=src:packages/dungeon-engine/src` over the changed test ->
  **passed**.
- Ruff lint/format over the changed test -> **passed**.
- direct Pydantic validation of the new feature/trap/objective/narrative faux outputs ->
  **passed**.
- `git diff --check` -> **passed** before final documentation refresh.

Suggested commit subject: `P7-14f cover every resumed staged coordinator seam`

## Single Next Recommended Task

**Add a bounded provider-free repeated/full-chain coordinator over the proven one-step
boundary.**

**First concrete action:** add a failing test that supplies trusted exact policies for the
remaining deterministic plan, accepts two successive fake task children, then rejects the
third and proves repetition stops immediately with that parent current, no fourth provider
call/version, and no approval or canonical operation. Keep an explicit maximum task bound
and preserve the existing one-step coordinator as the only dispatch primitive.

Do **not** start a live/holistic provider call, Tier B/C, a migration, queue, model-authored
mechanics, automatic preparation approval, canon writes, or output/print work.

## Authoritative References

- [`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md), P7-14f
- [`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md),
  “Dungeon Generation Architecture” and “Dungeon Primitives and Model Tools”
- [`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md), R5
- [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md) for compact completed-milestone history
