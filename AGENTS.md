# Coding-Agent Instructions

## Start Every Session

Before changing code or schema:

1. Run `git status --short --branch`; inspect, but do not overwrite, existing work.
2. Read `PROJECT_STATUS.md` completely. It alone defines the live task and next action.
3. Read only that task in `dm-assistant-implementation-plan.md` and the linked architecture sections.
4. Follow repository-local package documentation for the area being changed.

Git is authoritative for branch, HEAD, ahead/behind state, and the working-tree diff. Do not copy
that volatile output into project documentation. `PROJECT_STATUS.md` records only the semantic
state Git cannot explain: whether intentional work is incomplete or unsafe, which uncommitted files
belong to the current task, and what the next agent should do with them.

## Non-Negotiable Boundaries

- Models create proposals only. They never approve preparation artifacts or commit canonical state.
- Canonical writes use a validated change set and create one atomic campaign revision.
- Preparation is separate from canon: `approved_for_play` or `used` never means planned events
  occurred.
- The model supplies typed creative intent. Deterministic code owns IDs, topology, exact geometry,
  pathfinding, arithmetic, validation, rendering, and exports.
- The pure in-process `dm_dungeon` package cannot import Workbench application modules, FastAPI,
  SQLAlchemy, retrieval, repositories, or provider clients.
- The Workbench owns orchestration and durable domain state. The private Node gateway owns only
  provider authentication, catalog, and transport through pinned `@earendil-works/pi-ai`.
- Chat and embedding runtimes remain separate. Never obtain embeddings by prompting a chat model.
- Generation uses a small common provenance envelope plus strict domain payloads; never create a
  universal optional-field generation context.
- Authorization and source filters run before retrieval and model context construction. Existing
  source revisions and cited spans are immutable.
- Missing or ambiguous information remains unknown. Keep plans, claims, beliefs, rules, and
  canonical reality distinguishable.
- Player/clean exports fail closed for secrets. Print exports must preserve exact scale and validated
  tiling/calibration when enabled.
- Do not add an agent framework, queue, database, domain service, or symmetric encounter package
  without measured need and an architecture update.
- Use only synthetic fixtures. Never commit real campaign text, copyrighted rules/bestiary content,
  character sheets, credentials, OAuth data, or provider responses.

## Alpha Retention Gate

Until both `PROJECT_STATUS.md` and the architecture declare the retention gate crossed, evolve active
V1 schemas, prompts, generators, renderers, exporters, fixtures, and review packets in place. Do not
add compatibility readers or version bumps for disposable alpha data.

Cross the gate no later than the first intentionally retained real-user artifact/campaign, external
consumer, non-disposable deployment, or promised replay requirement. Before an incompatible change
after that point, document reader, migration, replay, and rollback policy.

## Task Discipline

- Use the implementation-plan task ID in work and commit subjects when applicable.
- Keep one task small and independently testable; do not opportunistically begin the next phase.
- Add or update tests with behavior.
- Prefer migrations over ad hoc schema creation.
- Reuse application services from CLI, API, and web handlers.
- Record architecture-level decisions before relying on them broadly.
- Do not run live model/provider calls without explicit authorization.

## Handoff

Before stopping:

1. Run focused tests and at least `git diff --check`.
2. Update `PROJECT_STATUS.md` to at most 70 lines with:
   - current task and exact state;
   - completed behavior;
   - intentional uncommitted or unsafe files, if any;
   - relevant tests and unresolved blockers;
   - one next task and its first concrete action.
3. Do **not** record branch names, commit hashes, ahead/behind counts, or a full `git status`; the next
   session obtains those directly from Git.
4. Move only durable milestone outcomes to `PROJECT_HISTORY.md` in compact form. Git retains detailed
   chronology, run-by-run investigation, and old handoffs.
5. If work is incomplete, state whether it is runnable and identify any partial migration or write
   path explicitly.

No document other than `PROJECT_STATUS.md` may present itself as the current task or next action.
