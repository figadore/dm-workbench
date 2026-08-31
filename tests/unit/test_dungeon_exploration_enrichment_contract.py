"""Exact-ID Workbench exploration and feature-enrichment contract coverage."""

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
    DungeonExplorationAffordanceApproval,
    DungeonExplorationContextSelection,
    DungeonExplorationEnrichmentInput,
    DungeonExplorationEnrichmentOutput,
    DungeonFeatureInteractionContextSelection,
    DungeonFeatureInteractionEnrichmentInput,
    DungeonFeatureInteractionEnrichmentOutput,
    DungeonFeatureInteractionFeature,
    DungeonFeatureInteractionIssue,
    DungeonFeatureInteractionRoomContext,
    DungeonFeatureInteractionValidationResult,
    DungeonPuzzleAlternateHandling,
    DungeonPuzzleClue,
    DungeonPuzzleClueApproval,
    DungeonPuzzleContextSelection,
    DungeonPuzzleEnrichmentOutput,
)
from dm_assistant.orchestration.dungeons.continuity import (
    derive_dungeon_creative_continuity,
)
from dm_assistant.orchestration.dungeons.service import (
    build_dungeon_dm_guide,
    build_dungeon_exploration_enrichment_input,
    build_dungeon_feature_interaction_enrichment_input,
    build_dungeon_preparation_readiness,
    build_dungeon_puzzle_enrichment_input,
    project_dungeon_exploration_enrichment,
    project_dungeon_feature_interaction_enrichment,
    project_dungeon_puzzle_enrichment,
    validate_dungeon_exploration_enrichment,
    validate_dungeon_feature_interaction_enrichment,
    validate_dungeon_puzzle_enrichment,
)
from dm_dungeon import (
    DungeonPackage,
    DungeonPlan,
    LayoutRequest,
    compile_dungeon_plan,
    generate_layout,
)
from dm_dungeon.contracts import FeatureIntentKind
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


def _skyroot_package() -> tuple[DungeonPlan, LayoutRequest, DungeonPackage]:
    plan = DungeonPlan.model_validate_json(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "title": "Skyroot Conservatory",
                "premise": "Recover a synthetic cloud-pine cutting from a storm-damaged mountaintop glasshouse.",
                "themes": ["rain-fed glasshouse", "counterweighted brass"],
                "rooms": [
                    {
                        "ref": "portico",
                        "name": "Hailstone Portico",
                        "role": "entrance",
                        "purpose": "Establish the exposed conservatory entrance.",
                    },
                    {
                        "ref": "gallery",
                        "name": "Rain Gallery",
                        "role": "exploration",
                        "purpose": "Cross a rain channel by manipulating the surviving shutters.",
                        "encounter": "exploration",
                    },
                    {
                        "ref": "oriel",
                        "name": "Sun Oriel",
                        "role": "puzzle",
                        "purpose": "Redirect pale light through the propagation lock.",
                    },
                    {
                        "ref": "nursery",
                        "name": "Cloud-Pine Nursery",
                        "role": "objective",
                        "purpose": "Hold the named cloud-pine cutting.",
                    },
                ],
                "critical_path": ["portico", "gallery", "oriel", "nursery"],
                "room_contents": [
                    {
                        "room_ref": "gallery",
                        "feature": {
                            "kind": "other",
                            "name": "Counterweight Shutters",
                            "description": "Brass counterweights move intact roof shutters above the rain channel.",
                        },
                    },
                    {
                        "room_ref": "oriel",
                        "feature": {
                            "kind": "other",
                            "name": "Prism Stand",
                            "description": "A fixed prism stand catches light from the surviving roof panes.",
                        },
                    },
                    {
                        "room_ref": "nursery",
                        "feature": {
                            "kind": "other",
                            "name": "Mistwheel Console",
                            "description": "A handwheel and two sight glasses regulate mist around the cloud-pine bed.",
                        },
                        "objective": "Cloud-Pine Cutting",
                    },
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
        package_id="package_skyroot_conservatory",
        brief=compiled.brief,
        topology=compiled.topology,
        certificate=compiled.certificate,
        seed=714000019,
        generator_version=ORTHOGONAL_LAYOUT_GENERATOR_VERSION,
        mechanics_plan=compiled.mechanics_plan,
        floor_bounds=compiled.floor_bounds,
    )
    layout = generate_layout(request)
    assert layout.success and layout.package is not None
    return plan, request, layout.package


def _exploration_output(
    *, package_id: str, room_id: str, encounter_slot_id: str, affordance_id: str
) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "package_id": package_id,
        "room_id": room_id,
        "encounter_slot_id": encounter_slot_id,
        "observable_cues": [
            "Rain fills the center channel while intact roof shutters hang above it.",
            "The nearest brass counterweight lifts one shutter and lowers another.",
        ],
        "approaches": [
            {
                "affordance_ids": [affordance_id],
                "action": "Work the counterweights to create a moving strip of shelter.",
                "adjudication": "Advance the safe strip one bay whenever the group balances the next weight.",
                "consequence": "The group crosses together but must leave carried bulky gear until the return trip.",
            },
            {
                "affordance_ids": [affordance_id],
                "action": "Lock every raised shutter and hurry through the open rain channel.",
                "adjudication": "Treat secure wedges or tied weights as effective without requiring one prescribed tool.",
                "consequence": "The group crosses quickly, but unsecured gear is swept to the gallery entrance.",
            },
        ],
        "escalation": "After the second major delay, runoff reaches the lowest counterweight and makes it harder to hold steady.",
        "recovery": "Opening the west drain lowers the water and returns the counterweights to their starting positions.",
    }


def _exploration_selection(
    *, room_id: str, affordance_id: str
) -> DungeonExplorationContextSelection:
    return DungeonExplorationContextSelection(
        room_id=room_id,
        affordances=(
            DungeonExplorationAffordanceApproval(
                affordance_id=affordance_id,
                use="The shutter counterweights can create shelter or redirect runoff.",
            ),
        ),
        pacing_role="rising_tension",
        stakes="Crossing carelessly separates carried supplies from the group; failure never blocks the only route permanently.",
        constraints=(
            "Do not add creatures or combatants",
            "Allow more than one reasonable crossing method",
            "Do not invent numeric difficulty values",
        ),
    )


def test_exact_package_builds_local_exploration_context_and_rejects_foreign_ids() -> (
    None
):
    plan, _, package = _skyroot_package()
    continuity = _standalone_continuity(plan)
    compiled = compile_dungeon_plan(plan)
    assert compiled.certificate is not None
    assert compiled.mechanics_plan is not None
    room_ids = {item.ref: item.room_id for item in compiled.certificate.rooms}
    affordance_id = next(
        item.id
        for item in compiled.mechanics_plan.room_features
        if item.room_id == room_ids["gallery"]
    )
    encounter_slot_id = next(
        item.id
        for item in compiled.mechanics_plan.encounter_slots
        if item.room_id == room_ids["gallery"]
    )
    selection = _exploration_selection(
        room_id=room_ids["gallery"], affordance_id=affordance_id
    )

    context = build_dungeon_exploration_enrichment_input(
        package,
        selection,
        plan=plan,
        creative_continuity=continuity,
    )

    exact_room = next(room for room in package.rooms if room.id == room_ids["gallery"])
    marker = next(
        item for item in package.room_mechanic_markers if item.id == affordance_id
    )
    assert context.package_id == package.id
    assert context.room.room_id == exact_room.id
    assert context.room.floor_id == exact_room.floor_id
    assert context.room.boundary == exact_room.boundary
    assert context.room.capacity == exact_room.capacity
    assert context.room.encounter_slot_id == encounter_slot_id
    assert len(context.affordances) == 1
    assert context.affordances[0].affordance_id == affordance_id
    assert context.affordances[0].position == marker.position
    assert context.affordances[0].use == selection.affordances[0].use
    assert context.pacing_role == "rising_tension"
    assert context.stakes == selection.stakes
    assert context.constraints == selection.constraints

    input_schema = str(DungeonExplorationEnrichmentInput.model_json_schema())
    output_schema = str(DungeonExplorationEnrichmentOutput.model_json_schema())
    assert "DungeonPlan" not in input_schema
    assert "continuity" in input_schema
    assert "DungeonPuzzle" not in output_schema
    assert "topology" not in output_schema

    with pytest.raises(ConflictError, match="unknown exact exploration room"):
        build_dungeon_exploration_enrichment_input(
            package,
            selection.model_copy(update={"room_id": "room_from_another_package"}),
            plan=plan,
            creative_continuity=continuity,
        )
    with pytest.raises(ConflictError, match="unknown exact environmental affordance"):
        build_dungeon_exploration_enrichment_input(
            package,
            selection.model_copy(
                update={
                    "affordances": (
                        DungeonExplorationAffordanceApproval(
                            affordance_id="feature_from_another_package",
                            use="This is not part of the accepted room.",
                        ),
                    )
                }
            ),
            plan=plan,
            creative_continuity=continuity,
        )
    with pytest.raises(ConflictError, match="outside the selected exploration room"):
        build_dungeon_exploration_enrichment_input(
            package,
            selection.model_copy(
                update={
                    "affordances": (
                        DungeonExplorationAffordanceApproval(
                            affordance_id=next(
                                item.id
                                for item in compiled.mechanics_plan.room_features
                                if item.room_id == room_ids["oriel"]
                            ),
                            use="This exact feature belongs to a different room.",
                        ),
                    )
                }
            ),
            plan=plan,
            creative_continuity=continuity,
        )


def _feature_selection(
    *, room_id: str, feature_id: str
) -> DungeonFeatureInteractionContextSelection:
    return DungeonFeatureInteractionContextSelection(
        room_id=room_id,
        feature_id=feature_id,
        interaction_goal="Let the party stabilize the nursery mist before handling the cutting.",
        stakes="A careless adjustment drenches the cutting but never destroys or permanently blocks it.",
        constraints=(
            "Keep the handwheel and two sight glasses as the complete apparatus",
            "Do not invent numeric difficulty values",
            "Allow more than one reasonable adjustment method",
        ),
    )


def _feature_output(
    *, package_id: str, room_id: str, feature_id: str
) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "package_id": package_id,
        "room_id": room_id,
        "feature_id": feature_id,
        "observable_setup": [
            "The left sight glass is empty while the right glass pulses with cloudy water.",
            "Turning the handwheel changes both water levels in opposite directions.",
        ],
        "affordances": [
            {
                "action": "Turn the wheel until both sight glasses hold the same level.",
                "adjudication": "Slow adjustments reveal the levels settling toward the center marks.",
                "consequence": "Balanced flow parts the mist around the cutting bed.",
            },
            {
                "action": "Clamp one feed line while another character feathers the wheel.",
                "adjudication": "A secure soft clamp can hold either line without prescribing one tool.",
                "consequence": "The mist clears, but the clamped line must be released before the cutting is removed.",
            },
        ],
        "reset_or_retry": "Opening the drain lever empties both glasses and returns the wheel to its starting mark.",
    }


def test_exact_guide_feature_builds_local_context_and_rejects_foreign_ids() -> None:
    plan, request, package = _skyroot_package()
    continuity = _standalone_continuity(plan)
    compiled = compile_dungeon_plan(plan)
    assert compiled.certificate is not None
    assert compiled.mechanics_plan is not None
    room_ids = {item.ref: item.room_id for item in compiled.certificate.rooms}
    feature_ids = {
        item.room_id: item.id for item in compiled.mechanics_plan.room_features
    }
    guide = build_dungeon_dm_guide(request, package, plan)
    selection = _feature_selection(
        room_id=room_ids["nursery"],
        feature_id=feature_ids[room_ids["nursery"]],
    )

    context = build_dungeon_feature_interaction_enrichment_input(
        package,
        guide,
        selection,
        plan=plan,
        creative_continuity=continuity,
    )

    exact_room = next(room for room in package.rooms if room.id == room_ids["nursery"])
    marker = next(
        item
        for item in package.room_mechanic_markers
        if item.id == feature_ids[room_ids["nursery"]]
    )
    assert context.package_id == package.id
    assert context.room == DungeonFeatureInteractionRoomContext(
        room_id=exact_room.id,
        floor_id=exact_room.floor_id,
        boundary=exact_room.boundary,
        capacity=exact_room.capacity,
    )
    assert context.feature == DungeonFeatureInteractionFeature(
        feature_id=marker.id,
        room_id=marker.room_id,
        floor_id=marker.floor_id,
        position=marker.position,
        kind=FeatureIntentKind.OTHER,
        name="Mistwheel Console",
        description="A handwheel and two sight glasses regulate mist around the cloud-pine bed.",
    )
    assert context.interaction_goal == selection.interaction_goal
    assert context.stakes == selection.stakes
    assert context.constraints == selection.constraints

    input_schema = str(DungeonFeatureInteractionEnrichmentInput.model_json_schema())
    output_schema = str(DungeonFeatureInteractionEnrichmentOutput.model_json_schema())
    assert "DungeonPlan" not in input_schema
    assert "continuity" in input_schema
    assert "DungeonPuzzle" not in output_schema
    assert "encounter_content" not in output_schema
    assert "topology" not in output_schema

    with pytest.raises(ConflictError, match="unknown exact feature room"):
        build_dungeon_feature_interaction_enrichment_input(
            package,
            guide,
            selection.model_copy(update={"room_id": "room_from_another_package"}),
            plan=plan,
            creative_continuity=continuity,
        )
    with pytest.raises(ConflictError, match="unknown exact room feature"):
        build_dungeon_feature_interaction_enrichment_input(
            package,
            guide,
            selection.model_copy(update={"feature_id": "feature_from_another_package"}),
            plan=plan,
            creative_continuity=continuity,
        )
    with pytest.raises(ConflictError, match="outside the selected feature room"):
        build_dungeon_feature_interaction_enrichment_input(
            package,
            guide,
            selection.model_copy(
                update={"feature_id": feature_ids[room_ids["gallery"]]}
            ),
            plan=plan,
            creative_continuity=continuity,
        )

    valid_document = _feature_output(
        package_id=package.id,
        room_id=room_ids["nursery"],
        feature_id=feature_ids[room_ids["nursery"]],
    )
    output = DungeonFeatureInteractionEnrichmentOutput.model_validate(valid_document)
    assert (
        validate_dungeon_feature_interaction_enrichment(context, output).accepted_output
        == output
    )

    structural_mutation = deepcopy(valid_document)
    structural_mutation["topology"] = {"replace": True}
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        DungeonFeatureInteractionEnrichmentOutput.model_validate(structural_mutation)
    cross_task_mutation = deepcopy(valid_document)
    cross_task_mutation["encounter_content"] = {"replace": True}
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        DungeonFeatureInteractionEnrichmentOutput.model_validate(cross_task_mutation)

    mismatch = deepcopy(valid_document)
    mismatch["package_id"] = "package_other"
    mismatch["room_id"] = "room_other"
    mismatch["feature_id"] = "feature_other"
    rejected = validate_dungeon_feature_interaction_enrichment(
        context, DungeonFeatureInteractionEnrichmentOutput.model_validate(mismatch)
    )
    assert rejected == DungeonFeatureInteractionValidationResult(
        schema_version="1.0.0",
        issues=(
            DungeonFeatureInteractionIssue(
                code="feature_interaction.package_mismatch",
                component_id="package_other",
                message="Feature interaction targets a different dungeon package.",
            ),
            DungeonFeatureInteractionIssue(
                code="feature_interaction.room_mismatch",
                component_id="room_other",
                message="Feature interaction targets a different exact room.",
            ),
            DungeonFeatureInteractionIssue(
                code="feature_interaction.feature_mismatch",
                component_id="feature_other",
                message="Feature interaction targets a different exact feature.",
            ),
        ),
    )


def test_exploration_validation_rejects_foreign_ids_and_structural_mutation() -> None:
    plan, _, package = _skyroot_package()
    continuity = _standalone_continuity(plan)
    compiled = compile_dungeon_plan(plan)
    assert compiled.certificate is not None
    assert compiled.mechanics_plan is not None
    room_ids = {item.ref: item.room_id for item in compiled.certificate.rooms}
    affordance_id = next(
        item.id
        for item in compiled.mechanics_plan.room_features
        if item.room_id == room_ids["gallery"]
    )
    context = build_dungeon_exploration_enrichment_input(
        package,
        _exploration_selection(
            room_id=room_ids["gallery"], affordance_id=affordance_id
        ),
        plan=plan,
        creative_continuity=continuity,
    )
    valid_document = _exploration_output(
        package_id=package.id,
        room_id=room_ids["gallery"],
        encounter_slot_id=context.room.encounter_slot_id,
        affordance_id=affordance_id,
    )
    output = DungeonExplorationEnrichmentOutput.model_validate(valid_document)
    assert (
        validate_dungeon_exploration_enrichment(context, output).accepted_output
        == output
    )

    mutation = deepcopy(valid_document)
    mutation["connections"] = ["replace_the_topology"]
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        DungeonExplorationEnrichmentOutput.model_validate(mutation)

    mismatch = deepcopy(valid_document)
    mismatch["package_id"] = "package_other"
    mismatch["room_id"] = "room_other"
    mismatch["encounter_slot_id"] = "slot_other"
    approaches = mismatch["approaches"]
    assert isinstance(approaches, list)
    approaches[0]["affordance_ids"] = ["foreign_affordance"]
    rejected = validate_dungeon_exploration_enrichment(
        context, DungeonExplorationEnrichmentOutput.model_validate(mismatch)
    )
    assert rejected.accepted_output is None
    assert {issue.code for issue in rejected.issues} == {
        "exploration_enrichment.package_mismatch",
        "exploration_enrichment.room_mismatch",
        "exploration_enrichment.encounter_slot_mismatch",
        "exploration_enrichment.affordance_invalid",
    }


def test_accepted_exploration_projects_one_challenge_without_cross_task_mutation() -> (
    None
):
    plan, request, package = _skyroot_package()
    continuity = _standalone_continuity(plan)
    compiled = compile_dungeon_plan(plan)
    assert compiled.certificate is not None
    assert compiled.mechanics_plan is not None
    room_ids = {item.ref: item.room_id for item in compiled.certificate.rooms}
    feature_ids = {
        item.room_id: item.id for item in compiled.mechanics_plan.room_features
    }
    base_guide = build_dungeon_dm_guide(request, package, plan)

    puzzle_context = build_dungeon_puzzle_enrichment_input(
        package,
        DungeonPuzzleContextSelection(
            room_id=room_ids["oriel"],
            clue_locations=(
                DungeonPuzzleClueApproval(
                    location_id=feature_ids[room_ids["oriel"]],
                    purpose="The prism stand is the approved local light source.",
                ),
            ),
        ),
        plan=plan,
        creative_continuity=continuity,
    )
    puzzle_output = DungeonPuzzleEnrichmentOutput(
        schema_version="1.0.0",
        package_id=package.id,
        room_id=room_ids["oriel"],
        name="Three Pale Beams",
        observable_elements=(
            "A fixed prism divides the roof light into three pale beams.",
            "Three cloudy panes brighten when a beam crosses them.",
        ),
        solution_steps=(
            "Turn the three pane frames until every pane catches one beam.",
        ),
        clue_path=(
            DungeonPuzzleClue(
                location_id=feature_ids[room_ids["oriel"]],
                observation="The fixed prism already divides the light evenly.",
                inference="The pane frames, rather than the prism, are meant to move.",
            ),
        ),
        alternate_handling=(
            DungeonPuzzleAlternateHandling(
                approach="Reflect the three beams with polished carried objects.",
                adjudication="Three stable reflected beams brighten the panes equally well.",
            ),
        ),
        success_outcome="The nursery latch opens when all three panes brighten.",
        failure_consequence="A moved frame slowly settles back when no beam reaches it.",
        reset_or_retry="The frames can be repositioned immediately.",
    )
    guide_with_puzzle = project_dungeon_puzzle_enrichment(
        base_guide,
        plan=plan,
        package=package,
        creative_continuity=continuity,
        context=puzzle_context,
        validation=validate_dungeon_puzzle_enrichment(puzzle_context, puzzle_output),
    )

    affordance_id = feature_ids[room_ids["gallery"]]
    context = build_dungeon_exploration_enrichment_input(
        package,
        _exploration_selection(
            room_id=room_ids["gallery"], affordance_id=affordance_id
        ),
        plan=plan,
        creative_continuity=continuity,
    )
    output = DungeonExplorationEnrichmentOutput.model_validate(
        _exploration_output(
            package_id=package.id,
            room_id=room_ids["gallery"],
            encounter_slot_id=context.room.encounter_slot_id,
            affordance_id=affordance_id,
        )
    )
    validation = validate_dungeon_exploration_enrichment(context, output)
    package_before = package.model_dump_json()

    guide = project_dungeon_exploration_enrichment(
        guide_with_puzzle,
        plan=plan,
        package=package,
        creative_continuity=continuity,
        context=context,
        validation=validation,
    )

    assert package.model_dump_json() == package_before
    assert guide.map_callouts == guide_with_puzzle.map_callouts
    assert guide.connections == guide_with_puzzle.connections
    assert guide.dependencies == guide_with_puzzle.dependencies
    assert guide.traps == guide_with_puzzle.traps
    assert guide.puzzles == guide_with_puzzle.puzzles
    assert guide.features == guide_with_puzzle.features
    assert guide.objectives == guide_with_puzzle.objectives
    gallery = next(room for room in guide.rooms if room.room_id == room_ids["gallery"])
    assert gallery.encounter_content is not None
    assert "Rain fills the center channel" in gallery.encounter_content.situation
    assert "Crossing carelessly separates" in gallery.encounter_content.situation
    assert "Rising tension" in gallery.encounter_content.adjudication
    assert len(gallery.encounter_content.player_choices) == 2
    assert "unsecured gear" in gallery.encounter_content.player_choices[1].outcome
    assert all(
        room
        == next(
            item for item in guide_with_puzzle.rooms if item.room_id == room.room_id
        )
        for room in guide.rooms
        if room.room_id != room_ids["gallery"]
    )
    removed_issue = next(
        issue
        for issue in guide_with_puzzle.content_issues
        if issue.kind == "encounter" and issue.room_ref == "gallery"
    )
    assert guide.content_issues == tuple(
        issue for issue in guide_with_puzzle.content_issues if issue != removed_issue
    )
    assert {issue.kind for issue in guide.content_issues} == {
        "room",
        "feature",
        "objective",
    }
    readiness = build_dungeon_preparation_readiness(guide)
    assert readiness is not None and not readiness.ready
    assert {item.code for item in readiness.diagnostics} == {
        "dungeon_preparation.guide_content_missing"
    }

    with pytest.raises(
        ConflictError, match="cannot replace accepted exploration content"
    ):
        project_dungeon_exploration_enrichment(
            guide,
            plan=plan,
            package=package,
            creative_continuity=continuity,
            context=context,
            validation=validation,
        )

    feature_id = feature_ids[room_ids["nursery"]]
    feature_context = build_dungeon_feature_interaction_enrichment_input(
        package,
        guide,
        _feature_selection(room_id=room_ids["nursery"], feature_id=feature_id),
        plan=plan,
        creative_continuity=continuity,
    )
    feature_output = DungeonFeatureInteractionEnrichmentOutput.model_validate(
        _feature_output(
            package_id=package.id,
            room_id=room_ids["nursery"],
            feature_id=feature_id,
        )
    )
    feature_validation = validate_dungeon_feature_interaction_enrichment(
        feature_context, feature_output
    )

    guide_with_feature = project_dungeon_feature_interaction_enrichment(
        guide,
        plan=plan,
        package=package,
        creative_continuity=continuity,
        context=feature_context,
        validation=feature_validation,
    )

    assert package.model_dump_json() == package_before
    assert guide_with_feature.map_callouts == guide.map_callouts
    assert guide_with_feature.rooms == guide.rooms
    assert guide_with_feature.connections == guide.connections
    assert guide_with_feature.dependencies == guide.dependencies
    assert guide_with_feature.traps == guide.traps
    assert guide_with_feature.puzzles == guide.puzzles
    assert guide_with_feature.objectives == guide.objectives
    target = next(
        item for item in guide_with_feature.features if item.marker_id == feature_id
    )
    assert target.content is not None
    assert "left sight glass is empty" in target.content.situation
    assert "careless adjustment drenches" in target.content.situation
    assert "Opening the drain lever" in target.content.adjudication
    assert len(target.content.player_choices) == 2
    assert "Balanced flow parts the mist" in target.content.player_choices[0].outcome
    assert all(
        item
        == next(prior for prior in guide.features if prior.marker_id == item.marker_id)
        for item in guide_with_feature.features
        if item.marker_id != feature_id
    )
    removed_feature_issue = next(
        issue
        for issue in guide.content_issues
        if issue.kind == "feature" and issue.room_ref == "nursery"
    )
    assert guide_with_feature.content_issues == tuple(
        issue for issue in guide.content_issues if issue != removed_feature_issue
    )
    assert {issue.kind for issue in guide_with_feature.content_issues} == {
        "room",
        "feature",
        "objective",
    }

    with pytest.raises(
        ConflictError, match="cannot replace accepted feature interaction content"
    ):
        project_dungeon_feature_interaction_enrichment(
            guide_with_feature,
            plan=plan,
            package=package,
            creative_continuity=continuity,
            context=feature_context,
            validation=feature_validation,
        )
