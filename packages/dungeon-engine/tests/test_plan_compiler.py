"""Tier A plan, topology-construction, and certificate tests."""

import json
from copy import deepcopy

import pytest
from pydantic import ValidationError

from dm_dungeon import (
    DungeonPlan,
    compile_dungeon_plan,
    load_dungeon_plan_json,
    to_canonical_json,
    validate_topology,
    validate_topology_certificate,
)


def minimal_plan() -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "title": "Salt Cellar",
        "premise": "A tide-worn archive protects a sealed ledger.",
        "themes": ["salt", "tide"],
        "rooms": [
            {
                "ref": "entry",
                "name": "Wet Steps",
                "role": "entrance",
                "size": "small",
                "purpose": "Establish the flooded descent.",
            },
            {
                "ref": "stacks",
                "name": "Drowned Stacks",
                "role": "exploration",
                "purpose": "Reveal the archive's history.",
            },
            {
                "ref": "gallery",
                "name": "Salt Gallery",
                "role": "exploration",
                "purpose": "Foreshadow the sealed ledger.",
            },
            {
                "ref": "vault",
                "name": "Ledger Vault",
                "role": "objective",
                "purpose": "Hold the final objective.",
            },
        ],
        "critical_path": ["entry", "stacks", "gallery", "vault"],
        "room_contents": [{"room_ref": "vault", "objective": "Sealed Ledger"}],
    }


def rich_plan() -> dict[str, object]:
    payload = minimal_plan()
    rooms = payload["rooms"]
    assert isinstance(rooms, list)
    rooms.insert(
        3,
        {
            "ref": "workshop",
            "name": "Lens Workshop",
            "role": "optional",
            "size": "small",
            "purpose": "Hold the brass lens key and a risky bypass.",
            "encounter": "exploration",
        },
    )
    payload["branches"] = [
        {"ref": "workshop_branch", "from_room": "stacks", "rooms": ["workshop"]}
    ]
    payload["loops"] = [
        {
            "ref": "workshop_bypass",
            "from_room": "workshop",
            "to_room": "vault",
            "secret": True,
        }
    ]
    payload["gates"] = [
        {
            "ref": "vault_gate",
            "between_rooms": ["gallery", "vault"],
            "kind": "locked",
            "dependency_kind": "key",
            "dependency_room": "workshop",
            "dependency_name": "Brass Lens Key",
        }
    ]
    payload["room_contents"] = [
        {
            "room_ref": "stacks",
            "trap": {
                "name": "Collapsing Shelves",
                "trigger": "Disturb the chained folios.",
                "effect": "Shelves collapse into the aisle.",
            },
            "feature": {
                "kind": "furniture",
                "name": "Chained Shelves",
                "description": "Salt-crusted shelves divide the chamber.",
            },
        },
        {"room_ref": "vault", "objective": "Sealed Ledger"},
    ]
    return payload


def plan(payload: dict[str, object]) -> DungeonPlan:
    return DungeonPlan.model_validate_json(json.dumps(payload))


def test_compiler_constructs_connected_critical_path_and_valid_certificate() -> None:
    source = plan(minimal_plan())

    result = compile_dungeon_plan(source)

    assert result.accepted
    assert result.compiler_version == "dungeon-plan-compiler-v1"
    assert result.topology is not None
    assert result.certificate is not None
    assert result.mechanics_plan is not None
    assert len(result.topology.rooms) == 4
    assert len(result.topology.connections) == 3
    assert result.certificate.component_count == 1
    assert result.certificate.cycle_rank == 0
    assert result.certificate.critical_path.room_ids[0] == next(
        room.id for room in result.topology.rooms if room.role.value == "entrance"
    )
    assert validate_topology(result.topology).valid
    assert validate_topology_certificate(
        source, result.topology, result.mechanics_plan, result.certificate
    ).valid


def test_branch_loop_gate_secret_and_demand_witnesses_are_recomputed() -> None:
    source = plan(rich_plan())

    result = compile_dungeon_plan(source)

    assert result.accepted
    assert result.topology is not None
    assert result.certificate is not None
    assert result.mechanics_plan is not None
    certificate = result.certificate
    assert certificate.room_count == 5
    assert certificate.connection_count == 5
    assert certificate.cycle_rank == 1
    assert len(certificate.branches) == 1
    assert certificate.branches[0].band == "upper"
    assert len(certificate.loops) == 1
    assert certificate.loops[0].secret
    assert len(certificate.loops[0].cycle_room_ids) == 4
    assert len(certificate.gates) == 1
    assert certificate.gates[0].dependency_room_id in (
        certificate.gates[0].reachable_before_gate_room_ids
    )
    assert len(result.topology.secret_bypasses) == 1
    assert len(certificate.full_reachable_room_ids) == 5
    assert len(certificate.public_reachable_room_ids) == 5
    assert certificate.required_bands == 3
    assert len(certificate.room_ports) == certificate.room_count
    assert len(certificate.connection_channels) == certificate.connection_count
    assert {item.kind for item in certificate.connection_channels} == {
        "backbone",
        "branch",
        "loop",
    }
    stacks_id = next(item.room_id for item in certificate.rooms if item.ref == "stacks")
    demand = next(
        item for item in certificate.room_demands if item.room_id == stacks_id
    )
    assert demand.degree == demand.required_ports == 3
    assert demand.feature_cells == 4
    assert demand.trap_cells == 1
    assert validate_topology(result.topology).valid
    assert validate_topology_certificate(
        source, result.topology, result.mechanics_plan, certificate
    ).valid


def test_certificate_validator_rejects_mutated_independent_claims() -> None:
    source = plan(rich_plan())
    result = compile_dungeon_plan(source)
    assert result.topology is not None
    assert result.certificate is not None
    assert result.mechanics_plan is not None
    demand = result.certificate.room_demands[0]
    ports = result.certificate.room_ports[0]
    channel = result.certificate.connection_channels[0]
    mutated = result.certificate.model_copy(
        update={
            "cycle_rank": 0,
            "room_demands": (
                demand.model_copy(update={"required_ports": demand.required_ports + 1}),
                *result.certificate.room_demands[1:],
            ),
            "room_ports": (
                ports.model_copy(update={"north_connection_ids": ()}),
                *result.certificate.room_ports[1:],
            ),
            "connection_channels": (
                channel.model_copy(update={"band_index": channel.band_index + 1}),
                *result.certificate.connection_channels[1:],
            ),
        }
    )

    report = validate_topology_certificate(
        source, result.topology, result.mechanics_plan, mutated
    )

    assert not report.valid
    assert {item.code for item in report.diagnostics} >= {
        "certificate.graph_fact_mismatch",
        "certificate.room_demand_mismatch",
        "certificate.room_port_assignment_mismatch",
        "certificate.connection_channel_mismatch",
    }


def test_compilation_is_canonical_and_server_ids_ignore_prose() -> None:
    original = plan(minimal_plan())
    changed_payload = deepcopy(minimal_plan())
    changed_payload["title"] = "Renamed Salt Cellar"
    rooms = changed_payload["rooms"]
    assert isinstance(rooms, list)
    rooms[1]["purpose"] = "Different synthetic prose."
    changed = plan(changed_payload)

    first = compile_dungeon_plan(original)
    second = compile_dungeon_plan(changed)

    assert first.accepted and second.accepted
    assert first.topology is not None and second.topology is not None
    assert {room.id for room in first.topology.rooms} == {
        room.id for room in second.topology.rooms
    }
    assert {connection.id for connection in first.topology.connections} == {
        connection.id for connection in second.topology.connections
    }
    assert first.input_hash != second.input_hash


@pytest.mark.parametrize(
    ("mutation", "code"),
    (
        (
            lambda value: value["critical_path"].append("stacks"),
            "plan.duplicate_path_room",
        ),
        (
            lambda value: value["critical_path"].remove("gallery"),
            "plan.unassigned_room",
        ),
        (
            lambda value: value.update(
                {
                    "loops": [
                        {
                            "ref": "duplicate_edge",
                            "from_room": "entry",
                            "to_room": "stacks",
                        }
                    ]
                }
            ),
            "plan.duplicate_connection",
        ),
    ),
)
def test_reference_and_cardinality_diagnostics_are_bounded(
    mutation: object, code: str
) -> None:
    payload = minimal_plan()
    assert callable(mutation)
    mutation(payload)

    result = compile_dungeon_plan(plan(payload))

    assert not result.accepted
    assert code in {item.code for item in result.diagnostics}
    assert len(result.diagnostics) <= 8
    assert all(len(item.affected_refs) <= 8 for item in result.diagnostics)


def test_gate_dependency_must_be_publicly_reachable_before_gate() -> None:
    payload = minimal_plan()
    payload["gates"] = [
        {
            "ref": "vault_gate",
            "between_rooms": ["gallery", "vault"],
            "kind": "locked",
            "dependency_kind": "key",
            "dependency_room": "vault",
            "dependency_name": "Impossible Key",
        }
    ]

    result = compile_dungeon_plan(plan(payload))

    assert not result.accepted
    assert result.diagnostics[0].code == "plan.gate_dependency_unreachable"
    assert result.diagnostics[0].path == "/gates/0/dependency_room"


def test_plan_schema_is_bounded_and_has_no_arbitrary_edge_or_geometry_fields() -> None:
    schema = DungeonPlan.model_json_schema(mode="validation")
    root = schema["properties"]

    assert schema["title"] == "DungeonPlan"
    assert root["schema_version"]["const"] == "1.0.0"
    assert root["rooms"]["minItems"] == 4
    assert root["rooms"]["maxItems"] == 8
    assert root["branches"]["maxItems"] == 2
    assert root["loops"]["maxItems"] == 1
    assert root["gates"]["maxItems"] == 1
    assert "connections" not in root
    assert "floors" not in root
    rendered = json.dumps(schema, sort_keys=True)
    for forbidden in ("x", "y", "width_cells", "height_cells", "seed"):
        assert f'"{forbidden}"' not in rendered
    for definition in schema["$defs"].values():
        if definition.get("type") == "object":
            assert definition.get("additionalProperties") is False


def test_plan_schema_round_trip_and_unknown_version_fail() -> None:
    source = plan(minimal_plan())
    assert load_dungeon_plan_json(to_canonical_json(source)) == source

    payload = minimal_plan()
    payload["schema_version"] = "99.0.0"
    with pytest.raises(ValueError, match="Unsupported DungeonPlan schema version"):
        load_dungeon_plan_json(json.dumps(payload))

    payload = minimal_plan()
    payload["seed"] = 2
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        plan(payload)


def test_schema_enforces_tier_a_cardinalities_without_provider_call() -> None:
    payload = minimal_plan()
    rooms = payload["rooms"]
    assert isinstance(rooms, list)
    rooms.pop()
    with pytest.raises(ValidationError, match="rooms"):
        plan(payload)

    payload = minimal_plan()
    payload["loops"] = [
        {"ref": "first", "from_room": "entry", "to_room": "gallery"},
        {"ref": "second", "from_room": "stacks", "to_room": "vault"},
    ]
    with pytest.raises(ValidationError, match="loops"):
        plan(payload)
