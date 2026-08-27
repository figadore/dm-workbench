"""Certificate-driven constructive Tier A room and channel allocation."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from math import ceil

from dm_dungeon.contracts.certificate import (
    RoomPortAssignmentWitness,
    TopologyCertificate,
)
from dm_dungeon.contracts.geometry import GridPoint, GridSegment, PolylineGeometry
from dm_dungeon.contracts.package import PassageApproachDirection
from dm_dungeon.contracts.topology import DungeonTopology, TopologyRoom
from dm_dungeon.layout.contracts import FloorLayoutBounds
from dm_dungeon.layout.placement import Rect
from dm_dungeon.layout.routing import PassageRoute

_ROOM_GAP_CELLS = 5
_ROCK_MARGIN_CELLS = 4


@dataclass(frozen=True, slots=True)
class ConstructiveLayout:
    """Exact baseline allocation computed before package cells are emitted."""

    bounds: FloorLayoutBounds
    room_rects: dict[str, Rect]
    passage_routes: dict[str, PassageRoute]


def required_floor_bounds(
    certificate: TopologyCertificate,
    topology: DungeonTopology,
) -> FloorLayoutBounds:
    """Return the exact proven Tier A floor bound without routing cells."""

    bounds, _ = _place_rooms(certificate, topology)
    return bounds


def construct_tier_a_layout(
    certificate: TopologyCertificate,
    topology: DungeonTopology,
) -> ConstructiveLayout:
    """Materialize the spacious guaranteed baseline; no retries or random search."""

    bounds, room_rects = _place_rooms(certificate, topology)
    ports = {item.room_id: item for item in certificate.room_ports}
    connections = {item.id: item for item in topology.connections}
    reserved_cells: set[tuple[int, int]] = set()
    routes: dict[str, PassageRoute] = {}

    for channel in certificate.connection_channels:
        connection = connections[channel.connection_id]
        source = room_rects[connection.from_room_id]
        target = room_rects[connection.to_room_id]
        source_opening = _opening_for_connection(
            source,
            ports[connection.from_room_id],
            channel.connection_id,
        )
        target_opening = _opening_for_connection(
            target,
            ports[connection.to_room_id],
            channel.connection_id,
        )
        route = _route_reserved_channel(
            source_opening,
            target_opening,
            room_rects,
            bounds,
            reserved_cells,
        )
        if route is None:
            raise RuntimeError(
                f"certified channel {channel.connection_id!r} could not be materialized"
            )
        routes[channel.connection_id] = route
        reserved_cells.update(_polyline_cells(route.path))

    return ConstructiveLayout(
        bounds=bounds,
        room_rects=room_rects,
        passage_routes=routes,
    )


def _place_rooms(
    certificate: TopologyCertificate,
    topology: DungeonTopology,
) -> tuple[FloorLayoutBounds, dict[str, Rect]]:
    if len(topology.floors) != 1:
        raise ValueError("constructive Tier A layout requires exactly one floor")

    rooms = {item.id: item for item in topology.rooms}
    demands = {item.room_id: item for item in certificate.room_demands}
    ports = {item.room_id: item for item in certificate.room_ports}
    sizes = {
        room_id: _room_size(
            rooms[room_id], demands[room_id].required_interior_cells, ports[room_id]
        )
        for room_id in rooms
    }
    embedding = {item.room_id: item for item in certificate.embedding_rooms}
    critical_ids = certificate.critical_path.room_ids
    backbone_height = max(sizes[room_id][1] for room_id in critical_ids)

    upper_branches = [item for item in certificate.branches if item.band == "upper"]
    upper_height = max(
        (
            sum(sizes[room_id][1] + _ROOM_GAP_CELLS for room_id in item.room_ids)
            for item in upper_branches
        ),
        default=0,
    )
    backbone_top = _ROCK_MARGIN_CELLS + upper_height

    raw: dict[str, Rect] = {}
    x = _ROCK_MARGIN_CELLS
    for room_id in critical_ids:
        width, height = sizes[room_id]
        raw[room_id] = Rect(
            x=x,
            y=backbone_top + (backbone_height - height) // 2,
            width=width,
            height=height,
        )
        x += width + _ROOM_GAP_CELLS

    for branch in certificate.branches:
        attachment = raw[branch.attachment_room_id]
        center_x = attachment.center[0]
        if branch.band == "upper":
            edge = attachment.y - _ROOM_GAP_CELLS
            for room_id in branch.room_ids:
                width, height = sizes[room_id]
                rect = Rect(center_x - width // 2, edge - height, width, height)
                raw[room_id] = rect
                edge = rect.y - _ROOM_GAP_CELLS
        else:
            edge = attachment.bottom + _ROOM_GAP_CELLS
            for room_id in branch.room_ids:
                width, height = sizes[room_id]
                rect = Rect(center_x - width // 2, edge, width, height)
                raw[room_id] = rect
                edge = rect.bottom + _ROOM_GAP_CELLS

    # Every certified room must be embedded exactly once; use the witness here so a
    # future grammar extension cannot silently fall through this Tier A allocator.
    if set(raw) != set(embedding):
        raise ValueError(
            "certificate embedding does not describe one Tier A room layout"
        )

    min_x = min(rect.x for rect in raw.values())
    min_y = min(rect.y for rect in raw.values())
    shift_x = max(0, _ROCK_MARGIN_CELLS - min_x)
    shift_y = max(0, _ROCK_MARGIN_CELLS - min_y)
    placed = {
        room_id: Rect(
            rect.x + shift_x,
            rect.y + shift_y,
            rect.width,
            rect.height,
        )
        for room_id, rect in raw.items()
    }
    width = max(rect.right for rect in placed.values()) + _ROCK_MARGIN_CELLS
    height = max(rect.bottom for rect in placed.values()) + _ROCK_MARGIN_CELLS
    floor_id = topology.floors[0].id
    return (
        FloorLayoutBounds(
            floor_id=floor_id,
            width_cells=width,
            height_cells=height,
            margin_cells=_ROCK_MARGIN_CELLS,
        ),
        placed,
    )


def _room_size(
    room: TopologyRoom,
    required_area: int,
    ports: RoomPortAssignmentWitness,
) -> tuple[int, int]:
    north_south = max(
        _side_length(len(ports.north_connection_ids)),
        _side_length(len(ports.south_connection_ids)),
    )
    east_west = max(
        _side_length(len(ports.east_connection_ids)),
        _side_length(len(ports.west_connection_ids)),
    )
    constraints = room.size
    maximum_width = constraints.maximum_width_cells or max(
        constraints.minimum_width_cells, north_south, required_area
    )
    maximum_height = constraints.maximum_height_cells or max(
        constraints.minimum_height_cells, east_west, required_area
    )
    candidates: list[tuple[int, int, int]] = []
    for width in range(
        max(constraints.minimum_width_cells, north_south), maximum_width + 1
    ):
        minimum_height = max(
            constraints.minimum_height_cells,
            east_west,
            ceil(required_area / width),
            ceil(constraints.minimum_area_cells / width),
        )
        for height in range(minimum_height, maximum_height + 1):
            area = width * height
            if (
                constraints.maximum_area_cells is not None
                and area > constraints.maximum_area_cells
            ):
                continue
            candidates.append((area, width, height))
    if not candidates:
        raise ValueError(
            f"room {room.id!r} cannot satisfy certified side/interior demand"
        )
    _, width, height = min(candidates)
    return width, height


def _side_length(port_count: int) -> int:
    return 0 if port_count == 0 else 2 * port_count - 1


@dataclass(frozen=True, slots=True)
class _Opening:
    segment: GridSegment
    direction: PassageApproachDirection


def _opening_for_connection(
    rect: Rect,
    ports: RoomPortAssignmentWitness,
    connection_id: str,
) -> _Opening:
    side_values = (
        ("north", ports.north_connection_ids),
        ("east", ports.east_connection_ids),
        ("south", ports.south_connection_ids),
        ("west", ports.west_connection_ids),
    )
    side, connection_ids = next(
        (side, values) for side, values in side_values if connection_id in values
    )
    slot = connection_ids.index(connection_id)
    count = len(connection_ids)
    if side in {"north", "south"}:
        start_x = rect.x + (rect.width - _side_length(count)) // 2 + 2 * slot
        y = rect.y if side == "north" else rect.bottom
        return _Opening(
            segment=GridSegment(
                start=GridPoint(x=start_x, y=y),
                end=GridPoint(x=start_x + 1, y=y),
            ),
            direction=(
                PassageApproachDirection.NORTH
                if side == "north"
                else PassageApproachDirection.SOUTH
            ),
        )
    start_y = rect.y + (rect.height - _side_length(count)) // 2 + 2 * slot
    x = rect.right if side == "east" else rect.x
    return _Opening(
        segment=GridSegment(
            start=GridPoint(x=x, y=start_y),
            end=GridPoint(x=x, y=start_y + 1),
        ),
        direction=(
            PassageApproachDirection.EAST
            if side == "east"
            else PassageApproachDirection.WEST
        ),
    )


def _route_reserved_channel(
    source: _Opening,
    target: _Opening,
    rooms: dict[str, Rect],
    bounds: FloorLayoutBounds,
    reserved_cells: set[tuple[int, int]],
) -> PassageRoute | None:
    start, start_lead = _endpoint_cells(source)
    end, end_lead = _endpoint_cells(target)
    allowed = {start, start_lead, end, end_lead}
    blocked = _room_halo_cells(rooms.values()) | reserved_cells
    blocked -= allowed
    middle = _bfs(start_lead, end_lead, blocked, bounds)
    if middle is None:
        return None
    full = _deduplicate((start, start_lead, *middle, end_lead, end))
    compressed = _compress(full)
    return PassageRoute(
        path=PolylineGeometry(
            kind="polyline",
            points=tuple(GridPoint(x=x, y=y) for x, y in compressed),
        ),
        from_segment=source.segment,
        from_direction=source.direction,
        to_segment=target.segment,
        to_direction=target.direction,
    )


def _endpoint_cells(opening: _Opening) -> tuple[tuple[int, int], tuple[int, int]]:
    x = opening.segment.start.x
    y = opening.segment.start.y
    delta = {
        PassageApproachDirection.NORTH: (0, -1),
        PassageApproachDirection.EAST: (1, 0),
        PassageApproachDirection.SOUTH: (0, 1),
        PassageApproachDirection.WEST: (-1, 0),
    }[opening.direction]
    exterior = (
        x if delta[0] >= 0 else x - 1,
        y if delta[1] >= 0 else y - 1,
    )
    return exterior, (exterior[0] + delta[0], exterior[1] + delta[1])


def _room_halo_cells(rectangles: Iterable[Rect]) -> set[tuple[int, int]]:
    return {
        (x, y)
        for rect in rectangles
        for x in range(rect.x - 1, rect.right + 1)
        for y in range(rect.y - 1, rect.bottom + 1)
    }


def _bfs(
    start: tuple[int, int],
    end: tuple[int, int],
    blocked: set[tuple[int, int]],
    bounds: FloorLayoutBounds,
) -> tuple[tuple[int, int], ...] | None:
    directions = ((1, 0), (0, 1), (-1, 0), (0, -1))
    pending = deque((start,))
    previous: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    while pending:
        point = pending.popleft()
        if point == end:
            path = [end]
            while previous[path[-1]] is not None:
                prior = previous[path[-1]]
                assert prior is not None
                path.append(prior)
            return tuple(reversed(path))
        for dx, dy in directions:
            neighbor = (point[0] + dx, point[1] + dy)
            if (
                neighbor in previous
                or neighbor in blocked
                or neighbor[0] < 0
                or neighbor[1] < 0
                or neighbor[0] >= bounds.width_cells
                or neighbor[1] >= bounds.height_cells
            ):
                continue
            previous[neighbor] = point
            pending.append(neighbor)
    return None


def _deduplicate(points: tuple[tuple[int, int], ...]) -> tuple[tuple[int, int], ...]:
    return tuple(
        point
        for index, point in enumerate(points)
        if index == 0 or point != points[index - 1]
    )


def _compress(path: tuple[tuple[int, int], ...]) -> tuple[tuple[int, int], ...]:
    if len(path) <= 2:
        return path
    compressed = [path[0]]
    prior = (path[1][0] - path[0][0], path[1][1] - path[0][1])
    for index in range(1, len(path) - 1):
        direction = (
            path[index + 1][0] - path[index][0],
            path[index + 1][1] - path[index][1],
        )
        if direction != prior:
            compressed.append(path[index])
            prior = direction
    compressed.append(path[-1])
    return tuple(compressed)


def _polyline_cells(path: PolylineGeometry) -> set[tuple[int, int]]:
    cells: set[tuple[int, int]] = set()
    for first, second in zip(path.points, path.points[1:], strict=False):
        if first.x == second.x:
            for y in range(min(first.y, second.y), max(first.y, second.y) + 1):
                cells.add((first.x, y))
        else:
            for x in range(min(first.x, second.x), max(first.x, second.x) + 1):
                cells.add((x, first.y))
    return cells
