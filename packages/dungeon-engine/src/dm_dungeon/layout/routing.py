"""Deterministic orthogonal connection routing between placed rooms."""

from collections import deque
from dataclasses import dataclass

from dm_dungeon.contracts.geometry import GridPoint, GridSegment, PolylineGeometry
from dm_dungeon.contracts.package_v2 import PassageApproachDirection
from dm_dungeon.layout.contracts import FloorLayoutBounds
from dm_dungeon.layout.placement import Rect
from dm_dungeon.layout.random_source import DeterministicRandom

_UNRELATED_ROOM_CLEARANCE_CELLS = 1
_ENDPOINT_LEAD_CELLS = 1


@dataclass(frozen=True, slots=True)
class PassageRoute:
    """A routed passage plus its two explicit room-wall opening records."""

    path: PolylineGeometry
    from_segment: GridSegment
    from_direction: PassageApproachDirection
    to_segment: GridSegment
    to_direction: PassageApproachDirection


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


def route_passage_between_rooms(
    source: Rect,
    target: Rect,
    all_rooms: tuple[Rect, ...],
    bounds: FloorLayoutBounds,
    width_cells: int,
    random_source: DeterministicRandom,
) -> PassageRoute | None:
    """Route a P7-13 passage with explicit perpendicular endpoint leads.

    Each candidate starts in the exterior cell immediately beyond a one-cell room
    opening, then takes one additional cell in the declared outward direction.
    That lead makes a turn at a doorway or its first exterior cell impossible.
    All candidates are scored rather than accepting the first BFS result.
    """
    endpoints = tuple(_passage_endpoints(source))
    target_endpoints = tuple(_passage_endpoints(target))
    candidates = [
        (from_endpoint, to_endpoint)
        for from_endpoint in endpoints
        for to_endpoint in target_endpoints
    ]
    random_source.shuffle(candidates)
    directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    random_source.shuffle(directions)
    routes: list[tuple[tuple[int, int, int, int], PassageRoute]] = []

    for tie_break, (from_endpoint, to_endpoint) in enumerate(candidates):
        start, start_lead = _endpoint_cells(from_endpoint)
        end, end_lead = _endpoint_cells(to_endpoint)
        endpoint_cells = (start, start_lead, end, end_lead)
        if not all(_cell_in_bounds(cell, bounds) for cell in endpoint_cells):
            continue
        if any(cell in _room_interior_cells(all_rooms) for cell in endpoint_cells):
            continue
        unrelated_rooms = tuple(
            rect for rect in all_rooms if rect not in {source, target}
        )
        if any(
            cell in _blocked_passage_points(unrelated_rooms, width_cells)
            for cell in endpoint_cells
        ):
            continue
        blocked = _blocked_passage_points(all_rooms, width_cells)
        blocked.difference_update((start, start_lead, end, end_lead))
        middle = _breadth_first_route(
            start_lead,
            end_lead,
            blocked,
            bounds,
            directions,
        )
        if middle is None:
            continue
        path = _join_passage_path(start, start_lead, middle, end_lead, end)
        compressed = _compress_path(path)
        route = PassageRoute(
            path=PolylineGeometry(
                kind="polyline",
                points=tuple(GridPoint(x=x, y=y) for x, y in compressed),
            ),
            from_segment=from_endpoint.segment,
            from_direction=from_endpoint.direction,
            to_segment=to_endpoint.segment,
            to_direction=to_endpoint.direction,
        )
        routes.append(
            (
                (
                    _bend_count(compressed),
                    len(path) - 1,
                    -_unrelated_clearance(path, source, target, all_rooms),
                    tie_break,
                ),
                route,
            )
        )
    if not routes:
        return None
    return min(routes, key=lambda item: item[0])[1]


@dataclass(frozen=True, slots=True)
class _PassageEndpoint:
    segment: GridSegment
    direction: PassageApproachDirection


def passage_endpoint_at_exterior_cell(
    rect: Rect,
    cell: GridPoint,
) -> tuple[GridSegment, PassageApproachDirection] | None:
    """Recover a declared opening from a locked corridor endpoint cell."""
    for endpoint in _passage_endpoints(rect):
        exterior, _lead = _endpoint_cells(endpoint)
        if exterior == (cell.x, cell.y):
            return endpoint.segment, endpoint.direction
    return None


def _passage_endpoints(rect: Rect) -> tuple[_PassageEndpoint, ...]:
    endpoints: list[_PassageEndpoint] = []
    for y in range(rect.y, rect.bottom):
        endpoints.extend(
            (
                _PassageEndpoint(
                    GridSegment(
                        start=GridPoint(x=rect.x, y=y),
                        end=GridPoint(x=rect.x, y=y + 1),
                    ),
                    PassageApproachDirection.WEST,
                ),
                _PassageEndpoint(
                    GridSegment(
                        start=GridPoint(x=rect.right, y=y),
                        end=GridPoint(x=rect.right, y=y + 1),
                    ),
                    PassageApproachDirection.EAST,
                ),
            )
        )
    for x in range(rect.x, rect.right):
        endpoints.extend(
            (
                _PassageEndpoint(
                    GridSegment(
                        start=GridPoint(x=x, y=rect.y),
                        end=GridPoint(x=x + 1, y=rect.y),
                    ),
                    PassageApproachDirection.NORTH,
                ),
                _PassageEndpoint(
                    GridSegment(
                        start=GridPoint(x=x, y=rect.bottom),
                        end=GridPoint(x=x + 1, y=rect.bottom),
                    ),
                    PassageApproachDirection.SOUTH,
                ),
            )
        )
    return tuple(endpoints)


def _endpoint_cells(
    endpoint: _PassageEndpoint,
) -> tuple[tuple[int, int], tuple[int, int]]:
    segment = endpoint.segment
    if endpoint.direction is PassageApproachDirection.NORTH:
        cell = (segment.start.x, segment.start.y - 1)
        return cell, (cell[0], cell[1] - _ENDPOINT_LEAD_CELLS)
    if endpoint.direction is PassageApproachDirection.EAST:
        cell = (segment.start.x, segment.start.y)
        return cell, (cell[0] + _ENDPOINT_LEAD_CELLS, cell[1])
    if endpoint.direction is PassageApproachDirection.SOUTH:
        cell = (segment.start.x, segment.start.y)
        return cell, (cell[0], cell[1] + _ENDPOINT_LEAD_CELLS)
    cell = (segment.start.x - 1, segment.start.y)
    return cell, (cell[0] - _ENDPOINT_LEAD_CELLS, cell[1])


def _room_interior_cells(rectangles: tuple[Rect, ...]) -> set[tuple[int, int]]:
    return {
        (x, y)
        for rect in rectangles
        for x in range(rect.x, rect.right)
        for y in range(rect.y, rect.bottom)
    }


def _blocked_passage_points(
    rectangles: tuple[Rect, ...], width_cells: int
) -> set[tuple[int, int]]:
    """Block room interiors and wall-adjacent cells except declared endpoints."""
    reach = _UNRELATED_ROOM_CLEARANCE_CELLS + width_cells // 2
    return {
        (x, y)
        for rect in rectangles
        for x in range(rect.x - reach, rect.right + reach)
        for y in range(rect.y - reach, rect.bottom + reach)
    }


def _cell_in_bounds(cell: tuple[int, int], bounds: FloorLayoutBounds) -> bool:
    return 0 <= cell[0] < bounds.width_cells and 0 <= cell[1] < bounds.height_cells


def _join_passage_path(
    start: tuple[int, int],
    start_lead: tuple[int, int],
    middle: tuple[tuple[int, int], ...],
    end_lead: tuple[int, int],
    end: tuple[int, int],
) -> tuple[tuple[int, int], ...]:
    points = (start, start_lead, *middle, end_lead, end)
    return tuple(
        point
        for index, point in enumerate(points)
        if index == 0 or point != points[index - 1]
    )


def _bend_count(path: tuple[tuple[int, int], ...]) -> int:
    return max(0, len(_compress_path(path)) - 2)


def _unrelated_clearance(
    path: tuple[tuple[int, int], ...],
    source: Rect,
    target: Rect,
    all_rooms: tuple[Rect, ...],
) -> int:
    unrelated = tuple(rect for rect in all_rooms if rect not in {source, target})
    if not unrelated:
        return 0
    return min(
        abs(x - room_x) + abs(y - room_y)
        for x, y in path
        for rect in unrelated
        for room_x in range(rect.x, rect.right)
        for room_y in range(rect.y, rect.bottom)
    )


def door_segment_between_rects(source: Rect, target: Rect) -> GridSegment | None:
    """Return the centered one-cell opening on a shared room wall."""

    if source.right == target.x or target.right == source.x:
        wall_x = source.right if source.right == target.x else target.right
        start = max(source.y, target.y)
        end = min(source.bottom, target.bottom)
        if end - start < 1:
            return None
        y = start + (end - start - 1) // 2
        return GridSegment(
            start=GridPoint(x=wall_x, y=y),
            end=GridPoint(x=wall_x, y=y + 1),
        )
    if source.bottom == target.y or target.bottom == source.y:
        wall_y = source.bottom if source.bottom == target.y else target.bottom
        start = max(source.x, target.x)
        end = min(source.right, target.right)
        if end - start < 1:
            return None
        x = start + (end - start - 1) // 2
        return GridSegment(
            start=GridPoint(x=x, y=wall_y),
            end=GridPoint(x=x + 1, y=wall_y),
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
