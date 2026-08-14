"""Pure deterministic compiler from compact V2 design intent to kernel contracts."""

from __future__ import annotations

import json
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
from dm_dungeon.contracts.design_v2 import (
    BarrierIntent,
    Concealment,
    DependencyKind,
    DungeonDesignSpecV2,
    HazardIntent,
    PassageType,
    RoomSizeBand,
)
from dm_dungeon.contracts.topology import (
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

DUNGEON_DESIGN_COMPILER_VERSION: Literal["dungeon-design-v2-compiler-1"] = (
    "dungeon-design-v2-compiler-1"
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
    compiler_version: Literal["dungeon-design-v2-compiler-1"]
    input_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    output_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")] | None = None
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
            or self.output_hash is not None
            or self.floor_bounds
        ):
            raise ValueError("rejected compilation cannot contain compiled intent")
        elif not self.diagnostics:
            raise ValueError("rejected compilation requires diagnostics")
        return self


def compile_dungeon_design_v2(spec: DungeonDesignSpecV2) -> DungeonDesignCompileResult:
    """Compile a V2 design without accessing persistence, providers, or randomness."""
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
    rooms = tuple(
        TopologyRoom(
            id=room_ids[room.local_ref],
            floor_id=floor_ids[floor.local_ref],
            name=room.name,
            role=(
                # The V1 kernel requires a reachable exit. V2 final-objective
                # semantics are the compact equivalent, so the compiler—not
                # the model—materializes that mechanical role.
                RoomRole.EXIT if room.local_ref in final_objective_rooms else room.role
            ),
            required=not room.optional,
            size=_size_constraints(room.room_size),
            capacity=_capacity(room.occupancy),
            visibility=Visibility.PLAYER_SAFE,
        )
        for floor in sorted(spec.floors, key=lambda value: value.local_ref)
        for room in sorted(floor.rooms, key=lambda value: value.local_ref)
    )

    dependency_by_connection = {item.connection_ref: item for item in spec.dependencies}
    gates: list[Gate] = []
    keys: list[KeyPlacement] = []
    clues: list[CluePlacement] = []
    connections: list[TopologyConnection] = []
    for connection in sorted(spec.connections, key=lambda value: value.local_ref):
        connection_id = connection_ids[connection.local_ref]
        from_id, to_id = room_ids[connection.from_ref], room_ids[connection.to_ref]
        visibility = (
            Visibility.DM_ONLY
            if connection.concealment is Concealment.SECRET
            or connection.hazard is HazardIntent.TRAPPED
            else Visibility.PLAYER_SAFE
        )
        gate_id: str | None = None
        trap_id: str | None = None
        dependency = dependency_by_connection.get(connection.local_ref)
        if connection.barrier is not BarrierIntent.NONE:
            # _validate_design() rejects a barred connection without its dependency.
            assert dependency is not None
            gate_id = _component_id("gate", connection.local_ref)
            dependency_id = _component_id("dependency", dependency.local_ref)
            gates.append(
                Gate(
                    id=gate_id,
                    name=f"Gate {connection.local_ref}",
                    kind=(
                        GateKind.LOCK
                        if connection.barrier is BarrierIntent.LOCKED
                        else GateKind.PUZZLE
                    ),
                    blocks_connection_ids=(connection_id,),
                    requires_all=(
                        GateDependency(
                            kind=(
                                GateDependencyKind.KEY
                                if dependency.kind is DependencyKind.KEY
                                else GateDependencyKind.CLUE
                            ),
                            target_id=dependency_id,
                        ),
                    ),
                    visibility=Visibility.DM_ONLY,
                )
            )
            if dependency.kind is DependencyKind.KEY:
                keys.append(
                    KeyPlacement(
                        id=dependency_id,
                        name=dependency.name,
                        located_in_room_id=room_ids[dependency.located_in_room_ref],
                        opens_gate_ids=(gate_id,),
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
                        supports_gate_ids=(gate_id,),
                        visibility=Visibility.DM_ONLY,
                    )
                )
        if connection.hazard is HazardIntent.TRAPPED:
            trap_id = _component_id("trap", connection.local_ref)

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
            door_type = (
                DoorType.SECRET
                if connection.concealment is Concealment.SECRET
                else (
                    DoorType.TRAPPED
                    if trap_id
                    else (DoorType.LOCKED if gate_id else DoorType.NORMAL)
                )
            )
            connections.append(
                DoorConnection(
                    kind="door",
                    id=connection_id,
                    from_room_id=from_id,
                    to_room_id=to_id,
                    door_type=door_type,
                    gate_id=gate_id if door_type is DoorType.LOCKED else None,
                    trap_id=trap_id if door_type is DoorType.TRAPPED else None,
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
            "floor_bounds": [item.model_dump(mode="json") for item in floor_bounds],
        }
    )
    return DungeonDesignCompileResult(
        accepted=True,
        compiler_version=DUNGEON_DESIGN_COMPILER_VERSION,
        input_hash=input_hash,
        output_hash=output_hash,
        brief=brief,
        topology=topology,
        floor_bounds=floor_bounds,
        diagnostics=(),
    )


def _validate_design(spec: DungeonDesignSpecV2) -> list[DungeonDesignCompileDiagnostic]:
    diagnostics: list[DungeonDesignCompileDiagnostic] = []
    seen: set[str] = set()
    for floor_index, floor in enumerate(spec.floors):
        if floor.local_ref in seen:
            diagnostics.append(
                _diagnostic(
                    "design.duplicate_local_ref",
                    f"/floors/{floor_index}/local_ref",
                    (floor.local_ref,),
                    "use a unique floor local ref",
                )
            )
        seen.add(floor.local_ref)
        for room_index, room in enumerate(floor.rooms):
            if room.local_ref in seen:
                diagnostics.append(
                    _diagnostic(
                        "design.duplicate_local_ref",
                        f"/floors/{floor_index}/rooms/{room_index}/local_ref",
                        (room.local_ref,),
                        "use a unique room local ref",
                    )
                )
            seen.add(room.local_ref)
    room_refs = {room.local_ref for floor in spec.floors for room in floor.rooms}
    connection_refs: set[str] = set()
    for index, connection in enumerate(spec.connections):
        if connection.local_ref in seen or connection.local_ref in connection_refs:
            diagnostics.append(
                _diagnostic(
                    "design.duplicate_local_ref",
                    f"/connections/{index}/local_ref",
                    (connection.local_ref,),
                    "use a unique connection local ref",
                )
            )
        connection_refs.add(connection.local_ref)
        for field, ref in (
            ("from_ref", connection.from_ref),
            ("to_ref", connection.to_ref),
        ):
            if ref not in room_refs:
                diagnostics.append(
                    _diagnostic(
                        "design.unknown_room_ref",
                        f"/connections/{index}/{field}",
                        (ref,),
                        "reference a declared room local ref",
                    )
                )
        if connection.from_ref == connection.to_ref:
            diagnostics.append(
                _diagnostic(
                    "design.self_connection",
                    f"/connections/{index}",
                    (connection.from_ref,),
                    "connect two distinct rooms",
                )
            )
        same_floor = (
            room_refs
            and connection.from_ref in room_refs
            and connection.to_ref in room_refs
        )
        if (
            same_floor
            and connection.from_ref in room_refs
            and connection.to_ref in room_refs
        ):
            # lookup is intentionally delayed until refs are known
            floor_for = {
                room.local_ref: floor.local_ref
                for floor in spec.floors
                for room in floor.rooms
            }
            crosses_floor = (
                floor_for[connection.from_ref] != floor_for[connection.to_ref]
            )
            if crosses_floor and connection.passage in {
                PassageType.PASSAGE,
                PassageType.DOOR,
            }:
                diagnostics.append(
                    _diagnostic(
                        "design.cross_floor_passage",
                        f"/connections/{index}/passage",
                        (connection.local_ref,),
                        "use stairs or ladder between floors",
                    )
                )
            if not crosses_floor and connection.passage in {
                PassageType.STAIRS,
                PassageType.LADDER,
            }:
                diagnostics.append(
                    _diagnostic(
                        "design.same_floor_vertical",
                        f"/connections/{index}/passage",
                        (connection.local_ref,),
                        "use passage or door on one floor",
                    )
                )
        if connection.passage is not PassageType.DOOR and (
            connection.concealment is Concealment.SECRET
            or connection.hazard is HazardIntent.TRAPPED
            or connection.barrier is not BarrierIntent.NONE
        ):
            diagnostics.append(
                _diagnostic(
                    "design.connection_intent_unsupported",
                    f"/connections/{index}",
                    (connection.local_ref,),
                    "use a door for secret, barrier, or trapped intent",
                )
            )
        if connection.concealment is Concealment.SECRET and (
            connection.hazard is HazardIntent.TRAPPED
            or connection.barrier is not BarrierIntent.NONE
        ):
            diagnostics.append(
                _diagnostic(
                    "design.connection_combination_unsupported",
                    f"/connections/{index}",
                    (connection.local_ref,),
                    "split secret access from trapped or barred access",
                )
            )
        if (
            connection.hazard is HazardIntent.TRAPPED
            and connection.barrier is not BarrierIntent.NONE
        ):
            diagnostics.append(
                _diagnostic(
                    "design.connection_combination_unsupported",
                    f"/connections/{index}",
                    (connection.local_ref,),
                    "split trapped access from barred access",
                )
            )
    entrances = [
        room
        for floor in spec.floors
        for room in floor.rooms
        if room.role.value == "entrance"
    ]
    if len(entrances) != 1:
        diagnostics.append(
            _diagnostic(
                "design.entrance_required",
                "/floors",
                (),
                "declare exactly one room with role entrance",
            )
        )
    final_objectives = [
        item for item in spec.objectives if item.kind.value == "final_objective"
    ]
    if len(final_objectives) != 1:
        diagnostics.append(
            _diagnostic(
                "design.final_objective_required",
                "/objectives",
                (),
                "declare exactly one final_objective",
            )
        )
    for index, objective in enumerate(spec.objectives):
        if objective.room_ref not in room_refs:
            diagnostics.append(
                _diagnostic(
                    "design.unknown_room_ref",
                    f"/objectives/{index}/room_ref",
                    (objective.room_ref,),
                    "reference a declared room local ref",
                )
            )
    seen.update(connection_refs)
    dependency_refs: set[str] = set()
    for index, dependency in enumerate(spec.dependencies):
        if dependency.local_ref in seen or dependency.local_ref in dependency_refs:
            diagnostics.append(
                _diagnostic(
                    "design.duplicate_local_ref",
                    f"/dependencies/{index}/local_ref",
                    (dependency.local_ref,),
                    "use a unique dependency local ref",
                )
            )
        dependency_refs.add(dependency.local_ref)
        if dependency.connection_ref not in connection_refs:
            diagnostics.append(
                _diagnostic(
                    "design.unknown_connection_ref",
                    f"/dependencies/{index}/connection_ref",
                    (dependency.connection_ref,),
                    "reference a declared barred connection",
                )
            )
        if dependency.located_in_room_ref not in room_refs:
            diagnostics.append(
                _diagnostic(
                    "design.unknown_room_ref",
                    f"/dependencies/{index}/located_in_room_ref",
                    (dependency.located_in_room_ref,),
                    "place the dependency in a declared room",
                )
            )
    barred = {
        item.local_ref
        for item in spec.connections
        if item.barrier is not BarrierIntent.NONE
    }
    for ref in sorted(barred - {item.connection_ref for item in spec.dependencies}):
        diagnostics.append(
            _diagnostic(
                "design.missing_dependency",
                "/dependencies",
                (ref,),
                "add one key or clue dependency for each barred connection",
            )
        )
    for ref in sorted({item.connection_ref for item in spec.dependencies} - barred):
        diagnostics.append(
            _diagnostic(
                "design.unneeded_dependency",
                "/dependencies",
                (ref,),
                "dependencies may target only locked or puzzle connections",
            )
        )
    return diagnostics


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
    return f"v2-{kind}-{digest}"


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
