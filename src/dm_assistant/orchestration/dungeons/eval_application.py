"""Durable, reproducible execution boundary for fixed Tier A eval tasks."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Literal, cast

from pydantic import Field, JsonValue, model_validator

from dm_assistant.errors import ConflictError
from dm_assistant.modules.modeling import ResolvedModelRunProfile
from dm_assistant.modules.preparation import (
    FinishGenerationRun,
    GenerationContextPin,
    GenerationStatus,
    PreparationService,
    StartGenerationRun,
    canonical_json_sha256,
)
from dm_assistant.modules.scope import TaskType, resolve_task_scope
from dm_assistant.orchestration.dungeons.application import (
    DungeonPromptApplicationService,
    DungeonPromptAttemptResult,
)
from dm_assistant.orchestration.dungeons.canary_application import (
    DungeonTierACanaryProfiles,
)
from dm_assistant.orchestration.dungeons.contracts import (
    DungeonModelCallMeasurement,
    DungeonStudioSpecification,
    PromptDungeonExplorationWorkflow,
    PromptDungeonFeatureInteractionWorkflow,
    PromptDungeonObjectiveWorkflow,
    PromptDungeonPuzzleWorkflow,
    PromptDungeonRoomNarrativeWorkflow,
    PromptDungeonTrapWorkflow,
    PromptDungeonWorkflow,
    WorkflowModel,
)
from dm_assistant.orchestration.dungeons.evals import (
    DungeonTierAArtifactEvidence,
    DungeonTierAEvalCase,
    DungeonTierAEvalManifest,
    DungeonTierAFixedCaseDispatchPlan,
    DungeonTierATaskMeasurement,
    build_dungeon_exploration_overage_protocol,
    build_dungeon_tier_a_artifact_evidence,
    build_dungeon_tier_a_fixed_case_context,
    build_dungeon_tier_a_fixed_case_dispatch,
    validate_dungeon_tier_a_fixed_case_structure,
)
from dm_assistant.orchestration.dungeons.service import DungeonStudioService
from dm_assistant.orchestration.dungeons.staged_enrichment_coordinator import (
    DungeonStagedEnrichmentCoordinator,
    DungeonStagedEnrichmentStepResult,
    DungeonStagedExplorationPolicy,
    DungeonStagedFeatureInteractionPolicy,
    DungeonStagedObjectivePolicy,
    DungeonStagedPuzzlePolicy,
    DungeonStagedRoomNarrativePolicy,
    DungeonStagedTrapPolicy,
    PromptDungeonStagedEnrichmentWorkflow,
)

_FIXED_CASE_EXECUTION_SCHEMA_VERSION = "1.0.0"
_FIXED_CASE_EXECUTION_KIND = "dungeon_tier_a_eval_task"
_FIXED_CASE_STRUCTURAL_KIND = "dungeon_tier_a_eval_structure"


class PromptDungeonTierAFixedCaseStructuralWorkflow(WorkflowModel):
    """Start or exactly resume one manifest-derived structural case."""

    campaign_id: uuid.UUID
    case_id: str = Field(pattern=r"^tier_a_case_[0-9]{2}$")
    variant_id: str = Field(pattern=r"^variant_[0-9]{2}$")
    created_by: Literal["dm"] = "dm"
    resume_from_evaluation_run_id: uuid.UUID | None = None


class DungeonTierAFixedCaseStructuralPayload(WorkflowModel):
    """Private structural context/profile plus body-free replay identities."""

    execution_version: Literal["dungeon-tier-a-fixed-case-structure-v1"]
    case_id: str = Field(pattern=r"^tier_a_case_[0-9]{2}$")
    case_definition_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    variant_id: str = Field(pattern=r"^variant_[0-9]{2}$")
    variant_assignment_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    seed: int = Field(ge=0, le=2**63 - 1)
    trusted_context: dict[str, JsonValue]
    trusted_context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    resolved_profile: dict[str, JsonValue]
    resolved_profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def verify_replay_hashes(self) -> DungeonTierAFixedCaseStructuralPayload:
        if canonical_json_sha256(self.trusted_context) != self.trusted_context_sha256:
            raise ValueError("fixed-case structural context hash is stale")
        if canonical_json_sha256(self.resolved_profile) != self.resolved_profile_sha256:
            raise ValueError("fixed-case structural profile hash is stale")
        return self


@dataclass(frozen=True, slots=True)
class DungeonTierAFixedCaseStructuralResult:
    """Body-free structural wrapper outcome and ordinary prompt attempt."""

    evaluation_run_id: uuid.UUID
    structural_attempt: DungeonPromptAttemptResult
    validation_codes: tuple[str, ...]

    @property
    def success(self) -> bool:
        result = self.structural_attempt.result
        return bool(
            result is not None
            and result.success
            and result.artifact_id is not None
            and result.artifact_version_id is not None
            and not self.validation_codes
        )


class DungeonTierAFixedCaseStructuralApplicationService:
    """Build, pin, execute, and validate one frozen structural eval case."""

    def __init__(
        self,
        preparation: PreparationService,
        structural: DungeonPromptApplicationService,
    ) -> None:
        self._preparation = preparation
        self._structural = structural

    def execute(
        self,
        command: PromptDungeonTierAFixedCaseStructuralWorkflow,
        manifest: DungeonTierAEvalManifest,
        structural_profile: ResolvedModelRunProfile,
        staged_profiles: DungeonTierACanaryProfiles,
    ) -> DungeonTierAFixedCaseStructuralResult:
        cases = {case.case_id: case for case in manifest.cases}
        case = cases.get(command.case_id)
        if case is None:
            raise ValueError(f"unknown Tier A fixed case: {command.case_id}")
        if command.variant_id not in {
            variant.variant_id for variant in manifest.variants
        }:
            raise ValueError(f"unknown Tier A fixed variant: {command.variant_id}")
        self._require_matching_assignment(structural_profile, staged_profiles)
        context = build_dungeon_tier_a_fixed_case_context(
            manifest,
            command.case_id,
            preparation_owner_id=command.campaign_id,
        )
        protocol = build_dungeon_exploration_overage_protocol(
            manifest, staged_profiles.exploration
        )
        context_document = cast(dict[str, JsonValue], context.model_dump(mode="json"))
        profile_document = cast(
            dict[str, JsonValue], structural_profile.model_dump(mode="json")
        )
        payload = DungeonTierAFixedCaseStructuralPayload(
            execution_version="dungeon-tier-a-fixed-case-structure-v1",
            case_id=case.case_id,
            case_definition_sha256=canonical_json_sha256(case.model_dump(mode="json")),
            variant_id=command.variant_id,
            variant_assignment_sha256=protocol.variant_assignment_sha256,
            seed=case.seed,
            trusted_context=context_document,
            trusted_context_sha256=canonical_json_sha256(context_document),
            resolved_profile=profile_document,
            resolved_profile_sha256=canonical_json_sha256(profile_document),
        )
        input_scope = self._input_scope(payload)
        context_pin = self._private_context_pin(payload)
        if command.resume_from_evaluation_run_id is not None:
            self._require_exact_resume(
                command.campaign_id,
                command.resume_from_evaluation_run_id,
                input_scope=input_scope,
                context_payload_sha256=context_pin.payload_sha256,
                model_task_profile_id=structural_profile.task_profile_id,
            )
        evaluation_run_id = self._preparation.start_generation_run(
            StartGenerationRun(
                campaign_id=command.campaign_id,
                generation_kind=_FIXED_CASE_STRUCTURAL_KIND,
                seed=case.seed,
                input_scope=input_scope,
                context=context_pin,
                schema_versions={
                    "dungeon_tier_a_eval_structure": (
                        _FIXED_CASE_EXECUTION_SCHEMA_VERSION
                    )
                },
                generator_versions={
                    "dungeon_tier_a_fixed_case_structure": (
                        _FIXED_CASE_EXECUTION_SCHEMA_VERSION
                    )
                },
                model_task_profile_id=structural_profile.task_profile_id,
            )
        ).id
        try:
            structural_attempt, validation_codes = self._execute_structural(
                command,
                case=case,
                context=context,
                profile=structural_profile,
            )
        except Exception:
            self._finish(
                command.campaign_id,
                evaluation_run_id,
                GenerationStatus.FAILED,
                {
                    "stage": "structural_dispatch",
                    "code": "dungeon_tier_a_fixed_case_structure_failed",
                },
            )
            raise
        result = structural_attempt.result
        success = bool(
            result is not None
            and result.success
            and result.artifact_id is not None
            and result.artifact_version_id is not None
            and not validation_codes
        )
        report: dict[str, JsonValue] = {
            "stage": "completed" if success else "structural_rejected",
            "code": (
                "dungeon_tier_a_fixed_case_structure_completed"
                if success
                else "dungeon_tier_a_fixed_case_structure_rejected"
            ),
            "structural_attempt_run_id": str(structural_attempt.attempt_run_id),
            "artifact_id": (str(result.artifact_id) if result is not None else None),
            "artifact_version_id": (
                str(result.artifact_version_id) if result is not None else None
            ),
            "validation_codes": list(validation_codes),
            "model_measurement": (
                result.model_measurement.model_dump(mode="json")
                if result is not None and result.model_measurement is not None
                else None
            ),
        }
        self._finish(
            command.campaign_id,
            evaluation_run_id,
            GenerationStatus.SUCCEEDED if success else GenerationStatus.FAILED,
            report,
        )
        return DungeonTierAFixedCaseStructuralResult(
            evaluation_run_id=evaluation_run_id,
            structural_attempt=structural_attempt,
            validation_codes=validation_codes,
        )

    def _execute_structural(
        self,
        command: PromptDungeonTierAFixedCaseStructuralWorkflow,
        *,
        case: DungeonTierAEvalCase,
        context: GenerationContextPin,
        profile: ResolvedModelRunProfile,
    ) -> tuple[DungeonPromptAttemptResult, tuple[str, ...]]:
        attempt = self._structural.execute(
            PromptDungeonWorkflow(
                campaign_id=command.campaign_id,
                title=case.title,
                prompt=case.prompt,
                seed=case.seed,
                created_by=command.created_by,
                scope=resolve_task_scope(
                    dm_principal_id=command.created_by,
                    campaign_owner_id=command.created_by,
                    task_type=TaskType.STANDALONE_DUNGEON,
                ),
            ),
            profile,
            surface=command.case_id,
            trusted_context=context,
            debug=None,
        )
        result = attempt.result
        if result is None or not result.success or result.artifact_version_id is None:
            return attempt, ()
        version = self._preparation.get_version(
            command.campaign_id, result.artifact_version_id
        )
        specification = DungeonStudioSpecification.model_validate_json(
            json.dumps(version.specification, separators=(",", ":"), sort_keys=True)
        )
        return attempt, validate_dungeon_tier_a_fixed_case_structure(
            case, specification
        )

    @staticmethod
    def _require_matching_assignment(
        structural: ResolvedModelRunProfile,
        staged: DungeonTierACanaryProfiles,
    ) -> None:
        profiles = (
            structural,
            staged.puzzle,
            staged.exploration,
            staged.feature_interaction,
            staged.trap,
            staged.objective,
            staged.room_narrative,
        )
        assignments = {
            (
                profile.provider_id,
                profile.model_id,
                profile.runtime_adapter,
                profile.requested_effort,
            )
            for profile in profiles
        }
        if len(assignments) != 1:
            raise ValueError("Tier A structural and staged profile assignment drift")

    @staticmethod
    def _input_scope(
        payload: DungeonTierAFixedCaseStructuralPayload,
    ) -> dict[str, JsonValue]:
        return {
            "task_type": "dungeon_tier_a_fixed_case_structure",
            "surface": payload.case_id,
            "case_id": payload.case_id,
            "case_definition_sha256": payload.case_definition_sha256,
            "variant_id": payload.variant_id,
            "variant_assignment_sha256": payload.variant_assignment_sha256,
            "seed": payload.seed,
            "trusted_context_sha256": payload.trusted_context_sha256,
            "resolved_profile_sha256": payload.resolved_profile_sha256,
        }

    @staticmethod
    def _private_context_pin(
        payload: DungeonTierAFixedCaseStructuralPayload,
    ) -> GenerationContextPin:
        document = cast(dict[str, JsonValue], payload.model_dump(mode="json"))
        return GenerationContextPin(
            envelope_kind="dungeon_tier_a_eval_structure",
            payload_version=_FIXED_CASE_EXECUTION_SCHEMA_VERSION,
            envelope={"payload": document},
            payload_sha256=canonical_json_sha256(document),
        )

    def _require_exact_resume(
        self,
        campaign_id: uuid.UUID,
        run_id: uuid.UUID,
        *,
        input_scope: dict[str, JsonValue],
        context_payload_sha256: str,
        model_task_profile_id: uuid.UUID,
    ) -> None:
        prior = self._preparation.get_generation_run(campaign_id, run_id)
        if prior.generation_kind != _FIXED_CASE_STRUCTURAL_KIND:
            raise ConflictError("Resume run is not a Tier A fixed-case structure.")
        if prior.status is not GenerationStatus.FAILED:
            raise ConflictError("Only a failed fixed-case structure can be resumed.")
        if prior.input_scope != input_scope:
            raise ConflictError("Fixed-case structural resume input pins changed.")
        if prior.context_payload_sha256 != context_payload_sha256:
            raise ConflictError("Fixed-case structural resume context changed.")
        if prior.model_task_profile_id != model_task_profile_id:
            raise ConflictError("Fixed-case structural resume profile changed.")
        if prior.schema_versions != {
            "dungeon_tier_a_eval_structure": _FIXED_CASE_EXECUTION_SCHEMA_VERSION
        }:
            raise ConflictError("Fixed-case structural resume schema changed.")
        if prior.generator_versions != {
            "dungeon_tier_a_fixed_case_structure": (
                _FIXED_CASE_EXECUTION_SCHEMA_VERSION
            )
        }:
            raise ConflictError("Fixed-case structural resume generator changed.")

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


class BuildDungeonTierAFixedCaseEvidenceWorkflow(WorkflowModel):
    """Collect one exact structural wrapper and its ordered task wrappers."""

    campaign_id: uuid.UUID
    artifact_id: uuid.UUID
    artifact_version_id: uuid.UUID
    case_id: str = Field(pattern=r"^tier_a_case_[0-9]{2}$")
    variant_id: str = Field(pattern=r"^variant_[0-9]{2}$")
    evaluation_run_ids: tuple[uuid.UUID, ...] = Field(min_length=2, max_length=32)


class DungeonTierAFixedCaseEvidenceService:
    """Verify wrapper lineage and build body-free whole-artifact evidence."""

    def __init__(self, preparation: PreparationService) -> None:
        self._preparation = preparation

    def build(
        self,
        command: BuildDungeonTierAFixedCaseEvidenceWorkflow,
        manifest: DungeonTierAEvalManifest,
    ) -> DungeonTierAArtifactEvidence:
        runs = tuple(
            self._preparation.get_generation_run(command.campaign_id, run_id)
            for run_id in command.evaluation_run_ids
        )
        structural = runs[0]
        if structural.generation_kind != _FIXED_CASE_STRUCTURAL_KIND or (
            structural.status
            not in {GenerationStatus.SUCCEEDED, GenerationStatus.FAILED}
        ):
            raise ConflictError(
                "Tier A evidence requires one completed structural wrapper first."
            )
        structural_reclassified = structural.status is GenerationStatus.FAILED
        if structural_reclassified and structural.validation_report.get("code") != (
            "dungeon_tier_a_fixed_case_structure_rejected"
        ):
            raise ConflictError(
                "Tier A evidence cannot reclassify a provider-failed structure."
            )
        self._require_common_scope(
            structural.input_scope,
            command=command,
            require_variant=True,
        )
        assignment_hash = structural.input_scope.get("variant_assignment_sha256")
        if not isinstance(assignment_hash, str):
            raise ConflictError("Tier A structural assignment hash is unavailable.")
        structural_report = structural.validation_report
        current_version_id = self._report_uuid(structural_report, "artifact_version_id")
        if self._report_uuid(structural_report, "artifact_id") != command.artifact_id:
            raise ConflictError("Tier A structural wrapper artifact does not match.")
        measurements = [
            DungeonTierATaskMeasurement(
                task_kind="structural",
                wrapper_run_id=structural.id,
                measurement=self._measurement(structural_report),
            )
        ]

        for run in runs[1:]:
            if (
                run.generation_kind != _FIXED_CASE_EXECUTION_KIND
                or run.status is not GenerationStatus.SUCCEEDED
            ):
                raise ConflictError(
                    "Tier A evidence requires successful fixed-case task wrappers."
                )
            self._require_common_scope(
                run.input_scope,
                command=command,
                require_variant=True,
            )
            if run.input_scope.get("variant_assignment_sha256") != assignment_hash:
                raise ConflictError("Tier A evidence assignment hash drifted.")
            if run.input_scope.get("artifact_id") != str(command.artifact_id):
                raise ConflictError("Tier A task wrapper artifact does not match.")
            if run.input_scope.get("parent_version_id") != str(current_version_id):
                raise ConflictError(
                    "Tier A task wrapper parent chain is not contiguous."
                )
            task_kind = run.input_scope.get("task_kind")
            if task_kind not in {
                "puzzle",
                "exploration",
                "feature_interaction",
                "trap",
                "objective",
                "room_narrative",
            }:
                raise ConflictError("Tier A task wrapper kind is invalid.")
            current_version_id = self._report_uuid(
                run.validation_report, "artifact_version_id"
            )
            measurements.append(
                DungeonTierATaskMeasurement(
                    task_kind=cast(
                        Literal[
                            "puzzle",
                            "exploration",
                            "feature_interaction",
                            "trap",
                            "objective",
                            "room_narrative",
                        ],
                        task_kind,
                    ),
                    wrapper_run_id=run.id,
                    measurement=self._measurement(run.validation_report),
                )
            )
        if current_version_id != command.artifact_version_id:
            raise ConflictError(
                "Tier A evidence final artifact version does not match."
            )
        artifact = self._preparation.get_artifact(
            command.campaign_id, command.artifact_id
        )
        if artifact.current_version_id != command.artifact_version_id:
            raise ConflictError(
                "Tier A evidence requires the current artifact version."
            )
        version = self._preparation.get_version(
            command.campaign_id, command.artifact_version_id
        )
        specification = DungeonStudioSpecification.model_validate_json(
            json.dumps(version.specification, separators=(",", ":"), sort_keys=True)
        )
        return build_dungeon_tier_a_artifact_evidence(
            manifest,
            case_id=command.case_id,
            variant_id=command.variant_id,
            variant_assignment_hash=assignment_hash,
            specification=specification,
            task_measurements=tuple(measurements),
            structural_wrapper_reclassified=structural_reclassified,
        )

    @staticmethod
    def _require_common_scope(
        scope: dict[str, JsonValue],
        *,
        command: BuildDungeonTierAFixedCaseEvidenceWorkflow,
        require_variant: bool,
    ) -> None:
        if scope.get("case_id") != command.case_id:
            raise ConflictError("Tier A evidence case ID does not match.")
        if require_variant and scope.get("variant_id") != command.variant_id:
            raise ConflictError("Tier A evidence variant ID does not match.")

    @staticmethod
    def _measurement(report: dict[str, JsonValue]) -> DungeonModelCallMeasurement:
        value = report.get("model_measurement")
        if not isinstance(value, dict):
            raise ConflictError("Tier A wrapper has no model measurement.")
        try:
            return DungeonModelCallMeasurement.model_validate_json(
                json.dumps(value, separators=(",", ":"), sort_keys=True)
            )
        except ValueError as error:
            raise ConflictError(
                "Tier A wrapper model measurement is invalid."
            ) from error

    @staticmethod
    def _report_uuid(report: dict[str, JsonValue], field: str) -> uuid.UUID:
        value = report.get(field)
        if not isinstance(value, str):
            raise ConflictError(f"Tier A wrapper {field} is unavailable.")
        try:
            return uuid.UUID(value)
        except ValueError as error:
            raise ConflictError(f"Tier A wrapper {field} is invalid.") from error


class PromptDungeonTierAFixedCaseTaskWorkflow(WorkflowModel):
    """Execute or exactly resume one manifest-derived fixed-case task."""

    campaign_id: uuid.UUID
    artifact_id: uuid.UUID
    parent_version_id: uuid.UUID
    case_id: str = Field(pattern=r"^tier_a_case_[0-9]{2}$")
    variant_id: str = Field(pattern=r"^variant_[0-9]{2}$")
    created_by: str = Field(min_length=1, max_length=200)
    resume_from_evaluation_run_id: uuid.UUID | None = None


class DungeonTierAFixedCaseExecutionPayload(WorkflowModel):
    """Private persisted replay payload; public run inspection exposes only hashes."""

    execution_version: Literal["dungeon-tier-a-fixed-case-execution-v1"]
    case_id: str = Field(pattern=r"^tier_a_case_[0-9]{2}$")
    case_definition_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    variant_id: str = Field(pattern=r"^variant_[0-9]{2}$")
    artifact_id: uuid.UUID
    parent_version_id: uuid.UUID
    parent_specification_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    variant_assignment_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    exploration_task_contract_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    task_kind: Literal[
        "puzzle",
        "exploration",
        "feature_interaction",
        "trap",
        "objective",
        "room_narrative",
    ]
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
        if command.variant_id not in {
            variant.variant_id for variant in manifest.variants
        }:
            raise ValueError(f"unknown Tier A fixed variant: {command.variant_id}")
        case = next(
            (case for case in manifest.cases if case.case_id == command.case_id), None
        )
        if case is None:
            raise ValueError(f"unknown Tier A fixed case: {command.case_id}")
        if command.resume_from_evaluation_run_id is not None:
            self._require_resume_case_pin(
                command.campaign_id,
                command.resume_from_evaluation_run_id,
                case_definition_sha256=canonical_json_sha256(
                    case.model_dump(mode="json")
                ),
                variant_id=command.variant_id,
            )
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
            feature_interaction_profile=profiles.feature_interaction,
            trap_profile=profiles.trap,
            objective_profile=profiles.objective,
            room_narrative_profile=profiles.room_narrative,
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
            "model_measurement": (
                attempt.result.model_measurement.model_dump(mode="json")
                if attempt is not None
                and attempt.result is not None
                and attempt.result.model_measurement is not None
                else None
            ),
        }
        if attempt is not None and not success:
            task_run = self._preparation.get_generation_run(
                command.campaign_id, attempt.attempt_run_id
            )
            abstention_code = task_run.validation_report.get("abstention_code")
            if isinstance(abstention_code, str):
                report["abstention_code"] = abstention_code
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
        if isinstance(policy, DungeonStagedFeatureInteractionPolicy):
            feature_context = self._studio.build_feature_interaction_context(
                PromptDungeonFeatureInteractionWorkflow(
                    campaign_id=command.campaign_id,
                    artifact_id=command.artifact_id,
                    parent_version_id=command.parent_version_id,
                    selection=policy.selection,
                    created_by=command.created_by,
                )
            )
            return canonical_json_sha256(feature_context.model_dump(mode="json"))
        if isinstance(policy, DungeonStagedTrapPolicy):
            trap_context = self._studio.build_trap_context(
                PromptDungeonTrapWorkflow(
                    campaign_id=command.campaign_id,
                    artifact_id=command.artifact_id,
                    parent_version_id=command.parent_version_id,
                    selection=policy.selection,
                    created_by=command.created_by,
                )
            )
            return canonical_json_sha256(trap_context.model_dump(mode="json"))
        if isinstance(policy, DungeonStagedObjectivePolicy):
            objective_context = self._studio.build_objective_context(
                PromptDungeonObjectiveWorkflow(
                    campaign_id=command.campaign_id,
                    artifact_id=command.artifact_id,
                    parent_version_id=command.parent_version_id,
                    selection=policy.selection,
                    created_by=command.created_by,
                )
            )
            return canonical_json_sha256(objective_context.model_dump(mode="json"))
        if isinstance(policy, DungeonStagedRoomNarrativePolicy):
            narrative_context = self._studio.build_room_narrative_context(
                PromptDungeonRoomNarrativeWorkflow(
                    campaign_id=command.campaign_id,
                    artifact_id=command.artifact_id,
                    parent_version_id=command.parent_version_id,
                    selection=policy.selection,
                    created_by=command.created_by,
                )
            )
            return canonical_json_sha256(narrative_context.model_dump(mode="json"))
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
            variant_id=command.variant_id,
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
            "variant_id": payload.variant_id,
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

    def _require_resume_case_pin(
        self,
        campaign_id: uuid.UUID,
        run_id: uuid.UUID,
        *,
        case_definition_sha256: str,
        variant_id: str,
    ) -> None:
        prior = self._preparation.get_generation_run(campaign_id, run_id)
        if prior.generation_kind != _FIXED_CASE_EXECUTION_KIND:
            raise ConflictError("Resume run is not a Tier A fixed-case task.")
        if prior.status is not GenerationStatus.FAILED:
            raise ConflictError("Only a failed fixed-case task can be resumed.")
        if (
            prior.input_scope.get("case_definition_sha256") != case_definition_sha256
            or prior.input_scope.get("variant_id") != variant_id
        ):
            raise ConflictError("Fixed-case resume input pins changed.")

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
