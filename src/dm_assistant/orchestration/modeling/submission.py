"""One-shot structured model submissions for narrowly constrained workflows."""

from __future__ import annotations

import json
import math
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, TypeVar, cast

from pydantic import BaseModel, JsonValue, ValidationError

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

_INPUT_TOKEN_ESTIMATE_BYTES_PER_TOKEN = 4
_INPUT_TOKEN_ESTIMATE_OVERHEAD = 512

_CUSTOM_SCHEMA_DIAGNOSTICS: dict[str, tuple[str, str, str]] = {
    "puzzle_clue_location_duplicate": (
        "submission.puzzle_clue_location_duplicate",
        "/clue_path",
        "use each clue location ID at most once",
    ),
    "puzzle_guide_projection_too_long": (
        "submission.puzzle_guide_projection_too_long",
        "/",
        (
            "shorten puzzle prose so each assembled situation, solution, and "
            "adjudication section is at most 2000 characters"
        ),
    ),
}


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


class StructuredSubmissionBudgetExceeded(ModelRunAbstained):
    """Measured provider usage exceeded a structured request's pinned ceiling."""

    def __init__(
        self,
        *,
        limit_kind: Literal["output", "cumulative"],
        token_limit: int,
        input_tokens: int,
        output_tokens: int,
        duration_ms: int,
    ) -> None:
        super().__init__("token budget exhausted before completion")
        self.limit_kind = limit_kind
        self.token_limit = token_limit
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.duration_ms = duration_ms


class StructuredSubmissionRejected(ModelRunAbstained):
    """One schema-invalid call that may consume the workflow's repair budget."""

    def __init__(
        self,
        message: str,
        *,
        record: ModelRunRecord,
        diagnostics: tuple[dict[str, JsonValue], ...],
    ) -> None:
        super().__init__(message)
        self.record = record
        self.diagnostics = diagnostics


class StructuredSubmissionRepairBudgetExhausted(ModelRunAbstained):
    """Body-free initial measurement and exact unavailable-repair arithmetic."""

    def __init__(
        self,
        *,
        profile: ResolvedModelRunProfile,
        record: ModelRunRecord,
        estimated_input_tokens: int,
    ) -> None:
        super().__init__(
            "no budget remains for deterministic diagnostic repair",
            code="repair_budget_exhausted",
        )
        if not record.usage_measured:
            raise ValueError("repair-budget evidence requires measured initial usage")
        assert record.usage_input_tokens is not None
        assert record.usage_output_tokens is not None
        configured_output = profile.override_notes.get("output_token_limit")
        self.workflow_token_budget = profile.token_budget
        self.workflow_time_budget_seconds = profile.time_budget_seconds
        self.initial_input_tokens = record.usage_input_tokens
        self.initial_output_tokens = record.usage_output_tokens
        self.initial_duration_ms = record.duration_ms
        self.charged_initial_seconds = (record.duration_ms + 999) // 1000
        self.request_token_budget = (
            profile.token_budget
            - record.usage_input_tokens
            - record.usage_output_tokens
        )
        self.request_time_budget_seconds = (
            profile.time_budget_seconds - self.charged_initial_seconds
        )
        self.estimated_input_tokens = estimated_input_tokens
        self.output_tokens_available = (
            self.request_token_budget - estimated_input_tokens
        )
        self.configured_output_token_limit = (
            configured_output
            if isinstance(configured_output, int) and configured_output > 0
            else None
        )
        self.effective_output_token_limit = max(
            0,
            min(
                self.configured_output_token_limit,
                self.output_tokens_available,
            )
            if self.configured_output_token_limit is not None
            else self.output_tokens_available,
        )

    def report(self) -> dict[str, JsonValue]:
        """Return safe evidence proving why no repair request was dispatched."""
        blockers: list[JsonValue] = []
        if self.output_tokens_available < 1:
            blockers.append("output_token_reserve")
        if self.request_time_budget_seconds < 1:
            blockers.append("time_reserve")
        return {
            "abstention_code": self.code,
            "submission_attempt": "initial",
            "repair_attempted": False,
            "submission_attempts": [
                {
                    "attempt": "initial",
                    "duration_ms": self.initial_duration_ms,
                    "usage": {
                        "measured": True,
                        "input_tokens": self.initial_input_tokens,
                        "output_tokens": self.initial_output_tokens,
                    },
                }
            ],
            "repair_reserve": {
                "blockers": blockers,
                "token_arithmetic": {
                    "workflow_token_budget": self.workflow_token_budget,
                    "initial_input_tokens": self.initial_input_tokens,
                    "initial_output_tokens": self.initial_output_tokens,
                    "initial_total_tokens": (
                        self.initial_input_tokens + self.initial_output_tokens
                    ),
                    "request_token_budget": self.request_token_budget,
                    "estimated_input_tokens": self.estimated_input_tokens,
                    "output_tokens_available": self.output_tokens_available,
                    "configured_output_token_limit": (
                        self.configured_output_token_limit
                    ),
                    "effective_output_token_limit": (self.effective_output_token_limit),
                },
                "time_arithmetic": {
                    "workflow_time_budget_seconds": (self.workflow_time_budget_seconds),
                    "initial_duration_ms": self.initial_duration_ms,
                    "charged_initial_seconds": self.charged_initial_seconds,
                    "request_time_budget_seconds": (self.request_time_budget_seconds),
                },
            },
        }


class StructuredSubmissionRunner:
    """Accept exactly one valid submit call; never request a duplicate final answer."""

    def __init__(
        self,
        client: GatewayClient,
        *,
        monotonic_clock: Callable[[], float] = time.monotonic,
        is_cancelled: Callable[[], bool] = lambda: False,
        debug: Callable[[str, dict[str, object]], None] | None = None,
    ) -> None:
        self._client = client
        self._monotonic_clock = monotonic_clock
        self._is_cancelled = is_cancelled
        self._debug = debug

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
            raise ModelRunAbstained("model run cancelled", code="model_run_cancelled")
        remaining_seconds = math.ceil(deadline - self._monotonic_clock())
        if remaining_seconds < 1:
            raise ModelRunAbstained(
                "time budget exhausted before submission",
                code="submission_time_budget_exhausted",
            )
        request_profile = profile.model_copy(
            update={"time_budget_seconds": remaining_seconds}
        )
        gateway_schema = tool.gateway_schema()
        if "json_schema_constrained_sampling" in profile.observed_capabilities:
            gateway_schema = gateway_schema.model_copy(
                update={"constrained_sampling": "prefer"}
            )
        if self._debug is None:
            completion = self._client.complete(
                profile=request_profile,
                messages=run_input.messages,
                allowed_tools=(tool.name,),
                tool_schemas=(gateway_schema,),
            )
        else:
            completion = self._client.complete(  # type: ignore[call-arg]
                profile=request_profile,
                messages=run_input.messages,
                allowed_tools=(tool.name,),
                tool_schemas=(gateway_schema,),
                debug=self._debug,
            )
        if self._is_cancelled() or self._monotonic_clock() >= deadline:
            raise ModelRunAbstained(
                "model run cancelled or timed out during submission",
                code="submission_timed_out",
            )
        _enforce_measured_usage(profile, completion, started_at=started_at)
        if len(completion.tool_calls) != 1:
            raise ModelRunAbstained(
                "model must submit exactly one structured call",
                code="structured_call_count_invalid",
            )
        call = completion.tool_calls[0]
        if call.tool_name != tool.name:
            raise ModelRunAbstained(
                "model requested an unauthorized submission tool",
                code="unauthorized_submission_tool",
            )
        try:
            # Tool arguments are JSON objects. This preserves strict scalar rules
            # while allowing JSON enum strings in the nested pure contracts.
            submission = tool.input_schema.model_validate_json(
                json.dumps(call.arguments, separators=(",", ":"), sort_keys=True)
            )
        except ValidationError as error:
            diagnostic_values: list[dict[str, JsonValue]] = []
            for detail in error.errors(include_url=False, include_context=True)[:8]:
                diagnostic_values.append(_schema_diagnostic(detail))
            diagnostics = tuple(diagnostic_values)
            result = ToolResult(
                tool_name=tool.name,
                call_id=call.call_id,
                payload={"accepted": False, "diagnostics": list(diagnostics)},
            )
            if self._debug is not None:
                self._debug("harness_tool_rejected", result.model_dump(mode="json"))
            record = _record(
                started_at=started_at,
                profile=profile,
                run_input=run_input,
                completion=completion,
                call=call,
                result=result,
                output=None,
                status="abstained",
                abstain_reason="model submission failed schema validation",
            )
            raise StructuredSubmissionRejected(
                "model submission failed schema validation",
                record=record,
                diagnostics=diagnostics,
            ) from error
        typed_submission = cast(SubmissionModel, submission)
        if self._debug is not None:
            self._debug("harness_tool_call", call.model_dump(mode="json"))
        result = handler(typed_submission)
        if self._debug is not None:
            self._debug("harness_tool_result", result.model_dump(mode="json"))
        record = _record(
            started_at=started_at,
            profile=profile,
            run_input=run_input,
            completion=completion,
            call=call,
            result=result,
            output=typed_submission,
            status="succeeded",
        )
        return typed_submission, record


def _enforce_measured_usage(
    profile: ResolvedModelRunProfile,
    completion: GatewayCompletion,
    *,
    started_at: datetime,
) -> None:
    """Fail before validation/publication when measured request usage exceeds a pin."""
    if completion.input_tokens is None or completion.output_tokens is None:
        return
    duration_ms = max(0, int((datetime.now(UTC) - started_at).total_seconds() * 1000))
    configured_output = profile.override_notes.get("output_token_limit")
    if isinstance(configured_output, int) and completion.output_tokens > min(
        configured_output, profile.token_budget
    ):
        raise StructuredSubmissionBudgetExceeded(
            limit_kind="output",
            token_limit=min(configured_output, profile.token_budget),
            input_tokens=completion.input_tokens,
            output_tokens=completion.output_tokens,
            duration_ms=duration_ms,
        )
    if completion.input_tokens + completion.output_tokens > profile.token_budget:
        raise StructuredSubmissionBudgetExceeded(
            limit_kind="cumulative",
            token_limit=profile.token_budget,
            input_tokens=completion.input_tokens,
            output_tokens=completion.output_tokens,
            duration_ms=duration_ms,
        )


def reserve_structured_submission_repair(
    profile: ResolvedModelRunProfile,
    record: ModelRunRecord,
    *,
    repair_input: ModelRunInput,
    tool: StructuredSubmissionTool,
) -> ResolvedModelRunProfile:
    """Reserve one complete repair request and expose exact denial arithmetic."""
    if not record.usage_measured:
        raise ModelRunAbstained(
            "model usage was unavailable; repair budget is unknown",
            code="repair_usage_unavailable",
        )
    assert record.usage_input_tokens is not None
    assert record.usage_output_tokens is not None
    remaining_tokens = (
        profile.token_budget - record.usage_input_tokens - record.usage_output_tokens
    )
    remaining_seconds = profile.time_budget_seconds - (
        (record.duration_ms + 999) // 1000
    )
    estimated_input_tokens = _estimated_input_tokens(repair_input, tool)
    remaining_output_tokens = remaining_tokens - estimated_input_tokens
    if remaining_output_tokens < 1 or remaining_seconds < 1:
        raise StructuredSubmissionRepairBudgetExhausted(
            profile=profile,
            record=record,
            estimated_input_tokens=estimated_input_tokens,
        )
    configured_output = profile.override_notes.get("output_token_limit")
    output_limit = (
        min(configured_output, remaining_output_tokens)
        if isinstance(configured_output, int) and configured_output > 0
        else remaining_output_tokens
    )
    return profile.model_copy(
        update={
            "token_budget": remaining_tokens,
            "time_budget_seconds": remaining_seconds,
            "override_notes": {
                **profile.override_notes,
                "output_token_limit": output_limit,
                "estimated_input_tokens": estimated_input_tokens,
            },
        }
    )


def _estimated_input_tokens(
    run_input: ModelRunInput, tool: StructuredSubmissionTool
) -> int:
    request_document = {
        "messages": [message.model_dump(mode="json") for message in run_input.messages],
        "tool": tool.gateway_schema().model_dump(mode="json"),
    }
    byte_size = len(
        json.dumps(request_document, separators=(",", ":"), sort_keys=True).encode(
            "utf-8"
        )
    )
    return (
        byte_size + _INPUT_TOKEN_ESTIMATE_BYTES_PER_TOKEN - 1
    ) // _INPUT_TOKEN_ESTIMATE_BYTES_PER_TOKEN + _INPUT_TOKEN_ESTIMATE_OVERHEAD


def _schema_diagnostic(detail: Mapping[str, object]) -> dict[str, JsonValue]:
    """Reduce one validation detail to allowlisted, body-free schema evidence."""
    error_type = detail.get("type")
    custom = (
        _CUSTOM_SCHEMA_DIAGNOSTICS.get(error_type)
        if isinstance(error_type, str)
        else None
    )
    if custom is not None:
        code, path, repair = custom
    else:
        code = "submission.schema_invalid"
        location = detail.get("loc")
        path = (
            "/" + "/".join(str(item) for item in location)
            if isinstance(location, tuple)
            else "/"
        )
        repair = _schema_repair_hint(detail)
    return {
        "code": code,
        "path": path,
        "affected_refs": [],
        "repair": repair,
    }


def _schema_repair_hint(detail: Mapping[str, object]) -> str:
    """Return only stable schema facts, never model input or validator prose."""
    error_type = detail.get("type")
    if error_type == "missing":
        return "provide this required field"
    if error_type == "extra_forbidden":
        return "remove this field because it is not in the submitted schema"
    if error_type in {"enum", "literal_error"}:
        context = detail.get("ctx")
        expected = context.get("expected") if isinstance(context, dict) else None
        if isinstance(expected, str) and len(expected) <= 500:
            return f"use one of the allowed values: {expected}"
    return "provide a value matching the submitted tool schema"


def _record(
    *,
    started_at: datetime,
    profile: ResolvedModelRunProfile,
    run_input: ModelRunInput,
    completion: GatewayCompletion,
    call: ToolCall,
    result: ToolResult,
    output: BaseModel | None,
    status: Literal["succeeded", "abstained"],
    abstain_reason: str | None = None,
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
        output_payload=output.model_dump(mode="json") if output is not None else None,
        status=status,
        abstain_reason=abstain_reason,
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
