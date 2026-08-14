"""Bounded gateway loop tests for model-task orchestration."""

import json
import uuid

import pytest
from pydantic import BaseModel, Field

from dm_assistant.modules.modeling import (
    DungeonIntentV1,
    GatewayModelCatalogEntry,
    GatewayModelKey,
    ModelEndpointProfile,
    ModelRunInput,
    PromptMessage,
    ReasoningEffort,
    ReasoningLevel,
    ResolvedModelRunProfile,
    TaskProfile,
    ToolCall,
    resolve_run_profile,
)
from dm_assistant.orchestration.modeling import (
    GatewayCompletion,
    ModelRunAbstained,
    ModelTaskRunner,
    ServerTool,
    build_dungeon_intent_tool_result,
)


class BriefToolInput(BaseModel):
    model_config = {"extra": "forbid", "frozen": True, "strict": True}

    rooms: int = Field(ge=1)


class FakeClient:
    def __init__(self, completions: tuple[GatewayCompletion, ...]) -> None:
        self._completions = list(completions)

    def complete(
        self,
        *,
        profile: object,
        messages: tuple[PromptMessage, ...],
        allowed_tools: tuple[str, ...],
        tool_schemas: tuple[object, ...],
    ) -> GatewayCompletion:
        del profile, messages, allowed_tools, tool_schemas
        if not self._completions:
            raise AssertionError("unexpected extra gateway call")
        return self._completions.pop(0)


def _resolved_profile() -> tuple[
    TaskProfile,
    ResolvedModelRunProfile,
    ModelTaskRunner,
    ServerTool,
]:
    catalog_entry = GatewayModelCatalogEntry(
        provider_id="faux",
        model_id="faux_deterministic_v1",
        runtime_adapter="pi_ai",
        observed_capabilities=("text", "tool_calls"),
        supported_reasoning_levels=(ReasoningLevel.LOW, ReasoningLevel.MEDIUM),
        context_window_tokens=16_384,
        output_token_limit=4_096,
    )
    endpoint_profile = ModelEndpointProfile(
        profile_id=uuid.uuid4(),
        profile_version="1.0.0",
        runtime_adapter="pi_ai",
        provider_id="faux",
        model_id="faux_deterministic_v1",
        supported_efforts=(ReasoningEffort.FAST, ReasoningEffort.STANDARD),
        default_effort=ReasoningEffort.STANDARD,
        observed_capabilities=("text", "tool_calls"),
        context_window_tokens=16_384,
        output_token_limit=4_096,
        fallback_order=(GatewayModelKey(provider_id="faux", model_id="fallback"),),
    )
    task_profile = TaskProfile(
        profile_id=uuid.uuid4(),
        profile_version="1.0.0",
        task_name="dungeon_intent_v1",
        prompt_version="prompt-1",
        instruction_version="instructions-1",
        output_schema_name="dungeon_intent_v1",
        output_schema_version="1.0.0",
        allowed_tools=("set_brief",),
        turn_budget=2,
        tool_budget=1,
        time_budget_seconds=30,
        token_budget=512,
    )
    resolved = resolve_run_profile(
        endpoint_profile=endpoint_profile,
        task_profile=task_profile,
        catalog_entry=catalog_entry,
    )
    tool = ServerTool(
        name="set_brief",
        description="Validate a synthetic dungeon brief.",
        input_schema=BriefToolInput,
        handler=lambda _: build_dungeon_intent_tool_result(
            tool_name="set_brief",
            call_id="call-1",
            payload={"status": "ok"},
            citation_ids=("cite-1", "rules-1"),
            official_rule_ids=("rules-1",),
        ),
    )
    client = FakeClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="set_brief", call_id="call-1", arguments={"rooms": 3}
                    ),
                ),
                input_tokens=10,
                output_tokens=4,
            ),
            GatewayCompletion(
                content=DungeonIntentV1(
                    intent="Build a three-room dungeon.",
                    requested_constraints=("single entrance",),
                    citation_ids=("cite-1", "rules-1"),
                    official_rules=("five-foot grid",),
                    house_rule_overrides=("wider corridors",),
                ).model_dump_json(),
                input_tokens=6,
                output_tokens=12,
            ),
        )
    )
    runner = ModelTaskRunner(client)
    return task_profile, resolved, runner, tool


def test_bounded_loop_executes_server_tool_and_records_run_lineage() -> None:
    task_profile, resolved, runner, tool = _resolved_profile()
    run_input = ModelRunInput(
        messages=(
            PromptMessage(role="user", content="Create a synthetic dungeon intent."),
        ),
        authorized_citation_ids=("cite-1", "rules-1"),
    )

    output, record = runner.run(
        profile=resolved,
        run_input=run_input,
        output_schema=DungeonIntentV1,
        tools={tool.name: tool},
    )

    assert output.intent == "Build a three-room dungeon."
    assert record.status == "succeeded"
    assert record.resolved_profile.requested_effort is ReasoningEffort.STANDARD
    assert (
        record.resolved_profile.output_schema_version
        == task_profile.output_schema_version
    )
    assert record.tool_invocations[0].result.citation_ids == ("cite-1", "rules-1")
    assert record.usage_input_tokens == 16
    assert record.usage_output_tokens == 16


def test_bounded_loop_accepts_parallel_calls_within_the_invocation_budget() -> None:
    _, resolved, _, tool = _resolved_profile()
    profile = resolved.model_copy(update={"tool_budget": 2})
    final = DungeonIntentV1(
        intent="Build a three-room dungeon after parallel review.",
        citation_ids=("cite-1",),
    )
    client = FakeClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="set_brief",
                        call_id="call-1",
                        arguments={"rooms": 3},
                    ),
                    ToolCall(
                        tool_name="set_brief",
                        call_id="call-2",
                        arguments={"rooms": 3},
                    ),
                ),
                input_tokens=5,
                output_tokens=2,
            ),
            GatewayCompletion(
                content=final.model_dump_json(),
                input_tokens=7,
                output_tokens=9,
            ),
        )
    )

    output, record = ModelTaskRunner(client).run(
        profile=profile,
        run_input=ModelRunInput(
            messages=(PromptMessage(role="user", content="Create a dungeon."),),
            authorized_citation_ids=("cite-1", "rules-1"),
        ),
        output_schema=DungeonIntentV1,
        tools={tool.name: tool},
    )

    assert output == final
    assert record.turn_count == 2
    assert [item.call_id for item in record.tool_invocations] == ["call-1", "call-2"]


def test_bounded_loop_logs_safe_tool_details_when_invocation_budget_is_exceeded(
    caplog: pytest.LogCaptureFixture,
) -> None:
    _, resolved, _, tool = _resolved_profile()
    client = FakeClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="set_brief",
                        call_id="call-1",
                        arguments={"rooms": 3},
                    ),
                    ToolCall(
                        tool_name="set_brief",
                        call_id="call-2",
                        arguments={"rooms": 3},
                    ),
                )
            ),
        )
    )

    with pytest.raises(ModelRunAbstained, match="tool budget exhausted"):
        ModelTaskRunner(client).run(
            profile=resolved,
            run_input=ModelRunInput(
                messages=(PromptMessage(role="user", content="Create a dungeon."),),
            ),
            output_schema=DungeonIntentV1,
            tools={tool.name: tool},
        )

    record = next(
        item
        for item in caplog.records
        if item.message == "model tool calls exceeded the bounded task budget"
    )
    assert record.event_data == {
        "stage": "model_tool_policy",
        "tool_budget": 1,
        "prior_tool_count": 0,
        "requested_tool_count": 2,
        "requested_tool_names": ["set_brief", "set_brief"],
    }


def test_bounded_loop_logs_safe_tool_schema_diagnostics(
    caplog: pytest.LogCaptureFixture,
) -> None:
    _, resolved, _, tool = _resolved_profile()
    client = FakeClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="set_brief",
                        call_id="call-1",
                        arguments={"rooms": 0},
                    ),
                )
            ),
        )
    )

    with pytest.raises(ValueError, match="invalid arguments for tool set_brief"):
        ModelTaskRunner(client).run(
            profile=resolved,
            run_input=ModelRunInput(
                messages=(PromptMessage(role="user", content="Create a dungeon."),),
            ),
            output_schema=DungeonIntentV1,
            tools={tool.name: tool},
        )

    record = next(
        item
        for item in caplog.records
        if item.message == "model tool arguments failed server schema validation"
    )
    assert record.event_data["stage"] == "model_tool_validation"
    assert record.event_data["tool_name"] == "set_brief"
    assert record.event_data["validation_errors"] == [
        {
            "location": ["rooms"],
            "type": "greater_than_equal",
            "message": "Input should be greater than or equal to 1",
        }
    ]


def test_bounded_loop_repairs_schema_invalid_output_with_safe_diagnostics(
    caplog: pytest.LogCaptureFixture,
) -> None:
    _, resolved, _, tool = _resolved_profile()
    valid = DungeonIntentV1(
        intent="Build a repaired three-room dungeon.",
        citation_ids=("cite-1",),
    )
    client = FakeClient(
        (
            GatewayCompletion(
                content=json.dumps({"intent": ""}),
                input_tokens=5,
                output_tokens=2,
            ),
            GatewayCompletion(
                content=valid.model_dump_json(),
                input_tokens=7,
                output_tokens=9,
            ),
        )
    )

    output, record = ModelTaskRunner(client).run(
        profile=resolved,
        run_input=ModelRunInput(
            messages=(PromptMessage(role="user", content="Create a dungeon."),),
            authorized_citation_ids=("cite-1",),
        ),
        output_schema=DungeonIntentV1,
        tools={tool.name: tool},
    )

    assert output == valid
    assert record.turn_count == 2
    assert record.usage_input_tokens == 12
    assert record.usage_output_tokens == 11
    validation_log = next(
        item
        for item in caplog.records
        if item.message == "model output failed server schema validation"
    )
    assert validation_log.event_data["stage"] == "model_output_validation"
    assert validation_log.event_data["turn"] == 1
    assert validation_log.event_data["validation_errors"] == [
        {
            "location": ["intent"],
            "type": "string_too_short",
            "message": "String should have at least 1 character",
        }
    ]


def test_bounded_loop_abstains_when_citations_are_unauthorized() -> None:
    catalog_entry = GatewayModelCatalogEntry(
        provider_id="faux",
        model_id="faux_deterministic_v1",
        runtime_adapter="pi_ai",
        observed_capabilities=("text",),
        supported_reasoning_levels=(ReasoningLevel.LOW, ReasoningLevel.MEDIUM),
        context_window_tokens=16_384,
        output_token_limit=4_096,
    )
    endpoint_profile = ModelEndpointProfile(
        profile_id=uuid.uuid4(),
        profile_version="1.0.0",
        runtime_adapter="pi_ai",
        provider_id="faux",
        model_id="faux_deterministic_v1",
        supported_efforts=(ReasoningEffort.FAST, ReasoningEffort.STANDARD),
        default_effort=ReasoningEffort.STANDARD,
        context_window_tokens=16_384,
        output_token_limit=4_096,
    )
    task_profile = TaskProfile(
        profile_id=uuid.uuid4(),
        profile_version="1.0.0",
        task_name="dungeon_intent_v1",
        prompt_version="prompt-1",
        instruction_version="instructions-1",
        output_schema_name="dungeon_intent_v1",
        output_schema_version="1.0.0",
        turn_budget=2,
        tool_budget=1,
        time_budget_seconds=30,
        token_budget=512,
    )
    resolved = resolve_run_profile(
        endpoint_profile=endpoint_profile,
        task_profile=task_profile,
        catalog_entry=catalog_entry,
    )
    client = FakeClient(
        (
            GatewayCompletion(
                content=json.dumps(
                    {
                        "intent": "Build a synthetic dungeon.",
                        "citation_ids": ("unauthorized-cite",),
                        "official_rules": (),
                        "house_rule_overrides": (),
                        "requested_constraints": (),
                        "unknowns": (),
                        "conflicts": (),
                        "abstain_reason": None,
                    }
                ),
                input_tokens=4,
                output_tokens=6,
            ),
        )
    )
    runner = ModelTaskRunner(client)

    with pytest.raises(ModelRunAbstained, match="unauthorized evidence"):
        runner.run(
            profile=resolved,
            run_input=ModelRunInput(
                messages=(
                    PromptMessage(role="user", content="Ask for a dungeon intent."),
                ),
                authorized_citation_ids=("cite-1",),
            ),
            output_schema=DungeonIntentV1,
            tools={},
        )
