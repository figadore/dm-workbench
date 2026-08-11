"""Roll20-compatible bundle integrity, scale, and secrecy tests."""

import hashlib
import io
import json
import zipfile
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image
from pydantic import ValidationError

from dm_dungeon import DungeonPackage, to_canonical_json
from dm_dungeon.export import (
    ExportDiagnosticCode,
    Roll20AssetRole,
    Roll20ExportManifest,
    Roll20ExportRequest,
    export_roll20_bundle,
    validate_roll20_artifact,
    write_roll20_directory,
    write_roll20_zip,
)
from dm_dungeon.rendering import RenderAudience, SvgThemeName


def roll20_request(
    package: DungeonPackage,
    *,
    audience: str = "player",
    floor_id: str = "floor_upper",
    include_token_placements: bool = False,
) -> Roll20ExportRequest:
    return Roll20ExportRequest(
        schema_version="1.0.0",
        package_id=package.id,
        floor_id=floor_id,
        audience=RenderAudience(audience),
        filename_prefix="sunken-archive",
        pixels_per_cell=20,
        dpi=140,
        include_token_placements=include_token_placements,
        show_labels=True,
        show_markers=True,
        theme=SvgThemeName.LOW_INK,
        maximum_ink_coverage_basis_points=5000,
    )


def test_roll20_bundle_is_byte_deterministic_and_self_consistent(
    synthetic_package: DungeonPackage,
) -> None:
    request = roll20_request(synthetic_package)

    first = export_roll20_bundle(synthetic_package, request)
    second = export_roll20_bundle(synthetic_package, request)

    assert first == second
    assert first.zip_data is not None
    assert first.result.manifest is not None
    assert first.result.bundle_sha256 == hashlib.sha256(first.zip_data).hexdigest()
    manifest = first.result.manifest
    assert manifest.grid.model_dump() == {
        "width_cells": 21,
        "height_cells": 12,
        "pixels_per_cell": 20,
        "cell_scale_feet": 5,
        "origin_x_cells": 0,
        "origin_y_cells": 0,
        "origin_x_pixels": 0,
        "origin_y_pixels": 0,
    }
    assert [asset.role for asset in manifest.assets] == [
        Roll20AssetRole.GRID_ON_MAP,
        Roll20AssetRole.GRIDLESS_MAP,
    ]
    assert all(
        (asset.width_pixels, asset.height_pixels) == (420, 240)
        for asset in manifest.assets
    )

    files = {item.filename: item.data for item in first.files}
    for asset in manifest.assets:
        assert hashlib.sha256(files[asset.filename]).hexdigest() == asset.sha256
        with Image.open(io.BytesIO(files[asset.filename])) as image:
            assert image.size == (asset.width_pixels, asset.height_pixels)
            assert image.info["dpi"] == pytest.approx((140, 140), abs=0.02)
    assert files[manifest.assets[0].filename] != files[manifest.assets[1].filename]


def test_zip_has_only_safe_fixed_metadata_and_manifest_matches_files(
    synthetic_package: DungeonPackage,
) -> None:
    artifact = export_roll20_bundle(
        synthetic_package,
        roll20_request(synthetic_package),
    )
    assert artifact.zip_data is not None

    with zipfile.ZipFile(io.BytesIO(artifact.zip_data)) as archive:
        infos = archive.infolist()
        assert [item.filename for item in infos] == sorted(
            item.filename for item in infos
        )
        assert all(item.date_time == (1980, 1, 1, 0, 0, 0) for item in infos)
        assert all(
            "/" not in item.filename and "\\" not in item.filename for item in infos
        )
        archived = {name: archive.read(name) for name in archive.namelist()}

    assert archived == {item.filename: item.data for item in artifact.files}
    manifest = json.loads(archived["sunken-archive.manifest.json"])
    assert manifest == artifact.result.manifest.model_dump(mode="json")
    assert manifest["direct_upload_supported"] is False
    assert manifest["dynamic_lighting_import_supported"] is False


def test_player_manifest_omits_every_dm_only_geometry_and_metadata(
    synthetic_package: DungeonPackage,
) -> None:
    artifact = export_roll20_bundle(
        synthetic_package,
        roll20_request(synthetic_package),
    )
    assert artifact.result.manifest is not None
    manifest = artifact.result.manifest
    document = to_canonical_json(manifest)
    hidden_values = {
        "room_vault",
        "corridor_vault_secret",
        "connection_vault_secret",
        "connection_secret_ladder",
        "label_secret_vault",
        "gate_vault",
        "secret",
    }
    assert all(value not in document for value in hidden_values)
    assert {wall.component_id for wall in manifest.wall_polygons} == {
        "room_entrance",
        "room_hall",
    }
    assert {door.component_id for door in manifest.door_segments} == {
        "connection_entry_door"
    }
    assert manifest.token_placements == ()


def test_dm_only_metadata_changes_do_not_change_player_bundle(
    synthetic_package: DungeonPackage,
) -> None:
    labels = tuple(
        label.model_copy(update={"text": "Changed hidden answer"})
        if label.id == "label_secret_vault"
        else label
        for label in synthetic_package.labels
    )
    changed = synthetic_package.model_copy(update={"labels": labels})
    request = roll20_request(synthetic_package)

    original = export_roll20_bundle(synthetic_package, request)
    changed_artifact = export_roll20_bundle(changed, request)

    assert changed_artifact == original


def test_optional_tokens_include_only_visible_position_anchors(
    synthetic_package: DungeonPackage,
) -> None:
    player = export_roll20_bundle(
        synthetic_package,
        roll20_request(
            synthetic_package,
            floor_id="floor_lower",
            include_token_placements=True,
        ),
    )
    dm = export_roll20_bundle(
        synthetic_package,
        roll20_request(
            synthetic_package,
            audience="dm",
            floor_id="floor_lower",
            include_token_placements=True,
        ),
    )
    assert player.result.manifest is not None
    assert dm.result.manifest is not None

    assert [item.anchor_id for item in player.result.manifest.token_placements] == [
        "anchor_archive_exit"
    ]
    assert {item.anchor_id for item in dm.result.manifest.token_placements} == {
        "anchor_guardian_start",
        "anchor_archive_exit",
    }
    exit_placement = player.result.manifest.token_placements[0]
    assert (exit_placement.x_pixels, exit_placement.y_pixels) == (540, 120)
    assert "anchor_guardian_start" not in to_canonical_json(player.result.manifest)


def test_request_rejects_unsafe_or_unsupported_values(
    synthetic_package: DungeonPackage,
) -> None:
    base = roll20_request(synthetic_package).model_dump()

    with pytest.raises(ValidationError):
        Roll20ExportRequest.model_validate({**base, "filename_prefix": "../secret"})
    with pytest.raises(ValidationError):
        Roll20ExportRequest.model_validate({**base, "filename_prefix": "map..old"})
    with pytest.raises(ValidationError):
        Roll20ExportRequest.model_validate({**base, "schema_version": "2.0.0"})


def test_manifest_rejects_mismatched_asset_dimensions(
    synthetic_package: DungeonPackage,
) -> None:
    artifact = export_roll20_bundle(
        synthetic_package,
        roll20_request(synthetic_package),
    )
    assert artifact.result.manifest is not None
    payload = artifact.result.manifest.model_dump()
    payload["assets"][0]["width_pixels"] += 1

    with pytest.raises(ValidationError, match="dimensions"):
        Roll20ExportManifest.model_validate(payload)


def test_artifact_validation_rejects_tampered_asset_bytes(
    synthetic_package: DungeonPackage,
) -> None:
    artifact = export_roll20_bundle(
        synthetic_package,
        roll20_request(synthetic_package),
    )
    first_file, *remaining = artifact.files
    tampered = replace(
        artifact,
        files=(replace(first_file, data=first_file.data + b"tampered"), *remaining),
    )

    with pytest.raises(ValueError, match="hash mismatch"):
        validate_roll20_artifact(tampered)


def test_render_failure_produces_no_partial_bundle(
    synthetic_package: DungeonPackage,
) -> None:
    request = roll20_request(synthetic_package).model_copy(
        update={"floor_id": "floor_missing"}
    )

    artifact = export_roll20_bundle(synthetic_package, request)

    assert artifact.result.success is False
    assert artifact.result.manifest is None
    assert artifact.result.bundle_sha256 is None
    assert artifact.files == ()
    assert artifact.zip_data is None
    assert artifact.result.diagnostics[0].code is ExportDiagnosticCode.SVG_RENDER_FAILED


def test_file_adapters_write_exact_bundle_and_reject_failure(
    synthetic_package: DungeonPackage,
    tmp_path: Path,
) -> None:
    artifact = export_roll20_bundle(
        synthetic_package,
        roll20_request(synthetic_package),
    )
    zip_path = tmp_path / "map.zip"
    directory = tmp_path / "map"

    write_roll20_zip(zip_path, artifact)
    write_roll20_directory(directory, artifact)

    assert zip_path.read_bytes() == artifact.zip_data
    assert {path.name for path in directory.iterdir()} == {
        item.filename for item in artifact.files
    }
    assert all(
        (directory / item.filename).read_bytes() == item.data for item in artifact.files
    )

    failed = export_roll20_bundle(
        synthetic_package,
        roll20_request(synthetic_package).model_copy(
            update={"package_id": "wrong_package"}
        ),
    )
    with pytest.raises(ValueError, match="unsuccessful"):
        write_roll20_zip(tmp_path / "failed.zip", failed)
    with pytest.raises(ValueError, match="unsuccessful"):
        write_roll20_directory(tmp_path / "failed", failed)
