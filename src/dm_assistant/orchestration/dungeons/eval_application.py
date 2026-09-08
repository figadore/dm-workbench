"""Durable, reproducible execution boundary for fixed Tier A eval tasks."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Literal, cast

from pydantic import Field, JsonValue, model_validator

from dm_assistant.errors import ConflictError
from dm_assistant.modules.preparation import (
    FinishGenerationRun,
    GenerationContextPin,
    GenerationStatus,
    PreparationService,
    StartGenerationRun,
    canonical_json_sha256,
)
from dm_assistant.orchestration.dungeons.canary_application import (
    DungeonTierACanaryProfiles,
)
from dm_assistant.orchestration.dungeons.contracts import (
    DungeonStudioSpecification,
    PromptDungeonExplorationWorkflow,
    PromptDungeonPuzzleWorkflow,
    WorkflowModel,
)
from dm_assistant.orchestration.dungeons.evals import (
    DungeonTierAEvalManifest,
    DungeonTierAFixedCaseDispatchPlan,
    build_dungeon_tier_a_fixed_case_dispatch,
)
from dm_assistant.orchestration.dungeons.service import DungeonStudioService
from dm_assistant.orchestration.dungeons.staged_enrichment_coordinator import (
    DungeonStagedEnrichmentCoordinator,
    DungeonStagedEnrichmentStepResult,
    DungeonStagedExplorationPolicy,
    DungeonStagedPuzzlePolicy,
    PromptDungeonStagedEnrichmentWorkflow,
)

_FIXED_CASE_EXECUTION_SCHEMA_VERSION = "1.0.0"
_FIXED_CASE_EXECUTION_KIND = "dungeon_tier_a_eval_task"


class PromptDungeonTierAFixedCaseTaskWorkflow(WorkflowModel):
    """Execute or exactly resume one manifest-derived fixed-case task."""

    campaign_id: uuid.UUID
    artifact_id: uuid.UUID
    parent_version_id: uuid.UUID
    case_id: str = Field(pattern=r"^tier_a_case_[0-9]{2}$")
    created_by: str = Field(min_length=1, max_length=200)
    resume_from_evaluation_run_id: uuid.UUID | None = None


class DungeonTierAFixedCaseExecutionPayload(WorkflowModel):
    """Private persisted replay payload; public run inspection exposes only hashes."""

    execution_version: Literal["dungeon-tier-a-fixed-case-execution-v1"]
    case_id: str = Field(pattern=r"^tier_a_case_[0-9]{2}$")
    case_definition_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact_id: uuid.UUID
    parent_version_id: uuid.UUID
    parent_specification_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    variant_assignment_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    exploration_task_contract_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    task_kind: Literal["puzzle", "exploration"]
    trusted_policy: dict[str, JsonValue]
    trusted_policy_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    resolved_profile: dict[str, JsonValue]
    resolved_profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def verify_replay_hashes(self) -> DungeonTierAFixedCaseExecutionPayload:
        if canonical_json_sha256(self.trusted_policy) != self.trusted_policy_sha256:
            raise ValueError("fixed-case persisted policy hash is stale")
        if canonical_json_sha256(self.resolved_profile) != self.resolved_profile_sha256:
            raise ValueError("fixed-case persisted profile hash is stale")
        return self


@dataclass(frozen=True, slots=True)
class DungeonTierAFixedCaseTaskResult:
    """Body-free result for one fixed-case wrapper and its existing task seam."""

    evaluation_run_id: uuid.UUID
    plan: DungeonTierAFixedCaseDispatchPlan
    step: DungeonStagedEnrichmentStepResult

    @property
    def success(self) -> bool:
        attempt = self.step.attempt
        return bool(
            attempt is not None
            and attempt.result is not None
            and attempt.result.success
            and attempt.result.artifact_version_id is not None
        )


class DungeonTierAFixedCaseApplicationService:
    """Pin, execute, and fail-closed resume one fixed synthetic eval task."""

    def __init__(
        self,
        preparation: PreparationService,
        studio: DungeonStudioService,
        one_step: DungeonStagedEnrichmentCoordinator,
    ) -> None:
        self._preparation = preparation
        self._studio = studio
        self._one_step = one_step

    def execute(
        self,
        command: PromptDungeonTierAFixedCaseTaskWorkflow,
        manifest: DungeonTierAEvalManifest,
        profiles: DungeonTierACanaryProfiles,
    ) -> DungeonTierAFixedCaseTaskResult:
        artifact = self._preparation.get_artifact(
            command.campaign_id, command.artifact_id
        )
        if artifact.current_version_id != command.parent_version_id:
            raise ConflictError("Fixed-case execution requires the current parent.")
        version = self._preparation.get_version(
            command.campaign_id, command.parent_version_id
        )
        if version.artifact_id != command.artifact_id:
            raise ConflictError("Fixed-case parent does not belong to the artifact.")
        specification = DungeonStudioSpecification.model_validate_json(
            json.dumps(version.specification, separators=(",", ":"), sort_keys=True)
        )
        plan = build_dungeon_tier_a_fixed_case_dispatch(
            manifest,
            command.case_id,
            specification,
            puzzle_profile=profiles.puzzle,
            exploration_profile=profiles.exploration,
        )
        context_hash = self._context_hash(command, plan)
        payload = self._execution_payload(command, plan, context_hash)
        scope = self._input_scope(payload)
        context_pin = self._context_pin(payload)

        if command.resume_from_evaluation_run_id is not None:
            self._require_exact_resume(
                command.campaign_id,
                command.resume_from_evaluation_run_id,
                plan=plan,
                input_scope=scope,
                context_payload_sha256=context_pin.payload_sha256,
            )

        evaluation_run_id = self._preparation.start_generation_run(
            StartGenerationRun(
                campaign_id=command.campaign_id,
                generation_kind=_FIXED_CASE_EXECUTION_KIND,
                input_scope=scope,
                context=context_pin,
                schema_versions={
                    "dungeon_tier_a_eval_task": _FIXED_CASE_EXECUTION_SCHEMA_VERSION
                },
                generator_versions={
                    "dungeon_tier_a_fixed_case_execution": (
                        _FIXED_CASE_EXECUTION_SCHEMA_VERSION
                    )
                },
                model_task_profile_id=plan.dispatch.profile.task_profile_id,
            )
        ).id

        try:
            step = self._one_step.execute(
                PromptDungeonStagedEnrichmentWorkflow(
                    campaign_id=command.campaign_id,
                    artifact_id=command.artifact_id,
                    parent_version_id=command.parent_version_id,
                    policy=plan.dispatch.policy,
                    created_by=command.created_by,
                ),
                plan.dispatch.profile,
                surface=command.case_id,
                debug=None,
            )
        except Exception:
            self._finish(
                command.campaign_id,
                evaluation_run_id,
                GenerationStatus.FAILED,
                {
                    "stage": "dispatch",
                    "code": "dungeon_tier_a_fixed_case_dispatch_failed",
                    "task_kind": plan.task_kind,
                },
            )
            raise

        attempt = step.attempt
        success = bool(
            attempt is not None
            and attempt.result is not None
            and attempt.result.success
            and attempt.result.artifact_version_id is not None
        )
        report: dict[str, JsonValue] = {
            "stage": "completed" if success else "task_rejected",
            "code": (
                "dungeon_tier_a_fixed_case_task_completed"
                if success
                else "dungeon_tier_a_fixed_case_task_rejected"
            ),
            "task_kind": plan.task_kind,
            "task_attempt_run_id": (
                str(attempt.attempt_run_id) if attempt is not None else None
            ),
            "task_public_code": step.public_code,
            "artifact_version_id": (
                str(attempt.result.artifact_version_id)
                if success and attempt is not None and attempt.result is not None
                else None
            ),
        }
        self._finish(
            command.campaign_id,
            evaluation_run_id,
            GenerationStatus.SUCCEEDED if success else GenerationStatus.FAILED,
            report,
        )
        return DungeonTierAFixedCaseTaskResult(
            evaluation_run_id=evaluation_run_id,
            plan=plan,
            step=step,
        )

    def _context_hash(
        self,
        command: PromptDungeonTierAFixedCaseTaskWorkflow,
        plan: DungeonTierAFixedCaseDispatchPlan,
    ) -> str:
        policy = plan.dispatch.policy
        if isinstance(policy, DungeonStagedPuzzlePolicy):
            puzzle_context = self._studio.build_puzzle_context(
                PromptDungeonPuzzleWorkflow(
                    campaign_id=command.campaign_id,
                    artifact_id=command.artifact_id,
                    parent_version_id=command.parent_version_id,
                    selection=policy.selection,
                    created_by=command.created_by,
                )
            )
            return canonical_json_sha256(puzzle_context.model_dump(mode="json"))
        if isinstance(policy, DungeonStagedExplorationPolicy):
            exploration_context = self._studio.build_exploration_context(
                PromptDungeonExplorationWorkflow(
                    campaign_id=command.campaign_id,
                    artifact_id=command.artifact_id,
                    parent_version_id=command.parent_version_id,
                    selection=policy.selection,
                    created_by=command.created_by,
                )
            )
            return canonical_json_sha256(exploration_context.model_dump(mode="json"))
        raise ConflictError("Unsupported fixed-case task policy.")

    @staticmethod
    def _execution_payload(
        command: PromptDungeonTierAFixedCaseTaskWorkflow,
        plan: DungeonTierAFixedCaseDispatchPlan,
        context_hash: str,
    ) -> DungeonTierAFixedCaseExecutionPayload:
        return DungeonTierAFixedCaseExecutionPayload(
            execution_version=plan.execution_version,
            case_id=plan.case_id,
            case_definition_sha256=plan.case_definition_sha256,
            artifact_id=command.artifact_id,
            parent_version_id=command.parent_version_id,
            parent_specification_sha256=plan.parent_specification_sha256,
            variant_assignment_sha256=plan.variant_assignment_sha256,
            exploration_task_contract_sha256=(plan.exploration_task_contract_sha256),
            task_kind=plan.task_kind,
            trusted_policy=cast(
                dict[str, JsonValue], plan.dispatch.policy.model_dump(mode="json")
            ),
            trusted_policy_sha256=plan.trusted_policy_sha256,
            resolved_profile=cast(
                dict[str, JsonValue], plan.dispatch.profile.model_dump(mode="json")
            ),
            resolved_profile_sha256=plan.resolved_profile_sha256,
            context_sha256=context_hash,
        )

    @staticmethod
    def _input_scope(
        payload: DungeonTierAFixedCaseExecutionPayload,
    ) -> dict[str, JsonValue]:
        return {
            "task_type": "dungeon_tier_a_fixed_case_task",
            "surface": payload.case_id,
            "case_id": payload.case_id,
            "case_definition_sha256": payload.case_definition_sha256,
            "artifact_id": str(payload.artifact_id),
            "parent_version_id": str(payload.parent_version_id),
            "parent_specification_sha256": payload.parent_specification_sha256,
            "task_kind": payload.task_kind,
            "trusted_policy_sha256": payload.trusted_policy_sha256,
            "resolved_profile_sha256": payload.resolved_profile_sha256,
            "context_sha256": payload.context_sha256,
            "variant_assignment_sha256": payload.variant_assignment_sha256,
            "exploration_task_contract_sha256": (
                payload.exploration_task_contract_sha256
            ),
        }

    @staticmethod
    def _context_pin(
        payload: DungeonTierAFixedCaseExecutionPayload,
    ) -> GenerationContextPin:
        document = cast(dict[str, JsonValue], payload.model_dump(mode="json"))
        return GenerationContextPin(
            envelope_kind="dungeon_tier_a_eval_task",
            payload_version=_FIXED_CASE_EXECUTION_SCHEMA_VERSION,
            envelope={"payload": document},
            payload_sha256=canonical_json_sha256(document),
        )

    def _require_exact_resume(
        self,
        campaign_id: uuid.UUID,
        run_id: uuid.UUID,
        *,
        plan: DungeonTierAFixedCaseDispatchPlan,
        input_scope: dict[str, JsonValue],
        context_payload_sha256: str,
    ) -> None:
        prior = self._preparation.get_generation_run(campaign_id, run_id)
        if prior.generation_kind != _FIXED_CASE_EXECUTION_KIND:
            raise ConflictError("Resume run is not a Tier A fixed-case task.")
        if prior.status is not GenerationStatus.FAILED:
            raise ConflictError("Only a failed fixed-case task can be resumed.")
        if prior.input_scope != input_scope:
            raise ConflictError("Fixed-case resume input pins changed.")
        if prior.context_payload_sha256 != context_payload_sha256:
            raise ConflictError("Fixed-case resume context payload changed.")
        if prior.model_task_profile_id != plan.dispatch.profile.task_profile_id:
            raise ConflictError("Fixed-case resume task profile changed.")
        if prior.schema_versions != {
            "dungeon_tier_a_eval_task": _FIXED_CASE_EXECUTION_SCHEMA_VERSION
        }:
            raise ConflictError("Fixed-case resume schema changed.")
        if prior.generator_versions != {
            "dungeon_tier_a_fixed_case_execution": (
                _FIXED_CASE_EXECUTION_SCHEMA_VERSION
            )
        }:
            raise ConflictError("Fixed-case resume generator changed.")

    def _finish(
        self,
        campaign_id: uuid.UUID,
        run_id: uuid.UUID,
        status: GenerationStatus,
        report: dict[str, JsonValue],
    ) -> None:
        self._preparation.finish_generation_run(
            FinishGenerationRun(
                campaign_id=campaign_id,
                run_id=run_id,
                status=cast(
                    Literal[
                        GenerationStatus.SUCCEEDED,
                        GenerationStatus.FAILED,
                        GenerationStatus.CANCELLED,
                    ],
                    status,
                ),
                validation_report=report,
            )
        )
