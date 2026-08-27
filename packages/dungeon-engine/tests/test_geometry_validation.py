"""Exact geometry, walkability, alignment, and capacity tests."""

from dm_dungeon.contracts import (
    DungeonPackage,
    PassageApproachDirection,
)
from dm_dungeon.contracts.geometry import (
    GridPoint,
    GridSegment,
    GridSpec,
    GridType,
    PolygonGeometry,
    PolylineGeometry,
)
from dm_dungeon.layout import LayoutRequest, generate_layout
from dm_dungeon.validation import GeometryDiagnosticCode, validate_geometry


def codes(package: DungeonPackage) -> set[GeometryDiagnosticCode]:
    return {item.code for item in validate_geometry(package).diagnostics}


def test_hand_authored_and_generated_packages_have_valid_geometry(
    synthetic_package: DungeonPackage,
    generated_package: DungeonPackage,
) -> None:
    hand_report = validate_geometry(synthetic_package)
    generated_report = validate_geometry(generated_package)

    assert hand_report.valid is True
    assert hand_report.diagnostics == ()
    assert hand_report.walkable_cell_count > 0
    assert generated_report.valid is True
    assert generated_report.diagnostics == ()


def test_geometry_rejects_undeclared_openings_and_endpoint_doglegs(
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
    assert result.package is not None
    assert isinstance(result.package, DungeonPackage)
    package = result.package
    corridor = package.corridors[0]
    opening = next(
        item
        for item in package.passage_openings
        if item.room_id == corridor.connects_room_ids[0]
    )
    wrong_point = _wrong_first_step(corridor.path.points[0], opening.approach_direction)
    dogleg = corridor.model_copy(
        update={
            "path": PolylineGeometry(
                kind="polyline",
                points=(corridor.path.points[0], wrong_point, corridor.path.points[-1]),
            )
        }
    )
    broken_dogleg = package.model_copy(
        update={"corridors": (dogleg, *package.corridors[1:])}
    )
    moved_opening = opening.model_copy(
        update={
            "segment": GridSegment(start=GridPoint(x=0, y=0), end=GridPoint(x=1, y=0))
        }
    )
    broken_opening = package.model_copy(
        update={
            "passage_openings": tuple(
                moved_opening if item.id == opening.id else item
                for item in package.passage_openings
            )
        }
    )
    missing_direct_door = package.model_copy(
        update={"composable_doors": package.composable_doors[1:]}
    )

    assert GeometryDiagnosticCode.PASSAGE_ENDPOINT_APPROACH_INVALID in codes(
        broken_dogleg
    )
    assert GeometryDiagnosticCode.PASSAGE_OPENING_INVALID in codes(broken_opening)
    assert GeometryDiagnosticCode.DIRECT_DOOR_NOT_SHARED_WALL in codes(
        missing_direct_door
    )


def _wrong_first_step(
    point: GridPoint,
    direction: PassageApproachDirection,
) -> GridPoint:
    if direction in {PassageApproachDirection.NORTH, PassageApproachDirection.SOUTH}:
        return GridPoint(x=point.x + 1, y=point.y)
    return GridPoint(x=point.x, y=point.y + 1)


def test_overlapping_rooms_are_reported(generated_package: DungeonPackage) -> None:
    first, second, *remaining = generated_package.rooms
    overlapping = second.model_copy(update={"boundary": first.boundary})
    broken = generated_package.model_copy(
        update={"rooms": (first, overlapping, *remaining)}
    )

    assert GeometryDiagnosticCode.ROOM_OVERLAP in codes(broken)


def test_self_intersecting_orthogonal_room_is_reported(
    generated_package: DungeonPackage,
) -> None:
    room = generated_package.rooms[0]
    crossing = PolygonGeometry(
        kind="polygon",
        points=(
            GridPoint(x=1, y=1),
            GridPoint(x=5, y=1),
            GridPoint(x=5, y=5),
            GridPoint(x=3, y=5),
            GridPoint(x=3, y=0),
            GridPoint(x=2, y=0),
            GridPoint(x=2, y=4),
            GridPoint(x=1, y=4),
        ),
    )
    broken_room = room.model_copy(update={"boundary": crossing})
    broken = generated_package.model_copy(
        update={"rooms": (broken_room, *generated_package.rooms[1:])}
    )

    assert GeometryDiagnosticCode.ROOM_POLYGON_INVALID in codes(broken)


def test_out_of_bounds_room_is_reported(generated_package: DungeonPackage) -> None:
    room = generated_package.rooms[0]
    shifted = PolygonGeometry(
        kind="polygon",
        points=tuple(
            GridPoint(x=point.x + 100, y=point.y + 100)
            for point in room.boundary.points
        ),
    )
    broken_room = room.model_copy(update={"boundary": shifted})
    broken = generated_package.model_copy(
        update={"rooms": (broken_room, *generated_package.rooms[1:])}
    )

    assert GeometryDiagnosticCode.GEOMETRY_OUT_OF_BOUNDS in codes(broken)


def test_diagonal_corridor_is_reported(generated_package: DungeonPackage) -> None:
    corridor = generated_package.corridors[0]
    start = corridor.path.points[0]
    diagonal = PolylineGeometry(
        kind="polyline",
        points=(start, GridPoint(x=start.x + 2, y=start.y + 2)),
    )
    broken_corridor = corridor.model_copy(update={"path": diagonal})
    broken = generated_package.model_copy(
        update={"corridors": (broken_corridor, *generated_package.corridors[1:])}
    )

    assert GeometryDiagnosticCode.CORRIDOR_NON_ORTHOGONAL in codes(broken)


def test_corridor_crossings_are_rejected_independently(
    generated_package: DungeonPackage,
) -> None:
    first, second, *remaining = generated_package.corridors
    crossing = second.model_copy(update={"path": first.path})
    broken = generated_package.model_copy(
        update={"corridors": (first, crossing, *remaining)}
    )

    assert GeometryDiagnosticCode.CORRIDOR_OVERLAP in codes(broken)


def test_requested_corridor_width_is_enforced(
    synthetic_package: DungeonPackage,
) -> None:
    generated_package = synthetic_package
    target_id = generated_package.corridors[0].id
    connection = next(
        item for item in generated_package.topology.connections if item.id == target_id
    )
    wider_request = connection.model_copy(update={"minimum_width_cells": 2})
    topology = generated_package.topology.model_copy(
        update={
            "connections": tuple(
                wider_request if item.id == target_id else item
                for item in generated_package.topology.connections
            )
        }
    )
    broken = generated_package.model_copy(update={"topology": topology})

    assert GeometryDiagnosticCode.CORRIDOR_WIDTH_INSUFFICIENT in codes(broken)


def test_door_must_align_with_room_wall_and_corridor(
    generated_package: DungeonPackage,
) -> None:
    door = generated_package.composable_doors[0]
    moved = door.model_copy(
        update={
            "segment": GridSegment(
                start=GridPoint(x=0, y=0),
                end=GridPoint(x=1, y=1),
            )
        }
    )
    broken = generated_package.model_copy(
        update={"composable_doors": (moved, *generated_package.composable_doors[1:])}
    )

    assert GeometryDiagnosticCode.DIRECT_DOOR_NOT_SHARED_WALL in codes(broken)


def test_stairs_and_vertical_links_must_pair_exactly(
    synthetic_package: DungeonPackage,
) -> None:
    generated_package = synthetic_package
    stair = generated_package.stairs[0]
    moved_stair = stair.model_copy(
        update={"position": GridPoint(x=stair.position.x + 1, y=stair.position.y)}
    )
    misaligned = generated_package.model_copy(
        update={"stairs": (moved_stair, *generated_package.stairs[1:])}
    )
    unpaired = generated_package.model_copy(update={"vertical_links": ()})

    assert GeometryDiagnosticCode.STAIR_ALIGNMENT_INVALID in codes(misaligned)
    assert GeometryDiagnosticCode.FLOOR_TRANSITION_UNPAIRED in codes(unpaired)


def test_grid_scale_must_be_five_feet(generated_package: DungeonPackage) -> None:
    broken = generated_package.model_copy(
        update={
            "grid": GridSpec(
                grid_type=GridType.SQUARE,
                cell_scale_feet=10,
                orthogonal=True,
            )
        }
    )

    assert GeometryDiagnosticCode.GRID_SCALE_INVALID in codes(broken)


def test_disconnected_walkable_regions_are_reported(
    synthetic_package: DungeonPackage,
) -> None:
    generated_package = synthetic_package
    corridors = tuple(
        corridor
        for corridor in generated_package.corridors
        if corridor.id != "connection_sanctum_exit"
    )
    broken = generated_package.model_copy(update={"corridors": corridors})

    assert GeometryDiagnosticCode.WALKABLE_REGION_DISCONNECTED in codes(broken)


def test_room_capacity_uses_unblocked_walkable_cells(
    generated_package: DungeonPackage,
) -> None:
    topology_room = generated_package.topology.rooms[0]
    excessive_capacity = topology_room.capacity.model_copy(
        update={
            "comfortable_occupants": 999,
            "maximum_occupants": 999,
        }
    )
    changed_topology_room = topology_room.model_copy(
        update={"capacity": excessive_capacity}
    )
    topology = generated_package.topology.model_copy(
        update={
            "rooms": (
                changed_topology_room,
                *generated_package.topology.rooms[1:],
            )
        }
    )
    exact_room = generated_package.rooms[0].model_copy(
        update={"capacity": excessive_capacity}
    )
    broken = generated_package.model_copy(
        update={
            "topology": topology,
            "rooms": (exact_room, *generated_package.rooms[1:]),
        }
    )

    assert GeometryDiagnosticCode.ROOM_CAPACITY_INSUFFICIENT in codes(broken)
