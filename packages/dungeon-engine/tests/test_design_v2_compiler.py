"""V2 compact-design compiler contracts."""

import json
from copy import deepcopy

import pytest
from pydantic import ValidationError

from dm_dungeon import (
    DungeonDesignSpecV2,
    DungeonPackage,
    compile_dungeon_design_v2,
    load_dungeon_design_v2_json,
    to_canonical_json,
    validate_topology,
)
from dm_dungeon.layout import LayoutRequest, generate_layout
from dm_dungeon.rendering import RenderAudience, SvgRenderRequest, render_svg


def _minimal_design() -> dict[str, object]:
    return {
        "schema_version": "2.1.0",
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


def _generate(payload: dict[str, object]) -> DungeonPackage:
    compiled = compile_dungeon_design_v2(_spec(payload))
    assert compiled.accepted
    assert compiled.brief is not None
    assert compiled.topology is not None
    generated = generate_layout(
        LayoutRequest(
            schema_version="1.0.0",
            package_id="directional-concealment-test",
            brief=compiled.brief,
            topology=compiled.topology,
            seed=1042,
            generator_version="orthogonal-v2",
            floor_bounds=compiled.floor_bounds,
        )
    )
    assert generated.package is not None
    return generated.package


def _render(package: DungeonPackage, floor_id: str, audience: RenderAudience) -> str:
    result = render_svg(
        package,
        SvgRenderRequest(
            schema_version="1.0.0",
            package_id=package.id,
            floor_id=floor_id,
            audience=audience,
            pixels_per_cell=20,
        ),
    )
    assert result.svg is not None
    return result.svg


def test_compiler_generates_exact_kernel_intent_without_model_ids_or_counts() -> None:
    result = compile_dungeon_design_v2(_spec(_minimal_design()))

    assert result.accepted is True
    assert result.compiler_version == "dungeon-design-v2-compiler-3"
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


def test_one_sided_hidden_door_is_safe_and_visible_from_its_open_side() -> None:
    payload = _minimal_design()
    connection = payload["connections"][0]
    assert isinstance(connection, dict)
    connection["to_hidden"] = True

    package = _generate(payload)

    door = package.doors[0]
    floor_id = package.floors[0].id
    dm_svg = _render(package, floor_id, RenderAudience.DM)
    player_svg = _render(package, floor_id, RenderAudience.PLAYER)
    assert door.from_hidden is False
    assert door.to_hidden is True
    assert f'data-component-id="{door.id}"' in player_svg
    assert 'data-door-type="normal"' in player_svg
    assert 'data-door-type="secret"' not in player_svg
    assert "door-secret-symbol" not in player_svg
    assert f'data-component-id="{door.id}"' in dm_svg
    assert 'data-door-type="secret"' in dm_svg
    assert "door-secret-symbol" in dm_svg


@pytest.mark.parametrize(
    ("hidden_passage", "public_passage"),
    (("ladder", "stairs"), ("stairs", "ladder")),
)
def test_one_sided_hidden_vertical_link_renders_only_its_publishable_endpoint(
    hidden_passage: str,
    public_passage: str,
) -> None:
    payload = _minimal_design()
    upper = payload["floors"][0]
    assert isinstance(upper, dict)
    upper_rooms = upper["rooms"]
    assert isinstance(upper_rooms, list)
    upper["rooms"] = [upper_rooms[0]]
    payload["floors"].append(
        {
            "local_ref": "lower",
            "name": "Lower Archive",
            "rooms": [
                {"local_ref": "landing", "name": "Landing", "role": "exploration"},
                {"local_ref": "vault", "name": "Vault", "role": "objective"},
            ],
        }
    )
    payload["connections"] = [
        {
            "local_ref": "public-stairs",
            "from_ref": "entry",
            "to_ref": "landing",
            "passage": public_passage,
        },
        {
            "local_ref": "hidden-descent",
            "from_ref": "entry",
            "to_ref": "landing",
            "passage": hidden_passage,
            "from_hidden": True,
            "to_hidden": False,
        },
        {
            "local_ref": "landing-vault",
            "from_ref": "landing",
            "to_ref": "vault",
        },
    ]

    package = _generate(payload)

    hidden_link = next(
        item for item in package.vertical_links if item.link_type == hidden_passage
    )
    upper_floor = next(item for item in package.floors if item.name == "Salt Cellar")
    lower_floor = next(item for item in package.floors if item.name == "Lower Archive")
    upper_player = _render(package, upper_floor.id, RenderAudience.PLAYER)
    lower_player = _render(package, lower_floor.id, RenderAudience.PLAYER)
    upper_dm = _render(package, upper_floor.id, RenderAudience.DM)
    lower_dm = _render(package, lower_floor.id, RenderAudience.DM)
    assert [item.visibility.value for item in hidden_link.endpoints] == [
        "dm_only",
        "player_safe",
    ]
    upper_endpoint, lower_endpoint = hidden_link.endpoints
    upper_component_id = upper_endpoint.stair_id or hidden_link.id
    lower_component_id = lower_endpoint.stair_id or hidden_link.id
    upper_component = f'data-component-id="{upper_component_id}"'
    lower_component = f'data-component-id="{lower_component_id}"'
    assert upper_component not in upper_player
    assert lower_component in lower_player
    assert upper_component in upper_dm
    assert lower_component in lower_dm


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
