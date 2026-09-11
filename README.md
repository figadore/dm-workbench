# DM Assistant Harness

A self-hosted workbench for preparing and running adventures with a human Dungeon Master.

**First product:** turn a prompt into a complete, independently runnable small dungeon one-shot in a
pleasant map-and-guide workspace. Then add component-scoped AI revision, selected campaign hooks, and
persistent campaign memory. Models propose; the DM controls edits, preparation approval, and canon.

## What Exists and What Is Planned

The alpha implements a Python Workbench, private `pi-ai` model gateway, pure deterministic dungeon
kernel, DM/player exports, preparation storage/versioning, Dungeon Studio, and immutable-source/hybrid
retrieval foundations. The existing prompted authoring path uses staged enrichments; the unified
roadmap replaces that path with cohesive whole-adventure authoring after proving its usefulness.

The existing browser still uses API-token login and a basic asset-oriented interface. Normal owner
login, a polished inline review workspace, manual text editing, and component conversations are
**planned**, not delivered by the documentation update. Existing faux Ask surfaces are not a completed
campaign-grounded assistant. Passing technical checks does not establish that generated one-shots are
ready to run without additional authoring. Application-wide guidance, human-confirmed preferences and
reusable non-executable procedures are also **planned**, not implemented by these documents.

See [`PROJECT_STATUS.md`](PROJECT_STATUS.md) for the exact live task, evidence, and next action.

## What You Will Be Able to Try

| Phase | Experience |
| --- | --- |
| **1 — A One-Shot Worth Running** | Review and walk through complete adventures with concrete clues, obstacles, opposition, and endings. |
| **2 — Prompt to Play** | Sign in, supply scoped guidance, generate, review/edit map and guide together, save, and export. |
| **3 — Maps Worth Exploring** | Use attractive compact maps with meaningful terrain, consistent keys, and synchronized selection. |
| **4 — Revise with Your Assistant** | Ask or propose scoped edits; separately confirm remembered preferences and reuse reviewed procedures when justified. |
| **5 — Bring Your Campaign** | Attach selected facts, claims and hooks without turning preparation into canon. |
| **6 — Remember What Happened** | Ask sourced campaign questions and review session outcomes into persistent memory. |

Browser usability begins in phase 2, not after campaign integration. Map visual quality follows in
phase 3; contextual collaboration follows the safe editing boundary in phase 4. Exact-scale print,
arbitrary maps, and full encounter/profile systems are separate gates, not prerequisites for a useful
standalone release.

## Documentation

- [`dm-assistant-project-goals.md`](dm-assistant-project-goals.md) — product vision and user experience.
- [`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md) — ordered, human-readable
  phases, task IDs, dependencies, demos, and acceptance gates.
- [`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md) — target boundaries,
  authoring/revision design, security, context, persistence, and evaluation.
- [`PROJECT_STATUS.md`](PROJECT_STATUS.md) — the only live resume point.
- [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md) — compact delivered milestones and durable decisions.

The old dungeon recovery/output plans are superseded navigation stubs, not additional roadmaps.
For implementation, follow [`AGENTS.md`](AGENTS.md): inspect Git, read status completely, then read only
the selected task and linked architecture/package documentation.

## Architecture

- One Python 3.12 FastAPI/Typer modular Workbench; CLI/API/browser share application services.
- One pure in-process `dm_dungeon` package for exact construction, validation, rendering, and exports.
- One private Node gateway through pinned `@earendil-works/pi-ai` for provider auth/catalog/transport.
- One PostgreSQL 16 database with pgvector and immutable source/artifact lineage; embedding adapters
  are separate from chat runtime.

Dungeon authoring is a Workbench capability, not a microservice. Standalone means no campaign lore is
required; it may still use the existing preparation owner and selected rules/party assumptions. The
model supplies creative intent; code owns IDs, geometry, numeric policy and publication. Player output
is filtered before rendering. No generated or approved preparation establishes that events occurred.

## Run the Existing Alpha

These commands describe implemented interfaces, not the future UI. Requirements: Docker Desktop or
Podman, `make`, and OpenSSL or Python for local secret generation.

```bash
make stack-up
make stack-smoke
make stack-token
```

Open `http://127.0.0.1:8000/login` and use the token printed by `make stack-token` **until P7-16b replaces
the browser login experience**. Do not disable authentication to bypass this temporary UX.

Bootstrap creates an ignored mode-`0600` `.env` with distinct local database/API/session/gateway
secrets, builds containers, migrates PostgreSQL, and starts the stack. It never creates provider
credentials. Only Workbench is host-published; gateway credentials remain in its private volume.

```bash
make stack-down       # retains volumes
make dev-db           # PostgreSQL for native development
make dev-api          # Python Workbench
make dev-gateway      # separate terminal; requires the internal gateway token
```

For native development:

```bash
uv sync --all-packages --all-groups --frozen
uv run --frozen alembic upgrade head
uv run --frozen dm doctor
uv run --frozen dm --help
```

For macOS/Podman native operation, configure `.env` with a host database URL at `127.0.0.1` and real
absolute `DM_SOURCE_ROOTS`, `DM_ASSET_ROOT`, and `DM_SCRATCH_ROOT` paths. Host-loopback gateway URLs are
for native execution; Compose uses `http://model-gateway:3000` internally. See
[`model-gateway/README.md`](model-gateway/README.md) for gateway-specific setup.

## Existing Dungeon and Source Interfaces

The gateway is optional for deterministic map work:

```bash
uv run --frozen dm campaign create "Main Campaign"
uv run --frozen dm campaign use "Main Campaign"
uv run --frozen dm dungeon generate layout-request.json --title "Sunken Archive"
uv run --frozen dm dungeon inspect <artifact-uuid>
uv run --frozen dm dungeon compare <left-version> <right-version>
uv run --frozen dm dungeon export <version-uuid>
uv run --frozen dm dungeon approve <artifact-uuid> <version-uuid> --reason "Reviewed for play."
```

The current prompted flow starts with `dm dungeon prompt "A flooded archive beneath a lighthouse"`;
it is not yet the new complete two-pass one-shot workflow. Provider calls/retries/evaluations require
explicit authorization. Inspect providers with `dm model providers`; use `dm model login <provider>`
for deliberate gateway-owned authentication. Never put provider credentials in root `.env`.
`dm dungeon run inspect <attempt-run-id>` gives body-free diagnostics. Explicit `--debug` capture is
sensitive local output, not routine logging or a commit input.

Historical fixed-case/evidence commands and ignored packets characterize the staged alpha, not a
required product review workflow. Use CLI help and project status before operating them. Do not run
new provider comparisons merely to satisfy superseded gates.

Source imports copy authorized local material into managed volumes, but do not make it canonical:

```bash
make import-campaign-sources SOURCE="$HOME/Documents/my-campaign"
make import-rules-sources SOURCE="$HOME/Documents/my-authorized-rules"
docker compose exec workbench dm library ingest notes/session-01.md --root root-0
docker compose exec workbench dm library ingest rules/hiding.md \
  --root root-1 --corpus global_rules --ruleset 5e2024
```

Existing revisions/citations are immutable. Do not intentionally retain real-user artifacts or deploy
non-disposable data without declaring the retention gate and migration/replay/rollback policy.

The pure kernel is independently usable:

```bash
uv run dm-dungeon validate packages/dungeon-engine/tests/fixtures/sunken_archive.v1.json
uv run dm-dungeon schema
```

See [`packages/dungeon-engine/README.md`](packages/dungeon-engine/README.md) and its
[`TOPOLOGY_MATH.md`](packages/dungeon-engine/src/dm_dungeon/validation/TOPOLOGY_MATH.md).

## Verification

```bash
uv run --frozen pytest -q tests/unit tests/evals
uv run --frozen pytest -q packages/dungeon-engine/tests
make test-integration
make check
```

Root and package suites run separately because test basenames overlap. Integration tests use isolated
PostgreSQL databases. `make check` runs the disposable containerized gate; select Podman with
`CONTAINER_ENGINE=podman ./scripts/check-container.sh` if needed.

Human review and actual rendered maps/browser walkthroughs complement tests; they are not replaced by
schema success or AI critique. `make dungeon-review-packet` creates an ignored synthetic technical
regression packet, not evidence of generalized live adventure quality or preparation approval.

Health: `/health/live` and `/health/ready`; other application/API access is authenticated. Credentials,
real campaign/rules/bestiary/sheet material, and raw provider responses never belong in the repository.

## License and Third-Party Marks

Copyright (C) 2026 Reese Wilson. Original code/documentation are licensed under AGPL-3.0-only; see
[`LICENSE`](LICENSE). Third-party dependencies retain their terms. Dungeons & Dragons, D&D, and Roll20
are trademarks of their respective owners; descriptive use implies no affiliation.
