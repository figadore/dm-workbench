"""Shared durable V1 prompt application boundary for CLI and web adapters."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, cast

from pydantic import JsonValue

from dm_assistant.modules.modeling import ResolvedModelRunProfile
from dm_assistant.modules.preparation import (
    FinishGenerationRun,
    GenerationContextPin,
    GenerationStatus,
    PreparationService,
    StartGenerationRun,
)
from dm_assistant.observability import bind_log_context, get_logger
from dm_assistant.orchestration.dungeons.contracts import (
    DUNGEON_GENERATION_PROPOSAL_SCHEMA_VERSION,
    DungeonWorkflowResult,
    PromptDungeonWorkflow,
)
from dm_assistant.orchestration.dungeons.prompting import (
    DungeonPromptService,
    DungeonProposalRejectedAfterRepair,
)
from dm_assistant.orchestration.modeling import (
    ModelRunAbstained,
    ModelTransportError,
    StructuredSubmissionBudgetExceeded,
)

logger = get_logger(__name__)


def _failure_code(error: Exception) -> str:
    """Classify known safe prompt failures without exposing model/provider text."""
    if isinstance(error, DungeonProposalRejectedAfterRepair):
        return "dungeon_prompt_rejected_after_repair"
    if isinstance(error, StructuredSubmissionBudgetExceeded):
        return "dungeon_prompt_token_budget_exhausted"
    if isinstance(error, ModelRunAbstained) and (
        error.code == "repair_usage_unavailable"
    ):
        return "dungeon_prompt_repair_usage_unavailable"
    return "dungeon_prompt_failed"


def _failure_report(
    error: Exception,
    code: str,
) -> dict[str, JsonValue]:
    """Build durable body-free failure details for the run inspector."""
    if isinstance(error, DungeonProposalRejectedAfterRepair) and error.failures:
        report: dict[str, JsonValue] = {
            "stage": error.failures[-1].stage,
            "code": code,
            "repair_attempted": True,
            "submission_attempts": [failure.report() for failure in error.failures],
        }
    elif isinstance(error, StructuredSubmissionBudgetExceeded):
        report = {
            "stage": "model_submission",
            "code": code,
            "duration_ms": error.duration_ms,
            "usage": {
                "limit_kind": error.limit_kind,
                "token_limit": error.token_limit,
                "input_tokens": error.input_tokens,
                "output_tokens": error.output_tokens,
            },
        }
    elif isinstance(error, ModelTransportError):
        report = {
            "stage": "model_submission",
            "code": code,
            "transport_error_code": error.code,
        }
    elif isinstance(error, ModelRunAbstained):
        report = {
            "stage": "model_submission",
            "code": code,
            "abstention_code": error.code,
        }
    else:
        report = {"stage": "model_submission", "code": code}
    return report


def _failure_diagnostic_codes(error: Exception) -> list[str]:
    """Return stable codes suitable for ordinary structured logs."""
    if isinstance(error, ModelTransportError):
        return [error.code]
    if not isinstance(error, DungeonProposalRejectedAfterRepair):
        return []
    return [
        diagnostic_code
        for failure in error.failures
        for diagnostic in failure.diagnostics
        if isinstance((diagnostic_code := diagnostic.get("code")), str)
    ]


@dataclass(frozen=True, slots=True)
class DungeonPromptAttemptResult:
    attempt_run_id: uuid.UUID
    result: DungeonWorkflowResult | None
    public_code: str


class DungeonPromptApplicationService:
    """Own attempt lifecycle; surfaces provide only their already-resolved command/profile."""

    def __init__(
        self, preparation: PreparationService, prompts: DungeonPromptService
    ) -> None:
        self._preparation = preparation
        self._prompts = prompts

    def begin_attempt(
        self, command: PromptDungeonWorkflow, *, surface: str
    ) -> uuid.UUID:
        """Persist the caller-owned attempt before model catalog/provider contact."""
        return self._preparation.start_generation_run(
            StartGenerationRun(
                campaign_id=command.campaign_id,
                generation_kind="dungeon_prompt",
                seed=command.seed,
                input_scope={"task_type": "standalone_dungeon", "surface": surface},
                schema_versions={
                    "dungeon_generation_proposal": DUNGEON_GENERATION_PROPOSAL_SCHEMA_VERSION
                },
            )
        ).id

    def execute(
        self,
        command: PromptDungeonWorkflow,
        profile: ResolvedModelRunProfile,
        *,
        surface: str,
        attempt_run_id: uuid.UUID | None = None,
        trusted_context: GenerationContextPin | None = None,
        debug: Callable[[str, dict[str, object]], None] | None = None,
    ) -> DungeonPromptAttemptResult:
        attempt_id = attempt_run_id or self.begin_attempt(command, surface=surface)
        with bind_log_context(attempt_run_id=str(attempt_id)):
            try:
                result = (
                    self._prompts.create(
                        command, profile, stream_run_id=str(attempt_id), debug=debug
                    )
                    if trusted_context is None
                    else self._prompts.create_with_context(
                        command,
                        profile,
                        context=trusted_context,
                        stream_run_id=str(attempt_id),
                        debug=debug,
                    )
                )
            except Exception as error:
                cancelled = isinstance(error, ModelRunAbstained) and error.code in {
                    "model_run_cancelled",
                    "submission_timed_out",
                }
                code = "dungeon_prompt_cancelled" if cancelled else _failure_code(error)
                failure_report = _failure_report(error, code)
                logger.warning(
                    "dungeon prompt attempt stopped",
                    extra={
                        "event_data": {
                            "stage": failure_report["stage"],
                            "code": code,
                            "exception_class": error.__class__.__name__,
                            "diagnostic_codes": _failure_diagnostic_codes(error),
                        }
                    },
                )
                self._finish(
                    command.campaign_id,
                    attempt_id,
                    GenerationStatus.CANCELLED
                    if cancelled
                    else GenerationStatus.FAILED,
                    failure_report,
                )
                return DungeonPromptAttemptResult(attempt_id, None, code)
            status = (
                GenerationStatus.SUCCEEDED
                if result.success
                else GenerationStatus.FAILED
            )
            code = (
                "dungeon_prompt_completed"
                if result.success
                else "dungeon_prompt_failed"
            )
            completion_report: dict[str, JsonValue] = {
                "stage": "completed" if result.success else "deterministic_preflight",
                "code": code,
                "artifact_generation_run_id": str(result.generation_run_id),
                "artifact_version_id": str(result.artifact_version_id)
                if result.artifact_version_id
                else None,
                "model_measurement": (
                    result.model_measurement.model_dump(mode="json")
                    if result.model_measurement is not None
                    else None
                ),
            }
            self._finish(
                command.campaign_id,
                attempt_id,
                status,
                completion_report,
            )
            logger.info(
                "dungeon prompt attempt finished",
                extra={
                    "event_data": {
                        "stage": "completed"
                        if result.success
                        else "deterministic_preflight",
                        "code": code,
                        "artifact_generation_run_id": str(result.generation_run_id),
                    }
                },
            )
            return DungeonPromptAttemptResult(attempt_id, result, code)

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
