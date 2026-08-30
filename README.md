# DM Assistant Harness

A self-hosted, AI-assisted dungeon/encounter generator, campaign memory, and context compiler for a human Dungeon Master running D&D 5e/2024-era campaigns.

The project is in early implementation. The Python 3.12 Workbench, provider-independent Dungeon Studio, deterministic dungeon/export kernel, PostgreSQL preparation lifecycle, and immutable allowlisted Library source registry are in place.

## Start Here

For a first-time architecture review:

1. [`dm-assistant-project-goals.md`](dm-assistant-project-goals.md) — product goals and boundaries.
2. [`dm-assistant-technical-architecture.md`](dm-assistant-technical-architecture.md) — architecture, data semantics, and accepted decisions.
3. [`dm-assistant-implementation-plan.md`](dm-assistant-implementation-plan.md) — phased tasks and acceptance gates.

For an implementation session or return after a break, conserve context:

1. Run `git status`.
2. Read [`PROJECT_STATUS.md`](PROJECT_STATUS.md) — the live handoff and next exact task.
3. Read [`AGENTS.md`](AGENTS.md).
4. Read only the current task/phase and relevant architecture sections, not every planning document again.

## Architectural Summary

- One Python/FastAPI DM Workbench modular monolith plus a narrow private Node model-gateway process.
- One independently packaged pure `dm_dungeon` kernel loaded in the Python process; it has no database, UI, retrieval, or model-runtime dependency.
- The gateway uses pinned `@earendil-works/pi-ai` for provider OAuth/API-key auth, model catalogs, streaming, tool-call transport, and reasoning controls.
- A first-party thin web UI is the normal conversational/review interface; the Typer CLI remains the automation, administration, and recovery interface.
- One PostgreSQL database with pgvector; embeddings use a separate Python-side runtime because `pi-ai` does not provide embeddings.
- Immutable, versioned campaign/rules source documents.
- Hybrid lexical and semantic retrieval.
- Perspective-aware, provenance-aware campaign state.
- Seeded dungeon generation: Workbench/model-authored intent compiled by the deterministic `dm_dungeon` topology, geometry, validation, rendering, and export package.
- Practical grids rendered through deterministic SVG, exported as DM/clean PNG, low-ink stitchable one-inch-scale PDF, and Roll20-compatible images/metadata.
- Party/playstyle-aware combat and noncombat encounters with complete creature statistics. Encounter orchestration starts in the Workbench; only a proven deterministic `encounter-mechanics` seam may be extracted later.
- Models create proposals/preparation drafts; only the DM approves artifacts or commits canon.
- PostgreSQL stores canonical revision history, artifact lineage, and readable change summaries.
- Generation runs share a small scope/provenance envelope but use separate strict payloads such as `DungeonGenerationContext` and `EncounterGenerationContext`; there is no universal all-purpose generation payload.
- The web shell is organized into Library, Chronicle, Dungeon/Encounter Studios, Session Desk, Assistant, and Settings while retaining separate preparation-approval and canonical-commit workflows.
- DM-only interface initially, including supplied character sheets and important story items.

## Isolated Development

Project dependencies are installed only in a container-managed project virtual environment. The full-stack Make workflow creates the ignored `.env` automatically and generates distinct persistent database, API, session-signing, and Workbench-to-gateway secrets with `openssl` (or Python's `secrets` fallback). No provider credential is generated or stored there; provider OAuth remains in the dedicated gateway volume.

### Two supported workflows

Use native processes for the rapid edit/test loop. Compose supplies only
PostgreSQL in that mode, so Python and Node changes are immediately visible:

```bash
make dev-db
make dev-api
# In another terminal, after exporting the shared gateway token:
make dev-gateway
```

`make dev-api` enables Uvicorn reload. Unit tests and most focused tests do not
need Compose. `make test-integration` starts an isolated pgvector PostgreSQL on
an automatically assigned loopback port, runs the integration suite, and removes
the container even on failure. It does not use or modify the persistent development
database. Pass a focused pytest path with, for example,
`make test-integration PYTEST_ARGS=tests/integration/test_dungeon_studio_web_prompt.py`.
All repository tests ignore the developer-local `.env` and provide synthetic
settings explicitly, so an enabled native gateway cannot change test behavior.
`make check` runs the larger disposable containerized quality gate. The Makefile
auto-selects Docker when `docker` is installed and otherwise uses Podman;
`CONTAINER_ENGINE=...` remains an explicit override.

Use the same repository to test the complete deployable topology locally and to install it on a Proxmox VM. On a Mac with Docker Desktop, first run is:

```bash
make stack-up
make stack-smoke
```

`make stack-up` runs an idempotent bootstrap before Compose. It creates `.env` with mode `0600`, generates only missing/placeholder local secrets, preserves them across restarts, builds the images, and starts PostgreSQL, the private model gateway, and Workbench. Use `make stack-token` when the browser/API login token is needed. Direct `docker compose up` remains a lower-level command and expects bootstrap to have run first (`make bootstrap`).

Only the Workbench is published, on `127.0.0.1:8000`; the gateway has no host port and is reachable solely as `model-gateway:3000` on the private Compose network. Empty campaign/rules source volumes, database data, gateway credentials, and generated assets are all managed named volumes, so no host directories are required. The asset volume contains separate asset and scratch subdirectories so atomic no-overwrite hard-link publication never crosses a container mount boundary. The source volumes are mounted read-only in Workbench. The Workbench startup performs its Alembic upgrade before becoming ready; use one Workbench replica and take a database backup before deploying migrations.

To copy an existing source tree into a managed volume deliberately, use an explicit import target. Imports reject symlinks and atomically replace that source volume's current tree:

```bash
make import-campaign-sources SOURCE="$HOME/Documents/my-campaign"
make import-rules-sources SOURCE="$HOME/Documents/my-authorized-rules"
```

Copying files does not silently make them canonical or indexed. Create immutable Library revisions explicitly, for example:

```bash
docker compose exec workbench dm library ingest notes/session-01.md --root root-0
docker compose exec workbench dm library ingest rules/hiding.md \
  --root root-1 --corpus global_rules --ruleset 5e2024
```

Campaign Library ingestion uses the active campaign when `--campaign` is omitted. Re-importing a source volume never rewrites existing immutable revisions; a subsequent Library ingestion records/reconciles new source state through the normal service boundary.

The default Compose limits reserve a modest two vCPU and 2.25 GB RAM ceiling
across PostgreSQL, Workbench, and gateway. Override the documented
`DM_*_CPU_LIMIT` and `DM_*_MEMORY_LIMIT` values in `.env` only after measuring
the selected embedding/runtime workload on the Proxmox host.

### macOS native workflow

To run the Python Workbench and the loopback-only model gateway on one Mac, use
native `uv`/Node processes and Podman only for PostgreSQL:

```bash
brew install uv node podman
podman machine init
podman machine start
```

Set `DM_DATABASE_URL` in `.env` to the host-published PostgreSQL address
(`127.0.0.1`, not the Compose service hostname), and set
`DM_SOURCE_ROOTS`, `DM_ASSET_ROOT`, and `DM_SCRATCH_ROOT` to real absolute
macOS paths. Then start PostgreSQL, install the pinned Python dependencies,
migrate, and launch the private-only API:

```bash
podman compose up -d postgres
uv sync --all-packages --all-groups --frozen
uv run --frozen alembic upgrade head
uv run --frozen dm doctor
uv run --frozen uvicorn dm_assistant.api.app:create_app \
  --factory --host 127.0.0.1 --port 8000
```

The containerized API command below remains useful when model support is
disabled. A gateway at host `127.0.0.1` is not reachable from that container;
run the gateway in the same private network instead, or use the native workflow
above.

For the full Compose stack, do not use a host-loopback gateway URL. Compose injects `http://model-gateway:3000` into the Workbench and keeps the gateway unpublished. `make stack-down` stops the stack without deleting persistent volumes. `make stack-up` normally auto-selects Docker Desktop; use `CONTAINER_ENGINE=docker make stack-up` only to override detection explicitly.

Start the pinned PostgreSQL 16/pgvector service, migrate, and run the API on the private Compose network:

```bash
cp .env.example .env
podman compose up -d postgres
podman run --rm -it \
  --network dm-assistant_default \
  -p 127.0.0.1:8000:8000 \
  -e UV_LINK_MODE=copy \
  -v "$PWD:/workspace" \
  -v dm-assistant-dev-venv:/workspace/.venv \
  -w /workspace \
  ghcr.io/astral-sh/uv:0.9.5-python3.12-bookworm-slim \
  sh -lc 'uv sync --all-packages --all-groups --frozen && \
    uv run --frozen alembic upgrade head && \
    uv run --frozen dm doctor && \
    exec uv run --frozen uvicorn dm_assistant.api.app:create_app \
      --factory --host 0.0.0.0 --port 8000'
```

Liveness has no database dependency; readiness verifies PostgreSQL 16, pgvector 0.8.1, and exact Alembic head. Every other path—including docs/schema—is authenticated:

```bash
curl http://127.0.0.1:8000/health/live
curl http://127.0.0.1:8000/health/ready
curl -H 'Authorization: Bearer <DM_API_TOKEN>' \
  http://127.0.0.1:8000/openapi.json
```

Run the complete frozen gate—including a disposable safety-named test database, migration round trip, `dm doctor`, all tests, lint, formatting, mypy, and diff checks—with one command. It removes its database volume/network even on failure:

```bash
./scripts/check-container.sh
# Docker alternative:
CONTAINER_ENGINE=docker ./scripts/check-container.sh
```

Stop the development database with `podman compose down`; add `-v` only when intentionally deleting local development data.

## Private Model Gateway

For full Compose, `make bootstrap` generates `DM_MODEL_GATEWAY_INTERNAL_TOKEN` once and stores it in the ignored mode-`0600` `.env`. Compose injects the same bearer secret into Workbench (caller) and the private gateway (verifier); it is defense-in-depth authentication for Python-to-gateway HTTP, not an OpenAI credential. OpenAI OAuth access/refresh credentials are created only by provider login and remain in the separate gateway credential volume. The bootstrap also generates distinct PostgreSQL, browser/API, and session-signing secrets because those protect different boundaries; users do not need to choose or synchronize any of them manually.

The model gateway is a separate Node 22.19+ private process. The commented gateway values in `.env.example` describe advanced native/model-disabled operation; Compose explicitly enables its private gateway and consumes the generated internal token. Leave `DM_MODEL_GATEWAY_POLICY=disabled` in a native setup to use the fully model-independent Studio. To enable the native backend model client without Compose, set the following in the ignored root `.env`, using one shared token:

```dotenv
DM_MODEL_GATEWAY_POLICY=optional
DM_MODEL_GATEWAY_URL=http://127.0.0.1:3000
DM_MODEL_GATEWAY_INTERNAL_TOKEN=<32+-character-random-token>
```

Start the gateway with the same token; provider credentials remain only in its
dedicated credential file:

```bash
cd model-gateway
npm ci
export DM_MODEL_GATEWAY_INTERNAL_TOKEN='<same token as .env>'
export MODEL_GATEWAY_CREDENTIAL_PATH="$HOME/.local/share/dm-model-gateway/credentials.json"
npm run build
npm start
```

Verify the private boundary without a provider credential:

```bash
curl -H "Authorization: Bearer $DM_MODEL_GATEWAY_INTERNAL_TOKEN" \
  http://127.0.0.1:3000/health
```

P7-10a exposes the headless private-gateway path. With the native workflow,
run these commands directly; with the full Compose stack, prefix each command
with `podman compose exec workbench` (or `docker compose exec workbench`). First
inspect the allowlisted providers and models:

```bash
uv run --frozen dm model providers
```

The faux provider is intended for scripted automated contracts; its default
response is not a complete dungeon design. GitHub Copilot and OpenAI Codex are
available as subscription OAuth providers. On first model-required use, the CLI
asks once when multiple unauthenticated subscription providers are available;
the successful selection is saved per task. Provider credentials remain in the
gateway credential volume. A provider can also be selected explicitly:

```bash
uv run --frozen dm model login github-copilot
# or
uv run --frozen dm model login openai-codex
uv run --frozen dm model login-status <login-id>
# Only when a returned non-secret prompt event requests a response:
uv run --frozen dm model login-respond <login-id> <prompt-id>
uv run --frozen dm model providers
```

Ordinarily the prompt command handles these defaults itself: it creates an
empty `My Campaign` ownership workspace when none exists, uses the active
campaign, reuses a saved task-specific provider/model/effort selection, starts
and polls OAuth when login is required, generates and pins a seed, and persists
the validated model-authored brief title. The normal command is therefore:

```bash
uv run --frozen dm dungeon prompt \
  "A flooded archive beneath a lighthouse"
```

Add `--debug` to stream the complete request, normalized gateway events, model
submissions, and deterministic harness tool results as JSON Lines on stderr in
real time. This explicit terminal-only transcript is not logged or persisted;
treat it as sensitive because it includes the model context and response.

The first OAuth flow prints device-code instructions and resumes the original
prompt after login completes. Provider/model/effort, campaign, seed, and title
flags remain inspectable reproducibility overrides. Campaign roots can be
created and switched without copying UUIDs into every command:

### Alpha dungeon V1 evaluation

The alpha accepts one compact `submit_dungeon_plan` proposal only. Proposal fields
(`proposal_version`, `plan`, and optional guide content) are the tool arguments directly;
there is no additional `proposal` wrapper. Models supply a bounded `DungeonPlan`: 4–8
relative rooms, one critical path, up to two branches, one loop, one gate, and bounded
room content. Deterministic code constructs all
edges and IDs and emits an independently recomputed `TopologyCertificate` covering
connectivity, cycle/branch/gate/secret witnesses, room/port demand, and embedding
bands. Geometry, visibility, validation, rendering, persistence, and approval
remain server-owned. Run inspection remains body-free:

```bash
uv run --frozen dm dungeon run inspect <attempt-run-id>
```

When both the initial structured submission and its one repair are rejected, the CLI
prints the durable attempt UUID and the inspection command. The attempt report records
each attempt's safe stage plus bounded server-authored diagnostic codes, JSON paths, and
repair hints. It never stores the prompt, submitted proposal, provider response, or
reasoning. Measured output or total request usage above the pinned token ceiling also
fails before publication and stores only safe counts/limit kind. Before the one repair,
the Workbench estimates its complete canonical message and tool-schema input and skips it
when the measured remaining budget cannot fit that input. Use transient `--debug` capture
only when sensitive bodies are explicitly needed for local diagnosis.

The current live canary is a committed one-floor Tier A prompt with seed `714000001`,
exposed only through `dm dungeon canary`; provider and model must be explicit. Do not run
it until the human guide review and provider-free Tier B/C gates pass. For the known
non-production Codex transport limitation, one operator may explicitly acknowledge that
the requested output cap is advisory:

```bash
uv run --frozen dm dungeon canary \
  --provider openai-codex \
  --model <contract-tested-model-id> \
  --acknowledge-advisory-output-cap
```

That flag is rejected for ordinary prompts, other providers, or production. It does not
raise or disable the 12,000 measured-token cumulative publication ceiling, repair-input
reservation, validation, secrecy, or atomic-publication gates. The attempt report and any
accepted model lineage record the canary ID and policy. Stop after this one attempt on
success or failure; post-response checks cannot recover provider tokens already consumed.

The frozen provider-free V1 suite is synthetic and safe for CI:

```bash
uv run --frozen pytest -q tests/evals/test_dungeon_evals.py
```

Generate the fixed synthetic human DM quality-review packet without PostgreSQL or a
model provider:

```bash
make dungeon-review-packet
open generated/dungeon-guide-review/dm-map.png
open generated/dungeon-guide-review/dm-guide.md
open generated/dungeon-guide-review/review-worksheet.md
```

The ignored packet contains DM/player maps, the exact keyed guide, its typed runnable
content input, automated rubric, reproducibility manifest, and a blank human worksheet.
The concise Markdown guide uses entry-first sequential presentation numbers while
preserving exact map callouts. It gives every room read-aloud material and groups only
actionable door state, checks, clues, triggers, consequences, challenges, features,
puzzles, and objectives in that room; ordinary map-visible connectivity and separate
sensory/purpose repetition are omitted. Each runnable gate dependency, scene pressure,
puzzle, feature, and objective includes a situation, adjudication guidance, and bounded
player choice/outcome pairs. Read-aloud is limited to what players can observe; hidden
mechanics stay in DM adjudication. Runnable interactions use concrete physical setups,
triggers, effects, recovery, and repeated-failure outcomes, and cross-room alarms state
both their shared state and whether anything responds.
The DM map includes visible
corridor boundaries, collision-tested mechanics badges, and a compact symbol key.
Player output defaults to geometry only: no room/door/feature keys, objective, start, or
encounter markers; visible ordinary doors use a heavy slab line rather than blending
into the light grid, and explicitly player-safe physical features retain only their
unlabelled shape. The single entrance is projected on the DM map as a distinct start flag; other
technical pathfinding anchors stay in package
lineage and optional VTT metadata rather than appearing as unexplained map glyphs.
Generation fails when the
output directory already exists so a completed worksheet is not overwritten; use
`REVIEW_OUTPUT=generated/<another-name>` for another review. Completing the worksheet
records quality evidence only—it does not approve preparation or write campaign canon.

This packet is a development quality gate, not a campaign-content feature or final
product format. It holds one synthetic prompt and seed constant so a DM can judge the
whole prompt-to-draft result—map readability, player secrecy, progression, clues, and
whether the guide is runnable without improvising missing material. The worksheet turns
subjective table-readiness feedback into concrete corrections; automated regressions then
preserve the objective parts of those corrections. A passing packet demonstrates that it
is worth moving on to harder topology stress cases and eventually live-model canaries. It
does not prove every future dungeon is good, and it is not intended to become a library
of authored adventures.

Live small-model runs remain paused until the provider-free and faux Tier A
gates pass. The alpha retains no compatibility readers for disposable prior
generation contracts.

```bash
uv run --frozen dm campaign create "Main Campaign"
uv run --frozen dm campaign use "Main Campaign"
uv run --frozen dm campaign list
```

The standalone prompt selects no campaign revision, corpus, rules profile, or
retrieval context yet; automatic bounded active-campaign grounding is a later
explicit architecture update.

Live OAuth/model checks are manual and opt-in. Verify the selected account and
subscription permit the intended endpoint and workload. Automated checks use
only synthetic responses:

```bash
uv run pytest -q tests/unit/test_model_gateway_client.py \
  tests/unit/test_prompted_dungeon_workflow.py
npm --prefix model-gateway run check
npm --prefix model-gateway test
```

## Provider-Independent Dungeon Studio

After migration, the first prompt/list operation creates an empty `My Campaign` ownership root when needed; create or switch named roots with `dm campaign create` / `dm campaign use`. Then log in at `http://127.0.0.1:8000/login` with `DM_API_TOKEN`. The signed browser session contains no API token; all browser writes require CSRF. Dungeon Studio can ingest a versioned `LayoutRequest` JSON, generate and validate exact geometry, inspect run/input/version lineage, compare/regenerate with locks, preview DM/player maps, create PDF/Roll20 exports, download assets, and explicitly approve preparation for play without a model gateway.

The same application workflow is available through authenticated `/api/dungeons` routes and CLI commands:

```bash
uv run --frozen dm dungeon generate /data/campaign/layout-request.json \
  --campaign <campaign-uuid> --title "Sunken Archive"
uv run --frozen dm dungeon inspect <artifact-uuid> --campaign <campaign-uuid>
uv run --frozen dm dungeon compare <left-version> <right-version> \
  --campaign <campaign-uuid>
uv run --frozen dm dungeon regenerate <artifact-uuid> <parent-version> \
  --campaign <campaign-uuid> --seed 888888 --lock room_entrance \
  --summary "Regenerate unlocked geometry."
uv run --frozen dm dungeon export <version-uuid> --campaign <campaign-uuid>
uv run --frozen dm dungeon approve <artifact-uuid> <version-uuid> \
  --campaign <campaign-uuid> --reason "Reviewed for play."
```

`approved_for_play` is preparation state only. It does not make planned encounters, discoveries, deaths, treasure, or any other event canonical.

## Immutable Library Foundation

Alembic revision `0003_library_sources` defines campaign/global-rules source scopes, stable logical documents and safe relative path history, exact immutable UTF-8 revisions with verified SHA-256 identity, typed authority/document/ruleset/visibility metadata, exact-span chunks with PostgreSQL full-text vectors, terminal ingestion-run pins, and candidate/active corpus snapshots. Database guards reject cross-scope membership, broader child visibility, source/chunk mutation, and membership changes after activation.

The internal P1-02 Library service now ingests bounded strict-UTF-8 files through named allowlisted roots, rejects traversal/symlinks/non-files, reuses unchanged revisions, appends novel edits, retains identity across exact moves, records explicit duplicates, returns review-required ambiguity without mutation, and retires missing files only through an explicit reconciliation call. Public CLI/API ingestion remains deferred to P1-06; no Markdown parser, chunks, search, embeddings, model calls, or canonical writes are involved yet.

## Current Next Step

Continue **P7-14e** with human DM review of the regenerated fixed Tier A packet after the physical-causality correction. If every quality dimension and player secrecy pass, record the evidence and begin provider-free Tier B/C stress-ladder design; otherwise make only the next bounded fixture/renderer correction. Keep live canaries paused. See [`dungeon-generation-recovery-plan.md`](dungeon-generation-recovery-plan.md) and [`PROJECT_STATUS.md`](PROJECT_STATUS.md) for the exact resumable action.

## License and Third-Party Marks

Copyright (C) 2026 Reese Wilson.

Except where otherwise noted, original code and documentation in this repository
are licensed under the [GNU Affero General Public License version 3.0
only](LICENSE). Third-party dependencies and referenced platforms remain subject
to their own licenses and terms.

This repository does not include proprietary game-rule text, published
adventures, artwork, maps, or character data. Users are responsible for having
the rights to any content they import.

Dungeons & Dragons, D&D, and Roll20 are trademarks of their respective owners.
Their descriptive use does not imply affiliation, sponsorship, or endorsement.
