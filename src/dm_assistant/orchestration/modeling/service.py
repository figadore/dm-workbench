"""Bounded model-task orchestration with server-owned tool execution."""

from __future__ import annotations

import json
import math
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol, TypeVar, cast

from pydantic import BaseModel, ConfigDict, JsonValue, ValidationError

from dm_assistant.modules.modeling import (
    ModelRunInput,
    ModelRunRecord,
    PromptMessage,
    ResolvedModelRunProfile,
    ToolCall,
    ToolInvocationRecord,
    ToolResult,
)
from dm_assistant.observability import get_logger

OutputModel = TypeVar("OutputModel", bound=BaseModel)
logger = get_logger(__name__)


class GatewayCompletion(BaseModel):
    """One bounded gateway response turn."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    content: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    input_tokens: int | None = None
    output_tokens: int | None = None


class GatewayToolSchema(BaseModel):
    """One model-visible schema generated from a server-owned tool contract."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    name: str
    description: str
    parameters: dict[str, JsonValue]
    constrained_sampling: Literal["prefer", "require"] | None = None


class GatewayClient(Protocol):
    """Minimal gateway client used by the bounded prompt loop."""

    def complete(
        self,
        *,
        profile: ResolvedModelRunProfile,
        messages: tuple[PromptMessage, ...],
        allowed_tools: tuple[str, ...],
        tool_schemas: tuple[GatewayToolSchema, ...],
    ) -> GatewayCompletion: ...


@dataclass(frozen=True, slots=True)
class ServerTool:
    """Server-owned tool schema plus deterministic application handler."""

    name: str
    description: str
    input_schema: type[BaseModel]
    handler: Callable[[BaseModel], ToolResult]

    def gateway_schema(self) -> GatewayToolSchema:
        """Expose only the versioned input JSON Schema to the gateway."""

        document = json.loads(json.dumps(self.input_schema.model_json_schema()))
        return GatewayToolSchema.model_validate(
            {
                "name": self.name,
                "description": self.description,
                "parameters": document,
            }
        )


class ModelRunAbstained(RuntimeError):
    """Raised when the task profile requires abstention instead of an answer."""


class ModelTaskRunner:
    """Run a bounded model loop while enforcing profile, citation, and tool policy."""

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
        output_schema: type[OutputModel],
        tools: Mapping[str, ServerTool],
        deadline_monotonic: float | None = None,
    ) -> tuple[OutputModel, ModelRunRecord]:
        started_at = datetime.now(UTC)
        messages = tuple(run_input.messages)
        tool_invocations: list[ToolInvocationRecord] = []
        total_input_tokens: int | None = 0
        total_output_tokens: int | None = 0
        turns = 0
        deadline = deadline_monotonic or (
            self._monotonic_clock() + profile.time_budget_seconds
        )

        while True:
            if self._is_cancelled():
                raise ModelRunAbstained("model run cancelled")
            remaining_seconds = math.ceil(deadline - self._monotonic_clock())
            if remaining_seconds < 1:
                raise ModelRunAbstained("time budget exhausted before a final answer")
            if turns >= profile.turn_budget:
                raise ModelRunAbstained("turn budget exhausted before a final answer")
            unknown_tools = set(profile.allowed_tools) - set(tools)
            if unknown_tools:
                raise ValueError(
                    "task profile allows unregistered tools: "
                    + ", ".join(sorted(unknown_tools))
                )
            request_profile = profile.model_copy(
                update={"time_budget_seconds": remaining_seconds}
            )
            completion = self._client.complete(
                profile=request_profile,
                messages=messages,
                allowed_tools=profile.allowed_tools,
                tool_schemas=tuple(
                    tools[name].gateway_schema() for name in profile.allowed_tools
                ),
            )
            turns += 1
            if completion.input_tokens is None or completion.output_tokens is None:
                total_input_tokens = None
                total_output_tokens = None
            elif total_input_tokens is not None and total_output_tokens is not None:
                total_input_tokens += completion.input_tokens
                total_output_tokens += completion.output_tokens
                _check_token_budget(
                    profile.token_budget, total_input_tokens, total_output_tokens
                )
            if self._monotonic_clock() >= deadline:
                raise ModelRunAbstained("time budget exhausted before a final answer")

            if completion.tool_calls:
                call_ids = tuple(call.call_id for call in completion.tool_calls)
                if len(set(call_ids)) != len(call_ids) or any(
                    call_id in {item.call_id for item in tool_invocations}
                    for call_id in call_ids
                ):
                    raise ModelRunAbstained("duplicate model tool call ID")
                if (
                    len(tool_invocations) + len(completion.tool_calls)
                    > profile.tool_budget
                ):
                    logger.warning(
                        "model tool calls exceeded the bounded task budget",
                        extra={
                            "event_data": {
                                "stage": "model_tool_policy",
                                "tool_budget": profile.tool_budget,
                                "prior_tool_count": len(tool_invocations),
                                "requested_tool_count": len(completion.tool_calls),
                                "requested_tool_names": [
                                    call.tool_name for call in completion.tool_calls
                                ],
                            }
                        },
                    )
                    raise ModelRunAbstained("tool budget exhausted before completion")
                messages = messages + (
                    PromptMessage(
                        role="assistant",
                        content=completion.content or "",
                        tool_calls=completion.tool_calls,
                    ),
                )
                for call in completion.tool_calls:
                    if call.tool_name not in profile.allowed_tools:
                        raise ModelRunAbstained("model requested an unauthorized tool")
                    tool = tools.get(call.tool_name)
                    if tool is None:
                        raise ModelRunAbstained("model requested an unavailable tool")
                    result = self._execute_tool(
                        profile=profile,
                        tool=tool,
                        call=call,
                        authorized_citations=run_input.authorized_citation_ids,
                    )
                    tool_invocations.append(
                        ToolInvocationRecord(
                            tool_name=call.tool_name,
                            call_id=call.call_id,
                            arguments=call.arguments,
                            result=result,
                        )
                    )
                    messages = messages + (
                        PromptMessage(
                            role="tool_result",
                            content=json.dumps(
                                result.model_dump(mode="json"),
                                separators=(",", ":"),
                                sort_keys=True,
                            ),
                            tool_call_id=call.call_id,
                            tool_name=call.tool_name,
                            is_error=False,
                        ),
                    )
                continue

            if completion.content is None:
                raise ModelRunAbstained("the model returned no answer content")

            try:
                final = output_schema.model_validate_json(completion.content)
            except ValidationError as error:
                validation_errors = [
                    {
                        "location": [str(part) for part in item["loc"]],
                        "type": item["type"],
                        "message": item["msg"],
                    }
                    for item in error.errors(
                        include_url=False,
                        include_input=False,
                    )[:16]
                ]
                logger.warning(
                    "model output failed server schema validation",
                    extra={
                        "event_data": {
                            "stage": "model_output_validation",
                            "turn": turns,
                            "turn_budget": profile.turn_budget,
                            "validation_errors": validation_errors,
                        }
                    },
                )
                if turns >= profile.turn_budget:
                    raise ModelRunAbstained(
                        "model output failed schema validation within the repair budget"
                    ) from None
                messages = messages + (
                    PromptMessage(
                        role="user",
                        content=json.dumps(
                            {
                                "kind": "output_schema_repair",
                                "instruction": (
                                    "Return a complete replacement JSON response that "
                                    "matches the required output schema exactly."
                                ),
                                "validation_errors": validation_errors,
                            },
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                    ),
                )
                continue
            output_payload = final.model_dump(mode="json")
            citation_value = output_payload.get("citation_ids")
            if isinstance(citation_value, list) and all(
                isinstance(item, str) for item in citation_value
            ):
                citation_ids = tuple(citation_value)
                if profile.require_citation_ids and not citation_ids:
                    raise ModelRunAbstained("the task requires citation-backed answers")
                if profile.require_authorized_citations:
                    if not run_input.authorized_citation_ids and citation_ids:
                        raise ModelRunAbstained("answer cited unauthorized evidence")
                    _validate_citations(
                        citation_ids,
                        run_input.authorized_citation_ids,
                        require_authorized=True,
                    )
                abstain_value = output_payload.get("abstain_reason")
                abstain_reason = (
                    abstain_value if isinstance(abstain_value, str) else None
                )
                if abstain_reason:
                    return self._finish_run(
                        started_at=started_at,
                        profile=profile,
                        run_input=run_input,
                        output=final,
                        status="abstained",
                        abstain_reason=abstain_reason,
                        input_tokens=total_input_tokens,
                        output_tokens=total_output_tokens,
                        turn_count=turns,
                        tool_invocations=tuple(tool_invocations),
                    )
                if profile.require_citation_ids and not citation_ids:
                    raise ModelRunAbstained("the task requires citation-backed answers")
                if profile.require_authorized_citations:
                    if not run_input.authorized_citation_ids and citation_ids:
                        raise ModelRunAbstained("answer cited unauthorized evidence")
                    _validate_citations(
                        citation_ids,
                        run_input.authorized_citation_ids,
                        require_authorized=True,
                    )
            return self._finish_run(
                started_at=started_at,
                profile=profile,
                run_input=run_input,
                output=final,
                status="succeeded",
                abstain_reason=None,
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                turn_count=turns,
                tool_invocations=tuple(tool_invocations),
            )

    def _execute_tool(
        self,
        *,
        profile: ResolvedModelRunProfile,
        tool: ServerTool,
        call: ToolCall,
        authorized_citations: tuple[str, ...],
    ) -> ToolResult:
        try:
            args = tool.input_schema.model_validate(call.arguments)
        except ValidationError as error:
            logger.warning(
                "model tool arguments failed server schema validation",
                extra={
                    "event_data": {
                        "stage": "model_tool_validation",
                        "tool_name": tool.name,
                        "validation_errors": [
                            {
                                "location": [str(part) for part in item["loc"]],
                                "type": item["type"],
                            }
                            for item in error.errors(
                                include_url=False,
                                include_input=False,
                            )[:16]
                        ],
                    }
                },
            )
            raise ModelRunAbstained(
                "model tool arguments failed schema validation"
            ) from error
        result = tool.handler(args)
        if profile.require_authorized_citations and any(
            citation not in authorized_citations for citation in result.citation_ids
        ):
            raise ModelRunAbstained("tool result cited unauthorized evidence")
        return result

    def _finish_run(
        self,
        *,
        started_at: datetime,
        profile: ResolvedModelRunProfile,
        run_input: ModelRunInput,
        output: OutputModel,
        status: str,
        abstain_reason: str | None,
        input_tokens: int | None,
        output_tokens: int | None,
        turn_count: int,
        tool_invocations: tuple[ToolInvocationRecord, ...],
    ) -> tuple[OutputModel, ModelRunRecord]:
        completed_at = datetime.now(UTC)
        record = ModelRunRecord(
            started_at=started_at.isoformat(),
            completed_at=completed_at.isoformat(),
            duration_ms=max(
                0,
                int((completed_at - started_at).total_seconds() * 1000),
            ),
            turn_count=turn_count,
            resolved_profile=profile,
            run_input=run_input,
            output_payload=output.model_dump(mode="json"),
            status=cast(Literal["succeeded", "abstained"], status),
            abstain_reason=abstain_reason,
            usage_input_tokens=input_tokens,
            usage_output_tokens=output_tokens,
            usage_measured=input_tokens is not None and output_tokens is not None,
            tool_invocations=tool_invocations,
        )
        return output, record


def _check_token_budget(
    token_budget: int,
    input_tokens: int,
    output_tokens: int,
) -> None:
    if input_tokens + output_tokens > token_budget:
        raise ModelRunAbstained("token budget exhausted before completion")


def _validate_citations(
    citation_ids: Iterable[str],
    authorized_citation_ids: tuple[str, ...],
    *,
    require_authorized: bool,
) -> None:
    if not require_authorized:
        return
    authorized = set(authorized_citation_ids)
    for citation_id in citation_ids:
        if citation_id not in authorized:
            raise ModelRunAbstained("answer cited unauthorized evidence")


def build_dungeon_intent_tool_result(
    *,
    tool_name: str,
    call_id: str,
    payload: dict[str, JsonValue],
    citation_ids: tuple[str, ...] = (),
    official_rule_ids: tuple[str, ...] = (),
    house_rule_overrides: tuple[str, ...] = (),
) -> ToolResult:
    """Convenience helper for tests and server-owned dungeon intent tools."""

    return ToolResult(
        tool_name=tool_name,
        call_id=call_id,
        payload=payload,
        citation_ids=citation_ids,
        official_rule_ids=official_rule_ids,
        house_rule_overrides=house_rule_overrides,
    )


__all__ = [
    "GatewayClient",
    "GatewayCompletion",
    "ModelRunAbstained",
    "ModelTaskRunner",
    "ServerTool",
    "build_dungeon_intent_tool_result",
]
