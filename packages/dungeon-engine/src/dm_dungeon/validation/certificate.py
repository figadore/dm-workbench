"""Independent recomputation of Tier A topology-certificate claims."""

from __future__ import annotations

import json
from collections import deque
from hashlib import sha256

from dm_dungeon.contracts.certificate import (
    TOPOLOGY_CERTIFICATE_VERSION,
    TOPOLOGY_GRAMMAR_VERSION,
    TopologyCertificate,
    TopologyCertificateDiagnostic,
    TopologyCertificateValidationReport,
)
from dm_dungeon.contracts.common import ContractModel, Visibility
from dm_dungeon.contracts.mechanics import DungeonMechanicsPlan
from dm_dungeon.contracts.plan import DungeonPlan, RoomSizeBand
from dm_dungeon.contracts.topology import DungeonTopology


def validate_topology_certificate(
    plan: DungeonPlan,
    topology: DungeonTopology,
    mechanics: DungeonMechanicsPlan,
    certificate: TopologyCertificate,
) -> TopologyCertificateValidationReport:
    """Recompute graph, progression, demand, and embedding witnesses."""
    diagnostics: list[TopologyCertificateDiagnostic] = []

    def reject(
        code: str,
        path: str,
        affected: tuple[str, ...],
        repair: str,
    ) -> None:
        diagnostics.append(
            TopologyCertificateDiagnostic(
                code=code,
                path=path,
                affected_ids=tuple(sorted(set(affected)))[:8],
                repair=repair,
            )
        )

    if certificate.grammar_version != TOPOLOGY_GRAMMAR_VERSION:
        reject(
            "certificate.grammar_version_mismatch",
            "/grammar_version",
            (certificate.topology_id,),
            "recompile with the supported topology grammar",
        )
    if certificate.topology_id != topology.id:
        reject(
            "certificate.topology_id_mismatch",
            "/topology_id",
            (certificate.topology_id, topology.id),
            "bind the certificate to the compiled topology",
        )
    if certificate.plan_hash != _hash_contract(plan):
        reject(
            "certificate.plan_hash_mismatch",
            "/plan_hash",
            (topology.id,),
            "recompute the certificate from the exact plan",
        )
    if certificate.topology_hash != _hash_contract(topology):
        reject(
            "certificate.topology_hash_mismatch",
            "/topology_hash",
            (topology.id,),
            "recompute the certificate from the exact topology",
        )

    room_ref_ids = {item.ref: item.room_id for item in certificate.rooms}
    topology_rooms = {item.id: item for item in topology.rooms}
    if set(room_ref_ids) != {room.ref for room in plan.rooms} or set(
        room_ref_ids.values()
    ) != set(topology_rooms):
        reject(
            "certificate.room_mapping_mismatch",
            "/rooms",
            tuple(room_ref_ids.values()),
            "map every plan room ref to exactly one topology room",
        )

    expected_edges = _expected_edges(plan)
    certified_edges = {item.ref: item for item in certificate.connections}
    topology_edges = {item.id: item for item in topology.connections}
    if set(certified_edges) != set(expected_edges) or set(
        item.connection_id for item in certified_edges.values()
    ) != set(topology_edges):
        reject(
            "certificate.connection_mapping_mismatch",
            "/connections",
            tuple(item.connection_id for item in certified_edges.values()),
            "map every grammar edge to exactly one topology connection",
        )
    else:
        for ref, (kind, left_ref, right_ref, secret) in expected_edges.items():
            item = certified_edges[ref]
            connection = topology_edges[item.connection_id]
            expected_ids = {room_ref_ids.get(left_ref), room_ref_ids.get(right_ref)}
            actual_ids = {connection.from_room_id, connection.to_room_id}
            if (
                item.kind != kind
                or {item.from_room_id, item.to_room_id} != expected_ids
                or actual_ids != expected_ids
                or (connection.visibility is Visibility.DM_ONLY) != secret
            ):
                reject(
                    "certificate.connection_witness_mismatch",
                    f"/connections/{ref}",
                    (item.connection_id,),
                    "recompute this edge from its progression primitive",
                )

    adjacency = _topology_adjacency(topology)
    components = _component_count(adjacency)
    rank = len(topology.connections) - len(topology.rooms) + components
    graph_values = (
        ("component_count", certificate.component_count, components),
        ("room_count", certificate.room_count, len(topology.rooms)),
        ("connection_count", certificate.connection_count, len(topology.connections)),
        ("cycle_rank", certificate.cycle_rank, rank),
    )
    for field, actual, expected in graph_values:
        if actual != expected:
            reject(
                "certificate.graph_fact_mismatch",
                f"/{field}",
                (topology.id,),
                f"record recomputed {field}",
            )
    if rank != len(plan.loops) or components != 1:
        reject(
            "certificate.unsupported_graph",
            "/cycle_rank",
            (topology.id,),
            "compile one connected component with one independent edge per loop",
        )

    critical_ids = tuple(room_ref_ids.get(ref, "") for ref in plan.critical_path)
    critical_edge_ids = tuple(
        certified_edges[f"critical_{index}"].connection_id
        for index in range(len(plan.critical_path) - 1)
        if f"critical_{index}" in certified_edges
    )
    if (
        certificate.critical_path.room_ids != critical_ids
        or certificate.critical_path.connection_ids != critical_edge_ids
    ):
        reject(
            "certificate.critical_path_mismatch",
            "/critical_path",
            critical_ids,
            "recompute the ordered entrance-to-objective path",
        )

    branch_by_ref = {item.ref: item for item in certificate.branches}
    for index, branch in enumerate(plan.branches):
        branch_witness = branch_by_ref.get(branch.ref)
        expected_room_ids = tuple(room_ref_ids.get(ref, "") for ref in branch.rooms)
        expected_connection_ids = tuple(
            certified_edges[f"{branch.ref}_{edge_index}"].connection_id
            for edge_index in range(len(branch.rooms))
            if f"{branch.ref}_{edge_index}" in certified_edges
        )
        expected_band = "upper" if index % 2 == 0 else "lower"
        if branch_witness is None or (
            branch_witness.attachment_room_id != room_ref_ids.get(branch.from_room)
            or branch_witness.room_ids != expected_room_ids
            or branch_witness.connection_ids != expected_connection_ids
            or branch_witness.band != expected_band
            or branch_witness.band_index != index // 2 + 1
        ):
            reject(
                "certificate.branch_witness_mismatch",
                f"/branches/{index}",
                expected_room_ids,
                "recompute the ordered attached branch path and band",
            )
    if set(branch_by_ref) != {item.ref for item in plan.branches}:
        reject(
            "certificate.branch_count_mismatch",
            "/branches",
            tuple(item.attachment_room_id for item in certificate.branches),
            "record exactly one witness per declared branch",
        )

    loop_by_ref = {item.ref: item for item in certificate.loops}
    expected_embedding_ids = tuple(
        room_ref_ids.get(ref, "")
        for ref in (
            *plan.critical_path,
            *(room_ref for branch in plan.branches for room_ref in branch.rooms),
        )
    )
    expected_embedding_index = {
        room_id: index for index, room_id in enumerate(expected_embedding_ids)
    }
    tree_refs = {
        ref: value for ref, value in expected_edges.items() if value[0] != "loop"
    }
    for index, loop in enumerate(plan.loops):
        loop_witness = loop_by_ref.get(loop.ref)
        path_refs, path_edge_refs = _tree_path(tree_refs, loop.from_room, loop.to_room)
        expected_cycle_rooms = tuple(room_ref_ids.get(ref, "") for ref in path_refs)
        expected_cycle_edges = tuple(
            certified_edges[ref].connection_id
            for ref in (*path_edge_refs, loop.ref)
            if ref in certified_edges
        )
        if loop_witness is None or (
            loop_witness.from_room_id != room_ref_ids.get(loop.from_room)
            or loop_witness.to_room_id != room_ref_ids.get(loop.to_room)
            or loop_witness.connection_id
            != getattr(certified_edges.get(loop.ref), "connection_id", None)
            or loop_witness.cycle_room_ids != expected_cycle_rooms
            or loop_witness.cycle_connection_ids != expected_cycle_edges
            or loop_witness.interval_start
            != min(
                expected_embedding_index.get(room_ref_ids.get(loop.from_room, ""), -1),
                expected_embedding_index.get(room_ref_ids.get(loop.to_room, ""), -1),
            )
            or loop_witness.interval_end
            != max(
                expected_embedding_index.get(room_ref_ids.get(loop.from_room, ""), -1),
                expected_embedding_index.get(room_ref_ids.get(loop.to_room, ""), -1),
            )
            or loop_witness.band != "loop"
            or loop_witness.band_index != 1
            or loop_witness.secret != loop.secret
        ):
            reject(
                "certificate.loop_witness_mismatch",
                f"/loops/{index}",
                expected_cycle_rooms,
                "recompute the simple-cycle witness from the tree path and loop edge",
            )
    if set(loop_by_ref) != {item.ref for item in plan.loops}:
        reject(
            "certificate.loop_count_mismatch",
            "/loops",
            tuple(item.connection_id for item in certificate.loops),
            "record exactly one witness per declared loop",
        )

    entrance_id = room_ref_ids.get(plan.critical_path[0], "")
    full_reachable = tuple(sorted(_reachable(adjacency, entrance_id)))
    public_adjacency = _topology_adjacency(topology, public_only=True)
    public_reachable = tuple(sorted(_reachable(public_adjacency, entrance_id)))
    if certificate.full_reachable_room_ids != full_reachable:
        reject(
            "certificate.full_reachability_mismatch",
            "/full_reachable_room_ids",
            full_reachable,
            "recompute reachability over all DM topology edges",
        )
    if certificate.public_reachable_room_ids != public_reachable:
        reject(
            "certificate.public_reachability_mismatch",
            "/public_reachable_room_ids",
            public_reachable,
            "recompute reachability without secret edges",
        )

    gate_witnesses = {item.gate_id: item for item in certificate.gates}
    resource_rooms = {
        **{item.id: item.located_in_room_id for item in topology.keys},
        **{item.id: item.located_in_room_id for item in topology.clues},
    }
    for gate in topology.gates:
        gate_witness = gate_witnesses.get(gate.id)
        dependency = gate.requires_all[0] if gate.requires_all else None
        blocked = gate.blocks_connection_ids[0]
        before_graph = _topology_adjacency(
            topology,
            public_only=True,
            excluded_connection_ids={blocked},
        )
        before = tuple(sorted(_reachable(before_graph, entrance_id)))
        dependency_id = None if dependency is None else dependency.target_id
        dependency_room_id = resource_rooms.get(dependency_id or "")
        if (
            gate_witness is None
            or dependency_room_id is None
            or (
                gate_witness.dependency_id != dependency_id
                or gate_witness.dependency_room_id != dependency_room_id
                or gate_witness.blocked_connection_id != blocked
                or gate_witness.reachable_before_gate_room_ids != before
                or gate_witness.opened_order != 1
                or dependency_room_id not in before
            )
        ):
            reject(
                "certificate.gate_reachability_mismatch",
                "/gates",
                (gate.id, blocked),
                "recompute dependency reachability with the gate closed",
            )
    if set(gate_witnesses) != {item.id for item in topology.gates}:
        reject(
            "certificate.gate_count_mismatch",
            "/gates",
            tuple(gate_witnesses),
            "record exactly one reachability witness per gate",
        )

    room_by_ref = {item.ref: item for item in plan.rooms}
    demands = {item.room_id: item for item in certificate.room_demands}
    feature_room_ids = {item.room_id for item in mechanics.room_features}
    trap_room_ids = {item.room_id for item in mechanics.room_traps}
    for ref, room_id in room_ref_ids.items():
        room = room_by_ref.get(ref)
        demand = demands.get(room_id)
        if room is None or demand is None:
            reject(
                "certificate.room_demand_missing",
                "/room_demands",
                (room_id,),
                "record one demand witness per room",
            )
            continue
        degree = len(adjacency.get(room_id, set()))
        base = {
            RoomSizeBand.SMALL: 9,
            RoomSizeBand.MEDIUM: 25,
            RoomSizeBand.LARGE: 64,
        }[room.size]
        encounter = (
            0
            if room.encounter is None
            else 16
            if room.encounter.value in {"combat", "ambush"}
            else 9
        )
        feature = 4 if room_id in feature_room_ids else 0
        trap = 1 if room_id in trap_room_ids else 0
        expected_demand = (
            degree,
            degree,
            1,
            max(0, degree - 1),
            degree + max(0, degree - 1),
            base,
            encounter,
            feature,
            trap,
            max(base, encounter + feature + trap + 4),
        )
        actual_demand = (
            demand.degree,
            demand.required_ports,
            demand.opening_width_cells,
            demand.separation_clearance_cells,
            demand.minimum_boundary_cells,
            demand.base_interior_cells,
            demand.encounter_cells,
            demand.feature_cells,
            demand.trap_cells,
            demand.required_interior_cells,
        )
        if actual_demand != expected_demand:
            reject(
                "certificate.room_demand_mismatch",
                f"/room_demands/{ref}",
                (room_id,),
                "recompute degree, port, and interior demand",
            )
    if set(demands) != set(topology_rooms):
        reject(
            "certificate.room_demand_count_mismatch",
            "/room_demands",
            tuple(demands),
            "record exactly one demand witness per topology room",
        )

    embedding = {item.room_id: item for item in certificate.embedding_rooms}
    for index, ref in enumerate(plan.critical_path):
        embedding_room = embedding.get(room_ref_ids.get(ref, ""))
        if embedding_room is None or (
            embedding_room.region != "backbone"
            or embedding_room.order != index
            or embedding_room.band != "backbone"
            or embedding_room.band_index != 0
        ):
            reject(
                "certificate.embedding_mismatch",
                "/embedding_rooms",
                (room_ref_ids.get(ref, ""),),
                "place critical-path rooms in ordered backbone columns",
            )
    for branch_index, branch in enumerate(plan.branches):
        band = "upper" if branch_index % 2 == 0 else "lower"
        for room_index, ref in enumerate(branch.rooms):
            embedding_room = embedding.get(room_ref_ids.get(ref, ""))
            if embedding_room is None or (
                embedding_room.region != "branch"
                or embedding_room.order != room_index
                or embedding_room.band != band
                or embedding_room.band_index != branch_index // 2 + 1
            ):
                reject(
                    "certificate.embedding_mismatch",
                    "/embedding_rooms",
                    (room_ref_ids.get(ref, ""),),
                    "place branch rooms in their dedicated ordered band",
                )
    if set(embedding) != set(topology_rooms):
        reject(
            "certificate.embedding_room_count_mismatch",
            "/embedding_rooms",
            tuple(embedding),
            "embed every topology room exactly once",
        )
    if certificate.required_bands != 1 + len(plan.branches) + len(plan.loops):
        reject(
            "certificate.required_bands_mismatch",
            "/required_bands",
            (topology.id,),
            "reserve one backbone and one band per branch and loop",
        )

    expected_grammar_steps: list[tuple[str, str, tuple[str, ...], tuple[str, ...]]] = [
        (
            "critical_path",
            "critical_path",
            tuple(room_ref_ids.get(ref, "") for ref in plan.critical_path),
            critical_edge_ids,
        )
    ]
    expected_grammar_steps.extend(
        (
            "branch",
            branch.ref,
            (
                room_ref_ids.get(branch.from_room, ""),
                *(room_ref_ids.get(ref, "") for ref in branch.rooms),
            ),
            tuple(
                certified_edges[f"{branch.ref}_{index}"].connection_id
                for index in range(len(branch.rooms))
                if f"{branch.ref}_{index}" in certified_edges
            ),
        )
        for branch in plan.branches
    )
    expected_grammar_steps.extend(
        (
            "loop",
            loop.ref,
            (
                room_ref_ids.get(loop.from_room, ""),
                room_ref_ids.get(loop.to_room, ""),
            ),
            (
                (certified_edges[loop.ref].connection_id,)
                if loop.ref in certified_edges
                else ()
            ),
        )
        for loop in plan.loops
    )
    actual_grammar_steps = [
        (step.kind, step.ref, step.room_ids, step.connection_ids)
        for step in certificate.grammar_steps
    ]
    if actual_grammar_steps != expected_grammar_steps:
        reject(
            "certificate.grammar_steps_mismatch",
            "/grammar_steps",
            (topology.id,),
            "record the exact critical-path, branch, and loop productions",
        )

    ordered = tuple(
        sorted(diagnostics, key=lambda item: (item.code, item.path, item.affected_ids))
    )
    return TopologyCertificateValidationReport(
        certificate_version=TOPOLOGY_CERTIFICATE_VERSION,
        topology_id=topology.id,
        valid=not ordered,
        diagnostics=ordered,
    )


def _expected_edges(
    plan: DungeonPlan,
) -> dict[str, tuple[str, str, str, bool]]:
    edges: dict[str, tuple[str, str, str, bool]] = {}
    for index, (left, right) in enumerate(
        zip(plan.critical_path, plan.critical_path[1:], strict=False)
    ):
        edges[f"critical_{index}"] = ("critical_path", left, right, False)
    for branch in plan.branches:
        previous = branch.from_room
        for index, room in enumerate(branch.rooms):
            edges[f"{branch.ref}_{index}"] = (
                "branch",
                previous,
                room,
                False,
            )
            previous = room
    for loop in plan.loops:
        edges[loop.ref] = (
            "loop",
            loop.from_room,
            loop.to_room,
            loop.secret,
        )
    return edges


def _topology_adjacency(
    topology: DungeonTopology,
    *,
    public_only: bool = False,
    excluded_connection_ids: set[str] | None = None,
) -> dict[str, set[str]]:
    adjacency: dict[str, set[str]] = {room.id: set() for room in topology.rooms}
    excluded = excluded_connection_ids or set()
    for connection in topology.connections:
        if connection.id in excluded:
            continue
        if public_only and connection.visibility is Visibility.DM_ONLY:
            continue
        if (
            connection.from_room_id in adjacency
            and connection.to_room_id in adjacency
            and connection.from_room_id != connection.to_room_id
        ):
            adjacency[connection.from_room_id].add(connection.to_room_id)
            adjacency[connection.to_room_id].add(connection.from_room_id)
    return adjacency


def _reachable(adjacency: dict[str, set[str]], start: str) -> set[str]:
    if start not in adjacency:
        return set()
    seen = {start}
    pending = deque((start,))
    while pending:
        current = pending.popleft()
        for neighbor in sorted(adjacency[current] - seen):
            seen.add(neighbor)
            pending.append(neighbor)
    return seen


def _component_count(adjacency: dict[str, set[str]]) -> int:
    remaining = set(adjacency)
    count = 0
    while remaining:
        reached = _reachable(adjacency, min(remaining))
        remaining -= reached
        count += 1
    return count


def _tree_path(
    edges: dict[str, tuple[str, str, str, bool]], start: str, end: str
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    neighbors: dict[str, list[tuple[str, str]]] = {}
    for edge_ref, (_, left, right, _) in edges.items():
        neighbors.setdefault(left, []).append((right, edge_ref))
        neighbors.setdefault(right, []).append((left, edge_ref))
    pending = deque((start,))
    previous: dict[str, tuple[str, str] | None] = {start: None}
    while pending:
        current = pending.popleft()
        for neighbor, edge_ref in sorted(neighbors.get(current, ())):
            if neighbor not in previous:
                previous[neighbor] = (current, edge_ref)
                pending.append(neighbor)
    rooms = [end]
    edge_refs: list[str] = []
    while rooms[-1] != start:
        step = previous[rooms[-1]]
        assert step is not None
        prior, edge_ref = step
        rooms.append(prior)
        edge_refs.append(edge_ref)
    rooms.reverse()
    edge_refs.reverse()
    return tuple(rooms), tuple(edge_refs)


def _hash_contract(contract: ContractModel) -> str:
    payload = contract.model_dump(mode="json", round_trip=True)
    encoded = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return sha256(encoded).hexdigest()
