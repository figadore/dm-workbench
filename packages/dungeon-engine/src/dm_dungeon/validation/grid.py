"""Deterministic square-cell rasterization and pathfinding primitives."""

from collections import deque
from dataclasses import dataclass
from math import gcd

from dm_dungeon.contracts.geometry import (
    FeatureKind,
    MapGeometry,
    PointGeometry,
    PolygonGeometry,
    PolylineGeometry,
    RectangleGeometry,
    SegmentGeometry,
)
from dm_dungeon.contracts.package import DungeonPackage
from dm_dungeon.validation.geometry_contracts import CreatureFootprint

type Cell = tuple[int, int]
type FloorCell = tuple[str, int, int]


@dataclass(slots=True)
class WalkableGrid:
    """Rasterized walkable cells and cross-floor adjacency."""

    floor_cells: dict[str, set[Cell]]
    room_cells: dict[str, set[Cell]]
    corridor_cells: dict[str, set[Cell]]
    blocked_cells: dict[str, set[Cell]]
    vertical_edges: dict[FloorCell, set[FloorCell]]

    @property
    def total_walkable_cells(self) -> int:
        return sum(len(cells) for cells in self.floor_cells.values())


def build_walkable_grid(package: DungeonPackage) -> WalkableGrid:
    """Rasterize exact rooms/corridors and remove explicit blockers."""
    floor_bounds = {
        floor.id: cells_for_geometry(floor.bounds) for floor in package.floors
    }
    room_cells = {room.id: cells_for_geometry(room.boundary) for room in package.rooms}
    corridor_cells = {
        corridor.id: cells_for_corridor(corridor.path, corridor.width_cells)
        for corridor in package.corridors
    }
    blocked_cells: dict[str, set[Cell]] = {floor.id: set() for floor in package.floors}
    blocking_feature_kinds = {
        FeatureKind.FURNITURE,
        FeatureKind.PILLAR,
        FeatureKind.PIT,
        FeatureKind.STATUE,
    }
    for feature in package.features:
        if feature.kind in blocking_feature_kinds:
            blocked_cells.setdefault(feature.floor_id, set()).update(
                cells_for_geometry(feature.geometry)
            )
    for terrain in package.terrain:
        if terrain.blocks_movement:
            blocked_cells.setdefault(terrain.floor_id, set()).update(
                cells_for_geometry(terrain.area)
            )

    floor_cells: dict[str, set[Cell]] = {floor.id: set() for floor in package.floors}
    rooms_by_id = {room.id: room for room in package.rooms}
    corridors_by_id = {corridor.id: corridor for corridor in package.corridors}
    for room_id, cells in room_cells.items():
        room = rooms_by_id[room_id]
        floor_cells[room.floor_id].update(cells)
    for corridor_id, cells in corridor_cells.items():
        corridor = corridors_by_id[corridor_id]
        floor_cells[corridor.floor_id].update(cells)

    for floor_id, cells in floor_cells.items():
        cells.intersection_update(floor_bounds.get(floor_id, set()))
        cells.difference_update(blocked_cells.get(floor_id, set()))

    vertical_edges: dict[FloorCell, set[FloorCell]] = {}
    for link in package.vertical_links:
        endpoints = [
            (endpoint.floor_id, endpoint.position.x, endpoint.position.y)
            for endpoint in link.endpoints
        ]
        for index, first in enumerate(endpoints):
            if (first[1], first[2]) not in floor_cells.get(first[0], set()):
                continue
            for second in endpoints[index + 1 :]:
                if (second[1], second[2]) not in floor_cells.get(second[0], set()):
                    continue
                vertical_edges.setdefault(first, set()).add(second)
                vertical_edges.setdefault(second, set()).add(first)

    return WalkableGrid(
        floor_cells=floor_cells,
        room_cells=room_cells,
        corridor_cells=corridor_cells,
        blocked_cells=blocked_cells,
        vertical_edges=vertical_edges,
    )


def cells_for_geometry(geometry: MapGeometry) -> set[Cell]:
    """Rasterize one renderer-neutral geometry shape to occupied cells."""
    if isinstance(geometry, PointGeometry):
        return {(geometry.point.x, geometry.point.y)}
    if isinstance(geometry, SegmentGeometry):
        return _segment_cells(
            (geometry.segment.start.x, geometry.segment.start.y),
            (geometry.segment.end.x, geometry.segment.end.y),
        )
    if isinstance(geometry, PolylineGeometry):
        cells: set[Cell] = set()
        for first, second in zip(
            geometry.points,
            geometry.points[1:],
            strict=False,
        ):
            cells.update(_segment_cells((first.x, first.y), (second.x, second.y)))
        return cells
    if isinstance(geometry, PolygonGeometry):
        return _polygon_cells(geometry)
    if isinstance(geometry, RectangleGeometry):
        return {
            (x, y)
            for x in range(geometry.origin.x, geometry.origin.x + geometry.width_cells)
            for y in range(
                geometry.origin.y,
                geometry.origin.y + geometry.height_cells,
            )
        }
    raise TypeError(f"Unsupported map geometry: {type(geometry)!r}")


def cells_for_corridor(path: PolylineGeometry, width_cells: int) -> set[Cell]:
    """Rasterize an orthogonal corridor with deterministic even-width bias."""
    cells: set[Cell] = set()
    negative_offset = (width_cells - 1) // 2
    positive_offset = width_cells // 2
    for first, second in zip(path.points, path.points[1:], strict=False):
        start = (first.x, first.y)
        end = (second.x, second.y)
        centerline = _segment_cells(start, end)
        if first.y == second.y:
            for x, y in centerline:
                cells.update(
                    (x, y + offset)
                    for offset in range(-negative_offset, positive_offset + 1)
                )
        elif first.x == second.x:
            for x, y in centerline:
                cells.update(
                    (x + offset, y)
                    for offset in range(-negative_offset, positive_offset + 1)
                )
        else:
            cells.update(centerline)
    return cells


def footprint_cells(origin: FloorCell, footprint: CreatureFootprint) -> set[FloorCell]:
    """Expand a top-left floor cell into an axis-aligned creature footprint."""
    floor_id, origin_x, origin_y = origin
    return {
        (floor_id, origin_x + offset_x, origin_y + offset_y)
        for offset_x in range(footprint.width_cells)
        for offset_y in range(footprint.height_cells)
    }


def footprint_fits(
    grid: WalkableGrid,
    origin: FloorCell,
    footprint: CreatureFootprint,
) -> bool:
    """Return whether every footprint cell is walkable on one floor."""
    floor_id = origin[0]
    walkable = grid.floor_cells.get(floor_id, set())
    return all(
        cell_floor == floor_id and (x, y) in walkable
        for cell_floor, x, y in footprint_cells(origin, footprint)
    )


def valid_origins(
    grid: WalkableGrid,
    floor_id: str,
    footprint: CreatureFootprint,
    allowed_cells: set[Cell] | None = None,
) -> set[Cell]:
    """Return walkable top-left origins that fit a footprint."""
    candidates = (
        allowed_cells
        if allowed_cells is not None
        else grid.floor_cells.get(floor_id, set())
    )
    return {
        cell
        for cell in candidates
        if footprint_fits(grid, (floor_id, cell[0], cell[1]), footprint)
        and (
            allowed_cells is None
            or {
                (cell_x, cell_y)
                for _, cell_x, cell_y in footprint_cells(
                    (floor_id, cell[0], cell[1]),
                    footprint,
                )
            }.issubset(allowed_cells)
        )
    }


def shortest_path(
    grid: WalkableGrid,
    start: FloorCell,
    end: FloorCell,
    footprint: CreatureFootprint,
) -> tuple[FloorCell, ...] | None:
    """Find a deterministic shortest path, including cross-floor links."""
    if not footprint_fits(grid, start, footprint) or not footprint_fits(
        grid, end, footprint
    ):
        return None
    pending = deque((start,))
    previous: dict[FloorCell, FloorCell | None] = {start: None}
    while pending:
        current = pending.popleft()
        if current == end:
            return _reconstruct(previous, end)
        floor_id, x, y = current
        neighbors = [
            (floor_id, x, y - 1),
            (floor_id, x - 1, y),
            (floor_id, x + 1, y),
            (floor_id, x, y + 1),
            *sorted(grid.vertical_edges.get(current, set())),
        ]
        for neighbor in neighbors:
            if neighbor in previous or not footprint_fits(grid, neighbor, footprint):
                continue
            previous[neighbor] = current
            pending.append(neighbor)
    return None


def connected_components(grid: WalkableGrid) -> tuple[frozenset[FloorCell], ...]:
    """Return all 1x1 walkable connected components in stable order."""
    remaining = {
        (floor_id, x, y)
        for floor_id, cells in grid.floor_cells.items()
        for x, y in cells
    }
    components: list[frozenset[FloorCell]] = []
    footprint = CreatureFootprint()
    while remaining:
        start = min(remaining)
        visited = _flood_fill(grid, start, footprint)
        components.append(frozenset(visited))
        remaining.difference_update(visited)
    return tuple(sorted(components, key=lambda item: min(item)))


def _flood_fill(
    grid: WalkableGrid,
    start: FloorCell,
    footprint: CreatureFootprint,
) -> set[FloorCell]:
    pending = deque((start,))
    visited = {start}
    while pending:
        floor_id, x, y = pending.popleft()
        neighbors = (
            (floor_id, x, y - 1),
            (floor_id, x - 1, y),
            (floor_id, x + 1, y),
            (floor_id, x, y + 1),
            *sorted(grid.vertical_edges.get((floor_id, x, y), set())),
        )
        for neighbor in neighbors:
            if neighbor in visited or not footprint_fits(grid, neighbor, footprint):
                continue
            visited.add(neighbor)
            pending.append(neighbor)
    return visited


def _segment_cells(start: Cell, end: Cell) -> set[Cell]:
    delta_x = end[0] - start[0]
    delta_y = end[1] - start[1]
    steps = gcd(abs(delta_x), abs(delta_y))
    if steps == 0:
        return {start}
    step_x = delta_x // steps
    step_y = delta_y // steps
    return {
        (start[0] + index * step_x, start[1] + index * step_y)
        for index in range(steps + 1)
    }


def _polygon_cells(polygon: PolygonGeometry) -> set[Cell]:
    minimum_x = min(point.x for point in polygon.points)
    maximum_x = max(point.x for point in polygon.points)
    minimum_y = min(point.y for point in polygon.points)
    maximum_y = max(point.y for point in polygon.points)
    return {
        (x, y)
        for x in range(minimum_x, maximum_x)
        for y in range(minimum_y, maximum_y)
        if _point_inside_polygon(x + 0.5, y + 0.5, polygon)
    }


def _point_inside_polygon(x: float, y: float, polygon: PolygonGeometry) -> bool:
    inside = False
    points = polygon.points
    for first, second in zip(points, (*points[1:], points[0]), strict=True):
        if (first.y > y) == (second.y > y):
            continue
        intersection_x = (second.x - first.x) * (y - first.y) / (
            second.y - first.y
        ) + first.x
        if x < intersection_x:
            inside = not inside
    return inside


def _reconstruct(
    previous: dict[FloorCell, FloorCell | None],
    end: FloorCell,
) -> tuple[FloorCell, ...]:
    reversed_path = [end]
    current = end
    while previous[current] is not None:
        predecessor = previous[current]
        assert predecessor is not None
        reversed_path.append(predecessor)
        current = predecessor
    return tuple(reversed(reversed_path))
