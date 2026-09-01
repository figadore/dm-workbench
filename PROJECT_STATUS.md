# Project Status and Handoff

> Read this bounded live handoff first. Completed milestones and superseded notes are in
> [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md); implementation detail remains available in
> Git. Do not infer the next task from historical V2/V3/V4 names.

## Current State

- **Updated:** 2026-08-31
- **Branch/HEAD:** `fast-track-prompt-to-dungeon` at `b6977e1`, six commits ahead of
  `origin/fast-track-prompt-to-dungeon`, plus the uncommitted slice below.
- **Current task:** **P7-14f — Staged Tier A authoring and anti-overfitting evaluation.**
- **Task state:** the first provider-free multi-case evaluation manifest and strict
  body-free evidence contracts are implemented. Evidence-matrix validation, blinded
  aggregation, actual human ratings, and live staged Tier A remain pending.
- **Schema head:** `0008_workbench_defaults`; no migration changed or is pending.
- **Retention gate:** **not crossed.** Active V1 contracts evolve in place; there is no
  retained real-user artifact, external consumer, non-disposable deployment, or promised
  replay requirement.

## Implemented This Slice

The new Tier A anti-overfitting protocol freezes three original, non-copyrighted synthetic
briefs that differ in setting and interaction style:

- a standalone salt-marsh signal house focused on environmental navigation;
- a synthetic-grounded rootbound embassy focused on social inference and ecological
  affordances; and
- a standalone ashfall gallery focused on investigative reconstruction and risk tradeoffs.

The manifest pins three opaque stable variant IDs, hides their prompt/model/effort
assignments from reviewers, and declares one five-point quality scale. Strict models now
separate:

- body-free run measurements: stable case/variant/run IDs, assignment and artifact hashes,
  cumulative latency and measured token usage, first-pass validity, bounded repair count,
  and final validity; and
- blinded human reviews: stable reviewer/case/variant/artifact IDs plus all six cohesion
  dimensions, clue logic, player agency, puzzle comprehensibility, exploration quality,
  and DM preparation usefulness. Lore consistency is nullable for standalone cases.

Extra fields fail closed, so provider responses/excerpts cannot enter either evidence
record. Run validation enforces coherent first-pass, repair, final-validity, and artifact-
hash relationships. This is protocol/fixture coverage only; it is not generated quality
evidence and the Synthetic Constructive Archive remains only a technical regression.

## Active Boundaries and Known Issues

- There is no matrix validator yet to join manifest cases, blinded variants, run
  measurements, and human reviews or enforce exact case-by-variant coverage, stable
  assignment hashes, lore-rating applicability, and artifact-hash matching.
- No aggregate semantic/usefulness scores, latency/usage statistics, first-pass-validity
  rate, or repair rate have been calculated; no rating values are stored as evidence.
- There is still no staged live result, Tier B/C work, or resumed output/print work.
- There is no bounded cohesion-reviewer model call. Current strict report/disposition
  evidence is provider-free/human-constructible and non-authoritative.
- Live provider use remains paused. Pinned `@earendil-works/pi-ai` Codex transport does not
  serialize the requested hard output limit; post-response checks protect publication but
  cannot prevent provider usage.
- Package and root pytest suites must run separately because duplicate test module basenames
  cause import-file-mismatch when collected in one process.
- No provider was contacted. No credential, canon write, preparation approval, migration,
  queue, redaction system, second persistence store, or model-authored mechanics were added.

## Current Files and Verification

Uncommitted production/eval fixture/tests:

- `src/dm_assistant/orchestration/dungeons/evals.py`
- `tests/evals/test_dungeon_evals.py`
- `tests/evals/golden/dungeon_tier_a_manifest.json`

Uncommitted documentation:

- `dm-assistant-{implementation-plan,technical-architecture}.md`
- `dungeon-generation-recovery-plan.md`
- `PROJECT_HISTORY.md`
- `PROJECT_STATUS.md`

Recorded for this slice:

- `uv run pytest -q tests/unit tests/evals` -> **226 passed**.
- `uv run pytest -q packages/dungeon-engine/tests` -> **139 passed**.
- strict mypy over the changed Python files -> **passed**.
- Ruff lint/format over the changed Python files -> **passed**.
- JSON parsing for the new manifest -> **passed**.

Suggested commit subject: `P7-14f freeze blinded multi-case Tier A eval protocol`

## Single Next Recommended Task

**Add provider-free Tier A evidence-matrix validation and blinded aggregation.**

**First concrete action:** add a failing eval test that supplies one body-free run and one
human review for every manifest case/variant pair, then prove missing/duplicate pairs,
variant assignment-hash drift, mismatched artifact hashes, and standalone/grounded lore-
rating mistakes fail closed. Aggregate by opaque variant ID only, including every semantic
and DM-usefulness mean plus latency, token usage, first-pass-validity rate, and repair rate.
Do not store provider bodies or claim synthetic test values as quality evidence.

Do **not** start a live provider call, Tier B/C, a migration, queue, model-authored mechanics,
automatic preparation approval, canon writes, or output/print work.

## Authoritative References

- [`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md), P7-14f
- [`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md),
  “Dungeon Generation Architecture” and “Dungeon Primitives and Model Tools”
- [`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md), R5
- [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md) for compact completed-milestone history
