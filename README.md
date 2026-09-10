# DM Assistant Harness

A self-hosted, AI-assisted dungeon and encounter generator, campaign memory, and context compiler for
a human Dungeon Master running D&D 5e/2024-era campaigns.

The project is in alpha. The Python Workbench, private model gateway, provider-independent Dungeon
Studio, deterministic dungeon/export kernel, PostgreSQL preparation lifecycle, immutable Library
sources, and hybrid retrieval foundation are implemented. See [`PROJECT_STATUS.md`](PROJECT_STATUS.md)
for the exact current task.

## Documentation

For product or architecture review:

1. [`dm-assistant-project-goals.md`](dm-assistant-project-goals.md) — desired product and scope.
2. [`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md) — current
   boundaries, data semantics, and invariants.
3. [`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md) — completed index and
   unfinished tasks.

For an implementation session:

1. Run `git status --short --branch`.
2. Read [`PROJECT_STATUS.md`](PROJECT_STATUS.md) and [`AGENTS.md`](AGENTS.md).
3. Read only the active task and linked architecture sections.

Historical detail is in Git; [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md) is only a milestone summary.

## Architecture at a Glance

- One Python 3.12 FastAPI/Typer Workbench organized as a modular monolith.
- One independently testable pure `dm_dungeon` package loaded in that Python process.
- One private Node gateway using pinned `@earendil-works/pi-ai` for provider credentials, catalog,
  streaming, tool transport, and usage—not campaign state.
- One PostgreSQL 16 database with pgvector; embedding adapters are separate from chat providers.
- Immutable source revisions and versioned lexical/semantic retrieval projections.
- Perspective-, temporal-, and provenance-aware canonical campaign state.
- Versioned preparation artifacts with seeded deterministic dungeon topology, geometry, validation,
  rendering, and exports.
- Models propose; only the DM approves preparation or commits canon.
- Player-facing output fails closed for secret or unclassified data.

## Quick Start: Full Stack

Requirements: Docker Desktop or Podman, `make`, and OpenSSL (or Python for secret generation).

```bash
make stack-up
make stack-smoke
make stack-token
```

`make stack-up` creates the ignored mode-`0600` `.env` when needed, generates distinct local
database/API/session/internal-gateway secrets, builds images, migrates PostgreSQL, and starts the
stack. It never generates provider credentials.

Open `http://127.0.0.1:8000/login` and use the token printed by `make stack-token`. Only the
Workbench is host-published. The model gateway remains on the private Compose network and stores
OAuth credentials in its dedicated volume.

```bash
make stack-down       # retain volumes
# Add the engine's volume-removal option only when intentionally deleting local data.
```

## Quick Start: Native Development

Use native Python and Node processes for fast reloads while Compose supplies PostgreSQL:

```bash
make dev-db
make dev-api
# In another terminal, with the shared internal gateway token exported:
make dev-gateway
```

The Python environment is repository-local and managed by `uv`:

```bash
uv sync --all-packages --all-groups --frozen
uv run --frozen alembic upgrade head
uv run --frozen dm doctor
uv run --frozen dm --help
```

For macOS with Podman, configure `.env` with a host PostgreSQL URL using `127.0.0.1`, plus real
absolute `DM_SOURCE_ROOTS`, `DM_ASSET_ROOT`, and `DM_SCRATCH_ROOT` paths. A host-loopback gateway URL
works only for native Workbench execution; Compose uses `http://model-gateway:3000` internally.

## Verification

Focused unit tests do not require Compose. Integration tests create and remove an isolated
PostgreSQL database:

```bash
uv run --frozen pytest -q tests/unit tests/evals
uv run --frozen pytest -q packages/dungeon-engine/tests
make test-integration
```

Run the complete disposable containerized gate with:

```bash
make check
# or explicitly
CONTAINER_ENGINE=podman ./scripts/check-container.sh
```

Root and dungeon-package pytest suites run separately because they contain duplicate test basenames.

Health endpoints:

```bash
curl http://127.0.0.1:8000/health/live
curl http://127.0.0.1:8000/health/ready
curl -H 'Authorization: Bearer <DM_API_TOKEN>' http://127.0.0.1:8000/openapi.json
```

Only exact liveness/readiness and login routes bypass normal authentication as documented in the
architecture.

## Sources and Library

Compose uses separate managed campaign and rules source volumes, mounted read-only into Workbench.
Import a source tree deliberately; imports reject symlinks and atomically replace the managed tree:

```bash
make import-campaign-sources SOURCE="$HOME/Documents/my-campaign"
make import-rules-sources SOURCE="$HOME/Documents/my-authorized-rules"
```

Copying files does not make them canonical or indexed. Create immutable Library revisions through
the application boundary:

```bash
docker compose exec workbench dm library ingest notes/session-01.md --root root-0
docker compose exec workbench dm library ingest rules/hiding.md \
  --root root-1 --corpus global_rules --ruleset 5e2024
```

Re-importing or editing source never rewrites an existing revision or cited span.

## Model Gateway

The gateway is optional for deterministic Dungeon Studio work. Provider credentials never belong in
root `.env`; they are created by gateway-owned login and remain in its credential store.

Inspect providers and complete an explicit login when needed:

```bash
uv run --frozen dm model providers
uv run --frozen dm model login github-copilot
# or
uv run --frozen dm model login openai-codex
uv run --frozen dm model login-status <login-id>
```

The normal prompted flow resolves the active campaign owner, saved task profile, provider/model/
effort, title, and seed, then stores all resolved values in artifact lineage:

```bash
uv run --frozen dm dungeon prompt "A flooded archive beneath a lighthouse"
```

`--debug` emits a transient sensitive JSONL transcript to stderr; it is never routine logging and
must be used only for explicitly authorized local diagnosis. Live provider calls, canaries, and
retries are manual and opt-in. Always consult `PROJECT_STATUS.md` before making one.

The alpha structural tool accepts a compact `DungeonPlan`; deterministic code constructs graph edges,
IDs, topology certificate, exact geometry, maps, and readiness state. Puzzle, exploration, feature,
trap, objective, and narrative enrichment run as separate bounded exact-ID tasks. A failed enrichment
preserves the valid draft and leaves explicit blockers. Ordinary run inspection is body-free. Fail-closed model stops expose only an allowlisted
`abstention_code`, never provider text:

```bash
uv run --frozen dm dungeon run inspect <attempt-run-id>
```

Frozen Tier A evaluation artifacts start from a packaged case/seed and then advance through one
reproducibly pinned task at a time. The exact current parent is mandatory, and `--resume-run` accepts
only an unchanged failed wrapper:

```bash
uv run --frozen dm dungeon fixed-case-start tier_a_case_02 variant_01 \
  --provider openai-codex --model gpt-5.6-luna --effort fast
uv run --frozen dm dungeon fixed-case tier_a_case_02 variant_01 \
  <artifact-uuid> <current-version-uuid> \
  --provider openai-codex --model gpt-5.6-luna --effort fast
```

After the staged plan is complete, pass the ordered structural-then-task wrapper IDs to
`dm dungeon fixed-case-evidence` for a body-free measurement and separately blinded reviewer input.
Add `--review-packet <new-directory>` to atomically write only that input, the final DM guide, and
DM/player PNG maps for human review; assignment, provider, lineage, and run measurements are omitted.
These commands never approve preparation or write campaign canon.

Gateway-specific local operation and checks are documented in
[`model-gateway/README.md`](model-gateway/README.md).

## Provider-Independent Dungeon Studio

The same preparation workflow works with the gateway disabled:

```bash
uv run --frozen dm campaign create "Main Campaign"
uv run --frozen dm campaign use "Main Campaign"
uv run --frozen dm dungeon generate layout-request.json --title "Sunken Archive"
uv run --frozen dm dungeon inspect <artifact-uuid>
uv run --frozen dm dungeon compare <left-version> <right-version>
uv run --frozen dm dungeon regenerate <artifact-uuid> <parent-version> \
  --seed 888888 --lock room_entrance --summary "Regenerate unlocked geometry."
uv run --frozen dm dungeon export <version-uuid>
uv run --frozen dm dungeon approve <artifact-uuid> <version-uuid> \
  --reason "Reviewed for play."
```

Authenticated `/api/dungeons` routes and the browser call the same application services. Dungeon
Studio supports version inspection, comparison, deterministic regeneration with locks, DM/player
previews, asset downloads, and explicit preparation approval.

`approved_for_play` is preparation state only. It does not establish that any planned event occurred.

The pure package can also run independently:

```bash
uv run dm-dungeon validate packages/dungeon-engine/tests/fixtures/sunken_archive.v1.json
uv run dm-dungeon schema
```

See [`packages/dungeon-engine/README.md`](packages/dungeon-engine/README.md) for package commands and
[`packages/dungeon-engine/src/dm_dungeon/validation/TOPOLOGY_MATH.md`](packages/dungeon-engine/src/dm_dungeon/validation/TOPOLOGY_MATH.md)
for the graph/progression proof boundary.

## Synthetic Dungeon Review

Generate the fixed provider-free quality packet with:

```bash
make dungeon-review-packet
```

The ignored packet contains synthetic DM/player maps, keyed guide, manifest, automated rubric, and a
blank human worksheet. It is a renderer, secrecy, and contract regression—not a campaign artifact or
proof that live generation quality generalizes. Completing the worksheet records evidence only; it
cannot approve preparation or write canon.

## License and Third-Party Marks

Copyright (C) 2026 Reese Wilson.

Original code and documentation are licensed under the GNU Affero General Public License version 3.0
only; see [`LICENSE`](LICENSE). Third-party dependencies and named platforms retain their own terms.

This repository contains no proprietary game-rule text, published adventures, artwork, real character
data, or provider credentials/responses. Dungeons & Dragons, D&D, and Roll20 are trademarks of their
respective owners; descriptive use implies no affiliation.
