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
    ) -> None:
        super().__init__("token budget exhausted before completion")
        self.limit_kind = limit_kind
        self.token_limit = token_limit
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


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
            raise ModelRunAbstained("model run cancelled")
        remaining_seconds = math.ceil(deadline - self._monotonic_clock())
        if remaining_seconds < 1:
            raise ModelRunAbstained("time budget exhausted before submission")
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
                "model run cancelled or timed out during submission"
            )
        _enforce_measured_usage(profile, completion)
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
    profile: ResolvedModelRunProfile, completion: GatewayCompletion
) -> None:
    """Fail before validation/publication when measured request usage exceeds a pin."""
    if completion.input_tokens is None or completion.output_tokens is None:
        return
    configured_output = profile.override_notes.get("output_token_limit")
    if isinstance(configured_output, int) and completion.output_tokens > min(
        configured_output, profile.token_budget
    ):
        raise StructuredSubmissionBudgetExceeded(
            limit_kind="output",
            token_limit=min(configured_output, profile.token_budget),
            input_tokens=completion.input_tokens,
            output_tokens=completion.output_tokens,
        )
    if completion.input_tokens + completion.output_tokens > profile.token_budget:
        raise StructuredSubmissionBudgetExceeded(
            limit_kind="cumulative",
            token_limit=profile.token_budget,
            input_tokens=completion.input_tokens,
            output_tokens=completion.output_tokens,
        )


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
