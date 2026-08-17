"""One-shot structured model submissions for narrowly constrained workflows."""

from __future__ import annotations

import json
import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TypeVar, cast

from pydantic import BaseModel, ValidationError

from dm_assistant.modules.modeling import (
    ModelRunInput,
    ModelRunRecord,
    ResolvedModelRunProfile,
    ToolCall,
    ToolInvocationRecord,
    ToolResult,
)
from dm_assistant.orchestration.modeling.service import (
    GatewayClient,
    GatewayCompletion,
    GatewayToolSchema,
    ModelRunAbstained,
)

SubmissionModel = TypeVar("SubmissionModel", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class StructuredSubmissionTool:
    """The single server-owned tool a one-shot submission may invoke."""

    name: str
    description: str
    input_schema: type[BaseModel]

    def gateway_schema(self) -> GatewayToolSchema:
        return GatewayToolSchema(
            name=self.name,
            description=self.description,
            parameters=json.loads(json.dumps(self.input_schema.model_json_schema())),
        )


class StructuredSubmissionRunner:
    """Accept exactly one valid submit call; never request a duplicate final answer."""

    def __init__(
        self,
        client: GatewayClient,
        *,
        monotonic_clock: Callable[[], float] = time.monotonic,
        is_cancelled: Callable[[], bool] = lambda: False,
    ) -> None:
        self._client = client
        self._monotonic_clock = monotonic_clock
        self._is_cancelled = is_cancelled

    def run(
        self,
        *,
        profile: ResolvedModelRunProfile,
        run_input: ModelRunInput,
        tool: StructuredSubmissionTool,
        handler: Callable[[SubmissionModel], ToolResult],
        deadline_monotonic: float | None = None,
    ) -> tuple[SubmissionModel, ModelRunRecord]:
        """Make one provider request and validate/record its one submission call."""
        if profile.allowed_tools != (tool.name,) or profile.tool_budget != 1:
            raise ValueError("structured submission requires exactly one allowed tool")
        if profile.turn_budget != 1:
            raise ValueError("structured submission requires a one-turn profile")
        started_at = datetime.now(UTC)
        deadline = deadline_monotonic or (
            self._monotonic_clock() + profile.time_budget_seconds
        )
        if self._is_cancelled():
            raise ModelRunAbstained("model run cancelled")
        remaining_seconds = math.ceil(deadline - self._monotonic_clock())
        if remaining_seconds < 1:
            raise ModelRunAbstained("time budget exhausted before submission")
        completion = self._client.complete(
            profile=profile.model_copy(
                update={"time_budget_seconds": remaining_seconds}
            ),
            messages=run_input.messages,
            allowed_tools=(tool.name,),
            tool_schemas=(tool.gateway_schema(),),
        )
        if self._is_cancelled() or self._monotonic_clock() >= deadline:
            raise ModelRunAbstained(
                "model run cancelled or timed out during submission"
            )
        if len(completion.tool_calls) != 1:
            raise ModelRunAbstained("model must submit exactly one structured call")
        call = completion.tool_calls[0]
        if call.tool_name != tool.name:
            raise ModelRunAbstained("model requested an unauthorized submission tool")
        try:
            # Tool arguments are JSON objects. This preserves strict scalar rules
            # while allowing JSON enum strings in the nested pure contracts.
            submission = tool.input_schema.model_validate_json(
                json.dumps(call.arguments, separators=(",", ":"), sort_keys=True)
            )
        except ValidationError as error:
            raise ModelRunAbstained(
                "model submission failed schema validation"
            ) from error
        typed_submission = cast(SubmissionModel, submission)
        result = handler(typed_submission)
        record = _record(
            started_at=started_at,
            profile=profile,
            run_input=run_input,
            completion=completion,
            call=call,
            result=result,
            output=typed_submission,
        )
        return typed_submission, record


def _record(
    *,
    started_at: datetime,
    profile: ResolvedModelRunProfile,
    run_input: ModelRunInput,
    completion: GatewayCompletion,
    call: ToolCall,
    result: ToolResult,
    output: BaseModel,
) -> ModelRunRecord:
    completed_at = datetime.now(UTC)
    measured = (
        completion.input_tokens is not None and completion.output_tokens is not None
    )
    return ModelRunRecord(
        started_at=started_at.isoformat(),
        completed_at=completed_at.isoformat(),
        duration_ms=max(0, int((completed_at - started_at).total_seconds() * 1000)),
        turn_count=1,
        resolved_profile=profile,
        run_input=run_input,
        output_payload=output.model_dump(mode="json"),
        status="succeeded",
        usage_input_tokens=completion.input_tokens,
        usage_output_tokens=completion.output_tokens,
        usage_measured=measured,
        tool_invocations=(
            ToolInvocationRecord(
                tool_name=call.tool_name,
                call_id=call.call_id,
                arguments=call.arguments,
                result=result,
            ),
        ),
    )
