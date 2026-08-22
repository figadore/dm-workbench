"""Regression coverage for width-aware deterministic corridor routing."""

from dm_dungeon.contracts import GridPoint, PassageApproachDirection
from dm_dungeon.layout.contracts import FloorLayoutBounds
from dm_dungeon.layout.placement import Rect
from dm_dungeon.layout.random_source import DeterministicRandom
from dm_dungeon.layout.routing import (
    _breadth_first_route,
    route_between_rooms,
    route_passage_between_rooms,
)
from dm_dungeon.validation.grid import cells_for_corridor


def test_passage_routes_from_explicit_openings_with_endpoint_leads() -> None:
    source = Rect(x=2, y=5, width=3, height=3)
    target = Rect(x=15, y=5, width=3, height=3)
    unrelated = Rect(x=9, y=4, width=3, height=5)
    route = route_passage_between_rooms(
        source,
        target,
        (source, target, unrelated),
        FloorLayoutBounds(
            floor_id="floor_test",
            width_cells=22,
            height_cells=14,
        ),
        width_cells=1,
        random_source=DeterministicRandom(7, "orthogonal-v1"),
    )

    assert route is not None
    path = route.path.points
    assert len(path) >= 3  # The blocker forces an explainable bend.
    assert _direction(path[0], path[1]) is route.from_direction
    assert _direction(path[-1], path[-2]) is route.to_direction
    corridor_cells = cells_for_corridor(route.path, width_cells=1)
    room_cells = {
        (x, y)
        for rect in (source, target, unrelated)
        for x in range(rect.x, rect.right)
        for y in range(rect.y, rect.bottom)
    }
    assert corridor_cells.isdisjoint(room_cells)


def _direction(first: GridPoint, second: GridPoint) -> PassageApproachDirection:
    first_x, first_y = first.x, first.y
    second_x, second_y = second.x, second.y
    if second_y < first_y:
        return PassageApproachDirection.NORTH
    if second_x > first_x:
        return PassageApproachDirection.EAST
    if second_y > first_y:
        return PassageApproachDirection.SOUTH
    return PassageApproachDirection.WEST


def test_router_never_enters_the_exclusive_floor_boundary() -> None:
    bounds = FloorLayoutBounds(
        floor_id="floor_test",
        width_cells=2,
        height_cells=2,
    )

    route = _breadth_first_route(
        (0, 0),
        (2, 0),
        blocked=set(),
        bounds=bounds,
        directions=[(1, 0), (0, 1), (-1, 0), (0, -1)],
    )

    assert route is None


def test_wide_corridor_does_not_clip_an_adjacent_unrelated_room() -> None:
    source = Rect(x=1, y=4, width=3, height=3)
    target = Rect(x=15, y=4, width=3, height=3)
    unrelated = Rect(x=8, y=6, width=3, height=2)
    route = route_between_rooms(
        source,
        target,
        (source, target, unrelated),
        FloorLayoutBounds(
            floor_id="floor_test",
            width_cells=22,
            height_cells=12,
        ),
        width_cells=3,
        random_source=DeterministicRandom(7, "orthogonal-v1"),
    )

    assert route is not None
    corridor_cells = cells_for_corridor(route, width_cells=3)
    unrelated_cells = {
        (x, y)
        for x in range(unrelated.x, unrelated.right)
        for y in range(unrelated.y, unrelated.bottom)
    }
    assert corridor_cells.isdisjoint(unrelated_cells)


def test_corridor_leaves_clearance_from_an_unrelated_room_wall() -> None:
    source = Rect(x=1, y=4, width=3, height=3)
    target = Rect(x=15, y=4, width=3, height=3)
    unrelated = Rect(x=8, y=6, width=3, height=2)
    route = route_between_rooms(
        source,
        target,
        (source, target, unrelated),
        FloorLayoutBounds(
            floor_id="floor_test",
            width_cells=22,
            height_cells=12,
        ),
        width_cells=1,
        random_source=DeterministicRandom(7, "orthogonal-v1"),
    )

    assert route is not None
    corridor_cells = cells_for_corridor(route, width_cells=1)
    unrelated_cells = {
        (x, y)
        for x in range(unrelated.x, unrelated.right)
        for y in range(unrelated.y, unrelated.bottom)
    }
    # The shortest old route ran along y=5 directly against the room beginning
    # at y=6. That looks like an undeclared doorway in a rendered map.
    assert all(
        abs(corridor_x - room_x) + abs(corridor_y - room_y) > 1
        for corridor_x, corridor_y in corridor_cells
        for room_x, room_y in unrelated_cells
    )
