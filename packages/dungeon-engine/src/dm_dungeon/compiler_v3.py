"""Pure P7-13d mechanics-plan compiler for ``DungeonDesignSpecV3``.

This is intentionally a separate compiler/profile from V2.  It proves the
creative connection matrix and assigns stable IDs before a later V3 layout compiler
chooses anchors or emits a package.  In particular, a concealed physical barrier is
compiled once with *both* its gate and trap IDs; no exclusive door enum can discard
one requested mechanic.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from hashlib import sha256
from typing import Annotated, Literal

from pydantic import Field, model_validator

from dm_dungeon.contracts.common import ContractModel, NonEmptyText, OpaqueId
from dm_dungeon.contracts.design_v2 import (
    BarrierIntent,
    HazardIntent,
    ObjectiveKind,
    PassageType,
)
from dm_dungeon.contracts.design_v3 import (
    ChallengeBand,
    DesignFeatureV3,
    DesignPuzzleV3,
    DesignRoomV3,
    DesignTrapV3,
    DungeonDesignSpecV3,
    VerticalEndpointSide,
)
from dm_dungeon.contracts.topology import RoomRole

DUNGEON_DESIGN_V3_COMPILER_VERSION: Literal["dungeon-design-v3-compiler-1"] = (
    "dungeon-design-v3-compiler-1"
)
DUNGEON_MECHANICS_POLICY_VERSION: Literal["dungeon-mechanics-policy-1"] = (
    "dungeon-mechanics-policy-1"
)


class DungeonDesignV3CompileDiagnostic(ContractModel):
    code: Annotated[str, Field(pattern=r"^design_v3\.[a-z0-9_]+$")]
    path: Annotated[str, Field(min_length=1, max_length=256)]
    affected_refs: tuple[OpaqueId, ...] = Field(max_length=8)
    repair: NonEmptyText


class CompiledDoorMechanicsV3(ContractModel):
    """Exact non-geometric mechanics attached to one physical barrier."""

    id: OpaqueId
    connection_id: OpaqueId
    endpoint: VerticalEndpointSide | None = None
    concealed: bool
    gate_id: OpaqueId | None = None
    gate_kind: BarrierIntent = BarrierIntent.NONE
    trap_id: OpaqueId | None = None
    discovery_difficulty: int | None = Field(default=None, ge=0)
    unlock_difficulty: int | None = Field(default=None, ge=0)
    disable_difficulty: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def require_difficulties_for_mechanics(self) -> CompiledDoorMechanicsV3:
        if self.concealed and self.discovery_difficulty is None:
            raise ValueError("concealed mechanics require discovery_difficulty")
        if (self.gate_id is None) != (self.gate_kind is BarrierIntent.NONE):
            raise ValueError("gate_id and gate_kind must be present together")
        if self.gate_id is not None and self.unlock_difficulty is None:
            raise ValueError("gates require unlock_difficulty")
        if self.trap_id is not None and self.disable_difficulty is None:
            raise ValueError("traps require disable_difficulty")
        return self


class CompiledRoomTrapV3(ContractModel):
    id: OpaqueId
    room_id: OpaqueId
    detection_difficulty: int = Field(ge=0)
    disable_difficulty: int = Field(ge=0)


class DungeonMechanicsPlanV3(ContractModel):
    """Stable IDs/policy output that later geometry and DM-guide code consume."""

    policy_version: Literal["dungeon-mechanics-policy-1"]
    connection_ids: tuple[OpaqueId, ...]
    room_ids: tuple[OpaqueId, ...]
    door_mechanics: tuple[CompiledDoorMechanicsV3, ...]
    room_traps: tuple[CompiledRoomTrapV3, ...]


class DungeonDesignV3CompileResult(ContractModel):
    accepted: bool
    compiler_version: Literal["dungeon-design-v3-compiler-1"]
    input_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    output_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")] | None = None
    mechanics_plan: DungeonMechanicsPlanV3 | None = None
    diagnostics: tuple[DungeonDesignV3CompileDiagnostic, ...] = Field(max_length=8)

    @model_validator(mode="after")
    def require_consistent_result(self) -> DungeonDesignV3CompileResult:
        if self.accepted:
            if (
                self.output_hash is None
                or self.mechanics_plan is None
                or self.diagnostics
            ):
                raise ValueError(
                    "accepted compilation requires an output and no diagnostics"
                )
        elif (
            self.output_hash is not None
            or self.mechanics_plan is not None
            or not self.diagnostics
        ):
            raise ValueError("rejected compilation requires diagnostics only")
        return self


def compile_dungeon_design_v3(
    spec: DungeonDesignSpecV3,
) -> DungeonDesignV3CompileResult:
    """Validate all V3 refs and compile every independent requested mechanic."""
    input_hash = _hash_json(spec.model_dump(mode="json", round_trip=True))
    diagnostics = _validate_design(spec)
    if diagnostics:
        return DungeonDesignV3CompileResult(
            accepted=False,
            compiler_version=DUNGEON_DESIGN_V3_COMPILER_VERSION,
            input_hash=input_hash,
            diagnostics=tuple(diagnostics[:8]),
        )

    room_floor = {
        room.local_ref: floor.local_ref for floor in spec.floors for room in floor.rooms
    }
    room_ids = {
        ref: _component_id("room", f"{floor_ref}/{ref}")
        for ref, floor_ref in room_floor.items()
    }
    connection_ids = {
        connection.local_ref: _component_id("connection", connection.local_ref)
        for connection in spec.connections
    }
    dependencies = {
        dependency.target_ref: dependency for dependency in spec.dependencies
    }
    mechanics: list[CompiledDoorMechanicsV3] = []
    for connection in sorted(spec.connections, key=lambda value: value.local_ref):
        if connection.passage is PassageType.DOOR:
            mechanics.append(
                _compile_mechanics(
                    identity=connection.local_ref,
                    connection_id=connection_ids[connection.local_ref],
                    endpoint=None,
                    concealed=connection.from_hidden
                    or connection.to_hidden
                    or connection.door_mechanics.concealed,
                    barrier=connection.door_mechanics.barrier,
                    hazard=connection.door_mechanics.hazard,
                    challenge=connection.door_mechanics.challenge,
                    dependency=dependencies.get(connection.local_ref),
                )
            )
        elif connection.passage in {PassageType.STAIRS, PassageType.LADDER}:
            for endpoint_door in sorted(
                connection.endpoint_doors, key=lambda value: value.endpoint.value
            ):
                identity = endpoint_door.local_ref
                mechanics.append(
                    _compile_mechanics(
                        identity=identity,
                        connection_id=connection_ids[connection.local_ref],
                        endpoint=endpoint_door.endpoint,
                        concealed=endpoint_door.mechanics.concealed,
                        barrier=endpoint_door.mechanics.barrier,
                        hazard=endpoint_door.mechanics.hazard,
                        challenge=endpoint_door.mechanics.challenge,
                        dependency=dependencies.get(identity),
                    )
                )

    room_traps = tuple(
        CompiledRoomTrapV3(
            id=_component_id("trap", trap.local_ref),
            room_id=room_ids[trap.room_ref],
            detection_difficulty=_difficulty(trap.challenge),
            disable_difficulty=_difficulty(trap.challenge),
        )
        for trap in sorted(spec.traps, key=lambda value: value.local_ref)
    )
    plan = DungeonMechanicsPlanV3(
        policy_version=DUNGEON_MECHANICS_POLICY_VERSION,
        connection_ids=tuple(sorted(connection_ids.values())),
        room_ids=tuple(sorted(room_ids.values())),
        door_mechanics=tuple(mechanics),
        room_traps=room_traps,
    )
    return DungeonDesignV3CompileResult(
        accepted=True,
        compiler_version=DUNGEON_DESIGN_V3_COMPILER_VERSION,
        input_hash=input_hash,
        output_hash=_hash_json(plan.model_dump(mode="json", round_trip=True)),
        mechanics_plan=plan,
        diagnostics=(),
    )


def _compile_mechanics(
    *,
    identity: str,
    connection_id: str,
    endpoint: VerticalEndpointSide | None,
    concealed: bool,
    barrier: BarrierIntent,
    hazard: HazardIntent,
    challenge: ChallengeBand | None,
    dependency: object | None,
) -> CompiledDoorMechanicsV3:
    # Validation guarantees an active barrier has a matching dependency/challenge.
    difficulty = None if challenge is None else _difficulty(challenge)
    return CompiledDoorMechanicsV3(
        id=_component_id("door-mechanics", identity),
        connection_id=connection_id,
        endpoint=endpoint,
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


def _validate_design(
    spec: DungeonDesignSpecV3,
) -> list[DungeonDesignV3CompileDiagnostic]:
    diagnostics: list[DungeonDesignV3CompileDiagnostic] = []
    refs: dict[str, str] = {}

    def add_ref(ref: str, path: str) -> None:
        previous = refs.get(ref)
        if previous is not None:
            diagnostics.append(
                _diagnostic(
                    "design_v3.duplicate_local_ref",
                    path,
                    (ref,),
                    "use a unique local ref",
                )
            )
        refs[ref] = path

    room_floor: dict[str, str] = {}
    rooms: dict[str, DesignRoomV3] = {}
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
                        "design_v3.unknown_room_ref",
                        f"/connections/{index}/{field}",
                        (ref,),
                        "reference a declared room",
                    )
                )
        if connection.from_ref == connection.to_ref:
            diagnostics.append(
                _diagnostic(
                    "design_v3.self_connection",
                    f"/connections/{index}",
                    (connection.from_ref,),
                    "connect distinct rooms",
                )
            )
            continue
        if connection.from_ref not in room_floor or connection.to_ref not in room_floor:
            continue
        crosses_floor = room_floor[connection.from_ref] != room_floor[connection.to_ref]
        if crosses_floor != (
            connection.passage in {PassageType.STAIRS, PassageType.LADDER}
        ):
            diagnostics.append(
                _diagnostic(
                    "design_v3.connection_floor_mismatch",
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
    dependency_targets: set[str] = set()
    for index, dependency in enumerate(spec.dependencies):
        add_ref(dependency.local_ref, f"/dependencies/{index}/local_ref")
        dependency_targets.add(dependency.target_ref)
        if dependency.target_ref not in target_barriers:
            diagnostics.append(
                _diagnostic(
                    "design_v3.unneeded_dependency",
                    f"/dependencies/{index}/target_ref",
                    (dependency.target_ref,),
                    "target one locked or puzzle door/hatch",
                )
            )
        if dependency.located_in_room_ref not in rooms:
            diagnostics.append(
                _diagnostic(
                    "design_v3.unknown_room_ref",
                    f"/dependencies/{index}/located_in_room_ref",
                    (dependency.located_in_room_ref,),
                    "place the dependency in a declared room",
                )
            )
    for target in sorted(target_barriers - dependency_targets):
        diagnostics.append(
            _diagnostic(
                "design_v3.missing_dependency",
                "/dependencies",
                (target,),
                "add one key or clue dependency for each barrier",
            )
        )
    duplicate_targets = [item.target_ref for item in spec.dependencies]
    for target in sorted(
        {item for item in duplicate_targets if duplicate_targets.count(item) > 1}
    ):
        diagnostics.append(
            _diagnostic(
                "design_v3.duplicate_dependency_target",
                "/dependencies",
                (target,),
                "provide exactly one dependency per barrier",
            )
        )

    entrances = [room for room in rooms.values() if room.role is RoomRole.ENTRANCE]
    if len(entrances) != 1:
        diagnostics.append(
            _diagnostic(
                "design_v3.entrance_required",
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
                "design_v3.final_objective_required",
                "/objectives",
                (),
                "declare exactly one final objective",
            )
        )
    for index, item in enumerate(spec.objectives):
        if item.room_ref not in rooms:
            diagnostics.append(
                _diagnostic(
                    "design_v3.unknown_room_ref",
                    f"/objectives/{index}/room_ref",
                    (item.room_ref,),
                    "reference a declared room",
                )
            )
    _validate_room_local_refs("traps", spec.traps, rooms, add_ref, diagnostics)
    _validate_room_local_refs("puzzles", spec.puzzles, rooms, add_ref, diagnostics)
    _validate_room_local_refs("features", spec.features, rooms, add_ref, diagnostics)
    return diagnostics


def _validate_room_local_refs(
    collection_name: str,
    values: tuple[DesignTrapV3 | DesignPuzzleV3 | DesignFeatureV3, ...],
    rooms: dict[str, DesignRoomV3],
    add_ref: Callable[[str, str], None],
    diagnostics: list[DungeonDesignV3CompileDiagnostic],
) -> None:
    # ``add_ref`` is local to the compiler validation loop; keeping reference
    # collection there makes duplicate diagnostics deterministic.
    for index, item in enumerate(values):
        add_ref(item.local_ref, f"/{collection_name}/{index}/local_ref")
        if item.room_ref not in rooms:
            diagnostics.append(
                _diagnostic(
                    "design_v3.unknown_room_ref",
                    f"/{collection_name}/{index}/room_ref",
                    (item.room_ref,),
                    "reference a declared room",
                )
            )


def _diagnostic(
    code: str, path: str, refs: tuple[str, ...], repair: str
) -> DungeonDesignV3CompileDiagnostic:
    return DungeonDesignV3CompileDiagnostic(
        code=code, path=path, affected_refs=tuple(sorted(refs)), repair=repair
    )


def _component_id(kind: str, identity: str) -> str:
    digest = sha256(
        f"{DUNGEON_DESIGN_V3_COMPILER_VERSION}:{kind}:{identity}".encode()
    ).hexdigest()[:20]
    return f"v3-{kind}-{digest}"


def _difficulty(band: ChallengeBand) -> int:
    return {ChallengeBand.LOW: 10, ChallengeBand.MODERATE: 13, ChallengeBand.HIGH: 16}[
        band
    ]


def _hash_json(payload: object) -> str:
    return sha256(
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    ).hexdigest()
