"""Model/task profile contract tests for bounded gateway runs."""

import uuid

import pytest

from dm_assistant.modules.modeling import (
    DungeonIntentV1,
    GatewayModelCatalogEntry,
    GatewayModelKey,
    ModelEndpointProfile,
    ReasoningEffort,
    ReasoningLevel,
    TaskProfile,
    resolve_reasoning_level,
    resolve_run_profile,
)


def test_resolve_run_profile_maps_supported_efforts_and_records_lineage() -> None:
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

    assert resolve_reasoning_level(ReasoningEffort.DEEP).value == "high"

    resolved = resolve_run_profile(
        endpoint_profile=endpoint_profile,
        task_profile=task_profile,
        catalog_entry=catalog_entry,
        requested_effort=ReasoningEffort.FAST,
    )

    assert resolved.requested_effort is ReasoningEffort.FAST
    assert resolved.resolved_reasoning_level is ReasoningLevel.LOW
    assert resolved.output_schema_name == "dungeon_intent_v1"
    assert resolved.fallback_order == endpoint_profile.fallback_order


def test_resolve_run_profile_rejects_unsupported_effort() -> None:
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

    with pytest.raises(ValueError, match="not supported"):
        resolve_run_profile(
            endpoint_profile=endpoint_profile,
            task_profile=task_profile,
            catalog_entry=catalog_entry,
            requested_effort=ReasoningEffort.DEEP,
        )


def test_dungeon_intent_schema_carries_claims_and_abstention_fields() -> None:
    intent = DungeonIntentV1(
        intent="Build a three-room dungeon.",
        requested_constraints=("single entrance",),
        citation_ids=("cite-1",),
        official_rules=("five-foot grid",),
        house_rule_overrides=("wider corridors",),
    )

    assert intent.citation_ids == ("cite-1",)
    assert intent.abstain_reason is None
