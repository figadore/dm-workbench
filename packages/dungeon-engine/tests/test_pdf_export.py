"""Exact-scale low-ink tiled PDF export tests."""

import hashlib
import io
from pathlib import Path

from pypdf import PdfReader

from dm_dungeon import DungeonPackage, to_canonical_json
from dm_dungeon.export import (
    AssemblyMode,
    ExportDiagnosticCode,
    PaperSize,
    PdfExportRequest,
    export_pdf,
    write_pdf_artifact,
)
from dm_dungeon.rendering import RenderAudience


def pdf_request(
    package: DungeonPackage,
    audience: RenderAudience = RenderAudience.PLAYER,
) -> PdfExportRequest:
    return PdfExportRequest(
        schema_version="1.0.0",
        package_id=package.id,
        floor_id="floor_upper",
        audience=audience,
        paper_size=PaperSize.LETTER,
        assembly_mode=AssemblyMode.OVERLAP_AND_TAPE,
        margin_points=36,
        overlap_points=18,
        include_overview=True,
        include_grid=True,
        show_labels=True,
        show_markers=True,
    )


def test_pdf_export_is_deterministic_and_manifest_hashes_bytes(
    synthetic_package: DungeonPackage,
) -> None:
    request = pdf_request(synthetic_package)

    first = export_pdf(synthetic_package, request)
    second = export_pdf(synthetic_package, request)

    assert first.result.success is True
    assert first.data is not None
    assert first == second
    assert first.result.manifest is not None
    manifest = first.result.manifest
    assert manifest.asset_sha256 == hashlib.sha256(first.data).hexdigest()
    assert manifest.cell_scale_points == 72
    assert manifest.calibration_square_points == 72
    assert manifest.map_width_points == 20 * 72
    assert manifest.map_height_points == 20 * 72
    assert manifest.tile_rows == 3
    assert manifest.tile_columns == 3
    assert manifest.page_count == 10
    assert manifest.ink_coverage_basis_points < 3500


def test_pdf_media_crop_boxes_page_count_and_invariant_metadata(
    synthetic_package: DungeonPackage,
) -> None:
    artifact = export_pdf(synthetic_package, pdf_request(synthetic_package))
    assert artifact.data is not None
    assert artifact.result.manifest is not None
    reader = PdfReader(io.BytesIO(artifact.data))

    assert len(reader.pages) == artifact.result.manifest.page_count
    for page in reader.pages:
        assert tuple(float(item) for item in page.mediabox) == (0.0, 0.0, 612.0, 792.0)
        assert tuple(float(item) for item in page.cropbox) == (0.0, 0.0, 612.0, 792.0)
    assert reader.metadata is not None
    assert reader.metadata.title == "Dungeon print pkg_sunken_archive floor_upper"
    assert reader.metadata.creator == "dm-dungeon pdf-v1"
    assert reader.metadata.creation_date.year == 2000


def test_pdf_tiles_stitch_with_exact_requested_overlap(
    synthetic_package: DungeonPackage,
) -> None:
    artifact = export_pdf(synthetic_package, pdf_request(synthetic_package))
    assert artifact.result.manifest is not None
    manifest = artifact.result.manifest
    tiles = {(tile.row, tile.column): tile for tile in manifest.tiles}

    for tile in manifest.tiles:
        if tile.column + 1 < manifest.tile_columns:
            right = tiles[(tile.row, tile.column + 1)]
            assert right.source_x_points == (
                tile.source_x_points
                + tile.viewport_width_points
                - tile.overlap_right_points
            )
            assert tile.overlap_right_points == 18
            assert right.overlap_left_points == 18
        if tile.row + 1 < manifest.tile_rows:
            below = tiles[(tile.row + 1, tile.column)]
            assert below.source_y_points == (
                tile.source_y_points
                + tile.viewport_height_points
                - tile.overlap_bottom_points
            )
            assert tile.overlap_bottom_points == 18
            assert below.overlap_top_points == 18


def test_pdf_tile_pages_contain_calibration_and_actual_size_instructions(
    synthetic_package: DungeonPackage,
) -> None:
    artifact = export_pdf(synthetic_package, pdf_request(synthetic_package))
    assert artifact.data is not None
    reader = PdfReader(io.BytesIO(artifact.data))

    overview_text = reader.pages[0].extract_text()
    assert "ASSEMBLY OVERVIEW" in overview_text
    assert "NOT TO SCALE" in overview_text
    tile_text = reader.pages[1].extract_text()
    assert "Print at 100% / Actual Size" in tile_text
    assert "1 inch / one 5-foot cell" in tile_text
    content = reader.pages[1].get_contents().get_data()
    assert b"72 72 re" in content
    assert b"1 0 0 -1" in content


def test_a4_trim_and_butt_has_no_overlap_and_no_overview(
    synthetic_package: DungeonPackage,
) -> None:
    request = pdf_request(synthetic_package).model_copy(
        update={
            "paper_size": PaperSize.A4,
            "assembly_mode": AssemblyMode.TRIM_AND_BUTT,
            "overlap_points": 0,
            "include_overview": False,
        }
    )

    artifact = export_pdf(synthetic_package, request)

    assert artifact.data is not None
    assert artifact.result.manifest is not None
    manifest = artifact.result.manifest
    assert manifest.page_count == len(manifest.tiles)
    assert all(
        tile.overlap_left_points
        == tile.overlap_right_points
        == tile.overlap_top_points
        == tile.overlap_bottom_points
        == 0
        for tile in manifest.tiles
    )
    reader = PdfReader(io.BytesIO(artifact.data))
    assert tuple(float(item) for item in reader.pages[0].mediabox) == (
        0.0,
        0.0,
        595.0,
        842.0,
    )


def test_player_pdf_and_manifest_omit_dm_only_content(
    synthetic_package: DungeonPackage,
) -> None:
    player = export_pdf(synthetic_package, pdf_request(synthetic_package))
    dm = export_pdf(
        synthetic_package,
        pdf_request(synthetic_package, audience=RenderAudience.DM),
    )
    assert player.data is not None
    assert dm.data is not None
    assert player.result.manifest is not None
    assert dm.result.manifest is not None

    hidden_ids = {
        "room_vault",
        "connection_vault_secret_mechanics",
        "connection_secret_ladder",
    }
    assert hidden_ids.isdisjoint(player.result.manifest.rendered_component_ids)
    assert hidden_ids <= set(dm.result.manifest.rendered_component_ids)

    player_text = "\n".join(
        page.extract_text() or "" for page in PdfReader(io.BytesIO(player.data)).pages
    )
    dm_text = "\n".join(
        page.extract_text() or "" for page in PdfReader(io.BytesIO(dm.data)).pages
    )
    assert "Secret Index Vault" not in player_text
    assert "room_vault" not in player_text
    assert dm_text != player_text


def test_pdf_ink_budget_fails_without_partial_asset(
    synthetic_package: DungeonPackage,
) -> None:
    request = pdf_request(synthetic_package).model_copy(
        update={"maximum_ink_coverage_basis_points": 1}
    )

    artifact = export_pdf(synthetic_package, request)

    assert artifact.result.success is False
    assert artifact.data is None
    assert {item.code for item in artifact.result.diagnostics} == {
        ExportDiagnosticCode.INK_BUDGET_EXCEEDED
    }


def test_pdf_file_adapter_writes_bytes_and_canonical_manifest(
    synthetic_package: DungeonPackage,
    tmp_path: Path,
) -> None:
    artifact = export_pdf(synthetic_package, pdf_request(synthetic_package))
    asset_path = tmp_path / "map.pdf"
    manifest_path = tmp_path / "map.pdf.json"

    write_pdf_artifact(asset_path, manifest_path, artifact)

    assert artifact.data is not None
    assert artifact.result.manifest is not None
    assert asset_path.read_bytes() == artifact.data
    assert manifest_path.read_text(encoding="utf-8") == to_canonical_json(
        artifact.result.manifest
    )
