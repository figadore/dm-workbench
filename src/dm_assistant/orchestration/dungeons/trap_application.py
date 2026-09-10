"""Durable attempt lifecycle for independently bounded trap enrichment."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, cast

from pydantic import JsonValue

from dm_assistant.modules.modeling import ResolvedModelRunProfile
from dm_assistant.modules.preparation import (
    FinishGenerationRun,
    GenerationStatus,
    PreparationService,
    StartGenerationRun,
    canonical_json_sha256,
)
from dm_assistant.observability import bind_log_context, get_logger
from dm_assistant.orchestration.dungeons.contracts import (
    DUNGEON_TRAP_ENRICHMENT_SCHEMA_VERSION,
    DungeonTrapEnrichmentInput,
    DungeonWorkflowResult,
    PromptDungeonTrapWorkflow,
)
from dm_assistant.orchestration.dungeons.trap_prompting import (
    DungeonTrapPromptService,
    DungeonTrapRejectedAfterRepair,
)
from dm_assistant.orchestration.modeling import (
    ModelRunAbstained,
    StructuredSubmissionBudgetExceeded,
    StructuredSubmissionRepairBudgetExhausted,
)

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class DungeonTrapPromptAttemptResult:
    attempt_run_id: uuid.UUID
    result: DungeonWorkflowResult | None
    public_code: str


class DungeonTrapPromptApplicationService:
    """Persist minimal task metadata while accepted content stays with the artifact."""

    def __init__(
        self,
        preparation: PreparationService,
        prompts: DungeonTrapPromptService,
    ) -> None:
        self._preparation = preparation
        self._prompts = prompts

    def execute(
        self,
        command: PromptDungeonTrapWorkflow,
        profile: ResolvedModelRunProfile,
        *,
        surface: str,
        debug: Callable[[str, dict[str, object]], None] | None = None,
    ) -> DungeonTrapPromptAttemptResult:
        context = self._prompts.prepare_context(command)
        attempt_id = self._begin_attempt(
            command,
            context=context,
            profile=profile,
            surface=surface,
        )
        with bind_log_context(attempt_run_id=str(attempt_id)):
            try:
                result = self._prompts.create(
                    command,
                    profile,
                    context=context,
                    stream_run_id=str(attempt_id),
                    debug=debug,
                )
            except Exception as error:
                code, failure_report = _failure_report(error)
                logger.warning(
                    "dungeon trap prompt attempt stopped",
                    extra={
                        "event_data": {
                            "stage": failure_report["stage"],
                            "code": code,
                            "exception_class": error.__class__.__name__,
                            "diagnostic_codes": _diagnostic_codes(error),
                        }
                    },
                )
                self._finish(
                    command.campaign_id,
                    attempt_id,
                    GenerationStatus.FAILED,
                    failure_report,
                )
                return DungeonTrapPromptAttemptResult(attempt_id, None, code)

            code = (
                "dungeon_trap_prompt_completed"
                if result.success
                else "dungeon_trap_prompt_failed"
            )
            report: dict[str, JsonValue] = {
                "stage": "completed" if result.success else "projection",
                "code": code,
                "artifact_generation_run_id": str(result.generation_run_id),
                "artifact_version_id": (
                    str(result.artifact_version_id)
                    if result.artifact_version_id is not None
                    else None
                ),
            }
            self._finish(
                command.campaign_id,
                attempt_id,
                GenerationStatus.SUCCEEDED
                if result.success
                else GenerationStatus.FAILED,
                report,
            )
            logger.info(
                "dungeon trap prompt attempt finished",
                extra={
                    "event_data": {
                        "stage": report["stage"],
                        "code": code,
                        "artifact_generation_run_id": str(result.generation_run_id),
                    }
                },
            )
            return DungeonTrapPromptAttemptResult(attempt_id, result, code)

    def _begin_attempt(
        self,
        command: PromptDungeonTrapWorkflow,
        *,
        context: DungeonTrapEnrichmentInput,
        profile: ResolvedModelRunProfile,
        surface: str,
    ) -> uuid.UUID:
        context_hash = canonical_json_sha256(context.model_dump(mode="json"))
        return self._preparation.start_generation_run(
            StartGenerationRun(
                campaign_id=command.campaign_id,
                generation_kind="dungeon_trap_prompt",
                input_scope={
                    "task_type": "dungeon_trap_enrichment",
                    "surface": surface,
                    "artifact_id": str(command.artifact_id),
                    "parent_version_id": str(command.parent_version_id),
                    "package_id": context.package_id,
                    "room_id": context.room.room_id,
                    "trap_id": context.trap.trap_id,
                    "context_sha256": context_hash,
                },
                schema_versions={
                    "dungeon_trap_enrichment": (DUNGEON_TRAP_ENRICHMENT_SCHEMA_VERSION)
                },
                model_task_profile_id=profile.task_profile_id,
            )
        ).id

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


def _failure_report(error: Exception) -> tuple[str, dict[str, JsonValue]]:
    if isinstance(error, DungeonTrapRejectedAfterRepair):
        code = "dungeon_trap_prompt_rejected_after_repair"
        return code, {
            "stage": error.failures[-1].stage,
            "code": code,
            "repair_attempted": True,
            "submission_attempts": [item.report() for item in error.failures],
        }
    if isinstance(error, StructuredSubmissionBudgetExceeded):
        code = "dungeon_trap_prompt_token_budget_exhausted"
        return code, {
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
    if isinstance(error, StructuredSubmissionRepairBudgetExhausted):
        code = "dungeon_trap_prompt_repair_budget_exhausted"
        return code, {
            "stage": "model_submission",
            "code": code,
            **error.report(),
        }
    code = "dungeon_trap_prompt_failed"
    stage = "model_submission" if isinstance(error, ModelRunAbstained) else "projection"
    report: dict[str, JsonValue] = {"stage": stage, "code": code}
    if isinstance(error, ModelRunAbstained):
        report["abstention_code"] = error.code
    return code, report


def _diagnostic_codes(error: Exception) -> list[str]:
    if not isinstance(error, DungeonTrapRejectedAfterRepair):
        return []
    return [
        code
        for failure in error.failures
        for diagnostic in failure.diagnostics
        if isinstance((code := diagnostic.get("code")), str)
    ]
