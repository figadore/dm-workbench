"""Provider-free staged dungeon enrichment planning coverage."""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError

from dm_assistant.errors import ConflictError
from dm_assistant.modules.modeling import ModelRunRecord
from dm_assistant.modules.preparation import (
    ContextSourceLink,
    DungeonGenerationContext,
    DungeonGenerationFact,
    GenerationContextEnvelope,
    GenerationContextPin,
    VisibilityPolicy,
    canonical_json_sha256,
)
from dm_assistant.orchestration.dungeons import (
    DungeonCohesionAssessment,
    DungeonCohesionDimensionDisposition,
    DungeonCohesionFinding,
    DungeonCohesionReviewDisposition,
    DungeonCohesionReviewReport,
    DungeonCohesionTargetedRecommendation,
    DungeonExplorationApproach,
    DungeonExplorationEnrichmentOutput,
    DungeonFeatureInteractionAffordance,
    DungeonFeatureInteractionEnrichmentOutput,
    DungeonGenerationProposal,
    DungeonGuidePlayerChoice,
    DungeonGuideRunnableContent,
    DungeonObjectiveEnrichmentOutput,
    DungeonObjectiveResolution,
    DungeonPuzzleAlternateHandling,
    DungeonPuzzleClue,
    DungeonPuzzleEnrichmentOutput,
    DungeonRoomNarrativeEnrichmentOutput,
    DungeonRoomNarrativeRoomOutput,
    DungeonStudioSpecification,
    DungeonTrapEnrichmentOutput,
    PromptedDungeonExplorationLineage,
    PromptedDungeonFeatureInteractionLineage,
    PromptedDungeonModelLineage,
    PromptedDungeonObjectiveLineage,
    PromptedDungeonPuzzleLineage,
    PromptedDungeonRoomNarrativeLineage,
    PromptedDungeonTrapLineage,
    derive_dungeon_creative_continuity,
    plan_dungeon_staged_enrichment,
    require_dungeon_cohesion_disposition,
    validate_final_staged_dungeon,
)
from dm_assistant.orchestration.dungeons.contracts import DungeonGuidePuzzle
from dm_assistant.orchestration.dungeons.final_validation import (
    DungeonCohesionDimension,
)
from dm_assistant.orchestration.dungeons.review import (
    write_staged_dungeon_review_packet,
)
from dm_assistant.orchestration.dungeons.service import (
    DungeonStudioService,
    build_dungeon_dm_guide,
    build_dungeon_preparation_readiness,
)
from dm_dungeon import DungeonPlan, LayoutRequest, compile_dungeon_plan, generate_layout
from dm_dungeon.contracts import (
    EncounterSlotIntent,
    RoomMechanicMarkerKind,
    Visibility,
)
from dm_dungeon.layout import ORTHOGONAL_LAYOUT_GENERATOR_VERSION


def _specification(case: str) -> DungeonStudioSpecification:
    plan = DungeonPlan.model_validate_json(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "title": f"{case.title()} Glasshouse",
                "premise": f"Recover the synthetic {case} seed from a weathered glasshouse.",
                "themes": [f"{case} glass", "clockwork vines"],
                "rooms": [
                    {
                        "ref": f"{case}_entry",
                        "name": "Windbreak",
                        "role": "entrance",
                        "purpose": "Establish the exposed glasshouse threshold.",
                    },
                    {
                        "ref": f"{case}_walk",
                        "name": "Vine Walk",
                        "role": "exploration",
                        "purpose": "Cross a shifting trellis walk.",
                        "encounter": "exploration",
                    },
                    {
                        "ref": f"{case}_dial",
                        "name": "Sun Dial",
                        "role": "puzzle",
                        "purpose": "Align the shutters to reveal the seed vault.",
                    },
                    {
                        "ref": f"{case}_vault",
                        "name": "Seed Vault",
                        "role": "objective",
                        "purpose": "Hold the named synthetic seed.",
                    },
                ],
                "critical_path": [
                    f"{case}_entry",
                    f"{case}_walk",
                    f"{case}_dial",
                    f"{case}_vault",
                ],
                "gates": [
                    {
                        "ref": f"{case}_vault_gate",
                        "between_rooms": [f"{case}_dial", f"{case}_vault"],
                        "kind": "locked",
                        "dependency_kind": "key",
                        "dependency_room": f"{case}_entry",
                        "dependency_name": "Synthetic Shutter Key",
                    }
                ],
                "room_contents": [
                    {
                        "room_ref": f"{case}_entry",
                        "trap": {"name": "Falling Pane", "challenge": "moderate"},
                    },
                    {
                        "room_ref": f"{case}_walk",
                        "feature": {
                            "kind": "other",
                            "name": "Trellis Brake",
                            "description": "A brass brake changes the trellis angle.",
                        },
                    },
                    {"room_ref": f"{case}_vault", "objective": "Synthetic Seed"},
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
        package_id=f"package_{case}_glasshouse",
        brief=compiled.brief,
        topology=compiled.topology,
        certificate=compiled.certificate,
        seed=1701,
        generator_version=ORTHOGONAL_LAYOUT_GENERATOR_VERSION,
        mechanics_plan=compiled.mechanics_plan,
        floor_bounds=compiled.floor_bounds,
    )
    layout = generate_layout(request)
    assert layout.success and layout.package is not None
    guide = build_dungeon_dm_guide(request, layout.package, plan)
    guide_document = guide.model_dump(mode="python")
    guide_document["dependencies"] = tuple(
        dependency.model_copy(
            update={
                "discovery": "The synthetic shutter key hangs beside the entry diagram.",
                "content": _content("gate dependency"),
            }
        )
        for dependency in guide.dependencies
    )
    guide_document["content_issues"] = tuple(
        issue for issue in guide.content_issues if issue.kind != "gate_dependency"
    )
    guide = type(guide).model_validate(guide_document)
    source = ContextSourceLink(
        source_kind="document_revision",
        source_id="glasshouse_history_source",
        revision_id="synthetic_revision",
        sha256="a" * 64,
        visibility_policy=VisibilityPolicy.DM_ONLY,
    )
    payload = DungeonGenerationContext(
        context_version="1.0.0",
        prompt_input_sha256="b" * 64,
        tones=("wind-worn",),
        motif_variation_constraints=(
            "Vary the glass motif between light, sound, and unstable footing.",
        ),
        selected_facts=(
            DungeonGenerationFact(
                fact_id="glasshouse_history",
                kind="history",
                summary="The glasshouse shutters once protected rare synthetic seeds.",
                source_ids=(source.source_id,),
            ),
        ),
        grounding_mode="selected_campaign",
        preparation_owner_id="dm",
        context_provenance="synthetic_final_gate_fixture",
    )
    payload_document = payload.model_dump(mode="json")
    envelope = GenerationContextEnvelope(
        context_kind="dungeon_generation",
        payload_version="1.0.0",
        campaign_revision_id=UUID(int=101),
        corpus_snapshot_id=UUID(int=102),
        rules_profile_id=UUID(int=103),
        visibility_policy=VisibilityPolicy.DM_ONLY,
        source_links=(source,),
        payload=payload_document,
        payload_sha256=canonical_json_sha256(payload_document),
    )
    context_pin = GenerationContextPin(
        envelope_kind=envelope.context_kind,
        payload_version=envelope.payload_version,
        envelope=envelope.model_dump(mode="json"),
        payload_sha256=envelope.payload_sha256,
        source_links=envelope.source_links,
    )
    continuity = derive_dungeon_creative_continuity(envelope, plan)
    proposal = DungeonGenerationProposal(
        proposal_version="1",
        plan=plan,
        intent_summary="Build a synthetic glasshouse progression.",
    )
    structural_lineage = PromptedDungeonModelLineage(
        model_run_id=UUID(int=100),
        model_run=_run(proposal),
        proposal=proposal,
    )
    return DungeonStudioSpecification(
        schema_version="1.0.0",
        layout_request=request,
        package=layout.package,
        structural_context=context_pin,
        creative_continuity=continuity,
        dm_guide=guide,
        preparation_readiness=build_dungeon_preparation_readiness(guide),
        model_lineage=(structural_lineage,),
    )


def _content(label: str) -> DungeonGuideRunnableContent:
    return DungeonGuideRunnableContent(
        situation=f"Observable {label} situation.",
        adjudication=f"Actionable {label} adjudication.",
        player_choices=(
            DungeonGuidePlayerChoice(
                action=f"First {label} approach.", outcome=f"First {label} outcome."
            ),
            DungeonGuidePlayerChoice(
                action=f"Second {label} approach.", outcome=f"Second {label} outcome."
            ),
        ),
    )


def _run(output: Any) -> ModelRunRecord:
    payload = output.model_dump(mode="json")
    return ModelRunRecord.model_construct(status="succeeded", output_payload=payload)


def _lineage(
    lineage_type: type,
    output: object,
    sequence: int,
    continuity_sha256: str,
) -> object:
    continuity = (
        {
            "creative_continuity_version": "1.0.0",
            "creative_continuity_sha256": continuity_sha256,
            "selected_fact_ids": ("glasshouse_history",),
            "source_ids": ("glasshouse_history_source",),
        }
        if lineage_type
        in (
            PromptedDungeonPuzzleLineage,
            PromptedDungeonExplorationLineage,
            PromptedDungeonFeatureInteractionLineage,
            PromptedDungeonTrapLineage,
            PromptedDungeonObjectiveLineage,
            PromptedDungeonRoomNarrativeLineage,
        )
        else {}
    )
    return lineage_type(
        model_run_id=UUID(int=sequence),
        context_sha256=f"{sequence:064x}",
        model_run=_run(output),
        output=output,
        **continuity,
    )


def _accept_next(
    specification: DungeonStudioSpecification, sequence: int
) -> DungeonStudioSpecification:
    plan = plan_dungeon_staged_enrichment(specification)
    assert plan.status == "ready"
    assert plan.next_task is not None
    task = plan.next_task
    guide = specification.dm_guide
    assert guide is not None
    package_id = specification.package.id
    assert specification.creative_continuity is not None
    document = guide.model_dump(mode="python")
    update: dict[str, object]
    output: Any

    if task.kind == "puzzle":
        room_id = task.room_ids[0]
        room = next(item for item in guide.rooms if item.room_id == room_id)
        output = DungeonPuzzleEnrichmentOutput(
            schema_version="1.0.0",
            package_id=package_id,
            room_id=room_id,
            name="Shutter Dial",
            observable_elements=(
                "Four shutters ring a brass dial.",
                "Sunlight crosses etched arcs.",
            ),
            solution_steps=(
                "Turn the dial until every bright arc meets a shutter mark.",
            ),
            clue_path=(
                DungeonPuzzleClue(
                    location_id=room_id,
                    observation="One arc is polished brighter than the rest.",
                    inference="The bright arcs indicate the required alignment.",
                ),
            ),
            alternate_handling=(
                DungeonPuzzleAlternateHandling(
                    approach="Trace the arcs while another character turns the dial.",
                    adjudication="Reveal the next alignment after careful coordination.",
                ),
            ),
            success_outcome="The vault shutters open.",
            failure_consequence="The shutters reset with a loud click.",
        )
        document["puzzles"] = (
            DungeonGuidePuzzle(
                content_ref="accepted_shutter_dial",
                room_id=room_id,
                map_reference=room.map_reference,
                name=output.name,
                solution=output.guide_solution(),
                content=_content("puzzle"),
            ),
        )
        update = {
            "puzzle_model_lineage": (
                *specification.puzzle_model_lineage,
                _lineage(
                    PromptedDungeonPuzzleLineage,
                    output,
                    sequence,
                    specification.creative_continuity.projection_sha256,
                ),
            )
        }
    elif task.kind == "exploration":
        room_id = task.room_ids[0]
        slot_id = task.target_ids[0]
        output = DungeonExplorationEnrichmentOutput(
            schema_version="1.0.0",
            package_id=package_id,
            room_id=room_id,
            encounter_slot_id=slot_id,
            observable_cues=(
                "The trellis sways above cracked panes.",
                "A brass brake moves with the nearest support.",
            ),
            approaches=(
                DungeonExplorationApproach(
                    affordance_ids=(
                        next(
                            item.marker_id
                            for item in guide.features
                            if item.room_id == room_id
                        ),
                    ),
                    action="Set the trellis brake.",
                    adjudication="The crossing steadies long enough to advance.",
                    consequence="Loose glass falls into the lower beds.",
                ),
                DungeonExplorationApproach(
                    affordance_ids=(
                        next(
                            item.marker_id
                            for item in guide.features
                            if item.room_id == room_id
                        ),
                    ),
                    action="Move with the trellis swing.",
                    adjudication="Careful timing crosses without setting the brake.",
                    consequence="A mistimed step increases the sway.",
                ),
            ),
            escalation="The trellis swings farther after each failed attempt.",
            recovery="The brake can be reset from the near platform.",
        )
        document["rooms"] = tuple(
            item.model_copy(update={"encounter_content": _content("exploration")})
            if item.room_id == room_id
            else item
            for item in guide.rooms
        )
        update = {
            "exploration_model_lineage": (
                *specification.exploration_model_lineage,
                _lineage(
                    PromptedDungeonExplorationLineage,
                    output,
                    sequence,
                    specification.creative_continuity.projection_sha256,
                ),
            )
        }
    elif task.kind == "feature_interaction":
        room_id = task.room_ids[0]
        feature_id = task.target_ids[0]
        output = DungeonFeatureInteractionEnrichmentOutput(
            schema_version="1.0.0",
            package_id=package_id,
            room_id=room_id,
            feature_id=feature_id,
            observable_setup=("The brass brake has two reachable handles.",),
            affordances=(
                DungeonFeatureInteractionAffordance(
                    action="Pull both handles.",
                    adjudication="The trellis locks.",
                    consequence="The route steadies.",
                ),
                DungeonFeatureInteractionAffordance(
                    action="Release one handle.",
                    adjudication="The trellis tilts.",
                    consequence="A lower ledge becomes reachable.",
                ),
            ),
        )
        document["features"] = tuple(
            item.model_copy(update={"content": _content("feature")})
            if item.marker_id == feature_id
            else item
            for item in guide.features
        )
        update = {
            "feature_interaction_model_lineage": (
                *specification.feature_interaction_model_lineage,
                _lineage(
                    PromptedDungeonFeatureInteractionLineage,
                    output,
                    sequence,
                    specification.creative_continuity.projection_sha256,
                ),
            )
        }
    elif task.kind == "trap":
        room_id = task.room_ids[0]
        trap_id = task.target_ids[0]
        output = DungeonTrapEnrichmentOutput(
            schema_version="1.0.0",
            package_id=package_id,
            room_id=room_id,
            trap_id=trap_id,
            observable_warning="A pane hangs from one remaining hinge.",
            trigger="Crossing beneath the frame releases the hinge.",
            effect_narration="The pane drops across the threshold.",
            detection_method="Inspect the hinge and taut release wire.",
            disable_operation="Brace the pane and slacken the wire.",
            consequences=("The impact blocks the direct threshold.",),
        )
        document["traps"] = tuple(
            item.model_copy(
                update={
                    "warning": output.observable_warning,
                    "trigger": output.trigger,
                    "effect": output.effect_narration,
                    "detection": output.detection_method,
                    "disable": output.disable_operation,
                    "consequences": output.consequences,
                }
            )
            if item.marker_id == trap_id
            else item
            for item in guide.traps
        )
        update = {
            "trap_model_lineage": (
                *specification.trap_model_lineage,
                _lineage(
                    PromptedDungeonTrapLineage,
                    output,
                    sequence,
                    specification.creative_continuity.projection_sha256,
                ),
            )
        }
    elif task.kind == "objective":
        room_id = task.room_ids[0]
        objective_id = task.target_ids[0]
        output = DungeonObjectiveEnrichmentOutput(
            schema_version="1.0.0",
            package_id=package_id,
            room_id=room_id,
            objective_id=objective_id,
            observable_goal="The synthetic seed rests behind the last shutter.",
            resolution_guidance="Resolve removal according to the chosen approach.",
            resolutions=(
                DungeonObjectiveResolution(
                    action="Lift the seed cradle.",
                    outcome="The seed is recovered intact.",
                ),
                DungeonObjectiveResolution(
                    action="Open the cradle in place.",
                    outcome="The seed can be inspected before removal.",
                ),
            ),
            setback_or_aftermath="A forced cradle closes the outer shutters.",
        )
        document["objectives"] = tuple(
            item.model_copy(update={"content": _content("objective")})
            if item.marker_id == objective_id
            else item
            for item in guide.objectives
        )
        update = {
            "objective_model_lineage": (
                *specification.objective_model_lineage,
                _lineage(
                    PromptedDungeonObjectiveLineage,
                    output,
                    sequence,
                    specification.creative_continuity.projection_sha256,
                ),
            )
        }
    else:
        output = DungeonRoomNarrativeEnrichmentOutput(
            schema_version="1.0.0",
            package_id=package_id,
            rooms=tuple(
                DungeonRoomNarrativeRoomOutput(
                    room_id=room_id,
                    read_aloud="Pale light crosses old glass and trembling brasswork.",
                    observable_framing=(
                        "Wind moves through a cracked upper pane.",
                        "Dust gathers along the nearest threshold.",
                    ),
                )
                for room_id in task.room_ids
            ),
        )
        by_room = {item.room_id: item for item in output.rooms}
        document["rooms"] = tuple(
            item.model_copy(
                update={
                    "read_aloud": by_room[item.room_id].read_aloud,
                    "sensory_details": by_room[item.room_id].observable_framing,
                }
            )
            if item.room_id in by_room
            else item
            for item in guide.rooms
        )
        update = {
            "room_narrative_model_lineage": (
                *specification.room_narrative_model_lineage,
                _lineage(
                    PromptedDungeonRoomNarrativeLineage,
                    output,
                    sequence,
                    specification.creative_continuity.projection_sha256,
                ),
            )
        }

    room_ref_by_id = {
        item.room_id: item.ref
        for item in specification.layout_request.certificate.rooms
    }
    issue_kind = {
        "puzzle": "puzzle",
        "exploration": "encounter",
        "feature_interaction": "feature",
        "objective": "objective",
        "room_narrative": "room",
    }.get(task.kind)
    if issue_kind is not None:
        selected_room_refs = {room_ref_by_id[room_id] for room_id in task.room_ids}
        document["content_issues"] = tuple(
            issue
            for issue in guide.content_issues
            if not (
                issue.code == "guide_content.required_missing"
                and issue.kind == issue_kind
                and issue.room_ref in selected_room_refs
            )
        )

    enriched_guide = type(guide).model_validate(document)
    return specification.model_copy(
        update={
            "dm_guide": enriched_guide,
            "preparation_readiness": build_dungeon_preparation_readiness(
                enriched_guide
            ),
            **update,
        }
    )


@pytest.mark.parametrize("case", ["amber", "cobalt"])
def test_planner_orders_exact_tasks_and_skips_accepted_lineage(case: str) -> None:
    specification = _specification(case)
    original_json = specification.model_dump_json()
    expected_kinds = [
        "puzzle",
        "exploration",
        "feature_interaction",
        "trap",
        "objective",
        "room_narrative",
    ]

    for sequence, expected_kind in enumerate(expected_kinds, start=1):
        before_planning = specification.model_dump_json()
        plan = plan_dungeon_staged_enrichment(specification)
        assert specification.model_dump_json() == before_planning
        assert plan.status == "ready"
        assert plan.next_task is not None
        assert plan.next_task.kind == expected_kind

        if expected_kind == "puzzle":
            expected_room = next(
                room.id
                for room in specification.package.rooms
                if room.role.value == "puzzle"
            )
            assert plan.next_task.room_ids == (expected_room,)
            assert plan.next_task.target_ids == (expected_room,)
        elif expected_kind == "exploration":
            expected_slot = next(
                slot
                for slot in specification.package.encounter_slots
                if EncounterSlotIntent.EXPLORATION.value in slot.tags
            )
            assert plan.next_task.room_ids == (expected_slot.room_id,)
            assert plan.next_task.target_ids == (expected_slot.id,)
        elif expected_kind in {"feature_interaction", "trap", "objective"}:
            marker_kind = {
                "feature_interaction": RoomMechanicMarkerKind.FEATURE,
                "trap": RoomMechanicMarkerKind.TRAP,
                "objective": RoomMechanicMarkerKind.OBJECTIVE,
            }[expected_kind]
            marker = next(
                item
                for item in specification.package.room_mechanic_markers
                if item.kind is marker_kind
            )
            assert plan.next_task.room_ids == (marker.room_id,)
            assert plan.next_task.target_ids == (marker.id,)
        else:
            current_guide = specification.dm_guide
            assert current_guide is not None
            assert plan.next_task.room_ids == tuple(
                room.room_id for room in current_guide.rooms
            )
            assert plan.next_task.target_ids == plan.next_task.room_ids

        specification = _accept_next(specification, sequence)

    complete = plan_dungeon_staged_enrichment(specification)
    assert complete.status == "complete"
    assert complete.next_task is None
    assert not complete.blockers
    assert _specification(case).model_dump_json() == original_json


def test_planner_blocks_missing_guide_and_content_without_accepted_lineage() -> None:
    specification = _specification("violet")
    missing_guide = specification.model_copy(
        update={"dm_guide": None, "preparation_readiness": None}
    )
    assert plan_dungeon_staged_enrichment(missing_guide).status == "blocked"

    plan = plan_dungeon_staged_enrichment(specification)
    assert plan.next_task is not None and plan.next_task.kind == "puzzle"
    guide = specification.dm_guide
    assert guide is not None
    room = next(
        item for item in guide.rooms if item.room_id == plan.next_task.room_ids[0]
    )
    document = guide.model_dump(mode="python")
    document["puzzles"] = (
        DungeonGuidePuzzle(
            content_ref="untracked_puzzle",
            room_id=room.room_id,
            map_reference=room.map_reference,
            name="Untracked Puzzle",
            solution="An untracked solution.",
            content=_content("untracked puzzle"),
        ),
    )
    inconsistent = specification.model_copy(
        update={"dm_guide": type(guide).model_validate(document)}
    )
    blocked = plan_dungeon_staged_enrichment(inconsistent)
    assert blocked.status == "blocked"
    assert blocked.next_task is None
    assert [item.code for item in blocked.blockers] == [
        "staged_enrichment.accepted_state_inconsistent"
    ]


def _fully_enriched_specification(case: str) -> DungeonStudioSpecification:
    specification = _specification(case)
    for sequence in range(1, 8):
        plan = plan_dungeon_staged_enrichment(specification)
        if plan.status == "complete":
            break
        specification = _accept_next(specification, sequence)
    assert plan_dungeon_staged_enrichment(specification).status == "complete"
    return specification


def test_final_gate_accepts_one_fully_enriched_exact_source_lineage() -> None:
    specification = _fully_enriched_specification("silver")
    before = specification.model_dump_json()

    result = validate_final_staged_dungeon(specification)

    assert result.valid
    assert not result.diagnostics
    assert all(check.passed for check in result.checks)
    assert specification.model_dump_json() == before
    assert specification.creative_continuity is not None
    assert result.creative_continuity_sha256 == (
        specification.creative_continuity.projection_sha256
    )
    for lineage_group in (
        specification.puzzle_model_lineage,
        specification.exploration_model_lineage,
        specification.feature_interaction_model_lineage,
        specification.trap_model_lineage,
        specification.objective_model_lineage,
        specification.room_narrative_model_lineage,
    ):
        assert lineage_group
        assert {item.selected_fact_ids for item in lineage_group} == {
            ("glasshouse_history",)
        }
        assert {item.source_ids for item in lineage_group} == {
            ("glasshouse_history_source",)
        }


def test_final_gate_reports_body_free_source_lineage_content_and_structure_failures() -> (
    None
):
    specification = _fully_enriched_specification("bronze")
    stale_puzzle = specification.puzzle_model_lineage[0].model_copy(
        update={"source_ids": ("unauthorized_source",)}
    )
    stale_narrative = specification.room_narrative_model_lineage[0].model_copy(
        update={"creative_continuity_sha256": "0" * 64}
    )
    readiness = specification.preparation_readiness
    guide = specification.dm_guide
    assert readiness is not None and guide is not None and guide.dependencies
    broken_guide = guide.model_copy(
        update={
            "dependencies": (
                guide.dependencies[0].model_copy(
                    update={"target_gate_id": "unknown_gate"}
                ),
            )
        }
    )
    broken = specification.model_copy(
        update={
            "layout_request": specification.layout_request.model_copy(
                update={"package_id": "stale_package_id"}
            ),
            "dm_guide": broken_guide,
            "puzzle_model_lineage": (stale_puzzle,),
            "room_narrative_model_lineage": (stale_narrative,),
            "preparation_readiness": readiness.model_copy(update={"ready": False}),
        }
    )

    result = validate_final_staged_dungeon(broken)

    assert not result.valid
    assert {item.code for item in result.diagnostics} >= {
        "dungeon_final.dependency_mismatch",
        "dungeon_final.required_content_missing",
        "dungeon_final.lineage_continuity_mismatch",
        "dungeon_final.lineage_source_mismatch",
    }
    serialized = result.model_dump_json()
    assert "Observable puzzle situation" not in serialized
    assert "Pale light crosses" not in serialized
    assert len(result.diagnostics) <= 64


def test_final_gate_fails_closed_when_a_protected_marker_becomes_player_visible() -> (
    None
):
    specification = _fully_enriched_specification("ivory")
    trap_id = specification.trap_model_lineage[0].output.trap_id
    trap_marker = next(
        marker
        for marker in specification.package.room_mechanic_markers
        if marker.id == trap_id
    )
    player_layer = trap_marker.layer_id
    tampered_layers = tuple(
        layer.model_copy(
            update={
                "visibility": Visibility.PLAYER_SAFE,
                "include_in_player_export": True,
            }
        )
        if layer.id == player_layer
        else layer
        for layer in specification.package.layers
    )
    tampered_markers = tuple(
        marker.model_copy(
            update={
                "kind": RoomMechanicMarkerKind.FEATURE,
                "visibility": Visibility.PLAYER_SAFE,
            }
        )
        if marker.id == trap_id
        else marker
        for marker in specification.package.room_mechanic_markers
    )
    tampered_package = specification.package.model_copy(
        update={
            "layers": tampered_layers,
            "room_mechanic_markers": tampered_markers,
        }
    )
    tampered = specification.model_copy(update={"package": tampered_package})

    result = validate_final_staged_dungeon(tampered)

    assert not result.valid
    assert any(
        item.code == "dungeon_final.player_secret_leak"
        and trap_id in item.component_ids
        for item in result.diagnostics
    )


def test_prompted_approval_fails_before_transition_when_final_gate_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    specification = _fully_enriched_specification("approval")
    report, disposition = _cohesion_evidence(specification)
    stale_puzzle = specification.puzzle_model_lineage[0].model_copy(
        update={"source_ids": ("unauthorized_source",)}
    )
    broken = specification.model_copy(update={"puzzle_model_lineage": (stale_puzzle,)})

    class _PreparationBoundary:
        def get_version(self, campaign_id: UUID, version_id: UUID) -> object:
            del campaign_id, version_id
            return SimpleNamespace(specification=broken.model_dump(mode="json"))

        def transition_artifact(self, command: object) -> None:
            del command
            raise AssertionError("approval transition must not be attempted")

    monkeypatch.setattr(
        "dm_assistant.orchestration.dungeons.service._load_specification",
        lambda document: broken,
    )
    service = DungeonStudioService(_PreparationBoundary())  # type: ignore[arg-type]

    with pytest.raises(ConflictError, match="final deterministic approval gate"):
        service.approve(
            campaign_id=UUID(int=901),
            artifact_id=UUID(int=902),
            artifact_version_id=UUID(int=903),
            actor="synthetic-dm",
            reason="Synthetic review complete.",
            cohesion_report=report,
            cohesion_disposition=disposition,
        )


def _cohesion_evidence(
    specification: DungeonStudioSpecification,
    *,
    actor: str = "synthetic-dm",
) -> tuple[DungeonCohesionReviewReport, DungeonCohesionReviewDisposition]:
    validation = validate_final_staged_dungeon(specification)
    assert validation.valid and validation.creative_continuity_sha256 is not None
    dimensions: tuple[DungeonCohesionDimension, ...] = (
        "thematic_reinforcement",
        "history_environment_causality",
        "mechanic_objective_unity",
        "progression",
        "motif_variation",
        "selected_lore_consistency",
    )
    assessments = tuple(
        DungeonCohesionAssessment(dimension=dimension, decision="pass")
        for dimension in dimensions
    )
    report = DungeonCohesionReviewReport(
        specification_sha256=validation.specification_sha256,
        deterministic_validation_sha256=canonical_json_sha256(
            validation.model_dump(mode="json")
        ),
        creative_continuity_sha256=validation.creative_continuity_sha256,
        reviewer_kind="human_dm",
        assessments=assessments,
    )
    disposition = DungeonCohesionReviewDisposition(
        specification_sha256=validation.specification_sha256,
        report_sha256=canonical_json_sha256(report.model_dump(mode="json")),
        dm_actor=actor,
        dispositions=tuple(
            DungeonCohesionDimensionDisposition(
                dimension=assessment.dimension,
                decision="accepted",
            )
            for assessment in assessments
        ),
    )
    return report, disposition


def test_prompted_approval_requires_six_dimension_dm_disposition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    specification = _fully_enriched_specification("disposition")

    class _PreparationBoundary:
        def get_version(self, campaign_id: UUID, version_id: UUID) -> object:
            del campaign_id, version_id
            return SimpleNamespace(specification={})

        def transition_artifact(self, command: object) -> None:
            del command
            raise AssertionError("approval transition must not be attempted")

    monkeypatch.setattr(
        "dm_assistant.orchestration.dungeons.service._load_specification",
        lambda document: specification,
    )
    service = DungeonStudioService(_PreparationBoundary())  # type: ignore[arg-type]

    with pytest.raises(ConflictError, match="complete DM cohesion disposition"):
        service.approve(
            campaign_id=UUID(int=911),
            artifact_id=UUID(int=912),
            artifact_version_id=UUID(int=913),
            actor="synthetic-dm",
            reason="Synthetic review complete.",
        )


def test_provider_independent_manual_approval_keeps_readiness_only_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enriched = _fully_enriched_specification("manual")
    manual = enriched.model_copy(
        update={
            "structural_context": None,
            "creative_continuity": None,
            "model_lineage": (),
            "puzzle_model_lineage": (),
            "exploration_model_lineage": (),
            "feature_interaction_model_lineage": (),
            "trap_model_lineage": (),
            "objective_model_lineage": (),
            "room_narrative_model_lineage": (),
        }
    )
    assert manual.preparation_readiness is not None
    assert manual.preparation_readiness.ready

    class _TransitionReached(Exception):
        pass

    class _PreparationBoundary:
        def get_version(self, campaign_id: UUID, version_id: UUID) -> object:
            del campaign_id, version_id
            return SimpleNamespace(specification={})

        def transition_artifact(self, command: object) -> None:
            del command
            raise _TransitionReached

    monkeypatch.setattr(
        "dm_assistant.orchestration.dungeons.service._load_specification",
        lambda document: manual,
    )
    service = DungeonStudioService(_PreparationBoundary())  # type: ignore[arg-type]

    with pytest.raises(_TransitionReached):
        service.approve(
            campaign_id=UUID(int=916),
            artifact_id=UUID(int=917),
            artifact_version_id=UUID(int=918),
            actor="synthetic-dm",
            reason="Manual preparation review complete.",
        )


def test_complete_prompted_approval_evidence_reaches_lifecycle_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    specification = _fully_enriched_specification("approved")
    report, disposition = _cohesion_evidence(specification)

    class _TransitionReached(Exception):
        pass

    class _PreparationBoundary:
        def get_version(self, campaign_id: UUID, version_id: UUID) -> object:
            del campaign_id, version_id
            return SimpleNamespace(specification={})

        def transition_artifact(self, command: object) -> None:
            del command
            raise _TransitionReached

    monkeypatch.setattr(
        "dm_assistant.orchestration.dungeons.service._load_specification",
        lambda document: specification,
    )
    service = DungeonStudioService(_PreparationBoundary())  # type: ignore[arg-type]

    with pytest.raises(_TransitionReached):
        service.approve(
            campaign_id=UUID(int=921),
            artifact_id=UUID(int=922),
            artifact_version_id=UUID(int=923),
            actor="synthetic-dm",
            reason="Synthetic review complete.",
            cohesion_report=report,
            cohesion_disposition=disposition,
        )


def test_cohesion_disposition_binds_all_six_dimensions_and_cannot_clear_blockers() -> (
    None
):
    specification = _fully_enriched_specification("bound")
    validation = validate_final_staged_dungeon(specification)
    report, disposition = _cohesion_evidence(specification)

    require_dungeon_cohesion_disposition(
        validation,
        report,
        disposition,
        dm_actor="synthetic-dm",
    )

    stale_puzzle = specification.puzzle_model_lineage[0].model_copy(
        update={"source_ids": ("unauthorized_source",)}
    )
    broken = specification.model_copy(update={"puzzle_model_lineage": (stale_puzzle,)})
    failed_validation = validate_final_staged_dungeon(broken)
    assert not failed_validation.valid
    with pytest.raises(ConflictError, match="stale or mismatched"):
        require_dungeon_cohesion_disposition(
            failed_validation,
            report,
            disposition,
            dm_actor="synthetic-dm",
        )


def test_targeted_regeneration_disposition_cannot_authorize_approval() -> None:
    specification = _fully_enriched_specification("targeted")
    validation = validate_final_staged_dungeon(specification)
    assert validation.valid and validation.creative_continuity_sha256 is not None
    dimensions: tuple[DungeonCohesionDimension, ...] = (
        "thematic_reinforcement",
        "history_environment_causality",
        "mechanic_objective_unity",
        "progression",
        "motif_variation",
        "selected_lore_consistency",
    )
    room_id = specification.package.rooms[0].id
    assessments = (
        DungeonCohesionAssessment(
            dimension=dimensions[0],
            decision="needs_dm_disposition",
            findings=(
                DungeonCohesionFinding(
                    finding_code="theme_weak",
                    severity="blocking_dm_review",
                    summary="Synthetic thematic concern.",
                    recommendation=DungeonCohesionTargetedRecommendation(
                        task_kind="room_narrative",
                        room_ids=(room_id,),
                        target_ids=(room_id,),
                        rationale="Reinforce the selected theme in observable framing.",
                    ),
                ),
            ),
        ),
        *tuple(
            DungeonCohesionAssessment(dimension=dimension, decision="pass")
            for dimension in dimensions[1:]
        ),
    )
    report = DungeonCohesionReviewReport(
        specification_sha256=validation.specification_sha256,
        deterministic_validation_sha256=canonical_json_sha256(
            validation.model_dump(mode="json")
        ),
        creative_continuity_sha256=validation.creative_continuity_sha256,
        reviewer_kind="human_dm",
        assessments=assessments,
    )
    disposition = DungeonCohesionReviewDisposition(
        specification_sha256=validation.specification_sha256,
        report_sha256=canonical_json_sha256(report.model_dump(mode="json")),
        dm_actor="synthetic-dm",
        dispositions=(
            DungeonCohesionDimensionDisposition(
                dimension=dimensions[0],
                decision="targeted_regeneration",
                finding_codes=("theme_weak",),
                note="Regenerate the exact room-narrative seam.",
            ),
            *tuple(
                DungeonCohesionDimensionDisposition(
                    dimension=dimension,
                    decision="accepted",
                )
                for dimension in dimensions[1:]
            ),
        ),
    )

    require_dungeon_cohesion_disposition(
        validation,
        report,
        disposition,
        dm_actor="synthetic-dm",
        allow_targeted_regeneration=True,
    )
    with pytest.raises(ConflictError, match="targeted regeneration before approval"):
        require_dungeon_cohesion_disposition(
            validation,
            report,
            disposition,
            dm_actor="synthetic-dm",
        )


def test_staged_review_packet_records_body_free_gate_summary_and_dm_disposition(
    tmp_path: Path,
) -> None:
    specification = _fully_enriched_specification("packet")
    report, disposition = _cohesion_evidence(specification)
    output_dir = tmp_path / "staged-review"

    files = write_staged_dungeon_review_packet(
        specification,
        output_dir,
        cohesion_report=report,
        cohesion_disposition=disposition,
    )

    names = {item.name for item in files}
    assert {
        "final-validation-summary.json",
        "cohesion-review-report.json",
        "cohesion-disposition.json",
        "review-disposition.md",
        "dm-map.svg",
        "player-map.svg",
        "dm-guide.md",
        "manifest.json",
    } <= names
    summary = json.loads(
        (output_dir / "final-validation-summary.json").read_text(encoding="utf-8")
    )
    assert summary["valid"] is True
    assert "diagnostics" not in summary
    assert [item["kind"] for item in summary["checks"]] == [
        "continuity",
        "sources",
        "dependencies",
        "required_content",
        "lineage",
        "cross_task",
        "secrecy",
    ]
    serialized_summary = json.dumps(summary)
    assert "Observable puzzle situation" not in serialized_summary
    assert "Pale light crosses" not in serialized_summary
    disposition_document = json.loads(
        (output_dir / "cohesion-disposition.json").read_text(encoding="utf-8")
    )
    assert len(disposition_document["dispositions"]) == 6
    assert {item["decision"] for item in disposition_document["dispositions"]} == {
        "accepted"
    }
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["packet_kind"] == "staged_final_review"
    assert manifest["targeted_regeneration_required"] is False


def test_staged_review_packet_fails_before_writing_when_final_gate_fails(
    tmp_path: Path,
) -> None:
    specification = _fully_enriched_specification("packet_blocked")
    report, disposition = _cohesion_evidence(specification)
    stale_puzzle = specification.puzzle_model_lineage[0].model_copy(
        update={"source_ids": ("unauthorized_source",)}
    )
    broken = specification.model_copy(update={"puzzle_model_lineage": (stale_puzzle,)})
    output_dir = tmp_path / "blocked-review"

    with pytest.raises(ConflictError, match="review-packet gate"):
        write_staged_dungeon_review_packet(
            broken,
            output_dir,
            cohesion_report=report,
            cohesion_disposition=disposition,
        )

    assert not output_dir.exists()


def test_cohesion_report_is_six_dimension_read_only_metadata() -> None:
    specification = _fully_enriched_specification("pearl")
    validation = validate_final_staged_dungeon(specification)
    assert validation.valid and validation.creative_continuity_sha256 is not None
    dimensions: tuple[DungeonCohesionDimension, ...] = (
        "thematic_reinforcement",
        "history_environment_causality",
        "mechanic_objective_unity",
        "progression",
        "motif_variation",
        "selected_lore_consistency",
    )
    assessments = tuple(
        DungeonCohesionAssessment(dimension=dimension, decision="pass")
        for dimension in dimensions
    )
    report_document = {
        "schema_version": "1.0.0",
        "specification_sha256": validation.specification_sha256,
        "deterministic_validation_sha256": canonical_json_sha256(
            validation.model_dump(mode="json")
        ),
        "creative_continuity_sha256": validation.creative_continuity_sha256,
        "reviewer_kind": "bounded_model",
        "non_authoritative": True,
        "assessments": [item.model_dump(mode="json") for item in assessments],
    }

    report = DungeonCohesionReviewReport.model_validate(report_document)

    assert report.non_authoritative is True
    schema_properties = report.model_json_schema()["properties"]
    assert "approved" not in schema_properties
    assert "content_edits" not in schema_properties
    assert "canonical_operations" not in schema_properties
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        DungeonCohesionReviewReport.model_validate(
            {**report_document, "approved": True}
        )
