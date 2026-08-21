"""Deterministic topology, gating, and dependency validation.

See ``TOPOLOGY_MATH.md`` beside this module for the graph theory, progression
fixed-point reasoning, and topology-versus-geometry proof boundary.
"""

from collections import defaultdict, deque
from collections.abc import Iterable, Mapping

from dm_dungeon.contracts.common import Visibility
from dm_dungeon.contracts.topology import (
    ChokepointComponentKind,
    CorridorConnection,
    DoorConnection,
    DungeonTopology,
    GateDependencyKind,
    RoomRole,
    StairConnection,
    VerticalConnection,
)
from dm_dungeon.validation.diagnostics import (
    TOPOLOGY_VALIDATOR_VERSION,
    DiagnosticSeverity,
    TopologyDiagnosticCode,
    TopologyValidationReport,
    ValidationDiagnostic,
)

Adjacency = dict[str, set[str]]


def validate_topology(topology: DungeonTopology) -> TopologyValidationReport:
    """Validate a topology without mutating it or accessing external state."""
    diagnostics: list[ValidationDiagnostic] = []

    _validate_references_and_connection_kinds(topology, diagnostics)
    adjacency = _build_adjacency(topology)
    _validate_required_room_reachability(topology, adjacency, diagnostics)
    _validate_loop_requirements(topology, adjacency, diagnostics)
    _validate_branch_requirements(topology, adjacency, diagnostics)
    _validate_chokepoint_requirements(topology, adjacency, diagnostics)
    _validate_secret_bypasses(topology, diagnostics)
    _validate_gate_reciprocity(topology, diagnostics)
    _validate_gate_dependency_cycles(topology, diagnostics)
    _validate_gate_progression(topology, diagnostics)

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
    valid = not any(item.severity is DiagnosticSeverity.ERROR for item in ordered)
    return TopologyValidationReport(
        validator_version=TOPOLOGY_VALIDATOR_VERSION,
        topology_id=topology.id,
        valid=valid,
        diagnostics=ordered,
    )


def _diagnostic(
    code: TopologyDiagnosticCode,
    affected_ids: Iterable[str],
    message: str,
    repair_hint: str,
    severity: DiagnosticSeverity = DiagnosticSeverity.ERROR,
) -> ValidationDiagnostic:
    return ValidationDiagnostic(
        code=code,
        severity=severity,
        message=message,
        affected_ids=tuple(sorted(set(affected_ids))),
        repair_hint=repair_hint,
    )


def _validate_references_and_connection_kinds(
    topology: DungeonTopology,
    diagnostics: list[ValidationDiagnostic],
) -> None:
    floor_ids = {floor.id for floor in topology.floors}
    rooms = {room.id: room for room in topology.rooms}
    connections = {connection.id: connection for connection in topology.connections}
    gate_ids = {gate.id for gate in topology.gates}
    key_ids = {key.id for key in topology.keys}
    clue_ids = {clue.id for clue in topology.clues}

    for room in topology.rooms:
        if room.floor_id not in floor_ids:
            diagnostics.append(
                _diagnostic(
                    TopologyDiagnosticCode.UNKNOWN_FLOOR_REFERENCE,
                    (room.id, room.floor_id),
                    f"Room {room.id!r} references unknown floor {room.floor_id!r}.",
                    "Assign the room to a declared topology floor.",
                )
            )

    for connection in topology.connections:
        from_room = rooms.get(connection.from_room_id)
        to_room = rooms.get(connection.to_room_id)
        for room_id in (connection.from_room_id, connection.to_room_id):
            if room_id not in rooms:
                diagnostics.append(
                    _diagnostic(
                        TopologyDiagnosticCode.UNKNOWN_ROOM_REFERENCE,
                        (connection.id, room_id),
                        f"Connection {connection.id!r} references unknown room "
                        f"{room_id!r}.",
                        "Connect only declared room IDs or add the missing room.",
                    )
                )

        if connection.from_room_id == connection.to_room_id:
            diagnostics.append(
                _diagnostic(
                    TopologyDiagnosticCode.SELF_CONNECTION,
                    (connection.id, connection.from_room_id),
                    f"Connection {connection.id!r} connects a room to itself.",
                    "Connect two distinct rooms or remove the connection.",
                )
            )

        if isinstance(connection, CorridorConnection | DoorConnection):
            if (
                from_room is not None
                and to_room is not None
                and from_room.floor_id != to_room.floor_id
            ):
                diagnostics.append(
                    _diagnostic(
                        TopologyDiagnosticCode.SAME_FLOOR_CONNECTION_INVALID,
                        (connection.id, from_room.id, to_room.id),
                        f"Same-floor connection {connection.id!r} spans floors.",
                        "Use stairs or a vertical_link for cross-floor movement.",
                    )
                )
        elif isinstance(connection, StairConnection | VerticalConnection):
            _validate_floor_transition(
                connection,
                floor_ids,
                rooms,
                diagnostics,
            )

    for gate in topology.gates:
        for connection_id in gate.blocks_connection_ids:
            if connection_id not in connections:
                diagnostics.append(
                    _diagnostic(
                        TopologyDiagnosticCode.UNKNOWN_CONNECTION_REFERENCE,
                        (gate.id, connection_id),
                        f"Gate {gate.id!r} blocks unknown connection "
                        f"{connection_id!r}.",
                        "Reference a declared connection from the gate.",
                    )
                )
        for dependency in gate.requires_all:
            known_ids = {
                GateDependencyKind.GATE: gate_ids,
                GateDependencyKind.KEY: key_ids,
                GateDependencyKind.CLUE: clue_ids,
            }[dependency.kind]
            if dependency.target_id not in known_ids:
                code = {
                    GateDependencyKind.GATE: (
                        TopologyDiagnosticCode.UNKNOWN_GATE_REFERENCE
                    ),
                    GateDependencyKind.KEY: TopologyDiagnosticCode.UNKNOWN_KEY_REFERENCE,
                    GateDependencyKind.CLUE: (
                        TopologyDiagnosticCode.UNKNOWN_CLUE_REFERENCE
                    ),
                }[dependency.kind]
                diagnostics.append(
                    _diagnostic(
                        code,
                        (gate.id, dependency.target_id),
                        f"Gate {gate.id!r} requires unknown {dependency.kind.value} "
                        f"{dependency.target_id!r}.",
                        "Reference a declared dependency or remove the requirement.",
                    )
                )

    for key in topology.keys:
        _require_room_reference(
            owner_kind="Key",
            owner_id=key.id,
            room_id=key.located_in_room_id,
            room_ids=rooms.keys(),
            diagnostics=diagnostics,
        )
        for gate_id in key.opens_gate_ids:
            if gate_id not in gate_ids:
                diagnostics.append(
                    _diagnostic(
                        TopologyDiagnosticCode.UNKNOWN_GATE_REFERENCE,
                        (key.id, gate_id),
                        f"Key {key.id!r} opens unknown gate {gate_id!r}.",
                        "Reference a declared gate from the key placement.",
                    )
                )

    for clue in topology.clues:
        _require_room_reference(
            owner_kind="Clue",
            owner_id=clue.id,
            room_id=clue.located_in_room_id,
            room_ids=rooms.keys(),
            diagnostics=diagnostics,
        )
        for gate_id in clue.supports_gate_ids:
            if gate_id not in gate_ids:
                diagnostics.append(
                    _diagnostic(
                        TopologyDiagnosticCode.UNKNOWN_GATE_REFERENCE,
                        (clue.id, gate_id),
                        f"Clue {clue.id!r} supports unknown gate {gate_id!r}.",
                        "Reference a declared gate from the clue placement.",
                    )
                )

    for loop in topology.loops:
        _require_room_references("Loop", loop.id, loop.room_ids, rooms, diagnostics)
    for branch in topology.branches:
        _require_room_references(
            "Branch",
            branch.id,
            (branch.junction_room_id, *branch.branch_room_ids),
            rooms,
            diagnostics,
        )
    for chokepoint in topology.chokepoints:
        _require_room_references(
            "Chokepoint",
            chokepoint.id,
            chokepoint.separates_room_ids,
            rooms,
            diagnostics,
        )
        known_components = (
            rooms
            if chokepoint.component_kind is ChokepointComponentKind.ROOM
            else connections
        )
        if chokepoint.component_id not in known_components:
            code = (
                TopologyDiagnosticCode.UNKNOWN_ROOM_REFERENCE
                if chokepoint.component_kind is ChokepointComponentKind.ROOM
                else TopologyDiagnosticCode.UNKNOWN_CONNECTION_REFERENCE
            )
            diagnostics.append(
                _diagnostic(
                    code,
                    (chokepoint.id, chokepoint.component_id),
                    f"Chokepoint {chokepoint.id!r} references unknown "
                    f"{chokepoint.component_kind.value} "
                    f"{chokepoint.component_id!r}.",
                    "Reference a declared room or connection as the chokepoint.",
                )
            )

    for bypass in topology.secret_bypasses:
        _require_room_references(
            "Secret bypass",
            bypass.id,
            (bypass.entry_room_id, bypass.exit_room_id),
            rooms,
            diagnostics,
        )
        for connection_id in bypass.connection_ids:
            if connection_id not in connections:
                diagnostics.append(
                    _diagnostic(
                        TopologyDiagnosticCode.UNKNOWN_CONNECTION_REFERENCE,
                        (bypass.id, connection_id),
                        f"Secret bypass {bypass.id!r} references unknown connection "
                        f"{connection_id!r}.",
                        "Use declared connections to define the bypass route.",
                    )
                )
        for gate_id in bypass.bypassed_gate_ids:
            if gate_id not in gate_ids:
                diagnostics.append(
                    _diagnostic(
                        TopologyDiagnosticCode.UNKNOWN_GATE_REFERENCE,
                        (bypass.id, gate_id),
                        f"Secret bypass {bypass.id!r} references unknown gate "
                        f"{gate_id!r}.",
                        "Reference a declared gate that the route bypasses.",
                    )
                )


def _validate_floor_transition(
    connection: StairConnection | VerticalConnection,
    floor_ids: set[str],
    rooms: Mapping[str, object],
    diagnostics: list[ValidationDiagnostic],
) -> None:
    for floor_id in (connection.from_floor_id, connection.to_floor_id):
        if floor_id not in floor_ids:
            diagnostics.append(
                _diagnostic(
                    TopologyDiagnosticCode.UNKNOWN_FLOOR_REFERENCE,
                    (connection.id, floor_id),
                    f"Floor transition {connection.id!r} references unknown floor "
                    f"{floor_id!r}.",
                    "Reference declared floors at both transition endpoints.",
                )
            )

    from_room = rooms.get(connection.from_room_id)
    to_room = rooms.get(connection.to_room_id)
    invalid_ids: list[str] = []
    if connection.from_floor_id == connection.to_floor_id:
        invalid_ids.extend((connection.from_floor_id, connection.to_floor_id))
    if from_room is not None and getattr(from_room, "floor_id", None) != (
        connection.from_floor_id
    ):
        invalid_ids.append(connection.from_room_id)
    if to_room is not None and getattr(to_room, "floor_id", None) != (
        connection.to_floor_id
    ):
        invalid_ids.append(connection.to_room_id)

    if invalid_ids:
        diagnostics.append(
            _diagnostic(
                TopologyDiagnosticCode.FLOOR_TRANSITION_INVALID,
                (connection.id, *invalid_ids),
                f"Floor transition {connection.id!r} has mismatched endpoints.",
                "Use distinct declared floors matching the endpoint rooms.",
            )
        )


def _require_room_reference(
    owner_kind: str,
    owner_id: str,
    room_id: str,
    room_ids: Iterable[str],
    diagnostics: list[ValidationDiagnostic],
) -> None:
    if room_id not in set(room_ids):
        diagnostics.append(
            _diagnostic(
                TopologyDiagnosticCode.UNKNOWN_ROOM_REFERENCE,
                (owner_id, room_id),
                f"{owner_kind} {owner_id!r} references unknown room {room_id!r}.",
                "Reference a declared room or add the missing room.",
            )
        )


def _require_room_references(
    owner_kind: str,
    owner_id: str,
    room_ids: Iterable[str],
    known_rooms: Mapping[str, object],
    diagnostics: list[ValidationDiagnostic],
) -> None:
    for room_id in room_ids:
        _require_room_reference(
            owner_kind,
            owner_id,
            room_id,
            known_rooms.keys(),
            diagnostics,
        )


def _build_adjacency(
    topology: DungeonTopology,
    *,
    allowed_connection_ids: set[str] | None = None,
    excluded_connection_ids: set[str] | None = None,
    excluded_room_ids: set[str] | None = None,
    opened_gate_ids: set[str] | None = None,
) -> Adjacency:
    excluded_connections = excluded_connection_ids or set()
    excluded_rooms = excluded_room_ids or set()
    room_ids = {room.id for room in topology.rooms} - excluded_rooms
    adjacency: Adjacency = {room_id: set() for room_id in room_ids}

    blockers: dict[str, set[str]] = defaultdict(set)
    for gate in topology.gates:
        for connection_id in gate.blocks_connection_ids:
            blockers[connection_id].add(gate.id)

    for connection in topology.connections:
        if allowed_connection_ids is not None:
            if connection.id not in allowed_connection_ids:
                continue
        if connection.id in excluded_connections:
            continue
        if opened_gate_ids is not None:
            if not blockers[connection.id].issubset(opened_gate_ids):
                continue
        if (
            connection.from_room_id not in adjacency
            or connection.to_room_id not in adjacency
            or connection.from_room_id == connection.to_room_id
        ):
            continue
        adjacency[connection.from_room_id].add(connection.to_room_id)
        adjacency[connection.to_room_id].add(connection.from_room_id)
    return adjacency


def _reachable(adjacency: Adjacency, starts: Iterable[str]) -> set[str]:
    visited = {start for start in starts if start in adjacency}
    pending = deque(sorted(visited))
    while pending:
        room_id = pending.popleft()
        for neighbor in sorted(adjacency[room_id]):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            pending.append(neighbor)
    return visited


def _has_path(adjacency: Adjacency, start: str, end: str) -> bool:
    return end in _reachable(adjacency, (start,))


def _validate_required_room_reachability(
    topology: DungeonTopology,
    adjacency: Adjacency,
    diagnostics: list[ValidationDiagnostic],
) -> None:
    entrance_ids = tuple(
        room.id for room in topology.rooms if room.role is RoomRole.ENTRANCE
    )
    exit_ids = tuple(room.id for room in topology.rooms if room.role is RoomRole.EXIT)

    if not entrance_ids:
        diagnostics.append(
            _diagnostic(
                TopologyDiagnosticCode.MISSING_ENTRANCE,
                (topology.id,),
                "Topology has no entrance room.",
                "Mark at least one declared room with the entrance role.",
            )
        )
    if not exit_ids:
        diagnostics.append(
            _diagnostic(
                TopologyDiagnosticCode.MISSING_EXIT,
                (topology.id,),
                "Topology has no exit room.",
                "Mark at least one declared room with the exit role.",
            )
        )

    from_entrances = _reachable(adjacency, entrance_ids)
    from_exits = _reachable(adjacency, exit_ids)
    for room in topology.rooms:
        if not room.required:
            continue
        if entrance_ids and room.id not in from_entrances:
            diagnostics.append(
                _diagnostic(
                    TopologyDiagnosticCode.REQUIRED_ROOM_UNREACHABLE_FROM_ENTRANCE,
                    (room.id, *entrance_ids),
                    f"Required room {room.id!r} is unreachable from every entrance.",
                    "Connect the room to an entrance-reachable component.",
                )
            )
        if exit_ids and room.id not in from_exits:
            diagnostics.append(
                _diagnostic(
                    TopologyDiagnosticCode.REQUIRED_ROOM_UNREACHABLE_FROM_EXIT,
                    (room.id, *exit_ids),
                    f"Required room {room.id!r} cannot reach any exit.",
                    "Connect the room to an exit-reachable component.",
                )
            )


def _validate_loop_requirements(
    topology: DungeonTopology,
    adjacency: Adjacency,
    diagnostics: list[ValidationDiagnostic],
) -> None:
    known_rooms = set(adjacency)
    for loop in topology.loops:
        if not set(loop.room_ids).issubset(known_rooms):
            continue
        pairs = tuple(
            zip(
                loop.room_ids,
                (*loop.room_ids[1:], loop.room_ids[0]),
                strict=True,
            )
        )
        if len(set(loop.room_ids)) != len(loop.room_ids) or any(
            to_room not in adjacency[from_room] for from_room, to_room in pairs
        ):
            diagnostics.append(
                _diagnostic(
                    TopologyDiagnosticCode.LOOP_NOT_REALIZED,
                    (loop.id, *loop.room_ids),
                    f"Requested loop {loop.id!r} is not a closed simple cycle.",
                    "Add the missing consecutive connections or revise the loop order.",
                )
            )


def _validate_branch_requirements(
    topology: DungeonTopology,
    adjacency: Adjacency,
    diagnostics: list[ValidationDiagnostic],
) -> None:
    for branch in topology.branches:
        requested_rooms = {branch.junction_room_id, *branch.branch_room_ids}
        if not requested_rooms.issubset(adjacency):
            continue
        if len(set(branch.branch_room_ids)) != len(branch.branch_room_ids) or any(
            branch_room_id not in adjacency[branch.junction_room_id]
            for branch_room_id in branch.branch_room_ids
        ):
            diagnostics.append(
                _diagnostic(
                    TopologyDiagnosticCode.BRANCH_NOT_REALIZED,
                    (branch.id, branch.junction_room_id, *branch.branch_room_ids),
                    f"Requested branch {branch.id!r} is not realized at its junction.",
                    "Connect each distinct branch room directly to the junction.",
                )
            )


def _validate_chokepoint_requirements(
    topology: DungeonTopology,
    adjacency: Adjacency,
    diagnostics: list[ValidationDiagnostic],
) -> None:
    room_ids = set(adjacency)
    connection_ids = {connection.id for connection in topology.connections}
    for request in topology.chokepoints:
        start, end = request.separates_room_ids
        if start not in room_ids or end not in room_ids:
            continue
        if request.component_kind is ChokepointComponentKind.ROOM:
            if request.component_id not in room_ids:
                continue
            if request.component_id in {start, end}:
                realized = False
            else:
                without_component = _build_adjacency(
                    topology,
                    excluded_room_ids={request.component_id},
                )
                realized = _has_path(adjacency, start, end) and not _has_path(
                    without_component,
                    start,
                    end,
                )
        else:
            if request.component_id not in connection_ids:
                continue
            without_component = _build_adjacency(
                topology,
                excluded_connection_ids={request.component_id},
            )
            realized = _has_path(adjacency, start, end) and not _has_path(
                without_component,
                start,
                end,
            )

        if not realized:
            diagnostics.append(
                _diagnostic(
                    TopologyDiagnosticCode.CHOKEPOINT_NOT_REALIZED,
                    (
                        request.id,
                        request.component_id,
                        *request.separates_room_ids,
                    ),
                    f"Requested chokepoint {request.id!r} does not separate its "
                    "target rooms.",
                    "Remove alternate paths or select a component that disconnects "
                    "the requested regions.",
                )
            )


def _validate_secret_bypasses(
    topology: DungeonTopology,
    diagnostics: list[ValidationDiagnostic],
) -> None:
    connections = {connection.id: connection for connection in topology.connections}
    gates = {gate.id: gate for gate in topology.gates}
    room_ids = {room.id for room in topology.rooms}

    for bypass in topology.secret_bypasses:
        if (
            bypass.entry_room_id not in room_ids
            or bypass.exit_room_id not in room_ids
            or not set(bypass.connection_ids).issubset(connections)
            or not set(bypass.bypassed_gate_ids).issubset(gates)
        ):
            continue

        public_connections = tuple(
            connection_id
            for connection_id in bypass.connection_ids
            if connections[connection_id].visibility is not Visibility.DM_ONLY
        )
        if public_connections:
            diagnostics.append(
                _diagnostic(
                    TopologyDiagnosticCode.SECRET_BYPASS_NOT_SECRET,
                    (bypass.id, *public_connections),
                    f"Secret bypass {bypass.id!r} includes player-safe connections.",
                    "Classify every hidden bypass connection as dm_only.",
                )
            )

        blocked_connections = {
            connection_id
            for gate_id in bypass.bypassed_gate_ids
            for connection_id in gates[gate_id].blocks_connection_ids
        }
        usable_connections = set(bypass.connection_ids) - blocked_connections
        bypass_graph = _build_adjacency(
            topology,
            allowed_connection_ids=usable_connections,
        )
        if not _has_path(
            bypass_graph,
            bypass.entry_room_id,
            bypass.exit_room_id,
        ):
            diagnostics.append(
                _diagnostic(
                    TopologyDiagnosticCode.SECRET_BYPASS_NOT_REALIZED,
                    (
                        bypass.id,
                        bypass.entry_room_id,
                        bypass.exit_room_id,
                        *bypass.connection_ids,
                    ),
                    f"Secret bypass {bypass.id!r} does not form an unblocked route.",
                    "Provide a connected hidden route that avoids the bypassed gates.",
                )
            )


def _validate_gate_reciprocity(
    topology: DungeonTopology,
    diagnostics: list[ValidationDiagnostic],
) -> None:
    keys = {key.id: key for key in topology.keys}
    clues = {clue.id: clue for clue in topology.clues}
    for gate in topology.gates:
        for dependency in gate.requires_all:
            if dependency.kind is GateDependencyKind.KEY:
                key = keys.get(dependency.target_id)
                if key is not None and gate.id not in key.opens_gate_ids:
                    diagnostics.append(
                        _diagnostic(
                            TopologyDiagnosticCode.KEY_GATE_MISMATCH,
                            (gate.id, key.id),
                            f"Gate {gate.id!r} requires key {key.id!r}, but the key "
                            "does not name that gate.",
                            "Make the gate dependency and key opens_gate_ids reciprocal.",
                        )
                    )
            elif dependency.kind is GateDependencyKind.CLUE:
                clue = clues.get(dependency.target_id)
                if clue is not None and gate.id not in clue.supports_gate_ids:
                    diagnostics.append(
                        _diagnostic(
                            TopologyDiagnosticCode.CLUE_GATE_MISMATCH,
                            (gate.id, clue.id),
                            f"Gate {gate.id!r} requires clue {clue.id!r}, but the clue "
                            "does not name that gate.",
                            "Make the gate dependency and clue supports_gate_ids "
                            "reciprocal.",
                        )
                    )


def _validate_gate_dependency_cycles(
    topology: DungeonTopology,
    diagnostics: list[ValidationDiagnostic],
) -> None:
    gate_ids = {gate.id for gate in topology.gates}
    graph = {
        gate.id: {
            dependency.target_id
            for dependency in gate.requires_all
            if dependency.kind is GateDependencyKind.GATE
            and dependency.target_id in gate_ids
        }
        for gate in topology.gates
    }
    for cycle in _strongly_connected_gate_cycles(graph):
        diagnostics.append(
            _diagnostic(
                TopologyDiagnosticCode.GATE_DEPENDENCY_CYCLE,
                cycle,
                f"Gate dependency cycle detected among {', '.join(cycle)}.",
                "Remove or reorder at least one gate-to-gate dependency.",
            )
        )


def _strongly_connected_gate_cycles(
    graph: Mapping[str, set[str]],
) -> tuple[tuple[str, ...], ...]:
    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    low_links: dict[str, int] = {}
    components: list[tuple[str, ...]] = []

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = index
        low_links[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for neighbor in sorted(graph.get(node, set())):
            if neighbor not in indices:
                visit(neighbor)
                low_links[node] = min(low_links[node], low_links[neighbor])
            elif neighbor in on_stack:
                low_links[node] = min(low_links[node], indices[neighbor])

        if low_links[node] != indices[node]:
            return

        component: list[str] = []
        while stack:
            member = stack.pop()
            on_stack.remove(member)
            component.append(member)
            if member == node:
                break
        ordered = tuple(sorted(component))
        if len(ordered) > 1 or (ordered and ordered[0] in graph[ordered[0]]):
            components.append(ordered)

    for node in sorted(graph):
        if node not in indices:
            visit(node)
    return tuple(sorted(components))


def _validate_gate_progression(
    topology: DungeonTopology,
    diagnostics: list[ValidationDiagnostic],
) -> None:
    entrance_ids = {
        room.id for room in topology.rooms if room.role is RoomRole.ENTRANCE
    }
    if not entrance_ids:
        return

    known_key_ids = {key.id for key in topology.keys}
    known_clue_ids = {clue.id for clue in topology.clues}
    known_gate_ids = {gate.id for gate in topology.gates}
    collected_key_ids: set[str] = set()
    collected_clue_ids: set[str] = set()
    opened_gate_ids: set[str] = set()
    reachable_room_ids: set[str] = set()

    while True:
        previous_state = (
            frozenset(collected_key_ids),
            frozenset(collected_clue_ids),
            frozenset(opened_gate_ids),
            frozenset(reachable_room_ids),
        )
        gated_graph = _build_adjacency(
            topology,
            opened_gate_ids=opened_gate_ids,
        )
        reachable_room_ids = _reachable(gated_graph, entrance_ids)
        collected_key_ids.update(
            key.id
            for key in topology.keys
            if key.located_in_room_id in reachable_room_ids
        )
        collected_clue_ids.update(
            clue.id
            for clue in topology.clues
            if clue.located_in_room_id in reachable_room_ids
        )

        for gate in topology.gates:
            if gate.id in opened_gate_ids:
                continue
            if all(
                _dependency_is_satisfied(
                    dependency.kind,
                    dependency.target_id,
                    collected_key_ids,
                    collected_clue_ids,
                    opened_gate_ids,
                    known_key_ids,
                    known_clue_ids,
                    known_gate_ids,
                )
                for dependency in gate.requires_all
            ):
                opened_gate_ids.add(gate.id)

        current_state = (
            frozenset(collected_key_ids),
            frozenset(collected_clue_ids),
            frozenset(opened_gate_ids),
            frozenset(reachable_room_ids),
        )
        if current_state == previous_state:
            break

    for gate in topology.gates:
        if gate.id not in opened_gate_ids:
            dependency_ids = tuple(
                dependency.target_id for dependency in gate.requires_all
            )
            diagnostics.append(
                _diagnostic(
                    TopologyDiagnosticCode.GATE_UNRESOLVABLE,
                    (gate.id, *dependency_ids),
                    f"Gate {gate.id!r} cannot be resolved from reachable keys, "
                    "clues, and prerequisite gates.",
                    "Move a dependency before the gate or remove the dependency cycle.",
                )
            )

    for room in topology.rooms:
        if room.required and room.id not in reachable_room_ids:
            diagnostics.append(
                _diagnostic(
                    TopologyDiagnosticCode.REQUIRED_ROOM_GATE_BLOCKED,
                    (room.id,),
                    f"Required room {room.id!r} remains unreachable after gate "
                    "progression stabilizes.",
                    "Move required keys/clues earlier or provide a solvable bypass.",
                )
            )


def _dependency_is_satisfied(
    kind: GateDependencyKind,
    target_id: str,
    collected_key_ids: set[str],
    collected_clue_ids: set[str],
    opened_gate_ids: set[str],
    known_key_ids: set[str],
    known_clue_ids: set[str],
    known_gate_ids: set[str],
) -> bool:
    if kind is GateDependencyKind.KEY:
        return target_id in known_key_ids and target_id in collected_key_ids
    if kind is GateDependencyKind.CLUE:
        return target_id in known_clue_ids and target_id in collected_clue_ids
    return target_id in known_gate_ids and target_id in opened_gate_ids
