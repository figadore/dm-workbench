"""Focused deterministic topology and gating validation tests."""

from dm_dungeon import DungeonPackage, to_canonical_json, validate_topology
from dm_dungeon.contracts import (
    GateDependency,
    GateDependencyKind,
    Visibility,
)
from dm_dungeon.contracts.topology import DungeonTopology
from dm_dungeon.validation import (
    DiagnosticSeverity,
    TopologyDiagnosticCode,
)


def diagnostic_codes(topology: DungeonTopology) -> set[TopologyDiagnosticCode]:
    return {item.code for item in validate_topology(topology).diagnostics}


def test_synthetic_topology_is_valid_and_report_is_deterministic(
    synthetic_package: DungeonPackage,
) -> None:
    first = validate_topology(synthetic_package.topology)
    second = validate_topology(synthetic_package.topology)

    assert first.valid is True
    assert first.diagnostics == ()
    assert first == second
    assert to_canonical_json(first) == to_canonical_json(second)


def test_required_rooms_must_connect_entrance_to_exit(
    synthetic_package: DungeonPackage,
) -> None:
    topology = synthetic_package.topology
    connections = tuple(
        item for item in topology.connections if item.id != "connection_sanctum_exit"
    )
    broken = topology.model_copy(update={"connections": connections, "chokepoints": ()})

    codes = diagnostic_codes(broken)

    assert TopologyDiagnosticCode.REQUIRED_ROOM_UNREACHABLE_FROM_ENTRANCE in codes
    assert TopologyDiagnosticCode.REQUIRED_ROOM_UNREACHABLE_FROM_EXIT in codes


def test_requested_loop_and_branch_must_be_realized(
    synthetic_package: DungeonPackage,
) -> None:
    topology = synthetic_package.topology
    without_ladder = topology.model_copy(
        update={
            "connections": tuple(
                item
                for item in topology.connections
                if item.id != "connection_secret_ladder"
            ),
            "secret_bypasses": (),
        }
    )
    without_stairs = topology.model_copy(
        update={
            "connections": tuple(
                item
                for item in topology.connections
                if item.id != "connection_archive_stairs"
            )
        }
    )

    assert TopologyDiagnosticCode.LOOP_NOT_REALIZED in diagnostic_codes(without_ladder)
    assert TopologyDiagnosticCode.BRANCH_NOT_REALIZED in diagnostic_codes(
        without_stairs
    )


def test_requested_chokepoint_must_disconnect_target_regions(
    synthetic_package: DungeonPackage,
) -> None:
    topology = synthetic_package.topology
    exit_connection = next(
        item for item in topology.connections if item.id == "connection_sanctum_exit"
    )
    alternate = exit_connection.model_copy(
        update={"id": "connection_sanctum_exit_alternate"}
    )
    broken = topology.model_copy(
        update={"connections": (*topology.connections, alternate)}
    )

    assert TopologyDiagnosticCode.CHOKEPOINT_NOT_REALIZED in diagnostic_codes(broken)


def test_secret_bypass_must_be_hidden_and_avoid_blocked_connections(
    synthetic_package: DungeonPackage,
) -> None:
    topology = synthetic_package.topology
    bypass = topology.secret_bypasses[0].model_copy(
        update={"connection_ids": ("connection_sanctum_lock",)}
    )
    broken = topology.model_copy(update={"secret_bypasses": (bypass,)})

    codes = diagnostic_codes(broken)

    assert TopologyDiagnosticCode.SECRET_BYPASS_NOT_SECRET in codes
    assert TopologyDiagnosticCode.SECRET_BYPASS_NOT_REALIZED in codes


def test_floor_transition_must_match_distinct_endpoint_floors(
    synthetic_package: DungeonPackage,
) -> None:
    topology = synthetic_package.topology
    transition = next(
        item for item in topology.connections if item.id == "connection_archive_stairs"
    )
    broken_transition = transition.model_copy(update={"from_floor_id": "floor_lower"})
    broken = topology.model_copy(
        update={
            "connections": tuple(
                broken_transition if item.id == transition.id else item
                for item in topology.connections
            )
        }
    )

    assert TopologyDiagnosticCode.FLOOR_TRANSITION_INVALID in diagnostic_codes(broken)


def test_key_behind_its_gate_is_unresolvable(
    synthetic_package: DungeonPackage,
) -> None:
    topology = synthetic_package.topology
    key = topology.keys[0].model_copy(update={"located_in_room_id": "room_sanctum"})
    broken = topology.model_copy(
        update={
            "keys": (key,),
            "connections": tuple(
                item
                for item in topology.connections
                if item.id != "connection_secret_ladder"
            ),
            "loops": (),
            "secret_bypasses": (),
        }
    )

    codes = diagnostic_codes(broken)

    assert TopologyDiagnosticCode.GATE_UNRESOLVABLE in codes
    assert TopologyDiagnosticCode.REQUIRED_ROOM_GATE_BLOCKED in codes


def test_gate_dependency_cycle_is_reported_with_repair_context(
    synthetic_package: DungeonPackage,
) -> None:
    topology = synthetic_package.topology
    gate = topology.gates[0]
    cyclic_gate = gate.model_copy(
        update={
            "requires_all": (
                GateDependency(
                    kind=GateDependencyKind.GATE,
                    target_id=gate.id,
                ),
            )
        }
    )
    broken = topology.model_copy(update={"gates": (cyclic_gate,)})

    report = validate_topology(broken)
    diagnostic = next(
        item
        for item in report.diagnostics
        if item.code is TopologyDiagnosticCode.GATE_DEPENDENCY_CYCLE
    )

    assert report.valid is False
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.affected_ids == ("gate_sanctum",)
    assert diagnostic.repair_hint


def test_unknown_references_return_diagnostics_instead_of_raising(
    synthetic_package: DungeonPackage,
) -> None:
    topology = synthetic_package.topology
    key = topology.keys[0].model_copy(
        update={
            "located_in_room_id": "room_missing",
            "visibility": Visibility.DM_ONLY,
        }
    )
    broken = topology.model_copy(update={"keys": (key,)})

    report = validate_topology(broken)

    assert report.valid is False
    assert TopologyDiagnosticCode.UNKNOWN_ROOM_REFERENCE in {
        item.code for item in report.diagnostics
    }
