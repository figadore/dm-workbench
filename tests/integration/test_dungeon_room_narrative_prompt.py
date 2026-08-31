"""Faux-provider room narratives over the staged Copper Tide objective child."""

import json
import uuid
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

import pytest
import test_dungeon_exploration_prompt as staged
import test_dungeon_objective_prompt as objectives
from sqlalchemy import Engine

from dm_assistant.modules.modeling import (
    ReasoningEffort,
    ResolvedModelRunProfile,
    ToolCall,
)
from dm_assistant.modules.preparation import ArtifactAssetRole
from dm_assistant.orchestration.dungeons import (
    DungeonObjectivePromptApplicationService,
    DungeonObjectivePromptService,
    DungeonRoomNarrativeContextSelection,
    DungeonRoomNarrativePromptApplicationService,
    DungeonRoomNarrativePromptService,
    DungeonStudioSpecification,
    PromptDungeonObjectiveWorkflow,
    PromptDungeonRoomNarrativeWorkflow,
    resolve_dungeon_objective_prompt_profile,
    resolve_dungeon_room_narrative_prompt_profile,
)
from dm_assistant.orchestration.modeling import GatewayCompletion
from dm_dungeon import compile_dungeon_plan, to_canonical_json

pytestmark = pytest.mark.integration


def _narrative_output(package_id: str, room_ids: tuple[str, ...]) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "package_id": package_id,
        "rooms": [
            {
                "room_id": room_id,
                "read_aloud": (
                    f"Copper light crosses synthetic tide marks in chamber {index}, "
                    "while cool brine ticks from the old foundry stone."
                ),
                "observable_framing": [
                    "Fresh scrape marks interrupt the green copper patina.",
                    "A measured pulse travels through the room's visible fittings.",
                ],
            }
            for index, room_id in enumerate(room_ids, start=1)
        ],
    }


@dataclass(frozen=True)
class PreparedObjectiveCopper:
    base: objectives.PreparedTrappedCopper
    version_id: uuid.UUID
    specification: DungeonStudioSpecification
    objective_profile_id: uuid.UUID


def _prepare_objective_copper(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> PreparedObjectiveCopper:
    prepared = objectives._prepare_trapped_copper(engine, tmp_path, monkeypatch)
    selection = objectives._selection(prepared)
    gateway = staged.FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_objective",
                        call_id="copper-objective",
                        arguments=objectives._objective_output(
                            package_id=prepared.specification.package.id,
                            room_id=selection.room_id,
                            objective_id=selection.objective_id,
                            mechanic_ids=selection.mechanic_ids,
                        ),
                    ),
                ),
                input_tokens=240,
                output_tokens=360,
            ),
        )
    )
    profile = resolve_dungeon_objective_prompt_profile(
        provider_id="faux",
        model_id="faux_deterministic_v1",
        capabilities=("text", "tool_calls", "thinking"),
        context_window_tokens=16_384,
        output_token_limit=4_096,
        requested_effort=ReasoningEffort.FAST,
    )
    command = PromptDungeonObjectiveWorkflow(
        campaign_id=prepared.base.base.base.campaign_id,
        artifact_id=prepared.base.base.base.artifact_id,
        parent_version_id=prepared.version_id,
        selection=selection,
        created_by="synthetic-dm",
    )
    attempt = DungeonObjectivePromptApplicationService(
        prepared.base.base.base.preparation,
        DungeonObjectivePromptService(prepared.base.base.base.studio, gateway),
    ).execute(command, profile, surface="integration-setup")
    assert attempt.result is not None and attempt.result.artifact_version_id is not None
    version = prepared.base.base.base.preparation.get_version(
        prepared.base.base.base.campaign_id, attempt.result.artifact_version_id
    )
    return PreparedObjectiveCopper(
        base=prepared,
        version_id=version.id,
        specification=DungeonStudioSpecification.model_validate_json(
            json.dumps(version.specification)
        ),
        objective_profile_id=profile.task_profile_id,
    )


def _selection(
    prepared: PreparedObjectiveCopper,
) -> DungeonRoomNarrativeContextSelection:
    guide = prepared.specification.dm_guide
    assert guide is not None
    assert all(room.read_aloud is None for room in guide.rooms)
    package_rooms = {room.id: room for room in prepared.specification.package.rooms}
    selected: list[str] = []
    for room in guide.rooms:
        required: set[str] = set()
        accepted: set[str] = set()
        if package_rooms[room.room_id].role.value == "puzzle":
            required.add("puzzle")
            if any(item.room_id == room.room_id for item in guide.puzzles):
                accepted.add("puzzle")
        if (
            room.encounter_slot is not None
            and room.encounter_slot.value == "exploration"
        ):
            required.add("exploration")
            if room.encounter_content is not None:
                accepted.add("exploration")
        local_features = [
            item for item in guide.features if item.room_id == room.room_id
        ]
        if local_features:
            required.add("feature")
            if all(item.content is not None for item in local_features):
                accepted.add("feature")
        local_traps = [item for item in guide.traps if item.room_id == room.room_id]
        if local_traps:
            required.add("trap")
            if all(item.warning is not None for item in local_traps):
                accepted.add("trap")
        local_objectives = [
            item for item in guide.objectives if item.room_id == room.room_id
        ]
        if local_objectives:
            required.add("objective")
            if all(item.content is not None for item in local_objectives):
                accepted.add("objective")
        if required.issubset(accepted):
            selected.append(room.room_id)
    assert selected
    return DungeonRoomNarrativeContextSelection(
        room_ids=tuple(selected),
        tone=("salt-worn industrial mystery", "quiet pressure rather than alarm"),
        constraints=(
            "Use only player-observable information",
            "Do not reveal solutions, triggers, effects, or outcomes",
            "Do not invent creatures or mechanisms",
        ),
    )


def _command(
    prepared: PreparedObjectiveCopper,
    selection: DungeonRoomNarrativeContextSelection,
) -> PromptDungeonRoomNarrativeWorkflow:
    return PromptDungeonRoomNarrativeWorkflow(
        campaign_id=prepared.base.base.base.base.campaign_id,
        artifact_id=prepared.base.base.base.base.artifact_id,
        parent_version_id=prepared.version_id,
        selection=selection,
        created_by="synthetic-dm",
    )


def _profile() -> ResolvedModelRunProfile:
    return resolve_dungeon_room_narrative_prompt_profile(
        provider_id="faux",
        model_id="faux_deterministic_v1",
        capabilities=("text", "tool_calls", "thinking"),
        context_window_tokens=16_384,
        output_token_limit=4_096,
        requested_effort=ReasoningEffort.FAST,
    )


def test_faux_room_narratives_repair_and_publish_atomic_objective_child(
    db_engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared = _prepare_objective_copper(db_engine, tmp_path, monkeypatch)
    selection = _selection(prepared)
    valid = _narrative_output(prepared.specification.package.id, selection.room_ids)
    rejected = deepcopy(valid)
    rejected_rooms = rejected["rooms"]
    assert isinstance(rejected_rooms, list)
    rejected_rooms[0]["room_id"] = "rejected_foreign_room"
    rejected_rooms[0]["read_aloud"] = "REJECTED_NARRATIVE_BODY"
    gateway = staged.FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_room_narrative",
                        call_id="invalid-narratives",
                        arguments=rejected,
                    ),
                ),
                input_tokens=260,
                output_tokens=420,
            ),
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_room_narrative",
                        call_id="repaired-narratives",
                        arguments=valid,
                    ),
                ),
                input_tokens=340,
                output_tokens=520,
            ),
        )
    )
    profile = _profile()
    root = prepared.base.base.base.base
    attempt = DungeonRoomNarrativePromptApplicationService(
        root.preparation,
        DungeonRoomNarrativePromptService(root.studio, gateway),
    ).execute(_command(prepared, selection), profile, surface="integration")

    assert attempt.public_code == "dungeon_room_narrative_prompt_completed"
    assert attempt.result is not None and attempt.result.success
    assert attempt.result.artifact_version_id is not None
    child = root.preparation.get_version(
        root.campaign_id, attempt.result.artifact_version_id
    )
    child_spec = DungeonStudioSpecification.model_validate_json(
        json.dumps(child.specification)
    )
    assert child.parent_version_id == prepared.version_id
    assert to_canonical_json(child_spec.package) == to_canonical_json(
        prepared.specification.package
    )
    assert (
        child_spec.puzzle_model_lineage == prepared.specification.puzzle_model_lineage
    )
    assert (
        child_spec.exploration_model_lineage
        == prepared.specification.exploration_model_lineage
    )
    assert (
        child_spec.feature_interaction_model_lineage
        == prepared.specification.feature_interaction_model_lineage
    )
    assert child_spec.trap_model_lineage == prepared.specification.trap_model_lineage
    assert (
        child_spec.objective_model_lineage
        == prepared.specification.objective_model_lineage
    )
    assert len(child_spec.room_narrative_model_lineage) == 1
    assert (
        child_spec.room_narrative_model_lineage[0].output.model_dump(mode="json")
        == valid
    )
    assert (
        child_spec.dm_guide is not None and prepared.specification.dm_guide is not None
    )
    assert (
        child_spec.dm_guide.connections == prepared.specification.dm_guide.connections
    )
    assert (
        child_spec.dm_guide.dependencies == prepared.specification.dm_guide.dependencies
    )
    assert child_spec.dm_guide.puzzles == prepared.specification.dm_guide.puzzles
    assert child_spec.dm_guide.features == prepared.specification.dm_guide.features
    assert child_spec.dm_guide.traps == prepared.specification.dm_guide.traps
    assert child_spec.dm_guide.objectives == prepared.specification.dm_guide.objectives
    outputs = {item["room_id"]: item for item in valid["rooms"]}  # type: ignore[index]
    for room in child_spec.dm_guide.rooms:
        prior = next(
            item
            for item in prepared.specification.dm_guide.rooms
            if item.room_id == room.room_id
        )
        if room.room_id in outputs:
            assert room.read_aloud == outputs[room.room_id]["read_aloud"]
            assert (
                list(room.sensory_details)
                == outputs[room.room_id]["observable_framing"]
            )
            assert (
                room.model_copy(update={"read_aloud": None, "sensory_details": ()})
                == prior
            )
        else:
            assert room == prior
    structural = prepared.specification.model_lineage[-1].proposal
    assert structural is not None and structural.plan is not None
    compiled = compile_dungeon_plan(structural.plan)
    assert compiled.certificate is not None
    selected_refs = {
        room.ref
        for room in compiled.certificate.rooms
        if room.room_id in selection.room_ids
    }
    assert child_spec.dm_guide.content_issues == tuple(
        issue
        for issue in prepared.specification.dm_guide.content_issues
        if not (issue.kind == "room" and issue.room_ref in selected_refs)
    )
    assert prepared.specification.preparation_readiness is not None
    assert child_spec.preparation_readiness is not None
    removed = tuple(
        item
        for item in prepared.specification.preparation_readiness.diagnostics
        if item.component_id in selected_refs and "sensory read-aloud" in item.message
    )
    assert child_spec.preparation_readiness.diagnostics == tuple(
        item
        for item in prepared.specification.preparation_readiness.diagnostics
        if item not in removed
    )
    child_text = json.dumps(child.specification)
    assert "rejected_foreign_room" not in child_text
    assert "REJECTED_NARRATIVE_BODY" not in child_text

    assert gateway.allowed_tools == [
        ("submit_dungeon_room_narrative",),
        ("submit_dungeon_room_narrative",),
    ]
    schema_text = json.dumps(gateway.tool_schemas[0][0].parameters)
    assert "DungeonRoomNarrativeEnrichmentOutput" in schema_text
    assert "accepted_mechanics" not in schema_text
    assert "topology" not in schema_text
    initial_document = json.loads(gateway.messages[0][0].content)
    assert [room["room_id"] for room in initial_document["context"]["rooms"]] == list(
        selection.room_ids
    )
    repair_document = json.loads(gateway.messages[1][0].content)
    assert repair_document["context"] == initial_document["context"]
    assert repair_document["previous_arguments"] == rejected
    assert {item["code"] for item in repair_document["diagnostics"]} == {
        "room_narrative_enrichment.room_invalid",
        "room_narrative_enrichment.room_missing",
    }
    prior_profile_ids = {
        root.puzzle_profile.task_profile_id,
        prepared.base.base.base.profile.task_profile_id,
        prepared.base.base.feature_profile_id,
        prepared.base.trap_profile_id,
        prepared.objective_profile_id,
    }
    assert profile.task_profile_id not in prior_profile_ids
    assert profile.token_budget == 6_000
    assert profile.override_notes == {"output_token_limit": 2_048, "repair_limit": 1}
    assert gateway.profiles[1].token_budget == 5_320
    estimated_input = gateway.profiles[1].override_notes["estimated_input_tokens"]
    assert isinstance(estimated_input, int) and estimated_input > 0
    assert gateway.profiles[1].override_notes["output_token_limit"] <= (
        gateway.profiles[1].token_budget - estimated_input
    )

    attempt_run = root.preparation.get_generation_run(
        root.campaign_id, attempt.attempt_run_id
    )
    report_text = json.dumps(attempt_run.validation_report)
    assert (
        attempt_run.validation_report["code"]
        == "dungeon_room_narrative_prompt_completed"
    )
    assert valid["rooms"][0]["read_aloud"] not in report_text  # type: ignore[index]
    artifact_run = root.preparation.get_generation_run(
        root.campaign_id, attempt.result.generation_run_id
    )
    assert artifact_run.generation_kind == "dungeon_room_narrative_enrichment"
    assert artifact_run.model_task_profile_id == profile.task_profile_id
    assert artifact_run.tool_runs[0]["tool_name"] == "submit_dungeon_room_narrative"

    parent_assets = root.preparation.list_assets(root.campaign_id, prepared.version_id)
    child_assets = root.preparation.list_assets(root.campaign_id, child.id)
    map_roles = {
        ArtifactAssetRole.DM_SVG,
        ArtifactAssetRole.PLAYER_SVG,
        ArtifactAssetRole.DM_PNG,
        ArtifactAssetRole.PLAYER_PNG,
        ArtifactAssetRole.MANIFEST,
    }
    assert {
        (item.role, item.ordinal, item.sha256)
        for item in parent_assets
        if item.role in map_roles
    } == {
        (item.role, item.ordinal, item.sha256)
        for item in child_assets
        if item.role in map_roles
    }


def test_room_narrative_publication_failure_keeps_objective_parent_body_free(
    db_engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared = _prepare_objective_copper(db_engine, tmp_path, monkeypatch)
    selection = _selection(prepared)
    valid = _narrative_output(prepared.specification.package.id, selection.room_ids)
    gateway = staged.FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_room_narrative",
                        call_id="accepted-before-publication-failure",
                        arguments=valid,
                    ),
                ),
                input_tokens=260,
                output_tokens=420,
            ),
        )
    )
    root = prepared.base.base.base.base

    def fail_publication(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise RuntimeError("REJECTED_NARRATIVE_PUBLICATION_BODY")

    monkeypatch.setattr(root.preparation, "publish_generated_package", fail_publication)
    attempt = DungeonRoomNarrativePromptApplicationService(
        root.preparation,
        DungeonRoomNarrativePromptService(root.studio, gateway),
    ).execute(_command(prepared, selection), _profile(), surface="integration")

    assert attempt.result is None
    assert attempt.public_code == "dungeon_room_narrative_prompt_failed"
    assert (
        root.preparation.get_artifact(
            root.campaign_id, root.artifact_id
        ).current_version_id
        == prepared.version_id
    )
    run = root.preparation.get_generation_run(root.campaign_id, attempt.attempt_run_id)
    assert run.validation_report == {
        "stage": "projection",
        "code": "dungeon_room_narrative_prompt_failed",
    }
    report_text = json.dumps(run.validation_report)
    assert "REJECTED_NARRATIVE_PUBLICATION_BODY" not in report_text
    assert valid["rooms"][0]["read_aloud"] not in report_text  # type: ignore[index]


def test_failed_faux_room_narrative_keeps_objective_parent_body_free(
    db_engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared = _prepare_objective_copper(db_engine, tmp_path, monkeypatch)
    selection = _selection(prepared)
    invalid = _narrative_output(prepared.specification.package.id, selection.room_ids)
    invalid_rooms = invalid["rooms"]
    assert isinstance(invalid_rooms, list)
    invalid_rooms[0]["room_id"] = "foreign_rejected_room"
    invalid_rooms[0]["read_aloud"] = "REJECTED_NARRATIVE_FAILURE_BODY"

    def completion(call_id: str) -> GatewayCompletion:
        return GatewayCompletion(
            tool_calls=(
                ToolCall(
                    tool_name="submit_dungeon_room_narrative",
                    call_id=call_id,
                    arguments=invalid,
                ),
            ),
            input_tokens=300,
            output_tokens=450,
        )

    gateway = staged.FakeGatewayClient(
        (completion("invalid-initial"), completion("invalid-repair"))
    )
    root = prepared.base.base.base.base
    attempt = DungeonRoomNarrativePromptApplicationService(
        root.preparation,
        DungeonRoomNarrativePromptService(root.studio, gateway),
    ).execute(_command(prepared, selection), _profile(), surface="integration")

    assert attempt.result is None
    assert attempt.public_code == "dungeon_room_narrative_prompt_rejected_after_repair"
    assert (
        root.preparation.get_artifact(
            root.campaign_id, root.artifact_id
        ).current_version_id
        == prepared.version_id
    )
    run = root.preparation.get_generation_run(root.campaign_id, attempt.attempt_run_id)
    assert run.status.value == "failed"
    assert run.validation_report["repair_attempted"] is True
    report_text = json.dumps(run.validation_report)
    assert "room_narrative_enrichment.room_invalid" in report_text
    assert "foreign_rejected_room" not in report_text
    assert "REJECTED_NARRATIVE_FAILURE_BODY" not in report_text
    assert len(gateway.messages) == 2
    assert gateway.profiles[1].token_budget == gateway.profiles[0].token_budget - 750
