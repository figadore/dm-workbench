"""Shared durable V2 prompt application boundary for CLI and web adapters."""

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
)
from dm_assistant.observability import bind_log_context, get_logger
from dm_assistant.orchestration.dungeons.contracts import (
    DungeonWorkflowResult,
    PromptDungeonWorkflow,
)
from dm_assistant.orchestration.dungeons.prompting import DungeonPromptService
from dm_assistant.orchestration.modeling import ModelRunAbstained

logger = get_logger(__name__)

_REPAIR_USAGE_UNAVAILABLE = "model usage was unavailable; repair budget is unknown"


def _failure_code(error: Exception) -> str:
    """Classify known safe prompt failures without exposing model/provider text."""
    if isinstance(error, ModelRunAbstained) and str(error) == _REPAIR_USAGE_UNAVAILABLE:
        return "dungeon_prompt_repair_usage_unavailable"
    return "dungeon_prompt_failed"


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
                generation_kind="dungeon_prompt_v2",
                seed=command.seed,
                input_scope={"task_type": "standalone_dungeon", "surface": surface},
                schema_versions={"dungeon_generation_proposal": "2.1.0"},
            )
        ).id

    def execute(
        self,
        command: PromptDungeonWorkflow,
        profile: ResolvedModelRunProfile,
        *,
        surface: str,
        attempt_run_id: uuid.UUID | None = None,
        debug: Callable[[str, dict[str, object]], None] | None = None,
    ) -> DungeonPromptAttemptResult:
        attempt_id = attempt_run_id or self.begin_attempt(command, surface=surface)
        with bind_log_context(attempt_run_id=str(attempt_id)):
            try:
                result = self._prompts.create_v2(
                    command, profile, stream_run_id=str(attempt_id), debug=debug
                )
            except Exception as error:
                cancelled = isinstance(error, ModelRunAbstained) and (
                    "cancel" in str(error).lower()
                )
                code = "dungeon_prompt_cancelled" if cancelled else _failure_code(error)
                logger.warning(
                    "dungeon prompt attempt stopped",
                    extra={
                        "event_data": {
                            "stage": "model_submission",
                            "code": code,
                            "exception_class": error.__class__.__name__,
                        }
                    },
                )
                self._finish(
                    command.campaign_id,
                    attempt_id,
                    GenerationStatus.CANCELLED
                    if cancelled
                    else GenerationStatus.FAILED,
                    {"stage": "model_submission", "code": code},
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
            self._finish(
                command.campaign_id,
                attempt_id,
                status,
                {
                    "stage": "completed"
                    if result.success
                    else "deterministic_preflight",
                    "code": code,
                    "artifact_generation_run_id": str(result.generation_run_id),
                    "artifact_version_id": str(result.artifact_version_id)
                    if result.artifact_version_id
                    else None,
                },
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
