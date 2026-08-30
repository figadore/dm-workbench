# Coding-Agent Instructions

## Mandatory Read Order

Before changing code or schema:

1. Run `git status --short --branch` and inspect existing work.
2. Read `PROJECT_STATUS.md` completely.
3. Read the relevant phase/task in `dm-assistant-implementation-plan.md`.
4. Read the relevant architecture sections and follow their invariants.
5. Do not overwrite or discard work you did not create.

The live next task is defined by `PROJECT_STATUS.md`, not by guessing from the directory tree.

## Alpha Versioning and the Retention Gate

- Until the project explicitly declares the **retention gate** crossed in both
  `PROJECT_STATUS.md` and the architecture, evolve active V1 schemas, prompts,
  generators, renderers, exporters, fixtures, and review-packet formats **in place**.
  Do not bump labels or add compatibility readers for synthetic fixtures, ignored review
  packets, disposable alpha databases, or provider canaries.
- Declare the retention gate no later than the first intentionally retained real-user
  campaign/artifact, external consumer, non-disposable deployment, or promised replay
  requirement. At that point, freeze the retained pins and document reader/migration and
  compatibility policy before making incompatible changes.
- After the retention gate, version changes only when retained data or consumers need a
  distinguishable contract/implementation for correct reading, replay, migration, or
  rollback. A code change alone is not a reason to increment a version.

## Non-Negotiable Invariants

- A model can write canonical proposals only; it can never commit canonical campaign state or approve preparation artifacts.
- Canonical writes go through a validated change set and create one atomic campaign revision.
- Dungeon/encounter artifacts live in a separate preparation lifecycle. `approved_for_play` or `used` never means the planned events became canon.
- The LLM expresses dungeon/encounter intent through typed primitives; deterministic code owns IDs, exact geometry, connectivity/pathfinding, rules arithmetic, validation, rendering, and exports.
- The pure `dm_dungeon` workspace package runs in the Python Workbench process but cannot import Workbench application modules, FastAPI, SQLAlchemy, retrieval, campaign repositories, or model/provider clients. It accepts versioned typed inputs and is independently testable without PostgreSQL or a model credential.
- Generation context uses a small common envelope for scope/provenance/visibility/citations/hash plus strict domain payloads such as `DungeonGenerationContext` and `EncounterGenerationContext`. Never grow one universal optional-field `GenerationContext`.
- Encounter orchestration starts as a Workbench feature. Do not create an `encounter-engine` package for symmetry; extract only a measured cohesive deterministic `encounter-mechanics` boundary after the documented P8 decision.
- The independent DM harness owns its web/CLI interaction, task orchestration, context policy, and durable run state. A private Node gateway uses pinned `@earendil-works/pi-ai` only for provider auth/catalog/transport and must never expose OAuth credentials to the browser or Python service.
- Keep chat-model and embedding runtimes separate: `pi-ai` does not provide embeddings. Vectors are derived/versioned projections with lexical fallback; never generate embeddings by prompting a chat model.
- Do not add `@earendil-works/pi-agent-core` initially. Reconsider it only when measured open-ended multi-turn tool-loop needs exceed the bounded Python workflows, and keep PostgreSQL/application services authoritative if it is adopted.
- Pi extensions and local/private MCP are optional later adapters, not the primary UI or internal browser/API transport.
- Generated dungeon/artifact versions pin seeds, schemas, generator/renderer versions, the exact domain-context envelope/payload hash and sources, inputs, validation reports, and lineage.
- Every committed revision has a readable summary and detailed provenance/audit history.
- Plans, adventure material, beliefs, claims, rules, and canonical reality remain distinguishable.
- Authorization/source filters run before retrieval and model context construction.
- Existing document revisions and cited source spans are immutable.
- Missing or ambiguous information is reported as unknown; do not manufacture chronology or facts.
- Do not add domain microservices, an agent framework, another database, or a queue without measured need and an explicit architecture update. The narrow Node `pi-ai` model gateway is the documented runtime-boundary exception; the dungeon package is an in-process package boundary, not a service, and the gateway owns no campaign/domain state apart from its dedicated credential/runtime cache.
- Do not commit real campaign text, copyrighted rules/bestiary content, character sheets, OAuth/API credentials, or provider responses as test fixtures. Use synthetic fixtures, creatures, dungeons, encounters, and fake model/embedding providers.
- Clean map/handout exports must fail closed: no secret doors, traps, creature starts, hidden DCs, or puzzle solutions without explicit publication.
- Print exports use exact one-inch-per-five-foot scale, low-ink line styling, and validated tiled-page stitching/calibration metadata.

## How to Work a Task

- Use the task ID from the implementation plan, such as `P1-03`.
- Keep one task small and independently testable. Avoid opportunistically starting the next phase.
- Add or update tests with the behavior.
- Prefer migrations over ad hoc schema creation.
- Reuse application services from both CLI and API; do not duplicate business logic in handlers.
- Record any architecture-level decision in the architecture document or a later ADR before relying on it broadly.
- If commits are part of the current user/harness workflow, begin the subject with the task ID. Otherwise leave the work uncommitted and record a suggested commit subject in `PROJECT_STATUS.md`.

## Required Handoff Update

Before stopping—especially when context or credits are low—update `PROJECT_STATUS.md` with:

- task completed or exact WIP task;
- files and migrations changed;
- commands/tests run and their results;
- unresolved errors or assumptions;
- working-tree state;
- the **single next recommended task** and its first concrete action.

Keep `PROJECT_STATUS.md` as a bounded active handoff: no more than **150 lines or
12 KB**. Rewrite its current sections instead of appending chronology. Move completed
milestones, superseded handoffs, review iterations, and old verification runs to
`PROJECT_HISTORY.md` in compact form. Do not duplicate Git history or retain a broad
repository file inventory; identify only current-task or uncommitted files and let agents
use Git for older detail.

If stopping mid-task, include the failing command/output summary and identify incomplete or unsafe code. Never leave the next agent to infer whether a migration or canonical-write path is partially implemented.

Run at least `git diff --check` before handoff. Run the phase-specific gate commands whenever the environment supports them.
