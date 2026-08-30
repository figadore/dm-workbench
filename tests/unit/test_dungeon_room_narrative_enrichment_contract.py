"""Provider-free exact-ID room-narrative enrichment contract coverage."""

import json
from copy import deepcopy

import pytest
from pydantic import ValidationError

from dm_assistant.errors import ConflictError
from dm_assistant.orchestration.dungeons import (
    DungeonGuidePlayerChoice,
    DungeonGuideRunnableContent,
    DungeonRoomNarrativeContextSelection,
    DungeonRoomNarrativeEnrichmentInput,
    DungeonRoomNarrativeEnrichmentOutput,
    DungeonRoomNarrativeIssue,
    DungeonRoomNarrativeRoomOutput,
    DungeonRoomNarrativeValidationResult,
)
from dm_assistant.orchestration.dungeons.contracts import (
    DungeonDmGuide,
    DungeonGuidePuzzle,
)
from dm_assistant.orchestration.dungeons.service import (
    build_dungeon_dm_guide,
    build_dungeon_preparation_readiness,
    build_dungeon_room_narrative_enrichment_input,
    project_dungeon_room_narrative_enrichment,
    validate_dungeon_room_narrative_enrichment,
)
from dm_dungeon import (
    DungeonPackage,
    DungeonPlan,
    LayoutRequest,
    compile_dungeon_plan,
    generate_layout,
)
from dm_dungeon.layout import ORTHOGONAL_LAYOUT_GENERATOR_VERSION


def _moonseed_package() -> tuple[DungeonPlan, LayoutRequest, DungeonPackage]:
    plan = DungeonPlan.model_validate_json(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "title": "Moonseed Aviary",
                "premise": "Recover a synthetic moonseed from a wind-torn cliffside aviary.",
                "themes": ["silver grass", "woven reed vanes"],
                "rooms": [
                    {
                        "ref": "perch",
                        "name": "Broken Perch",
                        "role": "entrance",
                        "purpose": "Establish the open, wind-battered aviary.",
                    },
                    {
                        "ref": "canopy",
                        "name": "Sail Canopy",
                        "role": "exploration",
                        "purpose": "Cross beneath shifting reed sails.",
                        "encounter": "exploration",
                    },
                    {
                        "ref": "choir",
                        "name": "Whistle Choir",
                        "role": "puzzle",
                        "purpose": "Tune three wind pipes to open the seed house.",
                    },
                    {
                        "ref": "seedhouse",
                        "name": "Moonseed House",
                        "role": "objective",
                        "purpose": "Hold the named synthetic moonseed.",
                    },
                ],
                "critical_path": ["perch", "canopy", "choir", "seedhouse"],
                "room_contents": [
                    {
                        "room_ref": "perch",
                        "trap": {"name": "Snapped Tether", "challenge": "moderate"},
                    },
                    {
                        "room_ref": "canopy",
                        "feature": {
                            "kind": "other",
                            "name": "Reed Sail Winch",
                            "description": "A low winch changes the angle of the woven overhead sails.",
                        },
                    },
                    {"room_ref": "seedhouse", "objective": "Synthetic Moonseed"},
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
        package_id="package_moonseed_aviary",
        brief=compiled.brief,
        topology=compiled.topology,
        certificate=compiled.certificate,
        seed=714000029,
        generator_version=ORTHOGONAL_LAYOUT_GENERATOR_VERSION,
        mechanics_plan=compiled.mechanics_plan,
        floor_bounds=compiled.floor_bounds,
    )
    layout = generate_layout(request)
    assert layout.success and layout.package is not None
    return plan, request, layout.package


def _content(label: str) -> DungeonGuideRunnableContent:
    return DungeonGuideRunnableContent(
        situation=f"Observable accepted {label} setup.",
        adjudication=f"Hidden accepted {label} adjudication.",
        player_choices=(
            DungeonGuidePlayerChoice(
                action=f"Use the first {label} approach.",
                outcome=f"Hidden first {label} outcome.",
            ),
            DungeonGuidePlayerChoice(
                action=f"Use the second {label} approach.",
                outcome=f"Hidden second {label} outcome.",
            ),
        ),
    )


def _accepted_guide(
    plan: DungeonPlan, request: LayoutRequest, package: DungeonPackage
) -> tuple[DungeonDmGuide, dict[str, str]]:
    compiled = compile_dungeon_plan(plan)
    assert compiled.certificate is not None
    room_ids = {item.ref: item.room_id for item in compiled.certificate.rooms}
    guide = build_dungeon_dm_guide(request, package, plan)
    exploration_room = next(
        room for room in guide.rooms if room.room_id == room_ids["canopy"]
    )
    feature = next(
        item for item in guide.features if item.room_id == room_ids["canopy"]
    )
    trap = next(item for item in guide.traps if item.room_id == room_ids["perch"])
    objective = next(
        item for item in guide.objectives if item.room_id == room_ids["seedhouse"]
    )
    puzzle_room = next(
        room for room in guide.rooms if room.room_id == room_ids["choir"]
    )
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
    document["traps"] = tuple(
        item.model_copy(
            update={
                "warning": "Observable accepted trap warning.",
                "trigger": "Hidden accepted trap trigger.",
                "effect": "Hidden accepted trap effect.",
                "detection": "Hidden accepted trap detection.",
                "disable": "Hidden accepted trap disable operation.",
                "consequences": ("Hidden accepted trap consequence.",),
            }
        )
        if item.marker_id == trap.marker_id
        else item
        for item in guide.traps
    )
    document["puzzles"] = (
        DungeonGuidePuzzle(
            content_ref="accepted_wind_pipe_tuning",
            room_id=puzzle_room.room_id,
            map_reference=puzzle_room.map_reference,
            name="Three Wind Pipes",
            solution="Hidden accepted puzzle solution.",
            content=_content("puzzle"),
        ),
    )
    document["objectives"] = tuple(
        item.model_copy(update={"content": _content("objective")})
        if item.marker_id == objective.marker_id
        else item
        for item in guide.objectives
    )
    return DungeonDmGuide.model_validate(document), room_ids


def _selection(room_ids: tuple[str, ...]) -> DungeonRoomNarrativeContextSelection:
    return DungeonRoomNarrativeContextSelection(
        room_ids=room_ids,
        tone=("bright but precarious", "wind carries every small sound"),
        constraints=(
            "Use only player-observable information",
            "Do not reveal triggers, solutions, or consequences",
            "Do not invent creatures or new mechanisms",
        ),
    )


def _output(package_id: str, room_ids: tuple[str, ...]) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "package_id": package_id,
        "rooms": [
            {
                "room_id": room_id,
                "read_aloud": f"Wind combs silver grass around {index} leaning reed frames, each trembling without falling.",
                "observable_framing": [
                    "Loose seed husks skitter toward the cliffward wall.",
                    "The nearest woven vane answers each gust with a dry rattle.",
                ],
            }
            for index, room_id in enumerate(room_ids, start=1)
        ],
    }


def test_room_narrative_context_contains_only_selected_geometry_state_and_observables() -> (
    None
):
    plan, request, package = _moonseed_package()
    guide, room_ids = _accepted_guide(plan, request, package)
    selected_ids = (room_ids["perch"], room_ids["canopy"], room_ids["seedhouse"])

    context = build_dungeon_room_narrative_enrichment_input(
        package, guide, _selection(selected_ids)
    )

    assert context.package_id == package.id
    assert tuple(room.room_id for room in context.rooms) == selected_ids
    package_rooms = {room.id: room for room in package.rooms}
    guide_rooms = {room.room_id: room for room in guide.rooms}
    for room in context.rooms:
        assert room.floor_id == package_rooms[room.room_id].floor_id
        assert room.boundary == package_rooms[room.room_id].boundary
        assert room.capacity == package_rooms[room.room_id].capacity
        assert room.name == guide_rooms[room.room_id].name
        assert room.role == guide_rooms[room.room_id].role
        assert room.current_read_aloud is None
        assert room.current_observable_framing == ()
    summaries = {
        (room.room_id, mechanic.kind): mechanic.observable_summary
        for room in context.rooms
        for mechanic in room.accepted_mechanics
    }
    assert summaries == {
        (room_ids["perch"], "trap"): "Observable accepted trap warning.",
        (room_ids["canopy"], "exploration"): "Observable accepted exploration setup.",
        (room_ids["canopy"], "feature"): "Observable accepted feature setup.",
        (room_ids["seedhouse"], "objective"): "Observable accepted objective setup.",
    }
    serialized = context.model_dump_json()
    assert "Hidden accepted" not in serialized
    assert context.tone == _selection(selected_ids).tone
    assert context.constraints == _selection(selected_ids).constraints

    input_schema = str(DungeonRoomNarrativeEnrichmentInput.model_json_schema())
    output_schema = str(DungeonRoomNarrativeEnrichmentOutput.model_json_schema())
    assert "DungeonPlan" not in input_schema
    assert "preparation_note" not in input_schema
    assert "adjudication" not in input_schema
    assert "topology" not in output_schema
    assert "accepted_mechanics" not in output_schema
    assert "objective_content" not in output_schema

    with pytest.raises(ConflictError, match="unknown exact narrative room"):
        build_dungeon_room_narrative_enrichment_input(
            package, guide, _selection(("room_from_another_package",))
        )
    with pytest.raises(ConflictError, match="accepted local mechanics"):
        build_dungeon_room_narrative_enrichment_input(
            package,
            build_dungeon_dm_guide(request, package, plan),
            _selection((room_ids["canopy"],)),
        )
    with pytest.raises(ValidationError, match="unique exact room IDs"):
        _selection((room_ids["perch"], room_ids["perch"]))


def test_room_narrative_output_rejects_foreign_duplicate_and_cross_task_targets() -> (
    None
):
    plan, request, package = _moonseed_package()
    guide, room_ids = _accepted_guide(plan, request, package)
    selected_ids = (room_ids["perch"], room_ids["canopy"])
    context = build_dungeon_room_narrative_enrichment_input(
        package, guide, _selection(selected_ids)
    )
    valid_document = _output(package.id, selected_ids)
    output = DungeonRoomNarrativeEnrichmentOutput.model_validate(valid_document)
    assert (
        validate_dungeon_room_narrative_enrichment(context, output).accepted_output
        == output
    )

    for field, value in (
        ("topology", {"replace": True}),
        ("trap_content", {"replace": True}),
        ("objective_content", {"replace": True}),
        ("preparation_approval", True),
    ):
        mutation = deepcopy(valid_document)
        mutation[field] = value
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            DungeonRoomNarrativeEnrichmentOutput.model_validate(mutation)

    duplicate = deepcopy(valid_document)
    rooms = duplicate["rooms"]
    assert isinstance(rooms, list)
    rooms[1]["room_id"] = rooms[0]["room_id"]
    with pytest.raises(ValidationError, match="unique exact room IDs"):
        DungeonRoomNarrativeEnrichmentOutput.model_validate(duplicate)

    mismatch = deepcopy(valid_document)
    mismatch["package_id"] = "package_other"
    mismatch_rooms = mismatch["rooms"]
    assert isinstance(mismatch_rooms, list)
    mismatch_rooms[0]["room_id"] = "room_other"
    rejected = validate_dungeon_room_narrative_enrichment(
        context, DungeonRoomNarrativeEnrichmentOutput.model_validate(mismatch)
    )
    assert rejected == DungeonRoomNarrativeValidationResult(
        schema_version="1.0.0",
        issues=(
            DungeonRoomNarrativeIssue(
                code="room_narrative_enrichment.package_mismatch",
                component_id="package_other",
                message="Room narrative enrichment targets a different dungeon package.",
            ),
            DungeonRoomNarrativeIssue(
                code="room_narrative_enrichment.room_invalid",
                component_id="room_other",
                message="Room narrative enrichment targets a room outside the selected context.",
            ),
            DungeonRoomNarrativeIssue(
                code="room_narrative_enrichment.room_missing",
                component_id=room_ids["perch"],
                message="Room narrative enrichment omits a selected exact room.",
            ),
        ),
    )


def test_accepted_room_narratives_project_only_selected_rooms_and_room_blockers() -> (
    None
):
    plan, request, package = _moonseed_package()
    guide, room_ids = _accepted_guide(plan, request, package)
    selected_ids = (room_ids["perch"], room_ids["canopy"])
    selection = _selection(selected_ids)
    context = build_dungeon_room_narrative_enrichment_input(package, guide, selection)
    output = DungeonRoomNarrativeEnrichmentOutput.model_validate(
        _output(package.id, selected_ids)
    )
    validation = validate_dungeon_room_narrative_enrichment(context, output)
    package_before = package.model_dump_json()
    readiness_before = build_dungeon_preparation_readiness(guide)
    assert readiness_before is not None

    enriched = project_dungeon_room_narrative_enrichment(
        guide,
        plan=plan,
        package=package,
        context=context,
        validation=validation,
    )

    assert package.model_dump_json() == package_before
    assert enriched.map_callouts == guide.map_callouts
    assert enriched.connections == guide.connections
    assert enriched.dependencies == guide.dependencies
    assert enriched.traps == guide.traps
    assert enriched.puzzles == guide.puzzles
    assert enriched.features == guide.features
    assert enriched.objectives == guide.objectives
    outputs = {room.room_id: room for room in output.rooms}
    for room in enriched.rooms:
        prior = next(item for item in guide.rooms if item.room_id == room.room_id)
        if room.room_id in selected_ids:
            assert room.read_aloud == outputs[room.room_id].read_aloud
            assert room.sensory_details == outputs[room.room_id].observable_framing
            assert (
                room.model_copy(update={"read_aloud": None, "sensory_details": ()})
                == prior
            )
        else:
            assert room == prior
    removed_room_refs = {"perch", "canopy"}
    assert enriched.content_issues == tuple(
        issue
        for issue in guide.content_issues
        if not (issue.kind == "room" and issue.room_ref in removed_room_refs)
    )
    assert any(
        issue.kind == "room" and issue.room_ref == "choir"
        for issue in enriched.content_issues
    )
    readiness = build_dungeon_preparation_readiness(enriched)
    assert readiness is not None
    removed_diagnostics = tuple(
        item
        for item in readiness_before.diagnostics
        if item.component_id in removed_room_refs
        and "sensory read-aloud" in item.message
    )
    assert {item.component_id for item in removed_diagnostics} == removed_room_refs
    assert readiness.diagnostics == tuple(
        item for item in readiness_before.diagnostics if item not in removed_diagnostics
    )

    with pytest.raises(ConflictError, match="cannot replace accepted room narrative"):
        project_dungeon_room_narrative_enrichment(
            enriched,
            plan=plan,
            package=package,
            context=context,
            validation=validation,
        )

    tampered_rooms = list(context.rooms)
    tampered_rooms[0] = tampered_rooms[0].model_copy(update={"accepted_mechanics": ()})
    with pytest.raises(ConflictError, match="exact package and guide"):
        project_dungeon_room_narrative_enrichment(
            guide,
            plan=plan,
            package=package,
            context=context.model_copy(update={"rooms": tuple(tampered_rooms)}),
            validation=validation,
        )


def test_room_narrative_output_model_is_bounded() -> None:
    with pytest.raises(ValidationError):
        DungeonRoomNarrativeRoomOutput(
            room_id="room_one",
            read_aloud="x" * 1_001,
            observable_framing=("Visible framing one.", "Visible framing two."),
        )
