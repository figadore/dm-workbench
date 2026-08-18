"""V2 compact-design compiler contracts."""

import json
from copy import deepcopy

import pytest
from pydantic import ValidationError

from dm_dungeon import (
    DungeonDesignSpecV2,
    compile_dungeon_design_v2,
    load_dungeon_design_v2_json,
    to_canonical_json,
    validate_topology,
)


def _minimal_design() -> dict[str, object]:
    return {
        "schema_version": "2.0.0",
        "title": "Salt Cellar",
        "premise": "A tide-worn cache protects a sealed ledger.",
        "themes": ["salt", "tide"],
        "floors": [
            {
                "local_ref": "cellar",
                "name": "Salt Cellar",
                "floor_scale": "small",
                "rooms": [
                    {
                        "local_ref": "entry",
                        "name": "Wet Steps",
                        "role": "entrance",
                        "room_size": "small",
                    },
                    {
                        "local_ref": "vault",
                        "name": "Ledger Vault",
                        "role": "objective",
                        "room_size": "medium",
                    },
                ],
            }
        ],
        "connections": [
            {
                "local_ref": "entry-vault",
                "from_ref": "entry",
                "to_ref": "vault",
                "passage": "door",
            }
        ],
        "objectives": [{"room_ref": "vault", "kind": "final_objective"}],
        "dependencies": [],
    }


def _spec(payload: dict[str, object]) -> DungeonDesignSpecV2:
    return DungeonDesignSpecV2.model_validate_json(json.dumps(payload))


def test_compiler_generates_exact_kernel_intent_without_model_ids_or_counts() -> None:
    result = compile_dungeon_design_v2(_spec(_minimal_design()))

    assert result.accepted is True
    assert result.compiler_version == "dungeon-design-v2-compiler-2"
    assert result.brief is not None
    assert result.topology is not None
    assert result.brief.floor_count == 1
    assert result.brief.target_room_count == 2
    assert result.floor_bounds[0].width_cells == 28
    assert validate_topology(result.topology).valid is True
    assert all(component.id.startswith("v2-") for component in result.topology.rooms)


def test_compiler_replay_is_canonical_and_ids_ignore_prose_and_array_order() -> None:
    original = _minimal_design()
    altered = deepcopy(original)
    altered["title"] = "Renamed Salt Cellar"
    floor = altered["floors"][0]
    assert isinstance(floor, dict)
    rooms = floor["rooms"]
    assert isinstance(rooms, list)
    rooms.reverse()

    first = compile_dungeon_design_v2(_spec(original))
    second = compile_dungeon_design_v2(_spec(altered))

    assert first.accepted and second.accepted
    assert first.topology is not None and second.topology is not None
    assert {room.id for room in first.topology.rooms} == {
        room.id for room in second.topology.rooms
    }
    assert to_canonical_json(first.topology) == to_canonical_json(second.topology)


def test_compiler_rejects_duplicate_local_refs_with_bounded_path_diagnostic() -> None:
    payload = _minimal_design()
    floor = payload["floors"][0]
    assert isinstance(floor, dict)
    rooms = floor["rooms"]
    assert isinstance(rooms, list)
    rooms[1]["local_ref"] = "entry"

    result = compile_dungeon_design_v2(_spec(payload))

    assert result.accepted is False
    assert result.diagnostics[0].code == "design.duplicate_local_ref"
    assert result.diagnostics[0].path == "/floors/0/rooms/1/local_ref"


def test_compiler_hides_rooms_reachable_only_through_secret_access() -> None:
    payload = _minimal_design()
    floor = payload["floors"][0]
    assert isinstance(floor, dict)
    rooms = floor["rooms"]
    assert isinstance(rooms, list)
    rooms.insert(
        1,
        {
            "local_ref": "hidden",
            "name": "Hidden Annex",
            "role": "exploration",
            "optional": True,
        },
    )
    connections = payload["connections"]
    assert isinstance(connections, list)
    connections.append(
        {
            "local_ref": "entry-hidden",
            "from_ref": "entry",
            "to_ref": "hidden",
            "passage": "door",
            "concealment": "secret",
        }
    )

    result = compile_dungeon_design_v2(_spec(payload))

    assert result.accepted and result.topology is not None
    rooms_by_name = {room.name: room for room in result.topology.rooms}
    assert rooms_by_name["Hidden Annex"].visibility.value == "dm_only"
    assert rooms_by_name["Ledger Vault"].visibility.value == "player_safe"
    secret = next(
        connection
        for connection in result.topology.connections
        if connection.id.startswith("v2-connection-")
        and connection.visibility.value == "dm_only"
    )
    assert secret.visibility.value == "dm_only"
    assert validate_topology(result.topology).valid is True


def test_compiler_preserves_one_sided_hidden_ladder_intent() -> None:
    payload = _minimal_design()
    payload["floors"].append(
        {
            "local_ref": "lower",
            "name": "Lower Archive",
            "rooms": [
                {"local_ref": "landing", "name": "Landing", "role": "exploration"}
            ],
        }
    )
    connections = payload["connections"]
    assert isinstance(connections, list)
    connections.append(
        {
            "local_ref": "hidden-ladder",
            "from_ref": "entry",
            "to_ref": "landing",
            "passage": "ladder",
            "from_hidden": True,
            "to_hidden": False,
        }
    )

    result = compile_dungeon_design_v2(_spec(payload))

    assert result.accepted and result.topology is not None
    ladder = next(item for item in result.topology.connections if item.from_hidden)
    assert ladder.from_hidden is True
    assert ladder.to_hidden is False


def test_compiler_derives_dm_only_gate_and_key_from_relative_intent() -> None:
    payload = _minimal_design()
    connection = payload["connections"][0]
    assert isinstance(connection, dict)
    connection["barrier"] = "locked"
    payload["dependencies"] = [
        {
            "local_ref": "vault-key",
            "kind": "key",
            "connection_ref": "entry-vault",
            "located_in_room_ref": "entry",
            "name": "Salt Key",
        }
    ]

    result = compile_dungeon_design_v2(_spec(payload))

    assert result.accepted and result.topology is not None
    assert result.topology.gates[0].visibility.value == "dm_only"
    assert result.topology.keys[0].visibility.value == "dm_only"


def test_compiler_rejects_multiple_dependencies_for_one_barrier() -> None:
    payload = _minimal_design()
    connection = payload["connections"][0]
    assert isinstance(connection, dict)
    connection["barrier"] = "locked"
    payload["dependencies"] = [
        {
            "local_ref": local_ref,
            "kind": "key",
            "connection_ref": "entry-vault",
            "located_in_room_ref": "entry",
            "name": name,
        }
        for local_ref, name in (
            ("first-key", "First Key"),
            ("second-key", "Second Key"),
        )
    ]

    result = compile_dungeon_design_v2(_spec(payload))

    assert result.accepted is False
    assert any(
        item.code == "design.duplicate_dependency_target" for item in result.diagnostics
    )


def test_design_schema_round_trip_and_unknown_version_fail() -> None:
    spec = _spec(_minimal_design())
    assert load_dungeon_design_v2_json(to_canonical_json(spec)) == spec

    payload = _minimal_design()
    payload["schema_version"] = "99.0.0"
    with pytest.raises(
        ValueError, match="Unsupported DungeonDesignSpecV2 schema version"
    ):
        load_dungeon_design_v2_json(json.dumps(payload))

    payload = _minimal_design()
    payload["seed"] = 2
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        _spec(payload)
