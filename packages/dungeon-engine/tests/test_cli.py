"""Independent file-oriented CLI tests."""

import json
from pathlib import Path

import pytest

from dm_dungeon import to_canonical_json
from dm_dungeon.cli import main
from dm_dungeon.layout import LayoutRequest
from dm_dungeon.serialization import read_dungeon_package, write_dungeon_package


def test_validate_command_accepts_synthetic_package(
    fixture_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["validate", str(fixture_path)]) == 0

    output = capsys.readouterr().out
    assert output == "valid DungeonPackage 1.0.0: pkg_sunken_archive\n"


def test_canonicalize_command_writes_stable_json(
    fixture_path: Path,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "canonical.json"

    assert main(["canonicalize", str(fixture_path), "--output", str(output_path)]) == 0

    package = read_dungeon_package(fixture_path)
    assert output_path.read_text(encoding="utf-8") == to_canonical_json(package)


def test_invalid_topology_returns_structured_report(
    fixture_path: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    package = read_dungeon_package(fixture_path)
    topology = package.topology.model_copy(
        update={
            "connections": tuple(
                item
                for item in package.topology.connections
                if item.id != "connection_sanctum_exit"
            )
        }
    )
    invalid_package = package.model_copy(
        update={"topology": topology, "corridors": (), "passage_openings": ()}
    )
    input_path = tmp_path / "invalid.json"
    write_dungeon_package(input_path, invalid_package)

    assert main(["validate", str(input_path)]) == 1

    report = json.loads(capsys.readouterr().err)
    assert report["valid"] is False
    assert report["diagnostics"]


def test_invalid_geometry_returns_structured_report(
    fixture_path: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    package = read_dungeon_package(fixture_path)
    first, second, *remaining = package.rooms
    overlap = second.model_copy(update={"boundary": first.boundary})
    invalid_package = package.model_copy(update={"rooms": (first, overlap, *remaining)})
    input_path = tmp_path / "invalid-geometry.json"
    write_dungeon_package(input_path, invalid_package)

    assert main(["validate", str(input_path)]) == 1

    report = json.loads(capsys.readouterr().err)
    assert report["valid"] is False
    assert any(
        item["code"] == "geometry.room_overlap" for item in report["diagnostics"]
    )


def test_layout_command_generates_canonical_result(
    layout_request: LayoutRequest,
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "layout-request.json"
    output_path = tmp_path / "layout-result.json"
    input_path.write_text(to_canonical_json(layout_request), encoding="utf-8")

    assert main(["layout", str(input_path), "--output", str(output_path)]) == 0

    result = json.loads(output_path.read_text(encoding="utf-8"))
    assert result["success"] is True
    assert result["package"]["id"] == layout_request.package_id


def test_render_svg_command_writes_player_safe_document(
    fixture_path: Path,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "player.svg"

    assert (
        main(
            [
                "render-svg",
                str(fixture_path),
                "--floor",
                "floor_upper",
                "--audience",
                "player",
                "--pixels-per-cell",
                "20",
                "--output",
                str(output_path),
            ]
        )
        == 0
    )

    document = output_path.read_text(encoding="utf-8")
    assert document.startswith("<svg")
    assert "room_vault" not in document
    assert "connection_vault_secret" not in document


def test_export_png_command_writes_asset_and_manifest(
    fixture_path: Path,
    tmp_path: Path,
) -> None:
    asset_path = tmp_path / "player.png"
    manifest_path = tmp_path / "player.png.json"

    assert (
        main(
            [
                "export-png",
                str(fixture_path),
                "--floor",
                "floor_upper",
                "--audience",
                "player",
                "--pixels-per-cell",
                "20",
                "--output",
                str(asset_path),
                "--manifest",
                str(manifest_path),
            ]
        )
        == 0
    )

    assert asset_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["audience"] == "player"
    assert "room_vault" not in manifest["rendered_component_ids"]


def test_export_pdf_command_writes_asset_and_manifest(
    fixture_path: Path,
    tmp_path: Path,
) -> None:
    asset_path = tmp_path / "player.pdf"
    manifest_path = tmp_path / "player.pdf.json"

    assert (
        main(
            [
                "export-pdf",
                str(fixture_path),
                "--floor",
                "floor_upper",
                "--audience",
                "player",
                "--output",
                str(asset_path),
                "--manifest",
                str(manifest_path),
            ]
        )
        == 0
    )

    assert asset_path.read_bytes().startswith(b"%PDF-")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["cell_scale_points"] == 72
    assert manifest["calibration_square_points"] == 72
    assert "room_vault" not in manifest["rendered_component_ids"]


def test_export_roll20_command_writes_safe_zip_and_directory(
    fixture_path: Path,
    tmp_path: Path,
) -> None:
    zip_path = tmp_path / "roll20.zip"
    directory = tmp_path / "roll20-files"

    assert (
        main(
            [
                "export-roll20",
                str(fixture_path),
                "--floor",
                "floor_upper",
                "--audience",
                "player",
                "--prefix",
                "archive-upper",
                "--pixels-per-cell",
                "20",
                "--output",
                str(zip_path),
                "--directory",
                str(directory),
            ]
        )
        == 0
    )

    assert zip_path.read_bytes().startswith(b"PK\x03\x04")
    manifest = json.loads(
        (directory / "archive-upper.manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["grid"]["pixels_per_cell"] == 20
    assert manifest["grid"]["cell_scale_feet"] == 5
    assert "room_vault" not in manifest["rendered_component_ids"]
    assert (directory / "archive-upper.grid.png").is_file()
    assert (directory / "archive-upper.gridless.png").is_file()


def test_schema_command_emits_json_schema(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "schema.json"

    assert main(["schema", "--output", str(output_path)]) == 0

    schema = json.loads(output_path.read_text(encoding="utf-8"))
    assert schema["title"] == "DungeonPackage"
