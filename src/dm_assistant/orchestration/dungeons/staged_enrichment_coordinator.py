"""One-step coordination for independently bounded dungeon enrichment tasks."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import Field

from dm_assistant.errors import ConflictError
from dm_assistant.modules.modeling import ResolvedModelRunProfile
from dm_assistant.modules.preparation import PreparationService
from dm_assistant.orchestration.dungeons.contracts import (
    DungeonExplorationContextSelection,
    DungeonFeatureInteractionContextSelection,
    DungeonObjectiveContextSelection,
    DungeonPuzzleContextSelection,
    DungeonRoomNarrativeContextSelection,
    DungeonStudioSpecification,
    DungeonTrapContextSelection,
    PromptDungeonExplorationWorkflow,
    PromptDungeonFeatureInteractionWorkflow,
    PromptDungeonObjectiveWorkflow,
    PromptDungeonPuzzleWorkflow,
    PromptDungeonRoomNarrativeWorkflow,
    PromptDungeonTrapWorkflow,
    WorkflowModel,
)
from dm_assistant.orchestration.dungeons.exploration_application import (
    DungeonExplorationPromptApplicationService,
    DungeonExplorationPromptAttemptResult,
)
from dm_assistant.orchestration.dungeons.feature_interaction_application import (
    DungeonFeatureInteractionPromptApplicationService,
    DungeonFeatureInteractionPromptAttemptResult,
)
from dm_assistant.orchestration.dungeons.objective_application import (
    DungeonObjectivePromptApplicationService,
    DungeonObjectivePromptAttemptResult,
)
from dm_assistant.orchestration.dungeons.puzzle_application import (
    DungeonPuzzlePromptApplicationService,
    DungeonPuzzlePromptAttemptResult,
)
from dm_assistant.orchestration.dungeons.room_narrative_application import (
    DungeonRoomNarrativePromptApplicationService,
    DungeonRoomNarrativePromptAttemptResult,
)
from dm_assistant.orchestration.dungeons.staged_enrichment import (
    DungeonStagedEnrichmentPlan,
    DungeonStagedEnrichmentTask,
    plan_dungeon_staged_enrichment,
)
from dm_assistant.orchestration.dungeons.trap_application import (
    DungeonTrapPromptApplicationService,
    DungeonTrapPromptAttemptResult,
)


class DungeonStagedPuzzlePolicy(WorkflowModel):
    """Trusted puzzle-only IDs and authoring policy for the selected task."""

    kind: Literal["puzzle"] = "puzzle"
    selection: DungeonPuzzleContextSelection


class DungeonStagedExplorationPolicy(WorkflowModel):
    """Trusted exploration-only IDs and authoring policy for the selected task."""

    kind: Literal["exploration"] = "exploration"
    selection: DungeonExplorationContextSelection


class DungeonStagedFeatureInteractionPolicy(WorkflowModel):
    """Trusted feature-only IDs and authoring policy for the selected task."""

    kind: Literal["feature_interaction"] = "feature_interaction"
    selection: DungeonFeatureInteractionContextSelection


class DungeonStagedTrapPolicy(WorkflowModel):
    """Trusted trap-only IDs and authoring policy for the selected task."""

    kind: Literal["trap"] = "trap"
    selection: DungeonTrapContextSelection


class DungeonStagedObjectivePolicy(WorkflowModel):
    """Trusted objective-only IDs and authoring policy for the selected task."""

    kind: Literal["objective"] = "objective"
    selection: DungeonObjectiveContextSelection


class DungeonStagedRoomNarrativePolicy(WorkflowModel):
    """Trusted room-set and style policy for the selected narrative task."""

    kind: Literal["room_narrative"] = "room_narrative"
    selection: DungeonRoomNarrativeContextSelection


DungeonStagedEnrichmentPolicy = Annotated[
    DungeonStagedPuzzlePolicy
    | DungeonStagedExplorationPolicy
    | DungeonStagedFeatureInteractionPolicy
    | DungeonStagedTrapPolicy
    | DungeonStagedObjectivePolicy
    | DungeonStagedRoomNarrativePolicy,
    Field(discriminator="kind"),
]


class PromptDungeonStagedEnrichmentWorkflow(WorkflowModel):
    """Request at most one planned enrichment call over one current parent."""

    campaign_id: uuid.UUID
    artifact_id: uuid.UUID
    parent_version_id: uuid.UUID
    policy: DungeonStagedEnrichmentPolicy
    created_by: str = Field(min_length=1, max_length=200)


DungeonStagedEnrichmentAttemptResult = (
    DungeonPuzzlePromptAttemptResult
    | DungeonExplorationPromptAttemptResult
    | DungeonFeatureInteractionPromptAttemptResult
    | DungeonTrapPromptAttemptResult
    | DungeonObjectivePromptAttemptResult
    | DungeonRoomNarrativePromptAttemptResult
)


@dataclass(frozen=True, slots=True)
class DungeonStagedEnrichmentStepResult:
    """One planner decision and, at most, one existing task-seam attempt."""

    plan_before: DungeonStagedEnrichmentPlan
    attempt: DungeonStagedEnrichmentAttemptResult | None
    plan_after: DungeonStagedEnrichmentPlan
    public_code: str


class DungeonStagedEnrichmentCoordinator:
    """Plan and dispatch exactly one enrichment responsibility without repetition."""

    def __init__(
        self,
        preparation: PreparationService,
        *,
        puzzle: DungeonPuzzlePromptApplicationService | None = None,
        exploration: DungeonExplorationPromptApplicationService | None = None,
        feature_interaction: DungeonFeatureInteractionPromptApplicationService
        | None = None,
        trap: DungeonTrapPromptApplicationService | None = None,
        objective: DungeonObjectivePromptApplicationService | None = None,
        room_narrative: DungeonRoomNarrativePromptApplicationService | None = None,
    ) -> None:
        self._preparation = preparation
        self._puzzle = puzzle
        self._exploration = exploration
        self._feature_interaction = feature_interaction
        self._trap = trap
        self._objective = objective
        self._room_narrative = room_narrative

    def execute(
        self,
        command: PromptDungeonStagedEnrichmentWorkflow,
        profile: ResolvedModelRunProfile,
        *,
        surface: str,
        debug: Callable[[str, dict[str, object]], None] | None = None,
    ) -> DungeonStagedEnrichmentStepResult:
        """Plan the current parent and invoke no more than its one selected seam."""

        plan_before = self._plan_current_parent(command)
        if plan_before.status != "ready":
            return DungeonStagedEnrichmentStepResult(
                plan_before=plan_before,
                attempt=None,
                plan_after=plan_before,
                public_code=f"dungeon_staged_enrichment_{plan_before.status}",
            )

        task = plan_before.next_task
        if task is None:  # Guard the validated plan invariant at this imperative seam.
            raise ConflictError("The staged enrichment plan has no dispatchable task.")
        attempt = self._dispatch(
            command,
            task=task,
            profile=profile,
            surface=surface,
            debug=debug,
        )
        result = attempt.result
        if result is None or not result.success or result.artifact_version_id is None:
            return DungeonStagedEnrichmentStepResult(
                plan_before=plan_before,
                attempt=attempt,
                plan_after=plan_before,
                public_code=attempt.public_code,
            )

        plan_after = self._plan_version(
            campaign_id=command.campaign_id,
            artifact_id=command.artifact_id,
            version_id=result.artifact_version_id,
            require_current=True,
        )
        return DungeonStagedEnrichmentStepResult(
            plan_before=plan_before,
            attempt=attempt,
            plan_after=plan_after,
            public_code=attempt.public_code,
        )

    def _plan_current_parent(
        self, command: PromptDungeonStagedEnrichmentWorkflow
    ) -> DungeonStagedEnrichmentPlan:
        return self._plan_version(
            campaign_id=command.campaign_id,
            artifact_id=command.artifact_id,
            version_id=command.parent_version_id,
            require_current=True,
        )

    def _plan_version(
        self,
        *,
        campaign_id: uuid.UUID,
        artifact_id: uuid.UUID,
        version_id: uuid.UUID,
        require_current: bool,
    ) -> DungeonStagedEnrichmentPlan:
        version = self._preparation.get_version(campaign_id, version_id)
        if version.artifact_id != artifact_id:
            raise ConflictError("The staged parent does not belong to the artifact.")
        if require_current:
            artifact = self._preparation.get_artifact(campaign_id, artifact_id)
            if artifact.current_version_id != version_id:
                raise ConflictError("Staged enrichment requires the current version.")
        specification = DungeonStudioSpecification.model_validate(version.specification)
        return plan_dungeon_staged_enrichment(specification)

    def _dispatch(
        self,
        command: PromptDungeonStagedEnrichmentWorkflow,
        *,
        task: DungeonStagedEnrichmentTask,
        profile: ResolvedModelRunProfile,
        surface: str,
        debug: Callable[[str, dict[str, object]], None] | None,
    ) -> DungeonStagedEnrichmentAttemptResult:
        policy = command.policy

        if isinstance(policy, DungeonStagedPuzzlePolicy):
            self._require_exact_policy(task, policy.kind, policy.selection.room_id)
            puzzle_service = self._require_service(self._puzzle, policy.kind)
            return puzzle_service.execute(
                PromptDungeonPuzzleWorkflow(
                    campaign_id=command.campaign_id,
                    artifact_id=command.artifact_id,
                    parent_version_id=command.parent_version_id,
                    selection=policy.selection,
                    created_by=command.created_by,
                ),
                profile,
                surface=surface,
                debug=debug,
            )
        if isinstance(policy, DungeonStagedExplorationPolicy):
            self._require_exact_policy(task, policy.kind, policy.selection.room_id)
            exploration_service = self._require_service(self._exploration, policy.kind)
            return exploration_service.execute(
                PromptDungeonExplorationWorkflow(
                    campaign_id=command.campaign_id,
                    artifact_id=command.artifact_id,
                    parent_version_id=command.parent_version_id,
                    selection=policy.selection,
                    created_by=command.created_by,
                ),
                profile,
                surface=surface,
                debug=debug,
            )
        if isinstance(policy, DungeonStagedFeatureInteractionPolicy):
            self._require_exact_policy(
                task,
                policy.kind,
                policy.selection.room_id,
                policy.selection.feature_id,
            )
            feature_service = self._require_service(
                self._feature_interaction, policy.kind
            )
            return feature_service.execute(
                PromptDungeonFeatureInteractionWorkflow(
                    campaign_id=command.campaign_id,
                    artifact_id=command.artifact_id,
                    parent_version_id=command.parent_version_id,
                    selection=policy.selection,
                    created_by=command.created_by,
                ),
                profile,
                surface=surface,
                debug=debug,
            )
        if isinstance(policy, DungeonStagedTrapPolicy):
            self._require_exact_policy(
                task,
                policy.kind,
                policy.selection.room_id,
                policy.selection.trap_id,
            )
            trap_service = self._require_service(self._trap, policy.kind)
            return trap_service.execute(
                PromptDungeonTrapWorkflow(
                    campaign_id=command.campaign_id,
                    artifact_id=command.artifact_id,
                    parent_version_id=command.parent_version_id,
                    selection=policy.selection,
                    created_by=command.created_by,
                ),
                profile,
                surface=surface,
                debug=debug,
            )
        if isinstance(policy, DungeonStagedObjectivePolicy):
            self._require_exact_policy(
                task,
                policy.kind,
                policy.selection.room_id,
                policy.selection.objective_id,
            )
            objective_service = self._require_service(self._objective, policy.kind)
            return objective_service.execute(
                PromptDungeonObjectiveWorkflow(
                    campaign_id=command.campaign_id,
                    artifact_id=command.artifact_id,
                    parent_version_id=command.parent_version_id,
                    selection=policy.selection,
                    created_by=command.created_by,
                ),
                profile,
                surface=surface,
                debug=debug,
            )

        self._require_exact_narrative_policy(
            task, policy.kind, policy.selection.room_ids
        )
        narrative_service = self._require_service(self._room_narrative, policy.kind)
        return narrative_service.execute(
            PromptDungeonRoomNarrativeWorkflow(
                campaign_id=command.campaign_id,
                artifact_id=command.artifact_id,
                parent_version_id=command.parent_version_id,
                selection=policy.selection,
                created_by=command.created_by,
            ),
            profile,
            surface=surface,
            debug=debug,
        )

    @staticmethod
    def _require_exact_policy(
        task: DungeonStagedEnrichmentTask,
        policy_kind: str,
        room_id: str,
        target_id: str | None = None,
    ) -> None:
        if policy_kind != task.kind:
            raise ConflictError(
                "The trusted task policy does not match the staged task."
            )
        expected_target = target_id if target_id is not None else room_id
        if task.room_ids != (room_id,) or task.target_ids != (expected_target,):
            raise ConflictError(
                "The trusted task policy does not match the staged exact target."
            )

    @staticmethod
    def _require_exact_narrative_policy(
        task: DungeonStagedEnrichmentTask,
        policy_kind: str,
        room_ids: tuple[str, ...],
    ) -> None:
        if (
            policy_kind != task.kind
            or task.room_ids != room_ids
            or task.target_ids != room_ids
        ):
            raise ConflictError(
                "The trusted room policy does not match the staged room set."
            )

    @staticmethod
    def _require_service[Service](service: Service | None, kind: str) -> Service:
        if service is None:
            raise ConflictError(f"The {kind} staged task service is unavailable.")
        return service
