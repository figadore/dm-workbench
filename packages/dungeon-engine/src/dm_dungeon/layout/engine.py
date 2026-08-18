"""Seeded graph-guided orthogonal dungeon layout engine."""

from collections.abc import Iterable

from dm_dungeon.contracts.common import Visibility
from dm_dungeon.contracts.geometry import (
    CorridorLayout,
    DoorLayout,
    FloorLayout,
    GridPoint,
    PositionAnchor,
    PositionAnchorKind,
    RenderLayer,
    RenderLayerKind,
    RoomLayout,
    StairLayout,
    VerticalEndpoint,
    VerticalLinkLayout,
)
from dm_dungeon.contracts.package import (
    ComponentIdStrategy,
    DungeonPackage,
    PackageMetadata,
)
from dm_dungeon.contracts.topology import (
    CorridorConnection,
    DoorConnection,
    StairConnection,
    StairDirection,
    VerticalConnection,
    VerticalLinkKind,
)
from dm_dungeon.layout.contracts import (
    LAYOUT_RESULT_SCHEMA_VERSION,
    FloorLayoutBounds,
    LayoutDiagnostic,
    LayoutDiagnosticCode,
    LayoutRequest,
    LayoutResult,
)
from dm_dungeon.layout.identifiers import derive_component_id
from dm_dungeon.layout.placement import (
    Rect,
    default_floor_bounds,
    place_floor_rooms,
    polygon_from_rect,
    rectangle_from_floor_bounds,
)
from dm_dungeon.layout.random_source import DeterministicRandom
from dm_dungeon.layout.routing import door_segment_at_anchor, route_between_rooms
from dm_dungeon.validation import (
    DiagnosticSeverity,
    validate_geometry,
    validate_topology,
)


def generate_layout(request: LayoutRequest) -> LayoutResult:
    """Generate an exact all-or-nothing layout from pinned topology input."""
    random_source = DeterministicRandom(request.seed, request.generator_version)
    diagnostics: list[LayoutDiagnostic] = []

    _validate_request_relationships(request, diagnostics)
    topology_report = validate_topology(request.topology)
    for finding in topology_report.diagnostics:
        if finding.severity is DiagnosticSeverity.ERROR:
            diagnostics.append(
                _diagnostic(
                    LayoutDiagnosticCode.TOPOLOGY_INVALID,
                    finding.affected_ids,
                    finding.message,
                    finding.repair_hint,
                    source_code=finding.code.value,
                )
            )
    _validate_locked_component_ids(request, diagnostics)
    if diagnostics:
        return _failed_result(request, random_source, diagnostics)

    base_layer, secret_layer = _render_layers(request)
    layer_by_visibility = {
        Visibility.PLAYER_SAFE: base_layer.id,
        Visibility.DM_ONLY: secret_layer.id,
    }
    _validate_locked_layer_assignments(
        request,
        layer_by_visibility,
        diagnostics,
    )
    if diagnostics:
        return _failed_result(request, random_source, diagnostics)

    floor_bounds = _resolve_floor_bounds(request, diagnostics)
    if diagnostics:
        return _failed_result(request, random_source, diagnostics)

    locked_floors = {item.id: item for item in request.locked.floors}
    locked_rooms = {item.id: item for item in request.locked.rooms}
    floors: list[FloorLayout] = []
    rooms: list[RoomLayout] = []
    room_rects: dict[str, Rect] = {}

    for topology_floor in request.topology.floors:
        bounds = floor_bounds[topology_floor.id]
        locked_floor = locked_floors.get(topology_floor.id)
        if locked_floor is not None:
            floors.append(locked_floor)
        else:
            floors.append(
                FloorLayout(
                    id=topology_floor.id,
                    layer_id=layer_by_visibility[topology_floor.visibility],
                    name=topology_floor.name,
                    level_index=topology_floor.level_index,
                    bounds=rectangle_from_floor_bounds(bounds),
                    visibility=topology_floor.visibility,
                )
            )

        topology_rooms = tuple(
            room
            for room in request.topology.rooms
            if room.floor_id == topology_floor.id
        )
        floor_locked_rooms = tuple(
            room for room in request.locked.rooms if room.floor_id == topology_floor.id
        )
        placed, failure = place_floor_rooms(
            request.topology,
            topology_floor,
            topology_rooms,
            bounds,
            floor_locked_rooms,
            random_source,
            request.maximum_placement_attempts,
        )
        if placed is None:
            code = (
                LayoutDiagnosticCode.LOCKED_COMPONENT_CONFLICT
                if failure is not None and failure.startswith("Locked room")
                else LayoutDiagnosticCode.ROOM_PLACEMENT_FAILED
            )
            diagnostics.append(
                _diagnostic(
                    code,
                    (topology_floor.id, *(room.id for room in topology_rooms)),
                    failure or f"Room placement failed on floor {topology_floor.id!r}.",
                    "Increase floor bounds, relax room constraints, or unlock conflicting "
                    "rooms.",
                )
            )
            continue

        room_rects.update(placed)
        for topology_room in topology_rooms:
            locked_room = locked_rooms.get(topology_room.id)
            if locked_room is not None:
                rooms.append(locked_room)
                continue
            rooms.append(
                RoomLayout(
                    id=topology_room.id,
                    layer_id=layer_by_visibility[topology_room.visibility],
                    floor_id=topology_room.floor_id,
                    role=topology_room.role,
                    boundary=polygon_from_rect(placed[topology_room.id]),
                    capacity=topology_room.capacity,
                    tags=topology_room.tags,
                    visibility=topology_room.visibility,
                )
            )

    if diagnostics:
        return _failed_result(request, random_source, diagnostics)

    corridors, doors = _generate_same_floor_connections(
        request,
        room_rects,
        floor_bounds,
        layer_by_visibility,
        random_source,
        diagnostics,
    )
    stairs, vertical_links = _generate_floor_transitions(
        request,
        room_rects,
        layer_by_visibility,
        diagnostics,
    )
    if diagnostics:
        return _failed_result(request, random_source, diagnostics)

    position_anchors = _generate_role_anchors(
        request,
        room_rects,
        layer_by_visibility,
    )

    try:
        package = DungeonPackage(
            schema_version="1.0.0",
            id=request.package_id,
            brief=request.brief,
            topology=request.topology,
            metadata=PackageMetadata(
                generator_name="dm-dungeon orthogonal layout",
                generator_version=request.generator_version,
                seed=request.seed,
                component_id_strategy=(
                    ComponentIdStrategy.INPUT_WITH_SHA256_V1_AUXILIARY
                ),
                parent_package_id=None,
                locked_component_ids=request.locked.component_ids(),
            ),
            grid=request.grid,
            layers=(base_layer, secret_layer),
            floors=tuple(floors),
            rooms=tuple(rooms),
            corridors=tuple(corridors),
            doors=tuple(doors),
            stairs=tuple(stairs),
            vertical_links=tuple(vertical_links),
            features=(),
            terrain=(),
            hazards=(),
            zones=(),
            labels=(),
            encounter_slots=(),
            position_anchors=position_anchors,
        )
    except ValueError as error:
        diagnostics.append(
            _diagnostic(
                LayoutDiagnosticCode.INTERNAL_CONTRACT_FAILURE,
                (request.package_id,),
                f"Generated layout failed its package contract: {error}",
                "Review locked components and report this deterministic generator "
                "failure.",
            )
        )
        return _failed_result(request, random_source, diagnostics)

    geometry_report = validate_geometry(package)
    if not geometry_report.valid:
        diagnostics.extend(
            _diagnostic(
                LayoutDiagnosticCode.INTERNAL_CONTRACT_FAILURE,
                finding.affected_ids,
                finding.message,
                finding.repair_hint,
                source_code=finding.code.value,
            )
            for finding in geometry_report.diagnostics
            if finding.severity is DiagnosticSeverity.ERROR
        )
        return _failed_result(request, random_source, diagnostics)

    return LayoutResult(
        schema_version=LAYOUT_RESULT_SCHEMA_VERSION,
        generator_version=request.generator_version,
        seed=request.seed,
        random_draw_count=random_source.draw_count,
        success=True,
        package=package,
        diagnostics=(),
    )


def _validate_request_relationships(
    request: LayoutRequest,
    diagnostics: list[LayoutDiagnostic],
) -> None:
    floor_count = len(request.topology.floors)
    room_count = len(request.topology.rooms)
    if request.brief.floor_count != floor_count:
        diagnostics.append(
            _diagnostic(
                LayoutDiagnosticCode.BRIEF_TOPOLOGY_MISMATCH,
                (request.brief.id, request.topology.id),
                f"Brief requests {request.brief.floor_count} floors but topology "
                f"declares {floor_count}.",
                "Make the brief and topology floor counts agree.",
            )
        )
    if request.brief.target_room_count != room_count:
        diagnostics.append(
            _diagnostic(
                LayoutDiagnosticCode.BRIEF_TOPOLOGY_MISMATCH,
                (request.brief.id, request.topology.id),
                f"Brief requests {request.brief.target_room_count} rooms but topology "
                f"declares {room_count}.",
                "Make the brief and topology room counts agree.",
            )
        )

    topology_floor_ids = {floor.id for floor in request.topology.floors}
    for bounds in request.floor_bounds:
        if bounds.floor_id not in topology_floor_ids:
            diagnostics.append(
                _diagnostic(
                    LayoutDiagnosticCode.UNKNOWN_FLOOR_BOUNDS,
                    (bounds.floor_id,),
                    f"Bounds reference unknown floor {bounds.floor_id!r}.",
                    "Remove the bounds or reference a declared topology floor.",
                )
            )
        elif (
            bounds.width_cells <= 2 * bounds.margin_cells
            or bounds.height_cells <= 2 * bounds.margin_cells
        ):
            diagnostics.append(
                _diagnostic(
                    LayoutDiagnosticCode.FLOOR_BOUNDS_INVALID,
                    (bounds.floor_id,),
                    f"Floor {bounds.floor_id!r} bounds leave no placeable interior.",
                    "Increase width/height or reduce the floor margin.",
                )
            )


def _validate_locked_component_ids(
    request: LayoutRequest,
    diagnostics: list[LayoutDiagnostic],
) -> None:
    floor_ids = {floor.id for floor in request.topology.floors}
    room_ids = {room.id for room in request.topology.rooms}
    corridor_ids: set[str] = set()
    door_ids: set[str] = set()
    stair_ids: set[str] = set()
    vertical_link_ids: set[str] = set()
    for connection in request.topology.connections:
        if isinstance(connection, CorridorConnection):
            corridor_ids.add(connection.id)
        elif isinstance(connection, DoorConnection):
            corridor_ids.add(_door_corridor_id(request, connection.id))
            door_ids.add(connection.id)
        elif isinstance(connection, StairConnection):
            stair_ids.update(_stair_ids(request, connection.id))
            vertical_link_ids.add(connection.id)
        elif isinstance(connection, VerticalConnection):
            vertical_link_ids.add(connection.id)

    expected_groups = (
        ("floor", request.locked.floors, floor_ids),
        ("room", request.locked.rooms, room_ids),
        ("corridor", request.locked.corridors, corridor_ids),
        ("door", request.locked.doors, door_ids),
        ("stair", request.locked.stairs, stair_ids),
        (
            "vertical link",
            request.locked.vertical_links,
            vertical_link_ids,
        ),
    )
    for kind, components, expected_ids in expected_groups:
        for component in components:
            if component.id not in expected_ids:
                diagnostics.append(
                    _diagnostic(
                        LayoutDiagnosticCode.LOCKED_COMPONENT_UNKNOWN,
                        (component.id,),
                        f"Locked {kind} {component.id!r} is not produced by this "
                        "topology.",
                        "Remove the stale lock or restore its topology component.",
                    )
                )

    topology_floors = {floor.id: floor for floor in request.topology.floors}
    for locked_floor in request.locked.floors:
        topology_floor = topology_floors.get(locked_floor.id)
        if topology_floor is not None and (
            locked_floor.level_index != topology_floor.level_index
            or locked_floor.visibility is not topology_floor.visibility
        ):
            diagnostics.append(
                _diagnostic(
                    LayoutDiagnosticCode.LOCKED_COMPONENT_CONFLICT,
                    (locked_floor.id,),
                    f"Locked floor {locked_floor.id!r} conflicts with topology fields.",
                    "Use a lock created from the same topology version.",
                )
            )

    topology_rooms = {room.id: room for room in request.topology.rooms}
    for locked_room in request.locked.rooms:
        topology_room = topology_rooms.get(locked_room.id)
        if topology_room is not None and (
            locked_room.floor_id != topology_room.floor_id
            or locked_room.role is not topology_room.role
            or locked_room.visibility is not topology_room.visibility
        ):
            diagnostics.append(
                _diagnostic(
                    LayoutDiagnosticCode.LOCKED_COMPONENT_CONFLICT,
                    (locked_room.id,),
                    f"Locked room {locked_room.id!r} conflicts with topology fields.",
                    "Use a lock created from the same topology version.",
                )
            )


def _render_layers(request: LayoutRequest) -> tuple[RenderLayer, RenderLayer]:
    base_id = derive_component_id(
        "layer",
        request.package_id,
        request.generator_version,
        "player-base",
    )
    secret_id = derive_component_id(
        "layer",
        request.package_id,
        request.generator_version,
        "dm-secrets",
    )
    return (
        RenderLayer(
            id=base_id,
            name="Generated base geometry",
            kind=RenderLayerKind.BASE,
            z_index=0,
            include_in_dm_export=True,
            include_in_player_export=True,
            visibility=Visibility.PLAYER_SAFE,
        ),
        RenderLayer(
            id=secret_id,
            name="Generated DM secrets",
            kind=RenderLayerKind.DM_SECRETS,
            z_index=100,
            include_in_dm_export=True,
            include_in_player_export=False,
            visibility=Visibility.DM_ONLY,
        ),
    )


def _validate_locked_layer_assignments(
    request: LayoutRequest,
    layer_by_visibility: dict[Visibility, str],
    diagnostics: list[LayoutDiagnostic],
) -> None:
    layered_locks = (
        *request.locked.floors,
        *request.locked.rooms,
        *request.locked.corridors,
        *request.locked.doors,
        *request.locked.stairs,
    )
    for component in layered_locks:
        expected_layer_id = layer_by_visibility[component.visibility]
        if component.layer_id != expected_layer_id:
            diagnostics.append(
                _diagnostic(
                    LayoutDiagnosticCode.LOCKED_COMPONENT_CONFLICT,
                    (component.id, component.layer_id, expected_layer_id),
                    f"Locked component {component.id!r} uses a layer from a different "
                    "package or generator contract.",
                    "Regenerate locks from the same package ID and generator version.",
                )
            )


def _resolve_floor_bounds(
    request: LayoutRequest,
    diagnostics: list[LayoutDiagnostic],
) -> dict[str, FloorLayoutBounds]:
    provided = {item.floor_id: item for item in request.floor_bounds}
    locked_floors = {item.id: item for item in request.locked.floors}
    resolved: dict[str, FloorLayoutBounds] = {}
    for floor in request.topology.floors:
        floor_rooms = tuple(
            room for room in request.topology.rooms if room.floor_id == floor.id
        )
        requested = provided.get(floor.id)
        locked = locked_floors.get(floor.id)
        if locked is not None:
            if locked.bounds.origin != GridPoint(x=0, y=0):
                diagnostics.append(
                    _diagnostic(
                        LayoutDiagnosticCode.LOCKED_COMPONENT_CONFLICT,
                        (locked.id,),
                        f"Locked floor {locked.id!r} does not use origin (0, 0).",
                        "Use floor-local locked geometry with origin (0, 0).",
                    )
                )
                continue
            margin = requested.margin_cells if requested is not None else 1
            locked_bounds = FloorLayoutBounds(
                floor_id=floor.id,
                width_cells=locked.bounds.width_cells,
                height_cells=locked.bounds.height_cells,
                margin_cells=margin,
            )
            if requested is not None and (
                requested.width_cells != locked_bounds.width_cells
                or requested.height_cells != locked_bounds.height_cells
            ):
                diagnostics.append(
                    _diagnostic(
                        LayoutDiagnosticCode.LOCKED_COMPONENT_CONFLICT,
                        (floor.id,),
                        f"Requested bounds conflict with locked floor {floor.id!r}.",
                        "Use the locked dimensions or unlock the floor.",
                    )
                )
                continue
            resolved[floor.id] = locked_bounds
        else:
            resolved[floor.id] = requested or default_floor_bounds(floor, floor_rooms)
    return resolved


def _generate_same_floor_connections(
    request: LayoutRequest,
    room_rects: dict[str, Rect],
    floor_bounds: dict[str, FloorLayoutBounds],
    layer_by_visibility: dict[Visibility, str],
    random_source: DeterministicRandom,
    diagnostics: list[LayoutDiagnostic],
) -> tuple[list[CorridorLayout], list[DoorLayout]]:
    topology_rooms = {room.id: room for room in request.topology.rooms}
    locked_corridors = {item.id: item for item in request.locked.corridors}
    locked_doors = {item.id: item for item in request.locked.doors}
    corridors: list[CorridorLayout] = []
    doors: list[DoorLayout] = []

    for connection in request.topology.connections:
        if not isinstance(connection, CorridorConnection | DoorConnection):
            continue
        source_room = topology_rooms[connection.from_room_id]
        floor_id = source_room.floor_id
        corridor_id = (
            connection.id
            if isinstance(connection, CorridorConnection)
            else _door_corridor_id(request, connection.id)
        )
        locked_corridor = locked_corridors.get(corridor_id)
        locked_door = (
            locked_doors.get(connection.id)
            if isinstance(connection, DoorConnection)
            else None
        )
        if locked_corridor is not None and (
            not isinstance(connection, DoorConnection) or locked_door is not None
        ):
            corridors.append(locked_corridor)
            if locked_door is not None:
                doors.append(locked_door)
            continue

        floor_rectangles = tuple(
            room_rects[room.id]
            for room in request.topology.rooms
            if room.floor_id == floor_id
        )
        route = route_between_rooms(
            room_rects[connection.from_room_id],
            room_rects[connection.to_room_id],
            floor_rectangles,
            floor_bounds[floor_id],
            (
                connection.minimum_width_cells
                if isinstance(connection, CorridorConnection)
                else 1
            ),
            random_source,
        )
        if route is None:
            diagnostics.append(
                _diagnostic(
                    LayoutDiagnosticCode.CONNECTION_ROUTING_FAILED,
                    (
                        connection.id,
                        connection.from_room_id,
                        connection.to_room_id,
                    ),
                    f"Could not route connection {connection.id!r} orthogonally.",
                    "Increase floor space, move unlocked rooms, or preserve a known "
                    "working corridor.",
                )
            )
            continue

        if locked_corridor is not None:
            corridors.append(locked_corridor)
        else:
            width = (
                connection.minimum_width_cells
                if isinstance(connection, CorridorConnection)
                else 1
            )
            corridors.append(
                CorridorLayout(
                    id=corridor_id,
                    layer_id=layer_by_visibility[connection.visibility],
                    floor_id=floor_id,
                    path=route,
                    width_cells=width,
                    connects_room_ids=(
                        connection.from_room_id,
                        connection.to_room_id,
                    ),
                    visibility=connection.visibility,
                )
            )

        if isinstance(connection, DoorConnection):
            if locked_door is not None:
                doors.append(locked_door)
                continue
            segment = door_segment_at_anchor(
                room_rects[connection.from_room_id],
                route.points[0],
            )
            if segment is None:
                diagnostics.append(
                    _diagnostic(
                        LayoutDiagnosticCode.CONNECTION_ROUTING_FAILED,
                        (connection.id, connection.from_room_id),
                        f"Door {connection.id!r} could not align to its room boundary.",
                        "Regenerate the route or unlock the source room.",
                    )
                )
                continue
            doors.append(
                DoorLayout(
                    id=connection.id,
                    layer_id=layer_by_visibility[connection.visibility],
                    floor_id=floor_id,
                    door_type=connection.door_type,
                    segment=segment,
                    connects_room_ids=(
                        connection.from_room_id,
                        connection.to_room_id,
                    ),
                    gate_id=connection.gate_id,
                    hazard_id=connection.trap_id,
                    visibility=connection.visibility,
                )
            )
    return corridors, doors


def _generate_floor_transitions(
    request: LayoutRequest,
    room_rects: dict[str, Rect],
    layer_by_visibility: dict[Visibility, str],
    diagnostics: list[LayoutDiagnostic],
) -> tuple[list[StairLayout], list[VerticalLinkLayout]]:
    locked_stairs = {item.id: item for item in request.locked.stairs}
    locked_links = {item.id: item for item in request.locked.vertical_links}
    stairs: list[StairLayout] = []
    links: list[VerticalLinkLayout] = []

    for connection in request.topology.connections:
        if isinstance(connection, StairConnection):
            from_stair_id, to_stair_id = _stair_ids(request, connection.id)
            locked_link = locked_links.get(connection.id)
            from_position = _locked_stair_position(
                locked_link,
                connection.from_floor_id,
                from_stair_id,
            ) or _center_point(room_rects[connection.from_room_id])
            to_position = _locked_stair_position(
                locked_link,
                connection.to_floor_id,
                to_stair_id,
            ) or _center_point(room_rects[connection.to_room_id])
            from_stair = locked_stairs.get(from_stair_id) or StairLayout(
                id=from_stair_id,
                layer_id=layer_by_visibility[connection.visibility],
                floor_id=connection.from_floor_id,
                position=from_position,
                direction=connection.direction,
                vertical_link_id=connection.id,
                hidden=connection.from_hidden,
                visibility=connection.visibility,
            )
            to_stair = locked_stairs.get(to_stair_id) or StairLayout(
                id=to_stair_id,
                layer_id=layer_by_visibility[connection.visibility],
                floor_id=connection.to_floor_id,
                position=to_position,
                direction=_opposite_direction(connection.direction),
                vertical_link_id=connection.id,
                hidden=connection.to_hidden,
                visibility=connection.visibility,
            )
            stairs.extend((from_stair, to_stair))
            links.append(
                locked_link
                or VerticalLinkLayout(
                    id=connection.id,
                    link_type=VerticalLinkKind.STAIRS,
                    endpoints=(
                        VerticalEndpoint(
                            floor_id=connection.from_floor_id,
                            position=from_stair.position,
                            stair_id=from_stair.id,
                            hidden=connection.from_hidden,
                        ),
                        VerticalEndpoint(
                            floor_id=connection.to_floor_id,
                            position=to_stair.position,
                            stair_id=to_stair.id,
                            hidden=connection.to_hidden,
                        ),
                    ),
                    visibility=connection.visibility,
                )
            )
        elif isinstance(connection, VerticalConnection):
            links.append(
                locked_links.get(connection.id)
                or VerticalLinkLayout(
                    id=connection.id,
                    link_type=connection.link_type,
                    endpoints=(
                        VerticalEndpoint(
                            floor_id=connection.from_floor_id,
                            position=_center_point(room_rects[connection.from_room_id]),
                            stair_id=None,
                            hidden=connection.from_hidden,
                        ),
                        VerticalEndpoint(
                            floor_id=connection.to_floor_id,
                            position=_center_point(room_rects[connection.to_room_id]),
                            stair_id=None,
                            hidden=connection.to_hidden,
                        ),
                    ),
                    visibility=connection.visibility,
                )
            )

    expected_stair_ids = {
        stair_id
        for connection in request.topology.connections
        if isinstance(connection, StairConnection)
        for stair_id in _stair_ids(request, connection.id)
    }
    if {stair.id for stair in stairs} != expected_stair_ids:
        diagnostics.append(
            _diagnostic(
                LayoutDiagnosticCode.FLOOR_TRANSITION_FAILED,
                expected_stair_ids,
                "Not every requested stair endpoint was emitted.",
                "Remove conflicting locks and regenerate the floor transitions.",
            )
        )
    return stairs, links


def _locked_stair_position(
    link: VerticalLinkLayout | None,
    floor_id: str,
    stair_id: str,
) -> GridPoint | None:
    """Keep regenerated stair layouts aligned with a preserved vertical-link lock."""

    if link is None:
        return None
    endpoint = next(
        (
            item
            for item in link.endpoints
            if item.floor_id == floor_id and item.stair_id == stair_id
        ),
        None,
    )
    return endpoint.position if endpoint is not None else None


def _opposite_direction(direction: StairDirection) -> StairDirection:
    if direction is StairDirection.UP:
        return StairDirection.DOWN
    if direction is StairDirection.DOWN:
        return StairDirection.UP
    return StairDirection.BOTH


def _generate_role_anchors(
    request: LayoutRequest,
    room_rects: dict[str, Rect],
    layer_by_visibility: dict[Visibility, str],
) -> tuple[PositionAnchor, ...]:
    anchors: list[PositionAnchor] = []
    for room in request.topology.rooms:
        if room.role.value not in {"entrance", "exit"}:
            continue
        kind = (
            PositionAnchorKind.ENTRANCE
            if room.role.value == "entrance"
            else PositionAnchorKind.EXIT
        )
        anchors.append(
            PositionAnchor(
                id=derive_component_id(
                    "anchor",
                    request.package_id,
                    request.generator_version,
                    f"room-role-anchor:{room.id}:{kind.value}",
                ),
                layer_id=layer_by_visibility[room.visibility],
                floor_id=room.floor_id,
                room_id=room.id,
                kind=kind,
                position=_center_point(room_rects[room.id]),
                name=f"Generated {kind.value} anchor",
                visibility=room.visibility,
            )
        )
    return tuple(anchors)


def _center_point(rect: Rect) -> GridPoint:
    center_x, center_y = rect.center
    return GridPoint(x=center_x, y=center_y)


def _door_corridor_id(request: LayoutRequest, connection_id: str) -> str:
    return derive_component_id(
        "corridor",
        request.package_id,
        request.generator_version,
        f"door-corridor:{connection_id}",
    )


def _stair_ids(request: LayoutRequest, connection_id: str) -> tuple[str, str]:
    return (
        derive_component_id(
            "stair",
            request.package_id,
            request.generator_version,
            f"stair:{connection_id}:from",
        ),
        derive_component_id(
            "stair",
            request.package_id,
            request.generator_version,
            f"stair:{connection_id}:to",
        ),
    )


def _diagnostic(
    code: LayoutDiagnosticCode,
    affected_ids: Iterable[str],
    message: str,
    repair_hint: str,
    source_code: str | None = None,
) -> LayoutDiagnostic:
    return LayoutDiagnostic(
        code=code,
        severity=DiagnosticSeverity.ERROR,
        message=message,
        affected_ids=tuple(sorted(set(affected_ids))),
        repair_hint=repair_hint,
        source_code=source_code,
    )


def _failed_result(
    request: LayoutRequest,
    random_source: DeterministicRandom,
    diagnostics: list[LayoutDiagnostic],
) -> LayoutResult:
    ordered = tuple(
        sorted(
            diagnostics,
            key=lambda item: (
                item.code.value,
                item.affected_ids,
                item.message,
            ),
        )
    )
    return LayoutResult(
        schema_version=LAYOUT_RESULT_SCHEMA_VERSION,
        generator_version=request.generator_version,
        seed=request.seed,
        random_draw_count=random_source.draw_count,
        success=False,
        package=None,
        diagnostics=ordered,
    )
