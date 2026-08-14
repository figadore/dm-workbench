"""Bounded standalone prompt-to-dungeon compilation over the pure kernel."""

from __future__ import annotations

import json
import uuid
from typing import Protocol, cast

from pydantic import BaseModel, ConfigDict, JsonValue

from dm_assistant.adapters.model_gateway import PiGatewayClient
from dm_assistant.modules.modeling import (
    DungeonGenerationIntentV1,
    GatewayModelCatalogEntry,
    ModelEndpointProfile,
    ModelRunInput,
    ModelRunRecord,
    PromptMessage,
    ReasoningEffort,
    ReasoningLevel,
    ResolvedModelRunProfile,
    TaskProfile,
    ToolResult,
    resolve_run_profile,
    supported_from_reasoning,
)
from dm_assistant.modules.preparation import (
    DungeonGenerationContext,
    GenerationContextEnvelope,
    GenerationContextPin,
    ToolRunPin,
    canonical_json_sha256,
)
from dm_assistant.observability import get_logger
from dm_assistant.orchestration.dungeons.contracts import (
    CreatePromptedDungeonWorkflow,
    DungeonWorkflowResult,
    PromptDungeonWorkflow,
    PromptedDungeonModelLineage,
)
from dm_assistant.orchestration.modeling import (
    GatewayClient,
    GatewayCompletion,
    GatewayToolSchema,
    ModelRunAbstained,
    ModelTaskRunner,
    ServerTool,
)
from dm_dungeon import (
    DungeonPackage,
    LayoutRequest,
    LockedLayoutComponents,
    generate_layout,
    validate_geometry,
    validate_topology,
)

_DUNGEON_CONTEXT_KIND = "dungeon_generation"
_DUNGEON_INTENT_SCHEMA_NAME = "dungeon_generation_intent_v1"
_DUNGEON_INTENT_SCHEMA_VERSION = "1.0.0"
_REVIEW_BRIEF_TOOL = "review_dungeon_brief"
_REVIEW_TOPOLOGY_TOOL = "review_dungeon_topology"
_GENERATE_LAYOUT_TOOL = "generate_dungeon_layout"
_VALIDATE_INTENT_TOOL = "validate_dungeon_intent"
_REGENERATE_LAYOUT_TOOL = "regenerate_dungeon_layout"
_DUNGEON_TOOL_NAMES = (
    _REVIEW_BRIEF_TOOL,
    _REVIEW_TOPOLOGY_TOOL,
    _GENERATE_LAYOUT_TOOL,
    _VALIDATE_INTENT_TOOL,
    _REGENERATE_LAYOUT_TOOL,
)
_MAX_REPAIR_DIAGNOSTICS = 16
logger = get_logger(__name__)


class _DungeonIntentToolInput(BaseModel):
    """Model-authored intent accepted by server-seeded deterministic tools."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    intent: DungeonGenerationIntentV1


class _TargetedRegenerationInput(_DungeonIntentToolInput):
    """Model request for a code-owned, non-persistent targeted layout preview."""

    seed: int
    locked_component_ids: list[str] = []


class PromptedDungeonCreator(Protocol):
    """Dungeon persistence boundary used by prompt orchestration."""

    def create_prompted(
        self,
        command: CreatePromptedDungeonWorkflow,
    ) -> DungeonWorkflowResult: ...


def resolve_dungeon_prompt_profile(
    *,
    provider_id: str,
    model_id: str,
    capabilities: tuple[str, ...],
    context_window_tokens: int,
    output_token_limit: int,
    requested_effort: ReasoningEffort = ReasoningEffort.STANDARD,
) -> ResolvedModelRunProfile:
    """Resolve the pinned standalone dungeon profile against gateway metadata."""

    reasoning_levels = (
        (ReasoningLevel.LOW, ReasoningLevel.MEDIUM, ReasoningLevel.HIGH)
        if "thinking" in capabilities
        else (ReasoningLevel.MEDIUM,)
    )
    supported_efforts = supported_from_reasoning(reasoning_levels)
    endpoint = ModelEndpointProfile(
        profile_id=uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"dm-assistant:model-endpoint:pi_ai:{provider_id}:{model_id}",
        ),
        profile_version="1.0.0",
        runtime_adapter="pi_ai",
        provider_id=provider_id,
        model_id=model_id,
        supported_efforts=supported_efforts,
        default_effort=(
            ReasoningEffort.STANDARD
            if ReasoningEffort.STANDARD in supported_efforts
            else supported_efforts[0]
        ),
        observed_capabilities=capabilities,
        context_window_tokens=context_window_tokens,
        output_token_limit=output_token_limit,
    )
    task = TaskProfile(
        profile_id=uuid.UUID("77777777-7777-7777-7777-777777777710"),
        profile_version="1.2.0",
        task_name=_DUNGEON_INTENT_SCHEMA_NAME,
        prompt_version="prompt-1",
        instruction_version="instructions-3",
        output_schema_name=_DUNGEON_INTENT_SCHEMA_NAME,
        output_schema_version=_DUNGEON_INTENT_SCHEMA_VERSION,
        allowed_tools=_DUNGEON_TOOL_NAMES,
        # One optional deterministic tool turn, one response turn, and one
        # schema-repair turn. Providers may emit multiple parallel calls in that
        # one tool turn, so the invocation budget covers each allowlisted tool
        # once. The turn budget still prevents a repeated open-ended tool loop.
        turn_budget=3,
        tool_budget=len(_DUNGEON_TOOL_NAMES),
        time_budget_seconds=300,
        # This cumulative budget covers all bounded prompt + typed-tool-schema
        # turns and output, not only generated tokens. Gateway output stays 16K.
        token_budget=min(context_window_tokens, 150_000),
        require_citation_ids=False,
        require_authorized_citations=False,
        allow_source_retrieval_tools=False,
    )
    catalog = GatewayModelCatalogEntry(
        provider_id=provider_id,
        model_id=model_id,
        runtime_adapter="pi_ai",
        observed_capabilities=capabilities,
        supported_reasoning_levels=reasoning_levels,
        context_window_tokens=context_window_tokens,
        output_token_limit=output_token_limit,
    )
    return resolve_run_profile(
        endpoint_profile=endpoint,
        task_profile=task,
        catalog_entry=catalog,
        requested_effort=requested_effort,
    )


class DungeonPromptService:
    """Compile standalone model intent and preserve replayable generation lineage."""

    def __init__(
        self,
        dungeon_studio: PromptedDungeonCreator,
        gateway_client: GatewayClient,
    ) -> None:
        self._dungeon_studio = dungeon_studio
        self._gateway_client = gateway_client

    def create(
        self,
        command: PromptDungeonWorkflow,
        profile: ResolvedModelRunProfile,
        stream_run_id: str | None = None,
    ) -> DungeonWorkflowResult:
        """Generate a draft from a standalone DM prompt with at most one repair."""

        _validate_profile(profile)
        context = _build_standalone_context(command)
        runner = ModelTaskRunner(
            _RunBoundGatewayClient(self._gateway_client, stream_run_id)
            if stream_run_id is not None
            else self._gateway_client
        )
        tools = _dungeon_tools(command.seed)
        logger.info(
            "dungeon prompt started",
            extra={
                "event_data": {
                    "stage": "model_intent",
                    "provider_id": profile.provider_id,
                    "model_id": profile.model_id,
                }
            },
        )
        try:
            intent, record = runner.run(
                profile=profile,
                run_input=_initial_model_input(command, context),
                output_schema=DungeonGenerationIntentV1,
                tools=tools,
            )
            _require_non_abstained_intent(intent, record)
        except ModelRunAbstained:
            logger.warning(
                "dungeon prompt stopped before topology was accepted",
                extra={"event_data": {"stage": "model_intent", "accepted": False}},
            )
            raise

        lineage = [_lineage(intent, record)]
        request, diagnostics, valid = _preflight(intent, command.seed)
        _log_layout_request(request=request, diagnostics=diagnostics, valid=valid)
        if not valid:
            repaired_profile = _remaining_profile(profile, record)
            try:
                repaired_intent, repaired_record = runner.run(
                    profile=repaired_profile,
                    run_input=_repair_model_input(
                        command, context, intent, diagnostics
                    ),
                    output_schema=DungeonGenerationIntentV1,
                    tools=tools,
                )
                _require_non_abstained_intent(repaired_intent, repaired_record)
            except ModelRunAbstained:
                logger.warning(
                    "dungeon prompt stopped during topology repair",
                    extra={
                        "event_data": {"stage": "topology_repair", "accepted": False}
                    },
                )
                raise
            lineage.append(_lineage(repaired_intent, repaired_record))
            intent = repaired_intent
            request, diagnostics, valid = _preflight(intent, command.seed)
            _log_layout_request(request=request, diagnostics=diagnostics, valid=valid)

        model_lineage = tuple(lineage)
        return self._dungeon_studio.create_prompted(
            CreatePromptedDungeonWorkflow(
                campaign_id=command.campaign_id,
                title=command.title or request.brief.title,
                layout_request=request,
                created_by=command.created_by,
                context=context,
                model_task_profile_id=profile.task_profile_id,
                model_lineage=model_lineage,
                tool_runs=_tool_run_pins(model_lineage),
                source_prompt=command.prompt,
            )
        )


class _RunBoundGatewayClient:
    """Bind a web-operation UUID to pi gateway cancellation without changing tools."""

    def __init__(self, client: GatewayClient, run_id: str) -> None:
        self._client = client
        self._run_id = run_id

    def complete(
        self,
        *,
        profile: ResolvedModelRunProfile,
        messages: tuple[PromptMessage, ...],
        allowed_tools: tuple[str, ...],
        tool_schemas: tuple[GatewayToolSchema, ...],
    ) -> GatewayCompletion:
        if isinstance(self._client, PiGatewayClient):
            return self._client.complete(
                profile=profile,
                messages=messages,
                allowed_tools=allowed_tools,
                tool_schemas=tool_schemas,
                run_id=self._run_id,
            )
        return self._client.complete(
            profile=profile,
            messages=messages,
            allowed_tools=allowed_tools,
            tool_schemas=tool_schemas,
        )


def _log_layout_request(
    *,
    request: LayoutRequest,
    diagnostics: tuple[dict[str, JsonValue], ...],
    valid: bool,
) -> None:
    """Expose the exact typed generator input when a model topology was accepted."""
    logger.info(
        "dungeon topology compiled",
        extra={
            "event_data": {
                "stage": "deterministic_preflight",
                "valid": valid,
                "diagnostic_codes": [
                    item["code"]
                    for item in diagnostics
                    if isinstance(item.get("code"), str)
                ],
                "layout_request": request.model_dump(mode="json"),
            }
        },
    )


def compile_layout_request(
    intent: DungeonGenerationIntentV1,
    seed: int,
) -> LayoutRequest:
    """Derive a stable package identity and exact layout request from typed intent."""

    _require_non_abstained_intent(intent, None)
    assert intent.brief is not None
    assert intent.topology is not None
    intent_document = cast(dict[str, JsonValue], intent.model_dump(mode="json"))
    source: dict[str, JsonValue] = {
        "intent": intent_document,
        "seed": seed,
        "generator_version": "orthogonal-v1",
    }
    package_id = f"dungeon_{canonical_json_sha256(source)[:32]}"
    return LayoutRequest(
        schema_version="1.0.0",
        package_id=package_id,
        brief=intent.brief,
        topology=intent.topology,
        seed=seed,
        generator_version="orthogonal-v1",
    )


def _build_standalone_context(
    command: PromptDungeonWorkflow,
) -> GenerationContextPin:
    payload = DungeonGenerationContext(
        context_version="1.0.0",
        prompt_input_sha256=canonical_json_sha256({"prompt": command.prompt}),
        requested_constraints=command.requested_constraints,
        preparation_owner_id=str(command.campaign_id),
        standalone_provenance="dm_prompt",
    )
    payload_document = payload.model_dump(mode="json")
    envelope = GenerationContextEnvelope(
        context_kind=_DUNGEON_CONTEXT_KIND,
        payload_version=payload.context_version,
        visibility_policy=command.scope.visibility,
        payload=payload_document,
        payload_sha256=canonical_json_sha256(payload_document),
    )
    return GenerationContextPin(
        envelope_kind=envelope.context_kind,
        payload_version=envelope.payload_version,
        envelope=envelope.model_dump(mode="json"),
        payload_sha256=envelope.payload_sha256,
    )


def _initial_model_input(
    command: PromptDungeonWorkflow,
    context: GenerationContextPin,
) -> ModelRunInput:
    return ModelRunInput(
        messages=(
            PromptMessage(
                role="user",
                content=_canonical_message(
                    {
                        "task": _DUNGEON_INTENT_SCHEMA_NAME,
                        "instructions": (
                            "Return only one dungeon_generation_intent_v1 JSON object. "
                            "Its exact schema is the intent field in the supplied tool "
                            "schemas. Author high-level brief and topology intent only; "
                            "do not author exact geometry, renderer syntax, files, "
                            "approval, or canonical state. Use stable descriptive IDs. "
                            "DungeonBrief.purpose is exactly one enum string. Brief "
                            "inhabitants, constraints, and campaign_hooks contain typed "
                            "objects with id, text, and visibility, never bare strings. "
                            "Give each topology room a concise, human-readable name; "
                            "keep prose constraints, hooks, and feature details in the "
                            "brief text fields rather than opaque IDs or map syntax. "
                            "For door connections, locked doors require gate_id, "
                            "trapped doors require trap_id, and secret or trapped doors "
                            "must use dm_only visibility. Every player_safe connection "
                            "must connect only player_safe rooms; mark any connection to "
                            "a dm_only room dm_only. Set brief.target_room_count exactly "
                            "to the number of topology rooms, keep each floor's target "
                            "count consistent, and include at least one exit-role room."
                        ),
                        "prompt": command.prompt,
                        "context": context.envelope,
                    }
                ),
            ),
        )
    )


def _repair_model_input(
    command: PromptDungeonWorkflow,
    context: GenerationContextPin,
    intent: DungeonGenerationIntentV1,
    diagnostics: tuple[dict[str, JsonValue], ...],
) -> ModelRunInput:
    return ModelRunInput(
        messages=(
            PromptMessage(
                role="user",
                content=_canonical_message(
                    {
                        "task": _DUNGEON_INTENT_SCHEMA_NAME,
                        "instructions": (
                            "Return only one corrected dungeon_generation_intent_v1 "
                            "JSON object using the intent schema in the supplied tools. "
                            "Repair the diagnostics without authoring exact geometry or "
                            "renderer syntax."
                        ),
                        "prompt": command.prompt,
                        "context": context.envelope,
                        "previous_intent": intent.model_dump(mode="json"),
                        "diagnostics": list(diagnostics[:_MAX_REPAIR_DIAGNOSTICS]),
                    }
                ),
            ),
        )
    )


def _preflight(
    intent: DungeonGenerationIntentV1,
    seed: int,
) -> tuple[LayoutRequest, tuple[dict[str, JsonValue], ...], bool]:
    request = compile_layout_request(intent, seed)
    topology = validate_topology(request.topology)
    if not topology.valid:
        diagnostics = _diagnostics(topology.diagnostics)
        return request, diagnostics, False

    layout = generate_layout(request)
    if not layout.success or layout.package is None:
        diagnostics = _diagnostics(layout.diagnostics)
        return request, diagnostics, False

    geometry = validate_geometry(layout.package)
    diagnostics = _diagnostics((*topology.diagnostics, *geometry.diagnostics))
    return request, diagnostics, geometry.valid


def _validate_intent_tool(value: _DungeonIntentToolInput, seed: int) -> ToolResult:
    """Return only structured deterministic validation diagnostics to the model."""

    _, diagnostics, valid = _preflight(value.intent, seed)
    return ToolResult(
        tool_name=_VALIDATE_INTENT_TOOL,
        call_id="server_validation",
        payload={"valid": valid, "diagnostics": list(diagnostics)},
    )


def _dungeon_tools(baseline_seed: int) -> dict[str, ServerTool]:
    return {
        _REVIEW_BRIEF_TOOL: ServerTool(
            name=_REVIEW_BRIEF_TOOL,
            description=(
                "Review the typed dungeon brief. The server retains all IDs, "
                "geometry, rendering, and persistence authority."
            ),
            input_schema=_DungeonIntentToolInput,
            handler=lambda value: _review_brief_tool(
                cast(_DungeonIntentToolInput, value)
            ),
        ),
        _REVIEW_TOPOLOGY_TOOL: ServerTool(
            name=_REVIEW_TOPOLOGY_TOOL,
            description=(
                "Validate typed room, connection, gate, clue, and secret-route "
                "topology without generating geometry."
            ),
            input_schema=_DungeonIntentToolInput,
            handler=lambda value: _review_topology_tool(
                cast(_DungeonIntentToolInput, value)
            ),
        ),
        _GENERATE_LAYOUT_TOOL: ServerTool(
            name=_GENERATE_LAYOUT_TOOL,
            description=(
                "Generate and validate a deterministic layout preview from typed "
                "intent. Returns only structured diagnostics and package identity."
            ),
            input_schema=_DungeonIntentToolInput,
            handler=lambda value: _generate_layout_tool(
                cast(_DungeonIntentToolInput, value), baseline_seed
            ),
        ),
        _VALIDATE_INTENT_TOOL: ServerTool(
            name=_VALIDATE_INTENT_TOOL,
            description=(
                "Validate typed dungeon brief/topology intent with deterministic "
                "topology, layout, and geometry checks."
            ),
            input_schema=_DungeonIntentToolInput,
            handler=lambda value: _validate_intent_tool(
                cast(_DungeonIntentToolInput, value), baseline_seed
            ),
        ),
        _REGENERATE_LAYOUT_TOOL: ServerTool(
            name=_REGENERATE_LAYOUT_TOOL,
            description=(
                "Preview targeted deterministic regeneration while retaining only "
                "server-generated locked component geometry."
            ),
            input_schema=_TargetedRegenerationInput,
            handler=lambda value: _regenerate_layout_tool(
                cast(_TargetedRegenerationInput, value), baseline_seed
            ),
        ),
    }


def _review_brief_tool(value: _DungeonIntentToolInput) -> ToolResult:
    _require_non_abstained_intent(value.intent, None)
    assert value.intent.brief is not None
    brief = value.intent.brief
    return ToolResult(
        tool_name=_REVIEW_BRIEF_TOOL,
        call_id="server_brief_review",
        payload={
            "brief_id": brief.id,
            "floor_count": brief.floor_count,
            "target_room_count": brief.target_room_count,
        },
    )


def _review_topology_tool(value: _DungeonIntentToolInput) -> ToolResult:
    _require_non_abstained_intent(value.intent, None)
    assert value.intent.topology is not None
    report = validate_topology(value.intent.topology)
    return ToolResult(
        tool_name=_REVIEW_TOPOLOGY_TOOL,
        call_id="server_topology_review",
        payload={
            "valid": report.valid,
            "diagnostics": list(_diagnostics(report.diagnostics)),
        },
    )


def _generate_layout_tool(value: _DungeonIntentToolInput, seed: int) -> ToolResult:
    request, diagnostics, valid = _preflight(value.intent, seed)
    return ToolResult(
        tool_name=_GENERATE_LAYOUT_TOOL,
        call_id="server_layout_generation",
        payload={
            "valid": valid,
            "package_id": request.package_id,
            "diagnostics": list(diagnostics),
        },
    )


def _regenerate_layout_tool(
    value: _TargetedRegenerationInput, baseline_seed: int
) -> ToolResult:
    request, diagnostics, valid = _preflight(value.intent, baseline_seed)
    if not valid:
        return ToolResult(
            tool_name=_REGENERATE_LAYOUT_TOOL,
            call_id="server_targeted_regeneration",
            payload={
                "valid": False,
                "diagnostics": list(diagnostics),
                "locked_component_ids": [],
            },
        )

    baseline = generate_layout(request)
    assert baseline.package is not None
    locks = _select_locked_components(baseline.package, value.locked_component_ids)
    regenerated_request = request.model_copy(
        update={"seed": value.seed, "locked": locks}
    )
    regenerated = generate_layout(regenerated_request)
    if not regenerated.success or regenerated.package is None:
        return ToolResult(
            tool_name=_REGENERATE_LAYOUT_TOOL,
            call_id="server_targeted_regeneration",
            payload={
                "valid": False,
                "diagnostics": list(_diagnostics(regenerated.diagnostics)),
                "locked_component_ids": list(locks.component_ids()),
            },
        )

    topology = validate_topology(regenerated.package.topology)
    geometry = validate_geometry(regenerated.package)
    return ToolResult(
        tool_name=_REGENERATE_LAYOUT_TOOL,
        call_id="server_targeted_regeneration",
        payload={
            "valid": topology.valid and geometry.valid,
            "diagnostics": list(
                _diagnostics((*topology.diagnostics, *geometry.diagnostics))
            ),
            "locked_component_ids": list(locks.component_ids()),
        },
    )


def _select_locked_components(
    package: DungeonPackage,
    component_ids: list[str],
) -> LockedLayoutComponents:
    selected = set(component_ids)
    known = {
        component.id
        for components in (
            package.floors,
            package.rooms,
            package.corridors,
            package.doors,
            package.stairs,
            package.vertical_links,
        )
        for component in components
    }
    if not selected <= known:
        raise ValueError("targeted regeneration requested an unknown component")
    return LockedLayoutComponents(
        floors=tuple(item for item in package.floors if item.id in selected),
        rooms=tuple(item for item in package.rooms if item.id in selected),
        corridors=tuple(item for item in package.corridors if item.id in selected),
        doors=tuple(item for item in package.doors if item.id in selected),
        stairs=tuple(item for item in package.stairs if item.id in selected),
        vertical_links=tuple(
            item for item in package.vertical_links if item.id in selected
        ),
    )


def _diagnostics(values: tuple[BaseModel, ...]) -> tuple[dict[str, JsonValue], ...]:
    documents: list[dict[str, JsonValue]] = []
    for value in values:
        dump = value.model_dump(mode="json")
        document = cast(dict[str, JsonValue], dump)
        allowed = {
            key: document[key]
            for key in ("code", "severity", "message", "affected_ids", "repair_hint")
            if key in document
        }
        documents.append(allowed)
    return tuple(documents)


def _lineage(
    intent: DungeonGenerationIntentV1,
    record: ModelRunRecord,
) -> PromptedDungeonModelLineage:
    return PromptedDungeonModelLineage(
        model_run_id=uuid.uuid4(),
        model_run=record,
        intent=intent,
    )


def _tool_run_pins(
    model_lineage: tuple[PromptedDungeonModelLineage, ...],
) -> tuple[ToolRunPin, ...]:
    return tuple(
        ToolRunPin(
            tool_name=invocation.tool_name,
            schema_version=_DUNGEON_INTENT_SCHEMA_VERSION,
            input_sha256=canonical_json_sha256(invocation.arguments),
            output_sha256=canonical_json_sha256(
                invocation.result.model_dump(mode="json")
            ),
            status="succeeded",
        )
        for lineage in model_lineage
        for invocation in lineage.model_run.tool_invocations
    )


def _remaining_profile(
    profile: ResolvedModelRunProfile,
    record: ModelRunRecord,
) -> ResolvedModelRunProfile:
    remaining_turns = profile.turn_budget - record.turn_count
    remaining_tools = profile.tool_budget - len(record.tool_invocations)
    remaining_tokens = (
        profile.token_budget - record.usage_input_tokens - record.usage_output_tokens
    )
    remaining_seconds = profile.time_budget_seconds - (
        (record.duration_ms + 999) // 1000
    )
    if (
        remaining_turns < 1
        or remaining_tools < 0
        or remaining_tokens < 1
        or remaining_seconds < 1
    ):
        raise ModelRunAbstained("no budget remains for deterministic diagnostic repair")
    return profile.model_copy(
        update={
            "turn_budget": remaining_turns,
            "tool_budget": remaining_tools,
            "token_budget": remaining_tokens,
            "time_budget_seconds": remaining_seconds,
        }
    )


def _require_non_abstained_intent(
    intent: DungeonGenerationIntentV1,
    record: ModelRunRecord | None,
) -> None:
    if intent.abstain_reason is not None:
        raise ModelRunAbstained(intent.abstain_reason)
    if intent.brief is None or intent.topology is None:
        raise ModelRunAbstained("dungeon intent did not include a brief and topology")
    if record is not None and record.status != "succeeded":
        raise ModelRunAbstained("dungeon intent run did not succeed")


def _validate_profile(profile: ResolvedModelRunProfile) -> None:
    if profile.output_schema_name != _DUNGEON_INTENT_SCHEMA_NAME:
        raise ValueError("prompted dungeon workflow requires the dungeon intent schema")
    if profile.output_schema_version != _DUNGEON_INTENT_SCHEMA_VERSION:
        raise ValueError(
            "prompted dungeon workflow requires intent schema version 1.0.0"
        )
    if profile.require_citation_ids or profile.require_authorized_citations:
        raise ValueError(
            "standalone prompted dungeon workflow cannot require citations"
        )
    if profile.allow_source_retrieval_tools:
        raise ValueError("standalone prompted dungeon workflow cannot retrieve sources")
    if tuple(profile.allowed_tools) != _DUNGEON_TOOL_NAMES:
        raise ValueError(
            "prompted dungeon workflow requires the pinned deterministic tool set"
        )


def _canonical_message(value: dict[str, object]) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
