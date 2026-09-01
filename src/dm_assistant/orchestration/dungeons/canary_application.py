"""Complete provider-free orchestration boundary for the frozen Tier A canary."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from pydantic import ValidationError

from dm_assistant.errors import ConflictError
from dm_assistant.modules.modeling import ReasoningEffort, ResolvedModelRunProfile
from dm_assistant.modules.preparation import PreparationService
from dm_assistant.orchestration.dungeons.application import (
    DungeonPromptApplicationService,
    DungeonPromptAttemptResult,
)
from dm_assistant.orchestration.dungeons.canary import DUNGEON_TIER_A_CANARY
from dm_assistant.orchestration.dungeons.contracts import (
    DungeonExplorationAffordanceApproval,
    DungeonExplorationContextSelection,
    DungeonFeatureInteractionContextSelection,
    DungeonObjectiveContextSelection,
    DungeonPuzzleClueApproval,
    DungeonPuzzleContextSelection,
    DungeonRoomNarrativeContextSelection,
    DungeonStudioSpecification,
    DungeonTrapContextSelection,
    PromptDungeonWorkflow,
)
from dm_assistant.orchestration.dungeons.exploration_prompting import (
    resolve_dungeon_exploration_prompt_profile,
)
from dm_assistant.orchestration.dungeons.feature_interaction_prompting import (
    resolve_dungeon_feature_interaction_prompt_profile,
)
from dm_assistant.orchestration.dungeons.final_validation import (
    DungeonFinalValidationResult,
    validate_final_staged_dungeon,
)
from dm_assistant.orchestration.dungeons.objective_prompting import (
    resolve_dungeon_objective_prompt_profile,
)
from dm_assistant.orchestration.dungeons.puzzle_prompting import (
    resolve_dungeon_puzzle_prompt_profile,
)
from dm_assistant.orchestration.dungeons.room_narrative_prompting import (
    resolve_dungeon_room_narrative_prompt_profile,
)
from dm_assistant.orchestration.dungeons.staged_enrichment_coordinator import (
    DungeonStagedEnrichmentChainCoordinator,
    DungeonStagedEnrichmentChainResult,
    DungeonStagedEnrichmentDispatch,
    DungeonStagedExplorationPolicy,
    DungeonStagedFeatureInteractionPolicy,
    DungeonStagedObjectivePolicy,
    DungeonStagedPuzzlePolicy,
    DungeonStagedRoomNarrativePolicy,
    DungeonStagedTrapPolicy,
    PromptDungeonStagedEnrichmentChainWorkflow,
)
from dm_assistant.orchestration.dungeons.trap_prompting import (
    resolve_dungeon_trap_prompt_profile,
)
from dm_dungeon.contracts import EncounterSlotIntent, RoomMechanicMarkerKind, RoomRole


@dataclass(frozen=True, slots=True)
class DungeonTierACanaryProfiles:
    """Six independently resolved task profiles for staged Tier A authoring."""

    puzzle: ResolvedModelRunProfile
    exploration: ResolvedModelRunProfile
    feature_interaction: ResolvedModelRunProfile
    trap: ResolvedModelRunProfile
    objective: ResolvedModelRunProfile
    room_narrative: ResolvedModelRunProfile


DungeonTierACanaryValidationCode = Literal[
    "canary.dispatch_policy_invalid",
    "canary.exploration_affordance_missing",
    "canary.structural_branch_count_mismatch",
    "canary.structural_exploration_count_mismatch",
    "canary.structural_feature_missing",
    "canary.structural_gate_count_mismatch",
    "canary.structural_objective_count_mismatch",
    "canary.structural_objective_name_mismatch",
    "canary.structural_puzzle_count_mismatch",
    "canary.structural_room_count_mismatch",
    "canary.structural_secret_loop_count_mismatch",
    "canary.structural_trap_count_mismatch",
]


@dataclass(frozen=True, slots=True)
class DungeonTierACanaryRunResult:
    """Body-free canary outcome; accepted content remains in the DM-only artifact."""

    structural_attempt: DungeonPromptAttemptResult
    chain: DungeonStagedEnrichmentChainResult | None
    final_validation: DungeonFinalValidationResult | None
    current_version_id: uuid.UUID | None
    public_code: str
    validation_codes: tuple[DungeonTierACanaryValidationCode, ...] = ()

    @property
    def success(self) -> bool:
        return self.public_code == "dungeon_tier_a_canary_completed"

    @property
    def task_attempt_run_ids(self) -> tuple[uuid.UUID, ...]:
        if self.chain is None:
            return ()
        return tuple(
            step.attempt.attempt_run_id
            for step in self.chain.steps
            if step.attempt is not None
        )


class DungeonTierACanaryApplicationService:
    """Resume one accepted structural canary through enrichment and final validation.

    This service never approves preparation and has no campaign-canonical dependency.
    Existing task application seams own every child publication and body-free attempt.
    """

    def __init__(
        self,
        preparation: PreparationService,
        structural: DungeonPromptApplicationService,
        chain: DungeonStagedEnrichmentChainCoordinator,
    ) -> None:
        self._preparation = preparation
        self._structural = structural
        self._chain = chain

    def execute(
        self,
        command: PromptDungeonWorkflow,
        structural_profile: ResolvedModelRunProfile,
        staged_profiles: DungeonTierACanaryProfiles,
        *,
        surface: str,
        debug: Callable[[str, dict[str, object]], None] | None = None,
    ) -> DungeonTierACanaryRunResult:
        """Run the frozen structural call, bounded chain, and read-only final gate."""

        if (
            command.prompt != DUNGEON_TIER_A_CANARY.prompt
            or command.seed != DUNGEON_TIER_A_CANARY.seed
            or surface != DUNGEON_TIER_A_CANARY.canary_id
        ):
            raise ConflictError(
                "The staged Tier A canary prompt, seed, or surface changed."
            )

        structural_attempt = self._structural.execute(
            command,
            structural_profile,
            surface=surface,
            debug=debug,
        )
        structural_result = structural_attempt.result
        if (
            structural_result is None
            or not structural_result.success
            or structural_result.artifact_id is None
            or structural_result.artifact_version_id is None
        ):
            return DungeonTierACanaryRunResult(
                structural_attempt=structural_attempt,
                chain=None,
                final_validation=None,
                current_version_id=(
                    structural_result.artifact_version_id
                    if structural_result is not None
                    else None
                ),
                public_code=structural_attempt.public_code,
            )

        specification = self._load_specification(
            command.campaign_id, structural_result.artifact_version_id
        )
        validation_codes = _canary_structural_validation_codes(specification)
        if validation_codes:
            return DungeonTierACanaryRunResult(
                structural_attempt=structural_attempt,
                chain=None,
                final_validation=None,
                current_version_id=structural_result.artifact_version_id,
                public_code="dungeon_tier_a_canary_structural_requirements_failed",
                validation_codes=validation_codes,
            )
        try:
            dispatches = build_dungeon_tier_a_canary_dispatches(
                specification, staged_profiles
            )
        except ConflictError:
            return DungeonTierACanaryRunResult(
                structural_attempt=structural_attempt,
                chain=None,
                final_validation=None,
                current_version_id=structural_result.artifact_version_id,
                public_code="dungeon_tier_a_canary_dispatch_blocked",
                validation_codes=("canary.dispatch_policy_invalid",),
            )
        chain = self._chain.execute(
            PromptDungeonStagedEnrichmentChainWorkflow(
                campaign_id=command.campaign_id,
                artifact_id=structural_result.artifact_id,
                parent_version_id=structural_result.artifact_version_id,
                dispatches=dispatches,
                maximum_tasks=len(dispatches),
                created_by=command.created_by,
            ),
            surface=surface,
            debug=debug,
        )
        if chain.stop_reason != "complete":
            return DungeonTierACanaryRunResult(
                structural_attempt=structural_attempt,
                chain=chain,
                final_validation=None,
                current_version_id=chain.current_version_id,
                public_code=f"dungeon_tier_a_canary_{chain.stop_reason}",
            )

        final_specification = self._load_specification(
            command.campaign_id, chain.current_version_id
        )
        final_validation = validate_final_staged_dungeon(final_specification)
        return DungeonTierACanaryRunResult(
            structural_attempt=structural_attempt,
            chain=chain,
            final_validation=final_validation,
            current_version_id=chain.current_version_id,
            public_code=(
                "dungeon_tier_a_canary_completed"
                if final_validation.valid
                else "dungeon_tier_a_canary_final_validation_failed"
            ),
        )

    def _load_specification(
        self, campaign_id: uuid.UUID, version_id: uuid.UUID
    ) -> DungeonStudioSpecification:
        version = self._preparation.get_version(campaign_id, version_id)
        try:
            return DungeonStudioSpecification.model_validate_json(
                json.dumps(version.specification, separators=(",", ":"), sort_keys=True)
            )
        except ValidationError as error:
            raise ConflictError("Stored dungeon specification is invalid.") from error


def _canary_structural_validation_codes(
    specification: DungeonStudioSpecification,
) -> tuple[DungeonTierACanaryValidationCode, ...]:
    """Check frozen canary semantics before any enrichment provider dispatch."""

    package = specification.package
    topology = package.topology
    puzzle_rooms = tuple(room for room in package.rooms if room.role is RoomRole.PUZZLE)
    exploration_slots = tuple(
        slot
        for slot in package.encounter_slots
        if EncounterSlotIntent.EXPLORATION.value in slot.tags
    )
    features = tuple(
        marker
        for marker in package.room_mechanic_markers
        if marker.kind is RoomMechanicMarkerKind.FEATURE
    )
    traps = tuple(
        marker
        for marker in package.room_mechanic_markers
        if marker.kind is RoomMechanicMarkerKind.TRAP
    )
    objectives = tuple(
        marker
        for marker in package.room_mechanic_markers
        if marker.kind is RoomMechanicMarkerKind.OBJECTIVE
    )
    feature_room_ids = {marker.room_id for marker in features}
    objective_plans = specification.layout_request.mechanics_plan.room_objectives

    codes: list[DungeonTierACanaryValidationCode] = []
    if len(package.rooms) != 5:
        codes.append("canary.structural_room_count_mismatch")
    if len(topology.branches) != 1:
        codes.append("canary.structural_branch_count_mismatch")
    if len(topology.loops) != 1 or len(topology.secret_bypasses) != 1:
        codes.append("canary.structural_secret_loop_count_mismatch")
    if len(topology.gates) != 1:
        codes.append("canary.structural_gate_count_mismatch")
    if len(puzzle_rooms) != 1:
        codes.append("canary.structural_puzzle_count_mismatch")
    if len(exploration_slots) != 1:
        codes.append("canary.structural_exploration_count_mismatch")
    if not features:
        codes.append("canary.structural_feature_missing")
    if len(traps) != 1:
        codes.append("canary.structural_trap_count_mismatch")
    if len(objectives) != 1 or len(objective_plans) != 1:
        codes.append("canary.structural_objective_count_mismatch")
    elif objective_plans[0].name != "Windglass Seed":
        codes.append("canary.structural_objective_name_mismatch")
    if any(slot.room_id not in feature_room_ids for slot in exploration_slots):
        codes.append("canary.exploration_affordance_missing")
    return tuple(codes)


def resolve_dungeon_tier_a_canary_profiles(
    *,
    provider_id: str,
    model_id: str,
    capabilities: tuple[str, ...],
    context_window_tokens: int,
    output_token_limit: int,
    requested_effort: ReasoningEffort,
) -> DungeonTierACanaryProfiles:
    """Resolve each enrichment responsibility through its own pinned task profile."""

    return DungeonTierACanaryProfiles(
        puzzle=resolve_dungeon_puzzle_prompt_profile(
            provider_id=provider_id,
            model_id=model_id,
            capabilities=capabilities,
            context_window_tokens=context_window_tokens,
            output_token_limit=output_token_limit,
            requested_effort=requested_effort,
        ),
        exploration=resolve_dungeon_exploration_prompt_profile(
            provider_id=provider_id,
            model_id=model_id,
            capabilities=capabilities,
            context_window_tokens=context_window_tokens,
            output_token_limit=output_token_limit,
            requested_effort=requested_effort,
        ),
        feature_interaction=resolve_dungeon_feature_interaction_prompt_profile(
            provider_id=provider_id,
            model_id=model_id,
            capabilities=capabilities,
            context_window_tokens=context_window_tokens,
            output_token_limit=output_token_limit,
            requested_effort=requested_effort,
        ),
        trap=resolve_dungeon_trap_prompt_profile(
            provider_id=provider_id,
            model_id=model_id,
            capabilities=capabilities,
            context_window_tokens=context_window_tokens,
            output_token_limit=output_token_limit,
            requested_effort=requested_effort,
        ),
        objective=resolve_dungeon_objective_prompt_profile(
            provider_id=provider_id,
            model_id=model_id,
            capabilities=capabilities,
            context_window_tokens=context_window_tokens,
            output_token_limit=output_token_limit,
            requested_effort=requested_effort,
        ),
        room_narrative=resolve_dungeon_room_narrative_prompt_profile(
            provider_id=provider_id,
            model_id=model_id,
            capabilities=capabilities,
            context_window_tokens=context_window_tokens,
            output_token_limit=output_token_limit,
            requested_effort=requested_effort,
        ),
    )


def build_dungeon_tier_a_canary_dispatches(
    specification: DungeonStudioSpecification,
    profiles: DungeonTierACanaryProfiles,
) -> tuple[DungeonStagedEnrichmentDispatch, ...]:
    """Build exact trusted canary policies from one accepted structural package.

    The frozen canary intentionally requires every staged task kind. Any missing or
    ambiguous exact slot fails before an enrichment provider call.
    """

    guide = specification.dm_guide
    if guide is None:
        raise ConflictError("The Tier A canary structural child has no exact DM guide.")
    presentation = {room.room_id: room.presentation_number for room in guide.rooms}
    package = specification.package

    puzzle_rooms = sorted(
        (room for room in package.rooms if room.role is RoomRole.PUZZLE),
        key=lambda room: (presentation[room.id], room.id),
    )
    exploration_slots = sorted(
        (
            slot
            for slot in package.encounter_slots
            if EncounterSlotIntent.EXPLORATION.value in slot.tags
        ),
        key=lambda slot: (presentation[slot.room_id], slot.id),
    )
    features = sorted(
        (
            marker
            for marker in package.room_mechanic_markers
            if marker.kind is RoomMechanicMarkerKind.FEATURE
        ),
        key=lambda marker: (presentation[marker.room_id], marker.id),
    )
    traps = sorted(
        (
            marker
            for marker in package.room_mechanic_markers
            if marker.kind is RoomMechanicMarkerKind.TRAP
        ),
        key=lambda marker: (presentation[marker.room_id], marker.id),
    )
    objectives = sorted(
        (
            marker
            for marker in package.room_mechanic_markers
            if marker.kind is RoomMechanicMarkerKind.OBJECTIVE
        ),
        key=lambda marker: (presentation[marker.room_id], marker.id),
    )
    if not all((puzzle_rooms, exploration_slots, features, traps, objectives)):
        raise ConflictError(
            "The frozen Tier A canary requires puzzle, exploration, feature, trap, "
            "and objective slots."
        )

    guide_features = {item.marker_id: item for item in guide.features}
    local_features: dict[str, list[str]] = {}
    for marker in features:
        local_features.setdefault(marker.room_id, []).append(marker.id)
    for slot in exploration_slots:
        if not local_features.get(slot.room_id):
            raise ConflictError(
                "The Tier A canary exploration slot requires an exact local feature."
            )

    dispatches: list[DungeonStagedEnrichmentDispatch] = []
    for room in puzzle_rooms:
        dispatches.append(
            DungeonStagedEnrichmentDispatch(
                policy=DungeonStagedPuzzlePolicy(
                    selection=DungeonPuzzleContextSelection(
                        room_id=room.id,
                        clue_locations=(
                            DungeonPuzzleClueApproval(
                                location_id=room.id,
                                purpose=(
                                    "Use player-observable details in the exact puzzle "
                                    "room as the local clue anchor."
                                ),
                            ),
                        ),
                        tone=("abandoned mountain shrine", "wind-worn mystery"),
                        constraints=("Do not author numeric difficulties.",),
                    )
                ),
                profile=profiles.puzzle,
            )
        )
    for slot in exploration_slots:
        affordances = tuple(
            DungeonExplorationAffordanceApproval(
                affordance_id=feature_id,
                use=(
                    f"Use {guide_features[feature_id].name} as the exact room-local "
                    "environmental affordance."
                ),
            )
            for feature_id in local_features[slot.room_id][:6]
        )
        dispatches.append(
            DungeonStagedEnrichmentDispatch(
                policy=DungeonStagedExplorationPolicy(
                    encounter_slot_id=slot.id,
                    selection=DungeonExplorationContextSelection(
                        room_id=slot.room_id,
                        affordances=affordances,
                        pacing_role="rising_tension",
                        stakes=(
                            "A setback creates meaningful pressure without permanently "
                            "closing the route."
                        ),
                        constraints=("Do not author numeric difficulties.",),
                    ),
                ),
                profile=profiles.exploration,
            )
        )
    for marker in features:
        feature = guide_features.get(marker.id)
        if feature is None:
            raise ConflictError("The Tier A canary feature is missing from the guide.")
        dispatches.append(
            DungeonStagedEnrichmentDispatch(
                policy=DungeonStagedFeatureInteractionPolicy(
                    selection=DungeonFeatureInteractionContextSelection(
                        room_id=marker.room_id,
                        feature_id=marker.id,
                        interaction_goal=(
                            f"Make {feature.name} a meaningful room-local interaction."
                        ),
                        stakes=(
                            "A poor choice changes the scene without invalidating the "
                            "dungeon progression."
                        ),
                        constraints=("Do not author numeric difficulties.",),
                    )
                ),
                profile=profiles.feature_interaction,
            )
        )
    for marker in traps:
        dispatches.append(
            DungeonStagedEnrichmentDispatch(
                policy=DungeonStagedTrapPolicy(
                    selection=DungeonTrapContextSelection(
                        room_id=marker.room_id,
                        trap_id=marker.id,
                        stakes=(
                            "The trap imposes a meaningful setback without sealing the "
                            "critical path."
                        ),
                        constraints=("Do not author numeric difficulties.",),
                    )
                ),
                profile=profiles.trap,
            )
        )

    mechanic_ids = tuple(
        [room.id for room in puzzle_rooms]
        + [slot.id for slot in exploration_slots]
        + [marker.id for marker in features]
        + [marker.id for marker in traps]
    )
    if len(mechanic_ids) > 8:
        raise ConflictError(
            "The Tier A canary objective context exceeds its mechanic bound."
        )
    for marker in objectives:
        dispatches.append(
            DungeonStagedEnrichmentDispatch(
                policy=DungeonStagedObjectivePolicy(
                    selection=DungeonObjectiveContextSelection(
                        room_id=marker.room_id,
                        objective_id=marker.id,
                        mechanic_ids=mechanic_ids,
                        stakes=(
                            "The party must make a consequential choice about the named "
                            "Windglass Seed."
                        ),
                        constraints=(
                            "Preserve the named objective and accepted mechanics.",
                        ),
                    )
                ),
                profile=profiles.objective,
            )
        )

    room_ids = tuple(
        room.room_id
        for room in sorted(guide.rooms, key=lambda room: room.presentation_number)
    )
    dispatches.append(
        DungeonStagedEnrichmentDispatch(
            policy=DungeonStagedRoomNarrativePolicy(
                selection=DungeonRoomNarrativeContextSelection(
                    room_ids=room_ids,
                    tone=("abandoned mountain shrine", "wind-worn mystery"),
                    constraints=("Use only player-observable information.",),
                )
            ),
            profile=profiles.room_narrative,
        )
    )
    if len(dispatches) > 32:
        raise ConflictError("The Tier A canary exceeds the staged task ceiling.")
    return tuple(dispatches)
