"""Bounded Workbench-owned runnable dungeon-guide content contracts."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from dm_assistant.orchestration.dungeons import DungeonGuideContentPlan
from dm_assistant.orchestration.dungeons.service import (
    build_dungeon_dm_guide,
    build_dungeon_preparation_readiness,
    render_dungeon_dm_guide_text,
    validate_dungeon_guide_content,
)
from dm_dungeon import DungeonPlan, LayoutRequest, compile_dungeon_plan, generate_layout
from dm_dungeon.layout import ORTHOGONAL_LAYOUT_GENERATOR_VERSION

_PLAN_PATH = Path(__file__).parents[1] / "evals/golden/dungeon_guide_quality_plan.json"


def _choices(label: str) -> list[dict[str, str]]:
    return [
        {
            "action": f"Use the direct {label} approach.",
            "outcome": f"The direct {label} outcome changes the room state.",
        },
        {
            "action": f"Use the cautious {label} approach.",
            "outcome": f"The cautious {label} outcome reveals useful information.",
        },
    ]


def _fixed_review_content() -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "room_narratives": [
            {
                "room_ref": room_ref,
                "read_aloud": f"Read-aloud arrival text for {room_ref}.",
                "sensory_details": [
                    f"A distinct sound identifies {room_ref}.",
                    f"A distinct texture identifies {room_ref}.",
                ],
            }
            for room_ref in ("entry", "gallery", "cache", "seal", "vault")
        ],
        "entries": [
            {
                "kind": "gate_dependency",
                "ref": "cache_key_interaction",
                "room_ref": "cache",
                "gate_ref": "seal_gate",
                "dependency_name": "Three-Wave Brass Key",
                "situation": "A matching archive insignia identifies the key rack.",
                "discovery": "Clearing the flooded index cards reveals the labelled key.",
                "adjudication": "No check is required after the rack is exposed.",
                "player_choices": _choices("key"),
            },
            {
                "kind": "encounter",
                "ref": "cache_exploration",
                "room_ref": "cache",
                "encounter_intent": "exploration",
                "situation": "Rising water shifts unstable archive crates.",
                "adjudication": "The DM resolves careful bracing without a check.",
                "player_choices": _choices("exploration"),
            },
            {
                "kind": "puzzle",
                "ref": "sealed_hall_index",
                "room_ref": "seal",
                "name": "Sealed Hall Index",
                "situation": "Three brass index tabs control the sealed hall shutters.",
                "solution": "Set the tabs in entry, catalogue, and vault order.",
                "adjudication": "The engraved headings make the order discoverable.",
                "player_choices": _choices("puzzle"),
            },
            {
                "kind": "feature",
                "ref": "indexing_dais_interaction",
                "room_ref": "seal",
                "feature_name": "Instruction Pedestal",
                "situation": "The dais lists the vault holding and its warning ward.",
                "adjudication": "Reading the intact index requires no check.",
                "player_choices": _choices("feature"),
            },
            {
                "kind": "objective",
                "ref": "vault_objective_resolution",
                "room_ref": "vault",
                "objective_name": "Synthetic Objective",
                "situation": "The indexed objective rests in a sealed display cradle.",
                "adjudication": "Opening the cradle completes the test objective.",
                "player_choices": _choices("objective"),
            },
        ],
    }


def test_guide_content_contract_covers_each_human_review_blocker() -> None:
    content = DungeonGuideContentPlan.model_validate(_fixed_review_content())

    assert [entry.kind for entry in content.entries] == [
        "gate_dependency",
        "encounter",
        "puzzle",
        "feature",
        "objective",
    ]
    assert [item.room_ref for item in content.room_narratives] == [
        "entry",
        "gallery",
        "cache",
        "seal",
        "vault",
    ]
    assert all(len(item.sensory_details) == 2 for item in content.room_narratives)
    assert all(len(entry.player_choices) == 2 for entry in content.entries)
    assert all(
        choice.action and choice.outcome
        for entry in content.entries
        for choice in entry.player_choices
    )

    schema = json.dumps(DungeonGuideContentPlan.model_json_schema())
    assert '"discriminator"' in schema
    assert '"propertyName": "kind"' in schema
    assert '"maxItems": 4' in schema


def test_guide_content_semantics_project_onto_exact_guide_ids() -> None:
    plan = DungeonPlan.model_validate_json(_PLAN_PATH.read_bytes())
    content = DungeonGuideContentPlan.model_validate(_fixed_review_content())
    validation = validate_dungeon_guide_content(plan, content)

    assert validation.issues == ()
    assert len(validation.accepted_room_narratives) == 5
    assert len(validation.accepted_entries) == 5

    compiled = compile_dungeon_plan(plan)
    assert compiled.accepted
    assert compiled.brief is not None
    assert compiled.topology is not None
    assert compiled.certificate is not None
    assert compiled.mechanics_plan is not None
    request = LayoutRequest(
        schema_version="1.0.0",
        package_id="guide_content_projection",
        brief=compiled.brief,
        topology=compiled.topology,
        certificate=compiled.certificate,
        seed=424242,
        generator_version=ORTHOGONAL_LAYOUT_GENERATOR_VERSION,
        mechanics_plan=compiled.mechanics_plan,
        floor_bounds=compiled.floor_bounds,
    )
    layout = generate_layout(request)
    assert layout.success and layout.package is not None

    guide = build_dungeon_dm_guide(request, layout.package, plan, content)

    assert guide.content_issues == ()
    assert [room.presentation_number for room in guide.rooms] == [1, 2, 3, 4, 5]
    assert all(room.read_aloud for room in guide.rooms)
    assert all(len(room.sensory_details) == 2 for room in guide.rooms)
    assert guide.dependencies[0].content is not None
    assert guide.dependencies[0].discovery is not None
    encounter_room = next(
        room for room in guide.rooms if room.encounter_slot is not None
    )
    assert encounter_room.encounter_content is not None
    assert len(guide.puzzles) == 1
    assert guide.puzzles[0].map_reference.component_id == guide.puzzles[0].room_id
    assert guide.features[0].content is not None
    assert guide.objectives[0].content is not None
    readiness = build_dungeon_preparation_readiness(guide)
    assert readiness is not None and readiness.ready
    text = render_dungeon_dm_guide_text(guide)
    assert "## Room-by-room guide" in text
    assert "### 1. Archive Entry (Map 2)" in text
    assert "**Read aloud**" in text
    assert "**Sensory cues:**" not in text
    assert "**Find:**" in text
    assert "**Situation:**" in text
    assert "**Run it:**" in text
    assert "##### Choices and consequences" in text
    assert "**Solution:**" in text
    assert "Passage:" not in text

    invalid_document = _fixed_review_content()
    invalid_entries = invalid_document["entries"]
    assert isinstance(invalid_entries, list)
    invalid_entries[0]["room_ref"] = "vault"
    invalid_entries.pop()
    invalid_narratives = invalid_document["room_narratives"]
    assert isinstance(invalid_narratives, list)
    invalid_narratives[0]["room_ref"] = "missing_room"
    invalid_content = DungeonGuideContentPlan.model_validate(invalid_document)
    invalid_validation = validate_dungeon_guide_content(plan, invalid_content)
    assert {issue.code for issue in invalid_validation.issues} == {
        "guide_content.required_missing",
        "guide_content.target_invalid",
    }

    blocked_guide = build_dungeon_dm_guide(
        request, layout.package, plan, invalid_content
    )
    blocked_readiness = build_dungeon_preparation_readiness(blocked_guide)
    assert [room.room_id for room in blocked_guide.rooms] == [
        room.room_id for room in guide.rooms
    ]
    assert [room.map_reference for room in blocked_guide.rooms] == [
        room.map_reference for room in guide.rooms
    ]
    assert blocked_guide.rooms[0].read_aloud is None
    assert blocked_readiness is not None and not blocked_readiness.ready
    assert {item.code for item in blocked_readiness.diagnostics} == {
        "dungeon_preparation.guide_content_invalid",
        "dungeon_preparation.guide_content_missing",
    }


def test_guide_content_contract_rejects_unrunnable_or_ambiguous_entries() -> None:
    too_few_choices = _fixed_review_content()
    entries = too_few_choices["entries"]
    assert isinstance(entries, list)
    entries[0]["player_choices"] = _choices("key")[:1]
    with pytest.raises(ValidationError, match="at least 2 items"):
        DungeonGuideContentPlan.model_validate(too_few_choices)

    duplicate_target = _fixed_review_content()
    entries = duplicate_target["entries"]
    assert isinstance(entries, list)
    duplicate = dict(entries[4])
    duplicate["ref"] = "second_vault_resolution"
    entries.append(duplicate)
    with pytest.raises(
        ValidationError, match="at most one entry of each kind per room"
    ):
        DungeonGuideContentPlan.model_validate(duplicate_target)

    duplicate_room = _fixed_review_content()
    narratives = duplicate_room["room_narratives"]
    assert isinstance(narratives, list)
    narratives[1]["room_ref"] = "entry"
    with pytest.raises(ValidationError, match="unique room refs"):
        DungeonGuideContentPlan.model_validate(duplicate_room)

    untyped_extra = _fixed_review_content()
    entries = untyped_extra["entries"]
    assert isinstance(entries, list)
    entries[2]["invented_renderer_marker"] = "P1"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        DungeonGuideContentPlan.model_validate(untyped_extra)
