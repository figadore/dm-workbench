# Project Status and Handoff

> Read this bounded live handoff first. Completed milestones and superseded notes are in
> [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md); implementation detail remains available in
> Git. Do not infer the next task from historical V2/V3/V4 names.

## Current State

- **Updated:** 2026-09-01
- **Branch/HEAD:** `fast-track-prompt-to-dungeon` at `4e870bc`, two commits ahead of
  `origin/fast-track-prompt-to-dungeon`, plus the uncommitted gate-repair slice below.
- **Current task:** **P7-14f — Staged Tier A authoring and anti-overfitting evaluation.**
- **Task state:** the complete frozen faux canary now passes against disposable PostgreSQL:
  both six-task/final-gate success and third-task output-cap rejection are proven through
  the shared application path. No live provider call or human quality rating has run.
- **Schema head:** `0008_workbench_defaults`; no migration changed or is pending.
- **Retention gate:** **not crossed.** Active V1 contracts evolve in place; there is no
  retained real-user artifact, external consumer, non-disposable deployment, or promised
  replay requirement.

## Implemented This Slice

The PostgreSQL gate exposed four defects hidden while the new tests were skipped:

1. the faux workflows supplied `synthetic-dm` to the single-DM scope contract instead of
   the authenticated `dm` principal;
2. exploration context incorrectly required `RoomRole.EXPLORATION`, although the Tier A
   compiler requires every branch room to retain `RoomRole.OPTIONAL`; the exact accepted
   exploration encounter slot/intent is now authoritative and projection still rechecks
   that intent against the accepted plan;
3. the dynamic faux gateway assumed every staged payload had singular `context.room`, so
   it failed on the bounded `context.rooms` narrative task; and
4. the rejection assertion used a retired limit-kind spelling rather than the emitted
   body-free `output` code.

The complete success case now publishes six atomic DM-only enrichment children after the
structural version, reaches the deterministic final gate, preserves package/map bytes,
keeps the artifact `draft`, and contacts exactly the seven expected tool seams. The
rejection case stops on feature output overage, leaves the puzzle/exploration child current,
persists only body-free usage evidence, and makes no later provider call.

A stale browser integration assertion now expects the intentional deterministic ordinary-
presence discovery statement for a structural gate dependency. Architecture and plan text
clarify that an exact exploration slot is authoritative for optional branch rooms; this is
an in-place alpha V1 clarification, not a version bump.

## Active Boundaries and Known Issues

- No live model generation was run. There are no generated-artifact ratings or aggregate
  quality conclusions; actual blinded human evidence remains pending.
- There is no bounded cohesion-reviewer model call. Current strict report/disposition
  evidence remains provider-free/human-constructible and non-authoritative.
- A broad disposable-PostgreSQL integration run reached **65 passed, 4 failed**. The one
  stale dungeon web assertion was corrected and passes in the focused gate. Three unrelated
  Library/schema failures remain: metadata reports 18 constraint diffs, one embedding run
  can set `finished_at` before database-authored `started_at`, and one direct document-
  revision fixture violates the source-history trigger. Do not conflate these with the
  green staged-canary gate; investigate them only as a separate task.
- Strict mypy over the changed production service and typed coordinator test passes. Adding
  the older web integration module to that command exposes nine pre-existing typing errors
  in its `Settings` construction/JSON indexing; this slice did not broaden into that cleanup.
- Package and root pytest suites must run separately because duplicate test module basenames
  cause import-file-mismatch when collected in one process.
- No canon write, preparation approval, migration, queue, redaction system, second
  persistence store, or model-authored mechanics was added.
- Tier B/C and output/print work remain deferred.

## Current Files and Verification

Uncommitted production code:

- `src/dm_assistant/orchestration/dungeons/service.py`

Uncommitted tests:

- `tests/integration/test_dungeon_staged_enrichment_coordinator.py`
- `tests/integration/test_dungeon_studio_web_prompt.py`

Uncommitted documentation:

- `dm-assistant-implementation-plan.md`
- `dm-assistant-technical-architecture.md`
- `PROJECT_STATUS.md`

Recorded for this slice:

- Required PostgreSQL gate over coordinator + CLI -> **10 passed**.
- Focused PostgreSQL gate including browser prompt -> **11 passed**.
- `uv run pytest -q tests/unit tests/evals` -> **229 passed**.
- `uv run pytest -q packages/dungeon-engine/tests` -> **139 passed**.
- Full `tests/integration` attempt -> **65 passed, 4 failed** before the relevant stale
  browser assertion was fixed; the three remaining failures are listed above.
- Strict mypy over changed production + typed coordinator test -> **passed**.
- Ruff lint/format over changed Python -> **passed**.
- `git diff --check` -> **passed** after the final handoff update.

Suggested commit subject: `P7-14f pass staged faux canary PostgreSQL gate`

## Single Next Recommended Task

**Run the frozen staged live Tier A canary exactly once with explicit provider/model/effort,
then stop on its first failure and retain only the existing body-free operational evidence.**

**First concrete action:** rebuild/restart the private model-gateway and Workbench containers
from current HEAD so the tested Codex `max_output_tokens` overlay and complete staged CLI are
active. Re-list authenticated providers, explicitly select the intended provider/model and
supported effort, then invoke `dm dungeon canary` once without transient debug-body logging.
Do not retry a failed stage or switch models in the same slice.

After that one run, record its IDs, stop/public code, measured usage, final deterministic
result, and whether a preparation-ready draft exists. Human quality review and the frozen
multi-case blinded matrix remain subsequent evidence work. Do **not** start Tier B/C, a
migration, queue, automatic approval, canon writes, or output/print work.

## Authoritative References

- [`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md), P7-14f
- [`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md),
  “Dungeon Generation Architecture” and “Dungeon Primitives and Model Tools”
- [`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md), R5
- [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md) for compact completed-milestone history
