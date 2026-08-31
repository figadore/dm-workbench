"""Faux-provider puzzle enrichment over one immutable structural dungeon."""

import json
import uuid
from copy import deepcopy
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
    DungeonPromptService,
    DungeonPuzzleClueApproval,
    DungeonPuzzleContextSelection,
    DungeonPuzzleDependencyApproval,
    DungeonPuzzleObjectiveApproval,
    DungeonPuzzlePromptApplicationService,
    DungeonPuzzlePromptService,
    DungeonStudioService,
    DungeonStudioSpecification,
    PromptDungeonPuzzleWorkflow,
    PromptDungeonWorkflow,
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


def _campaign(engine: Engine) -> uuid.UUID:
    campaign_id = uuid.uuid4()
    with transactional_session(build_session_factory(engine)) as session:
        session.add(Campaign(id=campaign_id, name="Synthetic Windglass Campaign"))
    return campaign_id


def _studio(
    engine: Engine, tmp_path: Path
) -> tuple[DungeonStudioService, PreparationService]:
    preparation = PreparationService(
        engine,
        LocalAssetStore(tmp_path / "puzzle-assets", tmp_path / "puzzle-scratch"),
    )
    return DungeonStudioService(preparation), preparation


def _structural_proposal() -> dict[str, object]:
    return {
        "proposal_version": "1",
        "plan": {
            "schema_version": "1.0.0",
            "title": "Windglass Shrine",
            "premise": "Recover a synthetic seed from an abandoned mountain shrine.",
            "themes": ["wind", "weathered stone"],
            "rooms": [
                {
                    "ref": "approach",
                    "name": "Broken Approach",
                    "role": "entrance",
                    "purpose": "Establish the wind-worn entrance.",
                },
                {
                    "ref": "nave",
                    "name": "Weathered Nave",
                    "role": "exploration",
                    "purpose": "Show a procession relief before the puzzle gate.",
                },
                {
                    "ref": "apse",
                    "name": "Echoing Apse",
                    "role": "puzzle",
                    "purpose": "Reserve a wind-and-chime puzzle controlling the vault.",
                },
                {
                    "ref": "vault",
                    "name": "Seed Vault",
                    "role": "objective",
                    "purpose": "Hold the named Windglass Seed objective.",
                },
            ],
            "critical_path": ["approach", "nave", "apse", "vault"],
            "gates": [
                {
                    "ref": "seed_gate",
                    "between_rooms": ["apse", "vault"],
                    "kind": "puzzle",
                    "dependency_kind": "clue",
                    "dependency_room": "nave",
                    "dependency_name": "Procession Relief",
                }
            ],
            "room_contents": [
                {
                    "room_ref": "apse",
                    "feature": {
                        "kind": "other",
                        "name": "Wind Chimes",
                        "description": "Three stone chimes reserve local puzzle space.",
                    },
                },
                {"room_ref": "vault", "objective": "Windglass Seed"},
            ],
        },
    }


def _puzzle_output(
    *, package_id: str, room_id: str, feature_id: str, dependency_id: str
) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "package_id": package_id,
        "room_id": room_id,
        "name": "The Returning Gale",
        "observable_elements": [
            "Three stone vanes turn toward sounds made in the apse.",
            "Matching chimes sound low, high, then middle when the wind rises.",
        ],
        "solution_steps": [
            "Turn the vanes toward the low, high, and middle chimes in that order."
        ],
        "clue_path": [
            {
                "location_id": feature_id,
                "observation": "The gust sounds the chimes low, high, then middle.",
                "inference": "The lock expects the same ordered pattern.",
            },
            {
                "location_id": dependency_id,
                "observation": "The relief points to low, high, and middle peaks.",
                "inference": "The relief confirms the order without requiring pitch recognition.",
            },
        ],
        "hints": ["A hand on a vane makes it hum at the matching pitch."],
        "alternate_handling": [
            {
                "approach": "Match the relief's peak heights instead of listening.",
                "adjudication": "The visual sequence opens the lock as well.",
            }
        ],
        "success_outcome": "The aligned vanes release the vault latch.",
        "failure_consequence": "A gust returns all vanes to neutral.",
        "reset_or_retry": "The vanes reset immediately.",
    }


def test_faux_puzzle_task_has_independent_budget_and_persists_exact_guide_version(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    campaign_id = _campaign(db_engine)
    studio, preparation = _studio(db_engine, tmp_path)
    structural_gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_plan",
                        call_id="structural-plan",
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
            prompt="Build the synthetic Windglass Shrine and recover the Windglass Seed.",
            seed=714000001,
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
            capabilities=("text", "tool_calls", "json_schema_constrained_sampling"),
            context_window_tokens=16_384,
            output_token_limit=4_096,
        ),
    )
    assert structural.artifact_id is not None
    assert structural.artifact_version_id is not None
    parent = preparation.get_version(campaign_id, structural.artifact_version_id)
    parent_spec = DungeonStudioSpecification.model_validate_json(
        json.dumps(parent.specification)
    )
    plan = parent_spec.model_lineage[-1].proposal
    assert plan is not None and plan.plan is not None
    assert parent_spec.structural_context is not None
    assert parent_spec.creative_continuity is not None
    continuity_hash = parent_spec.creative_continuity.projection_sha256
    assert parent_spec.creative_continuity.campaign_lore_status == "unknown"
    assert parent_spec.creative_continuity.selected_facts == ()
    compiled_room_ids = {
        item.ref: item.room_id for item in parent_spec.layout_request.certificate.rooms
    }
    feature_id = parent_spec.layout_request.mechanics_plan.room_features[0].id
    objective_id = parent_spec.layout_request.mechanics_plan.room_objectives[0].id
    gate = parent_spec.package.topology.gates[0]
    dependency_id = parent_spec.package.topology.clues[0].id
    selection = DungeonPuzzleContextSelection(
        room_id=compiled_room_ids["apse"],
        clue_locations=(
            DungeonPuzzleClueApproval(
                location_id=feature_id,
                purpose="The local chimes demonstrate the lock's notes.",
            ),
            DungeonPuzzleClueApproval(
                location_id=dependency_id,
                purpose="The nearby nave relief establishes their order.",
            ),
        ),
        objective=DungeonPuzzleObjectiveApproval(
            objective_id=objective_id, relationship="guards_access"
        ),
        dependency=DungeonPuzzleDependencyApproval(
            gate_id=gate.id,
            dependency_id=dependency_id,
            relationship="uses_dependency",
        ),
        tone=("windswept", "contemplative"),
        constraints=("No numeric difficulty values",),
    )
    output = _puzzle_output(
        package_id=parent_spec.package.id,
        room_id=compiled_room_ids["apse"],
        feature_id=feature_id,
        dependency_id=dependency_id,
    )
    rejected_initial = deepcopy(output)
    rejected_initial["clue_path"] = [
        {
            "location_id": "rejected_success_path_value",
            "observation": "REJECTED_SUCCESS_PATH_BODY",
            "inference": "REJECTED_SUCCESS_PATH_BODY",
        }
    ]
    puzzle_gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_puzzle",
                        call_id="puzzle-invalid-initial",
                        arguments=rejected_initial,
                    ),
                ),
                input_tokens=200,
                output_tokens=300,
            ),
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_puzzle",
                        call_id="puzzle-design-repair",
                        arguments=output,
                    ),
                ),
                input_tokens=300,
                output_tokens=500,
            ),
        )
    )
    puzzle_profile = resolve_dungeon_puzzle_prompt_profile(
        provider_id="faux",
        model_id="faux_deterministic_v1",
        capabilities=(
            "text",
            "tool_calls",
            "thinking",
            "json_schema_constrained_sampling",
        ),
        context_window_tokens=16_384,
        output_token_limit=4_096,
        requested_effort=ReasoningEffort.FAST,
    )
    application = DungeonPuzzlePromptApplicationService(
        preparation,
        DungeonPuzzlePromptService(studio, puzzle_gateway),
    )

    attempt = application.execute(
        PromptDungeonPuzzleWorkflow(
            campaign_id=campaign_id,
            artifact_id=structural.artifact_id,
            parent_version_id=structural.artifact_version_id,
            selection=selection,
            created_by="synthetic-dm",
        ),
        puzzle_profile,
        surface="integration",
    )

    assert attempt.public_code == "dungeon_puzzle_prompt_completed"
    assert attempt.result is not None and attempt.result.success
    assert attempt.result.artifact_id == structural.artifact_id
    assert attempt.result.artifact_version_id is not None
    child = preparation.get_version(campaign_id, attempt.result.artifact_version_id)
    child_spec = DungeonStudioSpecification.model_validate_json(
        json.dumps(child.specification)
    )
    assert child.parent_version_id == structural.artifact_version_id
    assert to_canonical_json(child_spec.package) == to_canonical_json(
        parent_spec.package
    )
    assert child_spec.dm_guide is not None
    assert child_spec.dm_guide.puzzles[0].name == "The Returning Gale"
    assert child_spec.puzzle_model_lineage[-1].output.name == "The Returning Gale"
    assert child_spec.creative_continuity == parent_spec.creative_continuity
    assert (
        child_spec.puzzle_model_lineage[-1].creative_continuity_sha256
        == continuity_hash
    )
    child_specification_text = json.dumps(child.specification)
    assert "rejected_success_path_value" not in child_specification_text
    assert "REJECTED_SUCCESS_PATH_BODY" not in child_specification_text
    assert child_spec.preparation_readiness is not None
    assert not child_spec.preparation_readiness.ready
    assert {issue.kind for issue in child_spec.dm_guide.content_issues} == {
        "room",
        "gate_dependency",
        "feature",
        "objective",
    }

    assert puzzle_gateway.allowed_tools == [
        ("submit_dungeon_puzzle",),
        ("submit_dungeon_puzzle",),
    ]
    assert puzzle_gateway.tool_schemas[0][0].name == "submit_dungeon_puzzle"
    puzzle_schema = json.dumps(puzzle_gateway.tool_schemas[0][0].parameters)
    assert "DungeonPuzzleEnrichmentOutput" in puzzle_schema
    assert "DungeonPlan" not in puzzle_schema
    assert "critical_path" not in puzzle_schema
    assert "exploration" not in puzzle_schema
    prompt_document = json.loads(puzzle_gateway.messages[0][0].content)
    assert prompt_document["context"]["package_id"] == parent_spec.package.id
    assert (
        prompt_document["context"]["continuity"]["projection_sha256"] == continuity_hash
    )
    assert "plan" not in prompt_document["context"]
    repair_document = json.loads(puzzle_gateway.messages[1][0].content)
    assert repair_document["previous_arguments"] == rejected_initial
    assert (
        repair_document["diagnostics"][0]["code"]
        == "puzzle_enrichment.clue_location_invalid"
    )
    assert (
        puzzle_profile.task_profile_id != structural_gateway.profiles[0].task_profile_id
    )
    assert puzzle_profile.requested_effort is ReasoningEffort.FAST
    assert structural_gateway.profiles[0].requested_effort is ReasoningEffort.STANDARD
    assert puzzle_profile.token_budget < structural_gateway.profiles[0].token_budget
    assert puzzle_profile.override_notes == {
        "output_token_limit": 2048,
        "repair_limit": 1,
    }

    attempt_run = preparation.get_generation_run(campaign_id, attempt.attempt_run_id)
    assert attempt_run.validation_report["code"] == "dungeon_puzzle_prompt_completed"
    report_text = json.dumps(attempt_run.validation_report)
    assert "The Returning Gale" not in report_text
    assert "observable_elements" not in report_text
    artifact_run = preparation.get_generation_run(
        campaign_id, attempt.result.generation_run_id
    )
    assert artifact_run.generation_kind == "dungeon_puzzle_enrichment"
    assert artifact_run.model_task_profile_id == puzzle_profile.task_profile_id
    assert artifact_run.input_scope["creative_continuity_sha256"] == continuity_hash
    assert artifact_run.tool_runs[0]["tool_name"] == "submit_dungeon_puzzle"

    parent_assets = preparation.list_assets(campaign_id, parent.id)
    child_assets = preparation.list_assets(campaign_id, child.id)
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


def test_failed_faux_puzzle_task_keeps_parent_and_persists_only_safe_diagnostics(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    campaign_id = _campaign(db_engine)
    studio, preparation = _studio(db_engine, tmp_path)
    structural_gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_plan",
                        call_id="structural-plan",
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
            prompt="Build the synthetic Windglass Shrine.",
            seed=714000001,
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
    parent = preparation.get_version(campaign_id, structural.artifact_version_id)
    parent_spec = DungeonStudioSpecification.model_validate_json(
        json.dumps(parent.specification)
    )
    room_ids = {
        item.ref: item.room_id for item in parent_spec.layout_request.certificate.rooms
    }
    feature_id = parent_spec.layout_request.mechanics_plan.room_features[0].id
    objective_id = parent_spec.layout_request.mechanics_plan.room_objectives[0].id
    gate = parent_spec.package.topology.gates[0]
    dependency_id = parent_spec.package.topology.clues[0].id
    selection = DungeonPuzzleContextSelection(
        room_id=room_ids["apse"],
        clue_locations=(
            DungeonPuzzleClueApproval(
                location_id=feature_id, purpose="Approved local clue."
            ),
            DungeonPuzzleClueApproval(
                location_id=dependency_id, purpose="Approved nearby clue."
            ),
        ),
        objective=DungeonPuzzleObjectiveApproval(
            objective_id=objective_id, relationship="guards_access"
        ),
        dependency=DungeonPuzzleDependencyApproval(
            gate_id=gate.id,
            dependency_id=dependency_id,
            relationship="uses_dependency",
        ),
    )
    invalid = _puzzle_output(
        package_id=parent_spec.package.id,
        room_id=room_ids["apse"],
        feature_id=feature_id,
        dependency_id=dependency_id,
    )
    invalid["clue_path"] = [
        {
            "location_id": "forbidden_rejected_value",
            "observation": "SHOULD_NOT_PERSIST",
            "inference": "SHOULD_NOT_PERSIST",
        }
    ]
    gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_puzzle",
                        call_id="invalid-initial",
                        arguments=invalid,
                    ),
                ),
                input_tokens=300,
                output_tokens=400,
            ),
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_puzzle",
                        call_id="invalid-repair",
                        arguments=invalid,
                    ),
                ),
                input_tokens=300,
                output_tokens=400,
            ),
        )
    )
    application = DungeonPuzzlePromptApplicationService(
        preparation, DungeonPuzzlePromptService(studio, gateway)
    )

    attempt = application.execute(
        PromptDungeonPuzzleWorkflow(
            campaign_id=campaign_id,
            artifact_id=structural.artifact_id,
            parent_version_id=structural.artifact_version_id,
            selection=selection,
            created_by="synthetic-dm",
        ),
        resolve_dungeon_puzzle_prompt_profile(
            provider_id="faux",
            model_id="faux_deterministic_v1",
            capabilities=("text", "tool_calls"),
            context_window_tokens=16_384,
            output_token_limit=4_096,
        ),
        surface="integration",
    )

    assert attempt.result is None
    assert attempt.public_code == "dungeon_puzzle_prompt_rejected_after_repair"
    artifact = preparation.get_artifact(campaign_id, structural.artifact_id)
    assert artifact.current_version_id == structural.artifact_version_id
    assert len(preparation.list_versions(campaign_id, structural.artifact_id)) == 1
    attempt_run = preparation.get_generation_run(campaign_id, attempt.attempt_run_id)
    assert attempt_run.status.value == "failed"
    assert attempt_run.validation_report["repair_attempted"] is True
    report_text = json.dumps(attempt_run.validation_report)
    assert "puzzle_enrichment.clue_location_invalid" in report_text
    assert "forbidden_rejected_value" not in report_text
    assert "SHOULD_NOT_PERSIST" not in report_text
    assert len(gateway.messages) == 2
    assert gateway.profiles[1].token_budget == gateway.profiles[0].token_budget - 700
    estimated_input = gateway.profiles[1].override_notes["estimated_input_tokens"]
    assert isinstance(estimated_input, int) and estimated_input > 0
    assert gateway.profiles[1].override_notes["output_token_limit"] <= (
        gateway.profiles[1].token_budget - estimated_input
    )
    repair_document = json.loads(gateway.messages[1][0].content)
    assert repair_document["previous_arguments"] == invalid
