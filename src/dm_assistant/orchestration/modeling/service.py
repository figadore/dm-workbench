"""Bounded model-task orchestration with server-owned tool execution."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from typing import Literal, Protocol, TypeVar, cast

from pydantic import BaseModel, ConfigDict, JsonValue, ValidationError

from dm_assistant.modules.modeling import (
    DungeonIntentV1,
    ModelRunInput,
    ModelRunRecord,
    PromptMessage,
    ResolvedModelRunProfile,
    ToolCall,
    ToolInvocationRecord,
    ToolResult,
)

OutputModel = TypeVar("OutputModel", bound=BaseModel)
ToolInputModel = TypeVar("ToolInputModel", bound=BaseModel)


class GatewayCompletion(BaseModel):
    """One bounded gateway response turn."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    content: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    input_tokens: int = 0
    output_tokens: int = 0


class GatewayClient(Protocol):
    """Minimal gateway client used by the bounded prompt loop."""

    def complete(
        self,
        *,
        profile: ResolvedModelRunProfile,
        messages: tuple[PromptMessage, ...],
        allowed_tools: tuple[str, ...],
    ) -> GatewayCompletion: ...


@dataclass(frozen=True, slots=True)
class ServerTool:
    """Server-owned tool schema plus deterministic application handler."""

    name: str
    input_schema: type[ToolInputModel]
    handler: Callable[[ToolInputModel], ToolResult]


class ModelRunAbstained(RuntimeError):
    """Raised when the task profile requires abstention instead of an answer."""


class ModelTaskRunner:
    """Run a bounded model loop while enforcing profile, citation, and tool policy."""

    def __init__(self, client: GatewayClient) -> None:
        self._client = client

    def run(
        self,
        *,
        profile: ResolvedModelRunProfile,
        run_input: ModelRunInput,
        output_schema: type[OutputModel],
        tools: Mapping[str, ServerTool],
    ) -> tuple[OutputModel, ModelRunRecord]:
        started_at = datetime.now(UTC)
        messages = tuple(run_input.messages)
        tool_invocations: list[ToolInvocationRecord] = []
        total_input_tokens = 0
        total_output_tokens = 0
        turns = 0

        while True:
            if turns >= profile.turn_budget:
                raise ModelRunAbstained("turn budget exhausted before a final answer")
            completion = self._client.complete(
                profile=profile,
                messages=messages,
                allowed_tools=profile.allowed_tools,
            )
            turns += 1
            total_input_tokens += completion.input_tokens
            total_output_tokens += completion.output_tokens
            _check_token_budget(profile.token_budget, total_input_tokens, total_output_tokens)

            if completion.tool_calls:
                if len(tool_invocations) + len(completion.tool_calls) > profile.tool_budget:
                    raise ModelRunAbstained("tool budget exhausted before completion")
                for call in completion.tool_calls:
                    if call.tool_name not in profile.allowed_tools:
                        raise ValueError(f"tool {call.tool_name} is not allowed for this task")
                    tool = tools.get(call.tool_name)
                    if tool is None:
                        raise ValueError(f"tool {call.tool_name} is not registered")
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
                            role="assistant",
                            content=json.dumps(
                                {
                                    "tool_call_id": call.call_id,
                                    "tool_name": call.tool_name,
                                    "result": result.model_dump(mode="json"),
                                },
                                separators=(",", ":"),
                                sort_keys=True,
                            ),
                        ),
                    )
                continue

            if completion.content is None:
                raise ModelRunAbstained("the model returned no answer content")

            final = output_schema.model_validate_json(completion.content)
            if hasattr(final, "citation_ids"):
                citation_ids = tuple(getattr(final, "citation_ids"))
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
                if getattr(final, "abstain_reason", None):
                    return self._finish_run(
                        started_at=started_at,
                        profile=profile,
                        run_input=run_input,
                        output=final,
                        status="abstained",
                        abstain_reason=getattr(final, "abstain_reason"),
                        input_tokens=total_input_tokens,
                        output_tokens=total_output_tokens,
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
            raise ValueError(f"invalid arguments for tool {tool.name}") from error
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
        input_tokens: int,
        output_tokens: int,
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
            resolved_profile=profile,
            run_input=run_input,
            output_payload=output.model_dump(mode="json"),
            status=cast(Literal["succeeded", "abstained"], status),
            abstain_reason=abstain_reason,
            usage_input_tokens=input_tokens,
            usage_output_tokens=output_tokens,
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
