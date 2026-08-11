"""Deterministic exact geometry, capacity, and walkability validation."""

from collections.abc import Iterable

from dm_dungeon.contracts.geometry import (
    CorridorLayout,
    GridPoint,
    GridSegment,
    PolygonGeometry,
    RectangleGeometry,
)
from dm_dungeon.contracts.package import DungeonPackage
from dm_dungeon.contracts.topology import (
    CorridorConnection,
    StairConnection,
    VerticalConnection,
)
from dm_dungeon.validation.diagnostics import DiagnosticSeverity
from dm_dungeon.validation.geometry_contracts import (
    GEOMETRY_VALIDATOR_VERSION,
    GeometryDiagnostic,
    GeometryDiagnosticCode,
    GeometryValidationReport,
)
from dm_dungeon.validation.grid import (
    Cell,
    WalkableGrid,
    build_walkable_grid,
    cells_for_geometry,
    connected_components,
)


def validate_geometry(package: DungeonPackage) -> GeometryValidationReport:
    """Validate exact renderer-neutral geometry without external state."""
    diagnostics: list[GeometryDiagnostic] = []
    grid = build_walkable_grid(package)

    _validate_grid_scale(package, diagnostics)
    _validate_room_geometry(package, grid, diagnostics)
    _validate_corridors(package, grid, diagnostics)
    _validate_doors(package, diagnostics)
    _validate_floor_transitions(package, grid, diagnostics)
    _validate_other_geometry_bounds(package, grid, diagnostics)
    _validate_walkable_connectivity(package, grid, diagnostics)

    ordered = tuple(
        sorted(
            diagnostics,
            key=lambda item: (item.code.value, item.affected_ids, item.message),
        )
    )
    valid = not any(item.severity is DiagnosticSeverity.ERROR for item in ordered)
    return GeometryValidationReport(
        validator_version=GEOMETRY_VALIDATOR_VERSION,
        package_id=package.id,
        valid=valid,
        walkable_cell_count=grid.total_walkable_cells,
        diagnostics=ordered,
    )


def _validate_grid_scale(
    package: DungeonPackage,
    diagnostics: list[GeometryDiagnostic],
) -> None:
    if package.grid.cell_scale_feet != 5:
        diagnostics.append(
            _diagnostic(
                GeometryDiagnosticCode.GRID_SCALE_INVALID,
                (package.id,),
                f"Initial dungeon geometry requires five-foot cells; package uses "
                f"{package.grid.cell_scale_feet} feet.",
                "Regenerate the package with cell_scale_feet set to 5.",
            )
        )
    for floor in package.floors:
        if floor.bounds.origin != GridPoint(x=0, y=0):
            diagnostics.append(
                _diagnostic(
                    GeometryDiagnosticCode.FLOOR_BOUNDS_INVALID,
                    (floor.id,),
                    f"Floor {floor.id!r} must use floor-local origin (0, 0).",
                    "Translate floor geometry to a zero-based local grid.",
                )
            )


def _validate_room_geometry(
    package: DungeonPackage,
    grid: WalkableGrid,
    diagnostics: list[GeometryDiagnostic],
) -> None:
    floors = {floor.id: floor for floor in package.floors}
    topology_rooms = {room.id: room for room in package.topology.rooms}
    room_by_id = {room.id: room for room in package.rooms}

    for room in package.rooms:
        if not _polygon_is_simple_orthogonal(room.boundary):
            diagnostics.append(
                _diagnostic(
                    GeometryDiagnosticCode.ROOM_POLYGON_INVALID,
                    (room.id,),
                    f"Room {room.id!r} is not a simple orthogonal polygon.",
                    "Use distinct axis-aligned polygon vertices without zero-length "
                    "edges.",
                )
            )
        cells = grid.room_cells[room.id]
        if not cells:
            diagnostics.append(
                _diagnostic(
                    GeometryDiagnosticCode.ROOM_POLYGON_INVALID,
                    (room.id,),
                    f"Room {room.id!r} has no interior grid cells.",
                    "Increase or repair the room polygon.",
                )
            )
        floor = floors[room.floor_id]
        outside = cells - cells_for_geometry(floor.bounds)
        if outside:
            diagnostics.append(
                _diagnostic(
                    GeometryDiagnosticCode.GEOMETRY_OUT_OF_BOUNDS,
                    (room.id, room.floor_id),
                    f"Room {room.id!r} extends outside floor bounds.",
                    "Move or resize the room inside its declared floor.",
                )
            )

        topology_room = topology_rooms[room.id]
        width = _polygon_width(room.boundary)
        height = _polygon_height(room.boundary)
        area = len(cells)
        constraints = topology_room.size
        if not (
            width >= constraints.minimum_width_cells
            and height >= constraints.minimum_height_cells
            and area >= constraints.minimum_area_cells
            and (
                constraints.maximum_width_cells is None
                or width <= constraints.maximum_width_cells
            )
            and (
                constraints.maximum_height_cells is None
                or height <= constraints.maximum_height_cells
            )
            and (
                constraints.maximum_area_cells is None
                or area <= constraints.maximum_area_cells
            )
        ):
            diagnostics.append(
                _diagnostic(
                    GeometryDiagnosticCode.ROOM_SIZE_CONSTRAINT_VIOLATION,
                    (room.id,),
                    f"Room {room.id!r} geometry violates topology size constraints.",
                    "Resize the room within its declared width, height, and area bounds.",
                )
            )

        usable_cells = cells - grid.blocked_cells.get(room.floor_id, set())
        if (
            room.capacity != topology_room.capacity
            or len(usable_cells) < topology_room.capacity.maximum_occupants
        ):
            diagnostics.append(
                _diagnostic(
                    GeometryDiagnosticCode.ROOM_CAPACITY_INSUFFICIENT,
                    (room.id,),
                    f"Room {room.id!r} has {len(usable_cells)} usable cells for a "
                    f"requested maximum of "
                    f"{topology_room.capacity.maximum_occupants} occupants.",
                    "Increase usable room area, remove blockers, or lower capacity.",
                )
            )

    for index, first in enumerate(package.rooms):
        first_cells = grid.room_cells[first.id]
        for second in package.rooms[index + 1 :]:
            if first.floor_id != second.floor_id:
                continue
            if first_cells & grid.room_cells[second.id]:
                diagnostics.append(
                    _diagnostic(
                        GeometryDiagnosticCode.ROOM_OVERLAP,
                        (first.id, second.id, first.floor_id),
                        f"Rooms {first.id!r} and {second.id!r} overlap.",
                        "Move or resize one room so their walkable cells are disjoint.",
                    )
                )

    missing_layout_ids = set(topology_rooms) - set(room_by_id)
    for room_id in sorted(missing_layout_ids):
        diagnostics.append(
            _diagnostic(
                GeometryDiagnosticCode.ROOM_POLYGON_INVALID,
                (room_id,),
                f"Topology room {room_id!r} has no exact layout.",
                "Generate exact geometry for every topology room.",
            )
        )


def _validate_corridors(
    package: DungeonPackage,
    grid: WalkableGrid,
    diagnostics: list[GeometryDiagnostic],
) -> None:
    floors = {floor.id: floor for floor in package.floors}
    rooms = {room.id: room for room in package.rooms}
    topology_corridors = {
        connection.id: connection
        for connection in package.topology.connections
        if isinstance(connection, CorridorConnection)
    }

    for corridor in package.corridors:
        if not _polyline_is_orthogonal(corridor):
            diagnostics.append(
                _diagnostic(
                    GeometryDiagnosticCode.CORRIDOR_NON_ORTHOGONAL,
                    (corridor.id,),
                    f"Corridor {corridor.id!r} contains a diagonal or zero-length "
                    "segment.",
                    "Route the corridor with nonzero horizontal/vertical segments.",
                )
            )
        cells = grid.corridor_cells[corridor.id]
        floor_cells = cells_for_geometry(floors[corridor.floor_id].bounds)
        if cells - floor_cells:
            diagnostics.append(
                _diagnostic(
                    GeometryDiagnosticCode.GEOMETRY_OUT_OF_BOUNDS,
                    (corridor.id, corridor.floor_id),
                    f"Corridor {corridor.id!r} extends outside floor bounds.",
                    "Reroute the corridor within the floor rectangle.",
                )
            )

        requested = topology_corridors.get(corridor.id)
        minimum_width = requested.minimum_width_cells if requested is not None else 1
        if corridor.width_cells < minimum_width:
            diagnostics.append(
                _diagnostic(
                    GeometryDiagnosticCode.CORRIDOR_WIDTH_INSUFFICIENT,
                    (corridor.id,),
                    f"Corridor {corridor.id!r} width {corridor.width_cells} is below "
                    f"requested minimum {minimum_width}.",
                    "Increase the corridor width to the topology minimum.",
                )
            )

        connected_room_ids = set(corridor.connects_room_ids)
        unrelated_overlap = sorted(
            room.id
            for room in package.rooms
            if room.floor_id == corridor.floor_id
            and room.id not in connected_room_ids
            and cells & grid.room_cells[room.id]
        )
        explicit_blockers = cells & grid.blocked_cells.get(corridor.floor_id, set())
        if unrelated_overlap or explicit_blockers:
            reason = (
                "unrelated room geometry"
                if unrelated_overlap
                else "explicit blocking geometry"
            )
            diagnostics.append(
                _diagnostic(
                    GeometryDiagnosticCode.CORRIDOR_BLOCKED,
                    (corridor.id, *unrelated_overlap),
                    f"Corridor {corridor.id!r} crosses {reason}.",
                    "Reroute around unrelated rooms/blockers or revise the "
                    "connection geometry.",
                )
            )

        first_room = rooms[corridor.connects_room_ids[0]]
        second_room = rooms[corridor.connects_room_ids[1]]
        start = corridor.path.points[0]
        end = corridor.path.points[-1]
        if not (
            _point_touches_cells(start, grid.room_cells[first_room.id])
            and _point_touches_cells(end, grid.room_cells[second_room.id])
        ) and not (
            _point_touches_cells(start, grid.room_cells[second_room.id])
            and _point_touches_cells(end, grid.room_cells[first_room.id])
        ):
            diagnostics.append(
                _diagnostic(
                    GeometryDiagnosticCode.CORRIDOR_ENDPOINT_MISALIGNED,
                    (corridor.id, *corridor.connects_room_ids),
                    f"Corridor {corridor.id!r} endpoints do not touch its rooms.",
                    "Move each path endpoint into or adjacent to its connected room.",
                )
            )


def _validate_doors(
    package: DungeonPackage,
    diagnostics: list[GeometryDiagnostic],
) -> None:
    rooms = {room.id: room for room in package.rooms}
    floors = {floor.id: floor for floor in package.floors}
    for door in package.doors:
        segment = door.segment
        length = _segment_length(segment)
        if length < 1:
            diagnostics.append(
                _diagnostic(
                    GeometryDiagnosticCode.DOOR_WIDTH_INSUFFICIENT,
                    (door.id,),
                    f"Door {door.id!r} has zero grid width.",
                    "Use an axis-aligned segment at least one cell long.",
                )
            )
        if not _segment_is_orthogonal(segment):
            diagnostics.append(
                _diagnostic(
                    GeometryDiagnosticCode.DOOR_ALIGNMENT_INVALID,
                    (door.id,),
                    f"Door {door.id!r} is not axis aligned.",
                    "Align the door to a horizontal or vertical room boundary.",
                )
            )
            continue

        floor = floors[door.floor_id]
        if not all(
            _point_within_floor_boundary(point, floor.bounds)
            for point in (segment.start, segment.end)
        ):
            diagnostics.append(
                _diagnostic(
                    GeometryDiagnosticCode.GEOMETRY_OUT_OF_BOUNDS,
                    (door.id, door.floor_id),
                    f"Door {door.id!r} extends outside floor bounds.",
                    "Move the door segment onto a room boundary inside the floor.",
                )
            )

        connected_rooms = [rooms[room_id] for room_id in door.connects_room_ids]
        if not any(
            _segment_on_polygon_boundary(segment, room.boundary)
            for room in connected_rooms
        ):
            diagnostics.append(
                _diagnostic(
                    GeometryDiagnosticCode.DOOR_ALIGNMENT_INVALID,
                    (door.id, *door.connects_room_ids),
                    f"Door {door.id!r} does not lie on a connected room boundary.",
                    "Place the door segment on one connected room's wall.",
                )
            )

        matching_corridors = [
            corridor
            for corridor in package.corridors
            if corridor.floor_id == door.floor_id
            and set(corridor.connects_room_ids) == set(door.connects_room_ids)
        ]
        if not any(
            _point_on_segment(corridor.path.points[0], segment)
            or _point_on_segment(corridor.path.points[-1], segment)
            for corridor in matching_corridors
        ):
            diagnostics.append(
                _diagnostic(
                    GeometryDiagnosticCode.DOOR_ALIGNMENT_INVALID,
                    (door.id,),
                    f"Door {door.id!r} is not aligned to a matching corridor endpoint.",
                    "Route a matching corridor endpoint through the door segment.",
                )
            )


def _validate_floor_transitions(
    package: DungeonPackage,
    grid: WalkableGrid,
    diagnostics: list[GeometryDiagnostic],
) -> None:
    links = {link.id: link for link in package.vertical_links}
    stairs = {stair.id: stair for stair in package.stairs}
    expected_link_ids = {
        connection.id
        for connection in package.topology.connections
        if isinstance(connection, StairConnection | VerticalConnection)
    }

    for connection in package.topology.connections:
        if not isinstance(connection, StairConnection | VerticalConnection):
            continue
        link = links.get(connection.id)
        if link is None:
            diagnostics.append(
                _diagnostic(
                    GeometryDiagnosticCode.FLOOR_TRANSITION_UNPAIRED,
                    (connection.id,),
                    f"Floor transition {connection.id!r} has no exact vertical link.",
                    "Emit one link with endpoints on both declared floors.",
                )
            )
            continue
        endpoint_floors = {endpoint.floor_id for endpoint in link.endpoints}
        expected_floors = {connection.from_floor_id, connection.to_floor_id}
        if endpoint_floors != expected_floors:
            diagnostics.append(
                _diagnostic(
                    GeometryDiagnosticCode.FLOOR_TRANSITION_UNPAIRED,
                    (connection.id, *endpoint_floors, *expected_floors),
                    f"Floor transition {connection.id!r} endpoints do not match "
                    "topology floors.",
                    "Pair one endpoint with each declared transition floor.",
                )
            )

        for endpoint in link.endpoints:
            cell = (endpoint.position.x, endpoint.position.y)
            if cell not in grid.floor_cells.get(endpoint.floor_id, set()):
                diagnostics.append(
                    _diagnostic(
                        GeometryDiagnosticCode.STAIR_ALIGNMENT_INVALID,
                        (connection.id, endpoint.floor_id),
                        f"Transition {connection.id!r} endpoint is not on a walkable "
                        "cell.",
                        "Move the endpoint into its connected room's walkable area.",
                    )
                )
            if endpoint.stair_id is not None:
                stair = stairs.get(endpoint.stair_id)
                if stair is None or (
                    stair.floor_id != endpoint.floor_id
                    or stair.position != endpoint.position
                ):
                    diagnostics.append(
                        _diagnostic(
                            GeometryDiagnosticCode.STAIR_ALIGNMENT_INVALID,
                            (connection.id, endpoint.stair_id),
                            f"Transition {connection.id!r} has a mismatched stair "
                            "endpoint.",
                            "Make stair and link floor/position fields identical.",
                        )
                    )

    for link_id in sorted(set(links) - expected_link_ids):
        diagnostics.append(
            _diagnostic(
                GeometryDiagnosticCode.FLOOR_TRANSITION_UNPAIRED,
                (link_id,),
                f"Vertical link {link_id!r} has no topology transition.",
                "Remove the orphan link or add its topology connection.",
            )
        )

    referenced_stair_ids = {
        endpoint.stair_id
        for link in package.vertical_links
        for endpoint in link.endpoints
        if endpoint.stair_id is not None
    }
    for stair_id in sorted(set(stairs) - referenced_stair_ids):
        diagnostics.append(
            _diagnostic(
                GeometryDiagnosticCode.FLOOR_TRANSITION_UNPAIRED,
                (stair_id,),
                f"Stair {stair_id!r} is not referenced by a vertical link.",
                "Attach the stair to a paired floor transition or remove it.",
            )
        )


def _validate_other_geometry_bounds(
    package: DungeonPackage,
    grid: WalkableGrid,
    diagnostics: list[GeometryDiagnostic],
) -> None:
    floors = {floor.id: floor for floor in package.floors}
    shaped_elements = (
        *((item.id, item.floor_id, item.geometry) for item in package.features),
        *((item.id, item.floor_id, item.area) for item in package.terrain),
        *((item.id, item.floor_id, item.geometry) for item in package.hazards),
        *((item.id, item.floor_id, item.geometry) for item in package.zones),
    )
    for component_id, floor_id, geometry in shaped_elements:
        if cells_for_geometry(geometry) - cells_for_geometry(floors[floor_id].bounds):
            diagnostics.append(
                _diagnostic(
                    GeometryDiagnosticCode.GEOMETRY_OUT_OF_BOUNDS,
                    (component_id, floor_id),
                    f"Component {component_id!r} extends outside floor bounds.",
                    "Move or resize the component inside its floor.",
                )
            )

    point_elements = (
        *((item.id, item.floor_id, item.position) for item in package.labels),
        *((item.id, item.floor_id, item.position) for item in package.position_anchors),
        *((item.id, item.floor_id, item.position) for item in package.stairs),
    )
    for component_id, floor_id, point in point_elements:
        if (point.x, point.y) not in cells_for_geometry(floors[floor_id].bounds):
            diagnostics.append(
                _diagnostic(
                    GeometryDiagnosticCode.GEOMETRY_OUT_OF_BOUNDS,
                    (component_id, floor_id),
                    f"Point component {component_id!r} is outside floor bounds.",
                    "Move the point inside its declared floor.",
                )
            )

    for anchor in package.position_anchors:
        if (anchor.position.x, anchor.position.y) not in grid.floor_cells.get(
            anchor.floor_id, set()
        ):
            diagnostics.append(
                _diagnostic(
                    GeometryDiagnosticCode.PATH_ANCHOR_BLOCKED,
                    (anchor.id,),
                    f"Anchor {anchor.id!r} is not on a walkable cell.",
                    "Move the anchor to unblocked room or corridor geometry.",
                )
            )


def _validate_walkable_connectivity(
    package: DungeonPackage,
    grid: WalkableGrid,
    diagnostics: list[GeometryDiagnostic],
) -> None:
    components = connected_components(grid)
    if len(components) > 1:
        representative_ids = tuple(
            f"{floor_id}:{x}:{y}"
            for floor_id, x, y in (min(component) for component in components)
        )
        diagnostics.append(
            _diagnostic(
                GeometryDiagnosticCode.WALKABLE_REGION_DISCONNECTED,
                (package.id,),
                f"Package has {len(components)} disconnected walkable regions "
                f"({', '.join(representative_ids)}).",
                "Connect every room/corridor region or remove unusable isolated cells.",
            )
        )


def _polygon_is_simple_orthogonal(polygon: PolygonGeometry) -> bool:
    points = polygon.points
    if len({(point.x, point.y) for point in points}) != len(points):
        return False
    edges = tuple(
        GridSegment(start=first, end=second)
        for first, second in zip(points, (*points[1:], points[0]), strict=True)
    )
    if not all(_segment_is_orthogonal(edge) for edge in edges):
        return False
    for first_index, first in enumerate(edges):
        for second_index in range(first_index + 1, len(edges)):
            if second_index in {
                first_index + 1,
                (first_index - 1) % len(edges),
            } or (first_index == 0 and second_index == len(edges) - 1):
                continue
            if _segments_intersect(first, edges[second_index]):
                return False
    return True


def _polyline_is_orthogonal(corridor: CorridorLayout) -> bool:
    return all(
        _points_form_nonzero_orthogonal_segment(first, second)
        for first, second in zip(
            corridor.path.points,
            corridor.path.points[1:],
            strict=False,
        )
    )


def _points_form_nonzero_orthogonal_segment(
    first: GridPoint,
    second: GridPoint,
) -> bool:
    return (first.x == second.x) != (first.y == second.y)


def _segment_is_orthogonal(segment: GridSegment) -> bool:
    return _points_form_nonzero_orthogonal_segment(segment.start, segment.end)


def _segment_length(segment: GridSegment) -> int:
    return abs(segment.end.x - segment.start.x) + abs(segment.end.y - segment.start.y)


def _point_touches_cells(point: GridPoint, cells: set[Cell]) -> bool:
    return any(abs(point.x - x) + abs(point.y - y) <= 1 for x, y in cells)


def _point_within_floor_boundary(
    point: GridPoint,
    bounds: RectangleGeometry,
) -> bool:
    return (
        bounds.origin.x <= point.x <= bounds.origin.x + bounds.width_cells
        and bounds.origin.y <= point.y <= bounds.origin.y + bounds.height_cells
    )


def _segment_on_polygon_boundary(
    segment: GridSegment,
    polygon: PolygonGeometry,
) -> bool:
    return any(
        _segment_contains_segment(edge, segment)
        for edge in (
            GridSegment(start=first, end=second)
            for first, second in zip(
                polygon.points,
                (*polygon.points[1:], polygon.points[0]),
                strict=True,
            )
        )
    )


def _segments_intersect(first: GridSegment, second: GridSegment) -> bool:
    first_vertical = first.start.x == first.end.x
    second_vertical = second.start.x == second.end.x
    if first_vertical and second_vertical:
        return first.start.x == second.start.x and not (
            max(first.start.y, first.end.y) < min(second.start.y, second.end.y)
            or max(second.start.y, second.end.y) < min(first.start.y, first.end.y)
        )
    if not first_vertical and not second_vertical:
        return first.start.y == second.start.y and not (
            max(first.start.x, first.end.x) < min(second.start.x, second.end.x)
            or max(second.start.x, second.end.x) < min(first.start.x, first.end.x)
        )
    vertical = first if first_vertical else second
    horizontal = second if first_vertical else first
    return min(horizontal.start.x, horizontal.end.x) <= vertical.start.x <= max(
        horizontal.start.x, horizontal.end.x
    ) and min(vertical.start.y, vertical.end.y) <= horizontal.start.y <= max(
        vertical.start.y, vertical.end.y
    )


def _segment_contains_segment(outer: GridSegment, inner: GridSegment) -> bool:
    if not _segment_is_orthogonal(outer) or not _segment_is_orthogonal(inner):
        return False
    if outer.start.x == outer.end.x:
        return (
            inner.start.x == inner.end.x == outer.start.x
            and min(outer.start.y, outer.end.y) <= min(inner.start.y, inner.end.y)
            and max(inner.start.y, inner.end.y) <= max(outer.start.y, outer.end.y)
        )
    return (
        inner.start.y == inner.end.y == outer.start.y
        and min(outer.start.x, outer.end.x) <= min(inner.start.x, inner.end.x)
        and max(inner.start.x, inner.end.x) <= max(outer.start.x, outer.end.x)
    )


def _point_on_segment(point: GridPoint, segment: GridSegment) -> bool:
    if segment.start.x == segment.end.x:
        return point.x == segment.start.x and min(
            segment.start.y, segment.end.y
        ) <= point.y <= max(segment.start.y, segment.end.y)
    if segment.start.y == segment.end.y:
        return point.y == segment.start.y and min(
            segment.start.x, segment.end.x
        ) <= point.x <= max(segment.start.x, segment.end.x)
    return False


def _polygon_width(polygon: PolygonGeometry) -> int:
    return max(point.x for point in polygon.points) - min(
        point.x for point in polygon.points
    )


def _polygon_height(polygon: PolygonGeometry) -> int:
    return max(point.y for point in polygon.points) - min(
        point.y for point in polygon.points
    )


def _diagnostic(
    code: GeometryDiagnosticCode,
    affected_ids: Iterable[str],
    message: str,
    repair_hint: str,
) -> GeometryDiagnostic:
    return GeometryDiagnostic(
        code=code,
        severity=DiagnosticSeverity.ERROR,
        message=message,
        affected_ids=tuple(sorted(set(affected_ids))),
        repair_hint=repair_hint,
    )
