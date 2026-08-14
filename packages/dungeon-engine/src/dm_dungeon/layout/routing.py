"""Deterministic orthogonal connection routing between placed rooms."""

from collections import deque

from dm_dungeon.contracts.geometry import GridPoint, GridSegment, PolylineGeometry
from dm_dungeon.layout.contracts import FloorLayoutBounds
from dm_dungeon.layout.placement import Rect
from dm_dungeon.layout.random_source import DeterministicRandom

_UNRELATED_ROOM_CLEARANCE_CELLS = 1


def route_between_rooms(
    source: Rect,
    target: Rect,
    all_rooms: tuple[Rect, ...],
    bounds: FloorLayoutBounds,
    width_cells: int,
    random_source: DeterministicRandom,
) -> PolylineGeometry | None:
    """Route an orthogonal corridor footprint between room-boundary anchors."""
    anchor_pairs = [
        (source_anchor, target_anchor)
        for source_anchor in _boundary_anchors(source)
        for target_anchor in _boundary_anchors(target)
        if source_anchor != target_anchor
    ]
    random_source.shuffle(anchor_pairs)
    anchor_pairs.sort(key=lambda pair: _manhattan(*pair))

    blocked = _blocked_room_points(all_rooms, source, target, width_cells)
    directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    random_source.shuffle(directions)
    for start, end in anchor_pairs:
        path = _breadth_first_route(
            start,
            end,
            blocked - {start, end},
            bounds,
            directions,
        )
        if path is not None:
            return PolylineGeometry(
                kind="polyline",
                points=tuple(GridPoint(x=x, y=y) for x, y in _compress_path(path)),
            )
    return None


def door_segment_at_anchor(room: Rect, anchor: GridPoint) -> GridSegment | None:
    """Create a one-cell door segment aligned to a room boundary anchor."""
    if anchor.x in {room.x, room.right} and room.y <= anchor.y <= room.bottom:
        start_y = min(max(anchor.y, room.y), room.bottom - 1)
        return GridSegment(
            start=GridPoint(x=anchor.x, y=start_y),
            end=GridPoint(x=anchor.x, y=start_y + 1),
        )
    if anchor.y in {room.y, room.bottom} and room.x <= anchor.x <= room.right:
        start_x = min(max(anchor.x, room.x), room.right - 1)
        return GridSegment(
            start=GridPoint(x=start_x, y=anchor.y),
            end=GridPoint(x=start_x + 1, y=anchor.y),
        )
    return None


def _boundary_anchors(rect: Rect) -> tuple[tuple[int, int], ...]:
    center_x, center_y = rect.center
    return tuple(
        dict.fromkeys(
            (
                (rect.x, center_y),
                (rect.right, center_y),
                (center_x, rect.y),
                (center_x, rect.bottom),
            )
        )
    )


def _blocked_room_points(
    rectangles: tuple[Rect, ...],
    source: Rect,
    target: Rect,
    width_cells: int,
) -> set[tuple[int, int]]:
    """Reserve every centerline point whose corridor footprint hits another room."""

    negative_offset = (width_cells - 1) // 2
    positive_offset = width_cells // 2
    blocked: set[tuple[int, int]] = set()
    for rect in rectangles:
        if rect in {source, target}:
            # An endpoint must be allowed to meet either connected room.
            blocked.update(
                (x, y)
                for x in range(rect.x + 1, rect.right)
                for y in range(rect.y + 1, rect.bottom)
            )
            continue
        for x in range(
            rect.x - _UNRELATED_ROOM_CLEARANCE_CELLS,
            rect.right + _UNRELATED_ROOM_CLEARANCE_CELLS,
        ):
            for y in range(
                rect.y - _UNRELATED_ROOM_CLEARANCE_CELLS,
                rect.bottom + _UNRELATED_ROOM_CLEARANCE_CELLS,
            ):
                # Horizontal corridors expand over y offsets; vertical corridors over
                # x offsets. Reserving both directions is conservative but guarantees
                # a later turn cannot sweep through unrelated room cells. The one-cell
                # halo also prevents a corridor from reading as an undeclared doorway
                # when it runs flush along another room's wall.
                blocked.update(
                    (x - offset, y)
                    for offset in range(-negative_offset, positive_offset + 1)
                )
                blocked.update(
                    (x, y - offset)
                    for offset in range(-negative_offset, positive_offset + 1)
                )
    return blocked


def _breadth_first_route(
    start: tuple[int, int],
    end: tuple[int, int],
    blocked: set[tuple[int, int]],
    bounds: FloorLayoutBounds,
    directions: list[tuple[int, int]],
) -> tuple[tuple[int, int], ...] | None:
    pending = deque((start,))
    previous: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    while pending:
        point = pending.popleft()
        if point == end:
            return _reconstruct_path(previous, end)
        for delta_x, delta_y in directions:
            neighbor = (point[0] + delta_x, point[1] + delta_y)
            if (
                neighbor in previous
                or neighbor in blocked
                or neighbor[0] < 0
                or neighbor[1] < 0
                or neighbor[0] > bounds.width_cells
                or neighbor[1] > bounds.height_cells
            ):
                continue
            previous[neighbor] = point
            pending.append(neighbor)
    return None


def _reconstruct_path(
    previous: dict[tuple[int, int], tuple[int, int] | None],
    end: tuple[int, int],
) -> tuple[tuple[int, int], ...]:
    reversed_path = [end]
    current = end
    while previous[current] is not None:
        predecessor = previous[current]
        assert predecessor is not None
        reversed_path.append(predecessor)
        current = predecessor
    return tuple(reversed(reversed_path))


def _compress_path(
    path: tuple[tuple[int, int], ...],
) -> tuple[tuple[int, int], ...]:
    if len(path) <= 2:
        return path
    compressed = [path[0]]
    previous_direction = (
        path[1][0] - path[0][0],
        path[1][1] - path[0][1],
    )
    for index in range(1, len(path) - 1):
        direction = (
            path[index + 1][0] - path[index][0],
            path[index + 1][1] - path[index][1],
        )
        if direction != previous_direction:
            compressed.append(path[index])
            previous_direction = direction
    compressed.append(path[-1])
    return tuple(compressed)


def _manhattan(first: tuple[int, int], second: tuple[int, int]) -> int:
    return abs(first[0] - second[0]) + abs(first[1] - second[1])
