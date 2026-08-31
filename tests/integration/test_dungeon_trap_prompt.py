"""Faux-provider trap enrichment over independent staged Copper Tide content."""

import json
import uuid
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

import pytest
import test_dungeon_exploration_prompt as staged
from sqlalchemy import Engine

from dm_assistant.modules.modeling import ReasoningEffort, ToolCall
from dm_assistant.modules.preparation import ArtifactAssetRole
from dm_assistant.orchestration.dungeons import (
    DungeonFeatureInteractionContextSelection,
    DungeonFeatureInteractionPromptApplicationService,
    DungeonFeatureInteractionPromptService,
    DungeonStudioSpecification,
    DungeonTrapContextSelection,
    DungeonTrapPromptApplicationService,
    DungeonTrapPromptService,
    PromptDungeonFeatureInteractionWorkflow,
    PromptDungeonTrapWorkflow,
    resolve_dungeon_feature_interaction_prompt_profile,
    resolve_dungeon_trap_prompt_profile,
)
from dm_assistant.orchestration.modeling import GatewayCompletion
from dm_dungeon import to_canonical_json

pytestmark = pytest.mark.integration


def _structural_proposal() -> dict[str, object]:
    return {
        "proposal_version": "1",
        "plan": {
            "schema_version": "1.0.0",
            "title": "Copper Tide Foundry",
            "premise": "Recover a synthetic tide gauge from an abandoned tidal foundry.",
            "themes": ["salt-stained copper", "slow tidal machinery"],
            "rooms": [
                {
                    "ref": "portico",
                    "name": "Sluice Vestibule",
                    "role": "entrance",
                    "purpose": "Introduce the foundry's tide-driven mechanisms.",
                },
                {
                    "ref": "gallery",
                    "name": "Casting Walk",
                    "role": "exploration",
                    "purpose": "Cross a wet casting channel using the overhead ladle rail.",
                    "encounter": "exploration",
                },
                {
                    "ref": "oriel",
                    "name": "Calibration Loft",
                    "role": "puzzle",
                    "purpose": "Align three floats to release the gauge cabinet.",
                },
                {
                    "ref": "nursery",
                    "name": "Gauge Vault",
                    "role": "objective",
                    "purpose": "Hold the named synthetic tide gauge.",
                },
            ],
            "critical_path": ["portico", "gallery", "oriel", "nursery"],
            "room_contents": [
                {
                    "room_ref": "portico",
                    "trap": {"name": "Counterweight Sweep", "challenge": "moderate"},
                },
                {
                    "room_ref": "gallery",
                    "feature": {
                        "kind": "other",
                        "name": "Overhead Ladle Rail",
                        "description": "A hand chain moves an empty copper ladle above the channel.",
                    },
                },
                {
                    "room_ref": "oriel",
                    "feature": {
                        "kind": "other",
                        "name": "Float Calibration Rack",
                        "description": "Three copper floats slide beside etched tide marks.",
                    },
                },
                {
                    "room_ref": "nursery",
                    "feature": {
                        "kind": "other",
                        "name": "Gauge Equalizer",
                        "description": "A handwheel balances two brine sight glasses.",
                    },
                    "trap": {"name": "Brine Vent", "challenge": "high"},
                    "objective": "Synthetic Tide Gauge",
                },
            ],
        },
    }


def _puzzle_output(
    *, package_id: str, room_id: str, affordance_id: str
) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "package_id": package_id,
        "room_id": room_id,
        "name": "Three Copper Floats",
        "observable_elements": [
            "Three floats rest at different heights beside etched tide marks.",
            "A common feed pipe raises one float whenever another falls.",
        ],
        "solution_steps": ["Balance all three floats at their matching tide marks."],
        "clue_path": [
            {
                "location_id": affordance_id,
                "observation": "Each tide mark bears the same three-wave stamp.",
                "inference": "The floats must align together rather than in sequence.",
            }
        ],
        "alternate_handling": [
            {
                "approach": "Hold one float while adjusting the other two feeds.",
                "adjudication": "A steady brace substitutes for closing that float's valve.",
            }
        ],
        "success_outcome": "The gauge cabinet latch releases when the floats align.",
        "failure_consequence": "An unbalanced float drains slowly to its starting mark.",
        "reset_or_retry": "Opening the common drain returns all three floats to the bottom.",
    }


def _exploration_output(
    *, package_id: str, room_id: str, encounter_slot_id: str, affordance_id: str
) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "package_id": package_id,
        "room_id": room_id,
        "encounter_slot_id": encounter_slot_id,
        "observable_cues": [
            "A wet casting channel divides the walk while an empty ladle hangs above it.",
            "The ladle's hand chain runs the full length of an overhead rail.",
        ],
        "approaches": [
            {
                "affordance_ids": [affordance_id],
                "action": "Ride the empty ladle across by working the hand chain.",
                "adjudication": "A second character can pull the ladle steadily from either bank.",
                "consequence": "The rider crosses with only what fits inside the ladle.",
            },
            {
                "affordance_ids": [affordance_id],
                "action": "Lock the ladle midway and use its chain as a guide line.",
                "adjudication": "A secure knot or rail pin holds the chain under tension.",
                "consequence": "The group crosses together but leaves the ladle fixed overhead.",
            },
        ],
        "escalation": "After a prolonged delay, the next tide deepens the casting channel.",
        "recovery": "Opening the floor sluice drains the channel and returns the ladle to its stop.",
    }


def _feature_output(
    *, package_id: str, room_id: str, feature_id: str
) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "package_id": package_id,
        "room_id": room_id,
        "feature_id": feature_id,
        "observable_setup": [
            "One brine sight glass is full while the other stands nearly empty.",
            "Turning the equalizer wheel changes both levels in opposite directions.",
        ],
        "affordances": [
            {
                "action": "Turn the wheel until both glasses meet their center marks.",
                "adjudication": "Slow adjustments reveal both levels settling toward balance.",
                "consequence": "Balanced pressure clears brine from the gauge cabinet.",
            },
            {
                "action": "Clamp the full feed while feathering the equalizer wheel.",
                "adjudication": "A soft clamp can hold the line without prescribing one tool.",
                "consequence": "The cabinet clears, but the clamp must be released afterward.",
            },
        ],
        "reset_or_retry": "The drain cock empties both glasses and resets the wheel.",
    }


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
            "A swept character ends beside the still-closed inner door.",
        ],
        "reset_or_recovery": "Closing the door slowly lowers the weight to its start.",
    }


def _patch_copper_case(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(staged, "_structural_proposal", _structural_proposal)
    monkeypatch.setattr(staged, "_puzzle_output", _puzzle_output)
    monkeypatch.setattr(staged, "_exploration_output", _exploration_output)
    monkeypatch.setattr(staged, "_feature_output", _feature_output)


@dataclass(frozen=True)
class PreparedCopper:
    base: staged.PreparedExploredSkyroot
    version_id: uuid.UUID
    specification: DungeonStudioSpecification
    feature_profile_id: uuid.UUID


def _prepare_featured_copper(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> PreparedCopper:
    _patch_copper_case(monkeypatch)
    prepared = staged._prepare_explored_skyroot(engine, tmp_path)
    room_id = prepared.base.room_ids["nursery"]
    feature_id = prepared.base.feature_ids[room_id]
    selection = DungeonFeatureInteractionContextSelection(
        room_id=room_id,
        feature_id=feature_id,
        interaction_goal="Balance brine pressure before removing the tide gauge.",
        stakes="A poor adjustment drenches supplies but never destroys the gauge.",
        constraints=("Keep the wheel and two sight glasses as the complete apparatus",),
    )
    gateway = staged.FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_feature_interaction",
                        call_id="copper-feature",
                        arguments=_feature_output(
                            package_id=prepared.specification.package.id,
                            room_id=room_id,
                            feature_id=feature_id,
                        ),
                    ),
                ),
                input_tokens=180,
                output_tokens=320,
            ),
        )
    )
    profile = resolve_dungeon_feature_interaction_prompt_profile(
        provider_id="faux",
        model_id="faux_deterministic_v1",
        capabilities=("text", "tool_calls", "thinking"),
        context_window_tokens=16_384,
        output_token_limit=4_096,
        requested_effort=ReasoningEffort.FAST,
    )
    attempt = DungeonFeatureInteractionPromptApplicationService(
        prepared.base.preparation,
        DungeonFeatureInteractionPromptService(prepared.base.studio, gateway),
    ).execute(
        PromptDungeonFeatureInteractionWorkflow(
            campaign_id=prepared.base.campaign_id,
            artifact_id=prepared.base.artifact_id,
            parent_version_id=prepared.version_id,
            selection=selection,
            created_by="synthetic-dm",
        ),
        profile,
        surface="integration-setup",
    )
    assert attempt.result is not None and attempt.result.artifact_version_id is not None
    version = prepared.base.preparation.get_version(
        prepared.base.campaign_id, attempt.result.artifact_version_id
    )
    return PreparedCopper(
        base=prepared,
        version_id=version.id,
        specification=DungeonStudioSpecification.model_validate_json(
            json.dumps(version.specification)
        ),
        feature_profile_id=profile.task_profile_id,
    )


def _selection(prepared: PreparedCopper) -> DungeonTrapContextSelection:
    room_id = prepared.base.base.room_ids["portico"]
    trap_id = next(
        item.id
        for item in prepared.specification.layout_request.mechanics_plan.room_traps
        if item.room_id == room_id
    )
    return DungeonTrapContextSelection(
        room_id=room_id,
        trap_id=trap_id,
        stakes="The sweep scatters supplies without sealing the only route.",
        constraints=(
            "Keep the door chain, shared pulley, and one padded counterweight",
            "Do not invent numeric difficulty values",
        ),
    )


def test_faux_trap_task_repairs_and_publishes_atomic_preserving_child(
    db_engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared = _prepare_featured_copper(db_engine, tmp_path, monkeypatch)
    assert prepared.specification.creative_continuity is not None
    continuity_hash = prepared.specification.creative_continuity.projection_sha256
    selection = _selection(prepared)
    valid = _trap_output(
        package_id=prepared.specification.package.id,
        room_id=selection.room_id,
        trap_id=selection.trap_id,
    )
    rejected = deepcopy(valid)
    rejected["trap_id"] = "rejected_foreign_trap"
    rejected["effect_narration"] = "REJECTED_TRAP_BODY"
    gateway = staged.FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_trap",
                        call_id="invalid-trap",
                        arguments=rejected,
                    ),
                ),
                input_tokens=220,
                output_tokens=320,
            ),
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_trap",
                        call_id="repaired-trap",
                        arguments=valid,
                    ),
                ),
                input_tokens=290,
                output_tokens=430,
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
        surface="integration",
    )

    assert attempt.public_code == "dungeon_trap_prompt_completed"
    assert attempt.result is not None and attempt.result.success
    assert attempt.result.artifact_version_id is not None
    child = prepared.base.base.preparation.get_version(
        prepared.base.base.campaign_id, attempt.result.artifact_version_id
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
    assert child_spec.trap_model_lineage[-1].output.trap_id == selection.trap_id
    assert (
        child_spec.trap_model_lineage[-1].creative_continuity_sha256 == continuity_hash
    )
    assert (
        child_spec.dm_guide is not None and prepared.specification.dm_guide is not None
    )
    assert child_spec.dm_guide.rooms == prepared.specification.dm_guide.rooms
    assert child_spec.dm_guide.puzzles == prepared.specification.dm_guide.puzzles
    assert child_spec.dm_guide.features == prepared.specification.dm_guide.features
    target = next(
        item
        for item in child_spec.dm_guide.traps
        if item.marker_id == selection.trap_id
    )
    assert target.warning == valid["observable_warning"]
    assert target.detection_difficulty == next(
        item.detection_difficulty
        for item in prepared.specification.dm_guide.traps
        if item.marker_id == selection.trap_id
    )
    assert all(
        item
        == next(
            old
            for old in prepared.specification.dm_guide.traps
            if old.marker_id == item.marker_id
        )
        for item in child_spec.dm_guide.traps
        if item.marker_id != selection.trap_id
    )
    assert prepared.specification.preparation_readiness is not None
    assert child_spec.preparation_readiness is not None
    assert not any(
        item.component_id == selection.trap_id
        for item in child_spec.preparation_readiness.diagnostics
    )
    assert child_spec.preparation_readiness.diagnostics == tuple(
        item
        for item in prepared.specification.preparation_readiness.diagnostics
        if item.component_id != selection.trap_id
    )
    child_text = json.dumps(child.specification)
    assert "rejected_foreign_trap" not in child_text
    assert "REJECTED_TRAP_BODY" not in child_text

    assert gateway.allowed_tools == [
        ("submit_dungeon_trap",),
        ("submit_dungeon_trap",),
    ]
    schema_text = json.dumps(gateway.tool_schemas[0][0].parameters)
    assert "DungeonTrapEnrichmentOutput" in schema_text
    assert "detection_difficulty" not in schema_text
    prompt_document = json.loads(gateway.messages[0][0].content)
    assert prompt_document["context"]["trap"]["trap_id"] == selection.trap_id
    assert prompt_document["context"]["trap"]["detection_difficulty"] >= 0
    assert (
        prompt_document["context"]["continuity"]["projection_sha256"] == continuity_hash
    )
    repair_document = json.loads(gateway.messages[1][0].content)
    assert repair_document["previous_arguments"] == rejected
    assert repair_document["diagnostics"][0]["code"] == "trap_enrichment.trap_mismatch"
    assert profile.task_profile_id not in {
        prepared.base.base.puzzle_profile.task_profile_id,
        prepared.base.profile.task_profile_id,
        prepared.feature_profile_id,
    }
    assert profile.token_budget == 6_000
    assert profile.override_notes == {"output_token_limit": 2_048, "repair_limit": 1}
    assert gateway.profiles[1].token_budget == 5_460
    estimated_input = gateway.profiles[1].override_notes["estimated_input_tokens"]
    assert isinstance(estimated_input, int) and estimated_input > 0
    assert gateway.profiles[1].override_notes["output_token_limit"] <= (
        gateway.profiles[1].token_budget - estimated_input
    )

    attempt_run = prepared.base.base.preparation.get_generation_run(
        prepared.base.base.campaign_id, attempt.attempt_run_id
    )
    report_text = json.dumps(attempt_run.validation_report)
    assert attempt_run.validation_report["code"] == "dungeon_trap_prompt_completed"
    assert "observable_warning" not in report_text
    assert valid["trigger"] not in report_text
    artifact_run = prepared.base.base.preparation.get_generation_run(
        prepared.base.base.campaign_id, attempt.result.generation_run_id
    )
    assert artifact_run.generation_kind == "dungeon_trap_enrichment"
    assert artifact_run.model_task_profile_id == profile.task_profile_id
    assert artifact_run.input_scope["creative_continuity_sha256"] == continuity_hash
    assert artifact_run.schema_versions["dungeon_creative_continuity"] == "1.0.0"
    assert (
        artifact_run.validation_report["trap_enrichment"]["creative_continuity_sha256"]
        == continuity_hash
    )
    assert artifact_run.tool_runs[0]["tool_name"] == "submit_dungeon_trap"

    parent_assets = prepared.base.base.preparation.list_assets(
        prepared.base.base.campaign_id, prepared.version_id
    )
    child_assets = prepared.base.base.preparation.list_assets(
        prepared.base.base.campaign_id, child.id
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


def test_trap_publication_failure_keeps_parent_and_body_free_diagnostics(
    db_engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared = _prepare_featured_copper(db_engine, tmp_path, monkeypatch)
    selection = _selection(prepared)
    valid = _trap_output(
        package_id=prepared.specification.package.id,
        room_id=selection.room_id,
        trap_id=selection.trap_id,
    )
    gateway = staged.FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_trap",
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
        raise RuntimeError("REJECTED_TRAP_PUBLICATION_BODY")

    monkeypatch.setattr(
        prepared.base.base.preparation,
        "publish_generated_package",
        fail_publication,
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
        resolve_dungeon_trap_prompt_profile(
            provider_id="faux",
            model_id="faux_deterministic_v1",
            capabilities=("text", "tool_calls"),
            context_window_tokens=16_384,
            output_token_limit=4_096,
        ),
        surface="integration",
    )

    assert attempt.result is None
    assert attempt.public_code == "dungeon_trap_prompt_failed"
    artifact = prepared.base.base.preparation.get_artifact(
        prepared.base.base.campaign_id, prepared.base.base.artifact_id
    )
    assert artifact.current_version_id == prepared.version_id
    assert (
        len(
            prepared.base.base.preparation.list_versions(
                prepared.base.base.campaign_id, prepared.base.base.artifact_id
            )
        )
        == 4
    )
    run = prepared.base.base.preparation.get_generation_run(
        prepared.base.base.campaign_id, attempt.attempt_run_id
    )
    report_text = json.dumps(run.validation_report)
    assert run.validation_report == {
        "stage": "projection",
        "code": "dungeon_trap_prompt_failed",
    }
    assert "REJECTED_TRAP_PUBLICATION_BODY" not in report_text
    assert valid["observable_warning"] not in report_text


def test_failed_faux_trap_keeps_parent_and_body_free_diagnostics(
    db_engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared = _prepare_featured_copper(db_engine, tmp_path, monkeypatch)
    selection = _selection(prepared)
    invalid = _trap_output(
        package_id=prepared.specification.package.id,
        room_id=selection.room_id,
        trap_id="foreign_rejected_trap",
    )
    invalid["effect_narration"] = "REJECTED_TRAP_FAILURE_BODY"

    def completion(call_id: str) -> GatewayCompletion:
        return GatewayCompletion(
            tool_calls=(
                ToolCall(
                    tool_name="submit_dungeon_trap",
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
        resolve_dungeon_trap_prompt_profile(
            provider_id="faux",
            model_id="faux_deterministic_v1",
            capabilities=("text", "tool_calls"),
            context_window_tokens=16_384,
            output_token_limit=4_096,
        ),
        surface="integration",
    )

    assert attempt.result is None
    assert attempt.public_code == "dungeon_trap_prompt_rejected_after_repair"
    artifact = prepared.base.base.preparation.get_artifact(
        prepared.base.base.campaign_id, prepared.base.base.artifact_id
    )
    assert artifact.current_version_id == prepared.version_id
    assert (
        len(
            prepared.base.base.preparation.list_versions(
                prepared.base.base.campaign_id, prepared.base.base.artifact_id
            )
        )
        == 4
    )
    run = prepared.base.base.preparation.get_generation_run(
        prepared.base.base.campaign_id, attempt.attempt_run_id
    )
    assert run.status.value == "failed"
    assert run.validation_report["repair_attempted"] is True
    report_text = json.dumps(run.validation_report)
    assert "trap_enrichment.trap_mismatch" in report_text
    assert "foreign_rejected_trap" not in report_text
    assert "REJECTED_TRAP_FAILURE_BODY" not in report_text
    assert len(gateway.messages) == 2
    assert gateway.profiles[1].token_budget == gateway.profiles[0].token_budget - 700
