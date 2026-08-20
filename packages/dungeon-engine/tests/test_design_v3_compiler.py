"""P7-13d retained-artifact-safe V3 mechanics-contract tests."""

import json

import pytest
from pydantic import ValidationError

from dm_dungeon import (
    DungeonDesignSpecV2,
    DungeonDesignSpecV3,
    compile_dungeon_design_v3,
    load_dungeon_design_v2_json,
    load_dungeon_design_v3_json,
    to_canonical_json,
)


def _design() -> dict[str, object]:
    return {
        "schema_version": "3.0.0",
        "title": "The Locked Observatory",
        "premise": "A fallen observatory seals its lens behind layered defenses.",
        "themes": ["stars"],
        "tones": ["tense"],
        "floors": [
            {
                "local_ref": "upper",
                "name": "Upper Observatory",
                "rooms": [
                    {
                        "local_ref": "entry",
                        "name": "Entry",
                        "role": "entrance",
                        "tags": ["wet"],
                        "preparation_note": "The wind hides quiet movement.",
                        "encounter_slot": "ambush",
                    },
                    {"local_ref": "study", "name": "Study", "role": "puzzle"},
                ],
            },
            {
                "local_ref": "lower",
                "name": "Lens Vault",
                "rooms": [{"local_ref": "vault", "name": "Vault", "role": "objective"}],
            },
        ],
        "connections": [
            {
                "local_ref": "study-door",
                "from_ref": "entry",
                "to_ref": "study",
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
                "from_ref": "study",
                "to_ref": "vault",
                "passage": "stairs",
                "to_hidden": True,
                "endpoint_doors": [
                    {
                        "local_ref": "vault-hatch",
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
        ],
        "objectives": [{"room_ref": "vault", "kind": "final_objective"}],
        "dependencies": [
            {
                "local_ref": "study-key",
                "kind": "key",
                "target_ref": "study-door",
                "located_in_room_ref": "entry",
                "name": "Brass Key",
            },
            {
                "local_ref": "vault-clue",
                "kind": "clue",
                "target_ref": "vault-hatch",
                "located_in_room_ref": "study",
                "name": "Star Chart",
            },
        ],
        "traps": [
            {
                "local_ref": "study-glyph",
                "room_ref": "study",
                "name": "Glyph",
                "trigger": "Touching the lens.",
                "effect": "A thunderous ward sounds.",
                "challenge": "high",
            }
        ],
        "puzzles": [
            {
                "local_ref": "star-dial",
                "room_ref": "study",
                "name": "Star Dial",
                "mechanism": "Three rotating rings.",
                "clue_refs": ["vault-clue"],
                "solution": "Align the summer constellation.",
                "consequence": "The hatch releases.",
                "challenge": "moderate",
            }
        ],
        "features": [
            {
                "local_ref": "lens",
                "room_ref": "vault",
                "kind": "altar",
                "name": "Fallen Lens",
                "description": "A cracked brass lens fills the chamber.",
            }
        ],
        "loops": [],
        "branches": [],
    }


def _spec(payload: dict[str, object]) -> DungeonDesignSpecV3:
    return DungeonDesignSpecV3.model_validate_json(json.dumps(payload))


def test_v3_compiles_every_requested_door_and_endpoint_mechanic() -> None:
    result = compile_dungeon_design_v3(_spec(_design()))

    assert result.accepted
    assert result.mechanics_plan is not None
    mechanics = {item.endpoint: item for item in result.mechanics_plan.door_mechanics}
    same_floor = mechanics[None]
    vertical = mechanics[
        next(endpoint for endpoint in mechanics if endpoint is not None)
    ]
    assert same_floor.concealed and same_floor.gate_id and same_floor.trap_id
    assert same_floor.gate_kind.value == "locked"
    assert same_floor.discovery_difficulty == 13
    assert same_floor.unlock_difficulty == 13
    assert same_floor.disable_difficulty == 13
    assert vertical.concealed and vertical.gate_id and vertical.trap_id
    assert vertical.gate_kind.value == "puzzle"
    assert vertical.discovery_difficulty == 16
    assert vertical.unlock_difficulty == 16
    assert vertical.disable_difficulty == 16
    assert len(result.mechanics_plan.room_traps) == 1


def test_v3_requires_explicit_vertical_endpoint_barriers() -> None:
    payload = _design()
    connection = payload["connections"][1]
    assert isinstance(connection, dict)
    connection["door_mechanics"] = {"barrier": "locked", "challenge": "low"}

    with pytest.raises(ValidationError, match="explicit endpoint_doors"):
        _spec(payload)


def test_v3_rejects_mechanics_on_a_same_floor_passage() -> None:
    payload = _design()
    connection = payload["connections"][0]
    assert isinstance(connection, dict)
    connection["passage"] = "passage"

    with pytest.raises(ValidationError, match="same-floor passages"):
        _spec(payload)


def test_v3_reports_missing_dependency_with_a_safe_target_ref() -> None:
    payload = _design()
    payload["dependencies"] = []

    result = compile_dungeon_design_v3(_spec(payload))

    assert not result.accepted
    assert {item.code for item in result.diagnostics} == {
        "design_v3.missing_dependency"
    }
    assert {item.affected_refs[0] for item in result.diagnostics} == {
        "study-door",
        "vault-hatch",
    }


def test_v3_reader_is_versioned_without_reinterpreting_v2() -> None:
    v3 = _spec(_design())
    assert load_dungeon_design_v3_json(to_canonical_json(v3)) == v3

    v2 = {
        "schema_version": "2.1.0",
        "title": "Old Cellar",
        "premise": "Old retained input.",
        "themes": ["salt"],
        "floors": [
            {
                "local_ref": "cellar",
                "name": "Cellar",
                "rooms": [
                    {"local_ref": "entry", "name": "Entry", "role": "entrance"},
                    {"local_ref": "vault", "name": "Vault", "role": "objective"},
                ],
            }
        ],
        "connections": [
            {
                "local_ref": "door",
                "from_ref": "entry",
                "to_ref": "vault",
                "passage": "door",
            }
        ],
        "objectives": [{"room_ref": "vault", "kind": "final_objective"}],
        "dependencies": [],
    }
    retained = load_dungeon_design_v2_json(json.dumps(v2))
    assert isinstance(retained, DungeonDesignSpecV2)
    with pytest.raises(ValueError, match="DungeonDesignSpecV3 schema version"):
        load_dungeon_design_v3_json(json.dumps(v2))
