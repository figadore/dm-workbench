"""Deterministic SVG snapshots and fail-closed secrecy tests."""

import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from pydantic import ValidationError

from dm_dungeon import DungeonPackage
from dm_dungeon.contracts import Visibility
from dm_dungeon.layout import LayoutRequest, generate_layout
from dm_dungeon.rendering import (
    RenderAudience,
    SvgAnnotationMode,
    SvgRenderDiagnosticCode,
    SvgRenderRequest,
    SvgThemeName,
    build_map_key,
    render_svg,
    write_svg,
)
from dm_dungeon.validation.grid import cells_for_corridor

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
    assert first.width_pixels == 400
    assert first.height_pixels == 400


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


def test_default_callouts_are_short_bijective_and_collision_free(
    layout_request: LayoutRequest,
) -> None:
    topology = layout_request.topology.model_copy(
        update={
            "connections": tuple(
                connection
                for connection in layout_request.topology.connections
                if connection.id != "connection_entry_corridor"
            )
        }
    )
    result = generate_layout(
        layout_request.model_copy(
            update={"generator_version": "orthogonal-v1", "topology": topology}
        )
    )
    assert isinstance(result.package, DungeonPackage)
    package = result.package
    floor_id = package.floors[0].id

    rendered = render_svg(
        package,
        SvgRenderRequest(
            schema_version="1.0.0",
            package_id=package.id,
            floor_id=floor_id,
            audience=RenderAudience.DM,
            pixels_per_cell=20,
            annotation_mode=SvgAnnotationMode.CALLOUTS,
        ),
    )
    assert rendered.svg is not None
    root = ET.fromstring(rendered.svg)
    callout_text = [
        element.text for element in root.iter() if "data-callout" in element.attrib
    ]
    assert callout_text
    assert all(text is not None and not text.startswith("v1-") for text in callout_text)

    key = build_map_key(package, floor_id, RenderAudience.DM, scale=20)
    assert {entry.token for entry in key.entries} == set(callout_text)
    boxes = [
        box
        for entry in key.entries
        for box in (
            (
                entry.label_x - entry.width / 2,
                entry.label_y - entry.height / 2,
                entry.label_x + entry.width / 2,
                entry.label_y + entry.height / 2,
            ),
            *(
                (
                    badge.label_x - badge.width / 2,
                    badge.label_y - badge.height / 2,
                    badge.label_x + badge.width / 2,
                    badge.label_y + badge.height / 2,
                )
                for badge in entry.badges
            ),
        )
    ]
    for index, first in enumerate(boxes):
        for second in boxes[index + 1 :]:
            assert (
                first[2] <= second[0]
                or second[2] <= first[0]
                or first[3] <= second[1]
                or second[3] <= first[1]
            )


def test_renderer_clips_room_walls_at_explicit_passage_openings(
    layout_request: LayoutRequest,
) -> None:
    topology = layout_request.topology.model_copy(
        update={
            "connections": tuple(
                connection
                for connection in layout_request.topology.connections
                if connection.id != "connection_entry_corridor"
            )
        }
    )
    result = generate_layout(
        layout_request.model_copy(
            update={"generator_version": "orthogonal-v1", "topology": topology}
        )
    )
    assert isinstance(result.package, DungeonPackage)
    package = result.package
    floor_id = package.corridors[0].floor_id

    rendered = render_svg(package, render_request(package, RenderAudience.DM, floor_id))

    assert rendered.success is True
    assert rendered.svg is not None
    root = ET.fromstring(rendered.svg)
    opening_lines = [
        element
        for element in root.iter()
        if element.attrib.get("class") == "passage-opening"
    ]
    assert len(opening_lines) == len(
        [
            item
            for item in package.passage_openings
            if item.corridor_id
            in {
                corridor.id
                for corridor in package.corridors
                if corridor.floor_id == floor_id
            }
        ]
    )


def test_corridor_rendering_uses_the_validated_cell_footprint(
    synthetic_package: DungeonPackage,
) -> None:
    original = synthetic_package.corridors[0]
    result = render_svg(
        synthetic_package,
        render_request(
            synthetic_package, RenderAudience.DM, floor_id=original.floor_id
        ),
    )

    assert result.svg is not None
    root = ET.fromstring(result.svg)
    corridor = next(
        element
        for element in root.iter()
        if element.attrib.get("data-component-id") == original.id
    )
    fills = [
        element for element in corridor if element.attrib.get("class") == "corridor"
    ]
    outlines = [
        element
        for element in corridor
        if element.attrib.get("class") == "corridor-outline"
    ]
    assert fills
    assert all(element.tag.endswith("rect") for element in fills)
    assert len(fills) == len(cells_for_corridor(original.path, original.width_cells))
    assert len(outlines) >= 2
    assert all(element.tag.endswith("line") for element in outlines)


def test_visible_doors_use_an_explicit_thick_slab_in_player_svg(
    synthetic_package: DungeonPackage,
) -> None:
    result = render_svg(
        synthetic_package,
        render_request(synthetic_package, RenderAudience.PLAYER),
    )

    assert result.svg is not None
    root = ET.fromstring(result.svg)
    visible_door_lines = [
        child
        for component in root.iter()
        if component.attrib.get("data-kind") == "door"
        for child in component
        if child.attrib.get("class") == "door"
    ]
    assert visible_door_lines
    assert all(line.attrib.get("stroke-width") == "6" for line in visible_door_lines)


def test_constructive_player_svg_omits_secret_channel_and_door(
    generated_package: DungeonPackage,
) -> None:
    floor_id = generated_package.floors[0].id
    dm = render_svg(
        generated_package,
        render_request(generated_package, RenderAudience.DM, floor_id),
    )
    player = render_svg(
        generated_package,
        render_request(generated_package, RenderAudience.PLAYER, floor_id),
    )
    assert dm.svg is not None
    assert player.svg is not None
    secret_connection_ids = {
        item.id
        for item in generated_package.topology.connections
        if item.visibility is Visibility.DM_ONLY
    }
    secret_door_ids = {
        item.id
        for item in generated_package.composable_doors
        if item.connection_id in secret_connection_ids
    }
    hidden_ids = secret_connection_ids | secret_door_ids

    assert hidden_ids
    assert hidden_ids <= xml_component_ids(dm.svg)
    assert hidden_ids.isdisjoint(xml_component_ids(player.svg))
    assert "dm_only" not in player.svg
    assert "data-callout" not in player.svg
    assert 'data-kind="dungeon-start"' not in player.svg
    assert 'data-mechanic-kind="objective"' not in player.svg


def test_player_default_is_geometry_only_without_keys_or_objective_markers(
    generated_package: DungeonPackage,
) -> None:
    floor_id = generated_package.floors[0].id
    result = render_svg(
        generated_package,
        SvgRenderRequest(
            schema_version="1.0.0",
            package_id=generated_package.id,
            floor_id=floor_id,
            audience=RenderAudience.PLAYER,
            pixels_per_cell=20,
            annotation_mode=SvgAnnotationMode.CALLOUTS,
            show_labels=True,
            show_markers=True,
        ),
    )

    assert result.svg is not None
    assert "data-callout" not in result.svg
    assert 'data-kind="dungeon-start"' not in result.svg
    assert 'data-kind="encounter-slot"' not in result.svg
    assert 'data-mechanic-kind="objective"' not in result.svg
    assert not any(
        component_id in result.svg
        for component_id in {
            item.id
            for item in generated_package.room_mechanic_markers
            if item.kind.value == "objective"
        }
    )
    assert {
        room.id
        for room in generated_package.rooms
        if room.visibility is Visibility.PLAYER_SAFE
    } <= xml_component_ids(result.svg)


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
        "connection_vault_secret_mechanics",
        "connection_secret_ladder",
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

    hidden_ids = {"connection_secret_ladder"}
    assert hidden_ids <= dm_ids
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
