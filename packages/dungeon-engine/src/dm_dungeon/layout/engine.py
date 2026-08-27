"""Certificate-driven constructive orthogonal dungeon layout engine."""

import json
from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha256

from dm_dungeon.contracts.common import Visibility
from dm_dungeon.contracts.geometry import (
    CorridorLayout,
    EncounterSlot,
    FloorLayout,
    GridPoint,
    GridSegment,
    PositionAnchor,
    PositionAnchorKind,
    RenderLayer,
    RenderLayerKind,
    RoomLayout,
    StairLayout,
    VerticalEndpoint,
    VerticalLinkLayout,
)
from dm_dungeon.contracts.mechanics import CompiledDoorMechanics, VerticalEndpointSide
from dm_dungeon.contracts.package import (
    DUNGEON_PACKAGE_SCHEMA_VERSION,
    ComponentIdStrategy,
    DoorMechanics,
    DungeonPackage,
    MechanicDoorLayout,
    PackageMetadata,
    PassageOpening,
    RoomMechanicMarker,
    RoomMechanicMarkerKind,
    VerticalEndpointDoorLayout,
)
from dm_dungeon.contracts.topology import (
    CorridorConnection,
    DoorConnection,
    StairConnection,
    StairDirection,
    VerticalConnection,
    VerticalLinkKind,
)
from dm_dungeon.layout.constructive import ConstructiveLayout, construct_tier_a_layout
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
    polygon_from_rect,
    rectangle_from_floor_bounds,
)
from dm_dungeon.layout.random_source import DeterministicRandom
from dm_dungeon.layout.routing import PassageRoute
from dm_dungeon.validation import (
    DiagnosticSeverity,
    validate_geometry,
    validate_topology,
)


@dataclass(frozen=True, slots=True)
class _DoorGeometry:
    """Internal shared-wall geometry before compiled mechanics are attached."""

    connection_id: str
    floor_id: str
    segment: GridSegment
    connects_room_ids: tuple[str, str]
    from_hidden: bool
    to_hidden: bool


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

    try:
        constructive = construct_tier_a_layout(request.certificate, request.topology)
    except (ValueError, RuntimeError) as error:
        diagnostics.append(
            _diagnostic(
                LayoutDiagnosticCode.INTERNAL_CONTRACT_FAILURE,
                (request.topology.id,),
                f"Certified constructive layout failed: {error}",
                "Report this deterministic generator regression; do not retry the model.",
            )
        )
        return _failed_result(request, random_source, diagnostics)

    floor_bounds = _resolve_floor_bounds(request, constructive, diagnostics)
    if diagnostics:
        return _failed_result(request, random_source, diagnostics)

    locked_floors = {item.id: item for item in request.locked.floors}
    locked_rooms = {item.id: item for item in request.locked.rooms}
    floors: list[FloorLayout] = []
    rooms: list[RoomLayout] = []
    room_rects = constructive.room_rects

    for topology_floor in request.topology.floors:
        bounds = floor_bounds[topology_floor.id]
        generated_floor = FloorLayout(
            id=topology_floor.id,
            layer_id=layer_by_visibility[topology_floor.visibility],
            name=topology_floor.name,
            level_index=topology_floor.level_index,
            bounds=rectangle_from_floor_bounds(bounds),
            visibility=topology_floor.visibility,
        )
        locked_floor = locked_floors.get(topology_floor.id)
        if locked_floor is not None and locked_floor != generated_floor:
            diagnostics.append(
                _diagnostic(
                    LayoutDiagnosticCode.LOCKED_COMPONENT_CONFLICT,
                    (locked_floor.id,),
                    "Locked floor differs from the proven constructive baseline.",
                    "Unlock the floor or use a lock from this certificate and generator.",
                )
            )
        floors.append(locked_floor or generated_floor)

    for topology_room in request.topology.rooms:
        generated_room = RoomLayout(
            id=topology_room.id,
            layer_id=layer_by_visibility[topology_room.visibility],
            floor_id=topology_room.floor_id,
            role=topology_room.role,
            boundary=polygon_from_rect(room_rects[topology_room.id]),
            capacity=topology_room.capacity,
            tags=topology_room.tags,
            visibility=topology_room.visibility,
        )
        locked_room = locked_rooms.get(topology_room.id)
        if locked_room is not None and locked_room != generated_room:
            diagnostics.append(
                _diagnostic(
                    LayoutDiagnosticCode.LOCKED_COMPONENT_CONFLICT,
                    (locked_room.id,),
                    "Locked room differs from the proven constructive baseline.",
                    "Unlock the room or use a lock from this certificate and generator.",
                )
            )
        rooms.append(locked_room or generated_room)

    if diagnostics:
        return _failed_result(request, random_source, diagnostics)

    corridors, door_geometries, passage_openings = _generate_same_floor_connections(
        request,
        constructive,
        layer_by_visibility,
        diagnostics,
    )
    stairs, vertical_links = _generate_floor_transitions(
        request,
        room_rects,
        layer_by_visibility,
        diagnostics,
    )
    composable_doors, vertical_endpoint_doors = _generate_mechanics_aware_doors(
        request,
        door_geometries,
        vertical_links,
        layer_by_visibility,
        diagnostics,
    )
    room_mechanic_markers = _generate_room_mechanic_markers(
        request,
        room_rects,
        layer_by_visibility,
        diagnostics,
    )
    encounter_slots = _generate_encounter_slots(request, layer_by_visibility)
    if diagnostics:
        return _failed_result(request, random_source, diagnostics)

    position_anchors = _generate_role_anchors(
        request,
        room_rects,
        layer_by_visibility,
    )

    try:
        package = DungeonPackage(
            schema_version=DUNGEON_PACKAGE_SCHEMA_VERSION,
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
            stairs=tuple(stairs),
            vertical_links=tuple(vertical_links),
            features=(),
            terrain=(),
            hazards=(),
            zones=(),
            labels=(),
            encounter_slots=tuple(encounter_slots),
            position_anchors=position_anchors,
            passage_openings=tuple(passage_openings),
            composable_doors=tuple(composable_doors),
            vertical_endpoint_doors=tuple(vertical_endpoint_doors),
            room_mechanic_markers=tuple(room_mechanic_markers),
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
    _validate_mechanics_plan(request, diagnostics)
    topology_payload = json.dumps(
        request.topology.model_dump(mode="json", round_trip=True),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    if (
        request.certificate.topology_id != request.topology.id
        or request.certificate.topology_hash != sha256(topology_payload).hexdigest()
        or {item.room_id for item in request.certificate.rooms}
        != {item.id for item in request.topology.rooms}
        or {item.connection_id for item in request.certificate.connections}
        != {item.id for item in request.topology.connections}
    ):
        diagnostics.append(
            _diagnostic(
                LayoutDiagnosticCode.TOPOLOGY_INVALID,
                (request.topology.id,),
                "Topology does not match its exact accepted certificate.",
                "Use the topology and certificate from one accepted compiler result.",
                source_code="certificate.binding_mismatch",
            )
        )

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


def _validate_mechanics_plan(
    request: LayoutRequest,
    diagnostics: list[LayoutDiagnostic],
) -> None:
    """Require a complete compiler plan before mechanics-aware layout begins."""

    plan = request.mechanics_plan

    topology_connection_ids = {item.id for item in request.topology.connections}
    topology_room_ids = {item.id for item in request.topology.rooms}
    if (
        set(plan.connection_ids) != topology_connection_ids
        or set(plan.room_ids) != topology_room_ids
    ):
        diagnostics.append(
            _diagnostic(
                LayoutDiagnosticCode.MECHANICS_PLAN_INVALID,
                (request.package_id,),
                "Mechanics plan IDs do not match the requested topology.",
                "Use the brief, topology, and mechanics plan from one compiler result.",
            )
        )
        return

    connections = {item.id: item for item in request.topology.connections}
    same_floor_ids: set[str] = set()
    endpoint_keys: set[tuple[str, VerticalEndpointSide]] = set()
    for mechanics in plan.door_mechanics:
        connection = connections.get(mechanics.connection_id)
        if connection is None:
            diagnostics.append(
                _mechanics_plan_diagnostic(
                    request, mechanics, "references an unknown connection"
                )
            )
            continue
        if mechanics.endpoint is None:
            if not isinstance(connection, DoorConnection):
                diagnostics.append(
                    _mechanics_plan_diagnostic(
                        request, mechanics, "must target a same-floor door"
                    )
                )
                continue
            same_floor_ids.add(mechanics.connection_id)
        elif not isinstance(connection, StairConnection | VerticalConnection):
            diagnostics.append(
                _mechanics_plan_diagnostic(
                    request, mechanics, "must target a vertical connection endpoint"
                )
            )
        else:
            endpoint_keys.add((mechanics.connection_id, mechanics.endpoint))

    required_same_floor_ids = {
        item.id
        for item in request.topology.connections
        if isinstance(item, DoorConnection)
    }
    if same_floor_ids != required_same_floor_ids:
        diagnostics.append(
            _diagnostic(
                LayoutDiagnosticCode.MECHANICS_PLAN_INVALID,
                tuple(sorted(required_same_floor_ids ^ same_floor_ids))
                or (request.package_id,),
                "Mechanics plan must provide exactly one record for every same-floor door.",
                "Recompile the design instead of editing its mechanics plan.",
            )
        )
    mechanic_ids = [item.id for item in plan.door_mechanics]
    if len(mechanic_ids) != len(set(mechanic_ids)) or len(endpoint_keys) != sum(
        item.endpoint is not None for item in plan.door_mechanics
    ):
        diagnostics.append(
            _diagnostic(
                LayoutDiagnosticCode.MECHANICS_PLAN_INVALID,
                (request.package_id,),
                "Mechanics plan contains duplicate physical-door records.",
                "Recompile the design instead of editing its mechanics plan.",
            )
        )
    marker_ids = [
        *(item.id for item in plan.room_traps),
        *(item.id for item in plan.room_puzzles),
        *(item.id for item in plan.room_features),
        *(item.id for item in plan.room_objectives),
        *(item.id for item in plan.encounter_slots),
    ]
    marker_room_ids = {
        *(item.room_id for item in plan.room_traps),
        *(item.room_id for item in plan.room_puzzles),
        *(item.room_id for item in plan.room_features),
        *(item.room_id for item in plan.room_objectives),
        *(item.room_id for item in plan.encounter_slots),
    }
    unknown_marker_rooms = sorted(marker_room_ids - topology_room_ids)
    if unknown_marker_rooms or len(marker_ids) != len(set(marker_ids)):
        diagnostics.append(
            _diagnostic(
                LayoutDiagnosticCode.MECHANICS_PLAN_INVALID,
                tuple(unknown_marker_rooms) or (request.package_id,),
                "Mechanics plan contains invalid room-marker records.",
                "Recompile the design instead of editing its mechanics plan.",
            )
        )


def _mechanics_plan_diagnostic(
    request: LayoutRequest,
    mechanics: CompiledDoorMechanics,
    issue: str,
) -> LayoutDiagnostic:
    return _diagnostic(
        LayoutDiagnosticCode.MECHANICS_PLAN_INVALID,
        (mechanics.id, mechanics.connection_id),
        f"Mechanics record {mechanics.id!r} {issue}.",
        "Recompile the design instead of editing its mechanics plan.",
    )


def _validate_locked_component_ids(
    request: LayoutRequest,
    diagnostics: list[LayoutDiagnostic],
) -> None:
    floor_ids = {floor.id for floor in request.topology.floors}
    room_ids = {room.id for room in request.topology.rooms}
    corridor_ids: set[str] = set()
    door_ids = {
        item.id
        for item in request.mechanics_plan.door_mechanics
        if item.endpoint is None
    }
    stair_ids: set[str] = set()
    vertical_link_ids: set[str] = set()
    for connection in request.topology.connections:
        if isinstance(connection, CorridorConnection | DoorConnection):
            corridor_ids.add(connection.id)
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

    mechanics_by_id = {
        item.id: item
        for item in request.mechanics_plan.door_mechanics
        if item.endpoint is None
    }
    topology_doors = {
        item.id: item
        for item in request.topology.connections
        if isinstance(item, DoorConnection)
    }
    for locked_door in request.locked.doors:
        mechanics = mechanics_by_id.get(locked_door.id)
        locked_connection = topology_doors.get(locked_door.connection_id)
        if mechanics is None or locked_connection is None:
            continue
        if (
            mechanics.connection_id != locked_door.connection_id
            or locked_door.connects_room_ids
            != (locked_connection.from_room_id, locked_connection.to_room_id)
            or locked_door.from_hidden != locked_connection.from_hidden
            or locked_door.to_hidden != locked_connection.to_hidden
            or locked_door.mechanics != _package_door_mechanics(mechanics)
        ):
            diagnostics.append(
                _diagnostic(
                    LayoutDiagnosticCode.LOCKED_COMPONENT_CONFLICT,
                    (locked_door.id, locked_door.connection_id),
                    f"Locked door {locked_door.id!r} conflicts with compiled intent.",
                    "Use a lock created from the same compiler and topology version.",
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
    constructive: ConstructiveLayout,
    diagnostics: list[LayoutDiagnostic],
) -> dict[str, FloorLayoutBounds]:
    """Check optional maxima, then retain the exact certificate-derived bound."""

    provided = {item.floor_id: item for item in request.floor_bounds}
    required = constructive.bounds
    maximum = provided.get(required.floor_id)
    if maximum is not None and (
        maximum.width_cells < required.width_cells
        or maximum.height_cells < required.height_cells
    ):
        diagnostics.append(
            _diagnostic(
                LayoutDiagnosticCode.FLOOR_BOUNDS_INVALID,
                (required.floor_id,),
                f"Floor maximum {maximum.width_cells}x{maximum.height_cells} cannot "
                f"contain required constructive bounds "
                f"{required.width_cells}x{required.height_cells}.",
                "Increase the caller maximum to at least the reported required bounds.",
            )
        )
    return {required.floor_id: required}


def _endpoint_visibility(hidden: bool, room_visibility: Visibility) -> Visibility:
    if hidden or room_visibility is Visibility.DM_ONLY:
        return Visibility.DM_ONLY
    return Visibility.PLAYER_SAFE


def _combined_visibility(*values: Visibility) -> Visibility:
    if any(value is Visibility.PLAYER_SAFE for value in values):
        return Visibility.PLAYER_SAFE
    return Visibility.DM_ONLY


def _connection_endpoint_visibilities(
    from_hidden: bool,
    to_hidden: bool,
    declared_visibility: Visibility,
    from_room_visibility: Visibility,
    to_room_visibility: Visibility,
) -> tuple[Visibility, Visibility]:
    if not from_hidden and not to_hidden:
        return declared_visibility, declared_visibility
    return (
        _endpoint_visibility(from_hidden, from_room_visibility),
        _endpoint_visibility(to_hidden, to_room_visibility),
    )


def _connection_layout_visibility(
    from_hidden: bool,
    to_hidden: bool,
    declared_visibility: Visibility,
    from_room_visibility: Visibility,
    to_room_visibility: Visibility,
) -> Visibility:
    return _combined_visibility(
        *_connection_endpoint_visibilities(
            from_hidden,
            to_hidden,
            declared_visibility,
            from_room_visibility,
            to_room_visibility,
        )
    )


def _generate_same_floor_connections(
    request: LayoutRequest,
    constructive: ConstructiveLayout,
    layer_by_visibility: dict[Visibility, str],
    diagnostics: list[LayoutDiagnostic],
) -> tuple[list[CorridorLayout], list[_DoorGeometry], list[PassageOpening]]:
    """Materialize every certified edge in its preallocated passage channel."""

    topology_rooms = {room.id: room for room in request.topology.rooms}
    locked_corridors = {item.id: item for item in request.locked.corridors}
    locked_doors = {item.connection_id: item for item in request.locked.doors}
    corridors: list[CorridorLayout] = []
    door_geometries: list[_DoorGeometry] = []
    passage_openings: list[PassageOpening] = []

    for connection in request.topology.connections:
        if not isinstance(connection, CorridorConnection | DoorConnection):
            continue
        source_room = topology_rooms[connection.from_room_id]
        target_room = topology_rooms[connection.to_room_id]
        floor_id = source_room.floor_id
        layout_visibility = _connection_layout_visibility(
            connection.from_hidden,
            connection.to_hidden,
            connection.visibility,
            source_room.visibility,
            target_room.visibility,
        )
        passage_route = constructive.passage_routes[connection.id]
        width_cells = (
            connection.minimum_width_cells
            if isinstance(connection, CorridorConnection)
            else 1
        )
        generated_corridor = CorridorLayout(
            id=connection.id,
            layer_id=layer_by_visibility[layout_visibility],
            floor_id=floor_id,
            path=passage_route.path,
            width_cells=width_cells,
            connects_room_ids=(connection.from_room_id, connection.to_room_id),
            visibility=layout_visibility,
        )
        locked_corridor = locked_corridors.get(connection.id)
        if locked_corridor is not None and locked_corridor != generated_corridor:
            diagnostics.append(
                _diagnostic(
                    LayoutDiagnosticCode.LOCKED_COMPONENT_CONFLICT,
                    (connection.id,),
                    "Locked corridor differs from its certificate-reserved channel.",
                    "Unlock it or retain the exact constructive corridor.",
                )
            )
        corridors.append(locked_corridor or generated_corridor)
        passage_openings.extend(
            _passage_openings_for_connection(request, connection.id, passage_route)
        )

        if isinstance(connection, DoorConnection):
            locked_door = locked_doors.get(connection.id)
            segment = passage_route.from_segment
            if locked_door is not None and locked_door.segment != segment:
                diagnostics.append(
                    _diagnostic(
                        LayoutDiagnosticCode.LOCKED_COMPONENT_CONFLICT,
                        (locked_door.id,),
                        "Locked door differs from its certificate-assigned opening.",
                        "Unlock it or retain the exact constructive door opening.",
                    )
                )
            door_geometries.append(
                _DoorGeometry(
                    connection_id=connection.id,
                    floor_id=floor_id,
                    segment=locked_door.segment if locked_door is not None else segment,
                    connects_room_ids=(
                        connection.from_room_id,
                        connection.to_room_id,
                    ),
                    from_hidden=connection.from_hidden,
                    to_hidden=connection.to_hidden,
                )
            )

    return corridors, door_geometries, passage_openings


def _passage_openings_for_connection(
    request: LayoutRequest,
    connection_id: str,
    passage_route: PassageRoute,
) -> tuple[PassageOpening, PassageOpening]:
    """Create stable package openings from a validated internal passage route."""
    # The narrow attributes are shared by generated and lock-recovered routes.
    from_segment = passage_route.from_segment
    from_direction = passage_route.from_direction
    to_segment = passage_route.to_segment
    to_direction = passage_route.to_direction
    connection = next(
        item for item in request.topology.connections if item.id == connection_id
    )
    assert isinstance(connection, CorridorConnection | DoorConnection)
    return (
        PassageOpening(
            id=derive_component_id(
                "passage-opening",
                request.package_id,
                request.generator_version,
                f"{connection_id}:from",
            ),
            corridor_id=connection_id,
            room_id=connection.from_room_id,
            segment=from_segment,
            approach_direction=from_direction,
        ),
        PassageOpening(
            id=derive_component_id(
                "passage-opening",
                request.package_id,
                request.generator_version,
                f"{connection_id}:to",
            ),
            corridor_id=connection_id,
            room_id=connection.to_room_id,
            segment=to_segment,
            approach_direction=to_direction,
        ),
    )


def _generate_mechanics_aware_doors(
    request: LayoutRequest,
    door_geometries: list[_DoorGeometry],
    vertical_links: list[VerticalLinkLayout],
    layer_by_visibility: dict[Visibility, str],
    diagnostics: list[LayoutDiagnostic],
) -> tuple[list[MechanicDoorLayout], list[VerticalEndpointDoorLayout]]:
    """Attach compiler-pinned mechanics to the exact openings chosen by layout."""

    mechanics_by_connection = {
        item.connection_id: item
        for item in request.mechanics_plan.door_mechanics
        if item.endpoint is None
    }
    topology_rooms = {item.id: item for item in request.topology.rooms}
    locked_doors = {item.connection_id: item for item in request.locked.doors}
    composable_doors: list[MechanicDoorLayout] = []
    for door in door_geometries:
        mechanics = mechanics_by_connection.get(door.connection_id)
        if mechanics is None:
            diagnostics.append(
                _diagnostic(
                    LayoutDiagnosticCode.MECHANICS_PLAN_INVALID,
                    (door.connection_id,),
                    f"Same-floor door {door.connection_id!r} has no compiled mechanics record.",
                    "Recompile the design instead of editing its mechanics plan.",
                )
            )
            continue
        locked_door = locked_doors.get(door.connection_id)
        if locked_door is not None:
            composable_doors.append(locked_door)
            continue
        # Derive geometry publication from endpoint/room discovery. Player renderers
        # normalize mechanics to an ordinary door without emitting mechanic data.
        from_room, to_room = (topology_rooms[item] for item in door.connects_room_ids)
        visibility = _connection_layout_visibility(
            door.from_hidden,
            door.to_hidden,
            Visibility.PLAYER_SAFE,
            from_room.visibility,
            to_room.visibility,
        )
        composable_doors.append(
            MechanicDoorLayout(
                id=mechanics.id,
                connection_id=door.connection_id,
                layer_id=layer_by_visibility[visibility],
                floor_id=door.floor_id,
                segment=door.segment,
                connects_room_ids=door.connects_room_ids,
                from_hidden=door.from_hidden,
                to_hidden=door.to_hidden,
                mechanics=_package_door_mechanics(mechanics),
                visibility=visibility,
            )
        )

    links = {item.id: item for item in vertical_links}
    connections = {item.id: item for item in request.topology.connections}
    endpoint_doors: list[VerticalEndpointDoorLayout] = []
    for mechanics in request.mechanics_plan.door_mechanics:
        if mechanics.endpoint is None:
            continue
        assert mechanics.endpoint_kind is not None
        link = links.get(mechanics.connection_id)
        connection = connections.get(mechanics.connection_id)
        if link is None or not isinstance(
            connection, StairConnection | VerticalConnection
        ):
            diagnostics.append(
                _mechanics_plan_diagnostic(
                    request, mechanics, "has no generated vertical link"
                )
            )
            continue
        floor_id = (
            connection.from_floor_id
            if mechanics.endpoint is VerticalEndpointSide.FROM
            else connection.to_floor_id
        )
        room_id = (
            connection.from_room_id
            if mechanics.endpoint is VerticalEndpointSide.FROM
            else connection.to_room_id
        )
        endpoint = next(
            (item for item in link.endpoints if item.floor_id == floor_id), None
        )
        if endpoint is None:
            diagnostics.append(
                _mechanics_plan_diagnostic(
                    request, mechanics, "has no generated endpoint position"
                )
            )
            continue
        visibility = endpoint.visibility
        endpoint_doors.append(
            VerticalEndpointDoorLayout(
                id=mechanics.id,
                layer_id=layer_by_visibility[visibility],
                vertical_link_id=mechanics.connection_id,
                endpoint=mechanics.endpoint,
                kind=mechanics.endpoint_kind,
                floor_id=floor_id,
                room_id=room_id,
                position=endpoint.position,
                mechanics=_package_door_mechanics(mechanics),
                visibility=visibility,
            )
        )
    return composable_doors, endpoint_doors


def _generate_room_mechanic_markers(
    request: LayoutRequest,
    room_rects: dict[str, Rect],
    layer_by_visibility: dict[Visibility, str],
    diagnostics: list[LayoutDiagnostic],
) -> list[RoomMechanicMarker]:
    """Choose stable, distinct interior cells for compiler-pinned room mechanics."""

    rooms = {item.id: item for item in request.topology.rooms}
    planned = [
        *(
            (item.id, item.room_id, RoomMechanicMarkerKind.TRAP)
            for item in request.mechanics_plan.room_traps
        ),
        *(
            (item.id, item.room_id, RoomMechanicMarkerKind.PUZZLE)
            for item in request.mechanics_plan.room_puzzles
        ),
        *(
            (item.id, item.room_id, RoomMechanicMarkerKind.FEATURE)
            for item in request.mechanics_plan.room_features
        ),
        *(
            (item.id, item.room_id, RoomMechanicMarkerKind.OBJECTIVE)
            for item in request.mechanics_plan.room_objectives
        ),
    ]
    by_room: dict[str, list[tuple[str, RoomMechanicMarkerKind]]] = {}
    for marker_id, room_id, kind in planned:
        by_room.setdefault(room_id, []).append((marker_id, kind))

    markers: list[RoomMechanicMarker] = []
    for room_id, room_markers in sorted(by_room.items()):
        rect = room_rects.get(room_id)
        room = rooms.get(room_id)
        if rect is None or room is None:
            diagnostics.append(
                _diagnostic(
                    LayoutDiagnosticCode.MECHANICS_PLAN_INVALID,
                    (room_id,),
                    "Mechanics plan references a room without generated geometry.",
                    "Recompile the design instead of editing its mechanics plan.",
                )
            )
            continue
        cells = sorted(
            (
                GridPoint(x=x, y=y)
                for x in range(rect.x, rect.right)
                for y in range(rect.y, rect.bottom)
            ),
            key=lambda point: (
                abs(point.x - rect.center[0]) + abs(point.y - rect.center[1]),
                point.y,
                point.x,
            ),
        )
        ordered_markers = sorted(room_markers)
        if len(ordered_markers) > len(cells):
            diagnostics.append(
                _diagnostic(
                    LayoutDiagnosticCode.MECHANICS_MARKER_PLACEMENT_FAILED,
                    tuple(marker_id for marker_id, _ in ordered_markers),
                    f"Room {room_id!r} has insufficient interior cells for its "
                    "requested mechanics markers.",
                    "Use fewer room-local mechanics or increase the room size band.",
                )
            )
            continue
        for (marker_id, kind), position in zip(ordered_markers, cells, strict=False):
            visibility = (
                Visibility.DM_ONLY
                if kind is RoomMechanicMarkerKind.TRAP
                or room.visibility is Visibility.DM_ONLY
                else Visibility.PLAYER_SAFE
            )
            markers.append(
                RoomMechanicMarker(
                    id=marker_id,
                    layer_id=layer_by_visibility[visibility],
                    floor_id=room.floor_id,
                    room_id=room_id,
                    position=position,
                    kind=kind,
                    visibility=visibility,
                )
            )
    return markers


def _generate_encounter_slots(
    request: LayoutRequest,
    layer_by_visibility: dict[Visibility, str],
) -> list[EncounterSlot]:
    """Materialize stable room-local slots without composing encounters."""

    rooms = {item.id: item for item in request.topology.rooms}
    return [
        EncounterSlot(
            id=item.id,
            layer_id=layer_by_visibility[Visibility.DM_ONLY],
            floor_id=rooms[item.room_id].floor_id,
            room_id=item.room_id,
            minimum_creatures=1,
            maximum_creatures=rooms[item.room_id].capacity.maximum_occupants,
            tags=(item.intent.value,),
            visibility=Visibility.DM_ONLY,
        )
        for item in request.mechanics_plan.encounter_slots
    ]


def _package_door_mechanics(
    mechanics: CompiledDoorMechanics,
) -> DoorMechanics:
    return DoorMechanics(
        concealed=mechanics.concealed,
        gate_id=mechanics.gate_id,
        gate_kind=mechanics.gate_kind,
        trap_id=mechanics.trap_id,
        discovery_difficulty=mechanics.discovery_difficulty,
        unlock_difficulty=mechanics.unlock_difficulty,
        disable_difficulty=mechanics.disable_difficulty,
    )


def _generate_floor_transitions(
    request: LayoutRequest,
    room_rects: dict[str, Rect],
    layer_by_visibility: dict[Visibility, str],
    diagnostics: list[LayoutDiagnostic],
) -> tuple[list[StairLayout], list[VerticalLinkLayout]]:
    topology_rooms = {room.id: room for room in request.topology.rooms}
    locked_stairs = {item.id: item for item in request.locked.stairs}
    locked_links = {item.id: item for item in request.locked.vertical_links}
    stairs: list[StairLayout] = []
    links: list[VerticalLinkLayout] = []

    for connection in request.topology.connections:
        if isinstance(connection, StairConnection):
            from_visibility, to_visibility = _connection_endpoint_visibilities(
                connection.from_hidden,
                connection.to_hidden,
                connection.visibility,
                topology_rooms[connection.from_room_id].visibility,
                topology_rooms[connection.to_room_id].visibility,
            )
            link_visibility = _combined_visibility(from_visibility, to_visibility)
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
                layer_id=layer_by_visibility[from_visibility],
                floor_id=connection.from_floor_id,
                position=from_position,
                direction=connection.direction,
                vertical_link_id=connection.id,
                visibility=from_visibility,
            )
            to_stair = locked_stairs.get(to_stair_id) or StairLayout(
                id=to_stair_id,
                layer_id=layer_by_visibility[to_visibility],
                floor_id=connection.to_floor_id,
                position=to_position,
                direction=_opposite_direction(connection.direction),
                vertical_link_id=connection.id,
                visibility=to_visibility,
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
                            visibility=from_visibility,
                            stair_id=from_stair.id,
                        ),
                        VerticalEndpoint(
                            floor_id=connection.to_floor_id,
                            position=to_stair.position,
                            visibility=to_visibility,
                            stair_id=to_stair.id,
                        ),
                    ),
                    visibility=link_visibility,
                )
            )
        elif isinstance(connection, VerticalConnection):
            from_visibility, to_visibility = _connection_endpoint_visibilities(
                connection.from_hidden,
                connection.to_hidden,
                connection.visibility,
                topology_rooms[connection.from_room_id].visibility,
                topology_rooms[connection.to_room_id].visibility,
            )
            links.append(
                locked_links.get(connection.id)
                or VerticalLinkLayout(
                    id=connection.id,
                    link_type=connection.link_type,
                    endpoints=(
                        VerticalEndpoint(
                            floor_id=connection.from_floor_id,
                            position=_center_point(room_rects[connection.from_room_id]),
                            visibility=from_visibility,
                            stair_id=None,
                        ),
                        VerticalEndpoint(
                            floor_id=connection.to_floor_id,
                            position=_center_point(room_rects[connection.to_room_id]),
                            visibility=to_visibility,
                            stair_id=None,
                        ),
                    ),
                    visibility=_combined_visibility(from_visibility, to_visibility),
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
        if room.role.value not in {"entrance", "exit", "objective"}:
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
