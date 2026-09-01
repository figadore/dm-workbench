# Project Status and Handoff

> Read this bounded live handoff first. Completed milestones and superseded notes are in
> [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md); implementation detail remains available in
> Git. Do not infer the next task from historical V2/V3/V4 names.

## Current State

- **Updated:** 2026-08-31
- **Branch/HEAD:** `fast-track-prompt-to-dungeon` at `ca9ce7d`, aligned with
  `origin/fast-track-prompt-to-dungeon`, plus the uncommitted slice below.
- **Current task:** **P7-14f — Staged Tier A authoring and anti-overfitting evaluation.**
- **Task state:** provider-free Tier A evidence-matrix validation and blinded aggregation
  are implemented. Actual human ratings, a transport-enforced output limit, and live staged
  Tier A remain pending.
- **Schema head:** `0008_workbench_defaults`; no migration changed or is pending.
- **Retention gate:** **not crossed.** Active V1 contracts evolve in place; there is no
  retained real-user artifact, external consumer, non-disposable deployment, or promised
  replay requirement.

## Implemented This Slice

The evaluator-side matrix now fails closed unless every frozen manifest case/opaque-variant
pair has exactly one body-free run measurement and one blinded human review. Validation also
enforces:

- no missing or duplicate run/review pairs and globally unique run/review IDs;
- manifest-matching measurement/rubric pins;
- one stable assignment hash per opaque variant across all cases;
- one matching final-valid artifact hash at the run/review join; and
- omitted lore ratings for standalone cases and required lore ratings for grounded cases.

Aggregation accepts only that validated matrix and groups by opaque variant ID. Its strict
body-free result includes means for all six cohesion ratings, clue logic, player agency,
puzzle comprehensibility, exploration quality, and DM preparation usefulness; it also
includes the applicable lore-rating denominator, mean latency/input/output/total tokens,
first-pass-validity rate, and repair rate. Assignment hashes, artifact/run/reviewer IDs, and
content do not enter the aggregate. Test ratings exercise arithmetic only and are not stored
or claimed as quality evidence.

## Active Boundaries and Known Issues

- There are no actual generated-artifact ratings or aggregate quality conclusions. The
  frozen synthetic briefs and arithmetic fixtures remain protocol/regression coverage only.
- There is still no staged live result, Tier B/C work, or resumed output/print work.
- There is no bounded cohesion-reviewer model call. Current strict report/disposition
  evidence remains provider-free/human-constructible and non-authoritative.
- Live provider use remains paused. Pinned `@earendil-works/pi-ai` Codex transport receives
  the gateway `maxTokens` option but has not been proven to serialize/enforce the requested
  hard output limit; post-response checks protect publication but cannot prevent usage.
- Package and root pytest suites must run separately because duplicate test module basenames
  cause import-file-mismatch when collected in one process.
- No provider was contacted. No credential, canon write, preparation approval, migration,
  queue, redaction system, second persistence store, or model-authored mechanics were added.

## Current Files and Verification

Uncommitted production/tests:

- `src/dm_assistant/orchestration/dungeons/evals.py`
- `tests/evals/test_dungeon_evals.py`

Uncommitted documentation:

- `dm-assistant-{implementation-plan,technical-architecture}.md`
- `dungeon-generation-recovery-plan.md`
- `PROJECT_HISTORY.md`
- `PROJECT_STATUS.md`

Recorded for this slice:

- `uv run pytest -q tests/unit tests/evals` -> **230 passed**.
- `uv run pytest -q packages/dungeon-engine/tests` -> **139 passed**.
- strict mypy over the changed Python files -> **passed**.
- Ruff lint/format over the changed Python files -> **passed**.
- `git diff --check` -> **passed**.

Suggested commit subject: `P7-14f validate and aggregate blinded Tier A evidence`

## Single Next Recommended Task

**Resolve hard provider output-limit enforcement without making a live provider call.**

**First concrete action:** add a failing model-gateway transport test around the pinned
`@earendil-works/pi-ai` `openai-codex` path that captures the outbound provider request and
proves the requested `outputTokenLimit` is serialized as the provider's hard output-limit
field. If the pinned library cannot express it, document and implement the narrowest pinned
transport replacement/update before changing canary policy. Do not use post-response usage
rejection as evidence of provider-side enforcement.

Do **not** start a live provider call, Tier B/C, a migration, queue, model-authored mechanics,
automatic preparation approval, canon writes, or output/print work.

## Authoritative References

- [`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md), P7-14f
- [`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md),
  “Dungeon Generation Architecture” and “Dungeon Primitives and Model Tools”
- [`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md), R5
- [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md) for compact completed-milestone history
