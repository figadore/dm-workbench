# Project Status and Handoff
> Only live resume point. Git supplies working-tree state; [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md)
> records durable milestones.

## Current Task
- **Application-wide guidance design:** documentation complete; no runtime implementation, schema
  change, or partial write path. P7-15a target-packet acceptance is not established by this change.
- **Schema head:** `0008_workbench_defaults`. **Retention gate:** not crossed.

## Design Outcome
- Architecture §9 owns the application-wide guidance contract: first-class natural language,
  observations distinct from desired direction, relevant task context, scope/pins and human confirmation.
- P7-16 introduces explicit guidance; P7-18 adds confirmed preferences and demand-driven procedures.
  Later workflows reuse the same contract. No feature-specific settings catalogue or puzzle subsystem.
- Removed puzzle-specific delivery commitments and shortened duplicated explanation in goals, plan,
  README and history. Existing examples are not additional product requirements.
- This change intentionally excludes the separate P7-15a adventure documents, map, and human-feedback
  record. Their absence here does not mean no candidate authoring or human review has occurred.

## Implementation Baseline
- Existing staged generation, token login, basic asset UI, and faux Ask surfaces remain implemented.
  Cohesive authoring, normal owner login, the new editor, guidance and contextual conversations remain
  planned. Technical checks alone do not establish adventure usefulness or human phase acceptance.

## Intentional Uncommitted Work
- Guidance documentation only: `dm-assistant-project-goals.md`, `dm-assistant-implementation-plan.md`,
  `dm-assistant-technical-architecture.md`, `README.md`, `PROJECT_HISTORY.md`, and this handoff.
- Conflicts in history/handoff resolved without importing unrelated target-packet milestones or
  claiming that absent review files are available. The resolved documentation is staged for completion.
- Existing alpha remains runnable. No live calls, preparation approval or canonical writes occurred.

## Verification / Blockers
- Provider-free `tests/evals/test_dungeon_evals.py`: **12 passed**.
- Documentation links, handoff length, conflict-marker/index checks and `git diff --check` checked.
- Candidate documents and existing human feedback must be reconciled separately before target
  acceptance. Do not invent missing review/edit-time or tabletop evidence; live trials need permission.

## Single Next Recommended Task
**P7-15a — Reconcile the target packet and review evidence.**
First action: read P7-15a and inspect the separately authored candidates and existing human feedback;
select the documents to bring into scope through a separate reviewed change. Use that evidence to
confirm or revise the target rather than asking for a redundant initial review. Do not begin live
trials or production refactoring before the relevant gates.
