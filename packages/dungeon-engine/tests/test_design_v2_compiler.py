"""V2 compact-design compiler contracts."""

import json
from copy import deepcopy

import pytest
from pydantic import ValidationError

from dm_dungeon import (
    DungeonDesignSpecV2,
    DungeonPackage,
    DungeonPackageV2,
    compile_dungeon_design_v2,
    load_dungeon_design_v2_json,
    to_canonical_json,
    validate_geometry,
    validate_topology,
)
from dm_dungeon.contracts import GridPoint
from dm_dungeon.layout import LayoutRequest, generate_layout
from dm_dungeon.rendering import RenderAudience, SvgRenderRequest, render_svg


def _minimal_design() -> dict[str, object]:
    return {
        "schema_version": "2.2.0",
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
    assert result.compiler_version == "dungeon-design-v2-compiler-4"
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
            "from_hidden": True,
            "to_hidden": True,
            "door_mechanics": {"concealed": True, "challenge": "low"},
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
    connection["door_mechanics"] = {"concealed": True, "challenge": "low"}

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
    connection["door_mechanics"] = {"barrier": "locked", "challenge": "low"}
    payload["dependencies"] = [
        {
            "local_ref": "vault-key",
            "kind": "key",
            "target_ref": "entry-vault",
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
    connection["door_mechanics"] = {"barrier": "locked", "challenge": "low"}
    payload["dependencies"] = [
        {
            "local_ref": local_ref,
            "kind": "key",
            "target_ref": "entry-vault",
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


def test_compiler_preserves_composable_door_and_vertical_endpoint_mechanics() -> None:
    payload = _minimal_design()
    payload["tones"] = ["tense"]
    floor = payload["floors"][0]
    assert isinstance(floor, dict)
    rooms = floor["rooms"]
    assert isinstance(rooms, list)
    rooms[0].update(
        {
            "tags": ["wet"],
            "preparation_note": "The wind hides quiet movement.",
            "encounter_slot": "ambush",
        }
    )
    payload["floors"].append(
        {
            "local_ref": "lower",
            "name": "Lower Vault",
            "rooms": [{"local_ref": "lens", "name": "Lens", "role": "puzzle"}],
        }
    )
    payload["connections"] = [
        {
            "local_ref": "study-door",
            "from_ref": "entry",
            "to_ref": "vault",
            "passage": "door",
            "from_hidden": True,
            "door_mechanics": {
                "concealed": True,
                "barrier": "locked",
                "hazard": "trapped",
                "challenge": "moderate",
            },
        },
        {
            "local_ref": "vault-stairs",
            "from_ref": "vault",
            "to_ref": "lens",
            "passage": "stairs",
            "to_hidden": True,
            "endpoint_doors": [
                {
                    "local_ref": "lens-hatch",
                    "endpoint": "to",
                    "kind": "hatch",
                    "mechanics": {
                        "concealed": True,
                        "barrier": "puzzle",
                        "hazard": "trapped",
                        "challenge": "high",
                    },
                }
            ],
        },
    ]
    payload["objectives"] = [{"room_ref": "lens", "kind": "final_objective"}]
    payload["dependencies"] = [
        {
            "local_ref": "study-key",
            "kind": "key",
            "target_ref": "study-door",
            "located_in_room_ref": "entry",
            "name": "Brass Key",
        },
        {
            "local_ref": "lens-clue",
            "kind": "clue",
            "target_ref": "lens-hatch",
            "located_in_room_ref": "vault",
            "name": "Star Chart",
        },
    ]
    payload["traps"] = [
        {
            "local_ref": "vault-glyph",
            "room_ref": "vault",
            "name": "Glyph",
            "trigger": "Touching the lens.",
            "effect": "A thunderous ward sounds.",
            "challenge": "high",
        }
    ]
    payload["puzzles"] = [
        {
            "local_ref": "star-dial",
            "room_ref": "lens",
            "name": "Star Dial",
            "mechanism": "Three rotating rings.",
            "clue_refs": ["lens-clue"],
            "solution": "Align the summer constellation.",
            "consequence": "The hatch releases.",
            "challenge": "moderate",
        }
    ]
    payload["features"] = [
        {
            "local_ref": "fallen-lens",
            "room_ref": "lens",
            "kind": "altar",
            "name": "Fallen Lens",
            "description": "A cracked brass lens fills the chamber.",
        }
    ]
    payload["loops"] = []
    payload["branches"] = []

    result = compile_dungeon_design_v2(_spec(payload))

    assert result.accepted and result.mechanics_plan is not None
    mechanics = {item.endpoint: item for item in result.mechanics_plan.door_mechanics}
    assert mechanics[None].gate_id and mechanics[None].trap_id
    assert mechanics[None].discovery_difficulty == 13
    vertical = mechanics[next(item for item in mechanics if item is not None)]
    assert vertical.gate_id and vertical.trap_id
    assert vertical.discovery_difficulty == vertical.unlock_difficulty == 16
    assert vertical.disable_difficulty == 16
    assert len(result.mechanics_plan.room_traps) == 1
    assert len(result.mechanics_plan.room_puzzles) == 1
    assert len(result.mechanics_plan.room_features) == 1

    assert result.brief is not None and result.topology is not None
    assert {item.id for item in result.topology.gates} == {
        mechanics[None].gate_id,
        vertical.gate_id,
    }
    assert result.topology.keys[0].opens_gate_ids == (mechanics[None].gate_id,)
    assert result.topology.clues[0].supports_gate_ids == (vertical.gate_id,)
    layout = generate_layout(
        LayoutRequest(
            schema_version="1.0.0",
            package_id="mechanics-aware-v2",
            brief=result.brief,
            topology=result.topology,
            seed=1042,
            generator_version="orthogonal-v4",
            mechanics_plan=result.mechanics_plan,
            floor_bounds=result.floor_bounds,
        )
    )
    assert layout.success is True
    assert isinstance(layout.package, DungeonPackageV2)
    package = layout.package
    assert package.doors == ()
    assert len(package.composable_doors) == 1
    door = package.composable_doors[0]
    assert door.id == mechanics[None].id
    assert door.connection_id == mechanics[None].connection_id
    assert door.mechanics.gate_id == mechanics[None].gate_id
    assert door.mechanics.trap_id == mechanics[None].trap_id
    assert len(package.vertical_endpoint_doors) == 1
    assert {marker.id for marker in package.room_mechanic_markers} == {
        item.id
        for item in (
            *result.mechanics_plan.room_traps,
            *result.mechanics_plan.room_puzzles,
            *result.mechanics_plan.room_features,
        )
    }
    markers = {marker.kind.value: marker for marker in package.room_mechanic_markers}
    assert markers["trap"].visibility.value == "dm_only"
    # The lower room is reachable only through a hidden endpoint, so its
    # otherwise physical puzzle/feature markers remain fail-closed too.
    assert markers["puzzle"].visibility.value == "dm_only"
    assert markers["feature"].visibility.value == "dm_only"
    assert (
        len(
            {
                (marker.room_id, marker.position.x, marker.position.y)
                for marker in markers.values()
            }
        )
        == 3
    )
    hatch = package.vertical_endpoint_doors[0]
    assert hatch.id == vertical.id
    assert hatch.kind.value == "hatch"
    assert (
        hatch.position
        == next(
            endpoint
            for link in package.vertical_links
            if link.id == vertical.connection_id
            for endpoint in link.endpoints
            if endpoint.floor_id == hatch.floor_id
        ).position
    )
    dm_svg = _render(package, door.floor_id, RenderAudience.DM)
    player_svg = _render(package, door.floor_id, RenderAudience.PLAYER)
    assert f'data-component-id="{door.id}"' in dm_svg
    assert 'data-door-concealed="true"' in dm_svg
    assert 'data-door-gated="true"' in dm_svg
    assert 'data-door-trapped="true"' in dm_svg
    assert f'data-component-id="{door.id}"' not in player_svg
    trap = markers["trap"]
    puzzle = markers["puzzle"]
    feature = markers["feature"]
    assert f'data-component-id="{trap.id}"' in dm_svg
    assert f'data-component-id="{trap.id}"' not in player_svg
    assert f'data-component-id="{puzzle.id}"' not in player_svg
    assert f'data-component-id="{feature.id}"' not in player_svg

    invalid_marker = trap.model_copy(update={"position": GridPoint(x=0, y=0)})
    invalid_package = package.model_copy(
        update={
            "room_mechanic_markers": (
                invalid_marker,
                *(
                    marker
                    for marker in package.room_mechanic_markers
                    if marker.id != trap.id
                ),
            )
        }
    )
    assert "geometry.room_mechanic_marker_invalid" in {
        item.code.value for item in validate_geometry(invalid_package).diagnostics
    }


@pytest.mark.parametrize(
    ("concealed", "barrier", "hazard"),
    (
        (False, "none", "none"),
        (True, "none", "none"),
        (False, "locked", "none"),
        (False, "puzzle", "none"),
        (False, "none", "trapped"),
        (True, "locked", "none"),
        (True, "puzzle", "none"),
        (True, "none", "trapped"),
        (False, "locked", "trapped"),
        (False, "puzzle", "trapped"),
        (True, "locked", "trapped"),
        (True, "puzzle", "trapped"),
    ),
)
def test_compiler_preserves_every_same_floor_door_mechanics_combination(
    concealed: bool, barrier: str, hazard: str
) -> None:
    payload = _minimal_design()
    connection = payload["connections"][0]
    assert isinstance(connection, dict)
    connection["from_hidden"] = concealed
    connection["door_mechanics"] = {
        "concealed": concealed,
        "barrier": barrier,
        "hazard": hazard,
        **(
            {"challenge": "moderate"}
            if concealed or barrier != "none" or hazard != "none"
            else {}
        ),
    }
    if barrier != "none":
        payload["dependencies"] = [
            {
                "local_ref": "door-dependency",
                "kind": "key" if barrier == "locked" else "clue",
                "target_ref": "entry-vault",
                "located_in_room_ref": "entry",
                "name": "Synthetic Dependency",
            }
        ]

    result = compile_dungeon_design_v2(_spec(payload))

    assert result.accepted and result.mechanics_plan is not None
    mechanics = result.mechanics_plan.door_mechanics[0]
    assert mechanics.endpoint is None
    assert mechanics.concealed is concealed
    assert (mechanics.gate_id is not None) is (barrier != "none")
    assert mechanics.gate_kind.value == barrier
    assert (mechanics.trap_id is not None) is (hazard == "trapped")
    assert (mechanics.discovery_difficulty is not None) is concealed
    assert (mechanics.unlock_difficulty is not None) is (barrier != "none")
    assert (mechanics.disable_difficulty is not None) is (hazard == "trapped")


@pytest.mark.parametrize("passage", ("stairs", "ladder"))
@pytest.mark.parametrize("endpoint", ("from", "to"))
@pytest.mark.parametrize(
    ("concealed", "barrier", "hazard"),
    (
        (False, "none", "none"),
        (True, "none", "none"),
        (False, "locked", "none"),
        (False, "puzzle", "none"),
        (False, "none", "trapped"),
        (True, "locked", "none"),
        (True, "puzzle", "none"),
        (True, "none", "trapped"),
        (False, "locked", "trapped"),
        (False, "puzzle", "trapped"),
        (True, "locked", "trapped"),
        (True, "puzzle", "trapped"),
    ),
)
def test_compiler_preserves_every_vertical_endpoint_mechanics_combination(
    passage: str, endpoint: str, concealed: bool, barrier: str, hazard: str
) -> None:
    payload = _minimal_design()
    upper = payload["floors"][0]
    assert isinstance(upper, dict)
    upper["rooms"] = [{"local_ref": "entry", "name": "Wet Steps", "role": "entrance"}]
    payload["floors"].append(
        {
            "local_ref": "lower",
            "name": "Lower Vault",
            "rooms": [{"local_ref": "vault", "name": "Vault", "role": "objective"}],
        }
    )
    endpoint_mechanics = {
        "concealed": concealed,
        "barrier": barrier,
        "hazard": hazard,
        **(
            {"challenge": "high"}
            if concealed or barrier != "none" or hazard != "none"
            else {}
        ),
    }
    payload["connections"] = [
        {
            "local_ref": "descent",
            "from_ref": "entry",
            "to_ref": "vault",
            "passage": passage,
            f"{endpoint}_hidden": concealed,
            "endpoint_doors": [
                {
                    "local_ref": "descent-hatch",
                    "endpoint": endpoint,
                    "kind": "hatch",
                    "mechanics": endpoint_mechanics,
                }
            ],
        }
    ]
    payload["objectives"] = [{"room_ref": "vault", "kind": "final_objective"}]
    if barrier != "none":
        payload["dependencies"] = [
            {
                "local_ref": "hatch-dependency",
                "kind": "key" if barrier == "locked" else "clue",
                "target_ref": "descent-hatch",
                "located_in_room_ref": "entry",
                "name": "Synthetic Dependency",
            }
        ]

    result = compile_dungeon_design_v2(_spec(payload))

    assert result.accepted and result.mechanics_plan is not None
    mechanics = result.mechanics_plan.door_mechanics[0]
    assert mechanics.endpoint is not None and mechanics.endpoint.value == endpoint
    assert (
        mechanics.endpoint_kind is not None and mechanics.endpoint_kind.value == "hatch"
    )
    assert mechanics.concealed is concealed
    assert (mechanics.gate_id is not None) is (barrier != "none")
    assert mechanics.gate_kind.value == barrier
    assert (mechanics.trap_id is not None) is (hazard == "trapped")
    assert (mechanics.discovery_difficulty is not None) is concealed
    assert (mechanics.unlock_difficulty is not None) is (barrier != "none")
    assert (mechanics.disable_difficulty is not None) is (hazard == "trapped")


def test_mechanics_aware_layout_rejects_a_missing_compiler_plan() -> None:
    result = compile_dungeon_design_v2(_spec(_minimal_design()))
    assert result.accepted and result.brief is not None and result.topology is not None

    layout = generate_layout(
        LayoutRequest(
            schema_version="1.0.0",
            package_id="missing-mechanics-plan",
            brief=result.brief,
            topology=result.topology,
            seed=1042,
            generator_version="orthogonal-v4",
            floor_bounds=result.floor_bounds,
        )
    )

    assert layout.success is False
    assert layout.diagnostics[0].code.value == "layout.mechanics_plan_invalid"


def test_design_contract_rejects_unsupported_connection_mechanics_matrix() -> None:
    payload = _minimal_design()
    connection = payload["connections"][0]
    assert isinstance(connection, dict)
    connection["passage"] = "passage"
    connection["door_mechanics"] = {"barrier": "locked", "challenge": "low"}

    with pytest.raises(ValidationError, match="same-floor passages"):
        _spec(payload)


@pytest.mark.parametrize(
    "field,value",
    (
        ("from_hidden", True),
        ("door_mechanics", {"barrier": "locked", "challenge": "low"}),
        (
            "endpoint_doors",
            [
                {
                    "local_ref": "invalid-endpoint",
                    "endpoint": "from",
                    "kind": "door",
                }
            ],
        ),
    ),
)
def test_design_contract_rejects_all_same_floor_passage_mechanics(
    field: str, value: object
) -> None:
    payload = _minimal_design()
    connection = payload["connections"][0]
    assert isinstance(connection, dict)
    connection["passage"] = "passage"
    connection[field] = value

    with pytest.raises(ValidationError, match="same-floor passages"):
        _spec(payload)


def test_design_contract_rejects_endpoint_doors_on_same_floor_doors() -> None:
    payload = _minimal_design()
    connection = payload["connections"][0]
    assert isinstance(connection, dict)
    connection["endpoint_doors"] = [
        {
            "local_ref": "invalid-endpoint",
            "endpoint": "from",
            "kind": "door",
        }
    ]

    with pytest.raises(ValidationError, match="same-floor doors"):
        _spec(payload)


def test_design_contract_rejects_vertical_transition_mechanics_without_endpoint_door() -> (
    None
):
    payload = _minimal_design()
    upper = payload["floors"][0]
    assert isinstance(upper, dict)
    upper["rooms"] = [{"local_ref": "entry", "name": "Wet Steps", "role": "entrance"}]
    payload["floors"].append(
        {
            "local_ref": "lower",
            "name": "Lower Vault",
            "rooms": [{"local_ref": "vault", "name": "Vault", "role": "objective"}],
        }
    )
    payload["connections"] = [
        {
            "local_ref": "descent",
            "from_ref": "entry",
            "to_ref": "vault",
            "passage": "stairs",
            "door_mechanics": {"hazard": "trapped", "challenge": "high"},
        }
    ]
    payload["objectives"] = [{"room_ref": "vault", "kind": "final_objective"}]

    with pytest.raises(ValidationError, match="require explicit endpoint_doors"):
        _spec(payload)


def test_design_contract_rejects_concealed_vertical_hatch_without_hidden_endpoint() -> (
    None
):
    payload = _minimal_design()
    upper = payload["floors"][0]
    assert isinstance(upper, dict)
    upper["rooms"] = [{"local_ref": "entry", "name": "Wet Steps", "role": "entrance"}]
    payload["floors"].append(
        {
            "local_ref": "lower",
            "name": "Lower Vault",
            "rooms": [{"local_ref": "vault", "name": "Vault", "role": "objective"}],
        }
    )
    payload["connections"] = [
        {
            "local_ref": "descent",
            "from_ref": "entry",
            "to_ref": "vault",
            "passage": "ladder",
            "endpoint_doors": [
                {
                    "local_ref": "descent-hatch",
                    "endpoint": "to",
                    "kind": "hatch",
                    "mechanics": {"concealed": True, "challenge": "high"},
                }
            ],
        }
    ]
    payload["objectives"] = [{"room_ref": "vault", "kind": "final_objective"}]

    with pytest.raises(ValidationError, match="requires its endpoint to be hidden"):
        _spec(payload)


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
