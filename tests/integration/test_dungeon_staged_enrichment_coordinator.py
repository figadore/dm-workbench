"""One-step faux-provider staged dungeon enrichment coordination."""

import json
import uuid
from pathlib import Path
from typing import cast

import pytest
from pydantic import JsonValue
from sqlalchemy import Engine

from dm_assistant.adapters.assets import LocalAssetStore
from dm_assistant.db import Campaign, build_session_factory, transactional_session
from dm_assistant.errors import ConflictError
from dm_assistant.modules.modeling import (
    PromptMessage,
    ResolvedModelRunProfile,
    ToolCall,
)
from dm_assistant.modules.preparation import PreparationService
from dm_assistant.modules.scope import TaskType, resolve_task_scope
from dm_assistant.orchestration.dungeons import (
    DungeonExplorationAffordanceApproval,
    DungeonExplorationContextSelection,
    DungeonExplorationPromptApplicationService,
    DungeonExplorationPromptService,
    DungeonPromptService,
    DungeonPuzzleClueApproval,
    DungeonPuzzleContextSelection,
    DungeonPuzzlePromptApplicationService,
    DungeonPuzzlePromptService,
    DungeonStagedEnrichmentCoordinator,
    DungeonStagedExplorationPolicy,
    DungeonStagedPuzzlePolicy,
    DungeonStudioService,
    DungeonStudioSpecification,
    DungeonWorkflowResult,
    PromptDungeonStagedEnrichmentWorkflow,
    PromptDungeonWorkflow,
    resolve_dungeon_exploration_prompt_profile,
    resolve_dungeon_prompt_profile,
    resolve_dungeon_puzzle_prompt_profile,
)
from dm_assistant.orchestration.modeling import GatewayCompletion, GatewayToolSchema

pytestmark = pytest.mark.integration


class FakeGatewayClient:
    def __init__(self, completions: tuple[GatewayCompletion, ...]) -> None:
        self._completions = list(completions)
        self.messages: list[tuple[PromptMessage, ...]] = []
        self.profiles: list[ResolvedModelRunProfile] = []
        self.allowed_tools: list[tuple[str, ...]] = []
        self.tool_schemas: list[tuple[GatewayToolSchema, ...]] = []

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
            raise AssertionError("unexpected staged provider call")
        return self._completions.pop(0)


def _proposal() -> dict[str, object]:
    return {
        "proposal_version": "1",
        "plan": {
            "schema_version": "1.0.0",
            "title": "Cobalt Orrery",
            "premise": "Recover a synthetic star seed from a wind-worn observatory.",
            "themes": ["cobalt glass", "clockwork stars"],
            "rooms": [
                {
                    "ref": "threshold",
                    "name": "Weather Door",
                    "role": "entrance",
                    "purpose": "Establish the abandoned observatory threshold.",
                },
                {
                    "ref": "gallery",
                    "name": "Hanging Gallery",
                    "role": "exploration",
                    "purpose": "Cross beneath moving model planets.",
                    "encounter": "exploration",
                },
                {
                    "ref": "orrery",
                    "name": "Cobalt Orrery",
                    "role": "puzzle",
                    "purpose": "Align the model sky to open the seed cradle.",
                },
                {
                    "ref": "cradle",
                    "name": "Star Cradle",
                    "role": "objective",
                    "purpose": "Hold the named synthetic star seed.",
                },
            ],
            "critical_path": ["threshold", "gallery", "orrery", "cradle"],
            "room_contents": [
                {
                    "room_ref": "gallery",
                    "feature": {
                        "kind": "other",
                        "name": "Orbit Counterweight",
                        "description": "A cobalt weight redirects the hanging planets.",
                    },
                },
                {"room_ref": "cradle", "objective": "Synthetic Star Seed"},
            ],
        },
    }


def _puzzle_output(
    *, package_id: str, room_id: str, clue_location_id: str
) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "package_id": package_id,
        "room_id": room_id,
        "name": "The Returning Constellation",
        "observable_elements": [
            "Three cobalt planets circle a brass star.",
            "Etched tracks brighten where their shadows overlap.",
        ],
        "solution_steps": [
            "Turn each planet until all three shadows meet the etched star."
        ],
        "clue_path": [
            {
                "location_id": clue_location_id,
                "observation": "One overlap point is polished brighter than the track.",
                "inference": "The model opens when every shadow shares that point.",
            }
        ],
        "alternate_handling": [
            {
                "approach": "Mark each orbit and coordinate several operators.",
                "adjudication": "Careful coordination reveals the same alignment.",
            }
        ],
        "success_outcome": "The aligned model releases the seed cradle.",
        "failure_consequence": "The planets drift back to their starting positions.",
        "reset_or_retry": "The model can be turned again immediately.",
    }


def _exploration_output(
    *,
    package_id: str,
    room_id: str,
    encounter_slot_id: str,
    affordance_id: str,
) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "package_id": package_id,
        "room_id": room_id,
        "encounter_slot_id": encounter_slot_id,
        "observable_cues": [
            "Cobalt planets sweep across the gallery above a narrow brass walk.",
            "A counterweight pauses one orbit while accelerating another.",
        ],
        "approaches": [
            {
                "affordance_ids": [affordance_id],
                "action": "Work the counterweight to open a moving gap in the orbits.",
                "adjudication": "Coordinated pulls keep the gap beside the crossing group.",
                "consequence": "The group crosses together but leaves the weight reset.",
            },
            {
                "affordance_ids": [affordance_id],
                "action": "Brace one planet and pass beneath the stalled model.",
                "adjudication": "A firm brace permits a slower single-file crossing.",
                "consequence": "The last traveler must release the brace from the far side.",
            },
        ],
        "escalation": "After a prolonged delay, the fastest planet reaches the brass walk.",
        "recovery": "Releasing the counterweight returns every orbit to its marked start.",
    }


def _campaign(engine: Engine) -> uuid.UUID:
    campaign_id = uuid.uuid4()
    with transactional_session(build_session_factory(engine)) as session:
        session.add(Campaign(id=campaign_id, name="Synthetic Cobalt Campaign"))
    return campaign_id


def _studio(
    engine: Engine, tmp_path: Path
) -> tuple[DungeonStudioService, PreparationService]:
    preparation = PreparationService(
        engine,
        LocalAssetStore(tmp_path / "staged-assets", tmp_path / "staged-scratch"),
    )
    return DungeonStudioService(preparation), preparation


def _structural_parent(
    *,
    campaign_id: uuid.UUID,
    studio: DungeonStudioService,
) -> tuple[DungeonWorkflowResult, FakeGatewayClient]:
    gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_plan",
                        call_id="structural-plan",
                        arguments=cast(dict[str, JsonValue], _proposal()),
                    ),
                ),
                input_tokens=100,
                output_tokens=200,
            ),
        )
    )
    result = DungeonPromptService(studio, gateway).create(
        PromptDungeonWorkflow(
            campaign_id=campaign_id,
            prompt="Build the synthetic Cobalt Orrery and recover its star seed.",
            seed=714000101,
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
    assert result.artifact_id is not None
    assert result.artifact_version_id is not None
    return result, gateway


def _coordinator_command(
    *,
    campaign_id: uuid.UUID,
    artifact_id: uuid.UUID,
    parent_version_id: uuid.UUID,
    specification: DungeonStudioSpecification,
) -> PromptDungeonStagedEnrichmentWorkflow:
    puzzle_room_id = next(
        room.id for room in specification.package.rooms if room.role.value == "puzzle"
    )
    return PromptDungeonStagedEnrichmentWorkflow(
        campaign_id=campaign_id,
        artifact_id=artifact_id,
        parent_version_id=parent_version_id,
        policy=DungeonStagedPuzzlePolicy(
            selection=DungeonPuzzleContextSelection(
                room_id=puzzle_room_id,
                clue_locations=(
                    DungeonPuzzleClueApproval(
                        location_id=puzzle_room_id,
                        purpose="The local orbit tracks reveal the alignment point.",
                    ),
                ),
                tone=("wind-worn", "astronomical"),
                constraints=("Do not author numeric difficulties.",),
            )
        ),
        created_by="synthetic-dm",
    )


def _profile() -> ResolvedModelRunProfile:
    return resolve_dungeon_puzzle_prompt_profile(
        provider_id="faux",
        model_id="faux_deterministic_v1",
        capabilities=("text", "tool_calls"),
        context_window_tokens=16_384,
        output_token_limit=4_096,
    )


def _exploration_profile() -> ResolvedModelRunProfile:
    return resolve_dungeon_exploration_prompt_profile(
        provider_id="faux",
        model_id="faux_deterministic_v1",
        capabilities=("text", "tool_calls"),
        context_window_tokens=16_384,
        output_token_limit=4_096,
    )


def _accepted_puzzle_child(
    *,
    campaign_id: uuid.UUID,
    studio: DungeonStudioService,
    preparation: PreparationService,
) -> tuple[uuid.UUID, uuid.UUID, DungeonStudioSpecification]:
    structural, _ = _structural_parent(campaign_id=campaign_id, studio=studio)
    parent_id = structural.artifact_version_id
    artifact_id = structural.artifact_id
    assert isinstance(parent_id, uuid.UUID)
    assert isinstance(artifact_id, uuid.UUID)
    parent = preparation.get_version(campaign_id, parent_id)
    specification = DungeonStudioSpecification.model_validate_json(
        json.dumps(parent.specification)
    )
    puzzle_room_id = next(
        room.id for room in specification.package.rooms if room.role.value == "puzzle"
    )
    gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_puzzle",
                        call_id="setup-puzzle",
                        arguments=cast(
                            dict[str, JsonValue],
                            _puzzle_output(
                                package_id=specification.package.id,
                                room_id=puzzle_room_id,
                                clue_location_id=puzzle_room_id,
                            ),
                        ),
                    ),
                ),
                input_tokens=200,
                output_tokens=350,
            ),
        )
    )
    step = DungeonStagedEnrichmentCoordinator(
        preparation,
        puzzle=DungeonPuzzlePromptApplicationService(
            preparation, DungeonPuzzlePromptService(studio, gateway)
        ),
    ).execute(
        _coordinator_command(
            campaign_id=campaign_id,
            artifact_id=artifact_id,
            parent_version_id=parent_id,
            specification=specification,
        ),
        _profile(),
        surface="integration-setup",
    )
    assert step.attempt is not None and step.attempt.result is not None
    child_id = step.attempt.result.artifact_version_id
    assert child_id is not None
    child = preparation.get_version(campaign_id, child_id)
    return (
        artifact_id,
        child_id,
        DungeonStudioSpecification.model_validate_json(json.dumps(child.specification)),
    )


def _exploration_policy(
    specification: DungeonStudioSpecification,
    *,
    encounter_slot_id: str | None = None,
) -> DungeonStagedExplorationPolicy:
    exploration_room_id = next(
        room.id
        for room in specification.package.rooms
        if room.role.value == "exploration"
    )
    slot = next(
        item
        for item in specification.package.encounter_slots
        if item.room_id == exploration_room_id and "exploration" in item.tags
    )
    affordance = next(
        marker
        for marker in specification.package.room_mechanic_markers
        if marker.room_id == exploration_room_id and marker.kind.value == "feature"
    )
    return DungeonStagedExplorationPolicy(
        encounter_slot_id=encounter_slot_id or slot.id,
        selection=DungeonExplorationContextSelection(
            room_id=exploration_room_id,
            affordances=(
                DungeonExplorationAffordanceApproval(
                    affordance_id=affordance.id,
                    use="The counterweight changes the timing of the hanging planets.",
                ),
            ),
            pacing_role="rising_tension",
            stakes="A poor crossing scatters supplies without permanently closing the route.",
            constraints=("Do not author numeric difficulties.",),
        ),
    )


def test_one_step_coordinator_publishes_one_puzzle_child_then_plans_exploration(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    campaign_id = _campaign(db_engine)
    studio, preparation = _studio(db_engine, tmp_path)
    structural, _ = _structural_parent(campaign_id=campaign_id, studio=studio)
    parent_id = structural.artifact_version_id
    artifact_id = structural.artifact_id
    assert isinstance(parent_id, uuid.UUID)
    assert isinstance(artifact_id, uuid.UUID)
    parent = preparation.get_version(campaign_id, parent_id)
    specification = DungeonStudioSpecification.model_validate_json(
        json.dumps(parent.specification)
    )
    puzzle_room_id = next(
        room.id for room in specification.package.rooms if room.role.value == "puzzle"
    )
    gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_puzzle",
                        call_id="accepted-puzzle",
                        arguments=cast(
                            dict[str, JsonValue],
                            _puzzle_output(
                                package_id=specification.package.id,
                                room_id=puzzle_room_id,
                                clue_location_id=puzzle_room_id,
                            ),
                        ),
                    ),
                ),
                input_tokens=200,
                output_tokens=350,
            ),
        )
    )
    coordinator = DungeonStagedEnrichmentCoordinator(
        preparation,
        puzzle=DungeonPuzzlePromptApplicationService(
            preparation, DungeonPuzzlePromptService(studio, gateway)
        ),
    )

    step = coordinator.execute(
        _coordinator_command(
            campaign_id=campaign_id,
            artifact_id=artifact_id,
            parent_version_id=parent_id,
            specification=specification,
        ),
        _profile(),
        surface="integration",
    )

    assert step.plan_before.next_task is not None
    assert step.plan_before.next_task.kind == "puzzle"
    assert step.attempt is not None and step.attempt.result is not None
    child_id = step.attempt.result.artifact_version_id
    assert child_id is not None
    assert step.plan_after.next_task is not None
    assert step.plan_after.next_task.kind == "exploration"
    assert (
        preparation.get_artifact(campaign_id, artifact_id).current_version_id
        == child_id
    )
    assert len(preparation.list_versions(campaign_id, artifact_id)) == 2
    child = preparation.get_version(campaign_id, child_id)
    assert child.parent_version_id == parent_id
    child_specification = DungeonStudioSpecification.model_validate_json(
        json.dumps(child.specification)
    )
    assert child_specification.puzzle_model_lineage[-1].output.room_id == puzzle_room_id
    assert len(gateway.messages) == 1
    assert gateway.allowed_tools == [("submit_dungeon_puzzle",)]


def test_one_step_coordinator_rejection_keeps_parent_and_does_not_plan_or_dispatch_next(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    campaign_id = _campaign(db_engine)
    studio, preparation = _studio(db_engine, tmp_path)
    structural, _ = _structural_parent(campaign_id=campaign_id, studio=studio)
    parent_id = structural.artifact_version_id
    artifact_id = structural.artifact_id
    assert isinstance(parent_id, uuid.UUID)
    assert isinstance(artifact_id, uuid.UUID)
    parent = preparation.get_version(campaign_id, parent_id)
    specification = DungeonStudioSpecification.model_validate_json(
        json.dumps(parent.specification)
    )
    puzzle_room_id = next(
        room.id for room in specification.package.rooms if room.role.value == "puzzle"
    )
    rejected = _puzzle_output(
        package_id=specification.package.id,
        room_id=puzzle_room_id,
        clue_location_id="foreign_clue_location",
    )
    gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_puzzle",
                        call_id="rejected-initial",
                        arguments=cast(dict[str, JsonValue], rejected),
                    ),
                ),
                input_tokens=200,
                output_tokens=300,
            ),
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_puzzle",
                        call_id="rejected-repair",
                        arguments=cast(dict[str, JsonValue], rejected),
                    ),
                ),
                input_tokens=200,
                output_tokens=300,
            ),
        )
    )
    coordinator = DungeonStagedEnrichmentCoordinator(
        preparation,
        puzzle=DungeonPuzzlePromptApplicationService(
            preparation, DungeonPuzzlePromptService(studio, gateway)
        ),
    )

    step = coordinator.execute(
        _coordinator_command(
            campaign_id=campaign_id,
            artifact_id=artifact_id,
            parent_version_id=parent_id,
            specification=specification,
        ),
        _profile(),
        surface="integration",
    )

    assert step.public_code == "dungeon_puzzle_prompt_rejected_after_repair"
    assert step.attempt is not None and step.attempt.result is None
    assert step.plan_before == step.plan_after
    assert step.plan_after.next_task is not None
    assert step.plan_after.next_task.kind == "puzzle"
    assert (
        preparation.get_artifact(campaign_id, artifact_id).current_version_id
        == parent_id
    )
    assert len(preparation.list_versions(campaign_id, artifact_id)) == 1
    assert len(gateway.messages) == 2
    report = preparation.get_generation_run(
        campaign_id, step.attempt.attempt_run_id
    ).validation_report
    assert "foreign_clue_location" not in json.dumps(report)


def test_resumed_exploration_publishes_one_child_then_plans_feature(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    campaign_id = _campaign(db_engine)
    studio, preparation = _studio(db_engine, tmp_path)
    artifact_id, puzzle_child_id, specification = _accepted_puzzle_child(
        campaign_id=campaign_id,
        studio=studio,
        preparation=preparation,
    )
    policy = _exploration_policy(specification)
    exploration_room_id = policy.selection.room_id
    affordance_id = policy.selection.affordances[0].affordance_id
    gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_exploration",
                        call_id="accepted-exploration",
                        arguments=cast(
                            dict[str, JsonValue],
                            _exploration_output(
                                package_id=specification.package.id,
                                room_id=exploration_room_id,
                                encounter_slot_id=policy.encounter_slot_id,
                                affordance_id=affordance_id,
                            ),
                        ),
                    ),
                ),
                input_tokens=210,
                output_tokens=360,
            ),
        )
    )
    coordinator = DungeonStagedEnrichmentCoordinator(
        preparation,
        exploration=DungeonExplorationPromptApplicationService(
            preparation, DungeonExplorationPromptService(studio, gateway)
        ),
    )

    step = coordinator.execute(
        PromptDungeonStagedEnrichmentWorkflow(
            campaign_id=campaign_id,
            artifact_id=artifact_id,
            parent_version_id=puzzle_child_id,
            policy=policy,
            created_by="synthetic-dm",
        ),
        _exploration_profile(),
        surface="integration",
    )

    assert step.plan_before.next_task is not None
    assert step.plan_before.next_task.kind == "exploration"
    assert step.plan_before.next_task.target_ids == (policy.encounter_slot_id,)
    assert step.attempt is not None and step.attempt.result is not None
    exploration_child_id = step.attempt.result.artifact_version_id
    assert exploration_child_id is not None
    assert step.plan_after.next_task is not None
    assert step.plan_after.next_task.kind == "feature_interaction"
    assert step.plan_after.next_task.room_ids == (exploration_room_id,)
    assert step.plan_after.next_task.target_ids == (affordance_id,)
    assert (
        preparation.get_artifact(campaign_id, artifact_id).current_version_id
        == exploration_child_id
    )
    assert len(preparation.list_versions(campaign_id, artifact_id)) == 3
    child = preparation.get_version(campaign_id, exploration_child_id)
    assert child.parent_version_id == puzzle_child_id
    child_specification = DungeonStudioSpecification.model_validate_json(
        json.dumps(child.specification)
    )
    assert (
        child_specification.exploration_model_lineage[-1].output.encounter_slot_id
        == policy.encounter_slot_id
    )
    assert len(gateway.messages) == 1
    assert gateway.allowed_tools == [("submit_dungeon_exploration",)]


def test_resumed_exploration_rejects_mismatched_slot_before_provider_call(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    campaign_id = _campaign(db_engine)
    studio, preparation = _studio(db_engine, tmp_path)
    artifact_id, puzzle_child_id, specification = _accepted_puzzle_child(
        campaign_id=campaign_id,
        studio=studio,
        preparation=preparation,
    )
    gateway = FakeGatewayClient(())
    coordinator = DungeonStagedEnrichmentCoordinator(
        preparation,
        exploration=DungeonExplorationPromptApplicationService(
            preparation, DungeonExplorationPromptService(studio, gateway)
        ),
    )

    with pytest.raises(ConflictError, match="staged exact target"):
        coordinator.execute(
            PromptDungeonStagedEnrichmentWorkflow(
                campaign_id=campaign_id,
                artifact_id=artifact_id,
                parent_version_id=puzzle_child_id,
                policy=_exploration_policy(
                    specification,
                    encounter_slot_id="foreign_exploration_slot",
                ),
                created_by="synthetic-dm",
            ),
            _exploration_profile(),
            surface="integration",
        )

    assert gateway.messages == []
    assert (
        preparation.get_artifact(campaign_id, artifact_id).current_version_id
        == puzzle_child_id
    )
    assert len(preparation.list_versions(campaign_id, artifact_id)) == 2
