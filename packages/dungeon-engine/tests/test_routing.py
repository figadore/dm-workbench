"""Regression coverage for width-aware deterministic corridor routing."""

from dm_dungeon.layout.contracts import FloorLayoutBounds
from dm_dungeon.layout.placement import Rect
from dm_dungeon.layout.random_source import DeterministicRandom
from dm_dungeon.layout.routing import route_between_rooms
from dm_dungeon.validation.grid import cells_for_corridor


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
        random_source=DeterministicRandom(7, "orthogonal-v2"),
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
        random_source=DeterministicRandom(7, "orthogonal-v2"),
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
