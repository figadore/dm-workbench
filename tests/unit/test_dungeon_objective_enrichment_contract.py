"""Provider-free exact-ID objective-enrichment contract coverage."""

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
    DungeonGuidePlayerChoice,
    DungeonGuideRunnableContent,
    DungeonObjectiveAcceptedMechanic,
    DungeonObjectiveContextSelection,
    DungeonObjectiveEnrichmentInput,
    DungeonObjectiveEnrichmentOutput,
    DungeonObjectiveIssue,
    DungeonObjectiveResolution,
    DungeonObjectiveRoomContext,
    DungeonObjectiveTarget,
    DungeonObjectiveValidationResult,
)
from dm_assistant.orchestration.dungeons.continuity import (
    derive_dungeon_creative_continuity,
)
from dm_assistant.orchestration.dungeons.contracts import (
    DungeonDmGuide,
    DungeonGuidePuzzle,
)
from dm_assistant.orchestration.dungeons.service import (
    build_dungeon_dm_guide,
    build_dungeon_objective_enrichment_input,
    build_dungeon_preparation_readiness,
    project_dungeon_objective_enrichment,
    render_dungeon_dm_guide_text,
    validate_dungeon_objective_enrichment,
)
from dm_dungeon import (
    DungeonPackage,
    DungeonPlan,
    LayoutRequest,
    compile_dungeon_plan,
    generate_layout,
)
from dm_dungeon.layout import ORTHOGONAL_LAYOUT_GENERATOR_VERSION


def _copper_tide_package() -> tuple[DungeonPlan, LayoutRequest, DungeonPackage]:
    plan = DungeonPlan.model_validate_json(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "title": "Copper Tide Foundry",
                "premise": "Recover a synthetic tide gauge from an abandoned tidal foundry.",
                "themes": ["salt-stained copper", "slow tidal machinery"],
                "rooms": [
                    {
                        "ref": "sluice",
                        "name": "Sluice Vestibule",
                        "role": "entrance",
                        "purpose": "Introduce the foundry's tide-driven mechanisms.",
                    },
                    {
                        "ref": "casting",
                        "name": "Casting Walk",
                        "role": "exploration",
                        "purpose": "Cross a wet casting channel using the overhead ladle rail.",
                        "encounter": "exploration",
                    },
                    {
                        "ref": "calibration",
                        "name": "Calibration Loft",
                        "role": "puzzle",
                        "purpose": "Align three floats to release the gauge cabinet.",
                    },
                    {
                        "ref": "vault",
                        "name": "Gauge Vault",
                        "role": "objective",
                        "purpose": "Hold the named synthetic tide gauge.",
                    },
                ],
                "critical_path": ["sluice", "casting", "calibration", "vault"],
                "room_contents": [
                    {
                        "room_ref": "sluice",
                        "trap": {
                            "name": "Counterweight Sweep",
                            "challenge": "moderate",
                        },
                    },
                    {
                        "room_ref": "casting",
                        "feature": {
                            "kind": "other",
                            "name": "Overhead Ladle Rail",
                            "description": "A hand chain moves an empty copper ladle above the channel.",
                        },
                    },
                    {
                        "room_ref": "vault",
                        "trap": {"name": "Brine Vent", "challenge": "high"},
                        "objective": "Synthetic Tide Gauge",
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
        package_id="package_copper_tide_foundry",
        brief=compiled.brief,
        topology=compiled.topology,
        certificate=compiled.certificate,
        seed=714000023,
        generator_version=ORTHOGONAL_LAYOUT_GENERATOR_VERSION,
        mechanics_plan=compiled.mechanics_plan,
        floor_bounds=compiled.floor_bounds,
    )
    layout = generate_layout(request)
    assert layout.success and layout.package is not None
    return plan, request, layout.package


def _creative_continuity(plan: DungeonPlan) -> DungeonCreativeContinuityProjection:
    payload = DungeonGenerationContext(
        context_version="1.0.0",
        prompt_input_sha256="7" * 64,
        preparation_owner_id="dm",
        context_provenance="synthetic_standalone",
    ).model_dump(mode="json")
    return derive_dungeon_creative_continuity(
        GenerationContextEnvelope(
            context_kind="dungeon_generation",
            payload_version="1.0.0",
            payload=payload,
            payload_sha256=canonical_json_sha256(payload),
        ),
        plan,
    )


def _content(label: str) -> DungeonGuideRunnableContent:
    return DungeonGuideRunnableContent(
        situation=f"Accepted observable {label} setup.",
        adjudication=f"Accepted {label} adjudication.",
        player_choices=(
            DungeonGuidePlayerChoice(
                action=f"Use the primary accepted {label} approach.",
                outcome=f"The primary {label} outcome advances the scene.",
            ),
            DungeonGuidePlayerChoice(
                action=f"Use the alternate accepted {label} approach.",
                outcome=f"The alternate {label} outcome also advances the scene.",
            ),
        ),
    )


def _accepted_mechanics_guide(
    guide: DungeonDmGuide,
) -> tuple[DungeonDmGuide, tuple[str, ...]]:
    exploration_room = next(
        room for room in guide.rooms if room.encounter_slot is not None
    )
    puzzle_room = next(room for room in guide.rooms if room.role.value == "puzzle")
    feature = guide.features[0]
    document = guide.model_dump(mode="python")
    document["rooms"] = tuple(
        room.model_copy(update={"encounter_content": _content("exploration")})
        if room.room_id == exploration_room.room_id
        else room
        for room in guide.rooms
    )
    document["features"] = tuple(
        item.model_copy(update={"content": _content("feature")})
        if item.marker_id == feature.marker_id
        else item
        for item in guide.features
    )
    document["puzzles"] = (
        DungeonGuidePuzzle(
            content_ref="accepted_float_alignment",
            room_id=puzzle_room.room_id,
            map_reference=puzzle_room.map_reference,
            name="Three Copper Floats",
            solution="Align the floats with the three etched tide marks.",
            content=_content("puzzle"),
        ),
    )
    document["traps"] = tuple(
        trap.model_copy(
            update={
                "warning": f"Accepted warning for {trap.name}.",
                "trigger": f"Accepted trigger for {trap.name}.",
                "effect": f"Accepted effect for {trap.name}.",
                "detection": f"Accepted detection method for {trap.name}.",
                "disable": f"Accepted disable operation for {trap.name}.",
                "consequences": (f"Accepted consequence for {trap.name}.",),
                "reset_or_recovery": f"Accepted recovery for {trap.name}.",
            }
        )
        for trap in guide.traps
    )
    accepted = DungeonDmGuide.model_validate(document)
    assert exploration_room.encounter_slot_id is not None
    return accepted, (
        exploration_room.encounter_slot_id,
        feature.marker_id,
        *(trap.marker_id for trap in guide.traps),
    )


def _objective_output(
    *, package_id: str, room_id: str, objective_id: str, mechanic_ids: tuple[str, ...]
) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "package_id": package_id,
        "room_id": room_id,
        "objective_id": objective_id,
        "observable_goal": "The synthetic tide gauge rests in a slotted cradle while its three copper floats continue to rise and fall.",
        "resolution_guidance": "The gauge can be secured once the cradle is steady; reward plans that reuse understood foundry mechanisms without requiring one prescribed sequence.",
        "resolutions": [
            {
                "mechanic_ids": [mechanic_ids[0], mechanic_ids[1]],
                "action": "Balance the ladle rail against the calibrated floats and lift the gauge straight from its cradle.",
                "outcome": "The gauge comes free intact, and the party can carry it back across the stabilized casting walk.",
            },
            {
                "mechanic_ids": [mechanic_ids[2]],
                "action": "Brace the cradle with the secured counterweight line before releasing its retaining pin.",
                "outcome": "The cradle stays level long enough to remove the gauge, but the line must be recovered before retreat.",
            },
        ],
        "setback_or_aftermath": "If the cradle tilts, brine fills its catch basin and the party must drain it before trying again; the gauge is not destroyed.",
    }


def test_exact_objective_context_joins_marker_guide_geometry_and_accepted_mechanics() -> (
    None
):
    plan, request, package = _copper_tide_package()
    compiled = compile_dungeon_plan(plan)
    assert compiled.certificate is not None
    assert compiled.mechanics_plan is not None
    room_ids = {item.ref: item.room_id for item in compiled.certificate.rooms}
    objective_plan = compiled.mechanics_plan.room_objectives[0]
    puzzle_id = room_ids["calibration"]
    guide, other_mechanic_ids = _accepted_mechanics_guide(
        build_dungeon_dm_guide(request, package, plan)
    )
    mechanic_ids = (puzzle_id, *other_mechanic_ids)
    selection = DungeonObjectiveContextSelection(
        room_id=room_ids["vault"],
        objective_id=objective_plan.id,
        mechanic_ids=mechanic_ids,
        stakes="Recover the gauge intact; a setback costs time but never destroys the named objective.",
        constraints=(
            "Offer at least two credible resolutions",
            "Do not invent new machinery or alter accepted mechanics",
            "Do not make one prior mechanic the mandatory solution",
        ),
    )

    continuity = _creative_continuity(plan)
    context = build_dungeon_objective_enrichment_input(
        package,
        guide,
        selection,
        plan=plan,
        creative_continuity=continuity,
    )

    room = next(item for item in package.rooms if item.id == room_ids["vault"])
    marker = next(
        item for item in package.room_mechanic_markers if item.id == objective_plan.id
    )
    guide_objective = guide.objectives[0]
    assert context.package_id == package.id
    assert context.continuity.projection_sha256 == continuity.projection_sha256
    assert context.continuity.campaign_lore_status == "unknown"
    assert context.continuity.selected_facts == ()
    assert context.continuity.source_links == ()
    assert {room.room_ref for room in context.continuity.room_intents} == {"vault"}
    assert {item.name for item in context.continuity.objective_intents} == {
        "Synthetic Tide Gauge"
    }
    assert context.room == DungeonObjectiveRoomContext(
        room_id=room.id,
        floor_id=room.floor_id,
        boundary=room.boundary,
        capacity=room.capacity,
    )
    assert context.objective == DungeonObjectiveTarget(
        objective_id=marker.id,
        room_id=marker.room_id,
        floor_id=marker.floor_id,
        position=marker.position,
        kind=guide_objective.kind,
        name=guide_objective.name,
        current_situation=None,
        current_adjudication=None,
        current_resolutions=(),
    )
    assert (
        tuple(item.mechanic_id for item in context.accepted_mechanics) == mechanic_ids
    )
    assert {item.kind for item in context.accepted_mechanics} == {
        "puzzle",
        "exploration",
        "feature",
        "trap",
    }
    puzzle_summary = context.accepted_mechanics[0]
    assert puzzle_summary == DungeonObjectiveAcceptedMechanic(
        mechanic_id=puzzle_id,
        room_id=next(room.room_id for room in guide.puzzles),
        kind="puzzle",
        name="Three Copper Floats",
        observable_summary="Accepted observable puzzle setup.",
        resolution_summary="Accepted puzzle adjudication.",
        outcome_summaries=(
            "The primary puzzle outcome advances the scene.",
            "The alternate puzzle outcome also advances the scene.",
        ),
    )
    assert context.stakes == selection.stakes
    assert context.constraints == selection.constraints

    input_schema = str(DungeonObjectiveEnrichmentInput.model_json_schema())
    output_schema = str(DungeonObjectiveEnrichmentOutput.model_json_schema())
    assert "accepted_mechanics" in input_schema
    assert "continuity" in input_schema
    assert "DungeonPlan" not in input_schema
    assert "topology" not in output_schema
    assert "trap_content" not in output_schema
    assert "objective_name" not in output_schema

    with pytest.raises(ConflictError, match="unknown exact objective room"):
        build_dungeon_objective_enrichment_input(
            package,
            guide,
            selection.model_copy(update={"room_id": "room_from_another_package"}),
            plan=plan,
            creative_continuity=continuity,
        )
    with pytest.raises(ConflictError, match="unknown exact room objective"):
        build_dungeon_objective_enrichment_input(
            package,
            guide,
            selection.model_copy(update={"objective_id": "objective_other"}),
            plan=plan,
            creative_continuity=continuity,
        )
    with pytest.raises(ConflictError, match="unknown or unaccepted exact mechanic"):
        build_dungeon_objective_enrichment_input(
            package,
            guide,
            selection.model_copy(
                update={"mechanic_ids": ("mechanic_from_another_package",)}
            ),
            plan=plan,
            creative_continuity=continuity,
        )


def test_objective_output_rejects_foreign_ids_mechanics_and_cross_task_mutation() -> (
    None
):
    plan, request, package = _copper_tide_package()
    compiled = compile_dungeon_plan(plan)
    assert compiled.certificate is not None
    assert compiled.mechanics_plan is not None
    room_ids = {item.ref: item.room_id for item in compiled.certificate.rooms}
    objective_id = compiled.mechanics_plan.room_objectives[0].id
    puzzle_id = room_ids["calibration"]
    guide, other_mechanic_ids = _accepted_mechanics_guide(
        build_dungeon_dm_guide(request, package, plan)
    )
    mechanic_ids = (puzzle_id, *other_mechanic_ids)
    continuity = _creative_continuity(plan)
    context = build_dungeon_objective_enrichment_input(
        package,
        guide,
        DungeonObjectiveContextSelection(
            room_id=room_ids["vault"],
            objective_id=objective_id,
            mechanic_ids=mechanic_ids,
            stakes="A setback costs time but does not destroy the gauge.",
        ),
        plan=plan,
        creative_continuity=continuity,
    )
    valid_document = _objective_output(
        package_id=package.id,
        room_id=room_ids["vault"],
        objective_id=objective_id,
        mechanic_ids=mechanic_ids,
    )
    output = DungeonObjectiveEnrichmentOutput.model_validate(valid_document)
    assert (
        validate_dungeon_objective_enrichment(context, output).accepted_output == output
    )

    for foreign_field, value in (
        ("topology", {"replace": True}),
        ("trap_content", {"replace": True}),
        ("objective_name", "A different objective"),
        ("objective_kind", "optional_objective"),
    ):
        mutation = deepcopy(valid_document)
        mutation[foreign_field] = value
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            DungeonObjectiveEnrichmentOutput.model_validate(mutation)

    invalid_mechanic = deepcopy(valid_document)
    resolutions = invalid_mechanic["resolutions"]
    assert isinstance(resolutions, list)
    resolutions[0]["mechanic_ids"] = ["foreign_mechanic"]
    rejected_mechanic = validate_dungeon_objective_enrichment(
        context, DungeonObjectiveEnrichmentOutput.model_validate(invalid_mechanic)
    )
    assert rejected_mechanic.issues == (
        DungeonObjectiveIssue(
            code="objective_enrichment.mechanic_invalid",
            component_id="foreign_mechanic",
            message="Objective resolution uses a mechanic outside the accepted context.",
        ),
    )

    mismatch = deepcopy(valid_document)
    mismatch["package_id"] = "package_other"
    mismatch["room_id"] = "room_other"
    mismatch["objective_id"] = "objective_other"
    rejected = validate_dungeon_objective_enrichment(
        context, DungeonObjectiveEnrichmentOutput.model_validate(mismatch)
    )
    assert rejected == DungeonObjectiveValidationResult(
        schema_version="1.0.0",
        issues=(
            DungeonObjectiveIssue(
                code="objective_enrichment.package_mismatch",
                component_id="package_other",
                message="Objective enrichment targets a different dungeon package.",
            ),
            DungeonObjectiveIssue(
                code="objective_enrichment.room_mismatch",
                component_id="room_other",
                message="Objective enrichment targets a different exact room.",
            ),
            DungeonObjectiveIssue(
                code="objective_enrichment.objective_mismatch",
                component_id="objective_other",
                message="Objective enrichment targets a different exact objective.",
            ),
        ),
    )


def test_accepted_objective_projects_only_selected_entry_and_clears_only_its_blocker() -> (
    None
):
    plan, request, package = _copper_tide_package()
    compiled = compile_dungeon_plan(plan)
    assert compiled.certificate is not None
    assert compiled.mechanics_plan is not None
    room_ids = {item.ref: item.room_id for item in compiled.certificate.rooms}
    objective_id = compiled.mechanics_plan.room_objectives[0].id
    puzzle_id = room_ids["calibration"]
    guide, other_mechanic_ids = _accepted_mechanics_guide(
        build_dungeon_dm_guide(request, package, plan)
    )
    mechanic_ids = (puzzle_id, *other_mechanic_ids)
    continuity = _creative_continuity(plan)
    context = build_dungeon_objective_enrichment_input(
        package,
        guide,
        DungeonObjectiveContextSelection(
            room_id=room_ids["vault"],
            objective_id=objective_id,
            mechanic_ids=mechanic_ids,
            stakes="Recover the gauge intact; setbacks cost time but do not destroy it.",
            constraints=("Offer at least two credible resolutions",),
        ),
        plan=plan,
        creative_continuity=continuity,
    )
    output = DungeonObjectiveEnrichmentOutput.model_validate(
        _objective_output(
            package_id=package.id,
            room_id=room_ids["vault"],
            objective_id=objective_id,
            mechanic_ids=mechanic_ids,
        )
    )
    validation = validate_dungeon_objective_enrichment(context, output)
    package_before = package.model_dump_json()
    readiness_before = build_dungeon_preparation_readiness(guide)
    assert readiness_before is not None

    enriched = project_dungeon_objective_enrichment(
        guide,
        plan=plan,
        package=package,
        creative_continuity=continuity,
        context=context,
        validation=validation,
    )

    assert package.model_dump_json() == package_before
    assert enriched.map_callouts == guide.map_callouts
    assert enriched.rooms == guide.rooms
    assert enriched.connections == guide.connections
    assert enriched.dependencies == guide.dependencies
    assert enriched.traps == guide.traps
    assert enriched.puzzles == guide.puzzles
    assert enriched.features == guide.features
    assert len(enriched.objectives) == len(guide.objectives) == 1
    target = enriched.objectives[0]
    assert target.marker_id == objective_id
    assert target.kind == guide.objectives[0].kind
    assert target.name == guide.objectives[0].name
    assert target.map_reference == guide.objectives[0].map_reference
    assert target.content is not None
    assert target.content.situation == output.observable_goal
    assert target.content.adjudication == (
        f"{output.resolution_guidance} Setback or aftermath: {output.setback_or_aftermath}"
    )
    assert target.content.player_choices == tuple(
        DungeonGuidePlayerChoice(action=item.action, outcome=item.outcome)
        for item in output.resolutions
    )
    assert all(
        isinstance(item, DungeonObjectiveResolution) for item in output.resolutions
    )
    rendered = render_dungeon_dm_guide_text(enriched)
    assert output.observable_goal in rendered
    assert output.resolutions[0].action in rendered
    assert output.setback_or_aftermath in rendered

    readiness = build_dungeon_preparation_readiness(enriched)
    assert readiness is not None
    objective_issue = next(
        item
        for item in guide.content_issues
        if item.kind == "objective" and item.room_ref == "vault"
    )
    assert enriched.content_issues == tuple(
        item for item in guide.content_issues if item != objective_issue
    )
    objective_diagnostic = next(
        item
        for item in readiness_before.diagnostics
        if item.component_id == objective_issue.target_ref
        and "runnable guide content" in item.message
    )
    assert readiness.diagnostics == tuple(
        item for item in readiness_before.diagnostics if item != objective_diagnostic
    )

    with pytest.raises(
        ConflictError, match="cannot replace accepted objective content"
    ):
        project_dungeon_objective_enrichment(
            enriched,
            plan=plan,
            package=package,
            creative_continuity=continuity,
            context=context,
            validation=validation,
        )
