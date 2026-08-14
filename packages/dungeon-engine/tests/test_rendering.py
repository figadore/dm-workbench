"""Deterministic SVG snapshots and fail-closed secrecy tests."""

import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from pydantic import ValidationError

from dm_dungeon import DungeonPackage
from dm_dungeon.contracts import Visibility
from dm_dungeon.rendering import (
    RenderAudience,
    SvgRenderDiagnosticCode,
    SvgRenderRequest,
    SvgThemeName,
    render_svg,
    write_svg,
)

GOLDEN_ROOT = Path(__file__).parent / "golden"


def render_request(
    package: DungeonPackage,
    audience: RenderAudience,
    floor_id: str = "floor_upper",
) -> SvgRenderRequest:
    return SvgRenderRequest(
        schema_version="1.0.0",
        package_id=package.id,
        floor_id=floor_id,
        audience=audience,
        pixels_per_cell=20,
        show_grid=True,
        show_labels=True,
        show_room_ids=True,
        show_markers=True,
        theme=SvgThemeName.LOW_INK,
    )


def xml_component_ids(svg: str) -> set[str]:
    root = ET.fromstring(svg)
    return {
        element.attrib["data-component-id"]
        for element in root.iter()
        if "data-component-id" in element.attrib
    }


def test_svg_render_is_byte_deterministic_and_hash_pinned(
    synthetic_package: DungeonPackage,
) -> None:
    request = render_request(synthetic_package, RenderAudience.DM)

    first = render_svg(synthetic_package, request)
    second = render_svg(synthetic_package, request)

    assert first.success is True
    assert first == second
    assert first.svg is not None
    assert first.sha256 == hashlib.sha256(first.svg.encode("utf-8")).hexdigest()
    assert first.width_pixels == 420
    assert first.height_pixels == 240


@pytest.mark.parametrize("audience", tuple(RenderAudience))
def test_upper_floor_svg_matches_golden_snapshot(
    synthetic_package: DungeonPackage,
    audience: RenderAudience,
) -> None:
    result = render_svg(synthetic_package, render_request(synthetic_package, audience))

    assert result.svg is not None
    golden = (GOLDEN_ROOT / f"sunken_archive.upper.{audience.value}.svg").read_text(
        encoding="utf-8"
    )
    assert result.svg == golden


def test_corridor_rendering_uses_the_validated_cell_footprint(
    synthetic_package: DungeonPackage,
) -> None:
    original = next(
        item
        for item in synthetic_package.corridors
        if item.id == "corridor_vault_secret"
    )
    widened = original.model_copy(update={"width_cells": 2})
    package = synthetic_package.model_copy(
        update={
            "corridors": tuple(
                widened if item.id == widened.id else item
                for item in synthetic_package.corridors
            )
        }
    )

    result = render_svg(package, render_request(package, RenderAudience.DM))

    assert result.svg is not None
    root = ET.fromstring(result.svg)
    corridor = next(
        element
        for element in root.iter()
        if element.attrib.get("data-component-id") == widened.id
    )
    fill = next(
        element for element in corridor if element.attrib.get("class") == "corridor"
    )
    # The two-cell corridor at y=6 occupies rows 6 and 7, never row 5. The
    # old centered SVG stroke spilled upward into row 5 despite validation
    # declaring only rows 6 and 7 walkable.
    assert fill.tag.endswith("path")
    assert fill.attrib["d"] == (
        "M260,120H280V140H260ZM280,120H300V140H280ZM300,120H320V140H300Z"
        "M260,140H280V160H260ZM280,140H300V160H280ZM300,140H320V160H300Z"
    )


def test_player_svg_omits_every_dm_only_upper_floor_component(
    synthetic_package: DungeonPackage,
) -> None:
    dm = render_svg(
        synthetic_package,
        render_request(synthetic_package, RenderAudience.DM),
    )
    player = render_svg(
        synthetic_package,
        render_request(synthetic_package, RenderAudience.PLAYER),
    )
    assert dm.svg is not None
    assert player.svg is not None
    dm_ids = xml_component_ids(dm.svg)
    player_ids = xml_component_ids(player.svg)

    hidden_ids = {
        "room_vault",
        "corridor_vault_secret",
        "connection_vault_secret",
        "connection_secret_ladder",
        "label_secret_vault",
    }
    assert hidden_ids <= dm_ids
    assert hidden_ids.isdisjoint(player_ids)
    assert player_ids < dm_ids
    assert "display:none" not in player.svg

    player_root = ET.fromstring(player.svg)
    for element in player_root.iter():
        visibility = element.attrib.get("data-visibility")
        if visibility is not None:
            assert visibility == "player_safe"


def test_player_lower_floor_omits_traps_creature_starts_and_dm_annotations(
    synthetic_package: DungeonPackage,
) -> None:
    dm = render_svg(
        synthetic_package,
        render_request(
            synthetic_package,
            RenderAudience.DM,
            floor_id="floor_lower",
        ),
    )
    player = render_svg(
        synthetic_package,
        render_request(
            synthetic_package,
            RenderAudience.PLAYER,
            floor_id="floor_lower",
        ),
    )
    assert dm.svg is not None
    assert player.svg is not None
    dm_ids = xml_component_ids(dm.svg)
    player_ids = xml_component_ids(player.svg)

    hidden_ids = {
        "connection_crypt_trap",
        "corridor_crypt_trap",
        "hazard_needle_lock",
        "zone_sanctum_encounter",
        "label_secret_vault",
        "encounter_slot_guardian",
        "anchor_guardian_start",
    }
    assert hidden_ids - {"label_secret_vault"} <= dm_ids
    assert hidden_ids.isdisjoint(player_ids)
    assert 'data-door-type="trapped"' not in player.svg
    assert 'data-anchor-kind="creature_start"' not in player.svg


def test_grid_label_and_marker_toggles_remove_elements_before_output(
    synthetic_package: DungeonPackage,
) -> None:
    request = render_request(synthetic_package, RenderAudience.DM).model_copy(
        update={"show_grid": False, "show_labels": False, "show_markers": False}
    )
    result = render_svg(synthetic_package, request)

    assert result.svg is not None
    root = ET.fromstring(result.svg)
    element_ids = {element.attrib.get("id") for element in root.iter()}
    assert "grid" not in element_ids
    assert "labels" not in element_ids
    assert "markers" not in element_ids
    assert "label_archive_entrance" not in result.rendered_component_ids
    assert "anchor_archive_entrance" not in result.rendered_component_ids


def test_invalid_geometry_fails_without_partial_svg(
    generated_package: DungeonPackage,
) -> None:
    first, second, *remaining = generated_package.rooms
    overlap = second.model_copy(update={"boundary": first.boundary})
    broken = generated_package.model_copy(
        update={"rooms": (first, overlap, *remaining)}
    )
    request = render_request(broken, RenderAudience.DM, floor_id=first.floor_id)

    result = render_svg(broken, request)

    assert result.success is False
    assert result.svg is None
    assert result.rendered_component_ids == ()
    assert {item.code for item in result.diagnostics} == {
        SvgRenderDiagnosticCode.GEOMETRY_INVALID
    }


def test_player_request_for_dm_only_floor_fails_closed(
    synthetic_package: DungeonPackage,
) -> None:
    upper, lower = synthetic_package.floors
    hidden_upper = upper.model_copy(update={"visibility": Visibility.DM_ONLY})
    broken = synthetic_package.model_copy(update={"floors": (hidden_upper, lower)})

    result = render_svg(
        broken,
        render_request(broken, RenderAudience.PLAYER),
    )

    assert result.success is False
    assert result.svg is None
    assert SvgRenderDiagnosticCode.FLOOR_NOT_PUBLISHABLE in {
        item.code for item in result.diagnostics
    }


def test_named_theme_is_strictly_validated(
    synthetic_package: DungeonPackage,
) -> None:
    payload = render_request(
        synthetic_package,
        RenderAudience.DM,
    ).model_dump(mode="json")
    payload["theme"] = "model-authored-css"

    with pytest.raises(ValidationError):
        SvgRenderRequest.model_validate(payload)


def test_svg_file_adapter_preserves_exact_document_bytes(
    synthetic_package: DungeonPackage,
    tmp_path: Path,
) -> None:
    result = render_svg(
        synthetic_package,
        render_request(synthetic_package, RenderAudience.PLAYER),
    )
    output = tmp_path / "player.svg"

    write_svg(output, result)

    assert result.svg is not None
    assert output.read_bytes() == result.svg.encode("utf-8")
