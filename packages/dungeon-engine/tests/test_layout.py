"""Seeded orthogonal layout engine tests."""

import json

import pytest
from pydantic import ValidationError

from dm_dungeon import to_canonical_json
from dm_dungeon.contracts import ComponentIdStrategy, DungeonPackage
from dm_dungeon.layout import (
    FloorLayoutBounds,
    LayoutDiagnosticCode,
    LayoutRequest,
    LockedLayoutComponents,
    generate_layout,
    load_layout_request_json,
)
from dm_dungeon.serialization import UnsupportedSchemaVersionError


def component_by_id(components: tuple[object, ...], component_id: str) -> object:
    return next(
        component
        for component in components
        if getattr(component, "id", None) == component_id
    )


def test_identical_request_produces_byte_equivalent_layout(
    layout_request: LayoutRequest,
) -> None:
    first = generate_layout(layout_request)
    second = generate_layout(layout_request)

    assert first.success is True
    assert first.package is not None
    assert first.diagnostics == ()
    assert first.random_draw_count > 0
    assert first == second
    assert to_canonical_json(first) == to_canonical_json(second)


def test_layout_emits_every_supported_topology_component(
    layout_request: LayoutRequest,
) -> None:
    result = generate_layout(layout_request)
    assert result.package is not None
    package = result.package

    assert len(package.floors) == len(layout_request.topology.floors)
    assert len(package.rooms) == len(layout_request.topology.rooms)
    assert len(package.corridors) == 6
    assert len(package.doors) == 4
    assert len(package.stairs) == 2
    assert len(package.vertical_links) == 2


def test_different_seeds_produce_valid_alternatives_with_stable_room_ids(
    layout_request: LayoutRequest,
) -> None:
    first = generate_layout(layout_request)
    alternate = generate_layout(layout_request.model_copy(update={"seed": 424243}))

    assert first.package is not None
    assert alternate.package is not None
    assert first.package.rooms != alternate.package.rooms
    assert {room.id for room in first.package.rooms} == {
        room.id for room in alternate.package.rooms
    }


def test_targeted_regeneration_preserves_every_locked_component(
    layout_request: LayoutRequest,
) -> None:
    original_result = generate_layout(layout_request)
    assert original_result.package is not None
    original = original_result.package
    locks = LockedLayoutComponents(
        floors=(original.floors[0],),
        rooms=(original.rooms[0], original.rooms[1], original.rooms[3]),
        corridors=(original.corridors[0], original.corridors[1]),
        doors=(original.doors[0],),
        stairs=(original.stairs[0],),
        vertical_links=(original.vertical_links[0],),
    )
    regenerated = generate_layout(
        layout_request.model_copy(update={"seed": 888888, "locked": locks})
    )

    assert regenerated.package is not None
    package = regenerated.package
    for locked in locks.floors:
        assert component_by_id(package.floors, locked.id) == locked
    for locked in locks.rooms:
        assert component_by_id(package.rooms, locked.id) == locked
    for locked in locks.corridors:
        assert component_by_id(package.corridors, locked.id) == locked
    for locked in locks.doors:
        assert component_by_id(package.doors, locked.id) == locked
    for locked in locks.stairs:
        assert component_by_id(package.stairs, locked.id) == locked
    for locked in locks.vertical_links:
        assert component_by_id(package.vertical_links, locked.id) == locked


def test_generated_rooms_honor_size_constraints(layout_request: LayoutRequest) -> None:
    result = generate_layout(layout_request)
    assert result.package is not None
    constraints = {room.id: room.size for room in layout_request.topology.rooms}

    for room in result.package.rooms:
        width = max(point.x for point in room.boundary.points) - min(
            point.x for point in room.boundary.points
        )
        height = max(point.y for point in room.boundary.points) - min(
            point.y for point in room.boundary.points
        )
        size = constraints[room.id]
        assert width >= size.minimum_width_cells
        assert height >= size.minimum_height_cells
        assert width * height >= size.minimum_area_cells
        if size.maximum_width_cells is not None:
            assert width <= size.maximum_width_cells
        if size.maximum_height_cells is not None:
            assert height <= size.maximum_height_cells
        if size.maximum_area_cells is not None:
            assert width * height <= size.maximum_area_cells


def test_room_rectangles_do_not_overlap(layout_request: LayoutRequest) -> None:
    result = generate_layout(layout_request)
    assert result.package is not None

    for index, first in enumerate(result.package.rooms):
        first_x = [point.x for point in first.boundary.points]
        first_y = [point.y for point in first.boundary.points]
        for second in result.package.rooms[index + 1 :]:
            if first.floor_id != second.floor_id:
                continue
            second_x = [point.x for point in second.boundary.points]
            second_y = [point.y for point in second.boundary.points]
            overlap = not (
                max(first_x) <= min(second_x)
                or max(second_x) <= min(first_x)
                or max(first_y) <= min(second_y)
                or max(second_y) <= min(first_y)
            )
            assert overlap is False, (first.id, second.id)


def test_corridors_and_doors_are_orthogonal(layout_request: LayoutRequest) -> None:
    result = generate_layout(layout_request)
    assert result.package is not None

    for corridor in result.package.corridors:
        for first, second in zip(
            corridor.path.points,
            corridor.path.points[1:],
            strict=False,
        ):
            assert first.x == second.x or first.y == second.y
    for door in result.package.doors:
        assert (
            door.segment.start.x == door.segment.end.x
            or door.segment.start.y == door.segment.end.y
        )


def test_impossible_floor_bounds_fail_with_diagnostics(
    layout_request: LayoutRequest,
) -> None:
    bounds = FloorLayoutBounds(
        floor_id="floor_upper",
        width_cells=4,
        height_cells=4,
        margin_cells=1,
    )
    result = generate_layout(
        layout_request.model_copy(update={"floor_bounds": (bounds,)})
    )

    assert result.success is False
    assert result.package is None
    assert LayoutDiagnosticCode.ROOM_PLACEMENT_FAILED in {
        item.code for item in result.diagnostics
    }


def test_invalid_topology_fails_without_partial_package(
    layout_request: LayoutRequest,
) -> None:
    broken_topology = layout_request.topology.model_copy(update={"connections": ()})
    result = generate_layout(
        layout_request.model_copy(update={"topology": broken_topology})
    )

    assert result.success is False
    assert result.package is None
    assert {item.code for item in result.diagnostics} == {
        LayoutDiagnosticCode.TOPOLOGY_INVALID
    }
    assert all(item.source_code for item in result.diagnostics)


def test_stale_locked_component_fails_explicitly(
    layout_request: LayoutRequest,
) -> None:
    original = generate_layout(layout_request)
    assert original.package is not None
    stale_room = original.package.rooms[0].model_copy(update={"id": "room_stale"})
    locks = LockedLayoutComponents(rooms=(stale_room,))

    result = generate_layout(layout_request.model_copy(update={"locked": locks}))

    assert result.success is False
    assert LayoutDiagnosticCode.LOCKED_COMPONENT_UNKNOWN in {
        item.code for item in result.diagnostics
    }


def test_locked_room_from_wrong_floor_fails_as_a_lock_conflict(
    layout_request: LayoutRequest,
) -> None:
    original = generate_layout(layout_request)
    assert original.package is not None
    misplaced = original.package.rooms[0].model_copy(update={"floor_id": "floor_lower"})
    locks = LockedLayoutComponents(rooms=(misplaced,))

    result = generate_layout(layout_request.model_copy(update={"locked": locks}))

    assert result.success is False
    assert LayoutDiagnosticCode.LOCKED_COMPONENT_CONFLICT in {
        item.code for item in result.diagnostics
    }


def test_layout_request_json_round_trip_and_unknown_version_rejection(
    layout_request: LayoutRequest,
) -> None:
    document = to_canonical_json(layout_request)

    assert load_layout_request_json(document) == layout_request

    payload = json.loads(document)
    payload["schema_version"] = "99.0.0"
    with pytest.raises(
        UnsupportedSchemaVersionError,
        match=r"Unsupported LayoutRequest schema version '99.0.0'",
    ):
        load_layout_request_json(json.dumps(payload))


def test_unknown_generator_version_is_rejected(layout_request: LayoutRequest) -> None:
    payload = json.loads(to_canonical_json(layout_request))
    payload["generator_version"] = "future-layout"

    with pytest.raises(ValidationError, match="orthogonal-v1"):
        load_layout_request_json(json.dumps(payload))


def test_layout_result_contains_a_valid_package_contract(
    layout_request: LayoutRequest,
) -> None:
    result = generate_layout(layout_request)
    assert result.package is not None

    document = to_canonical_json(result.package)
    reparsed = DungeonPackage.model_validate_json(document)

    assert reparsed == result.package
    assert reparsed.metadata.component_id_strategy is (
        ComponentIdStrategy.INPUT_WITH_SHA256_V1_AUXILIARY
    )
