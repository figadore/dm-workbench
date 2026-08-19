"""Frozen measurements for the retained pre-P7-13 output failure."""

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from dm_dungeon import DungeonPackage, read_dungeon_package
from dm_dungeon.export import PdfExportRequest, export_pdf
from dm_dungeon.rendering import (
    RenderAudience,
    SvgRenderRequest,
    SvgThemeName,
    render_svg,
)
from dm_dungeon.validation.grid import build_walkable_grid

FIXTURE_PATH = Path(__file__).parent / "fixtures/output_quality_baseline.v1.json"
GOLDEN_PATH = Path(__file__).parent / "golden/output_quality_baseline.upper.dm.svg"
_CELL_POINTS = 72


@dataclass(frozen=True)
class BaselineMetrics:
    raw_opaque_ids: int
    text_collisions: int
    endpoint_clearance_bends: int
    corridor_room_interior_overlaps: int
    missing_keyed_mechanics: int
    print_page_count: int
    blank_tile_ratio: float


def _dm_upper_svg(package: DungeonPackage) -> str:
    result = render_svg(
        package,
        SvgRenderRequest(
            schema_version="1.0.0",
            package_id=package.id,
            floor_id="floor_upper",
            audience=RenderAudience.DM,
            pixels_per_cell=20,
            show_grid=True,
            show_labels=True,
            show_room_ids=True,
            show_markers=True,
            theme=SvgThemeName.LOW_INK,
        ),
    )
    assert result.success and result.svg is not None
    return result.svg


def _text_collisions(svg: str) -> int:
    """Use the current renderer's deterministic monospace approximation."""

    boxes: list[tuple[float, float, float, float]] = []
    for element in ET.fromstring(svg).iter():
        is_room_id = element.attrib.get("data-kind") == "room-id"
        is_label = element.attrib.get("class") == "label"
        if not (is_room_id or is_label) or not element.text:
            continue
        x = float(element.attrib["x"])
        y = float(element.attrib["y"])
        width = len(element.text) * (6 if is_room_id else 7)
        if element.attrib.get("text-anchor") == "middle":
            x -= width / 2
        boxes.append((x, y - 12, x + width, y + 2))
    return sum(
        left[0] < right[2]
        and right[0] < left[2]
        and left[1] < right[3]
        and right[1] < left[3]
        for index, left in enumerate(boxes)
        for right in boxes[index + 1 :]
    )


def _endpoint_clearance_bends(package: DungeonPackage) -> int:
    count = 0
    for corridor in package.corridors:
        points = corridor.path.points
        for index in range(1, len(points) - 1):
            previous, bend, following = points[index - 1 : index + 2]
            first_length = abs(previous.x - bend.x) + abs(previous.y - bend.y)
            last_length = abs(following.x - bend.x) + abs(following.y - bend.y)
            if first_length <= 1 or last_length <= 1:
                count += 1
    return count


def _corridor_room_interior_overlaps(package: DungeonPackage) -> int:
    grid = build_walkable_grid(package)
    overlaps = 0
    for corridor in package.corridors:
        for room_id in corridor.connects_room_ids:
            overlaps += len(grid.corridor_cells[corridor.id] & grid.room_cells[room_id])
    return overlaps


def _blank_tile_ratio(package: DungeonPackage) -> tuple[int, float]:
    artifact = export_pdf(
        package,
        PdfExportRequest(
            schema_version="1.0.0",
            package_id=package.id,
            floor_id="floor_upper",
            audience=RenderAudience.DM,
            maximum_ink_coverage_basis_points=5000,
        ),
    )
    assert artifact.result.success and artifact.result.manifest is not None
    grid = build_walkable_grid(package)
    occupied = grid.floor_cells["floor_upper"]
    blank_tiles = 0
    for tile in artifact.result.manifest.tiles:
        min_x = tile.source_x_points // _CELL_POINTS
        min_y = tile.source_y_points // _CELL_POINTS
        max_x = (tile.source_x_points + tile.viewport_width_points - 1) // _CELL_POINTS
        max_y = (tile.source_y_points + tile.viewport_height_points - 1) // _CELL_POINTS
        if not any(min_x <= x <= max_x and min_y <= y <= max_y for x, y in occupied):
            blank_tiles += 1
    return artifact.result.manifest.page_count, blank_tiles / len(
        artifact.result.manifest.tiles
    )


def _metrics(package: DungeonPackage) -> BaselineMetrics:
    svg = _dm_upper_svg(package)
    root = ET.fromstring(svg)
    raw_opaque_ids = sum(
        element.attrib.get("data-kind") == "room-id" for element in root.iter()
    )
    special_doors = [door for door in package.doors if door.door_type.value != "normal"]
    page_count, blank_tile_ratio = _blank_tile_ratio(package)
    return BaselineMetrics(
        raw_opaque_ids=raw_opaque_ids,
        text_collisions=_text_collisions(svg),
        endpoint_clearance_bends=_endpoint_clearance_bends(package),
        corridor_room_interior_overlaps=_corridor_room_interior_overlaps(package),
        # The retained renderer has no DM key projection for any special door.
        missing_keyed_mechanics=len(special_doors),
        print_page_count=page_count,
        blank_tile_ratio=blank_tile_ratio,
    )


def test_retained_output_baseline_fixture_covers_output_refresh_cases() -> None:
    package = read_dungeon_package(FIXTURE_PATH)
    door_types = {door.door_type.value for door in package.doors}
    upper_rooms = {
        room.id: room for room in package.rooms if room.floor_id == "floor_upper"
    }

    assert {"normal", "secret", "locked", "trapped"} <= door_types
    assert package.hazards
    assert package.topology.keys and package.topology.clues
    assert package.stairs and package.features
    # The normal door now has rooms sharing its wall; the baseline corridor still
    # overlaps the destination interior, preserving the pre-P7-13b defect.
    assert max(
        point.x for point in upper_rooms["room_entrance"].boundary.points
    ) == min(point.x for point in upper_rooms["room_hall"].boundary.points)
    assert _dm_upper_svg(package) == GOLDEN_PATH.read_text(encoding="utf-8")


def test_retained_output_baseline_counts_known_failures() -> None:
    package = read_dungeon_package(FIXTURE_PATH)

    assert _metrics(package) == BaselineMetrics(
        raw_opaque_ids=3,
        text_collisions=3,
        endpoint_clearance_bends=1,
        corridor_room_interior_overlaps=6,
        missing_keyed_mechanics=3,
        print_page_count=73,
        blank_tile_ratio=66 / 72,
    )
