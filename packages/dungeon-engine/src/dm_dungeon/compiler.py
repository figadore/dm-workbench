"""Pure deterministic compiler from compact alpha V1 design intent."""

from __future__ import annotations

import json
from collections.abc import Callable
from hashlib import sha256
from typing import Annotated, Literal

from pydantic import Field, model_validator

from dm_dungeon.contracts.brief import DungeonBrief
from dm_dungeon.contracts.common import (
    ContractModel,
    NonEmptyText,
    OpaqueId,
    Visibility,
)
from dm_dungeon.contracts.design import (
    BarrierIntent,
    ChallengeBand,
    DependencyKind,
    DesignConnection,
    DesignDependency,
    DesignFeature,
    DesignPuzzle,
    DesignRoom,
    DesignTrap,
    DungeonDesignSpec,
    EndpointDoorKind,
    HazardIntent,
    ObjectiveKind,
    PassageType,
    RoomSizeBand,
    VerticalEndpointSide,
)
from dm_dungeon.contracts.mechanics import (
    DUNGEON_MECHANICS_POLICY_VERSION,
    CompiledDoorMechanics,
    CompiledEncounterSlot,
    CompiledRoomFeature,
    CompiledRoomObjective,
    CompiledRoomPuzzle,
    CompiledRoomTrap,
    DungeonMechanicsPlan,
)
from dm_dungeon.contracts.topology import (
    BranchRequirement,
    CluePlacement,
    CorridorConnection,
    DoorConnection,
    DoorType,
    DungeonTopology,
    Gate,
    GateDependency,
    GateDependencyKind,
    GateKind,
    KeyPlacement,
    LoopRequirement,
    RoomCapacity,
    RoomRole,
    RoomSizeConstraints,
    StairConnection,
    TopologyConnection,
    TopologyFloor,
    TopologyRoom,
    VerticalConnection,
    VerticalLinkKind,
)
from dm_dungeon.layout.contracts import FloorLayoutBounds

DUNGEON_DESIGN_COMPILER_VERSION: Literal["dungeon-design-compiler-v1"] = (
    "dungeon-design-compiler-v1"
)


class DungeonDesignCompileDiagnostic(ContractModel):
    """Bounded, body-free repair information for a rejected design."""

    code: Annotated[str, Field(pattern=r"^design\.[a-z0-9_]+$")]
    path: Annotated[str, Field(min_length=1, max_length=256)]
    affected_refs: tuple[OpaqueId, ...] = Field(max_length=8)
    repair: NonEmptyText


class DungeonDesignCompileResult(ContractModel):
    """A complete exact intent or a bounded set of compiler diagnostics."""

    accepted: bool
    compiler_version: Literal["dungeon-design-compiler-v1"]
    input_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    output_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")] | None = None
    mechanics_plan: DungeonMechanicsPlan | None = None
    brief: DungeonBrief | None = None
    topology: DungeonTopology | None = None
    floor_bounds: tuple[FloorLayoutBounds, ...] = ()
    warnings: tuple[DungeonDesignCompileDiagnostic, ...] = ()
    diagnostics: tuple[DungeonDesignCompileDiagnostic, ...] = Field(max_length=8)

    @model_validator(mode="after")
    def require_consistent_result(self) -> DungeonDesignCompileResult:
        if self.accepted:
            if (
                self.brief is None
                or self.topology is None
                or self.mechanics_plan is None
                or self.output_hash is None
                or not self.floor_bounds
            ):
                raise ValueError(
                    "accepted compilation requires brief, topology, and output_hash"
                )
            if self.diagnostics:
                raise ValueError("accepted compilation cannot contain diagnostics")
        elif (
            self.brief is not None
            or self.topology is not None
            or self.mechanics_plan is not None
            or self.output_hash is not None
            or self.floor_bounds
        ):
            raise ValueError("rejected compilation cannot contain compiled intent")
        elif not self.diagnostics:
            raise ValueError("rejected compilation requires diagnostics")
        return self


def compile_dungeon_design(spec: DungeonDesignSpec) -> DungeonDesignCompileResult:
    """Compile a V1 design without accessing persistence, providers, or randomness."""
    input_hash = _hash_contract(spec)
    diagnostics = _validate_design(spec)
    if diagnostics:
        return DungeonDesignCompileResult(
            accepted=False,
            compiler_version=DUNGEON_DESIGN_COMPILER_VERSION,
            input_hash=input_hash,
            diagnostics=tuple(diagnostics[:8]),
        )

    floor_by_ref = {floor.local_ref: floor for floor in spec.floors}
    room_floor_ref = {
        room.local_ref: floor.local_ref for floor in spec.floors for room in floor.rooms
    }
    floor_ids = {ref: _component_id("floor", ref) for ref in floor_by_ref}
    room_ids = {
        ref: _component_id("room", f"{floor_ref}/{ref}")
        for ref, floor_ref in room_floor_ref.items()
    }
    connection_ids = {
        connection.local_ref: _component_id("connection", connection.local_ref)
        for connection in spec.connections
    }

    floors = tuple(
        TopologyFloor(
            id=floor_ids[floor.local_ref],
            name=floor.name,
            level_index=index,
            target_room_count=len(floor.rooms),
            visibility=Visibility.PLAYER_SAFE,
        )
        for index, floor in enumerate(
            sorted(spec.floors, key=lambda value: value.local_ref)
        )
    )
    final_objective_rooms = {
        objective.room_ref
        for objective in spec.objectives
        if objective.kind.value == "final_objective"
    }
    player_visible_room_refs = _player_visible_room_refs(spec)
    rooms = tuple(
        TopologyRoom(
            id=room_ids[room.local_ref],
            floor_id=floor_ids[floor.local_ref],
            name=room.name,
            role=(
                # The kernel requires a reachable exit. Final-objective semantics
                # are the compact equivalent, so the compiler—not
                # the model—materializes that mechanical role.
                RoomRole.EXIT if room.local_ref in final_objective_rooms else room.role
            ),
            required=not room.optional,
            size=_size_constraints(room.room_size),
            capacity=_capacity(room.occupancy),
            tags=room.tags,
            visibility=(
                Visibility.PLAYER_SAFE
                if room.local_ref in player_visible_room_refs
                else Visibility.DM_ONLY
            ),
        )
        for floor in sorted(spec.floors, key=lambda value: value.local_ref)
        for room in sorted(floor.rooms, key=lambda value: value.local_ref)
    )

    dependency_by_target = {item.target_ref: item for item in spec.dependencies}
    mechanics_plan = _compile_mechanics_plan(
        spec,
        room_ids=room_ids,
        connection_ids=connection_ids,
    )
    same_floor_mechanics = {
        item.connection_id: item
        for item in mechanics_plan.door_mechanics
        if item.endpoint is None
    }
    gates: list[Gate] = []
    keys: list[KeyPlacement] = []
    clues: list[CluePlacement] = []
    mechanics_by_target_ref: dict[str, CompiledDoorMechanics] = {}
    for connection in sorted(spec.connections, key=lambda value: value.local_ref):
        if connection.passage is PassageType.DOOR:
            mechanics = same_floor_mechanics.get(connection_ids[connection.local_ref])
            if mechanics is not None:
                mechanics_by_target_ref[connection.local_ref] = mechanics
        else:
            for endpoint_door in connection.endpoint_doors:
                mechanics = next(
                    (
                        item
                        for item in mechanics_plan.door_mechanics
                        if item.connection_id == connection_ids[connection.local_ref]
                        and item.endpoint == endpoint_door.endpoint
                    ),
                    None,
                )
                if mechanics is not None:
                    mechanics_by_target_ref[endpoint_door.local_ref] = mechanics
    for target_ref, mechanics in sorted(mechanics_by_target_ref.items()):
        if mechanics.gate_id is None:
            continue
        dependency = dependency_by_target.get(target_ref)
        dependency_id = (
            None
            if dependency is None
            else _component_id("dependency", dependency.local_ref)
        )
        gates.append(
            Gate(
                id=mechanics.gate_id,
                name=f"Gate {target_ref}",
                kind=(
                    GateKind.LOCK
                    if mechanics.gate_kind is BarrierIntent.LOCKED
                    else GateKind.PUZZLE
                ),
                blocks_connection_ids=(mechanics.connection_id,),
                requires_all=(
                    ()
                    if dependency is None or dependency_id is None
                    else (
                        GateDependency(
                            kind=(
                                GateDependencyKind.KEY
                                if dependency.kind is DependencyKind.KEY
                                else GateDependencyKind.CLUE
                            ),
                            target_id=dependency_id,
                        ),
                    )
                ),
                visibility=Visibility.DM_ONLY,
            )
        )
        if dependency is not None and dependency_id is not None:
            if dependency.kind is DependencyKind.KEY:
                keys.append(
                    KeyPlacement(
                        id=dependency_id,
                        name=dependency.name,
                        located_in_room_id=room_ids[dependency.located_in_room_ref],
                        opens_gate_ids=(mechanics.gate_id,),
                        visibility=Visibility.DM_ONLY,
                    )
                )
            else:
                clues.append(
                    CluePlacement(
                        id=dependency_id,
                        name=dependency.name,
                        text=dependency.name,
                        located_in_room_id=room_ids[dependency.located_in_room_ref],
                        supports_gate_ids=(mechanics.gate_id,),
                        visibility=Visibility.DM_ONLY,
                    )
                )
    connections: list[TopologyConnection] = []
    for connection in sorted(spec.connections, key=lambda value: value.local_ref):
        connection_id = connection_ids[connection.local_ref]
        from_id, to_id = room_ids[connection.from_ref], room_ids[connection.to_ref]
        mechanics = same_floor_mechanics.get(connection_id)
        visibility = (
            Visibility.DM_ONLY
            if _hidden_at_either_end(connection)
            or (mechanics is not None and mechanics.trap_id is not None)
            or connection.from_ref not in player_visible_room_refs
            or connection.to_ref not in player_visible_room_refs
            else Visibility.PLAYER_SAFE
        )
        gate_id = None if mechanics is None else mechanics.gate_id
        trap_id = None if mechanics is None else mechanics.trap_id
        if connection.passage is PassageType.PASSAGE:
            connections.append(
                CorridorConnection(
                    kind="corridor",
                    id=connection_id,
                    from_room_id=from_id,
                    to_room_id=to_id,
                    visibility=visibility,
                )
            )
        elif connection.passage is PassageType.DOOR:
            # Topology retains a coarse exclusive door type for graph validation;
            # the mechanics plan carries independent exact door mechanics.
            door_type = (
                DoorType.SECRET
                if _hidden_at_either_end(connection)
                else (
                    DoorType.LOCKED
                    if gate_id is not None
                    else (DoorType.TRAPPED if trap_id is not None else DoorType.NORMAL)
                )
            )
            connections.append(
                DoorConnection(
                    kind="door",
                    id=connection_id,
                    from_room_id=from_id,
                    to_room_id=to_id,
                    door_type=door_type,
                    gate_id=gate_id,
                    trap_id=trap_id,
                    from_hidden=_hidden_from(connection),
                    to_hidden=_hidden_to(connection),
                    visibility=visibility,
                )
            )
        elif connection.passage is PassageType.STAIRS:
            connections.append(
                StairConnection(
                    kind="stairs",
                    id=connection_id,
                    from_room_id=from_id,
                    to_room_id=to_id,
                    from_floor_id=floor_ids[room_floor_ref[connection.from_ref]],
                    to_floor_id=floor_ids[room_floor_ref[connection.to_ref]],
                    from_hidden=_hidden_from(connection),
                    to_hidden=_hidden_to(connection),
                    visibility=visibility,
                )
            )
        else:
            connections.append(
                VerticalConnection(
                    kind="vertical_link",
                    id=connection_id,
                    from_room_id=from_id,
                    to_room_id=to_id,
                    from_floor_id=floor_ids[room_floor_ref[connection.from_ref]],
                    to_floor_id=floor_ids[room_floor_ref[connection.to_ref]],
                    link_type=VerticalLinkKind.LADDER,
                    from_hidden=_hidden_from(connection),
                    to_hidden=_hidden_to(connection),
                    visibility=visibility,
                )
            )

    floor_bounds = tuple(
        FloorLayoutBounds(
            floor_id=floor_ids[floor.local_ref],
            width_cells=_floor_extent(floor.floor_scale),
            height_cells=_floor_extent(floor.floor_scale),
        )
        for floor in sorted(spec.floors, key=lambda value: value.local_ref)
    )
    topology = DungeonTopology(
        schema_version="1.0.0",
        id=_component_id("topology", "root"),
        visibility=Visibility.PLAYER_SAFE,
        floors=floors,
        rooms=rooms,
        connections=tuple(connections),
        gates=tuple(gates),
        keys=tuple(keys),
        clues=tuple(clues),
        loops=tuple(
            LoopRequirement(
                id=_component_id("loop", requirement.local_ref),
                room_ids=tuple(room_ids[ref] for ref in requirement.room_refs),
                visibility=Visibility.PLAYER_SAFE,
            )
            for requirement in sorted(spec.loops, key=lambda value: value.local_ref)
        ),
        branches=tuple(
            BranchRequirement(
                id=_component_id("branch", requirement.local_ref),
                junction_room_id=room_ids[requirement.junction_room_ref],
                branch_room_ids=tuple(
                    room_ids[ref] for ref in requirement.branch_room_refs
                ),
                visibility=Visibility.PLAYER_SAFE,
            )
            for requirement in sorted(spec.branches, key=lambda value: value.local_ref)
        ),
    )
    brief = DungeonBrief(
        schema_version="1.0.0",
        id=_component_id("brief", "root"),
        title=spec.title,
        purpose=spec.purpose,
        summary=spec.premise,
        visibility=Visibility.PLAYER_SAFE,
        themes=spec.themes,
        pacing=spec.pacing,
        floor_count=len(floors),
        target_room_count=len(rooms),
    )
    output_hash = _hash_json(
        {
            "brief": brief.model_dump(mode="json"),
            "topology": topology.model_dump(mode="json"),
            "mechanics_plan": mechanics_plan.model_dump(mode="json"),
            "floor_bounds": [item.model_dump(mode="json") for item in floor_bounds],
        }
    )
    return DungeonDesignCompileResult(
        accepted=True,
        compiler_version=DUNGEON_DESIGN_COMPILER_VERSION,
        input_hash=input_hash,
        output_hash=output_hash,
        mechanics_plan=mechanics_plan,
        brief=brief,
        topology=topology,
        floor_bounds=floor_bounds,
        diagnostics=(),
    )


def _compile_mechanics_plan(
    spec: DungeonDesignSpec,
    *,
    room_ids: dict[str, str],
    connection_ids: dict[str, str],
) -> DungeonMechanicsPlan:
    mechanics: list[CompiledDoorMechanics] = []
    for connection in sorted(spec.connections, key=lambda value: value.local_ref):
        if connection.passage is PassageType.DOOR:
            mechanics.append(
                _compile_door_mechanics(
                    identity=connection.local_ref,
                    connection_id=connection_ids[connection.local_ref],
                    endpoint=None,
                    concealed=_hidden_at_either_end(connection),
                    barrier=connection.door_mechanics.barrier,
                    hazard=connection.door_mechanics.hazard,
                    challenge=connection.door_mechanics.challenge,
                )
            )
        elif connection.passage in {PassageType.STAIRS, PassageType.LADDER}:
            for endpoint_door in sorted(
                connection.endpoint_doors, key=lambda value: value.endpoint.value
            ):
                mechanics.append(
                    _compile_door_mechanics(
                        identity=endpoint_door.local_ref,
                        connection_id=connection_ids[connection.local_ref],
                        endpoint=endpoint_door.endpoint,
                        endpoint_kind=endpoint_door.kind,
                        concealed=(
                            connection.from_hidden
                            if endpoint_door.endpoint is VerticalEndpointSide.FROM
                            else connection.to_hidden
                        ),
                        barrier=endpoint_door.mechanics.barrier,
                        hazard=endpoint_door.mechanics.hazard,
                        challenge=endpoint_door.mechanics.challenge,
                    )
                )
    return DungeonMechanicsPlan(
        policy_version=DUNGEON_MECHANICS_POLICY_VERSION,
        connection_ids=tuple(sorted(connection_ids.values())),
        room_ids=tuple(sorted(room_ids.values())),
        door_mechanics=tuple(mechanics),
        room_traps=tuple(
            CompiledRoomTrap(
                id=_component_id("trap", trap.local_ref),
                room_id=room_ids[trap.room_ref],
                detection_difficulty=_difficulty(trap.challenge),
                disable_difficulty=_difficulty(trap.challenge),
            )
            for trap in sorted(spec.traps, key=lambda value: value.local_ref)
        ),
        room_puzzles=tuple(
            CompiledRoomPuzzle(
                id=_component_id("puzzle", puzzle.local_ref),
                room_id=room_ids[puzzle.room_ref],
                difficulty=_difficulty(puzzle.challenge),
            )
            for puzzle in sorted(spec.puzzles, key=lambda value: value.local_ref)
        ),
        room_features=tuple(
            CompiledRoomFeature(
                id=_component_id("feature", feature.local_ref),
                room_id=room_ids[feature.room_ref],
                kind=feature.kind,
            )
            for feature in sorted(spec.features, key=lambda value: value.local_ref)
        ),
        room_objectives=tuple(
            CompiledRoomObjective(
                id=_component_id(
                    "objective", f"{objective.kind.value}:{objective.room_ref}"
                ),
                room_id=room_ids[objective.room_ref],
                kind=objective.kind,
                name=objective.name,
            )
            for objective in sorted(
                spec.objectives,
                key=lambda value: (value.kind.value, value.room_ref),
            )
        ),
        encounter_slots=tuple(
            CompiledEncounterSlot(
                id=_component_id("encounter-slot", room.local_ref),
                room_id=room_ids[room.local_ref],
                intent=room.encounter_slot,
            )
            for floor in sorted(spec.floors, key=lambda value: value.local_ref)
            for room in sorted(floor.rooms, key=lambda value: value.local_ref)
            if room.encounter_slot is not None
        ),
    )


def _compile_door_mechanics(
    *,
    identity: str,
    connection_id: str,
    endpoint: VerticalEndpointSide | None,
    endpoint_kind: EndpointDoorKind | None = None,
    concealed: bool,
    barrier: BarrierIntent,
    hazard: HazardIntent,
    challenge: ChallengeBand | None,
) -> CompiledDoorMechanics:
    # A missing key/clue is a preparation-readiness blocker, not a reason to lose
    # an otherwise connected draft.  The gate remains exact; an empty dependency
    # list is projected into the DM guide/readiness report.
    active = (
        concealed or barrier is not BarrierIntent.NONE or hazard is HazardIntent.TRAPPED
    )
    difficulty = _difficulty(challenge or ChallengeBand.MODERATE) if active else None
    return CompiledDoorMechanics(
        id=_component_id("door-mechanics", identity),
        connection_id=connection_id,
        endpoint=endpoint,
        endpoint_kind=endpoint_kind,
        concealed=concealed,
        gate_id=(
            None if barrier is BarrierIntent.NONE else _component_id("gate", identity)
        ),
        gate_kind=barrier,
        trap_id=(
            None if hazard is HazardIntent.NONE else _component_id("trap", identity)
        ),
        discovery_difficulty=difficulty if concealed else None,
        unlock_difficulty=difficulty if barrier is not BarrierIntent.NONE else None,
        disable_difficulty=difficulty if hazard is HazardIntent.TRAPPED else None,
    )


def _difficulty(band: ChallengeBand) -> int:
    return {ChallengeBand.LOW: 10, ChallengeBand.MODERATE: 13, ChallengeBand.HIGH: 16}[
        band
    ]


def _hidden_from(connection: DesignConnection) -> bool:
    return connection.from_hidden


def _hidden_to(connection: DesignConnection) -> bool:
    return connection.to_hidden


def _hidden_at_either_end(connection: DesignConnection) -> bool:
    return _hidden_from(connection) or _hidden_to(connection)


def _player_visible_room_refs(spec: DungeonDesignSpec) -> set[str]:
    """Return rooms discoverable without traversing a secret connection.

    Traps and barriers stay DM-only mechanics, but do not hide the room geometry
    beyond them. A room reachable only through secret access remains absent from
    clean player output until a later explicit reveal workflow publishes it.
    """
    entrance = next(
        room.local_ref
        for floor in spec.floors
        for room in floor.rooms
        if room.role is RoomRole.ENTRANCE
    )
    neighbors: dict[str, set[str]] = {
        room.local_ref: set() for floor in spec.floors for room in floor.rooms
    }
    for connection in spec.connections:
        if not _hidden_from(connection):
            neighbors[connection.from_ref].add(connection.to_ref)
        if not _hidden_to(connection):
            neighbors[connection.to_ref].add(connection.from_ref)
    visible = {entrance}
    pending = [entrance]
    while pending:
        current = pending.pop()
        for neighbor in sorted(neighbors[current] - visible):
            visible.add(neighbor)
            pending.append(neighbor)
    return visible


def _validate_design(spec: DungeonDesignSpec) -> list[DungeonDesignCompileDiagnostic]:
    """Validate local relation refs before deriving opaque component IDs."""
    diagnostics: list[DungeonDesignCompileDiagnostic] = []
    refs: dict[str, str] = {}

    def add_ref(ref: str, path: str) -> None:
        if ref in refs:
            diagnostics.append(
                _diagnostic(
                    "design.duplicate_local_ref",
                    path,
                    (ref,),
                    "use a unique local ref",
                )
            )
        refs[ref] = path

    room_floor: dict[str, str] = {}
    rooms: dict[str, DesignRoom] = {}
    for floor_index, floor in enumerate(spec.floors):
        add_ref(floor.local_ref, f"/floors/{floor_index}/local_ref")
        for room_index, room in enumerate(floor.rooms):
            add_ref(
                room.local_ref, f"/floors/{floor_index}/rooms/{room_index}/local_ref"
            )
            room_floor[room.local_ref] = floor.local_ref
            rooms[room.local_ref] = room

    for index, connection in enumerate(spec.connections):
        add_ref(connection.local_ref, f"/connections/{index}/local_ref")
        for field, ref in (
            ("from_ref", connection.from_ref),
            ("to_ref", connection.to_ref),
        ):
            if ref not in rooms:
                diagnostics.append(
                    _diagnostic(
                        "design.unknown_room_ref",
                        f"/connections/{index}/{field}",
                        (ref,),
                        "reference a declared room",
                    )
                )
        if connection.from_ref == connection.to_ref:
            diagnostics.append(
                _diagnostic(
                    "design.self_connection",
                    f"/connections/{index}",
                    (connection.from_ref,),
                    "connect distinct rooms",
                )
            )
        elif connection.from_ref in room_floor and connection.to_ref in room_floor:
            crosses_floor = (
                room_floor[connection.from_ref] != room_floor[connection.to_ref]
            )
            if crosses_floor != (
                connection.passage in {PassageType.STAIRS, PassageType.LADDER}
            ):
                diagnostics.append(
                    _diagnostic(
                        "design.connection_floor_mismatch",
                        f"/connections/{index}/passage",
                        (connection.local_ref,),
                        "use doors/passages on one floor and stairs/ladders across floors",
                    )
                )
        for endpoint_index, endpoint_door in enumerate(connection.endpoint_doors):
            add_ref(
                endpoint_door.local_ref,
                f"/connections/{index}/endpoint_doors/{endpoint_index}/local_ref",
            )

    target_barriers: set[str] = set()
    for connection in spec.connections:
        if (
            connection.passage is PassageType.DOOR
            and connection.door_mechanics.barrier is not BarrierIntent.NONE
        ):
            target_barriers.add(connection.local_ref)
        for endpoint_door in connection.endpoint_doors:
            if endpoint_door.mechanics.barrier is not BarrierIntent.NONE:
                target_barriers.add(endpoint_door.local_ref)

    dependency_targets: list[str] = []
    dependencies_by_ref: dict[str, DesignDependency] = {}
    for index, dependency in enumerate(spec.dependencies):
        add_ref(dependency.local_ref, f"/dependencies/{index}/local_ref")
        dependencies_by_ref[dependency.local_ref] = dependency
        dependency_targets.append(dependency.target_ref)
        if dependency.target_ref not in target_barriers:
            diagnostics.append(
                _diagnostic(
                    "design.unneeded_dependency",
                    f"/dependencies/{index}/target_ref",
                    (dependency.target_ref,),
                    "target one locked or puzzle door/hatch",
                )
            )
        if dependency.located_in_room_ref not in rooms:
            diagnostics.append(
                _diagnostic(
                    "design.unknown_room_ref",
                    f"/dependencies/{index}/located_in_room_ref",
                    (dependency.located_in_room_ref,),
                    "place the dependency in a declared room",
                )
            )
    for target in sorted(
        {item for item in dependency_targets if dependency_targets.count(item) > 1}
    ):
        diagnostics.append(
            _diagnostic(
                "design.duplicate_dependency_target",
                "/dependencies",
                (target,),
                "provide exactly one dependency per barrier",
            )
        )

    entrances = [room for room in rooms.values() if room.role is RoomRole.ENTRANCE]
    if len(entrances) != 1:
        diagnostics.append(
            _diagnostic(
                "design.entrance_required",
                "/floors",
                (),
                "declare exactly one entrance room",
            )
        )
    final_objectives = [
        item for item in spec.objectives if item.kind is ObjectiveKind.FINAL_OBJECTIVE
    ]
    if len(final_objectives) != 1:
        diagnostics.append(
            _diagnostic(
                "design.final_objective_required",
                "/objectives",
                (),
                "declare exactly one final objective",
            )
        )
    objective_keys: set[tuple[ObjectiveKind, str]] = set()
    for index, objective in enumerate(spec.objectives):
        if objective.room_ref not in rooms:
            diagnostics.append(
                _diagnostic(
                    "design.unknown_room_ref",
                    f"/objectives/{index}/room_ref",
                    (objective.room_ref,),
                    "reference a declared room",
                )
            )
        objective_key = (objective.kind, objective.room_ref)
        if objective_key in objective_keys:
            diagnostics.append(
                _diagnostic(
                    "design.duplicate_objective",
                    f"/objectives/{index}",
                    (objective.room_ref,),
                    "declare each objective kind at most once per room",
                )
            )
        objective_keys.add(objective_key)

    _validate_room_local_refs("traps", spec.traps, rooms, add_ref, diagnostics)
    _validate_room_local_refs("puzzles", spec.puzzles, rooms, add_ref, diagnostics)
    _validate_room_local_refs("features", spec.features, rooms, add_ref, diagnostics)
    for index, puzzle in enumerate(spec.puzzles):
        for clue_index, clue_ref in enumerate(puzzle.clue_refs):
            puzzle_dependency = dependencies_by_ref.get(clue_ref)
            if puzzle_dependency is None:
                diagnostics.append(
                    _diagnostic(
                        "design.unknown_clue_ref",
                        f"/puzzles/{index}/clue_refs/{clue_index}",
                        (clue_ref,),
                        "reference a declared clue local ref",
                    )
                )
            elif puzzle_dependency.kind is not DependencyKind.CLUE:
                diagnostics.append(
                    _diagnostic(
                        "design.clue_ref_not_clue",
                        f"/puzzles/{index}/clue_refs/{clue_index}",
                        (clue_ref,),
                        "reference a dependency whose kind is clue",
                    )
                )

    for index, requirement in enumerate(spec.loops):
        add_ref(requirement.local_ref, f"/loops/{index}/local_ref")
        for room_index, room_ref in enumerate(requirement.room_refs):
            if room_ref not in rooms:
                diagnostics.append(
                    _diagnostic(
                        "design.unknown_room_ref",
                        f"/loops/{index}/room_refs/{room_index}",
                        (room_ref,),
                        "reference a declared room",
                    )
                )
    for index, branch_requirement in enumerate(spec.branches):
        add_ref(branch_requirement.local_ref, f"/branches/{index}/local_ref")
        for field, room_refs in (
            ("junction_room_ref", (branch_requirement.junction_room_ref,)),
            ("branch_room_refs", branch_requirement.branch_room_refs),
        ):
            for room_index, room_ref in enumerate(room_refs):
                path = f"/branches/{index}/{field}"
                if field == "branch_room_refs":
                    path = f"{path}/{room_index}"
                if room_ref not in rooms:
                    diagnostics.append(
                        _diagnostic(
                            "design.unknown_room_ref",
                            path,
                            (room_ref,),
                            "reference a declared room",
                        )
                    )
    return diagnostics


def _validate_room_local_refs(
    collection_name: str,
    values: tuple[DesignTrap | DesignPuzzle | DesignFeature, ...],
    rooms: dict[str, DesignRoom],
    add_ref: Callable[[str, str], None],
    diagnostics: list[DungeonDesignCompileDiagnostic],
) -> None:
    """Validate room-local components while keeping duplicate paths stable."""
    for index, item in enumerate(values):
        add_ref(item.local_ref, f"/{collection_name}/{index}/local_ref")
        if item.room_ref not in rooms:
            diagnostics.append(
                _diagnostic(
                    "design.unknown_room_ref",
                    f"/{collection_name}/{index}/room_ref",
                    (item.room_ref,),
                    "reference a declared room",
                )
            )


def _diagnostic(
    code: str, path: str, refs: tuple[str, ...], repair: str
) -> DungeonDesignCompileDiagnostic:
    return DungeonDesignCompileDiagnostic(
        code=code, path=path, affected_refs=tuple(sorted(refs)), repair=repair
    )


def _component_id(kind: str, identity: str) -> str:
    digest = sha256(
        f"{DUNGEON_DESIGN_COMPILER_VERSION}:{kind}:{identity}".encode()
    ).hexdigest()[:20]
    return f"v1-{kind}-{digest}"


def _floor_extent(band: object) -> int:
    """Pinned relative-scale mapping for the orthogonal layout kernel."""
    return {"small": 28, "medium": 40, "large": 56}[str(band)]


def _size_constraints(band: RoomSizeBand) -> RoomSizeConstraints:
    return {
        RoomSizeBand.SMALL: RoomSizeConstraints(
            minimum_width_cells=3,
            maximum_width_cells=5,
            minimum_height_cells=3,
            maximum_height_cells=5,
            minimum_area_cells=9,
            maximum_area_cells=25,
        ),
        RoomSizeBand.MEDIUM: RoomSizeConstraints(
            minimum_width_cells=5,
            maximum_width_cells=8,
            minimum_height_cells=5,
            maximum_height_cells=8,
            minimum_area_cells=25,
            maximum_area_cells=64,
        ),
        RoomSizeBand.LARGE: RoomSizeConstraints(
            minimum_width_cells=8,
            maximum_width_cells=12,
            minimum_height_cells=8,
            maximum_height_cells=12,
            minimum_area_cells=64,
            maximum_area_cells=144,
        ),
    }[band]


def _capacity(band: object) -> RoomCapacity:
    values = {"solo": (1, 2, 3), "group": (3, 5, 8), "crowd": (6, 10, 16)}[str(band)]
    return RoomCapacity(
        minimum_occupants=values[0],
        comfortable_occupants=values[1],
        maximum_occupants=values[2],
    )


def _hash_contract(contract: ContractModel) -> str:
    return _hash_json(contract.model_dump(mode="json", round_trip=True))


def _hash_json(payload: object) -> str:
    encoded = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return sha256(encoded).hexdigest()
