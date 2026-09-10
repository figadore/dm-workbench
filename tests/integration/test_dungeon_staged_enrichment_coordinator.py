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
from dm_assistant.modules.preparation import GenerationContextPin, PreparationService
from dm_assistant.modules.scope import TaskType, resolve_task_scope
from dm_assistant.orchestration.dungeons import (
    DUNGEON_TIER_A_CANARY,
    BuildDungeonTierAFixedCaseEvidenceWorkflow,
    DungeonExplorationAffordanceApproval,
    DungeonExplorationContextSelection,
    DungeonExplorationPromptApplicationService,
    DungeonExplorationPromptService,
    DungeonFeatureInteractionContextSelection,
    DungeonFeatureInteractionPromptApplicationService,
    DungeonFeatureInteractionPromptService,
    DungeonObjectiveContextSelection,
    DungeonObjectivePromptApplicationService,
    DungeonObjectivePromptService,
    DungeonPromptApplicationService,
    DungeonPromptService,
    DungeonPuzzleClueApproval,
    DungeonPuzzleContextSelection,
    DungeonPuzzlePromptApplicationService,
    DungeonPuzzlePromptService,
    DungeonRoomNarrativeContextSelection,
    DungeonRoomNarrativePromptApplicationService,
    DungeonRoomNarrativePromptService,
    DungeonStagedEnrichmentChainCoordinator,
    DungeonStagedEnrichmentCoordinator,
    DungeonStagedEnrichmentDispatch,
    DungeonStagedExplorationPolicy,
    DungeonStagedFeatureInteractionPolicy,
    DungeonStagedObjectivePolicy,
    DungeonStagedPuzzlePolicy,
    DungeonStagedRoomNarrativePolicy,
    DungeonStagedTrapPolicy,
    DungeonStudioService,
    DungeonStudioSpecification,
    DungeonTierACanaryApplicationService,
    DungeonTierAFixedCaseApplicationService,
    DungeonTierAFixedCaseEvidenceService,
    DungeonTierAFixedCaseStructuralApplicationService,
    DungeonTrapContextSelection,
    DungeonTrapPromptApplicationService,
    DungeonTrapPromptService,
    DungeonWorkflowResult,
    PromptDungeonStagedEnrichmentChainWorkflow,
    PromptDungeonStagedEnrichmentWorkflow,
    PromptDungeonTierAFixedCaseStructuralWorkflow,
    PromptDungeonTierAFixedCaseTaskWorkflow,
    PromptDungeonWorkflow,
    resolve_dungeon_exploration_prompt_profile,
    resolve_dungeon_feature_interaction_prompt_profile,
    resolve_dungeon_objective_prompt_profile,
    resolve_dungeon_prompt_profile,
    resolve_dungeon_puzzle_prompt_profile,
    resolve_dungeon_room_narrative_prompt_profile,
    resolve_dungeon_tier_a_canary_profiles,
    resolve_dungeon_trap_prompt_profile,
    validate_final_staged_dungeon,
)
from dm_assistant.orchestration.dungeons.evals import (
    build_dungeon_tier_a_fixed_case_context,
    load_dungeon_tier_a_eval_manifest,
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
                    "room_ref": "threshold",
                    "trap": {"name": "Falling Lens", "challenge": "moderate"},
                },
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


def _canary_proposal() -> dict[str, object]:
    """One provider-free structural child for staged canary wiring coverage."""

    return {
        "proposal_version": "1",
        "plan": {
            "schema_version": "1.0.0",
            "title": "Windglass Shrine",
            "premise": "Recover the Windglass Seed from an abandoned mountain shrine.",
            "themes": ["wind-carved stone", "colored mountain glass"],
            "rooms": [
                {
                    "ref": "entry",
                    "name": "Pilgrim Threshold",
                    "role": "entrance",
                    "purpose": "Establish the abandoned windswept shrine.",
                },
                {
                    "ref": "gallery",
                    "name": "Bell Gallery",
                    "role": "transition",
                    "purpose": "Carry the route toward the inner shrine.",
                },
                {
                    "ref": "lens",
                    "name": "Windglass Lens",
                    "role": "puzzle",
                    "purpose": "Align colored windglass before the inner sanctuary.",
                },
                {
                    "ref": "vault",
                    "name": "Seed Sanctuary",
                    "role": "objective",
                    "purpose": "Hold the named Windglass Seed objective.",
                },
                {
                    "ref": "branch",
                    "name": "Windswept Reliquary",
                    "role": "optional",
                    "purpose": "Offer an optional environmental crossing and bypass.",
                    "encounter": "exploration",
                },
            ],
            "critical_path": ["entry", "gallery", "lens", "vault"],
            "branches": [
                {
                    "ref": "reliquary_branch",
                    "from_room": "gallery",
                    "rooms": ["branch"],
                }
            ],
            "loops": [
                {
                    "ref": "reliquary_bypass",
                    "from_room": "branch",
                    "to_room": "vault",
                    "secret": True,
                }
            ],
            "gates": [
                {
                    "ref": "seed_gate",
                    "between_rooms": ["gallery", "lens"],
                    "kind": "locked",
                    "dependency_kind": "key",
                    "dependency_room": "branch",
                    "dependency_name": "Windglass Reliquary Key",
                }
            ],
            "room_contents": [
                {
                    "room_ref": "lens",
                    "trap": {"name": "Falling Windglass", "challenge": "moderate"},
                },
                {
                    "room_ref": "branch",
                    "feature": {
                        "kind": "other",
                        "name": "Reliquary Wind Brake",
                        "description": "A brass brake changes the force across the ledge.",
                    },
                },
                {"room_ref": "vault", "objective": "Windglass Seed"},
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


def _feature_output(
    *, package_id: str, room_id: str, feature_id: str
) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "package_id": package_id,
        "room_id": room_id,
        "feature_id": feature_id,
        "observable_setup": [
            "Two cobalt counterweight handles sit at different heights.",
            "Moving either handle changes the nearest model planet's orbit.",
        ],
        "affordances": [
            {
                "action": "Pull both handles until the orbit tracks align.",
                "adjudication": "Coordinated pulls hold the hanging planets apart.",
                "consequence": "The gallery crossing remains open while both handles are held.",
            },
            {
                "action": "Brace one handle and feather the other.",
                "adjudication": "Small adjustments move one planet at a time.",
                "consequence": "The crossing opens more slowly but needs only one operator.",
            },
        ],
        "reset_or_retry": "Releasing both handles returns the planets to their marked starts.",
    }


def _trap_output(*, package_id: str, room_id: str, trap_id: str) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "package_id": package_id,
        "room_id": room_id,
        "trap_id": trap_id,
        "observable_warning": "A cracked lens hangs above a bright wear mark.",
        "trigger": "Opening the weather door releases the lens frame.",
        "effect_narration": "The lens drops across the marked threshold.",
        "detection_method": "Inspect the loose hinge and taut release wire.",
        "disable_operation": "Brace the frame and slacken the wire before opening the door.",
        "consequences": ["The fallen lens blocks the direct threshold."],
        "reset_or_recovery": "The frame can be lifted back onto its hinge.",
    }


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
        "observable_goal": "The synthetic star seed rests inside the cobalt cradle.",
        "resolution_guidance": "Reward plans that reuse the observatory's understood mechanisms.",
        "resolutions": [
            {
                "mechanic_ids": list(mechanic_ids[:2]),
                "action": "Align the model sky and steady the gallery orbit.",
                "outcome": "The cradle opens while the approach remains stable.",
            },
            {
                "mechanic_ids": list(mechanic_ids[2:]),
                "action": "Brace the threshold lens and counterweight before lifting the seed.",
                "outcome": "The seed comes free without disturbing the model sky.",
            },
        ],
        "setback_or_aftermath": "A rushed attempt closes the cradle until the orbit resets.",
    }


def _narrative_output(
    *, package_id: str, room_ids: tuple[str, ...]
) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "package_id": package_id,
        "rooms": [
            {
                "room_id": room_id,
                "read_aloud": (
                    f"Cobalt light crosses weathered brass in observatory chamber {index}."
                ),
                "observable_framing": [
                    "Wind turns a visible model star.",
                    "Bright wear marks interrupt the blue patina.",
                ],
            }
            for index, room_id in enumerate(room_ids, start=1)
        ],
    }


class _DynamicCanaryGateway:
    """Faux provider that authors only from each exact task context."""

    def __init__(
        self,
        *,
        reject_feature: bool = False,
        overpopulate_exploration: bool = False,
        structural_room_count: int = 5,
    ) -> None:
        self.reject_feature = reject_feature
        self.overpopulate_exploration = overpopulate_exploration
        self.structural_room_count = structural_room_count
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
        self.messages.append(messages)
        self.profiles.append(profile)
        self.allowed_tools.append(allowed_tools)
        self.tool_schemas.append(tool_schemas)
        tool_name = allowed_tools[0]
        if tool_name == "submit_dungeon_plan":
            arguments = _canary_proposal()
            if self.structural_room_count > 5:
                plan = arguments["plan"]
                assert isinstance(plan, dict)
                rooms = plan["rooms"]
                branches = plan["branches"]
                loops = plan["loops"]
                assert isinstance(rooms, list)
                assert isinstance(branches, list)
                assert isinstance(loops, list)
                branch = branches[0]
                loop = loops[0]
                assert isinstance(branch, dict)
                assert isinstance(loop, dict)
                branch_rooms = branch["rooms"]
                assert isinstance(branch_rooms, list)
                for index in range(6, self.structural_room_count + 1):
                    ref = f"branch_{index}"
                    rooms.append(
                        {
                            "ref": ref,
                            "name": f"Optional Chamber {index}",
                            "role": "optional",
                            "purpose": "Vary the optional branch progression.",
                        }
                    )
                    branch_rooms.append(ref)
                    loop["from_room"] = ref
            if self.overpopulate_exploration:
                plan = arguments["plan"]
                assert isinstance(plan, dict)
                rooms = plan["rooms"]
                assert isinstance(rooms, list)
                for room in rooms:
                    assert isinstance(room, dict)
                    room["encounter"] = "exploration"
        else:
            document = json.loads(messages[0].content)
            context = document["context"]
            package_id = context["package_id"]
            if tool_name == "submit_dungeon_room_narrative":
                arguments = _narrative_output(
                    package_id=package_id,
                    room_ids=tuple(item["room_id"] for item in context["rooms"]),
                )
            else:
                room_id = context["room"]["room_id"]
                if tool_name == "submit_dungeon_puzzle":
                    arguments = _puzzle_output(
                        package_id=package_id,
                        room_id=room_id,
                        clue_location_id=context["clue_locations"][0]["location_id"],
                    )
                elif tool_name == "submit_dungeon_exploration":
                    arguments = _exploration_output(
                        package_id=package_id,
                        room_id=room_id,
                        encounter_slot_id=context["room"]["encounter_slot_id"],
                        affordance_id=context["affordances"][0]["affordance_id"],
                    )
                elif tool_name == "submit_dungeon_feature_interaction":
                    arguments = _feature_output(
                        package_id=package_id,
                        room_id=room_id,
                        feature_id=context["feature"]["feature_id"],
                    )
                elif tool_name == "submit_dungeon_trap":
                    arguments = _trap_output(
                        package_id=package_id,
                        room_id=room_id,
                        trap_id=context["trap"]["trap_id"],
                    )
                else:
                    assert tool_name == "submit_dungeon_objective"
                    arguments = _objective_output(
                        package_id=package_id,
                        room_id=room_id,
                        objective_id=context["objective"]["objective_id"],
                        mechanic_ids=tuple(
                            item["mechanic_id"]
                            for item in context["accepted_mechanics"]
                        ),
                    )
        return GatewayCompletion(
            tool_calls=(
                ToolCall(
                    tool_name=tool_name,
                    call_id=f"dynamic-{len(self.allowed_tools)}",
                    arguments=cast(dict[str, JsonValue], arguments),
                ),
            ),
            input_tokens=200,
            output_tokens=(
                2_049
                if self.reject_feature
                and tool_name == "submit_dungeon_feature_interaction"
                else 350
            ),
        )


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


def _canary_application(
    *,
    studio: DungeonStudioService,
    preparation: PreparationService,
    gateway: _DynamicCanaryGateway,
) -> DungeonTierACanaryApplicationService:
    structural = DungeonPromptApplicationService(
        preparation, DungeonPromptService(studio, gateway)
    )
    one_step = DungeonStagedEnrichmentCoordinator(
        preparation,
        puzzle=DungeonPuzzlePromptApplicationService(
            preparation, DungeonPuzzlePromptService(studio, gateway)
        ),
        exploration=DungeonExplorationPromptApplicationService(
            preparation, DungeonExplorationPromptService(studio, gateway)
        ),
        feature_interaction=DungeonFeatureInteractionPromptApplicationService(
            preparation, DungeonFeatureInteractionPromptService(studio, gateway)
        ),
        trap=DungeonTrapPromptApplicationService(
            preparation, DungeonTrapPromptService(studio, gateway)
        ),
        objective=DungeonObjectivePromptApplicationService(
            preparation, DungeonObjectivePromptService(studio, gateway)
        ),
        room_narrative=DungeonRoomNarrativePromptApplicationService(
            preparation, DungeonRoomNarrativePromptService(studio, gateway)
        ),
    )
    return DungeonTierACanaryApplicationService(
        preparation,
        structural,
        DungeonStagedEnrichmentChainCoordinator(one_step),
    )


def _structural_parent(
    *,
    campaign_id: uuid.UUID,
    studio: DungeonStudioService,
    prompt: str = "Build the synthetic Cobalt Orrery and recover its star seed.",
    proposal: dict[str, object] | None = None,
    context: GenerationContextPin | None = None,
) -> tuple[DungeonWorkflowResult, FakeGatewayClient]:
    gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_plan",
                        call_id="structural-plan",
                        arguments=cast(dict[str, JsonValue], proposal or _proposal()),
                    ),
                ),
                input_tokens=100,
                output_tokens=200,
            ),
        )
    )
    command = PromptDungeonWorkflow(
        campaign_id=campaign_id,
        prompt=prompt,
        seed=714000101,
        created_by="synthetic-dm",
        scope=resolve_task_scope(
            dm_principal_id="dm",
            campaign_owner_id="dm",
            task_type=TaskType.STANDALONE_DUNGEON,
        ),
    )
    profile = resolve_dungeon_prompt_profile(
        provider_id="faux",
        model_id="faux_deterministic_v1",
        capabilities=("text", "tool_calls"),
        context_window_tokens=16_384,
        output_token_limit=4_096,
    )
    prompts = DungeonPromptService(studio, gateway)
    result = (
        prompts.create(command, profile)
        if context is None
        else prompts.create_with_context(command, profile, context=context)
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


def _feature_profile() -> ResolvedModelRunProfile:
    return resolve_dungeon_feature_interaction_prompt_profile(
        provider_id="faux",
        model_id="faux_deterministic_v1",
        capabilities=("text", "tool_calls"),
        context_window_tokens=16_384,
        output_token_limit=4_096,
    )


def _trap_profile() -> ResolvedModelRunProfile:
    return resolve_dungeon_trap_prompt_profile(
        provider_id="faux",
        model_id="faux_deterministic_v1",
        capabilities=("text", "tool_calls"),
        context_window_tokens=16_384,
        output_token_limit=4_096,
    )


def _objective_profile() -> ResolvedModelRunProfile:
    return resolve_dungeon_objective_prompt_profile(
        provider_id="faux",
        model_id="faux_deterministic_v1",
        capabilities=("text", "tool_calls"),
        context_window_tokens=16_384,
        output_token_limit=4_096,
    )


def _narrative_profile() -> ResolvedModelRunProfile:
    return resolve_dungeon_room_narrative_prompt_profile(
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


def test_resumed_feature_trap_objective_and_narrative_each_dispatch_one_exact_seam(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    campaign_id = _campaign(db_engine)
    studio, preparation = _studio(db_engine, tmp_path)
    artifact_id, current_version_id, specification = _accepted_puzzle_child(
        campaign_id=campaign_id,
        studio=studio,
        preparation=preparation,
    )
    original_package = specification.package.model_dump_json()

    exploration_policy = _exploration_policy(specification)
    exploration_gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_exploration",
                        call_id="setup-exploration",
                        arguments=cast(
                            dict[str, JsonValue],
                            _exploration_output(
                                package_id=specification.package.id,
                                room_id=exploration_policy.selection.room_id,
                                encounter_slot_id=exploration_policy.encounter_slot_id,
                                affordance_id=(
                                    exploration_policy.selection.affordances[
                                        0
                                    ].affordance_id
                                ),
                            ),
                        ),
                    ),
                ),
                input_tokens=210,
                output_tokens=360,
            ),
        )
    )
    exploration_step = DungeonStagedEnrichmentCoordinator(
        preparation,
        exploration=DungeonExplorationPromptApplicationService(
            preparation, DungeonExplorationPromptService(studio, exploration_gateway)
        ),
    ).execute(
        PromptDungeonStagedEnrichmentWorkflow(
            campaign_id=campaign_id,
            artifact_id=artifact_id,
            parent_version_id=current_version_id,
            policy=exploration_policy,
            created_by="synthetic-dm",
        ),
        _exploration_profile(),
        surface="integration-setup",
    )
    assert exploration_step.attempt is not None
    assert exploration_step.attempt.result is not None
    assert exploration_step.attempt.result.artifact_version_id is not None
    current_version_id = exploration_step.attempt.result.artifact_version_id
    specification = DungeonStudioSpecification.model_validate_json(
        json.dumps(
            preparation.get_version(campaign_id, current_version_id).specification
        )
    )
    assert exploration_step.plan_after.next_task is not None
    assert exploration_step.plan_after.next_task.kind == "feature_interaction"

    feature_task = exploration_step.plan_after.next_task
    feature_policy = DungeonStagedFeatureInteractionPolicy(
        selection=DungeonFeatureInteractionContextSelection(
            room_id=feature_task.room_ids[0],
            feature_id=feature_task.target_ids[0],
            interaction_goal="Stabilize the model planets before crossing the gallery.",
            stakes="A poor adjustment delays the crossing without closing the route.",
            constraints=("Do not author numeric difficulties.",),
        )
    )
    version_count = len(preparation.list_versions(campaign_id, artifact_id))
    mismatched_feature_gateway = FakeGatewayClient(())
    with pytest.raises(ConflictError, match="staged exact target"):
        DungeonStagedEnrichmentCoordinator(
            preparation,
            feature_interaction=DungeonFeatureInteractionPromptApplicationService(
                preparation,
                DungeonFeatureInteractionPromptService(
                    studio, mismatched_feature_gateway
                ),
            ),
        ).execute(
            PromptDungeonStagedEnrichmentWorkflow(
                campaign_id=campaign_id,
                artifact_id=artifact_id,
                parent_version_id=current_version_id,
                policy=feature_policy.model_copy(
                    update={
                        "selection": feature_policy.selection.model_copy(
                            update={"feature_id": "foreign_feature"}
                        )
                    }
                ),
                created_by="synthetic-dm",
            ),
            _feature_profile(),
            surface="integration",
        )
    assert mismatched_feature_gateway.messages == []
    assert len(preparation.list_versions(campaign_id, artifact_id)) == version_count

    feature_gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_feature_interaction",
                        call_id="accepted-feature",
                        arguments=cast(
                            dict[str, JsonValue],
                            _feature_output(
                                package_id=specification.package.id,
                                room_id=feature_policy.selection.room_id,
                                feature_id=feature_policy.selection.feature_id,
                            ),
                        ),
                    ),
                ),
                input_tokens=220,
                output_tokens=340,
            ),
        )
    )
    feature_step = DungeonStagedEnrichmentCoordinator(
        preparation,
        feature_interaction=DungeonFeatureInteractionPromptApplicationService(
            preparation, DungeonFeatureInteractionPromptService(studio, feature_gateway)
        ),
    ).execute(
        PromptDungeonStagedEnrichmentWorkflow(
            campaign_id=campaign_id,
            artifact_id=artifact_id,
            parent_version_id=current_version_id,
            policy=feature_policy,
            created_by="synthetic-dm",
        ),
        _feature_profile(),
        surface="integration",
    )
    assert feature_step.attempt is not None and feature_step.attempt.result is not None
    assert feature_step.attempt.result.artifact_version_id is not None
    current_version_id = feature_step.attempt.result.artifact_version_id
    assert feature_step.plan_after.next_task is not None
    assert feature_step.plan_after.next_task.kind == "trap"
    assert len(feature_gateway.messages) == 1
    assert feature_gateway.allowed_tools == [("submit_dungeon_feature_interaction",)]
    assert len(preparation.list_versions(campaign_id, artifact_id)) == version_count + 1
    specification = DungeonStudioSpecification.model_validate_json(
        json.dumps(
            preparation.get_version(campaign_id, current_version_id).specification
        )
    )

    trap_task = feature_step.plan_after.next_task
    trap_policy = DungeonStagedTrapPolicy(
        selection=DungeonTrapContextSelection(
            room_id=trap_task.room_ids[0],
            trap_id=trap_task.target_ids[0],
            stakes="The falling lens delays entry without sealing the observatory.",
            constraints=("Do not author numeric difficulties.",),
        )
    )
    version_count = len(preparation.list_versions(campaign_id, artifact_id))
    mismatched_trap_gateway = FakeGatewayClient(())
    with pytest.raises(ConflictError, match="staged exact target"):
        DungeonStagedEnrichmentCoordinator(
            preparation,
            trap=DungeonTrapPromptApplicationService(
                preparation, DungeonTrapPromptService(studio, mismatched_trap_gateway)
            ),
        ).execute(
            PromptDungeonStagedEnrichmentWorkflow(
                campaign_id=campaign_id,
                artifact_id=artifact_id,
                parent_version_id=current_version_id,
                policy=trap_policy.model_copy(
                    update={
                        "selection": trap_policy.selection.model_copy(
                            update={"trap_id": "foreign_trap"}
                        )
                    }
                ),
                created_by="synthetic-dm",
            ),
            _trap_profile(),
            surface="integration",
        )
    assert mismatched_trap_gateway.messages == []
    assert len(preparation.list_versions(campaign_id, artifact_id)) == version_count

    trap_gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_trap",
                        call_id="accepted-trap",
                        arguments=cast(
                            dict[str, JsonValue],
                            _trap_output(
                                package_id=specification.package.id,
                                room_id=trap_policy.selection.room_id,
                                trap_id=trap_policy.selection.trap_id,
                            ),
                        ),
                    ),
                ),
                input_tokens=220,
                output_tokens=340,
            ),
        )
    )
    trap_step = DungeonStagedEnrichmentCoordinator(
        preparation,
        trap=DungeonTrapPromptApplicationService(
            preparation, DungeonTrapPromptService(studio, trap_gateway)
        ),
    ).execute(
        PromptDungeonStagedEnrichmentWorkflow(
            campaign_id=campaign_id,
            artifact_id=artifact_id,
            parent_version_id=current_version_id,
            policy=trap_policy,
            created_by="synthetic-dm",
        ),
        _trap_profile(),
        surface="integration",
    )
    assert trap_step.attempt is not None and trap_step.attempt.result is not None
    assert trap_step.attempt.result.artifact_version_id is not None
    current_version_id = trap_step.attempt.result.artifact_version_id
    assert trap_step.plan_after.next_task is not None
    assert trap_step.plan_after.next_task.kind == "objective"
    assert len(trap_gateway.messages) == 1
    assert trap_gateway.allowed_tools == [("submit_dungeon_trap",)]
    assert len(preparation.list_versions(campaign_id, artifact_id)) == version_count + 1
    specification = DungeonStudioSpecification.model_validate_json(
        json.dumps(
            preparation.get_version(campaign_id, current_version_id).specification
        )
    )

    objective_task = trap_step.plan_after.next_task
    mechanic_ids = (
        specification.puzzle_model_lineage[-1].output.room_id,
        specification.exploration_model_lineage[-1].output.encounter_slot_id,
        specification.feature_interaction_model_lineage[-1].output.feature_id,
        specification.trap_model_lineage[-1].output.trap_id,
    )
    objective_policy = DungeonStagedObjectivePolicy(
        selection=DungeonObjectiveContextSelection(
            room_id=objective_task.room_ids[0],
            objective_id=objective_task.target_ids[0],
            mechanic_ids=mechanic_ids,
            stakes="Recover the star seed intact; setbacks cost time only.",
            constraints=("Offer at least two credible resolutions.",),
        )
    )
    version_count = len(preparation.list_versions(campaign_id, artifact_id))
    mismatched_objective_gateway = FakeGatewayClient(())
    with pytest.raises(ConflictError, match="staged exact target"):
        DungeonStagedEnrichmentCoordinator(
            preparation,
            objective=DungeonObjectivePromptApplicationService(
                preparation,
                DungeonObjectivePromptService(studio, mismatched_objective_gateway),
            ),
        ).execute(
            PromptDungeonStagedEnrichmentWorkflow(
                campaign_id=campaign_id,
                artifact_id=artifact_id,
                parent_version_id=current_version_id,
                policy=objective_policy.model_copy(
                    update={
                        "selection": objective_policy.selection.model_copy(
                            update={"objective_id": "foreign_objective"}
                        )
                    }
                ),
                created_by="synthetic-dm",
            ),
            _objective_profile(),
            surface="integration",
        )
    assert mismatched_objective_gateway.messages == []
    assert len(preparation.list_versions(campaign_id, artifact_id)) == version_count

    objective_gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_objective",
                        call_id="accepted-objective",
                        arguments=cast(
                            dict[str, JsonValue],
                            _objective_output(
                                package_id=specification.package.id,
                                room_id=objective_policy.selection.room_id,
                                objective_id=objective_policy.selection.objective_id,
                                mechanic_ids=mechanic_ids,
                            ),
                        ),
                    ),
                ),
                input_tokens=240,
                output_tokens=380,
            ),
        )
    )
    objective_step = DungeonStagedEnrichmentCoordinator(
        preparation,
        objective=DungeonObjectivePromptApplicationService(
            preparation, DungeonObjectivePromptService(studio, objective_gateway)
        ),
    ).execute(
        PromptDungeonStagedEnrichmentWorkflow(
            campaign_id=campaign_id,
            artifact_id=artifact_id,
            parent_version_id=current_version_id,
            policy=objective_policy,
            created_by="synthetic-dm",
        ),
        _objective_profile(),
        surface="integration",
    )
    assert objective_step.attempt is not None
    assert objective_step.attempt.result is not None
    assert objective_step.attempt.result.artifact_version_id is not None
    current_version_id = objective_step.attempt.result.artifact_version_id
    assert objective_step.plan_after.next_task is not None
    assert objective_step.plan_after.next_task.kind == "room_narrative"
    assert len(objective_gateway.messages) == 1
    assert objective_gateway.allowed_tools == [("submit_dungeon_objective",)]
    assert len(preparation.list_versions(campaign_id, artifact_id)) == version_count + 1
    specification = DungeonStudioSpecification.model_validate_json(
        json.dumps(
            preparation.get_version(campaign_id, current_version_id).specification
        )
    )

    narrative_task = objective_step.plan_after.next_task
    narrative_policy = DungeonStagedRoomNarrativePolicy(
        selection=DungeonRoomNarrativeContextSelection(
            room_ids=narrative_task.room_ids,
            tone=("wind-worn astronomical mystery",),
            constraints=("Use only player-observable information.",),
        )
    )
    assert len(narrative_task.room_ids) > 1
    version_count = len(preparation.list_versions(campaign_id, artifact_id))
    mismatched_narrative_gateway = FakeGatewayClient(())
    with pytest.raises(ConflictError, match="staged room set"):
        DungeonStagedEnrichmentCoordinator(
            preparation,
            room_narrative=DungeonRoomNarrativePromptApplicationService(
                preparation,
                DungeonRoomNarrativePromptService(studio, mismatched_narrative_gateway),
            ),
        ).execute(
            PromptDungeonStagedEnrichmentWorkflow(
                campaign_id=campaign_id,
                artifact_id=artifact_id,
                parent_version_id=current_version_id,
                policy=narrative_policy.model_copy(
                    update={
                        "selection": narrative_policy.selection.model_copy(
                            update={"room_ids": narrative_task.room_ids[:-1]}
                        )
                    }
                ),
                created_by="synthetic-dm",
            ),
            _narrative_profile(),
            surface="integration",
        )
    assert mismatched_narrative_gateway.messages == []
    assert len(preparation.list_versions(campaign_id, artifact_id)) == version_count

    narrative_gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_room_narrative",
                        call_id="accepted-narratives",
                        arguments=cast(
                            dict[str, JsonValue],
                            _narrative_output(
                                package_id=specification.package.id,
                                room_ids=narrative_policy.selection.room_ids,
                            ),
                        ),
                    ),
                ),
                input_tokens=250,
                output_tokens=400,
            ),
        )
    )
    narrative_step = DungeonStagedEnrichmentCoordinator(
        preparation,
        room_narrative=DungeonRoomNarrativePromptApplicationService(
            preparation, DungeonRoomNarrativePromptService(studio, narrative_gateway)
        ),
    ).execute(
        PromptDungeonStagedEnrichmentWorkflow(
            campaign_id=campaign_id,
            artifact_id=artifact_id,
            parent_version_id=current_version_id,
            policy=narrative_policy,
            created_by="synthetic-dm",
        ),
        _narrative_profile(),
        surface="integration",
    )
    assert narrative_step.attempt is not None
    assert narrative_step.attempt.result is not None
    assert narrative_step.attempt.result.artifact_version_id is not None
    final_version_id = narrative_step.attempt.result.artifact_version_id
    assert narrative_step.plan_after.status == "complete"
    assert narrative_step.plan_after.next_task is None
    assert len(narrative_gateway.messages) == 1
    assert narrative_gateway.allowed_tools == [("submit_dungeon_room_narrative",)]
    assert len(preparation.list_versions(campaign_id, artifact_id)) == version_count + 1
    final_specification = DungeonStudioSpecification.model_validate_json(
        json.dumps(preparation.get_version(campaign_id, final_version_id).specification)
    )
    assert final_specification.package.model_dump_json() == original_package
    assert (
        preparation.get_artifact(campaign_id, artifact_id).current_version_id
        == final_version_id
    )


def test_frozen_canary_resumes_structural_child_through_all_tasks_and_final_gate(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    campaign_id = _campaign(db_engine)
    studio, preparation = _studio(db_engine, tmp_path)
    gateway = _DynamicCanaryGateway()
    application = _canary_application(
        studio=studio, preparation=preparation, gateway=gateway
    )
    structural_profile = resolve_dungeon_prompt_profile(
        provider_id="faux",
        model_id="faux_deterministic_v1",
        capabilities=("text", "tool_calls"),
        context_window_tokens=16_384,
        output_token_limit=4_096,
    )
    staged_profiles = resolve_dungeon_tier_a_canary_profiles(
        provider_id="faux",
        model_id="faux_deterministic_v1",
        capabilities=("text", "tool_calls"),
        context_window_tokens=16_384,
        output_token_limit=4_096,
        requested_effort=structural_profile.requested_effort,
    )

    outcome = application.execute(
        PromptDungeonWorkflow(
            campaign_id=campaign_id,
            prompt=DUNGEON_TIER_A_CANARY.prompt,
            seed=DUNGEON_TIER_A_CANARY.seed,
            created_by="synthetic-dm",
            scope=resolve_task_scope(
                dm_principal_id="dm",
                campaign_owner_id="dm",
                task_type=TaskType.STANDALONE_DUNGEON,
            ),
        ),
        structural_profile,
        staged_profiles,
        surface=DUNGEON_TIER_A_CANARY.canary_id,
    )

    assert outcome.success
    assert outcome.public_code == "dungeon_tier_a_canary_completed"
    assert outcome.chain is not None and outcome.chain.stop_reason == "complete"
    assert len(outcome.chain.steps) == 6
    assert len(outcome.task_attempt_run_ids) == 6
    assert outcome.final_validation is not None and outcome.final_validation.valid
    assert outcome.current_version_id is not None
    final_version = preparation.get_version(campaign_id, outcome.current_version_id)
    final_specification = DungeonStudioSpecification.model_validate_json(
        json.dumps(final_version.specification)
    )
    assert validate_final_staged_dungeon(final_specification).valid
    structural_result = outcome.structural_attempt.result
    assert structural_result is not None
    assert structural_result.artifact_id is not None
    assert structural_result.artifact_version_id is not None
    structural_specification = DungeonStudioSpecification.model_validate_json(
        json.dumps(
            preparation.get_version(
                campaign_id, structural_result.artifact_version_id
            ).specification
        )
    )
    assert (
        final_specification.package.model_dump_json()
        == structural_specification.package.model_dump_json()
    )
    assert (
        len(preparation.list_versions(campaign_id, structural_result.artifact_id)) == 7
    )
    artifact = preparation.get_artifact(campaign_id, structural_result.artifact_id)
    assert artifact.current_version_id == outcome.current_version_id
    assert artifact.lifecycle.value == "draft"
    assert gateway.allowed_tools == [
        ("submit_dungeon_plan",),
        ("submit_dungeon_puzzle",),
        ("submit_dungeon_exploration",),
        ("submit_dungeon_feature_interaction",),
        ("submit_dungeon_trap",),
        ("submit_dungeon_objective",),
        ("submit_dungeon_room_narrative",),
    ]
    assert len({profile.task_profile_id for profile in gateway.profiles}) == 7


def test_frozen_canary_stops_before_enrichment_when_structural_slots_are_overpopulated(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    campaign_id = _campaign(db_engine)
    studio, preparation = _studio(db_engine, tmp_path)
    gateway = _DynamicCanaryGateway(overpopulate_exploration=True)
    application = _canary_application(
        studio=studio, preparation=preparation, gateway=gateway
    )
    structural_profile = resolve_dungeon_prompt_profile(
        provider_id="faux",
        model_id="faux_deterministic_v1",
        capabilities=("text", "tool_calls"),
        context_window_tokens=16_384,
        output_token_limit=4_096,
    )

    outcome = application.execute(
        PromptDungeonWorkflow(
            campaign_id=campaign_id,
            prompt=DUNGEON_TIER_A_CANARY.prompt,
            seed=DUNGEON_TIER_A_CANARY.seed,
            created_by="synthetic-dm",
            scope=resolve_task_scope(
                dm_principal_id="dm",
                campaign_owner_id="dm",
                task_type=TaskType.STANDALONE_DUNGEON,
            ),
        ),
        structural_profile,
        resolve_dungeon_tier_a_canary_profiles(
            provider_id="faux",
            model_id="faux_deterministic_v1",
            capabilities=("text", "tool_calls"),
            context_window_tokens=16_384,
            output_token_limit=4_096,
            requested_effort=structural_profile.requested_effort,
        ),
        surface=DUNGEON_TIER_A_CANARY.canary_id,
    )

    assert not outcome.success
    assert outcome.public_code == "dungeon_tier_a_canary_structural_requirements_failed"
    assert outcome.validation_codes == (
        "canary.structural_exploration_count_mismatch",
        "canary.exploration_affordance_missing",
    )
    assert outcome.chain is None
    assert outcome.final_validation is None
    assert outcome.task_attempt_run_ids == ()
    assert outcome.current_version_id is not None
    assert gateway.allowed_tools == [("submit_dungeon_plan",)]
    structural_result = outcome.structural_attempt.result
    assert structural_result is not None and structural_result.artifact_id is not None
    artifact = preparation.get_artifact(campaign_id, structural_result.artifact_id)
    assert artifact.current_version_id == outcome.current_version_id
    assert artifact.lifecycle.value == "draft"
    assert len(preparation.list_versions(campaign_id, artifact.id)) == 1


def test_frozen_canary_stops_on_first_rejected_task_with_body_free_attempt(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    campaign_id = _campaign(db_engine)
    studio, preparation = _studio(db_engine, tmp_path)
    gateway = _DynamicCanaryGateway(reject_feature=True)
    application = _canary_application(
        studio=studio, preparation=preparation, gateway=gateway
    )
    structural_profile = resolve_dungeon_prompt_profile(
        provider_id="faux",
        model_id="faux_deterministic_v1",
        capabilities=("text", "tool_calls"),
        context_window_tokens=16_384,
        output_token_limit=4_096,
    )

    outcome = application.execute(
        PromptDungeonWorkflow(
            campaign_id=campaign_id,
            prompt=DUNGEON_TIER_A_CANARY.prompt,
            seed=DUNGEON_TIER_A_CANARY.seed,
            created_by="synthetic-dm",
            scope=resolve_task_scope(
                dm_principal_id="dm",
                campaign_owner_id="dm",
                task_type=TaskType.STANDALONE_DUNGEON,
            ),
        ),
        structural_profile,
        resolve_dungeon_tier_a_canary_profiles(
            provider_id="faux",
            model_id="faux_deterministic_v1",
            capabilities=("text", "tool_calls"),
            context_window_tokens=16_384,
            output_token_limit=4_096,
            requested_effort=structural_profile.requested_effort,
        ),
        surface=DUNGEON_TIER_A_CANARY.canary_id,
    )

    assert not outcome.success
    assert outcome.public_code == "dungeon_tier_a_canary_task_rejected"
    assert outcome.chain is not None
    assert outcome.chain.stop_reason == "task_rejected"
    assert len(outcome.chain.steps) == 3
    assert outcome.final_validation is None
    assert gateway.allowed_tools == [
        ("submit_dungeon_plan",),
        ("submit_dungeon_puzzle",),
        ("submit_dungeon_exploration",),
        ("submit_dungeon_feature_interaction",),
    ]
    assert outcome.current_version_id is not None
    structural_result = outcome.structural_attempt.result
    assert structural_result is not None and structural_result.artifact_id is not None
    artifact = preparation.get_artifact(campaign_id, structural_result.artifact_id)
    assert artifact.current_version_id == outcome.current_version_id
    assert artifact.lifecycle.value == "draft"
    assert (
        len(preparation.list_versions(campaign_id, structural_result.artifact_id)) == 3
    )
    failed_attempt = outcome.chain.steps[-1].attempt
    assert failed_attempt is not None
    report = preparation.get_generation_run(
        campaign_id, failed_attempt.attempt_run_id
    ).validation_report
    duration_ms = report.pop("duration_ms")
    assert isinstance(duration_ms, int) and duration_ms >= 0
    assert report == {
        "stage": "model_submission",
        "code": "dungeon_feature_interaction_prompt_token_budget_exhausted",
        "usage": {
            "limit_kind": "output",
            "token_limit": 2048,
            "input_tokens": 200,
            "output_tokens": 2049,
        },
    }
    assert "observable_setup" not in json.dumps(report)
    assert "Reliquary Wind Brake" not in json.dumps(report)


def test_repeated_coordinator_stops_after_third_task_rejection(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    campaign_id = _campaign(db_engine)
    studio, preparation = _studio(db_engine, tmp_path)
    structural, _ = _structural_parent(campaign_id=campaign_id, studio=studio)
    parent_version_id = structural.artifact_version_id
    artifact_id = structural.artifact_id
    assert isinstance(parent_version_id, uuid.UUID)
    assert isinstance(artifact_id, uuid.UUID)
    parent = preparation.get_version(campaign_id, parent_version_id)
    specification = DungeonStudioSpecification.model_validate_json(
        json.dumps(parent.specification)
    )
    package_id = specification.package.id
    puzzle_policy = _coordinator_command(
        campaign_id=campaign_id,
        artifact_id=artifact_id,
        parent_version_id=parent_version_id,
        specification=specification,
    ).policy
    assert isinstance(puzzle_policy, DungeonStagedPuzzlePolicy)
    puzzle_room_id = puzzle_policy.selection.room_id
    exploration_policy = _exploration_policy(specification)
    feature = next(
        marker
        for marker in specification.package.room_mechanic_markers
        if marker.kind.value == "feature"
    )
    feature_policy = DungeonStagedFeatureInteractionPolicy(
        selection=DungeonFeatureInteractionContextSelection(
            room_id=feature.room_id,
            feature_id=feature.id,
            interaction_goal="Stabilize the model planets before crossing the gallery.",
            stakes="A poor adjustment delays the crossing without closing the route.",
            constraints=("Do not author numeric difficulties.",),
        )
    )
    trap = next(
        marker
        for marker in specification.package.room_mechanic_markers
        if marker.kind.value == "trap"
    )
    trap_policy = DungeonStagedTrapPolicy(
        selection=DungeonTrapContextSelection(
            room_id=trap.room_id,
            trap_id=trap.id,
            stakes="The falling lens delays entry without sealing the observatory.",
            constraints=("Do not author numeric difficulties.",),
        )
    )

    puzzle_gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_puzzle",
                        call_id="chain-puzzle",
                        arguments=cast(
                            dict[str, JsonValue],
                            _puzzle_output(
                                package_id=package_id,
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
    exploration_gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_exploration",
                        call_id="chain-exploration",
                        arguments=cast(
                            dict[str, JsonValue],
                            _exploration_output(
                                package_id=package_id,
                                room_id=exploration_policy.selection.room_id,
                                encounter_slot_id=exploration_policy.encounter_slot_id,
                                affordance_id=(
                                    exploration_policy.selection.affordances[
                                        0
                                    ].affordance_id
                                ),
                            ),
                        ),
                    ),
                ),
                input_tokens=210,
                output_tokens=360,
            ),
        )
    )
    feature_gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_feature_interaction",
                        call_id="chain-feature-over-budget",
                        arguments=cast(
                            dict[str, JsonValue],
                            _feature_output(
                                package_id=package_id,
                                room_id=feature.room_id,
                                feature_id=feature.id,
                            ),
                        ),
                    ),
                ),
                input_tokens=220,
                output_tokens=2_049,
            ),
        )
    )
    trap_gateway = FakeGatewayClient(())
    one_step = DungeonStagedEnrichmentCoordinator(
        preparation,
        puzzle=DungeonPuzzlePromptApplicationService(
            preparation, DungeonPuzzlePromptService(studio, puzzle_gateway)
        ),
        exploration=DungeonExplorationPromptApplicationService(
            preparation, DungeonExplorationPromptService(studio, exploration_gateway)
        ),
        feature_interaction=DungeonFeatureInteractionPromptApplicationService(
            preparation,
            DungeonFeatureInteractionPromptService(studio, feature_gateway),
        ),
        trap=DungeonTrapPromptApplicationService(
            preparation, DungeonTrapPromptService(studio, trap_gateway)
        ),
    )

    chain = DungeonStagedEnrichmentChainCoordinator(one_step).execute(
        PromptDungeonStagedEnrichmentChainWorkflow(
            campaign_id=campaign_id,
            artifact_id=artifact_id,
            parent_version_id=parent_version_id,
            dispatches=(
                DungeonStagedEnrichmentDispatch(
                    policy=puzzle_policy,
                    profile=_profile(),
                ),
                DungeonStagedEnrichmentDispatch(
                    policy=exploration_policy,
                    profile=_exploration_profile(),
                ),
                DungeonStagedEnrichmentDispatch(
                    policy=feature_policy,
                    profile=_feature_profile(),
                ),
                DungeonStagedEnrichmentDispatch(
                    policy=trap_policy,
                    profile=_trap_profile(),
                ),
            ),
            maximum_tasks=4,
            created_by="synthetic-dm",
        ),
        surface="integration",
    )

    assert chain.stop_reason == "task_rejected"
    assert len(chain.steps) == 3
    assert chain.steps[-1].public_code == (
        "dungeon_feature_interaction_prompt_token_budget_exhausted"
    )
    assert chain.steps[-1].plan_before.next_task is not None
    assert chain.steps[-1].plan_before.next_task.kind == "feature_interaction"
    assert chain.plan_after == chain.steps[-1].plan_before
    assert chain.current_version_id == (
        chain.steps[1].attempt.result.artifact_version_id  # type: ignore[union-attr]
    )
    assert (
        preparation.get_artifact(campaign_id, artifact_id).current_version_id
        == chain.current_version_id
    )
    assert len(preparation.list_versions(campaign_id, artifact_id)) == 3
    assert (
        sum(
            len(gateway.messages)
            for gateway in (
                puzzle_gateway,
                exploration_gateway,
                feature_gateway,
                trap_gateway,
            )
        )
        == 3
    )
    assert trap_gateway.messages == []
    assert preparation.get_artifact(campaign_id, artifact_id).lifecycle.value == "draft"


def test_fixed_case_resumes_exact_failure_then_completes_every_staged_task(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    manifest = load_dungeon_tier_a_eval_manifest()
    case = manifest.cases[0]
    campaign_id = _campaign(db_engine)
    studio, preparation = _studio(db_engine, tmp_path)
    structural, _ = _structural_parent(
        campaign_id=campaign_id,
        studio=studio,
        prompt=case.prompt,
        proposal=_canary_proposal(),
        context=build_dungeon_tier_a_fixed_case_context(
            manifest,
            case.case_id,
            preparation_owner_id=campaign_id,
        ),
    )
    artifact_id = structural.artifact_id
    parent_version_id = structural.artifact_version_id
    assert isinstance(artifact_id, uuid.UUID)
    assert isinstance(parent_version_id, uuid.UUID)
    parent = preparation.get_version(campaign_id, parent_version_id)
    specification = DungeonStudioSpecification.model_validate_json(
        json.dumps(parent.specification)
    )
    original_package = specification.package.model_dump_json()
    puzzle_room_id = next(
        room.id for room in specification.package.rooms if room.role.value == "puzzle"
    )
    profiles = resolve_dungeon_tier_a_canary_profiles(
        provider_id="faux",
        model_id="faux_deterministic_v1",
        capabilities=("text", "thinking", "tool_calls"),
        context_window_tokens=16_384,
        output_token_limit=4_096,
        requested_effort=_profile().requested_effort,
    )
    command = PromptDungeonTierAFixedCaseTaskWorkflow(
        campaign_id=campaign_id,
        artifact_id=artifact_id,
        parent_version_id=parent_version_id,
        case_id=case.case_id,
        variant_id="variant_01",
        created_by="synthetic-dm",
    )

    rejected_gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_puzzle",
                        call_id="over-budget-puzzle",
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
                output_tokens=2_049,
            ),
        )
    )
    rejected = DungeonTierAFixedCaseApplicationService(
        preparation,
        studio,
        DungeonStagedEnrichmentCoordinator(
            preparation,
            puzzle=DungeonPuzzlePromptApplicationService(
                preparation, DungeonPuzzlePromptService(studio, rejected_gateway)
            ),
        ),
    ).execute(command, manifest, profiles)

    assert not rejected.success
    assert len(rejected_gateway.messages) == 1
    rejected_run = preparation.get_generation_run(
        campaign_id, rejected.evaluation_run_id
    )
    assert rejected_run.status.value == "failed"
    assert rejected_run.context_envelope_kind == "dungeon_tier_a_eval_task"
    assert rejected_run.context_payload_version == "1.0.0"
    assert rejected_run.context_payload_sha256 is not None
    assert rejected_run.input_scope["case_id"] == case.case_id
    assert rejected_run.input_scope["task_kind"] == "puzzle"
    assert isinstance(rejected.plan.dispatch.policy, DungeonStagedPuzzlePolicy)
    assert len(rejected.plan.dispatch.policy.selection.clue_locations) > 1
    assert rejected_run.input_scope["trusted_policy_sha256"] == (
        rejected.plan.trusted_policy_sha256
    )
    assert rejected_run.input_scope["context_sha256"]
    assert rejected_run.validation_report["task_attempt_run_id"]
    assert preparation.get_artifact(campaign_id, artifact_id).current_version_id == (
        parent_version_id
    )

    drifted_case = case.model_copy(
        update={"setting": f"{case.setting} A deliberately drifted detail."}
    )
    drifted_manifest = manifest.model_copy(
        update={"cases": (drifted_case, *manifest.cases[1:])}
    )
    no_call_gateway = FakeGatewayClient(())
    with pytest.raises(ConflictError, match="resume input pins changed"):
        DungeonTierAFixedCaseApplicationService(
            preparation,
            studio,
            DungeonStagedEnrichmentCoordinator(
                preparation,
                puzzle=DungeonPuzzlePromptApplicationService(
                    preparation, DungeonPuzzlePromptService(studio, no_call_gateway)
                ),
            ),
        ).execute(
            command.model_copy(
                update={"resume_from_evaluation_run_id": rejected.evaluation_run_id}
            ),
            drifted_manifest,
            profiles,
        )
    assert no_call_gateway.messages == []

    accepted_gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_puzzle",
                        call_id="accepted-resume-puzzle",
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
    resumed = DungeonTierAFixedCaseApplicationService(
        preparation,
        studio,
        DungeonStagedEnrichmentCoordinator(
            preparation,
            puzzle=DungeonPuzzlePromptApplicationService(
                preparation, DungeonPuzzlePromptService(studio, accepted_gateway)
            ),
        ),
    ).execute(
        command.model_copy(
            update={"resume_from_evaluation_run_id": rejected.evaluation_run_id}
        ),
        manifest,
        profiles,
    )

    assert resumed.success
    assert len(accepted_gateway.messages) == 1
    resumed_run = preparation.get_generation_run(campaign_id, resumed.evaluation_run_id)
    assert resumed_run.status.value == "succeeded"
    assert resumed_run.input_scope == rejected_run.input_scope
    assert resumed_run.context_payload_sha256 == rejected_run.context_payload_sha256
    assert resumed_run.validation_report["task_kind"] == "puzzle"
    assert resumed.step.attempt is not None
    assert resumed.step.attempt.result is not None
    child_id = resumed.step.attempt.result.artifact_version_id
    assert child_id is not None
    assert (
        preparation.get_artifact(campaign_id, artifact_id).current_version_id
        == child_id
    )
    assert len(preparation.list_versions(campaign_id, artifact_id)) == 2

    remaining_gateway = _DynamicCanaryGateway()
    remaining = DungeonTierAFixedCaseApplicationService(
        preparation,
        studio,
        DungeonStagedEnrichmentCoordinator(
            preparation,
            puzzle=DungeonPuzzlePromptApplicationService(
                preparation, DungeonPuzzlePromptService(studio, remaining_gateway)
            ),
            exploration=DungeonExplorationPromptApplicationService(
                preparation,
                DungeonExplorationPromptService(studio, remaining_gateway),
            ),
            feature_interaction=DungeonFeatureInteractionPromptApplicationService(
                preparation,
                DungeonFeatureInteractionPromptService(studio, remaining_gateway),
            ),
            trap=DungeonTrapPromptApplicationService(
                preparation, DungeonTrapPromptService(studio, remaining_gateway)
            ),
            objective=DungeonObjectivePromptApplicationService(
                preparation, DungeonObjectivePromptService(studio, remaining_gateway)
            ),
            room_narrative=DungeonRoomNarrativePromptApplicationService(
                preparation,
                DungeonRoomNarrativePromptService(studio, remaining_gateway),
            ),
        ),
    )
    current_version_id = child_id
    expected_kinds = (
        "exploration",
        "feature_interaction",
        "trap",
        "objective",
        "room_narrative",
    )
    last_step = None
    for expected_kind in expected_kinds:
        completed = remaining.execute(
            command.model_copy(update={"parent_version_id": current_version_id}),
            manifest,
            profiles,
        )
        assert completed.success
        assert completed.plan.task_kind == expected_kind
        assert completed.step.attempt is not None
        assert completed.step.attempt.result is not None
        next_version_id = completed.step.attempt.result.artifact_version_id
        assert next_version_id is not None
        current_version_id = next_version_id
        completed_run = preparation.get_generation_run(
            campaign_id, completed.evaluation_run_id
        )
        assert completed_run.status.value == "succeeded"
        assert completed_run.input_scope["task_kind"] == expected_kind
        assert completed_run.context_payload_sha256 is not None
        last_step = completed.step

    assert last_step is not None
    assert last_step.plan_after.status == "complete"
    final = DungeonStudioSpecification.model_validate_json(
        json.dumps(
            preparation.get_version(campaign_id, current_version_id).specification
        )
    )
    assert final.package.model_dump_json() == original_package
    assert validate_final_staged_dungeon(final).valid
    assert remaining_gateway.allowed_tools == [
        ("submit_dungeon_exploration",),
        ("submit_dungeon_feature_interaction",),
        ("submit_dungeon_trap",),
        ("submit_dungeon_objective",),
        ("submit_dungeon_room_narrative",),
    ]


def test_fixed_structure_resumes_only_when_manifest_and_assignment_pins_match(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    manifest = load_dungeon_tier_a_eval_manifest()
    case = manifest.cases[0]
    campaign_id = _campaign(db_engine)
    studio, preparation = _studio(db_engine, tmp_path)
    profiles = resolve_dungeon_tier_a_canary_profiles(
        provider_id="faux",
        model_id="faux_deterministic_v1",
        capabilities=("text", "thinking", "tool_calls"),
        context_window_tokens=16_384,
        output_token_limit=4_096,
        requested_effort=_profile().requested_effort,
    )
    structural_profile = resolve_dungeon_prompt_profile(
        provider_id="faux",
        model_id="faux_deterministic_v1",
        capabilities=("text", "thinking", "tool_calls"),
        context_window_tokens=16_384,
        output_token_limit=4_096,
        requested_effort=_profile().requested_effort,
    )
    command = PromptDungeonTierAFixedCaseStructuralWorkflow(
        campaign_id=campaign_id,
        case_id=case.case_id,
        variant_id="variant_01",
    )
    rejected_gateway = _DynamicCanaryGateway(overpopulate_exploration=True)
    rejected = DungeonTierAFixedCaseStructuralApplicationService(
        preparation,
        DungeonPromptApplicationService(
            preparation, DungeonPromptService(studio, rejected_gateway)
        ),
    ).execute(command, manifest, structural_profile, profiles)
    assert not rejected.success
    assert rejected.validation_codes == (
        "fixed_case.structural_exploration_count_mismatch",
        "fixed_case.exploration_affordance_missing",
    )
    rejected_run = preparation.get_generation_run(
        campaign_id, rejected.evaluation_run_id
    )
    assert rejected_run.status.value == "failed"

    drifted_case = case.model_copy(update={"setting": f"{case.setting} Drifted."})
    drifted_manifest = manifest.model_copy(
        update={"cases": (drifted_case, *manifest.cases[1:])}
    )
    no_call_gateway = _DynamicCanaryGateway()
    with pytest.raises(ConflictError, match="resume input pins changed"):
        DungeonTierAFixedCaseStructuralApplicationService(
            preparation,
            DungeonPromptApplicationService(
                preparation, DungeonPromptService(studio, no_call_gateway)
            ),
        ).execute(
            command.model_copy(
                update={"resume_from_evaluation_run_id": rejected.evaluation_run_id}
            ),
            drifted_manifest,
            structural_profile,
            profiles,
        )
    assert no_call_gateway.messages == []

    accepted_gateway = _DynamicCanaryGateway()
    resumed = DungeonTierAFixedCaseStructuralApplicationService(
        preparation,
        DungeonPromptApplicationService(
            preparation, DungeonPromptService(studio, accepted_gateway)
        ),
    ).execute(
        command.model_copy(
            update={"resume_from_evaluation_run_id": rejected.evaluation_run_id}
        ),
        manifest,
        structural_profile,
        profiles,
    )
    assert resumed.success
    resumed_run = preparation.get_generation_run(campaign_id, resumed.evaluation_run_id)
    assert resumed_run.input_scope == rejected_run.input_scope
    assert resumed_run.context_payload_sha256 == rejected_run.context_payload_sha256
    assert len(accepted_gateway.messages) == 1


def test_fixed_grounded_case_starts_completes_and_builds_blinded_evidence(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    manifest = load_dungeon_tier_a_eval_manifest()
    case = manifest.cases[1]
    campaign_id = _campaign(db_engine)
    studio, preparation = _studio(db_engine, tmp_path)
    gateway = _DynamicCanaryGateway(structural_room_count=case.room_count)
    profiles = resolve_dungeon_tier_a_canary_profiles(
        provider_id="faux",
        model_id="faux_deterministic_v1",
        capabilities=("text", "thinking", "tool_calls"),
        context_window_tokens=16_384,
        output_token_limit=4_096,
        requested_effort=_profile().requested_effort,
    )
    structural_profile = resolve_dungeon_prompt_profile(
        provider_id="faux",
        model_id="faux_deterministic_v1",
        capabilities=("text", "thinking", "tool_calls"),
        context_window_tokens=16_384,
        output_token_limit=4_096,
        requested_effort=_profile().requested_effort,
    )
    structural = DungeonTierAFixedCaseStructuralApplicationService(
        preparation,
        DungeonPromptApplicationService(
            preparation, DungeonPromptService(studio, gateway)
        ),
    ).execute(
        PromptDungeonTierAFixedCaseStructuralWorkflow(
            campaign_id=campaign_id,
            case_id=case.case_id,
            variant_id="variant_01",
        ),
        manifest,
        structural_profile,
        profiles,
    )

    assert structural.success
    structural_result = structural.structural_attempt.result
    assert structural_result is not None
    artifact_id = structural_result.artifact_id
    current_version_id = structural_result.artifact_version_id
    assert artifact_id is not None
    assert current_version_id is not None
    structural_run = preparation.get_generation_run(
        campaign_id, structural.evaluation_run_id
    )
    assert structural_run.input_scope["variant_id"] == "variant_01"
    structural_measurement = structural_run.validation_report["model_measurement"]
    assert isinstance(structural_measurement, dict)
    assert structural_measurement["first_pass_schema_valid"] is True
    assert structural_measurement["first_pass_semantic_valid"] is True
    assert structural_measurement["input_tokens"] == 200
    assert structural_measurement["output_tokens"] == 350
    assert structural_measurement["repair_count"] == 0
    assert structural_measurement["usage_measured"] is True

    one_step = DungeonStagedEnrichmentCoordinator(
        preparation,
        puzzle=DungeonPuzzlePromptApplicationService(
            preparation, DungeonPuzzlePromptService(studio, gateway)
        ),
        exploration=DungeonExplorationPromptApplicationService(
            preparation, DungeonExplorationPromptService(studio, gateway)
        ),
        feature_interaction=DungeonFeatureInteractionPromptApplicationService(
            preparation, DungeonFeatureInteractionPromptService(studio, gateway)
        ),
        trap=DungeonTrapPromptApplicationService(
            preparation, DungeonTrapPromptService(studio, gateway)
        ),
        objective=DungeonObjectivePromptApplicationService(
            preparation, DungeonObjectivePromptService(studio, gateway)
        ),
        room_narrative=DungeonRoomNarrativePromptApplicationService(
            preparation, DungeonRoomNarrativePromptService(studio, gateway)
        ),
    )
    tasks = DungeonTierAFixedCaseApplicationService(preparation, studio, one_step)
    wrapper_run_ids = [structural.evaluation_run_id]
    for _ in range(6):
        completed = tasks.execute(
            PromptDungeonTierAFixedCaseTaskWorkflow(
                campaign_id=campaign_id,
                artifact_id=artifact_id,
                parent_version_id=current_version_id,
                case_id=case.case_id,
                variant_id="variant_01",
                created_by="dm",
            ),
            manifest,
            profiles,
        )
        assert completed.success
        wrapper_run_ids.append(completed.evaluation_run_id)
        assert completed.step.attempt is not None
        assert completed.step.attempt.result is not None
        next_version_id = completed.step.attempt.result.artifact_version_id
        assert next_version_id is not None
        current_version_id = next_version_id
        if completed.step.plan_after.status == "complete":
            break
    else:
        pytest.fail("fixed grounded case did not complete within six tasks")

    final_version = preparation.get_version(campaign_id, current_version_id)
    final = DungeonStudioSpecification.model_validate_json(
        json.dumps(final_version.specification)
    )
    assert final.creative_continuity is not None
    assert final.creative_continuity.campaign_lore_status == "selected"
    assert (
        tuple(fact.summary for fact in final.creative_continuity.selected_facts)
        == case.authorized_facts
    )
    evidence = DungeonTierAFixedCaseEvidenceService(preparation).build(
        BuildDungeonTierAFixedCaseEvidenceWorkflow(
            campaign_id=campaign_id,
            artifact_id=artifact_id,
            artifact_version_id=current_version_id,
            case_id=case.case_id,
            variant_id="variant_01",
            evaluation_run_ids=tuple(wrapper_run_ids),
        ),
        manifest,
    )

    assert evidence.measurement.final_valid
    assert evidence.measurement.first_pass_valid
    assert evidence.measurement.repair_count == 0
    assert evidence.measurement.input_tokens == 1_400
    assert evidence.measurement.output_tokens == 2_450
    assert evidence.reviewer_input.lore_consistency_required
    reviewer_json = evidence.reviewer_input.model_dump_json()
    assert "variant_assignment" not in reviewer_json
    assert "provider" not in reviewer_json
    assert "model" not in reviewer_json
    assert evidence.final_validation.valid
