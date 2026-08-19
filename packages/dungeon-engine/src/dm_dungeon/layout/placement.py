"""Deterministic graph-guided orthogonal room placement."""

from dataclasses import dataclass
from math import ceil, sqrt

from dm_dungeon.contracts.geometry import (
    GridPoint,
    PolygonGeometry,
    RectangleGeometry,
    RoomLayout,
)
from dm_dungeon.contracts.topology import (
    DungeonTopology,
    RoomSizeConstraints,
    TopologyFloor,
    TopologyRoom,
)
from dm_dungeon.layout.contracts import FloorLayoutBounds
from dm_dungeon.layout.random_source import DeterministicRandom


@dataclass(frozen=True, slots=True)
class Rect:
    """Internal integer rectangle represented by origin and cell dimensions."""

    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)


def default_floor_bounds(
    floor: TopologyFloor,
    rooms: tuple[TopologyRoom, ...],
) -> FloorLayoutBounds:
    """Choose deterministic spacious bounds from minimum requested room areas."""
    minimum_area = sum(room.size.minimum_area_cells for room in rooms)
    spacing_area = max(minimum_area * 3, floor.target_room_count * 36)
    side = max(20, ceil(sqrt(spacing_area)) + 4)
    width = side + max(0, len(rooms) - 3) * 2
    height = side
    return FloorLayoutBounds(
        floor_id=floor.id,
        width_cells=width,
        height_cells=height,
        margin_cells=1,
    )


def rectangle_from_floor_bounds(bounds: FloorLayoutBounds) -> RectangleGeometry:
    """Convert floor bounds to exact renderer-neutral geometry."""
    return RectangleGeometry(
        kind="rectangle",
        origin=GridPoint(x=0, y=0),
        width_cells=bounds.width_cells,
        height_cells=bounds.height_cells,
    )


def rect_from_room_layout(room: RoomLayout) -> Rect | None:
    """Return a rectangle only when a locked room is exactly rectangular."""
    points = room.boundary.points
    xs = {point.x for point in points}
    ys = {point.y for point in points}
    if len(points) != 4 or len(xs) != 2 or len(ys) != 2:
        return None
    left, right = min(xs), max(xs)
    top, bottom = min(ys), max(ys)
    expected = {
        (left, top),
        (right, top),
        (right, bottom),
        (left, bottom),
    }
    if {(point.x, point.y) for point in points} != expected:
        return None
    if left == right or top == bottom:
        return None
    return Rect(left, top, right - left, bottom - top)


def polygon_from_rect(rect: Rect) -> PolygonGeometry:
    """Convert an internal rectangle to a four-corner polygon."""
    return PolygonGeometry(
        kind="polygon",
        points=(
            GridPoint(x=rect.x, y=rect.y),
            GridPoint(x=rect.right, y=rect.y),
            GridPoint(x=rect.right, y=rect.bottom),
            GridPoint(x=rect.x, y=rect.bottom),
        ),
    )


def place_floor_rooms(
    topology: DungeonTopology,
    floor: TopologyFloor,
    rooms: tuple[TopologyRoom, ...],
    bounds: FloorLayoutBounds,
    locked_rooms: tuple[RoomLayout, ...],
    random_source: DeterministicRandom,
    maximum_attempts: int,
    *,
    direct_door_pairs: frozenset[frozenset[str]] = frozenset(),
) -> tuple[dict[str, Rect] | None, str | None]:
    """Place one floor's rooms with bounded deterministic retries."""
    locked_rects: dict[str, Rect] = {}
    room_by_id = {room.id: room for room in rooms}
    for locked_room in locked_rooms:
        room = room_by_id.get(locked_room.id)
        if room is None:
            return None, f"Locked room {locked_room.id!r} is not on floor {floor.id!r}."
        rect = rect_from_room_layout(locked_room)
        if rect is None:
            return None, f"Locked room {locked_room.id!r} is not rectangular."
        if not _rect_fits_bounds(rect, bounds):
            return None, f"Locked room {locked_room.id!r} is outside floor bounds."
        if not _size_satisfies(rect, room.size):
            return None, f"Locked room {locked_room.id!r} violates size constraints."
        if any(
            _rects_conflict(
                rect,
                other,
                padding=0
                if frozenset((locked_room.id, other_id)) in direct_door_pairs
                else 1,
            )
            for other_id, other in locked_rects.items()
        ):
            return None, f"Locked room {locked_room.id!r} overlaps another lock."
        locked_rects[locked_room.id] = rect

    order = _graph_guided_room_order(topology, floor.id, rooms, random_source)
    unlocked = tuple(room for room in order if room.id not in locked_rects)
    if not unlocked:
        return locked_rects, None

    for _attempt in range(maximum_attempts):
        placed = dict(locked_rects)
        attempt_failed = False
        for room in unlocked:
            candidate = _choose_room_candidate(
                room,
                bounds,
                placed,
                topology,
                random_source,
                direct_door_pairs,
            )
            if candidate is None:
                attempt_failed = True
                break
            placed[room.id] = candidate
        if not attempt_failed:
            return placed, None

    return (
        None,
        f"Could not place all rooms on floor {floor.id!r} in "
        f"{maximum_attempts} deterministic attempts.",
    )


def _graph_guided_room_order(
    topology: DungeonTopology,
    floor_id: str,
    rooms: tuple[TopologyRoom, ...],
    random_source: DeterministicRandom,
) -> tuple[TopologyRoom, ...]:
    room_by_id = {room.id: room for room in rooms}
    adjacency = {room.id: set[str]() for room in rooms}
    for connection in topology.connections:
        if connection.from_room_id in adjacency and connection.to_room_id in adjacency:
            adjacency[connection.from_room_id].add(connection.to_room_id)
            adjacency[connection.to_room_id].add(connection.from_room_id)

    roots = sorted(
        rooms,
        key=lambda room: (
            0 if room.role.value == "entrance" else 1,
            room.id,
        ),
    )
    if not roots:
        return ()

    ordered: list[TopologyRoom] = []
    visited: set[str] = set()
    pending = [roots[0].id]
    while pending:
        room_id = pending.pop(0)
        if room_id in visited:
            continue
        visited.add(room_id)
        ordered.append(room_by_id[room_id])
        neighbors = sorted(adjacency[room_id])
        random_source.shuffle(neighbors)
        pending.extend(neighbors)

    remaining = sorted(set(room_by_id) - visited)
    random_source.shuffle(remaining)
    ordered.extend(room_by_id[room_id] for room_id in remaining)
    return tuple(ordered)


def _choose_room_candidate(
    room: TopologyRoom,
    bounds: FloorLayoutBounds,
    placed: dict[str, Rect],
    topology: DungeonTopology,
    random_source: DeterministicRandom,
    direct_door_pairs: frozenset[frozenset[str]],
) -> Rect | None:
    size_options = _size_options(room.size, bounds)
    random_source.shuffle(size_options)
    candidates: list[tuple[int, int, int, int, int, int, Rect]] = []
    connected_placed_ids = {
        other_id
        for connection in topology.connections
        for other_id in _other_endpoint(
            connection.from_room_id, connection.to_room_id, room.id
        )
        if other_id in placed
    }

    for width, height in size_options:
        max_x = bounds.width_cells - bounds.margin_cells - width
        max_y = bounds.height_cells - bounds.margin_cells - height
        for y in range(bounds.margin_cells, max_y + 1):
            for x in range(bounds.margin_cells, max_x + 1):
                candidate = Rect(x, y, width, height)
                if any(
                    _rects_conflict(
                        candidate,
                        existing,
                        padding=0
                        if frozenset((room.id, existing_id)) in direct_door_pairs
                        else 1,
                    )
                    for existing_id, existing in placed.items()
                ):
                    continue
                direct_neighbors = tuple(
                    existing
                    for existing_id, existing in placed.items()
                    if frozenset((room.id, existing_id)) in direct_door_pairs
                )
                if direct_neighbors and not all(
                    _shared_wall_length(candidate, existing) >= 1
                    for existing in direct_neighbors
                ):
                    continue
                score = _placement_score(
                    candidate,
                    connected_placed_ids,
                    placed,
                    bounds,
                )
                candidates.append((*score, y, x, width, height, candidate))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[:6])
    window = candidates[: min(24, len(candidates))]
    return random_source.choice(window)[6]


def _other_endpoint(
    from_room_id: str, to_room_id: str, room_id: str
) -> tuple[str, ...]:
    if from_room_id == room_id:
        return (to_room_id,)
    if to_room_id == room_id:
        return (from_room_id,)
    return ()


def _placement_score(
    candidate: Rect,
    connected_room_ids: set[str],
    placed: dict[str, Rect],
    bounds: FloorLayoutBounds,
) -> tuple[int, int]:
    """Rank compact occupied bounds before local graph distance.

    A bounded random choice among the best candidates still gives seeded variety,
    but it cannot spread a sparse graph across its whole floor band merely because
    every candidate has a similar connection distance.
    """
    occupied = (*placed.values(), candidate)
    compact_area = (
        max(rect.right for rect in occupied) - min(rect.x for rect in occupied)
    ) * (max(rect.bottom for rect in occupied) - min(rect.y for rect in occupied))
    candidate_x, candidate_y = candidate.center
    if connected_room_ids:
        connection_distance = sum(
            abs(candidate_x - placed[room_id].center[0])
            + abs(candidate_y - placed[room_id].center[1])
            for room_id in sorted(connected_room_ids)
        )
    else:
        floor_center_x = bounds.width_cells // 2
        floor_center_y = bounds.height_cells // 2
        connection_distance = abs(candidate_x - floor_center_x) + abs(
            candidate_y - floor_center_y
        )
    return compact_area, connection_distance


def _size_options(
    constraints: RoomSizeConstraints,
    bounds: FloorLayoutBounds,
) -> list[tuple[int, int]]:
    maximum_width = min(
        constraints.maximum_width_cells
        if constraints.maximum_width_cells is not None
        else constraints.minimum_width_cells + 3,
        bounds.width_cells - 2 * bounds.margin_cells,
    )
    maximum_height = min(
        constraints.maximum_height_cells
        if constraints.maximum_height_cells is not None
        else constraints.minimum_height_cells + 3,
        bounds.height_cells - 2 * bounds.margin_cells,
    )
    options: list[tuple[int, int]] = []
    for width in range(constraints.minimum_width_cells, maximum_width + 1):
        for height in range(constraints.minimum_height_cells, maximum_height + 1):
            area = width * height
            if area < constraints.minimum_area_cells:
                continue
            if (
                constraints.maximum_area_cells is not None
                and area > constraints.maximum_area_cells
            ):
                continue
            options.append((width, height))
    return options


def _rect_fits_bounds(rect: Rect, bounds: FloorLayoutBounds) -> bool:
    return (
        rect.x >= bounds.margin_cells
        and rect.y >= bounds.margin_cells
        and rect.right <= bounds.width_cells - bounds.margin_cells
        and rect.bottom <= bounds.height_cells - bounds.margin_cells
    )


def _size_satisfies(rect: Rect, constraints: RoomSizeConstraints) -> bool:
    area = rect.width * rect.height
    return (
        rect.width >= constraints.minimum_width_cells
        and (
            constraints.maximum_width_cells is None
            or rect.width <= constraints.maximum_width_cells
        )
        and rect.height >= constraints.minimum_height_cells
        and (
            constraints.maximum_height_cells is None
            or rect.height <= constraints.maximum_height_cells
        )
        and area >= constraints.minimum_area_cells
        and (
            constraints.maximum_area_cells is None
            or area <= constraints.maximum_area_cells
        )
    )


def _shared_wall_length(first: Rect, second: Rect) -> int:
    """Return a positive overlap only when rectangles share one wall."""

    if first.right == second.x or second.right == first.x:
        return max(0, min(first.bottom, second.bottom) - max(first.y, second.y))
    if first.bottom == second.y or second.bottom == first.y:
        return max(0, min(first.right, second.right) - max(first.x, second.x))
    return 0


def _rects_conflict(first: Rect, second: Rect, padding: int) -> bool:
    return not (
        first.right + padding <= second.x
        or second.right + padding <= first.x
        or first.bottom + padding <= second.y
        or second.bottom + padding <= first.y
    )
