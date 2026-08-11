# dm-dungeon

`dm-dungeon` is the pure, in-process dungeon contract and deterministic-mechanics boundary for the DM Assistant Workbench. It has no Workbench, web, database, retrieval, repository, or model-provider dependency.

From the workspace root, validate the synthetic package or emit its canonical JSON:

```bash
uv run dm-dungeon validate packages/dungeon-engine/tests/fixtures/sunken_archive.v1.json
uv run dm-dungeon canonicalize packages/dungeon-engine/tests/fixtures/sunken_archive.v1.json
uv run dm-dungeon schema
```

A versioned `LayoutRequest` can be generated through the file adapter without the Workbench:

```bash
uv run dm-dungeon layout layout-request.json --output layout-result.json
```

The `orthogonal-v1` baseline validates topology, places size-constrained non-overlapping rectangles per floor, routes orthogonal corridors and aligned doors, emits paired floor transitions, and returns an all-or-nothing structured result. Identical pinned requests are byte-equivalent; targeted regeneration passes exact components in `locked`.

`dm-dungeon validate` checks the schema, topology, and exact geometry. Python callers can use `validate_geometry`, `find_anchor_path`, and `evaluate_encounter_fit` for structured repair diagnostics, footprint-aware shortest paths, and conservative room-space/range/cover/objective measurements. These mechanics remain campaign-, provider-, and rules-agnostic.

Render a validated floor with a code-owned theme:

```bash
uv run dm-dungeon render-svg package.json \
  --floor floor_upper --audience player --output floor-upper.player.svg
```

DM/player visibility and layer policy are applied before XML construction. Filtered components never appear as hidden SVG elements or metadata.

Export raster and exact-scale print assets with canonical manifests:

```bash
uv run dm-dungeon export-png package.json \
  --floor floor_upper --audience player \
  --output floor.png --manifest floor.png.json
uv run dm-dungeon export-pdf package.json \
  --floor floor_upper --audience player \
  --output floor.pdf --manifest floor.pdf.json
```

Pillow is the minimal deterministic raster dependency. ReportLab's invariant vector canvas writes tiled PDFs directly at 72 points per five-foot cell; `pypdf` is used only by tests to inspect page boxes, metadata, calibration, and secrecy. No Cairo/system raster dependency is required.

Create a Roll20-compatible setup bundle (paired grid/gridless PNGs plus canonical manifest):

```bash
uv run dm-dungeon export-roll20 package.json \
  --floor floor_upper --audience player --prefix archive-upper \
  --output archive-upper.zip --directory roll20-files
```

The manifest pins grid dimensions, pixels per cell, five-foot scale, zero origin, asset hashes/dimensions, visible wall/door geometry, and optional visible anchor placements. It deliberately provides neither API upload nor dynamic-lighting import. Player bundles contain no DM-only records or full-source hash; changing hidden metadata leaves their bytes unchanged.

Run its independent tests and quality gates with:

```bash
uv run pytest packages/dungeon-engine/tests
uv run ruff check packages/dungeon-engine
uv run ruff format --check packages/dungeon-engine
uv run mypy packages/dungeon-engine/src
```

All fixtures are synthetic. The package accepts versioned typed inputs and owns no campaign state or preparation lifecycle.

## License

Copyright (C) 2026 Reese Wilson. This package is licensed under the GNU Affero
General Public License version 3.0 only. See [`LICENSE`](LICENSE).
