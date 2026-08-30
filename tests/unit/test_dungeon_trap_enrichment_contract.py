"""Exact-ID Workbench trap-enrichment contract coverage."""

import json
from copy import deepcopy

import pytest
from pydantic import ValidationError

from dm_assistant.errors import ConflictError
from dm_assistant.orchestration.dungeons import (
    DungeonGuidePlayerChoice,
    DungeonGuideRunnableContent,
    DungeonTrapContextSelection,
    DungeonTrapEnrichmentInput,
    DungeonTrapEnrichmentOutput,
    DungeonTrapIssue,
    DungeonTrapMechanic,
    DungeonTrapRoomContext,
    DungeonTrapValidationResult,
)
from dm_assistant.orchestration.dungeons.contracts import (
    DungeonDmGuide,
    DungeonGuidePuzzle,
)
from dm_assistant.orchestration.dungeons.service import (
    build_dungeon_dm_guide,
    build_dungeon_preparation_readiness,
    build_dungeon_trap_enrichment_input,
    project_dungeon_trap_enrichment,
    render_dungeon_dm_guide_text,
    validate_dungeon_trap_enrichment,
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
                        "trap": {
                            "name": "Brine Vent",
                            "challenge": "high",
                        },
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


def _trap_output(*, package_id: str, room_id: str, trap_id: str) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "package_id": package_id,
        "room_id": room_id,
        "trap_id": trap_id,
        "observable_warning": "A polished arc on the floor follows the hanging counterweight's reach.",
        "trigger": "Opening the inner sluice door pulls the counterweight across the vestibule.",
        "effect_narration": "The padded weight sweeps low across the marked arc and drives anyone there toward the wet threshold.",
        "detection_method": "Following the door chain upward reveals that it shares a pulley with the hanging weight.",
        "disable_operation": "Secure the weight to its wall ring or lift the door chain free of the shared pulley before opening the door.",
        "consequences": [
            "Loose carried objects slide into the shallow runoff at the threshold.",
            "A swept character ends on the vestibule side of the still-closed inner door.",
        ],
        "reset_or_recovery": "Closing the door slowly lowers the weight to its start; objects in the shallow runoff remain reachable.",
    }


def _accepted_prior_content(guide: DungeonDmGuide) -> DungeonDmGuide:
    content = DungeonGuideRunnableContent(
        situation="Accepted observable setup.",
        adjudication="Accepted adjudication that the trap task must not replace.",
        player_choices=(
            DungeonGuidePlayerChoice(
                action="Use the accepted local mechanism.",
                outcome="The accepted scene advances.",
            ),
            DungeonGuidePlayerChoice(
                action="Use the accepted alternate approach.",
                outcome="The accepted alternate also advances the scene.",
            ),
        ),
    )
    exploration_room = next(
        room for room in guide.rooms if room.encounter_slot is not None
    )
    feature = guide.features[0]
    puzzle_room = next(room for room in guide.rooms if room.role.value == "puzzle")
    puzzle_reference = puzzle_room.map_reference
    document = guide.model_dump(mode="python")
    document["rooms"] = tuple(
        room.model_copy(update={"encounter_content": content})
        if room.room_id == exploration_room.room_id
        else room
        for room in guide.rooms
    )
    document["features"] = tuple(
        item.model_copy(update={"content": content})
        if item.marker_id == feature.marker_id
        else item
        for item in guide.features
    )
    document["puzzles"] = (
        DungeonGuidePuzzle(
            content_ref="accepted_float_alignment",
            room_id=puzzle_room.room_id,
            map_reference=puzzle_reference,
            name="Three Copper Floats",
            solution="Align the floats with the three etched tide marks.",
            content=content,
        ),
    )
    return DungeonDmGuide.model_validate(document)


def test_exact_trap_context_joins_marker_guide_geometry_and_deterministic_mechanics() -> (
    None
):
    plan, request, package = _copper_tide_package()
    compiled = compile_dungeon_plan(plan)
    assert compiled.certificate is not None
    assert compiled.mechanics_plan is not None
    room_ids = {item.ref: item.room_id for item in compiled.certificate.rooms}
    trap_ids = {item.room_id: item.id for item in compiled.mechanics_plan.room_traps}
    guide = build_dungeon_dm_guide(request, package, plan)
    selection = DungeonTrapContextSelection(
        room_id=room_ids["sluice"],
        trap_id=trap_ids[room_ids["sluice"]],
        stakes="The sweep scatters supplies and repositions characters but never seals the only route.",
        constraints=(
            "Keep the door chain, shared pulley, and one padded counterweight as the complete mechanism",
            "Do not invent numeric difficulty values",
            "Permit more than one practical disable operation",
        ),
    )

    context = build_dungeon_trap_enrichment_input(package, guide, selection)

    room = next(item for item in package.rooms if item.id == room_ids["sluice"])
    marker = next(
        item
        for item in package.room_mechanic_markers
        if item.id == trap_ids[room_ids["sluice"]]
    )
    guide_trap = next(item for item in guide.traps if item.marker_id == marker.id)
    assert context.package_id == package.id
    assert context.room == DungeonTrapRoomContext(
        room_id=room.id,
        floor_id=room.floor_id,
        boundary=room.boundary,
        capacity=room.capacity,
    )
    assert context.trap == DungeonTrapMechanic(
        trap_id=marker.id,
        room_id=marker.room_id,
        floor_id=marker.floor_id,
        position=marker.position,
        name=guide_trap.name,
        current_warning=None,
        current_trigger=None,
        current_effect=None,
        current_detection=None,
        current_disable=None,
        current_consequences=(),
        current_reset_or_recovery=None,
        detection_difficulty=guide_trap.detection_difficulty,
        disable_difficulty=guide_trap.disable_difficulty,
    )
    assert context.stakes == selection.stakes
    assert context.constraints == selection.constraints

    input_schema = str(DungeonTrapEnrichmentInput.model_json_schema())
    output_schema = str(DungeonTrapEnrichmentOutput.model_json_schema())
    assert "detection_difficulty" in input_schema
    assert "disable_difficulty" in input_schema
    assert "detection_difficulty" not in output_schema
    assert "disable_difficulty" not in output_schema
    assert "DungeonPlan" not in input_schema
    assert "topology" not in output_schema
    assert "puzzle_content" not in output_schema

    with pytest.raises(ConflictError, match="unknown exact trap room"):
        build_dungeon_trap_enrichment_input(
            package,
            guide,
            selection.model_copy(update={"room_id": "room_from_another_package"}),
        )
    with pytest.raises(ConflictError, match="unknown exact room trap"):
        build_dungeon_trap_enrichment_input(
            package,
            guide,
            selection.model_copy(update={"trap_id": "trap_from_another_package"}),
        )
    with pytest.raises(ConflictError, match="outside the selected trap room"):
        build_dungeon_trap_enrichment_input(
            package,
            guide,
            selection.model_copy(update={"trap_id": trap_ids[room_ids["vault"]]}),
        )


def test_trap_output_rejects_foreign_ids_numeric_dcs_and_cross_task_mutation() -> None:
    plan, request, package = _copper_tide_package()
    compiled = compile_dungeon_plan(plan)
    assert compiled.certificate is not None
    assert compiled.mechanics_plan is not None
    room_ids = {item.ref: item.room_id for item in compiled.certificate.rooms}
    trap_id = next(
        item.id
        for item in compiled.mechanics_plan.room_traps
        if item.room_id == room_ids["sluice"]
    )
    context = build_dungeon_trap_enrichment_input(
        package,
        build_dungeon_dm_guide(request, package, plan),
        DungeonTrapContextSelection(
            room_id=room_ids["sluice"],
            trap_id=trap_id,
            stakes="Failure scatters supplies without sealing the route.",
        ),
    )
    valid_document = _trap_output(
        package_id=package.id,
        room_id=room_ids["sluice"],
        trap_id=trap_id,
    )
    output = DungeonTrapEnrichmentOutput.model_validate(valid_document)
    assert validate_dungeon_trap_enrichment(context, output).accepted_output == output

    numeric_dc = deepcopy(valid_document)
    numeric_dc["detection_method"] = "A DC 99 inspection reveals the shared pulley."
    with pytest.raises(ValidationError, match="cannot author numeric difficulty"):
        DungeonTrapEnrichmentOutput.model_validate(numeric_dc)

    for foreign_field, value in (
        ("topology", {"replace": True}),
        ("puzzle_content", {"replace": True}),
        ("detection_difficulty", 99),
        ("disable_difficulty", 99),
    ):
        mutation = deepcopy(valid_document)
        mutation[foreign_field] = value
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            DungeonTrapEnrichmentOutput.model_validate(mutation)

    mismatch = deepcopy(valid_document)
    mismatch["package_id"] = "package_other"
    mismatch["room_id"] = "room_other"
    mismatch["trap_id"] = "trap_other"
    rejected = validate_dungeon_trap_enrichment(
        context, DungeonTrapEnrichmentOutput.model_validate(mismatch)
    )
    assert rejected == DungeonTrapValidationResult(
        schema_version="1.0.0",
        issues=(
            DungeonTrapIssue(
                code="trap_enrichment.package_mismatch",
                component_id="package_other",
                message="Trap enrichment targets a different dungeon package.",
            ),
            DungeonTrapIssue(
                code="trap_enrichment.room_mismatch",
                component_id="room_other",
                message="Trap enrichment targets a different exact room.",
            ),
            DungeonTrapIssue(
                code="trap_enrichment.trap_mismatch",
                component_id="trap_other",
                message="Trap enrichment targets a different exact trap.",
            ),
        ),
    )


def test_accepted_trap_projects_only_selected_entry_and_clears_only_its_blockers() -> (
    None
):
    plan, request, package = _copper_tide_package()
    compiled = compile_dungeon_plan(plan)
    assert compiled.certificate is not None
    assert compiled.mechanics_plan is not None
    room_ids = {item.ref: item.room_id for item in compiled.certificate.rooms}
    trap_ids = {item.room_id: item.id for item in compiled.mechanics_plan.room_traps}
    base_guide = _accepted_prior_content(build_dungeon_dm_guide(request, package, plan))
    target_trap_id = trap_ids[room_ids["sluice"]]
    context = build_dungeon_trap_enrichment_input(
        package,
        base_guide,
        DungeonTrapContextSelection(
            room_id=room_ids["sluice"],
            trap_id=target_trap_id,
            stakes="The sweep scatters supplies and repositions characters but never seals the only route.",
            constraints=("Do not invent numeric difficulty values",),
        ),
    )
    output = DungeonTrapEnrichmentOutput.model_validate(
        _trap_output(
            package_id=package.id,
            room_id=room_ids["sluice"],
            trap_id=target_trap_id,
        )
    )
    validation = validate_dungeon_trap_enrichment(context, output)
    package_before = package.model_dump_json()
    readiness_before = build_dungeon_preparation_readiness(base_guide)
    assert readiness_before is not None

    guide = project_dungeon_trap_enrichment(
        base_guide,
        plan=plan,
        package=package,
        context=context,
        validation=validation,
    )

    assert package.model_dump_json() == package_before
    assert guide.map_callouts == base_guide.map_callouts
    assert guide.rooms == base_guide.rooms
    assert guide.connections == base_guide.connections
    assert guide.dependencies == base_guide.dependencies
    assert guide.puzzles == base_guide.puzzles
    assert guide.features == base_guide.features
    assert guide.objectives == base_guide.objectives
    assert guide.content_issues == base_guide.content_issues
    target = next(item for item in guide.traps if item.marker_id == target_trap_id)
    assert target.warning == output.observable_warning
    assert target.trigger == output.trigger
    assert target.effect == output.effect_narration
    assert target.detection == output.detection_method
    assert target.disable == output.disable_operation
    assert target.consequences == output.consequences
    assert target.reset_or_recovery == output.reset_or_recovery
    assert target.detection_difficulty == context.trap.detection_difficulty
    assert target.disable_difficulty == context.trap.disable_difficulty
    rendered_guide = render_dungeon_dm_guide_text(guide)
    assert f"**Warning:** {output.observable_warning}" in rendered_guide
    assert f"**Trigger:** {output.trigger}" in rendered_guide
    assert f"**Consequence:** {output.effect_narration}" in rendered_guide
    assert f"**Detect:** DC {target.detection_difficulty}" in rendered_guide
    assert f"**Disable:** DC {target.disable_difficulty}" in rendered_guide
    assert f"**Further consequence:** {output.consequences[0]}" in rendered_guide
    assert f"**Reset / recovery:** {output.reset_or_recovery}" in rendered_guide
    assert all(
        item == next(old for old in base_guide.traps if old.marker_id == item.marker_id)
        for item in guide.traps
        if item.marker_id != target_trap_id
    )

    readiness = build_dungeon_preparation_readiness(guide)
    assert readiness is not None
    target_codes_before = {
        item.code
        for item in readiness_before.diagnostics
        if item.component_id == target_trap_id
    }
    assert target_codes_before == {
        "dungeon_preparation.trap_effect_unknown",
        "dungeon_preparation.trap_method_unknown",
    }
    assert not any(
        item.component_id == target_trap_id for item in readiness.diagnostics
    )
    assert (
        tuple(
            item
            for item in readiness_before.diagnostics
            if item.component_id != target_trap_id
        )
        == readiness.diagnostics
    )

    with pytest.raises(ConflictError, match="cannot replace accepted trap content"):
        project_dungeon_trap_enrichment(
            guide,
            plan=plan,
            package=package,
            context=context,
            validation=validation,
        )
