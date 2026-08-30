"""Faux-provider objective enrichment over the staged Copper Tide trap child."""

import json
import uuid
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

import pytest
import test_dungeon_exploration_prompt as staged
import test_dungeon_trap_prompt as trapped
from sqlalchemy import Engine

from dm_assistant.modules.modeling import (
    ReasoningEffort,
    ResolvedModelRunProfile,
    ToolCall,
)
from dm_assistant.modules.preparation import ArtifactAssetRole
from dm_assistant.orchestration.dungeons import (
    DungeonObjectiveContextSelection,
    DungeonObjectivePromptApplicationService,
    DungeonObjectivePromptService,
    DungeonStudioSpecification,
    DungeonTrapPromptApplicationService,
    DungeonTrapPromptService,
    PromptDungeonObjectiveWorkflow,
    PromptDungeonTrapWorkflow,
    resolve_dungeon_objective_prompt_profile,
    resolve_dungeon_trap_prompt_profile,
)
from dm_assistant.orchestration.modeling import GatewayCompletion
from dm_dungeon import to_canonical_json

pytestmark = pytest.mark.integration


def _objective_output(
    *,
    package_id: str,
    room_id: str,
    objective_id: str,
    mechanic_ids: tuple[str, ...],
) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "package_id": package_id,
        "room_id": room_id,
        "objective_id": objective_id,
        "observable_goal": (
            "The synthetic tide gauge rests in a slotted cradle while its copper "
            "floats continue to rise and fall."
        ),
        "resolution_guidance": (
            "The gauge can be secured once the cradle is steady; reward plans that "
            "reuse understood foundry mechanisms without requiring one sequence."
        ),
        "resolutions": [
            {
                "mechanic_ids": [mechanic_ids[0], mechanic_ids[1]],
                "action": (
                    "Balance the ladle rail against the calibrated floats and lift "
                    "the gauge straight from its cradle."
                ),
                "outcome": (
                    "The gauge comes free intact for the return across the stabilized "
                    "casting walk."
                ),
            },
            {
                "mechanic_ids": [mechanic_ids[2], mechanic_ids[3]],
                "action": (
                    "Equalize the sight glasses, then brace the cradle with the "
                    "secured counterweight line."
                ),
                "outcome": (
                    "The cradle stays level long enough to release the retaining pin."
                ),
            },
        ],
        "setback_or_aftermath": (
            "If the cradle tilts, brine fills its catch basin and must be drained "
            "before another attempt; the gauge is not destroyed."
        ),
    }


@dataclass(frozen=True)
class PreparedTrappedCopper:
    base: trapped.PreparedCopper
    version_id: uuid.UUID
    specification: DungeonStudioSpecification
    trap_profile_id: uuid.UUID


def _prepare_trapped_copper(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> PreparedTrappedCopper:
    prepared = trapped._prepare_featured_copper(engine, tmp_path, monkeypatch)
    selection = trapped._selection(prepared)
    gateway = staged.FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_trap",
                        call_id="copper-trap",
                        arguments=trapped._trap_output(
                            package_id=prepared.specification.package.id,
                            room_id=selection.room_id,
                            trap_id=selection.trap_id,
                        ),
                    ),
                ),
                input_tokens=200,
                output_tokens=340,
            ),
        )
    )
    profile = resolve_dungeon_trap_prompt_profile(
        provider_id="faux",
        model_id="faux_deterministic_v1",
        capabilities=("text", "tool_calls", "thinking"),
        context_window_tokens=16_384,
        output_token_limit=4_096,
        requested_effort=ReasoningEffort.FAST,
    )
    attempt = DungeonTrapPromptApplicationService(
        prepared.base.base.preparation,
        DungeonTrapPromptService(prepared.base.base.studio, gateway),
    ).execute(
        PromptDungeonTrapWorkflow(
            campaign_id=prepared.base.base.campaign_id,
            artifact_id=prepared.base.base.artifact_id,
            parent_version_id=prepared.version_id,
            selection=selection,
            created_by="synthetic-dm",
        ),
        profile,
        surface="integration-setup",
    )
    assert attempt.result is not None and attempt.result.artifact_version_id is not None
    version = prepared.base.base.preparation.get_version(
        prepared.base.base.campaign_id, attempt.result.artifact_version_id
    )
    return PreparedTrappedCopper(
        base=prepared,
        version_id=version.id,
        specification=DungeonStudioSpecification.model_validate_json(
            json.dumps(version.specification)
        ),
        trap_profile_id=profile.task_profile_id,
    )


def _selection(prepared: PreparedTrappedCopper) -> DungeonObjectiveContextSelection:
    guide = prepared.specification.dm_guide
    assert guide is not None
    objective = guide.objectives[0]
    puzzle = guide.puzzles[0]
    exploration = next(
        room for room in guide.rooms if room.encounter_content is not None
    )
    feature = next(item for item in guide.features if item.content is not None)
    trap = next(item for item in guide.traps if item.warning is not None)
    assert exploration.encounter_slot_id is not None
    return DungeonObjectiveContextSelection(
        room_id=objective.room_id,
        objective_id=objective.marker_id,
        mechanic_ids=(
            puzzle.room_id,
            exploration.encounter_slot_id,
            feature.marker_id,
            trap.marker_id,
        ),
        stakes=(
            "Recover the gauge intact; a setback costs time but never destroys it."
        ),
        constraints=(
            "Offer at least two credible resolutions",
            "Do not invent machinery or alter accepted mechanics",
        ),
    )


def _command(
    prepared: PreparedTrappedCopper, selection: DungeonObjectiveContextSelection
) -> PromptDungeonObjectiveWorkflow:
    return PromptDungeonObjectiveWorkflow(
        campaign_id=prepared.base.base.base.campaign_id,
        artifact_id=prepared.base.base.base.artifact_id,
        parent_version_id=prepared.version_id,
        selection=selection,
        created_by="synthetic-dm",
    )


def _profile() -> ResolvedModelRunProfile:
    return resolve_dungeon_objective_prompt_profile(
        provider_id="faux",
        model_id="faux_deterministic_v1",
        capabilities=("text", "tool_calls", "thinking"),
        context_window_tokens=16_384,
        output_token_limit=4_096,
        requested_effort=ReasoningEffort.FAST,
    )


def test_faux_objective_task_repairs_and_publishes_atomic_preserving_trap_child(
    db_engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared = _prepare_trapped_copper(db_engine, tmp_path, monkeypatch)
    selection = _selection(prepared)
    valid = _objective_output(
        package_id=prepared.specification.package.id,
        room_id=selection.room_id,
        objective_id=selection.objective_id,
        mechanic_ids=selection.mechanic_ids,
    )
    rejected = deepcopy(valid)
    rejected["objective_id"] = "rejected_foreign_objective"
    rejected["observable_goal"] = "REJECTED_OBJECTIVE_BODY"
    gateway = staged.FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_objective",
                        call_id="invalid-objective",
                        arguments=rejected,
                    ),
                ),
                input_tokens=230,
                output_tokens=330,
            ),
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_objective",
                        call_id="repaired-objective",
                        arguments=valid,
                    ),
                ),
                input_tokens=300,
                output_tokens=440,
            ),
        )
    )
    profile = _profile()
    attempt = DungeonObjectivePromptApplicationService(
        prepared.base.base.base.preparation,
        DungeonObjectivePromptService(prepared.base.base.base.studio, gateway),
    ).execute(_command(prepared, selection), profile, surface="integration")

    assert attempt.public_code == "dungeon_objective_prompt_completed"
    assert attempt.result is not None and attempt.result.success
    assert attempt.result.artifact_version_id is not None
    child = prepared.base.base.base.preparation.get_version(
        prepared.base.base.base.campaign_id, attempt.result.artifact_version_id
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
        child_spec.objective_model_lineage[-1].output.objective_id
        == selection.objective_id
    )
    assert (
        child_spec.dm_guide is not None and prepared.specification.dm_guide is not None
    )
    assert child_spec.dm_guide.rooms == prepared.specification.dm_guide.rooms
    assert child_spec.dm_guide.puzzles == prepared.specification.dm_guide.puzzles
    assert child_spec.dm_guide.features == prepared.specification.dm_guide.features
    assert child_spec.dm_guide.traps == prepared.specification.dm_guide.traps
    target = next(
        item
        for item in child_spec.dm_guide.objectives
        if item.marker_id == selection.objective_id
    )
    assert target.content is not None
    assert target.content.situation == valid["observable_goal"]
    assert all(
        item
        == next(
            old
            for old in prepared.specification.dm_guide.objectives
            if old.marker_id == item.marker_id
        )
        for item in child_spec.dm_guide.objectives
        if item.marker_id != selection.objective_id
    )
    assert prepared.specification.preparation_readiness is not None
    assert child_spec.preparation_readiness is not None
    objective_issue = next(
        item
        for item in prepared.specification.dm_guide.content_issues
        if item.kind == "objective"
    )
    objective_diagnostic = next(
        item
        for item in prepared.specification.preparation_readiness.diagnostics
        if item.component_id == objective_issue.target_ref
        and "runnable guide content" in item.message
    )
    assert child_spec.preparation_readiness.diagnostics == tuple(
        item
        for item in prepared.specification.preparation_readiness.diagnostics
        if item != objective_diagnostic
    )
    child_text = json.dumps(child.specification)
    assert "rejected_foreign_objective" not in child_text
    assert "REJECTED_OBJECTIVE_BODY" not in child_text

    assert gateway.allowed_tools == [
        ("submit_dungeon_objective",),
        ("submit_dungeon_objective",),
    ]
    schema_text = json.dumps(gateway.tool_schemas[0][0].parameters)
    assert "DungeonObjectiveEnrichmentOutput" in schema_text
    assert "objective_kind" not in schema_text
    prompt_document = json.loads(gateway.messages[0][0].content)
    assert (
        prompt_document["context"]["objective"]["objective_id"]
        == selection.objective_id
    )
    assert {
        item["mechanic_id"] for item in prompt_document["context"]["accepted_mechanics"]
    } == set(selection.mechanic_ids)
    repair_document = json.loads(gateway.messages[1][0].content)
    assert repair_document["previous_arguments"] == rejected
    assert (
        repair_document["diagnostics"][0]["code"]
        == "objective_enrichment.objective_mismatch"
    )
    assert profile.task_profile_id not in {
        prepared.base.base.base.puzzle_profile.task_profile_id,
        prepared.base.base.profile.task_profile_id,
        prepared.base.feature_profile_id,
        prepared.trap_profile_id,
    }
    assert profile.token_budget == 6_000
    assert profile.override_notes == {"output_token_limit": 2_048, "repair_limit": 1}
    assert gateway.profiles[1].token_budget == 5_440
    estimated_input = gateway.profiles[1].override_notes["estimated_input_tokens"]
    assert isinstance(estimated_input, int) and estimated_input > 0
    assert gateway.profiles[1].override_notes["output_token_limit"] <= (
        gateway.profiles[1].token_budget - estimated_input
    )

    attempt_run = prepared.base.base.base.preparation.get_generation_run(
        prepared.base.base.base.campaign_id, attempt.attempt_run_id
    )
    report_text = json.dumps(attempt_run.validation_report)
    assert attempt_run.validation_report["code"] == "dungeon_objective_prompt_completed"
    assert "observable_goal" not in report_text
    assert valid["resolution_guidance"] not in report_text
    artifact_run = prepared.base.base.base.preparation.get_generation_run(
        prepared.base.base.base.campaign_id, attempt.result.generation_run_id
    )
    assert artifact_run.generation_kind == "dungeon_objective_enrichment"
    assert artifact_run.model_task_profile_id == profile.task_profile_id
    assert artifact_run.tool_runs[0]["tool_name"] == "submit_dungeon_objective"

    parent_assets = prepared.base.base.base.preparation.list_assets(
        prepared.base.base.base.campaign_id, prepared.version_id
    )
    child_assets = prepared.base.base.base.preparation.list_assets(
        prepared.base.base.base.campaign_id, child.id
    )
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


def test_objective_publication_failure_keeps_trap_parent_and_body_free_diagnostics(
    db_engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared = _prepare_trapped_copper(db_engine, tmp_path, monkeypatch)
    selection = _selection(prepared)
    valid = _objective_output(
        package_id=prepared.specification.package.id,
        room_id=selection.room_id,
        objective_id=selection.objective_id,
        mechanic_ids=selection.mechanic_ids,
    )
    gateway = staged.FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_objective",
                        call_id="accepted-before-publication-failure",
                        arguments=valid,
                    ),
                ),
                input_tokens=220,
                output_tokens=320,
            ),
        )
    )

    def fail_publication(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise RuntimeError("REJECTED_OBJECTIVE_PUBLICATION_BODY")

    monkeypatch.setattr(
        prepared.base.base.base.preparation,
        "publish_generated_package",
        fail_publication,
    )
    attempt = DungeonObjectivePromptApplicationService(
        prepared.base.base.base.preparation,
        DungeonObjectivePromptService(prepared.base.base.base.studio, gateway),
    ).execute(_command(prepared, selection), _profile(), surface="integration")

    assert attempt.result is None
    assert attempt.public_code == "dungeon_objective_prompt_failed"
    artifact = prepared.base.base.base.preparation.get_artifact(
        prepared.base.base.base.campaign_id, prepared.base.base.base.artifact_id
    )
    assert artifact.current_version_id == prepared.version_id
    run = prepared.base.base.base.preparation.get_generation_run(
        prepared.base.base.base.campaign_id, attempt.attempt_run_id
    )
    report_text = json.dumps(run.validation_report)
    assert run.validation_report == {
        "stage": "projection",
        "code": "dungeon_objective_prompt_failed",
    }
    assert "REJECTED_OBJECTIVE_PUBLICATION_BODY" not in report_text
    assert valid["observable_goal"] not in report_text


def test_failed_faux_objective_keeps_trap_parent_and_body_free_diagnostics(
    db_engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared = _prepare_trapped_copper(db_engine, tmp_path, monkeypatch)
    selection = _selection(prepared)
    invalid = _objective_output(
        package_id=prepared.specification.package.id,
        room_id=selection.room_id,
        objective_id=selection.objective_id,
        mechanic_ids=selection.mechanic_ids,
    )
    invalid["resolutions"][0]["mechanic_ids"] = ["foreign_rejected_mechanic"]  # type: ignore[index]
    invalid["observable_goal"] = "REJECTED_OBJECTIVE_FAILURE_BODY"

    def completion(call_id: str) -> GatewayCompletion:
        return GatewayCompletion(
            tool_calls=(
                ToolCall(
                    tool_name="submit_dungeon_objective",
                    call_id=call_id,
                    arguments=invalid,
                ),
            ),
            input_tokens=300,
            output_tokens=400,
        )

    gateway = staged.FakeGatewayClient(
        (completion("invalid-initial"), completion("invalid-repair"))
    )
    attempt = DungeonObjectivePromptApplicationService(
        prepared.base.base.base.preparation,
        DungeonObjectivePromptService(prepared.base.base.base.studio, gateway),
    ).execute(_command(prepared, selection), _profile(), surface="integration")

    assert attempt.result is None
    assert attempt.public_code == "dungeon_objective_prompt_rejected_after_repair"
    artifact = prepared.base.base.base.preparation.get_artifact(
        prepared.base.base.base.campaign_id, prepared.base.base.base.artifact_id
    )
    assert artifact.current_version_id == prepared.version_id
    run = prepared.base.base.base.preparation.get_generation_run(
        prepared.base.base.base.campaign_id, attempt.attempt_run_id
    )
    assert run.status.value == "failed"
    assert run.validation_report["repair_attempted"] is True
    report_text = json.dumps(run.validation_report)
    assert "objective_enrichment.mechanic_invalid" in report_text
    assert "foreign_rejected_mechanic" not in report_text
    assert "REJECTED_OBJECTIVE_FAILURE_BODY" not in report_text
    assert len(gateway.messages) == 2
    assert gateway.profiles[1].token_budget == gateway.profiles[0].token_budget - 700
