"""Exact-ID Workbench puzzle-enrichment contract coverage."""

import json
from copy import deepcopy

import pytest
from pydantic import ValidationError

from dm_assistant.errors import ConflictError
from dm_assistant.modules.preparation import (
    DungeonGenerationContext,
    GenerationContextEnvelope,
    canonical_json_sha256,
)
from dm_assistant.orchestration.dungeons import (
    DungeonCreativeContinuityProjection,
    DungeonPuzzleClueApproval,
    DungeonPuzzleContextSelection,
    DungeonPuzzleDependencyApproval,
    DungeonPuzzleEnrichmentInput,
    DungeonPuzzleEnrichmentOutput,
    DungeonPuzzleObjectiveApproval,
)
from dm_assistant.orchestration.dungeons.continuity import (
    derive_dungeon_creative_continuity,
)
from dm_assistant.orchestration.dungeons.service import (
    build_dungeon_dm_guide,
    build_dungeon_preparation_readiness,
    build_dungeon_puzzle_enrichment_input,
    project_dungeon_puzzle_enrichment,
    validate_dungeon_puzzle_enrichment,
)
from dm_dungeon import (
    DungeonPackage,
    DungeonPlan,
    LayoutRequest,
    compile_dungeon_plan,
    generate_layout,
)
from dm_dungeon.layout import ORTHOGONAL_LAYOUT_GENERATOR_VERSION


def _standalone_continuity(
    plan: DungeonPlan,
) -> DungeonCreativeContinuityProjection:
    payload = DungeonGenerationContext(
        context_version="1.0.0",
        prompt_input_sha256="a" * 64,
        preparation_owner_id="dm",
        context_provenance="synthetic_test",
    )
    payload_document = payload.model_dump(mode="json")
    envelope = GenerationContextEnvelope(
        context_kind="dungeon_generation",
        payload_version="1.0.0",
        payload=payload_document,
        payload_sha256=canonical_json_sha256(payload_document),
    )
    return derive_dungeon_creative_continuity(envelope, plan)


def _raw_continuity() -> dict[str, object]:
    return {
        "projection_version": "1.0.0",
        "projection_sha256": "a" * 64,
        "premise": "Recover a synthetic seed from an abandoned mountain shrine.",
        "themes": ["wind", "weathered stone"],
        "room_intents": [
            {
                "room_ref": "apse",
                "name": "Echoing Apse",
                "role": "puzzle",
                "purpose": "Control access to the seed vault.",
            }
        ],
        "critical_path": ["approach", "apse"],
        "campaign_lore_status": "unknown",
    }


def _wind_shrine_input() -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "package_id": "package_wind_shrine",
        "continuity": _raw_continuity(),
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
        "success_outcome": "The aligned vanes release the vault latch and settle facing the seed vault.",
        "failure_consequence": "An incorrect third setting releases a gust that returns all vanes to neutral.",
        "reset_or_retry": "The vanes reset immediately and can be tried again.",
    }


def _wind_shrine_package() -> tuple[DungeonPlan, LayoutRequest, DungeonPackage]:
    plan = DungeonPlan.model_validate_json(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "title": "Windglass Shrine",
                "premise": "Recover a synthetic seed from an abandoned mountain shrine.",
                "themes": ["wind", "weathered stone"],
                "rooms": [
                    {
                        "ref": "approach",
                        "name": "Broken Approach",
                        "role": "entrance",
                        "purpose": "Establish the wind-worn shrine entrance.",
                    },
                    {
                        "ref": "nave",
                        "name": "Weathered Nave",
                        "role": "exploration",
                        "purpose": "Show a procession relief that can support the puzzle clue path.",
                    },
                    {
                        "ref": "apse",
                        "name": "Echoing Apse",
                        "role": "puzzle",
                        "purpose": "Use local wind and chimes to control access to the seed vault.",
                    },
                    {
                        "ref": "vault",
                        "name": "Seed Vault",
                        "role": "objective",
                        "purpose": "Hold the named synthetic Windglass Seed objective.",
                    },
                ],
                "critical_path": ["approach", "nave", "apse", "vault"],
                "gates": [
                    {
                        "ref": "seed_gate",
                        "between_rooms": ["apse", "vault"],
                        "kind": "puzzle",
                        "dependency_kind": "clue",
                        "dependency_room": "nave",
                        "dependency_name": "Procession Relief",
                    }
                ],
                "room_contents": [
                    {
                        "room_ref": "apse",
                        "feature": {
                            "kind": "other",
                            "name": "Wind Chimes",
                            "description": "Three stone chimes turn and sound in the mountain wind.",
                        },
                    },
                    {"room_ref": "vault", "objective": "Windglass Seed"},
                ],
            }
        )
    )
    compiled = compile_dungeon_plan(plan)
    assert compiled.accepted
    assert compiled.brief is not None
    assert compiled.topology is not None
    assert compiled.certificate is not None
    assert compiled.mechanics_plan is not None
    request = LayoutRequest(
        schema_version="1.0.0",
        package_id="package_wind_shrine",
        brief=compiled.brief,
        topology=compiled.topology,
        certificate=compiled.certificate,
        seed=714000001,
        generator_version=ORTHOGONAL_LAYOUT_GENERATOR_VERSION,
        mechanics_plan=compiled.mechanics_plan,
        floor_bounds=compiled.floor_bounds,
    )
    layout = generate_layout(request)
    assert layout.success and layout.package is not None
    return plan, request, layout.package


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
    assert "continuity" in input_schema
    assert "exploration" not in output_schema
    assert "topology" not in output_schema


def test_exact_package_builds_narrow_puzzle_context_and_rejects_foreign_ids() -> None:
    plan, request, package = _wind_shrine_package()
    continuity = _standalone_continuity(plan)
    compiled = compile_dungeon_plan(plan)
    assert compiled.certificate is not None
    assert compiled.mechanics_plan is not None
    room_ids = {item.ref: item.room_id for item in compiled.certificate.rooms}
    feature_id = compiled.mechanics_plan.room_features[0].id
    objective_id = compiled.mechanics_plan.room_objectives[0].id
    gate = request.topology.gates[0]
    dependency_id = request.topology.clues[0].id
    selection = DungeonPuzzleContextSelection(
        room_id=room_ids["apse"],
        clue_locations=(
            DungeonPuzzleClueApproval(
                location_id=feature_id,
                purpose="The local chimes demonstrate the lock's notes.",
            ),
            DungeonPuzzleClueApproval(
                location_id=dependency_id,
                purpose="The nave relief establishes the intended note order.",
            ),
        ),
        objective=DungeonPuzzleObjectiveApproval(
            objective_id=objective_id,
            relationship="guards_access",
        ),
        dependency=DungeonPuzzleDependencyApproval(
            gate_id=gate.id,
            dependency_id=dependency_id,
            relationship="uses_dependency",
        ),
        tone=("windswept", "contemplative"),
        constraints=("No numeric difficulty values", "Allow non-musical solutions"),
    )

    context = build_dungeon_puzzle_enrichment_input(
        package,
        selection,
        plan=plan,
        creative_continuity=continuity,
    )

    puzzle_room = next(room for room in package.rooms if room.id == room_ids["apse"])
    assert context.package_id == package.id
    assert context.room.boundary == puzzle_room.boundary
    assert context.room.capacity == puzzle_room.capacity
    assert context.room.feature_ids == (feature_id,)
    assert set(context.room.connection_ids) == {
        connection.id
        for connection in package.topology.connections
        if room_ids["apse"] in (connection.from_room_id, connection.to_room_id)
    }
    assert [(item.location_id, item.room_id) for item in context.clue_locations] == [
        (feature_id, room_ids["apse"]),
        (dependency_id, room_ids["nave"]),
    ]
    assert context.objective_relationship is not None
    assert context.objective_relationship.objective_room_id == room_ids["vault"]
    assert context.dependency_relationship is not None
    assert context.dependency_relationship.gate_id == gate.id

    with pytest.raises(ConflictError, match="unknown exact puzzle room"):
        build_dungeon_puzzle_enrichment_input(
            package,
            selection.model_copy(update={"room_id": "room_from_another_package"}),
            plan=plan,
            creative_continuity=continuity,
        )
    foreign_clue = selection.model_copy(
        update={
            "clue_locations": (
                DungeonPuzzleClueApproval(
                    location_id="clue_from_another_package",
                    purpose="This ID was not approved from the accepted package.",
                ),
            )
        }
    )
    with pytest.raises(ConflictError, match="unknown exact clue location"):
        build_dungeon_puzzle_enrichment_input(
            package,
            foreign_clue,
            plan=plan,
            creative_continuity=continuity,
        )
    distant_clue = selection.model_copy(
        update={
            "clue_locations": (
                DungeonPuzzleClueApproval(
                    location_id=room_ids["approach"],
                    purpose="This exact room is outside the local puzzle neighborhood.",
                ),
            )
        }
    )
    with pytest.raises(ConflictError, match="outside the local puzzle neighborhood"):
        build_dungeon_puzzle_enrichment_input(
            package,
            distant_clue,
            plan=plan,
            creative_continuity=continuity,
        )


def test_accepted_puzzle_projects_into_exact_guide_without_mutating_package() -> None:
    plan, request, package = _wind_shrine_package()
    continuity = _standalone_continuity(plan)
    compiled = compile_dungeon_plan(plan)
    assert compiled.certificate is not None
    assert compiled.mechanics_plan is not None
    room_ids = {item.ref: item.room_id for item in compiled.certificate.rooms}
    feature_id = compiled.mechanics_plan.room_features[0].id
    objective_id = compiled.mechanics_plan.room_objectives[0].id
    gate = request.topology.gates[0]
    dependency_id = request.topology.clues[0].id
    selection = DungeonPuzzleContextSelection(
        room_id=room_ids["apse"],
        clue_locations=(
            DungeonPuzzleClueApproval(
                location_id=feature_id,
                purpose="The local chimes demonstrate the lock's notes.",
            ),
            DungeonPuzzleClueApproval(
                location_id=dependency_id,
                purpose="The nave relief establishes the intended note order.",
            ),
        ),
        objective=DungeonPuzzleObjectiveApproval(
            objective_id=objective_id,
            relationship="guards_access",
        ),
        dependency=DungeonPuzzleDependencyApproval(
            gate_id=gate.id,
            dependency_id=dependency_id,
            relationship="uses_dependency",
        ),
    )
    context = build_dungeon_puzzle_enrichment_input(
        package,
        selection,
        plan=plan,
        creative_continuity=continuity,
    )
    output_document = _wind_shrine_output()
    output_document["room_id"] = room_ids["apse"]
    output_document["clue_path"] = [
        {
            "location_id": feature_id,
            "observation": "The gust sounds the chimes low, high, then middle.",
            "inference": "The lock expects the same ordered pattern.",
        },
        {
            "location_id": dependency_id,
            "observation": "The relief points to low, high, and middle peaks.",
            "inference": "The relief confirms the order without requiring pitch recognition.",
        },
    ]
    output = DungeonPuzzleEnrichmentOutput.model_validate(output_document)
    validation = validate_dungeon_puzzle_enrichment(context, output)
    assert validation.accepted_output == output
    package_before = package.model_dump_json()
    base_guide = build_dungeon_dm_guide(request, package, plan)

    guide = project_dungeon_puzzle_enrichment(
        base_guide,
        plan=plan,
        package=package,
        creative_continuity=continuity,
        context=context,
        validation=validation,
    )

    assert package.model_dump_json() == package_before
    assert guide.map_callouts == base_guide.map_callouts
    assert guide.rooms == base_guide.rooms
    assert guide.connections == base_guide.connections
    assert guide.dependencies == base_guide.dependencies
    assert guide.traps == base_guide.traps
    assert guide.features == base_guide.features
    assert guide.objectives == base_guide.objectives
    assert len(guide.puzzles) == 1
    assert guide.puzzles[0].room_id == room_ids["apse"]
    assert guide.puzzles[0].name == "The Returning Gale"
    assert "low, high, and middle" in guide.puzzles[0].solution
    assert (
        guide.puzzles[0]
        .content.player_choices[0]
        .outcome.startswith("The aligned vanes")
    )
    assert not any(
        issue.kind == "puzzle" and issue.room_ref == "apse"
        for issue in guide.content_issues
    )
    assert {issue.kind for issue in guide.content_issues} == {
        "room",
        "feature",
        "objective",
    }
    assert guide.dependencies[0].discovery == (
        "Procession Relief is present in Weathered Nave."
    )
    readiness = build_dungeon_preparation_readiness(guide)
    assert readiness is not None and not readiness.ready
    assert {item.code for item in readiness.diagnostics} == {
        "dungeon_preparation.guide_content_missing"
    }


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
