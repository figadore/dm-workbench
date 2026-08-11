"""Deterministic grid-on/gridless PNG export tests."""

import hashlib
import io
from pathlib import Path

import pytest
from PIL import Image

from dm_dungeon import DungeonPackage, to_canonical_json
from dm_dungeon.export import (
    ExportDiagnosticCode,
    PngExportRequest,
    export_png,
    write_png_artifact,
)
from dm_dungeon.rendering import RenderAudience

GOLDEN_ROOT = Path(__file__).parent / "golden"


def png_request(
    package: DungeonPackage,
    audience: RenderAudience = RenderAudience.PLAYER,
    include_grid: bool = True,
) -> PngExportRequest:
    return PngExportRequest(
        schema_version="1.0.0",
        package_id=package.id,
        floor_id="floor_upper",
        audience=audience,
        pixels_per_cell=20,
        dpi=140,
        include_grid=include_grid,
        show_labels=True,
        show_markers=True,
    )


def test_png_export_is_deterministic_and_manifest_hashes_bytes(
    synthetic_package: DungeonPackage,
) -> None:
    request = png_request(synthetic_package)

    first = export_png(synthetic_package, request)
    second = export_png(synthetic_package, request)

    assert first.result.success is True
    assert first.data is not None
    assert first == second
    assert first.result.manifest is not None
    manifest = first.result.manifest
    assert manifest.asset_sha256 == hashlib.sha256(first.data).hexdigest()
    assert manifest.width_pixels == 420
    assert manifest.height_pixels == 240
    assert manifest.pixels_per_cell == 20
    assert manifest.dpi == 140
    assert manifest.ink_coverage_basis_points < 3500

    with Image.open(io.BytesIO(first.data)) as image:
        assert image.size == (420, 240)
        assert image.mode == "RGB"
        assert image.info["dpi"][0] == pytest.approx(140, abs=0.1)


def test_grid_on_and_gridless_png_keep_dimensions_but_change_pixels(
    synthetic_package: DungeonPackage,
) -> None:
    grid_on = export_png(
        synthetic_package, png_request(synthetic_package, include_grid=True)
    )
    gridless = export_png(
        synthetic_package,
        png_request(synthetic_package, include_grid=False),
    )

    assert grid_on.data is not None
    assert gridless.data is not None
    assert grid_on.data != gridless.data
    assert grid_on.result.manifest is not None
    assert gridless.result.manifest is not None
    assert (
        grid_on.result.manifest.width_pixels,
        grid_on.result.manifest.height_pixels,
    ) == (
        gridless.result.manifest.width_pixels,
        gridless.result.manifest.height_pixels,
    )
    assert gridless.result.manifest.ink_coverage_basis_points < (
        grid_on.result.manifest.ink_coverage_basis_points
    )


def test_png_player_manifest_omits_dm_only_components(
    synthetic_package: DungeonPackage,
) -> None:
    player = export_png(synthetic_package, png_request(synthetic_package))
    dm = export_png(
        synthetic_package,
        png_request(synthetic_package, audience=RenderAudience.DM),
    )
    assert player.result.manifest is not None
    assert dm.result.manifest is not None

    hidden_ids = {
        "room_vault",
        "connection_vault_secret",
        "corridor_vault_secret",
        "label_secret_vault",
    }
    assert hidden_ids.isdisjoint(player.result.manifest.rendered_component_ids)
    assert hidden_ids <= set(dm.result.manifest.rendered_component_ids)
    assert player.data is not None
    assert b"room_vault" not in player.data


def test_png_matches_golden_grid_variants(synthetic_package: DungeonPackage) -> None:
    for include_grid, suffix in ((True, "grid"), (False, "gridless")):
        artifact = export_png(
            synthetic_package,
            png_request(synthetic_package, include_grid=include_grid),
        )
        assert artifact.data is not None
        golden = (
            GOLDEN_ROOT / f"sunken_archive.upper.player.{suffix}.png"
        ).read_bytes()
        assert artifact.data == golden


def test_png_ink_budget_fails_without_partial_asset(
    synthetic_package: DungeonPackage,
) -> None:
    request = png_request(synthetic_package).model_copy(
        update={"maximum_ink_coverage_basis_points": 1}
    )

    artifact = export_png(synthetic_package, request)

    assert artifact.result.success is False
    assert artifact.data is None
    assert {item.code for item in artifact.result.diagnostics} == {
        ExportDiagnosticCode.INK_BUDGET_EXCEEDED
    }


def test_png_file_adapter_writes_bytes_and_canonical_manifest(
    synthetic_package: DungeonPackage,
    tmp_path: Path,
) -> None:
    artifact = export_png(synthetic_package, png_request(synthetic_package))
    asset_path = tmp_path / "map.png"
    manifest_path = tmp_path / "map.png.json"

    write_png_artifact(asset_path, manifest_path, artifact)

    assert artifact.data is not None
    assert artifact.result.manifest is not None
    assert asset_path.read_bytes() == artifact.data
    assert manifest_path.read_text(encoding="utf-8") == to_canonical_json(
        artifact.result.manifest
    )
