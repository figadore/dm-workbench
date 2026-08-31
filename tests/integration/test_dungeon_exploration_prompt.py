"""Faux-provider exploration enrichment over an accepted puzzle child version."""

import json
import uuid
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

import pytest
from sqlalchemy import Engine

from dm_assistant.adapters.assets import LocalAssetStore
from dm_assistant.db import Campaign, build_session_factory, transactional_session
from dm_assistant.modules.modeling import (
    PromptMessage,
    ReasoningEffort,
    ResolvedModelRunProfile,
    ToolCall,
)
from dm_assistant.modules.preparation import ArtifactAssetRole, PreparationService
from dm_assistant.modules.scope import TaskType, resolve_task_scope
from dm_assistant.orchestration.dungeons import (
    DungeonExplorationAffordanceApproval,
    DungeonExplorationContextSelection,
    DungeonExplorationPromptApplicationService,
    DungeonExplorationPromptService,
    DungeonFeatureInteractionContextSelection,
    DungeonFeatureInteractionPromptApplicationService,
    DungeonFeatureInteractionPromptService,
    DungeonPromptService,
    DungeonPuzzleClueApproval,
    DungeonPuzzleContextSelection,
    DungeonPuzzlePromptApplicationService,
    DungeonPuzzlePromptService,
    DungeonStudioService,
    DungeonStudioSpecification,
    PromptDungeonExplorationWorkflow,
    PromptDungeonFeatureInteractionWorkflow,
    PromptDungeonPuzzleWorkflow,
    PromptDungeonWorkflow,
    resolve_dungeon_exploration_prompt_profile,
    resolve_dungeon_feature_interaction_prompt_profile,
    resolve_dungeon_prompt_profile,
    resolve_dungeon_puzzle_prompt_profile,
)
from dm_assistant.orchestration.modeling import GatewayCompletion, GatewayToolSchema
from dm_dungeon import to_canonical_json

pytestmark = pytest.mark.integration


class FakeGatewayClient:
    def __init__(self, completions: tuple[GatewayCompletion, ...]) -> None:
        self._completions = list(completions)
        self.messages: list[tuple[PromptMessage, ...]] = []
        self.profiles: list[ResolvedModelRunProfile] = []
        self.tool_schemas: list[tuple[GatewayToolSchema, ...]] = []
        self.allowed_tools: list[tuple[str, ...]] = []

    def complete(
        self,
        *,
        profile: ResolvedModelRunProfile,
        messages: tuple[PromptMessage, ...],
        allowed_tools: tuple[str, ...],
        tool_schemas: tuple[GatewayToolSchema, ...],
    ) -> GatewayCompletion:
        self.profiles.append(profile)
        self.messages.append(messages)
        self.allowed_tools.append(allowed_tools)
        self.tool_schemas.append(tool_schemas)
        if not self._completions:
            raise AssertionError("unexpected extra completion")
        return self._completions.pop(0)


@dataclass(frozen=True)
class PreparedSkyroot:
    campaign_id: uuid.UUID
    studio: DungeonStudioService
    preparation: PreparationService
    artifact_id: uuid.UUID
    structural_version_id: uuid.UUID
    puzzle_version_id: uuid.UUID
    puzzle_specification: DungeonStudioSpecification
    room_ids: dict[str, str]
    feature_ids: dict[str, str]
    puzzle_profile: ResolvedModelRunProfile


def _structural_proposal() -> dict[str, object]:
    return {
        "proposal_version": "1",
        "plan": {
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
                    "purpose": "Cross a rain channel using surviving shutters.",
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
                        "description": "Brass counterweights move roof shutters above the rain channel.",
                    },
                },
                {
                    "room_ref": "oriel",
                    "feature": {
                        "kind": "other",
                        "name": "Prism Stand",
                        "description": "A fixed prism catches light from surviving roof panes.",
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
        },
    }


def _puzzle_output(
    *, package_id: str, room_id: str, affordance_id: str
) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "package_id": package_id,
        "room_id": room_id,
        "name": "Three Pale Beams",
        "observable_elements": [
            "A fixed prism divides the roof light into three pale beams.",
            "Three cloudy panes brighten when a beam crosses them.",
        ],
        "solution_steps": [
            "Turn the three pane frames until every pane catches one beam."
        ],
        "clue_path": [
            {
                "location_id": affordance_id,
                "observation": "The fixed prism already divides the light evenly.",
                "inference": "The pane frames, rather than the prism, are meant to move.",
            }
        ],
        "alternate_handling": [
            {
                "approach": "Reflect the beams with polished carried objects.",
                "adjudication": "Three stable reflected beams brighten the panes equally well.",
            }
        ],
        "success_outcome": "The nursery latch opens when all three panes brighten.",
        "failure_consequence": "A moved frame settles back when no beam reaches it.",
        "reset_or_retry": "The frames can be repositioned immediately.",
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
            "Rain fills the center channel while intact roof shutters hang above it.",
            "The nearest brass counterweight lifts one shutter and lowers another.",
        ],
        "approaches": [
            {
                "affordance_ids": [affordance_id],
                "action": "Work the counterweights to create a moving strip of shelter.",
                "adjudication": "Advance the safe strip whenever the group balances the next weight.",
                "consequence": "The group crosses together but leaves bulky gear for a return trip.",
            },
            {
                "affordance_ids": [affordance_id],
                "action": "Lock every raised shutter and hurry through the rain channel.",
                "adjudication": "Secure wedges or tied weights work without one prescribed tool.",
                "consequence": "The group crosses quickly, but loose gear washes to the entrance.",
            },
        ],
        "escalation": "After the second major delay, runoff reaches the lowest counterweight.",
        "recovery": "Opening the west drain lowers the water and resets the counterweights.",
    }


def _prepare_skyroot(engine: Engine, tmp_path: Path) -> PreparedSkyroot:
    campaign_id = uuid.uuid4()
    with transactional_session(build_session_factory(engine)) as session:
        session.add(Campaign(id=campaign_id, name="Synthetic Skyroot Campaign"))
    preparation = PreparationService(
        engine,
        LocalAssetStore(
            tmp_path / str(campaign_id) / "assets",
            tmp_path / str(campaign_id) / "scratch",
        ),
    )
    studio = DungeonStudioService(preparation)
    structural_gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_plan",
                        call_id="skyroot-structure",
                        arguments=_structural_proposal(),
                    ),
                ),
                input_tokens=100,
                output_tokens=200,
            ),
        )
    )
    structural = DungeonPromptService(studio, structural_gateway).create(
        PromptDungeonWorkflow(
            campaign_id=campaign_id,
            prompt="Build the synthetic Skyroot Conservatory.",
            seed=714000019,
            created_by="synthetic-dm",
            scope=resolve_task_scope(
                dm_principal_id="dm",
                campaign_owner_id="dm",
                task_type=TaskType.STANDALONE_DUNGEON,
            ),
        ),
        resolve_dungeon_prompt_profile(
            provider_id="faux",
            model_id="faux_deterministic_v1",
            capabilities=("text", "tool_calls"),
            context_window_tokens=16_384,
            output_token_limit=4_096,
        ),
    )
    assert structural.artifact_id is not None
    assert structural.artifact_version_id is not None
    structural_record = preparation.get_version(
        campaign_id, structural.artifact_version_id
    )
    structural_spec = DungeonStudioSpecification.model_validate_json(
        json.dumps(structural_record.specification)
    )
    room_ids = {
        item.ref: item.room_id
        for item in structural_spec.layout_request.certificate.rooms
    }
    feature_ids = {
        item.room_id: item.id
        for item in structural_spec.layout_request.mechanics_plan.room_features
    }
    oriel_feature_id = feature_ids[room_ids["oriel"]]
    puzzle_gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_puzzle",
                        call_id="skyroot-puzzle",
                        arguments=_puzzle_output(
                            package_id=structural_spec.package.id,
                            room_id=room_ids["oriel"],
                            affordance_id=oriel_feature_id,
                        ),
                    ),
                ),
                input_tokens=180,
                output_tokens=320,
            ),
        )
    )
    puzzle_profile = resolve_dungeon_puzzle_prompt_profile(
        provider_id="faux",
        model_id="faux_deterministic_v1",
        capabilities=("text", "tool_calls", "thinking"),
        context_window_tokens=16_384,
        output_token_limit=4_096,
        requested_effort=ReasoningEffort.STANDARD,
    )
    puzzle_attempt = DungeonPuzzlePromptApplicationService(
        preparation, DungeonPuzzlePromptService(studio, puzzle_gateway)
    ).execute(
        PromptDungeonPuzzleWorkflow(
            campaign_id=campaign_id,
            artifact_id=structural.artifact_id,
            parent_version_id=structural.artifact_version_id,
            selection=DungeonPuzzleContextSelection(
                room_id=room_ids["oriel"],
                clue_locations=(
                    DungeonPuzzleClueApproval(
                        location_id=oriel_feature_id,
                        purpose="The prism stand is the approved local light source.",
                    ),
                ),
            ),
            created_by="synthetic-dm",
        ),
        puzzle_profile,
        surface="integration-setup",
    )
    assert puzzle_attempt.result is not None
    assert puzzle_attempt.result.artifact_version_id is not None
    puzzle_record = preparation.get_version(
        campaign_id, puzzle_attempt.result.artifact_version_id
    )
    puzzle_spec = DungeonStudioSpecification.model_validate_json(
        json.dumps(puzzle_record.specification)
    )
    return PreparedSkyroot(
        campaign_id=campaign_id,
        studio=studio,
        preparation=preparation,
        artifact_id=structural.artifact_id,
        structural_version_id=structural.artifact_version_id,
        puzzle_version_id=puzzle_attempt.result.artifact_version_id,
        puzzle_specification=puzzle_spec,
        room_ids=room_ids,
        feature_ids=feature_ids,
        puzzle_profile=puzzle_profile,
    )


def _selection(prepared: PreparedSkyroot) -> DungeonExplorationContextSelection:
    return DungeonExplorationContextSelection(
        room_id=prepared.room_ids["gallery"],
        affordances=(
            DungeonExplorationAffordanceApproval(
                affordance_id=prepared.feature_ids[prepared.room_ids["gallery"]],
                use="The shutter counterweights create shelter or redirect runoff.",
            ),
        ),
        pacing_role="rising_tension",
        stakes="Careless crossing separates carried supplies but never blocks the route permanently.",
        constraints=(
            "Do not add creatures or combatants",
            "Allow more than one reasonable crossing method",
            "Do not invent numeric difficulty values",
        ),
    )


def test_faux_exploration_task_repairs_and_preserves_puzzle_child(
    db_engine: Engine, tmp_path: Path
) -> None:
    prepared = _prepare_skyroot(db_engine, tmp_path)
    assert prepared.puzzle_specification.creative_continuity is not None
    continuity_hash = (
        prepared.puzzle_specification.creative_continuity.projection_sha256
    )
    selection = _selection(prepared)
    context = prepared.studio.build_exploration_context(
        PromptDungeonExplorationWorkflow(
            campaign_id=prepared.campaign_id,
            artifact_id=prepared.artifact_id,
            parent_version_id=prepared.puzzle_version_id,
            selection=selection,
            created_by="synthetic-dm",
        )
    )
    valid = _exploration_output(
        package_id=prepared.puzzle_specification.package.id,
        room_id=prepared.room_ids["gallery"],
        encounter_slot_id=context.room.encounter_slot_id,
        affordance_id=selection.affordances[0].affordance_id,
    )
    rejected = deepcopy(valid)
    approaches = rejected["approaches"]
    assert isinstance(approaches, list)
    approaches[0]["affordance_ids"] = ["rejected_foreign_affordance"]
    approaches[0]["action"] = "REJECTED_EXPLORATION_BODY"
    gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_exploration",
                        call_id="invalid-exploration",
                        arguments=rejected,
                    ),
                ),
                input_tokens=210,
                output_tokens=310,
            ),
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_exploration",
                        call_id="repaired-exploration",
                        arguments=valid,
                    ),
                ),
                input_tokens=280,
                output_tokens=420,
            ),
        )
    )
    profile = resolve_dungeon_exploration_prompt_profile(
        provider_id="faux",
        model_id="faux_deterministic_v1",
        capabilities=("text", "tool_calls", "thinking"),
        context_window_tokens=16_384,
        output_token_limit=4_096,
        requested_effort=ReasoningEffort.FAST,
    )
    attempt = DungeonExplorationPromptApplicationService(
        prepared.preparation,
        DungeonExplorationPromptService(prepared.studio, gateway),
    ).execute(
        PromptDungeonExplorationWorkflow(
            campaign_id=prepared.campaign_id,
            artifact_id=prepared.artifact_id,
            parent_version_id=prepared.puzzle_version_id,
            selection=selection,
            created_by="synthetic-dm",
        ),
        profile,
        surface="integration",
    )

    assert attempt.public_code == "dungeon_exploration_prompt_completed"
    assert attempt.result is not None and attempt.result.success
    assert attempt.result.artifact_version_id is not None
    child = prepared.preparation.get_version(
        prepared.campaign_id, attempt.result.artifact_version_id
    )
    child_spec = DungeonStudioSpecification.model_validate_json(
        json.dumps(child.specification)
    )
    assert child.parent_version_id == prepared.puzzle_version_id
    assert to_canonical_json(child_spec.package) == to_canonical_json(
        prepared.puzzle_specification.package
    )
    assert (
        child_spec.puzzle_model_lineage
        == prepared.puzzle_specification.puzzle_model_lineage
    )
    assert child_spec.dm_guide is not None
    assert prepared.puzzle_specification.dm_guide is not None
    assert child_spec.dm_guide.puzzles == prepared.puzzle_specification.dm_guide.puzzles
    assert child_spec.exploration_model_lineage[-1].output.recovery.startswith(
        "Opening the west drain"
    )
    assert (
        child_spec.creative_continuity
        == prepared.puzzle_specification.creative_continuity
    )
    assert context.continuity.projection_sha256 == continuity_hash
    assert (
        child_spec.exploration_model_lineage[-1].creative_continuity_sha256
        == continuity_hash
    )
    gallery = next(
        room
        for room in child_spec.dm_guide.rooms
        if room.room_id == prepared.room_ids["gallery"]
    )
    assert gallery.encounter_content is not None
    assert len(gallery.encounter_content.player_choices) == 2
    child_text = json.dumps(child.specification)
    assert "rejected_foreign_affordance" not in child_text
    assert "REJECTED_EXPLORATION_BODY" not in child_text
    assert {issue.kind for issue in child_spec.dm_guide.content_issues} == {
        "room",
        "feature",
        "objective",
    }

    assert gateway.allowed_tools == [
        ("submit_dungeon_exploration",),
        ("submit_dungeon_exploration",),
    ]
    schema_text = json.dumps(gateway.tool_schemas[0][0].parameters)
    assert gateway.tool_schemas[0][0].name == "submit_dungeon_exploration"
    assert "DungeonExplorationEnrichmentOutput" in schema_text
    assert "DungeonPlan" not in schema_text
    assert "DungeonPuzzle" not in schema_text
    prompt_document = json.loads(gateway.messages[0][0].content)
    assert prompt_document["context"]["room"]["room_id"] == prepared.room_ids["gallery"]
    assert (
        prompt_document["context"]["continuity"]["projection_sha256"] == continuity_hash
    )
    assert "plan" not in prompt_document["context"]
    repair_document = json.loads(gateway.messages[1][0].content)
    assert repair_document["previous_arguments"] == rejected
    assert (
        repair_document["diagnostics"][0]["code"]
        == "exploration_enrichment.affordance_invalid"
    )
    assert profile.task_profile_id != prepared.puzzle_profile.task_profile_id
    assert profile.requested_effort is ReasoningEffort.FAST
    assert profile.override_notes == {"output_token_limit": 2048, "repair_limit": 1}

    attempt_run = prepared.preparation.get_generation_run(
        prepared.campaign_id, attempt.attempt_run_id
    )
    report_text = json.dumps(attempt_run.validation_report)
    assert (
        attempt_run.validation_report["code"] == "dungeon_exploration_prompt_completed"
    )
    assert "Opening the west drain" not in report_text
    assert "observable_cues" not in report_text
    artifact_run = prepared.preparation.get_generation_run(
        prepared.campaign_id, attempt.result.generation_run_id
    )
    assert artifact_run.generation_kind == "dungeon_exploration_enrichment"
    assert artifact_run.model_task_profile_id == profile.task_profile_id
    assert artifact_run.input_scope["creative_continuity_sha256"] == continuity_hash
    assert artifact_run.tool_runs[0]["tool_name"] == "submit_dungeon_exploration"

    parent_assets = prepared.preparation.list_assets(
        prepared.campaign_id, prepared.puzzle_version_id
    )
    child_assets = prepared.preparation.list_assets(prepared.campaign_id, child.id)
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


def test_failed_faux_exploration_keeps_puzzle_child_and_body_free_diagnostics(
    db_engine: Engine, tmp_path: Path
) -> None:
    prepared = _prepare_skyroot(db_engine, tmp_path)
    selection = _selection(prepared)
    invalid = _exploration_output(
        package_id=prepared.puzzle_specification.package.id,
        room_id=prepared.room_ids["gallery"],
        encounter_slot_id="foreign_rejected_slot",
        affordance_id=selection.affordances[0].affordance_id,
    )
    invalid["observable_cues"] = [
        "REJECTED_FAILURE_BODY",
        "REJECTED_FAILURE_BODY_TWO",
    ]

    def completion(call_id: str) -> GatewayCompletion:
        return GatewayCompletion(
            tool_calls=(
                ToolCall(
                    tool_name="submit_dungeon_exploration",
                    call_id=call_id,
                    arguments=invalid,
                ),
            ),
            input_tokens=300,
            output_tokens=400,
        )

    gateway = FakeGatewayClient(
        (completion("invalid-initial"), completion("invalid-repair"))
    )
    attempt = DungeonExplorationPromptApplicationService(
        prepared.preparation,
        DungeonExplorationPromptService(prepared.studio, gateway),
    ).execute(
        PromptDungeonExplorationWorkflow(
            campaign_id=prepared.campaign_id,
            artifact_id=prepared.artifact_id,
            parent_version_id=prepared.puzzle_version_id,
            selection=selection,
            created_by="synthetic-dm",
        ),
        resolve_dungeon_exploration_prompt_profile(
            provider_id="faux",
            model_id="faux_deterministic_v1",
            capabilities=("text", "tool_calls"),
            context_window_tokens=16_384,
            output_token_limit=4_096,
        ),
        surface="integration",
    )

    assert attempt.result is None
    assert attempt.public_code == "dungeon_exploration_prompt_rejected_after_repair"
    artifact = prepared.preparation.get_artifact(
        prepared.campaign_id, prepared.artifact_id
    )
    assert artifact.current_version_id == prepared.puzzle_version_id
    assert (
        len(
            prepared.preparation.list_versions(
                prepared.campaign_id, prepared.artifact_id
            )
        )
        == 2
    )
    run = prepared.preparation.get_generation_run(
        prepared.campaign_id, attempt.attempt_run_id
    )
    assert run.status.value == "failed"
    assert run.validation_report["repair_attempted"] is True
    report_text = json.dumps(run.validation_report)
    assert "exploration_enrichment.encounter_slot_mismatch" in report_text
    assert "foreign_rejected_slot" not in report_text
    assert "REJECTED_FAILURE_BODY" not in report_text
    assert len(gateway.messages) == 2
    assert gateway.profiles[1].token_budget == gateway.profiles[0].token_budget - 700
    estimated_input = gateway.profiles[1].override_notes["estimated_input_tokens"]
    assert isinstance(estimated_input, int) and estimated_input > 0
    assert gateway.profiles[1].override_notes["output_token_limit"] <= (
        gateway.profiles[1].token_budget - estimated_input
    )
    repair_document = json.loads(gateway.messages[1][0].content)
    assert repair_document["previous_arguments"] == invalid


@dataclass(frozen=True)
class PreparedExploredSkyroot:
    base: PreparedSkyroot
    version_id: uuid.UUID
    specification: DungeonStudioSpecification
    profile: ResolvedModelRunProfile


def _prepare_explored_skyroot(
    engine: Engine, tmp_path: Path
) -> PreparedExploredSkyroot:
    prepared = _prepare_skyroot(engine, tmp_path)
    selection = _selection(prepared)
    context = prepared.studio.build_exploration_context(
        PromptDungeonExplorationWorkflow(
            campaign_id=prepared.campaign_id,
            artifact_id=prepared.artifact_id,
            parent_version_id=prepared.puzzle_version_id,
            selection=selection,
            created_by="synthetic-dm",
        )
    )
    gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_exploration",
                        call_id="skyroot-exploration",
                        arguments=_exploration_output(
                            package_id=prepared.puzzle_specification.package.id,
                            room_id=prepared.room_ids["gallery"],
                            encounter_slot_id=context.room.encounter_slot_id,
                            affordance_id=selection.affordances[0].affordance_id,
                        ),
                    ),
                ),
                input_tokens=190,
                output_tokens=330,
            ),
        )
    )
    profile = resolve_dungeon_exploration_prompt_profile(
        provider_id="faux",
        model_id="faux_deterministic_v1",
        capabilities=("text", "tool_calls", "thinking"),
        context_window_tokens=16_384,
        output_token_limit=4_096,
        requested_effort=ReasoningEffort.FAST,
    )
    attempt = DungeonExplorationPromptApplicationService(
        prepared.preparation,
        DungeonExplorationPromptService(prepared.studio, gateway),
    ).execute(
        PromptDungeonExplorationWorkflow(
            campaign_id=prepared.campaign_id,
            artifact_id=prepared.artifact_id,
            parent_version_id=prepared.puzzle_version_id,
            selection=selection,
            created_by="synthetic-dm",
        ),
        profile,
        surface="integration-setup",
    )
    assert attempt.result is not None
    assert attempt.result.artifact_version_id is not None
    version = prepared.preparation.get_version(
        prepared.campaign_id, attempt.result.artifact_version_id
    )
    return PreparedExploredSkyroot(
        base=prepared,
        version_id=attempt.result.artifact_version_id,
        specification=DungeonStudioSpecification.model_validate_json(
            json.dumps(version.specification)
        ),
        profile=profile,
    )


def _feature_selection(
    prepared: PreparedExploredSkyroot,
) -> DungeonFeatureInteractionContextSelection:
    room_id = prepared.base.room_ids["nursery"]
    return DungeonFeatureInteractionContextSelection(
        room_id=room_id,
        feature_id=prepared.base.feature_ids[room_id],
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


def test_faux_feature_task_repairs_and_preserves_exploration_child(
    db_engine: Engine, tmp_path: Path
) -> None:
    prepared = _prepare_explored_skyroot(db_engine, tmp_path)
    assert prepared.specification.creative_continuity is not None
    continuity_hash = prepared.specification.creative_continuity.projection_sha256
    selection = _feature_selection(prepared)
    valid = _feature_output(
        package_id=prepared.specification.package.id,
        room_id=selection.room_id,
        feature_id=selection.feature_id,
    )
    rejected = deepcopy(valid)
    rejected["feature_id"] = "rejected_foreign_feature"
    affordances = rejected["affordances"]
    assert isinstance(affordances, list)
    affordances[0]["action"] = "REJECTED_FEATURE_BODY"
    gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_feature_interaction",
                        call_id="invalid-feature",
                        arguments=rejected,
                    ),
                ),
                input_tokens=220,
                output_tokens=320,
            ),
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_feature_interaction",
                        call_id="repaired-feature",
                        arguments=valid,
                    ),
                ),
                input_tokens=290,
                output_tokens=430,
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
        surface="integration",
    )

    assert attempt.public_code == "dungeon_feature_interaction_prompt_completed"
    assert attempt.result is not None and attempt.result.success
    assert attempt.result.artifact_version_id is not None
    child = prepared.base.preparation.get_version(
        prepared.base.campaign_id, attempt.result.artifact_version_id
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
    assert child_spec.dm_guide is not None
    assert prepared.specification.dm_guide is not None
    assert child_spec.dm_guide.puzzles == prepared.specification.dm_guide.puzzles
    assert child_spec.dm_guide.rooms == prepared.specification.dm_guide.rooms
    assert child_spec.feature_interaction_model_lineage[-1].output.reset_or_retry
    assert (
        child_spec.feature_interaction_model_lineage[-1].creative_continuity_sha256
        == continuity_hash
    )
    target = next(
        item
        for item in child_spec.dm_guide.features
        if item.marker_id == selection.feature_id
    )
    assert target.content is not None
    assert len(target.content.player_choices) == 2
    child_text = json.dumps(child.specification)
    assert "rejected_foreign_feature" not in child_text
    assert "REJECTED_FEATURE_BODY" not in child_text
    parent_target = next(
        item
        for item in prepared.specification.dm_guide.features
        if item.marker_id == selection.feature_id
    )
    assert parent_target.content is None
    removed_issue = next(
        issue
        for issue in prepared.specification.dm_guide.content_issues
        if issue.kind == "feature" and issue.room_ref == "nursery"
    )
    assert child_spec.dm_guide.content_issues == tuple(
        issue
        for issue in prepared.specification.dm_guide.content_issues
        if issue != removed_issue
    )
    assert all(
        item
        == next(
            prior
            for prior in prepared.specification.dm_guide.features
            if prior.marker_id == item.marker_id
        )
        for item in child_spec.dm_guide.features
        if item.marker_id != selection.feature_id
    )

    assert gateway.allowed_tools == [
        ("submit_dungeon_feature_interaction",),
        ("submit_dungeon_feature_interaction",),
    ]
    schema_text = json.dumps(gateway.tool_schemas[0][0].parameters)
    assert gateway.tool_schemas[0][0].name == "submit_dungeon_feature_interaction"
    assert "DungeonFeatureInteractionEnrichmentOutput" in schema_text
    assert "DungeonPlan" not in schema_text
    assert "DungeonPuzzle" not in schema_text
    prompt_document = json.loads(gateway.messages[0][0].content)
    assert prompt_document["context"]["feature"]["feature_id"] == selection.feature_id
    assert (
        prompt_document["context"]["continuity"]["projection_sha256"] == continuity_hash
    )
    assert "plan" not in prompt_document["context"]
    repair_document = json.loads(gateway.messages[1][0].content)
    assert repair_document["previous_arguments"] == rejected
    assert (
        repair_document["diagnostics"][0]["code"]
        == "feature_interaction.feature_mismatch"
    )
    assert profile.task_profile_id not in {
        prepared.base.puzzle_profile.task_profile_id,
        prepared.profile.task_profile_id,
    }
    assert profile.requested_effort is ReasoningEffort.FAST
    assert profile.override_notes == {"output_token_limit": 2048, "repair_limit": 1}

    attempt_run = prepared.base.preparation.get_generation_run(
        prepared.base.campaign_id, attempt.attempt_run_id
    )
    report_text = json.dumps(attempt_run.validation_report)
    assert (
        attempt_run.validation_report["code"]
        == "dungeon_feature_interaction_prompt_completed"
    )
    assert "Opening the drain lever" not in report_text
    assert "observable_setup" not in report_text
    artifact_run = prepared.base.preparation.get_generation_run(
        prepared.base.campaign_id, attempt.result.generation_run_id
    )
    assert artifact_run.generation_kind == "dungeon_feature_interaction_enrichment"
    assert artifact_run.model_task_profile_id == profile.task_profile_id
    assert artifact_run.input_scope["creative_continuity_sha256"] == continuity_hash
    assert artifact_run.schema_versions["dungeon_creative_continuity"] == "1.0.0"
    assert (
        artifact_run.validation_report["feature_interaction_enrichment"][
            "creative_continuity_sha256"
        ]
        == continuity_hash
    )
    assert (
        artifact_run.tool_runs[0]["tool_name"] == "submit_dungeon_feature_interaction"
    )

    parent_assets = prepared.base.preparation.list_assets(
        prepared.base.campaign_id, prepared.version_id
    )
    child_assets = prepared.base.preparation.list_assets(
        prepared.base.campaign_id, child.id
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


def test_failed_faux_feature_keeps_exploration_child_and_body_free_diagnostics(
    db_engine: Engine, tmp_path: Path
) -> None:
    prepared = _prepare_explored_skyroot(db_engine, tmp_path)
    selection = _feature_selection(prepared)
    invalid = _feature_output(
        package_id=prepared.specification.package.id,
        room_id=selection.room_id,
        feature_id="foreign_rejected_feature",
    )
    invalid["observable_setup"] = [
        "REJECTED_FEATURE_FAILURE_BODY",
        "REJECTED_FEATURE_FAILURE_BODY_TWO",
    ]

    def completion(call_id: str) -> GatewayCompletion:
        return GatewayCompletion(
            tool_calls=(
                ToolCall(
                    tool_name="submit_dungeon_feature_interaction",
                    call_id=call_id,
                    arguments=invalid,
                ),
            ),
            input_tokens=300,
            output_tokens=400,
        )

    gateway = FakeGatewayClient(
        (completion("invalid-initial"), completion("invalid-repair"))
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
        resolve_dungeon_feature_interaction_prompt_profile(
            provider_id="faux",
            model_id="faux_deterministic_v1",
            capabilities=("text", "tool_calls"),
            context_window_tokens=16_384,
            output_token_limit=4_096,
        ),
        surface="integration",
    )

    assert attempt.result is None
    assert (
        attempt.public_code
        == "dungeon_feature_interaction_prompt_rejected_after_repair"
    )
    artifact = prepared.base.preparation.get_artifact(
        prepared.base.campaign_id, prepared.base.artifact_id
    )
    assert artifact.current_version_id == prepared.version_id
    assert (
        len(
            prepared.base.preparation.list_versions(
                prepared.base.campaign_id, prepared.base.artifact_id
            )
        )
        == 3
    )
    run = prepared.base.preparation.get_generation_run(
        prepared.base.campaign_id, attempt.attempt_run_id
    )
    assert run.status.value == "failed"
    assert run.validation_report["repair_attempted"] is True
    report_text = json.dumps(run.validation_report)
    assert "feature_interaction.feature_mismatch" in report_text
    assert "foreign_rejected_feature" not in report_text
    assert "REJECTED_FEATURE_FAILURE_BODY" not in report_text
    assert len(gateway.messages) == 2
    assert gateway.profiles[1].token_budget == gateway.profiles[0].token_budget - 700
    estimated_input = gateway.profiles[1].override_notes["estimated_input_tokens"]
    assert isinstance(estimated_input, int) and estimated_input > 0
    assert gateway.profiles[1].override_notes["output_token_limit"] <= (
        gateway.profiles[1].token_budget - estimated_input
    )
    repair_document = json.loads(gateway.messages[1][0].content)
    assert repair_document["previous_arguments"] == invalid
