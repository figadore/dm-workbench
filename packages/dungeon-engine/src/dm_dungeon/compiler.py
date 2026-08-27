"""Pure deterministic compiler for the Tier A ``DungeonPlan`` grammar."""

from __future__ import annotations

import json
from collections import deque
from hashlib import sha256
from typing import Annotated, Literal

from pydantic import Field, model_validator

from dm_dungeon.contracts.brief import DungeonBrief, DungeonPurpose, PacingStyle
from dm_dungeon.contracts.certificate import (
    TOPOLOGY_CERTIFICATE_VERSION,
    TOPOLOGY_GRAMMAR_VERSION,
    BranchWitness,
    CertifiedConnectionRef,
    CertifiedRoomRef,
    ConnectionChannelWitness,
    CriticalPathWitness,
    EmbeddingRoomWitness,
    GateReachabilityWitness,
    GrammarStep,
    LoopWitness,
    RoomDemandWitness,
    RoomPortAssignmentWitness,
    TopologyCertificate,
)
from dm_dungeon.contracts.common import (
    ContractModel,
    NonEmptyText,
    OpaqueId,
    Visibility,
)
from dm_dungeon.contracts.mechanics import (
    DUNGEON_MECHANICS_POLICY_VERSION,
    BarrierIntent,
    CompiledDoorMechanics,
    CompiledEncounterSlot,
    CompiledRoomFeature,
    CompiledRoomObjective,
    CompiledRoomTrap,
    DungeonMechanicsPlan,
    ObjectiveKind,
)
from dm_dungeon.contracts.plan import (
    ChallengeBand,
    DependencyKind,
    DungeonPlan,
    GateIntentKind,
    PlanRoom,
    RoomSizeBand,
)
from dm_dungeon.contracts.topology import (
    BranchRequirement,
    CluePlacement,
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
    SecretBypass,
    TopologyFloor,
    TopologyRoom,
)
from dm_dungeon.layout.constructive import required_floor_bounds
from dm_dungeon.layout.contracts import FloorLayoutBounds
from dm_dungeon.validation.certificate import validate_topology_certificate

DUNGEON_PLAN_COMPILER_VERSION: Literal["dungeon-plan-compiler-v1"] = (
    "dungeon-plan-compiler-v1"
)


class DungeonPlanCompileDiagnostic(ContractModel):
    """Bounded, body-free repair information for a rejected plan."""

    code: Annotated[str, Field(pattern=r"^plan\.[a-z0-9_]+$")]
    path: Annotated[str, Field(min_length=1, max_length=256)]
    affected_refs: tuple[OpaqueId, ...] = Field(max_length=8)
    repair: NonEmptyText


class DungeonPlanCompileResult(ContractModel):
    """A compiled topology/certificate or bounded plan diagnostics."""

    accepted: bool
    compiler_version: Literal["dungeon-plan-compiler-v1"]
    input_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    output_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")] | None = None
    mechanics_plan: DungeonMechanicsPlan | None = None
    brief: DungeonBrief | None = None
    topology: DungeonTopology | None = None
    certificate: TopologyCertificate | None = None
    floor_bounds: tuple[FloorLayoutBounds, ...] = ()
    warnings: tuple[DungeonPlanCompileDiagnostic, ...] = ()
    diagnostics: tuple[DungeonPlanCompileDiagnostic, ...] = Field(max_length=8)

    @model_validator(mode="after")
    def require_consistent_result(self) -> DungeonPlanCompileResult:
        compiled = (
            self.brief,
            self.topology,
            self.certificate,
            self.mechanics_plan,
            self.output_hash,
        )
        if self.accepted:
            if any(value is None for value in compiled) or not self.floor_bounds:
                raise ValueError("accepted compilation requires all compiled outputs")
            if self.diagnostics:
                raise ValueError("accepted compilation cannot contain diagnostics")
        elif any(value is not None for value in compiled) or self.floor_bounds:
            raise ValueError("rejected compilation cannot contain compiled output")
        elif not self.diagnostics:
            raise ValueError("rejected compilation requires diagnostics")
        return self


class _Edge(ContractModel):
    ref: str
    kind: Literal["critical_path", "branch", "loop"]
    from_ref: str
    to_ref: str
    branch_ref: str | None = None
    loop_ref: str | None = None
    secret: bool = False


def compile_dungeon_plan(plan: DungeonPlan) -> DungeonPlanCompileResult:
    """Construct one connected graph without model-authored edges or randomness."""
    input_hash = _hash_contract(plan)
    diagnostics = _validate_plan(plan)
    if diagnostics:
        return DungeonPlanCompileResult(
            accepted=False,
            compiler_version=DUNGEON_PLAN_COMPILER_VERSION,
            input_hash=input_hash,
            diagnostics=tuple(diagnostics[:8]),
        )

    rooms_by_ref = {room.ref: room for room in plan.rooms}
    floor_id = _component_id("floor", "main")
    room_ids = {ref: _component_id("room", ref) for ref in rooms_by_ref}
    edges = _construct_edges(plan)
    connection_ids = {edge.ref: _component_id("connection", edge.ref) for edge in edges}
    gate = plan.gates[0] if plan.gates else None
    gated_edge = None if gate is None else _edge_between(edges, *gate.between_rooms)
    gate_id = None if gate is None else _component_id("gate", gate.ref)
    dependency_id = None if gate is None else _component_id("dependency", gate.ref)

    floor = TopologyFloor(
        id=floor_id,
        name=plan.title,
        level_index=0,
        target_room_count=len(plan.rooms),
        visibility=Visibility.PLAYER_SAFE,
    )
    critical_refs = set(plan.critical_path)
    topology_rooms = tuple(
        TopologyRoom(
            id=room_ids[room.ref],
            floor_id=floor_id,
            name=room.name,
            role=room.role,
            required=room.ref in critical_refs,
            size=_size_constraints(room.size),
            capacity=_capacity(room.encounter),
            tags=room.tags,
            visibility=Visibility.PLAYER_SAFE,
        )
        for room in sorted(plan.rooms, key=lambda item: item.ref)
    )
    topology_connections = tuple(
        DoorConnection(
            kind="door",
            id=connection_ids[edge.ref],
            from_room_id=room_ids[edge.from_ref],
            to_room_id=room_ids[edge.to_ref],
            door_type=(
                DoorType.SECRET
                if edge.secret
                else DoorType.LOCKED
                if gated_edge is not None and edge.ref == gated_edge.ref
                else DoorType.NORMAL
            ),
            gate_id=(
                gate_id
                if gated_edge is not None and edge.ref == gated_edge.ref
                else None
            ),
            from_hidden=edge.secret,
            to_hidden=edge.secret,
            visibility=Visibility.DM_ONLY if edge.secret else Visibility.PLAYER_SAFE,
        )
        for edge in edges
    )

    gates: tuple[Gate, ...] = ()
    keys: tuple[KeyPlacement, ...] = ()
    clues: tuple[CluePlacement, ...] = ()
    if gate is not None:
        assert (
            gated_edge is not None and gate_id is not None and dependency_id is not None
        )
        dependency_kind = (
            GateDependencyKind.KEY
            if gate.dependency_kind is DependencyKind.KEY
            else GateDependencyKind.CLUE
        )
        gates = (
            Gate(
                id=gate_id,
                name=f"Gate: {gate.dependency_name}",
                kind=(
                    GateKind.LOCK
                    if gate.kind is GateIntentKind.LOCKED
                    else GateKind.PUZZLE
                ),
                blocks_connection_ids=(connection_ids[gated_edge.ref],),
                requires_all=(
                    GateDependency(kind=dependency_kind, target_id=dependency_id),
                ),
                visibility=Visibility.DM_ONLY,
            ),
        )
        if gate.dependency_kind is DependencyKind.KEY:
            keys = (
                KeyPlacement(
                    id=dependency_id,
                    name=gate.dependency_name,
                    located_in_room_id=room_ids[gate.dependency_room],
                    opens_gate_ids=(gate_id,),
                    visibility=Visibility.DM_ONLY,
                ),
            )
        else:
            clues = (
                CluePlacement(
                    id=dependency_id,
                    name=gate.dependency_name,
                    text=gate.dependency_name,
                    located_in_room_id=room_ids[gate.dependency_room],
                    supports_gate_ids=(gate_id,),
                    visibility=Visibility.DM_ONLY,
                ),
            )

    tree_edges = tuple(edge for edge in edges if edge.kind != "loop")
    loop_requirements: list[LoopRequirement] = []
    secret_bypasses: list[SecretBypass] = []
    for loop in plan.loops:
        loop_edge = next(edge for edge in edges if edge.loop_ref == loop.ref)
        path_refs, path_edge_refs = _tree_path(tree_edges, loop.from_room, loop.to_room)
        loop_requirements.append(
            LoopRequirement(
                id=_component_id("loop", loop.ref),
                room_ids=tuple(room_ids[ref] for ref in path_refs),
                visibility=Visibility.DM_ONLY
                if loop.secret
                else Visibility.PLAYER_SAFE,
            )
        )
        if (
            loop.secret
            and gate_id is not None
            and gated_edge is not None
            and gated_edge.ref in path_edge_refs
        ):
            secret_bypasses.append(
                SecretBypass(
                    id=_component_id("secret-bypass", loop.ref),
                    entry_room_id=room_ids[loop.from_room],
                    exit_room_id=room_ids[loop.to_room],
                    connection_ids=(connection_ids[loop_edge.ref],),
                    bypassed_gate_ids=(gate_id,),
                    visibility=Visibility.DM_ONLY,
                )
            )

    topology = DungeonTopology(
        schema_version="1.0.0",
        id=_component_id("topology", "root"),
        visibility=Visibility.PLAYER_SAFE,
        floors=(floor,),
        rooms=topology_rooms,
        connections=topology_connections,
        gates=gates,
        keys=keys,
        clues=clues,
        loops=tuple(loop_requirements),
        branches=tuple(
            BranchRequirement(
                id=_component_id("branch", branch.ref),
                junction_room_id=room_ids[branch.from_room],
                branch_room_ids=tuple(room_ids[ref] for ref in branch.rooms),
                visibility=Visibility.PLAYER_SAFE,
            )
            for branch in plan.branches
        ),
        secret_bypasses=tuple(secret_bypasses),
    )
    mechanics_plan = _compile_mechanics(
        plan,
        edges=edges,
        room_ids=room_ids,
        connection_ids=connection_ids,
        gated_edge=gated_edge,
        gate_id=gate_id,
    )
    certificate = _compile_certificate(
        plan,
        topology=topology,
        mechanics=mechanics_plan,
        edges=edges,
        room_ids=room_ids,
        connection_ids=connection_ids,
        gated_edge=gated_edge,
        gate_id=gate_id,
        dependency_id=dependency_id,
    )
    certificate_report = validate_topology_certificate(
        plan, topology, mechanics_plan, certificate
    )
    if not certificate_report.valid:
        codes = ", ".join(item.code for item in certificate_report.diagnostics)
        raise RuntimeError(f"compiler emitted an invalid topology certificate: {codes}")

    brief = DungeonBrief(
        schema_version="1.0.0",
        id=_component_id("brief", "root"),
        title=plan.title,
        purpose=DungeonPurpose.RUIN,
        summary=plan.premise,
        visibility=Visibility.PLAYER_SAFE,
        themes=plan.themes,
        pacing=PacingStyle.BALANCED,
        floor_count=1,
        target_room_count=len(plan.rooms),
    )
    floor_bounds = (required_floor_bounds(certificate, topology),)
    output_hash = _hash_json(
        {
            "brief": brief.model_dump(mode="json"),
            "topology": topology.model_dump(mode="json"),
            "certificate": certificate.model_dump(mode="json"),
            "mechanics_plan": mechanics_plan.model_dump(mode="json"),
            "floor_bounds": [item.model_dump(mode="json") for item in floor_bounds],
        }
    )
    return DungeonPlanCompileResult(
        accepted=True,
        compiler_version=DUNGEON_PLAN_COMPILER_VERSION,
        input_hash=input_hash,
        output_hash=output_hash,
        mechanics_plan=mechanics_plan,
        brief=brief,
        topology=topology,
        certificate=certificate,
        floor_bounds=floor_bounds,
        diagnostics=(),
    )


def _validate_plan(plan: DungeonPlan) -> list[DungeonPlanCompileDiagnostic]:
    diagnostics: list[DungeonPlanCompileDiagnostic] = []
    rooms: dict[str, PlanRoom] = {}
    for index, room in enumerate(plan.rooms):
        if room.ref in rooms:
            diagnostics.append(
                _diagnostic(
                    "plan.duplicate_room_ref",
                    f"/rooms/{index}/ref",
                    (room.ref,),
                    "use a unique room ref",
                )
            )
        rooms[room.ref] = room

    entrances = [room.ref for room in plan.rooms if room.role is RoomRole.ENTRANCE]
    objectives = [room.ref for room in plan.rooms if room.role is RoomRole.OBJECTIVE]
    if len(entrances) != 1:
        diagnostics.append(
            _diagnostic(
                "plan.entrance_required",
                "/rooms",
                tuple(entrances),
                "declare exactly one entrance room",
            )
        )
    if len(objectives) != 1:
        diagnostics.append(
            _diagnostic(
                "plan.objective_required",
                "/rooms",
                tuple(objectives),
                "declare exactly one objective room",
            )
        )

    seen_path: set[str] = set()
    for index, ref in enumerate(plan.critical_path):
        if ref not in rooms:
            diagnostics.append(
                _diagnostic(
                    "plan.unknown_room_ref",
                    f"/critical_path/{index}",
                    (ref,),
                    "reference a declared room",
                )
            )
        if ref in seen_path:
            diagnostics.append(
                _diagnostic(
                    "plan.duplicate_path_room",
                    f"/critical_path/{index}",
                    (ref,),
                    "list each critical-path room once",
                )
            )
        seen_path.add(ref)
    if entrances and plan.critical_path[0] != entrances[0]:
        diagnostics.append(
            _diagnostic(
                "plan.critical_path_start",
                "/critical_path/0",
                (plan.critical_path[0], entrances[0]),
                "start the critical path at the entrance",
            )
        )
    if objectives and plan.critical_path[-1] != objectives[0]:
        diagnostics.append(
            _diagnostic(
                "plan.critical_path_end",
                f"/critical_path/{len(plan.critical_path) - 1}",
                (plan.critical_path[-1], objectives[0]),
                "end the critical path at the objective",
            )
        )

    introduced = set(plan.critical_path)
    branch_refs: set[str] = set()
    for index, branch in enumerate(plan.branches):
        if branch.ref in branch_refs:
            diagnostics.append(
                _diagnostic(
                    "plan.duplicate_branch_ref",
                    f"/branches/{index}/ref",
                    (branch.ref,),
                    "use a unique branch ref",
                )
            )
        branch_refs.add(branch.ref)
        if branch.from_room not in set(plan.critical_path):
            diagnostics.append(
                _diagnostic(
                    "plan.unsupported_branch_attachment",
                    f"/branches/{index}/from_room",
                    (branch.from_room,),
                    "attach a Tier A branch to a critical-path room",
                )
            )
        for room_index, ref in enumerate(branch.rooms):
            if ref not in rooms:
                diagnostics.append(
                    _diagnostic(
                        "plan.unknown_room_ref",
                        f"/branches/{index}/rooms/{room_index}",
                        (ref,),
                        "reference a declared room",
                    )
                )
            if ref in introduced:
                diagnostics.append(
                    _diagnostic(
                        "plan.room_reused",
                        f"/branches/{index}/rooms/{room_index}",
                        (ref,),
                        "introduce each non-critical room on exactly one branch",
                    )
                )
            introduced.add(ref)
    unassigned = sorted(set(rooms) - introduced)
    if unassigned:
        diagnostics.append(
            _diagnostic(
                "plan.unassigned_room",
                "/rooms",
                tuple(unassigned),
                "place every room on the critical path or one branch",
            )
        )
    for room in plan.rooms:
        if (
            room.ref not in set(plan.critical_path)
            and room.role is not RoomRole.OPTIONAL
        ):
            diagnostics.append(
                _diagnostic(
                    "plan.branch_room_not_optional",
                    f"/rooms/{plan.rooms.index(room)}/role",
                    (room.ref,),
                    "use the optional role for branch rooms",
                )
            )

    edges = _construct_edges(plan)
    existing_pairs = {
        _pair(edge.from_ref, edge.to_ref) for edge in edges if edge.kind != "loop"
    }
    loop_refs: set[str] = set()
    for index, loop in enumerate(plan.loops):
        if loop.ref in loop_refs:
            diagnostics.append(
                _diagnostic(
                    "plan.duplicate_loop_ref",
                    f"/loops/{index}/ref",
                    (loop.ref,),
                    "use a unique loop ref",
                )
            )
        loop_refs.add(loop.ref)
        for field, ref in (("from_room", loop.from_room), ("to_room", loop.to_room)):
            if ref not in rooms:
                diagnostics.append(
                    _diagnostic(
                        "plan.unknown_room_ref",
                        f"/loops/{index}/{field}",
                        (ref,),
                        "reference a declared room",
                    )
                )
        if loop.from_room == loop.to_room:
            diagnostics.append(
                _diagnostic(
                    "plan.self_loop",
                    f"/loops/{index}",
                    (loop.from_room,),
                    "connect two distinct rooms",
                )
            )
        elif _pair(loop.from_room, loop.to_room) in existing_pairs:
            diagnostics.append(
                _diagnostic(
                    "plan.duplicate_connection",
                    f"/loops/{index}",
                    (loop.from_room, loop.to_room),
                    "choose non-adjacent loop endpoints",
                )
            )

    content_rooms: set[str] = set()
    for index, content in enumerate(plan.room_contents):
        if content.room_ref not in rooms:
            diagnostics.append(
                _diagnostic(
                    "plan.unknown_room_ref",
                    f"/room_contents/{index}/room_ref",
                    (content.room_ref,),
                    "reference a declared room",
                )
            )
        if content.room_ref in content_rooms:
            diagnostics.append(
                _diagnostic(
                    "plan.duplicate_room_content",
                    f"/room_contents/{index}/room_ref",
                    (content.room_ref,),
                    "provide at most one content record per room",
                )
            )
        content_rooms.add(content.room_ref)
    objective_content = [
        item for item in plan.room_contents if item.objective is not None
    ]
    if len(objective_content) != 1 or (
        objectives
        and objective_content
        and objective_content[0].room_ref != objectives[0]
    ):
        diagnostics.append(
            _diagnostic(
                "plan.final_objective_content_required",
                "/room_contents",
                tuple(item.room_ref for item in objective_content),
                "name exactly one objective in the objective room",
            )
        )

    if plan.gates:
        gate = plan.gates[0]
        left, right = gate.between_rooms
        target = _edge_between(edges, left, right)
        if left not in rooms or right not in rooms:
            diagnostics.append(
                _diagnostic(
                    "plan.unknown_room_ref",
                    "/gates/0/between_rooms",
                    tuple(ref for ref in (left, right) if ref not in rooms),
                    "reference two declared rooms",
                )
            )
        if target is None:
            diagnostics.append(
                _diagnostic(
                    "plan.gate_connection_missing",
                    "/gates/0/between_rooms",
                    (left, right),
                    "gate one constructed critical-path or branch connection",
                )
            )
        elif target.secret:
            diagnostics.append(
                _diagnostic(
                    "plan.gate_on_secret_route",
                    "/gates/0/between_rooms",
                    (left, right),
                    "place the gate on a public progression connection",
                )
            )
        if gate.dependency_room not in rooms:
            diagnostics.append(
                _diagnostic(
                    "plan.unknown_room_ref",
                    "/gates/0/dependency_room",
                    (gate.dependency_room,),
                    "place the dependency in a declared room",
                )
            )
        if (
            gate.kind is GateIntentKind.LOCKED
            and gate.dependency_kind is not DependencyKind.KEY
        ) or (
            gate.kind is GateIntentKind.PUZZLE
            and gate.dependency_kind is not DependencyKind.CLUE
        ):
            diagnostics.append(
                _diagnostic(
                    "plan.gate_dependency_kind",
                    "/gates/0/dependency_kind",
                    (gate.ref,),
                    "use a key for a locked gate or a clue for a puzzle gate",
                )
            )
        if target is not None and entrances and gate.dependency_room in rooms:
            reachable = _reachable_refs(
                tuple(
                    edge for edge in edges if edge.ref != target.ref and not edge.secret
                ),
                entrances[0],
            )
            if gate.dependency_room not in reachable:
                diagnostics.append(
                    _diagnostic(
                        "plan.gate_dependency_unreachable",
                        "/gates/0/dependency_room",
                        (gate.dependency_room, gate.ref),
                        "place the dependency in a public room reachable before the gate",
                    )
                )
    return diagnostics


def _construct_edges(plan: DungeonPlan) -> tuple[_Edge, ...]:
    edges: list[_Edge] = []
    for index, (left, right) in enumerate(
        zip(plan.critical_path, plan.critical_path[1:], strict=False)
    ):
        edges.append(
            _Edge(
                ref=f"critical_{index}",
                kind="critical_path",
                from_ref=left,
                to_ref=right,
            )
        )
    for branch in plan.branches:
        previous = branch.from_room
        for index, room_ref in enumerate(branch.rooms):
            edges.append(
                _Edge(
                    ref=f"{branch.ref}_{index}",
                    kind="branch",
                    from_ref=previous,
                    to_ref=room_ref,
                    branch_ref=branch.ref,
                )
            )
            previous = room_ref
    for loop in plan.loops:
        edges.append(
            _Edge(
                ref=loop.ref,
                kind="loop",
                from_ref=loop.from_room,
                to_ref=loop.to_room,
                loop_ref=loop.ref,
                secret=loop.secret,
            )
        )
    return tuple(edges)


def _compile_mechanics(
    plan: DungeonPlan,
    *,
    edges: tuple[_Edge, ...],
    room_ids: dict[str, str],
    connection_ids: dict[str, str],
    gated_edge: _Edge | None,
    gate_id: str | None,
) -> DungeonMechanicsPlan:
    gate = plan.gates[0] if plan.gates else None
    contents = {item.room_ref: item for item in plan.room_contents}
    objective_room = next(
        room for room in plan.rooms if room.role is RoomRole.OBJECTIVE
    )
    objective_name = contents[objective_room.ref].objective
    assert objective_name is not None
    return DungeonMechanicsPlan(
        policy_version=DUNGEON_MECHANICS_POLICY_VERSION,
        connection_ids=tuple(connection_ids[edge.ref] for edge in edges),
        room_ids=tuple(sorted(room_ids.values())),
        door_mechanics=tuple(
            CompiledDoorMechanics(
                id=_component_id("door-mechanics", edge.ref),
                connection_id=connection_ids[edge.ref],
                concealed=edge.secret,
                gate_id=(
                    gate_id
                    if gated_edge is not None and edge.ref == gated_edge.ref
                    else None
                ),
                gate_kind=(
                    BarrierIntent.NONE
                    if gated_edge is None or edge.ref != gated_edge.ref or gate is None
                    else BarrierIntent.LOCKED
                    if gate.kind is GateIntentKind.LOCKED
                    else BarrierIntent.PUZZLE
                ),
                discovery_difficulty=13 if edge.secret else None,
                unlock_difficulty=(
                    13
                    if gated_edge is not None and edge.ref == gated_edge.ref
                    else None
                ),
            )
            for edge in edges
        ),
        room_traps=tuple(
            CompiledRoomTrap(
                id=_component_id("trap", content.room_ref),
                room_id=room_ids[content.room_ref],
                detection_difficulty=_difficulty(content.trap.challenge),
                disable_difficulty=_difficulty(content.trap.challenge),
            )
            for content in sorted(plan.room_contents, key=lambda item: item.room_ref)
            if content.trap is not None
        ),
        room_puzzles=(),
        room_features=tuple(
            CompiledRoomFeature(
                id=_component_id("feature", content.room_ref),
                room_id=room_ids[content.room_ref],
                kind=content.feature.kind,
            )
            for content in sorted(plan.room_contents, key=lambda item: item.room_ref)
            if content.feature is not None
        ),
        room_objectives=(
            CompiledRoomObjective(
                id=_component_id("objective", objective_room.ref),
                room_id=room_ids[objective_room.ref],
                kind=ObjectiveKind.FINAL_OBJECTIVE,
                name=objective_name,
            ),
        ),
        encounter_slots=tuple(
            CompiledEncounterSlot(
                id=_component_id("encounter-slot", room.ref),
                room_id=room_ids[room.ref],
                intent=room.encounter,
            )
            for room in sorted(plan.rooms, key=lambda item: item.ref)
            if room.encounter is not None
        ),
    )


def _compile_certificate(
    plan: DungeonPlan,
    *,
    topology: DungeonTopology,
    mechanics: DungeonMechanicsPlan,
    edges: tuple[_Edge, ...],
    room_ids: dict[str, str],
    connection_ids: dict[str, str],
    gated_edge: _Edge | None,
    gate_id: str | None,
    dependency_id: str | None,
) -> TopologyCertificate:
    tree_edges = tuple(edge for edge in edges if edge.kind != "loop")
    critical_edges = tuple(edge for edge in edges if edge.kind == "critical_path")
    branch_witnesses: list[BranchWitness] = []
    embedding: list[EmbeddingRoomWitness] = [
        EmbeddingRoomWitness(
            room_id=room_ids[ref],
            region="backbone",
            order=index,
            band="backbone",
            band_index=0,
        )
        for index, ref in enumerate(plan.critical_path)
    ]
    for index, branch in enumerate(plan.branches):
        branch_edges = tuple(edge for edge in edges if edge.branch_ref == branch.ref)
        band: Literal["upper", "lower"] = "upper" if index % 2 == 0 else "lower"
        band_index = index // 2 + 1
        branch_witnesses.append(
            BranchWitness(
                ref=branch.ref,
                attachment_room_id=room_ids[branch.from_room],
                room_ids=tuple(room_ids[ref] for ref in branch.rooms),
                connection_ids=tuple(connection_ids[edge.ref] for edge in branch_edges),
                band=band,
                band_index=band_index,
            )
        )
        embedding.extend(
            EmbeddingRoomWitness(
                room_id=room_ids[ref],
                region="branch",
                order=room_index,
                band=band,
                band_index=band_index,
            )
            for room_index, ref in enumerate(branch.rooms)
        )
    embedding_index = {item.room_id: index for index, item in enumerate(embedding)}
    loop_witnesses: list[LoopWitness] = []
    for loop in plan.loops:
        edge = next(item for item in edges if item.loop_ref == loop.ref)
        path_refs, path_edge_refs = _tree_path(tree_edges, loop.from_room, loop.to_room)
        endpoints = (
            embedding_index[room_ids[loop.from_room]],
            embedding_index[room_ids[loop.to_room]],
        )
        loop_witnesses.append(
            LoopWitness(
                ref=loop.ref,
                from_room_id=room_ids[loop.from_room],
                to_room_id=room_ids[loop.to_room],
                connection_id=connection_ids[edge.ref],
                cycle_room_ids=tuple(room_ids[ref] for ref in path_refs),
                cycle_connection_ids=(
                    *(connection_ids[ref] for ref in path_edge_refs),
                    connection_ids[edge.ref],
                ),
                interval_start=min(endpoints),
                interval_end=max(endpoints),
                secret=loop.secret,
            )
        )

    adjacency = _adjacency(edges)
    full_reachable = _reachable(adjacency, plan.critical_path[0])
    public_edges = tuple(edge for edge in edges if not edge.secret)
    public_reachable = _reachable(_adjacency(public_edges), plan.critical_path[0])
    gate_witnesses: tuple[GateReachabilityWitness, ...] = ()
    if plan.gates:
        gate = plan.gates[0]
        assert (
            gated_edge is not None and gate_id is not None and dependency_id is not None
        )
        before = _reachable_refs(
            tuple(edge for edge in public_edges if edge.ref != gated_edge.ref),
            plan.critical_path[0],
        )
        gate_witnesses = (
            GateReachabilityWitness(
                gate_id=gate_id,
                dependency_id=dependency_id,
                dependency_room_id=room_ids[gate.dependency_room],
                blocked_connection_id=connection_ids[gated_edge.ref],
                reachable_before_gate_room_ids=tuple(
                    sorted(room_ids[ref] for ref in before)
                ),
                opened_order=1,
            ),
        )

    mechanics_features = {item.room_id for item in mechanics.room_features}
    mechanics_traps = {item.room_id for item in mechanics.room_traps}
    demands: list[RoomDemandWitness] = []
    for room in sorted(plan.rooms, key=lambda item: item.ref):
        room_id = room_ids[room.ref]
        degree = len(adjacency[room.ref])
        base = _size_constraints(room.size).minimum_area_cells
        encounter = _encounter_demand(room.encounter)
        feature = 4 if room_id in mechanics_features else 0
        trap = 1 if room_id in mechanics_traps else 0
        required = max(base, encounter + feature + trap + 4)
        demands.append(
            RoomDemandWitness(
                room_id=room_id,
                degree=degree,
                required_ports=degree,
                separation_clearance_cells=max(0, degree - 1),
                minimum_boundary_cells=degree + max(0, degree - 1),
                base_interior_cells=base,
                encounter_cells=encounter,
                feature_cells=feature,
                trap_cells=trap,
                required_interior_cells=required,
            )
        )

    room_ports, connection_channels = _compile_physical_witnesses(
        edges,
        room_ids=room_ids,
        connection_ids=connection_ids,
        embedding=embedding,
        branch_witnesses=branch_witnesses,
    )

    grammar_steps: list[GrammarStep] = [
        GrammarStep(
            kind="critical_path",
            ref="critical_path",
            room_ids=tuple(room_ids[ref] for ref in plan.critical_path),
            connection_ids=tuple(connection_ids[edge.ref] for edge in critical_edges),
        )
    ]
    grammar_steps.extend(
        GrammarStep(
            kind="branch",
            ref=branch.ref,
            room_ids=(
                room_ids[branch.from_room],
                *(room_ids[ref] for ref in branch.rooms),
            ),
            connection_ids=tuple(
                connection_ids[edge.ref]
                for edge in edges
                if edge.branch_ref == branch.ref
            ),
        )
        for branch in plan.branches
    )
    grammar_steps.extend(
        GrammarStep(
            kind="loop",
            ref=loop.ref,
            room_ids=(room_ids[loop.from_room], room_ids[loop.to_room]),
            connection_ids=(connection_ids[loop.ref],),
        )
        for loop in plan.loops
    )
    return TopologyCertificate(
        certificate_version=TOPOLOGY_CERTIFICATE_VERSION,
        grammar_version=TOPOLOGY_GRAMMAR_VERSION,
        plan_hash=_hash_contract(plan),
        topology_hash=_hash_contract(topology),
        topology_id=topology.id,
        rooms=tuple(
            CertifiedRoomRef(ref=ref, room_id=room_ids[ref]) for ref in sorted(room_ids)
        ),
        connections=tuple(
            CertifiedConnectionRef(
                ref=edge.ref,
                connection_id=connection_ids[edge.ref],
                kind=edge.kind,
                from_room_id=room_ids[edge.from_ref],
                to_room_id=room_ids[edge.to_ref],
            )
            for edge in edges
        ),
        grammar_steps=tuple(grammar_steps),
        critical_path=CriticalPathWitness(
            room_ids=tuple(room_ids[ref] for ref in plan.critical_path),
            connection_ids=tuple(connection_ids[edge.ref] for edge in critical_edges),
        ),
        component_count=_component_count(adjacency),
        room_count=len(plan.rooms),
        connection_count=len(edges),
        cycle_rank=len(edges) - len(plan.rooms) + _component_count(adjacency),
        branches=tuple(branch_witnesses),
        loops=tuple(loop_witnesses),
        gates=gate_witnesses,
        full_reachable_room_ids=tuple(sorted(room_ids[ref] for ref in full_reachable)),
        public_reachable_room_ids=tuple(
            sorted(room_ids[ref] for ref in public_reachable)
        ),
        room_demands=tuple(demands),
        embedding_rooms=tuple(embedding),
        room_ports=room_ports,
        connection_channels=connection_channels,
        required_bands=1 + len(plan.branches) + len(plan.loops),
    )


def _compile_physical_witnesses(
    edges: tuple[_Edge, ...],
    *,
    room_ids: dict[str, str],
    connection_ids: dict[str, str],
    embedding: list[EmbeddingRoomWitness],
    branch_witnesses: list[BranchWitness],
) -> tuple[
    tuple[RoomPortAssignmentWitness, ...],
    tuple[ConnectionChannelWitness, ...],
]:
    """Assign wall sides and reserved bands without placing any cells."""

    sides: dict[str, dict[str, list[str]]] = {
        room_id: {"north": [], "east": [], "south": [], "west": []}
        for room_id in room_ids.values()
    }
    embedding_by_room = {item.room_id: item for item in embedding}
    branch_by_ref = {item.ref: item for item in branch_witnesses}
    channels: list[ConnectionChannelWitness] = []

    for edge in edges:
        connection_id = connection_ids[edge.ref]
        from_id = room_ids[edge.from_ref]
        to_id = room_ids[edge.to_ref]
        if edge.kind == "critical_path":
            from_side, to_side = "east", "west"
            channel_kind: Literal["backbone", "branch", "loop"] = "backbone"
            band: Literal["backbone", "upper", "lower", "loop"] = "backbone"
            band_index = 0
        elif edge.kind == "branch":
            assert edge.branch_ref is not None
            branch = branch_by_ref[edge.branch_ref]
            from_side, to_side = (
                ("north", "south") if branch.band == "upper" else ("south", "north")
            )
            channel_kind = "branch"
            band = branch.band
            band_index = branch.band_index
        else:
            from_side = _loop_port_side(embedding_by_room[from_id])
            to_side = _loop_port_side(embedding_by_room[to_id])
            channel_kind = "loop"
            band = "loop"
            band_index = 1
        sides[from_id][from_side].append(connection_id)
        sides[to_id][to_side].append(connection_id)
        channels.append(
            ConnectionChannelWitness(
                connection_id=connection_id,
                kind=channel_kind,
                band=band,
                band_index=band_index,
            )
        )

    return (
        tuple(
            RoomPortAssignmentWitness(
                room_id=room_id,
                north_connection_ids=tuple(sides[room_id]["north"]),
                east_connection_ids=tuple(sides[room_id]["east"]),
                south_connection_ids=tuple(sides[room_id]["south"]),
                west_connection_ids=tuple(sides[room_id]["west"]),
            )
            for room_id in sorted(sides)
        ),
        tuple(channels),
    )


def _loop_port_side(
    room: EmbeddingRoomWitness,
) -> Literal["north", "east", "south", "west"]:
    if room.band == "backbone":
        return "north"
    return "east" if room.band == "upper" else "west"


def _edge_between(edges: tuple[_Edge, ...], left: str, right: str) -> _Edge | None:
    pair = _pair(left, right)
    return next(
        (edge for edge in edges if _pair(edge.from_ref, edge.to_ref) == pair), None
    )


def _pair(left: str, right: str) -> frozenset[str]:
    return frozenset((left, right))


def _adjacency(edges: tuple[_Edge, ...]) -> dict[str, set[str]]:
    adjacency: dict[str, set[str]] = {}
    for edge in edges:
        adjacency.setdefault(edge.from_ref, set()).add(edge.to_ref)
        adjacency.setdefault(edge.to_ref, set()).add(edge.from_ref)
    return adjacency


def _reachable(adjacency: dict[str, set[str]], start: str) -> set[str]:
    seen = {start}
    pending = deque((start,))
    while pending:
        current = pending.popleft()
        for neighbor in sorted(adjacency.get(current, set()) - seen):
            seen.add(neighbor)
            pending.append(neighbor)
    return seen


def _reachable_refs(edges: tuple[_Edge, ...], start: str) -> set[str]:
    return _reachable(_adjacency(edges), start)


def _component_count(adjacency: dict[str, set[str]]) -> int:
    remaining = set(adjacency)
    count = 0
    while remaining:
        reached = _reachable(adjacency, min(remaining))
        remaining -= reached
        count += 1
    return count


def _tree_path(
    edges: tuple[_Edge, ...], start: str, end: str
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    neighbors: dict[str, list[tuple[str, str]]] = {}
    for edge in edges:
        neighbors.setdefault(edge.from_ref, []).append((edge.to_ref, edge.ref))
        neighbors.setdefault(edge.to_ref, []).append((edge.from_ref, edge.ref))
    pending = deque((start,))
    previous: dict[str, tuple[str, str] | None] = {start: None}
    while pending:
        current = pending.popleft()
        if current == end:
            break
        for neighbor, edge_ref in sorted(neighbors.get(current, ())):
            if neighbor not in previous:
                previous[neighbor] = (current, edge_ref)
                pending.append(neighbor)
    room_path = [end]
    edge_path: list[str] = []
    while room_path[-1] != start:
        step = previous[room_path[-1]]
        assert step is not None
        prior, edge_ref = step
        room_path.append(prior)
        edge_path.append(edge_ref)
    room_path.reverse()
    edge_path.reverse()
    return tuple(room_path), tuple(edge_path)


def _size_constraints(band: RoomSizeBand) -> RoomSizeConstraints:
    values = {
        RoomSizeBand.SMALL: (3, 5, 9, 25),
        RoomSizeBand.MEDIUM: (5, 8, 25, 64),
        RoomSizeBand.LARGE: (8, 12, 64, 144),
    }[band]
    return RoomSizeConstraints(
        minimum_width_cells=values[0],
        maximum_width_cells=values[1],
        minimum_height_cells=values[0],
        maximum_height_cells=values[1],
        minimum_area_cells=values[2],
        maximum_area_cells=values[3],
    )


def _capacity(encounter: object) -> RoomCapacity:
    if encounter is None:
        values = (1, 3, 6)
    elif str(encounter) in {"combat", "ambush"}:
        values = (3, 6, 10)
    else:
        values = (2, 5, 8)
    return RoomCapacity(
        minimum_occupants=values[0],
        comfortable_occupants=values[1],
        maximum_occupants=values[2],
    )


def _encounter_demand(encounter: object) -> int:
    if encounter is None:
        return 0
    return 16 if str(encounter) in {"combat", "ambush"} else 9


def _difficulty(band: ChallengeBand) -> int:
    return {
        ChallengeBand.LOW: 10,
        ChallengeBand.MODERATE: 13,
        ChallengeBand.HIGH: 16,
    }[band]


def _diagnostic(
    code: str, path: str, refs: tuple[str, ...], repair: str
) -> DungeonPlanCompileDiagnostic:
    return DungeonPlanCompileDiagnostic(
        code=code,
        path=path,
        affected_refs=tuple(sorted(set(refs)))[:8],
        repair=repair,
    )


def _component_id(kind: str, identity: str) -> str:
    digest = sha256(
        f"{DUNGEON_PLAN_COMPILER_VERSION}:{kind}:{identity}".encode()
    ).hexdigest()[:20]
    return f"v1-{kind}-{digest}"


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
