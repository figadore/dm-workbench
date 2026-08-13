"""Contract and canonical serialization tests."""

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from dm_dungeon import (
    DungeonPackage,
    dungeon_package_json_schema,
    load_dungeon_package_json,
    to_canonical_json,
)
from dm_dungeon.contracts import GridSpec, GridType
from dm_dungeon.serialization import UnsupportedSchemaVersionError


def read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_hand_authored_package_round_trips_without_information_loss(
    fixture_path: Path,
    synthetic_package: DungeonPackage,
) -> None:
    source = read_json_object(fixture_path)

    assert synthetic_package.model_dump(mode="json", round_trip=True) == source

    canonical = to_canonical_json(synthetic_package)
    round_tripped = load_dungeon_package_json(canonical)

    assert round_tripped == synthetic_package
    assert to_canonical_json(round_tripped) == canonical
    assert json.loads(canonical) == source


def test_package_json_schema_exposes_versioned_root_and_definitions() -> None:
    schema = dungeon_package_json_schema()

    assert schema["title"] == "DungeonPackage"
    assert schema["properties"]["schema_version"]["const"] == "1.0.0"
    assert "DungeonBrief" in schema["$defs"]
    assert "DungeonTopology" in schema["$defs"]
    assert "RenderLayer" in schema["$defs"]


def test_grid_defaults_to_orthogonal_five_foot_square_cells() -> None:
    grid = GridSpec()

    assert grid.grid_type is GridType.SQUARE
    assert grid.cell_scale_feet == 5
    assert grid.orthogonal is True


def test_unknown_root_schema_version_fails_explicitly(fixture_path: Path) -> None:
    payload = read_json_object(fixture_path)
    payload["schema_version"] = "99.0.0"

    with pytest.raises(
        UnsupportedSchemaVersionError,
        match=r"Unsupported DungeonPackage schema version '99.0.0'",
    ):
        load_dungeon_package_json(json.dumps(payload))


def test_unknown_nested_schema_version_fails_explicitly(fixture_path: Path) -> None:
    payload = read_json_object(fixture_path)
    payload["brief"]["schema_version"] = "99.0.0"

    with pytest.raises(
        ValidationError,
        match=r"Unsupported DungeonBrief schema version '99.0.0'",
    ):
        load_dungeon_package_json(json.dumps(payload))


def test_dm_only_element_requires_explicit_visibility(fixture_path: Path) -> None:
    payload = read_json_object(fixture_path)
    del payload["hazards"][0]["visibility"]

    with pytest.raises(ValidationError, match="visibility"):
        load_dungeon_package_json(json.dumps(payload))


def test_secret_access_does_not_make_a_floor_dm_only(fixture_path: Path) -> None:
    """A discovered floor always has a clean map; only its secrets stay hidden."""
    payload = read_json_object(fixture_path)
    lower_floor = next(
        floor for floor in payload["topology"]["floors"] if floor["id"] == "floor_lower"
    )
    lower_floor["visibility"] = "dm_only"

    with pytest.raises(ValidationError, match="player_safe"):
        load_dungeon_package_json(json.dumps(payload))


def test_secret_door_cannot_be_player_safe(fixture_path: Path) -> None:
    payload = read_json_object(fixture_path)
    secret_door = next(
        door for door in payload["doors"] if door["door_type"] == "secret"
    )
    secret_door["visibility"] = "player_safe"
    secret_door["layer_id"] = "layer_base"

    with pytest.raises(
        ValidationError, match="secret and trapped doors must be dm_only"
    ):
        load_dungeon_package_json(json.dumps(payload))


def test_dm_layer_cannot_enter_player_export(fixture_path: Path) -> None:
    payload = read_json_object(fixture_path)
    dm_layer = next(
        layer for layer in payload["layers"] if layer["visibility"] == "dm_only"
    )
    dm_layer["include_in_player_export"] = True

    with pytest.raises(
        ValidationError,
        match="dm_only layers cannot be included in player exports",
    ):
        load_dungeon_package_json(json.dumps(payload))


def test_layer_visibility_must_match_each_component(fixture_path: Path) -> None:
    payload = read_json_object(fixture_path)
    player_label = next(
        label for label in payload["labels"] if label["visibility"] == "player_safe"
    )
    player_label["layer_id"] = "layer_dm_annotations"

    with pytest.raises(ValidationError, match="visibility does not match layer"):
        load_dungeon_package_json(json.dumps(payload))


def test_strict_contract_rejects_scalar_coercion(fixture_path: Path) -> None:
    payload = read_json_object(fixture_path)
    payload["grid"]["cell_scale_feet"] = "5"

    with pytest.raises(ValidationError, match="Input should be a valid integer"):
        load_dungeon_package_json(json.dumps(payload))


def test_strict_contract_rejects_extra_fields(fixture_path: Path) -> None:
    payload = deepcopy(read_json_object(fixture_path))
    payload["renderer_instructions"] = "draw a secret in the player export"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        load_dungeon_package_json(json.dumps(payload))
