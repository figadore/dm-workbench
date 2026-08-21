"""Versioned model/task profile contracts for bounded prompt runs."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    model_validator,
)

Slug = Annotated[
    str,
    StringConstraints(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_]*$"),
]
GatewayIdentifier = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=160,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    ),
]
VersionText = Annotated[
    str,
    StringConstraints(
        min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9._+-]*$"
    ),
]
ShortText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
SummaryText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
]
PromptText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=16_000)
]


class ContractModel(BaseModel):
    """Strict immutable model boundary for profile and run contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ReasoningEffort(StrEnum):
    FAST = "fast"
    STANDARD = "standard"
    DEEP = "deep"


class ReasoningLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class GatewayModelKey(ContractModel):
    provider_id: GatewayIdentifier
    model_id: GatewayIdentifier


class GatewayModelCatalogEntry(ContractModel):
    """Gateway-observed capabilities for one provider/model pair."""

    provider_id: GatewayIdentifier
    model_id: GatewayIdentifier
    runtime_adapter: Slug
    observed_capabilities: tuple[Slug, ...] = ()
    supported_reasoning_levels: tuple[ReasoningLevel, ...] = Field(min_length=1)
    context_window_tokens: int = Field(ge=1)
    output_token_limit: int = Field(ge=1)

    @model_validator(mode="after")
    def dedupe_capabilities(self) -> Self:
        if len(set(self.observed_capabilities)) != len(self.observed_capabilities):
            raise ValueError("observed capabilities must be unique")
        if len(set(self.supported_reasoning_levels)) != len(
            self.supported_reasoning_levels
        ):
            raise ValueError("supported reasoning levels must be unique")
        return self


class ModelEndpointProfile(ContractModel):
    """Configured endpoint profile with fallback order and model budgets."""

    profile_id: UUID
    profile_version: VersionText
    runtime_adapter: Slug
    provider_id: GatewayIdentifier
    model_id: GatewayIdentifier
    supported_efforts: tuple[ReasoningEffort, ...] = Field(min_length=1)
    default_effort: ReasoningEffort = ReasoningEffort.STANDARD
    observed_capabilities: tuple[Slug, ...] = ()
    context_window_tokens: int = Field(ge=1)
    output_token_limit: int = Field(ge=1)
    fallback_order: tuple[GatewayModelKey, ...] = ()

    @model_validator(mode="after")
    def validate_endpoint_profile(self) -> Self:
        if len(set(self.supported_efforts)) != len(self.supported_efforts):
            raise ValueError("supported efforts must be unique")
        if self.default_effort not in self.supported_efforts:
            raise ValueError("default effort must be supported by the profile")
        if len(set(self.observed_capabilities)) != len(self.observed_capabilities):
            raise ValueError("observed capabilities must be unique")
        if len(set(self.fallback_order)) != len(self.fallback_order):
            raise ValueError("fallback order must be unique")
        if any(
            item.provider_id == self.provider_id and item.model_id == self.model_id
            for item in self.fallback_order
        ):
            raise ValueError("fallback order cannot include the active endpoint")
        return self


class TaskProfile(ContractModel):
    """Task-specific model contract with explicit budgets and tool policy."""

    profile_id: UUID
    profile_version: VersionText
    task_name: Slug
    prompt_version: VersionText
    instruction_version: VersionText
    output_schema_name: Slug
    output_schema_version: VersionText
    allowed_tools: tuple[Slug, ...] = ()
    turn_budget: int = Field(ge=1, le=32)
    tool_budget: int = Field(ge=0, le=64)
    time_budget_seconds: int = Field(ge=1, le=600)
    token_budget: int = Field(ge=1, le=262_144)
    require_citation_ids: bool = True
    require_authorized_citations: bool = True
    allow_source_retrieval_tools: bool = False

    @model_validator(mode="after")
    def validate_task_profile(self) -> Self:
        if len(set(self.allowed_tools)) != len(self.allowed_tools):
            raise ValueError("allowed tools must be unique")
        if not self.allow_source_retrieval_tools:
            if any(tool.startswith("retrieve_") for tool in self.allowed_tools):
                raise ValueError("source retrieval tools are not allowed by default")
        return self


class ResolvedModelRunProfile(ContractModel):
    """Run lineage record after validating the chosen endpoint and task profile."""

    endpoint_profile_id: UUID
    endpoint_profile_version: VersionText
    task_profile_id: UUID
    task_profile_version: VersionText
    provider_id: GatewayIdentifier
    model_id: GatewayIdentifier
    runtime_adapter: Slug
    requested_effort: ReasoningEffort
    resolved_reasoning_level: ReasoningLevel
    supported_efforts: tuple[ReasoningEffort, ...]
    observed_capabilities: tuple[Slug, ...]
    prompt_version: VersionText
    instruction_version: VersionText
    output_schema_name: Slug
    output_schema_version: VersionText
    allowed_tools: tuple[Slug, ...]
    turn_budget: int
    tool_budget: int
    time_budget_seconds: int
    token_budget: int
    require_citation_ids: bool
    require_authorized_citations: bool
    allow_source_retrieval_tools: bool
    fallback_order: tuple[GatewayModelKey, ...]
    override_notes: dict[str, JsonValue] = Field(default_factory=dict)


class ToolCall(ContractModel):
    tool_name: Slug
    call_id: str = Field(min_length=1, max_length=160)
    arguments: dict[str, JsonValue] = Field(default_factory=dict)


class PromptMessage(ContractModel):
    """Strict normalized transcript message for private gateway transport."""

    role: Literal["user", "assistant", "tool_result"]
    content: str = Field(min_length=0, max_length=16_000)
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = Field(default=None, min_length=1, max_length=160)
    tool_name: Slug | None = None
    is_error: bool | None = None
    opaque_continuity_signatures: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_role_shape(self) -> Self:
        if self.role == "user":
            if (
                not self.content
                or self.tool_calls
                or self.tool_call_id
                or self.tool_name
                or self.is_error is not None
            ):
                raise ValueError("user messages cannot carry tool result fields")
        elif self.role == "assistant":
            if self.tool_call_id or self.tool_name or self.is_error is not None:
                raise ValueError("assistant messages cannot carry tool result fields")
        elif (
            not self.content
            or self.tool_call_id is None
            or self.tool_name is None
            or self.is_error is None
        ):
            raise ValueError(
                "tool_result messages require call ID, name, and error flag"
            )
        return self


class ModelRunInput(ContractModel):
    messages: tuple[PromptMessage, ...] = Field(min_length=1)
    authorized_citation_ids: tuple[str, ...] = ()
    official_rule_ids: tuple[str, ...] = ()


class ToolResult(ContractModel):
    tool_name: Slug
    call_id: str = Field(min_length=1, max_length=160)
    payload: dict[str, JsonValue]
    citation_ids: tuple[str, ...] = ()
    official_rule_ids: tuple[str, ...] = ()
    house_rule_overrides: tuple[str, ...] = ()


class ToolInvocationRecord(ContractModel):
    tool_name: Slug
    call_id: str = Field(min_length=1, max_length=160)
    arguments: dict[str, JsonValue]
    result: ToolResult


class ModelRunRecord(ContractModel):
    started_at: str
    completed_at: str
    duration_ms: int = Field(ge=0)
    turn_count: int = Field(ge=1)
    resolved_profile: ResolvedModelRunProfile
    run_input: ModelRunInput
    output_payload: dict[str, JsonValue] | None = None
    status: Literal["succeeded", "abstained"]
    abstain_reason: str | None = None
    usage_input_tokens: int | None = Field(default=None, ge=0)
    usage_output_tokens: int | None = Field(default=None, ge=0)
    usage_measured: bool
    tool_invocations: tuple[ToolInvocationRecord, ...] = ()


class DungeonIntentV1(ContractModel):
    """Strict typed dungeon intent for the first prompted dungeon profile."""

    intent: ShortText
    requested_constraints: tuple[ShortText, ...] = ()
    citation_ids: tuple[str, ...] = ()
    official_rules: tuple[ShortText, ...] = ()
    house_rule_overrides: tuple[ShortText, ...] = ()
    unknowns: tuple[ShortText, ...] = ()
    conflicts: tuple[ShortText, ...] = ()
    abstain_reason: ShortText | None = None

    @model_validator(mode="after")
    def normalize_constraints(self) -> Self:
        object.__setattr__(
            self, "requested_constraints", tuple(self.requested_constraints)
        )
        return self


class AskResponseV1(ContractModel):
    """Strict typed answer payload for the general Ask workflow."""

    answer: SummaryText
    citation_ids: tuple[str, ...] = ()
    official_rules: tuple[ShortText, ...] = ()
    house_rule_overrides: tuple[ShortText, ...] = ()
    unknowns: tuple[ShortText, ...] = ()
    conflicts: tuple[ShortText, ...] = ()
    attachment_ids: tuple[UUID, ...] = ()
    comparison_summary: SummaryText | None = None


def resolve_reasoning_level(effort: ReasoningEffort) -> ReasoningLevel:
    """Map a user-facing effort to the normalized gateway reasoning level."""

    return {
        ReasoningEffort.FAST: ReasoningLevel.LOW,
        ReasoningEffort.STANDARD: ReasoningLevel.MEDIUM,
        ReasoningEffort.DEEP: ReasoningLevel.HIGH,
    }[effort]


def resolve_run_profile(
    *,
    endpoint_profile: ModelEndpointProfile,
    task_profile: TaskProfile,
    catalog_entry: GatewayModelCatalogEntry,
    requested_effort: ReasoningEffort | None = None,
    override_notes: dict[str, JsonValue] | None = None,
) -> ResolvedModelRunProfile:
    """Validate the chosen endpoint and task profile against gateway capabilities."""

    if (
        endpoint_profile.provider_id != catalog_entry.provider_id
        or endpoint_profile.model_id != catalog_entry.model_id
    ):
        raise ValueError("endpoint profile does not match the gateway catalog entry")
    if endpoint_profile.runtime_adapter != catalog_entry.runtime_adapter:
        raise ValueError("endpoint runtime adapter does not match the catalog entry")
    if not set(endpoint_profile.supported_efforts).issubset(
        supported_from_reasoning(catalog_entry.supported_reasoning_levels)
    ):
        raise ValueError("endpoint profile requests unsupported reasoning levels")

    resolved_effort = requested_effort or endpoint_profile.default_effort
    if resolved_effort not in endpoint_profile.supported_efforts:
        raise ValueError("requested effort is not supported by the selected model")

    reasoning_level = resolve_reasoning_level(resolved_effort)
    if reasoning_level not in catalog_entry.supported_reasoning_levels:
        raise ValueError("requested effort is not supported by the gateway catalog")

    return ResolvedModelRunProfile(
        endpoint_profile_id=endpoint_profile.profile_id,
        endpoint_profile_version=endpoint_profile.profile_version,
        task_profile_id=task_profile.profile_id,
        task_profile_version=task_profile.profile_version,
        provider_id=endpoint_profile.provider_id,
        model_id=endpoint_profile.model_id,
        runtime_adapter=endpoint_profile.runtime_adapter,
        requested_effort=resolved_effort,
        resolved_reasoning_level=reasoning_level,
        supported_efforts=endpoint_profile.supported_efforts,
        observed_capabilities=endpoint_profile.observed_capabilities,
        prompt_version=task_profile.prompt_version,
        instruction_version=task_profile.instruction_version,
        output_schema_name=task_profile.output_schema_name,
        output_schema_version=task_profile.output_schema_version,
        allowed_tools=task_profile.allowed_tools,
        turn_budget=task_profile.turn_budget,
        tool_budget=task_profile.tool_budget,
        time_budget_seconds=task_profile.time_budget_seconds,
        token_budget=task_profile.token_budget,
        require_citation_ids=task_profile.require_citation_ids,
        require_authorized_citations=task_profile.require_authorized_citations,
        allow_source_retrieval_tools=task_profile.allow_source_retrieval_tools,
        fallback_order=endpoint_profile.fallback_order,
        override_notes=override_notes or {},
    )


def supported_from_reasoning(
    reasoning_levels: tuple[ReasoningLevel, ...],
) -> tuple[ReasoningEffort, ...]:
    """Invert the gateway reasoning levels to the user-facing effort set."""

    mapping = {
        ReasoningLevel.LOW: ReasoningEffort.FAST,
        ReasoningLevel.MEDIUM: ReasoningEffort.STANDARD,
        ReasoningLevel.HIGH: ReasoningEffort.DEEP,
    }
    return tuple(mapping[level] for level in reasoning_levels)


def canonical_json_sha256(value: JsonValue | dict[str, JsonValue]) -> str:
    """Hash a JSON-serializable structure in canonical form."""

    document = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(document.encode("utf-8")).hexdigest()
