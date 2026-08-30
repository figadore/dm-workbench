"""Exact-ID Workbench puzzle-enrichment contract coverage."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from dm_assistant.orchestration.dungeons import (
    DungeonPuzzleEnrichmentInput,
    DungeonPuzzleEnrichmentOutput,
)
from dm_assistant.orchestration.dungeons.service import (
    validate_dungeon_puzzle_enrichment,
)


def _wind_shrine_input() -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "package_id": "package_wind_shrine",
        "room": {
            "room_id": "room_echoing_apse",
            "floor_id": "floor_mountain_shrine",
            "boundary": {
                "kind": "polygon",
                "points": [
                    {"x": 10, "y": 8},
                    {"x": 18, "y": 8},
                    {"x": 18, "y": 15},
                    {"x": 10, "y": 15},
                ],
            },
            "capacity": {
                "minimum_occupants": 0,
                "comfortable_occupants": 6,
                "maximum_occupants": 10,
            },
            "connection_ids": ["connection_nave_apse", "connection_apse_vault"],
            "feature_ids": ["feature_wind_chimes"],
        },
        "objective_relationship": {
            "objective_id": "objective_windglass_seed",
            "objective_room_id": "room_seed_vault",
            "relationship": "guards_access",
        },
        "clue_locations": [
            {
                "location_id": "feature_wind_chimes",
                "room_id": "room_echoing_apse",
                "floor_id": "floor_mountain_shrine",
                "purpose": "The chimes demonstrate the three notes used by the lock.",
            },
            {
                "location_id": "room_weathered_nave",
                "room_id": "room_weathered_nave",
                "floor_id": "floor_mountain_shrine",
                "purpose": "A worn procession relief establishes the note order.",
            },
        ],
        "tone": ["windswept", "contemplative"],
        "constraints": ["No numeric difficulty values", "Allow non-musical solutions"],
    }


def _wind_shrine_output() -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "package_id": "package_wind_shrine",
        "room_id": "room_echoing_apse",
        "name": "The Returning Gale",
        "observable_elements": [
            "Three stone vanes turn toward sounds made in the apse.",
            "Matching chimes sound low, high, then middle when the wind rises.",
        ],
        "solution_steps": [
            "Turn the vanes toward the low, high, and middle chimes in that order."
        ],
        "clue_path": [
            {
                "location_id": "feature_wind_chimes",
                "observation": "The gust sounds the chimes low, high, then middle.",
                "inference": "The lock expects the same ordered pattern.",
            },
            {
                "location_id": "room_weathered_nave",
                "observation": "The relief points to low, high, and middle peaks.",
                "inference": "The relief confirms the chime order without requiring pitch recognition.",
            },
        ],
        "hints": ["A hand on a vane makes it hum at the corresponding chime pitch."],
        "alternate_handling": [
            {
                "approach": "Match the relief's peak heights instead of listening to the chimes.",
                "adjudication": "The visual sequence opens the lock just as the musical sequence does.",
            }
        ],
        "failure_consequence": "An incorrect third setting releases a gust that returns all vanes to neutral.",
        "reset_or_retry": "The vanes reset immediately and can be tried again.",
    }


def test_puzzle_enrichment_contract_is_narrow_and_exact_id_keyed() -> None:
    context = DungeonPuzzleEnrichmentInput.model_validate(_wind_shrine_input())
    output = DungeonPuzzleEnrichmentOutput.model_validate(_wind_shrine_output())

    validation = validate_dungeon_puzzle_enrichment(context, output)

    assert validation.accepted_output == output
    assert validation.issues == ()
    assert output.room_id == context.room.room_id
    assert {clue.location_id for clue in output.clue_path} <= {
        clue.location_id for clue in context.clue_locations
    }

    input_schema = str(DungeonPuzzleEnrichmentInput.model_json_schema())
    output_schema = str(DungeonPuzzleEnrichmentOutput.model_json_schema())
    assert "DungeonPlan" not in input_schema
    assert "critical_path" not in input_schema
    assert "exploration" not in output_schema
    assert "topology" not in output_schema


def test_puzzle_enrichment_rejects_cross_task_mutation_and_unknown_ids() -> None:
    mutation = _wind_shrine_output()
    mutation["critical_path"] = ["room_echoing_apse", "room_seed_vault"]
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        DungeonPuzzleEnrichmentOutput.model_validate(mutation)

    context = DungeonPuzzleEnrichmentInput.model_validate(_wind_shrine_input())
    mismatch = deepcopy(_wind_shrine_output())
    mismatch["package_id"] = "package_other"
    mismatch["room_id"] = "room_other"
    clue_path = mismatch["clue_path"]
    assert isinstance(clue_path, list)
    clue_path[0]["location_id"] = "unknown_location"
    output = DungeonPuzzleEnrichmentOutput.model_validate(mismatch)

    validation = validate_dungeon_puzzle_enrichment(context, output)

    assert validation.accepted_output is None
    assert {issue.code for issue in validation.issues} == {
        "puzzle_enrichment.package_mismatch",
        "puzzle_enrichment.room_mismatch",
        "puzzle_enrichment.clue_location_invalid",
    }
