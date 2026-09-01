"""Bounded standalone prompt-to-dungeon compilation over the pure kernel."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Literal, Protocol, cast

from pydantic import BaseModel, ConfigDict, JsonValue

from dm_assistant.adapters.model_gateway import PiGatewayClient
from dm_assistant.modules.modeling import (
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
from dm_assistant.orchestration.dungeons.contracts import (
    DUNGEON_GENERATION_PROPOSAL_SCHEMA_VERSION,
    CreatePromptedDungeonWorkflow,
    DungeonGenerationProposal,
    DungeonWorkflowResult,
    PromptDungeonWorkflow,
    PromptedDungeonModelLineage,
)
from dm_assistant.orchestration.modeling import (
    GatewayClient,
    GatewayCompletion,
    GatewayToolSchema,
    ModelRunAbstained,
    StructuredSubmissionRejected,
    StructuredSubmissionRunner,
    StructuredSubmissionTool,
)
from dm_dungeon import (
    DUNGEON_PLAN_COMPILER_VERSION,
    DungeonPlan,
    DungeonPlanCompileResult,
    LayoutRequest,
    compile_dungeon_plan,
    generate_layout,
    validate_geometry,
    validate_topology,
)
from dm_dungeon.contracts import EncounterSlotIntent, RoomRole
from dm_dungeon.layout import ORTHOGONAL_LAYOUT_GENERATOR_VERSION

_DUNGEON_CONTEXT_KIND = "dungeon_generation"
_DUNGEON_SCHEMA_NAME = "dungeon_generation_proposal"
_DUNGEON_SCHEMA_VERSION = DUNGEON_GENERATION_PROPOSAL_SCHEMA_VERSION
_SUBMIT_DUNGEON_PLAN_TOOL = "submit_dungeon_plan"
_MAX_REPAIR_ARGUMENT_CHARACTERS = 12_000
_OUTPUT_TOKEN_LIMIT = 4_096
_CUMULATIVE_TOKEN_BUDGET = 12_000
_INPUT_TOKEN_ESTIMATE_BYTES_PER_TOKEN = 4
_INPUT_TOKEN_ESTIMATE_OVERHEAD = 512
_PLAN_GUIDANCE = (
    "Plan rules: one floor and 4–8 rooms; exactly one entrance and one objective; "
    "critical_path starts at the entrance and ends at the objective. Put every other "
    "room on one of at most two ordered branches and give branch rooms the optional "
    "role. Add at most one loop between non-adjacent rooms and mark it secret only "
    "when concealment is intended. Add at most one gate on a constructed public path "
    "edge; put its key or clue in a public room reachable before that gate. Name the "
    "final objective in exactly one room_contents[].objective field for the objective "
    "room. Use room roles, encounter intent, and room_contents only as typed content "
    "slots with conservative spatial demand. Reserve only the content slots and counts "
    "the request actually needs: each non-null rooms[].encounter creates a separate later "
    "authoring task, so leave it null in every room without a requested encounter and do "
    "not repeat an encounter kind across rooms unless the request asks for multiples. Keep "
    "structural descriptions brief. "
    "Do not design puzzle solutions, exploration approaches or outcomes, room narratives, "
    "read-aloud, or complete trap and feature interactions in this call. Later bounded "
    "tasks receive exact server IDs and geometry for that work. Do not author edges, IDs, "
    "floors, coordinates, dimensions, seeds, or numeric DCs."
)


class PromptedDungeonCreator(Protocol):
    """Dungeon persistence boundary used by prompt orchestration."""

    def create_prompted(
        self,
        command: CreatePromptedDungeonWorkflow,
    ) -> DungeonWorkflowResult: ...


class DungeonSubmissionResult(BaseModel):
    """Restricted alpha V1 submission outcome before Studio persistence."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    proposal: DungeonGenerationProposal
    compilation: DungeonPlanCompileResult | None = None
    layout_request: LayoutRequest | None = None
    model_run: ModelRunRecord
    model_runs: tuple[ModelRunRecord, ...] = ()
    repaired: bool = False


def resolve_dungeon_prompt_profile(
    *,
    provider_id: str,
    model_id: str,
    capabilities: tuple[str, ...],
    context_window_tokens: int,
    output_token_limit: int,
    requested_effort: ReasoningEffort = ReasoningEffort.STANDARD,
) -> ResolvedModelRunProfile:
    """Resolve the sole one-submission dungeon profile against gateway capabilities."""
    if "tool_calls" not in capabilities:
        raise ValueError("dungeon submission requires tool-call capability")
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
        profile_id=uuid.UUID("77777777-7777-7777-7777-777777777712"),
        profile_version="1.0.0",
        task_name=_DUNGEON_SCHEMA_NAME,
        prompt_version="prompt-1",
        instruction_version="instructions-1",
        output_schema_name=_DUNGEON_SCHEMA_NAME,
        output_schema_version=_DUNGEON_SCHEMA_VERSION,
        allowed_tools=(_SUBMIT_DUNGEON_PLAN_TOOL,),
        turn_budget=1,
        tool_budget=1,
        time_budget_seconds=300,
        token_budget=min(context_window_tokens, _CUMULATIVE_TOKEN_BUDGET),
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
        override_notes={"output_token_limit": _OUTPUT_TOKEN_LIMIT},
    )


DungeonSubmissionFailureStage = Literal[
    "model_submission", "intent_compile", "deterministic_preflight"
]


@dataclass(frozen=True, slots=True)
class DungeonSubmissionFailure:
    """One body-free rejection retained for safe after-the-fact inspection."""

    attempt: Literal["initial", "repair"]
    stage: DungeonSubmissionFailureStage
    diagnostics: tuple[dict[str, JsonValue], ...]

    def report(self) -> dict[str, JsonValue]:
        """Return the bounded JSON document safe to persist on an attempt run."""
        return {
            "attempt": self.attempt,
            "stage": self.stage,
            "diagnostics": [dict(item) for item in self.diagnostics],
        }


class DungeonProposalRejectedAfterRepair(Exception):
    """The initial and one permitted replacement submissions were rejected."""

    def __init__(
        self,
        message: str = "dungeon proposal was rejected after its one repair request",
        *,
        failures: tuple[DungeonSubmissionFailure, ...] = (),
    ) -> None:
        super().__init__(message)
        self.failures = failures


class DungeonSubmissionService:
    """One compact V1 submit call followed by pure compile and preflight only."""

    def __init__(
        self,
        gateway_client: GatewayClient,
        *,
        debug: Callable[[str, dict[str, object]], None] | None = None,
    ) -> None:
        self._gateway_client = gateway_client
        self._debug = debug

    def submit(
        self,
        *,
        profile: ResolvedModelRunProfile,
        run_input: ModelRunInput,
        seed: int,
    ) -> DungeonSubmissionResult:
        _validate_profile(profile)
        compiled: DungeonPlanCompileResult | None = None
        request: LayoutRequest | None = None
        rejection_stage: DungeonSubmissionFailureStage = "model_submission"

        def handle(proposal: DungeonGenerationProposal) -> ToolResult:
            nonlocal compiled, rejection_stage, request
            if proposal.abstention is not None:
                rejection_stage = "model_submission"
                return ToolResult(
                    tool_name=_SUBMIT_DUNGEON_PLAN_TOOL,
                    call_id="server_submit",
                    payload={"accepted": False, "code": "proposal.abstained"},
                )
            assert proposal.plan is not None
            compiled = compile_dungeon_plan(proposal.plan)
            if not compiled.accepted:
                rejection_stage = "intent_compile"
                return ToolResult(
                    tool_name=_SUBMIT_DUNGEON_PLAN_TOOL,
                    call_id="server_submit",
                    payload={
                        "accepted": False,
                        "diagnostics": [
                            item.model_dump(mode="json")
                            for item in compiled.diagnostics[:8]
                        ],
                    },
                )
            assert compiled.certificate is not None
            request = _compile_layout_request(compiled, seed)
            _, diagnostics, valid = _preflight(request)
            if not valid:
                rejection_stage = "deterministic_preflight"
                return ToolResult(
                    tool_name=_SUBMIT_DUNGEON_PLAN_TOOL,
                    call_id="server_submit",
                    payload={"accepted": False, "diagnostics": list(diagnostics[:8])},
                )
            return ToolResult(
                tool_name=_SUBMIT_DUNGEON_PLAN_TOOL,
                call_id="server_submit",
                payload={
                    "accepted": True,
                    "plan_hash": compiled.input_hash,
                    "topology": {
                        "rooms": compiled.certificate.room_count,
                        "connections": compiled.certificate.connection_count,
                        "branches": len(compiled.certificate.branches),
                        "cycle_rank": compiled.certificate.cycle_rank,
                        "secret_routes": sum(
                            item.secret for item in compiled.certificate.loops
                        ),
                        "gates": len(compiled.certificate.gates),
                    },
                    "certificate_version": compiled.certificate.certificate_version,
                    "content_slots": _content_slot_summary(proposal.plan),
                    "compiler_version": DUNGEON_PLAN_COMPILER_VERSION,
                    "compiler_output_hash": compiled.output_hash or "",
                    "package_id": request.package_id,
                    "warnings": [
                        item.model_dump(mode="json") for item in compiled.warnings
                    ],
                },
            )

        runner = StructuredSubmissionRunner(self._gateway_client, debug=self._debug)
        tool = StructuredSubmissionTool(
            name=_SUBMIT_DUNGEON_PLAN_TOOL,
            description=(
                "Submit one compact structural dungeon proposal. The server owns IDs, "
                "seed, geometry, detailed enrichment, visibility, validation, "
                "persistence, and approval."
            ),
            input_schema=DungeonGenerationProposal,
        )
        deadline = time.monotonic() + profile.time_budget_seconds
        initial_failure: DungeonSubmissionFailure | None = None
        try:
            submitted, record = runner.run(
                profile=profile,
                run_input=run_input,
                tool=tool,
                handler=handle,
                deadline_monotonic=deadline,
            )
        except StructuredSubmissionRejected as rejected:
            record = rejected.record
            runs = [record]
            initial_failure = DungeonSubmissionFailure(
                attempt="initial",
                stage="model_submission",
                diagnostics=rejected.diagnostics,
            )
            repair_input = _repair_model_input(
                command=run_input,
                prior_arguments=record.tool_invocations[0].arguments,
                diagnostics=rejected.diagnostics,
            )
            repaired_profile = _remaining_submission_profile(
                profile, record, repair_input=repair_input, tool=tool
            )
            try:
                submitted, record = runner.run(
                    profile=repaired_profile,
                    run_input=repair_input,
                    tool=tool,
                    handler=handle,
                    deadline_monotonic=deadline,
                )
            except StructuredSubmissionRejected as error:
                repair_failure = DungeonSubmissionFailure(
                    attempt="repair",
                    stage="model_submission",
                    diagnostics=error.diagnostics,
                )
                raise DungeonProposalRejectedAfterRepair(
                    failures=(initial_failure, repair_failure)
                ) from error
            assert isinstance(submitted, DungeonGenerationProposal)
            runs.append(record)
            repaired = True
        else:
            assert isinstance(submitted, DungeonGenerationProposal)
            runs = [record]
            repaired = False
            result_payload = record.tool_invocations[0].result.payload
            if submitted.abstention is None and result_payload.get("accepted") is False:
                initial_failure = _submission_failure(
                    record, attempt="initial", stage=rejection_stage
                )
                repair_input = _repair_model_input(
                    command=run_input,
                    prior_arguments=record.tool_invocations[0].arguments,
                    diagnostics=initial_failure.diagnostics,
                )
                compiled = None
                request = None
                repaired_profile = _remaining_submission_profile(
                    profile, record, repair_input=repair_input, tool=tool
                )
                try:
                    submitted, record = runner.run(
                        profile=repaired_profile,
                        run_input=repair_input,
                        tool=tool,
                        handler=handle,
                        deadline_monotonic=deadline,
                    )
                except StructuredSubmissionRejected as error:
                    repair_failure = DungeonSubmissionFailure(
                        attempt="repair",
                        stage="model_submission",
                        diagnostics=error.diagnostics,
                    )
                    raise DungeonProposalRejectedAfterRepair(
                        failures=(initial_failure, repair_failure)
                    ) from error
                assert isinstance(submitted, DungeonGenerationProposal)
                runs.append(record)
                repaired = True
        if repaired and submitted.abstention is None and request is None:
            assert initial_failure is not None
            repair_failure = _submission_failure(
                record, attempt="repair", stage=rejection_stage
            )
            raise DungeonProposalRejectedAfterRepair(
                failures=(initial_failure, repair_failure)
            )
        return DungeonSubmissionResult(
            proposal=submitted,
            compilation=compiled,
            layout_request=request,
            model_run=record,
            model_runs=tuple(runs),
            repaired=repaired,
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
        debug: Callable[[str, dict[str, object]], None] | None = None,
    ) -> DungeonWorkflowResult:
        """Submit compact V1 intent then publish through the atomic Studio path."""
        context = _build_standalone_context(command)
        gateway: GatewayClient = (
            _RunBoundGatewayClient(self._gateway_client, stream_run_id)
            if stream_run_id is not None
            else self._gateway_client
        )
        submitted = DungeonSubmissionService(gateway, debug=debug).submit(
            profile=profile,
            run_input=_initial_model_input(command, context),
            seed=command.seed,
        )
        if (
            submitted.proposal.abstention is not None
            or submitted.layout_request is None
        ):
            raise ModelRunAbstained("dungeon proposal was not accepted")
        lineage = tuple(_lineage(run) for run in submitted.model_runs)
        return self._dungeon_studio.create_prompted(
            CreatePromptedDungeonWorkflow(
                campaign_id=command.campaign_id,
                title=command.title or submitted.layout_request.brief.title,
                layout_request=submitted.layout_request,
                created_by=command.created_by,
                context=context,
                model_task_profile_id=profile.task_profile_id,
                model_lineage=lineage,
                tool_runs=_tool_run_pins(lineage),
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
        debug: Callable[[str, dict[str, object]], None] | None = None,
    ) -> GatewayCompletion:
        if isinstance(self._client, PiGatewayClient):
            return self._client.complete(
                profile=profile,
                messages=messages,
                allowed_tools=allowed_tools,
                tool_schemas=tool_schemas,
                run_id=self._run_id,
                debug=debug,
            )
        if debug is not None:
            return self._client.complete(  # type: ignore[call-arg]
                profile=profile,
                messages=messages,
                allowed_tools=allowed_tools,
                tool_schemas=tool_schemas,
                debug=debug,
            )
        return self._client.complete(
            profile=profile,
            messages=messages,
            allowed_tools=allowed_tools,
            tool_schemas=tool_schemas,
        )


def _build_standalone_context(
    command: PromptDungeonWorkflow,
) -> GenerationContextPin:
    payload = DungeonGenerationContext(
        context_version="1.0.0",
        prompt_input_sha256=canonical_json_sha256({"prompt": command.prompt}),
        requested_constraints=command.requested_constraints,
        preparation_owner_id=str(command.campaign_id),
        context_provenance="dm_prompt",
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
                        "task": _DUNGEON_SCHEMA_NAME,
                        "instruction": (
                            "Use submit_dungeon_plan exactly once with proposal_version "
                            "and plan directly at the tool-argument root; do not add a "
                            "proposal envelope or guide content. Use DungeonPlan schema "
                            "version 1.0.0. Submit the smallest Tier A plan satisfying the "
                            "prompt. Copy a specifically named final objective from the DM "
                            "prompt exactly into room_contents[].objective; never substitute "
                            "a generic relic or objective. Submit compact creative intent "
                            "only; the server owns graph edges, IDs, seed, geometry, "
                            "visibility, validation, persistence, and approval. "
                            f"{_PLAN_GUIDANCE}"
                        ),
                        "prompt": command.prompt,
                        "context": context.envelope,
                    }
                ),
            ),
        )
    )


def _repair_model_input(
    *,
    command: ModelRunInput,
    prior_arguments: dict[str, JsonValue],
    diagnostics: tuple[dict[str, JsonValue], ...],
) -> ModelRunInput:
    """Build a fresh bounded repair request without losing the original task."""
    try:
        initial = json.loads(command.messages[0].content)
    except json.JSONDecodeError:
        # Direct service callers in deterministic tests predate the structured
        # prompt envelope; retain their original text as the repair task.
        initial = {"prompt": command.messages[0].content, "context": None}
    if not isinstance(initial, dict):
        raise ValueError("repair requires the original structured request")
    prior_json = _canonical_message(prior_arguments)
    if len(prior_json) > _MAX_REPAIR_ARGUMENT_CHARACTERS:
        raise ModelRunAbstained("prior proposal exceeds the bounded repair context")
    repair_document = {
        "task": _DUNGEON_SCHEMA_NAME,
        "instruction": (
            "Submit one complete corrected replacement proposal. Preserve the original "
            "requested dungeon and every valid prior field; change only fields named "
            "by the diagnostics."
        ),
        "prompt": initial.get("prompt"),
        "context": initial.get("context"),
        "previous_arguments": prior_arguments,
        "diagnostics": list(diagnostics[:8]),
    }
    return ModelRunInput(
        messages=(
            PromptMessage(role="user", content=_canonical_message(repair_document)),
        )
    )


def _content_slot_summary(plan: DungeonPlan) -> dict[str, JsonValue]:
    """Project structural content-slot counts without accepting guide prose."""

    exploration_challenges = sum(
        room.encounter is EncounterSlotIntent.EXPLORATION for room in plan.rooms
    )
    return {
        "puzzles": sum(room.role is RoomRole.PUZZLE for room in plan.rooms),
        "exploration_challenges": exploration_challenges,
        "other_encounters": sum(room.encounter is not None for room in plan.rooms)
        - exploration_challenges,
        "traps": sum(content.trap is not None for content in plan.room_contents),
        "features": sum(content.feature is not None for content in plan.room_contents),
        "objectives": sum(
            content.objective is not None for content in plan.room_contents
        ),
    }


def _compile_layout_request(
    compiled: DungeonPlanCompileResult,
    seed: int,
) -> LayoutRequest:
    """Turn accepted pure V1 output plus server seed into an exact kernel request."""
    assert (
        compiled.accepted
        and compiled.brief is not None
        and compiled.topology is not None
        and compiled.certificate is not None
        and compiled.mechanics_plan is not None
    )
    assert compiled.output_hash is not None
    return LayoutRequest(
        schema_version="1.0.0",
        package_id=f"dungeon_{canonical_json_sha256({'compiler_output_hash': compiled.output_hash, 'seed': seed})[:32]}",
        brief=compiled.brief,
        topology=compiled.topology,
        certificate=compiled.certificate,
        seed=seed,
        generator_version=ORTHOGONAL_LAYOUT_GENERATOR_VERSION,
        mechanics_plan=compiled.mechanics_plan,
        floor_bounds=compiled.floor_bounds,
    )


def _preflight(
    request: LayoutRequest,
) -> tuple[LayoutRequest, tuple[dict[str, JsonValue], ...], bool]:
    topology = validate_topology(request.topology)
    if not topology.valid:
        return request, _diagnostics(topology.diagnostics), False
    layout = generate_layout(request)
    if not layout.success or layout.package is None:
        return request, _diagnostics(layout.diagnostics), False
    geometry = validate_geometry(layout.package)
    return (
        request,
        _diagnostics((*topology.diagnostics, *geometry.diagnostics)),
        geometry.valid,
    )


def _submission_failure(
    record: ModelRunRecord,
    *,
    attempt: Literal["initial", "repair"],
    stage: DungeonSubmissionFailureStage,
) -> DungeonSubmissionFailure:
    """Extract only server-authored bounded diagnostics from one rejected call."""
    payload = record.tool_invocations[0].result.payload
    raw_diagnostics = payload.get("diagnostics")
    diagnostics: list[dict[str, JsonValue]] = []
    if isinstance(raw_diagnostics, list):
        diagnostics.extend(
            item for item in raw_diagnostics[:8] if isinstance(item, dict)
        )
    if not diagnostics:
        code = payload.get("code")
        if isinstance(code, str):
            diagnostics.append({"code": code})
    return DungeonSubmissionFailure(
        attempt=attempt,
        stage=stage,
        diagnostics=tuple(diagnostics),
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


def _lineage(record: ModelRunRecord) -> PromptedDungeonModelLineage:
    proposal: DungeonGenerationProposal | None = None
    if record.output_payload is not None:
        proposal = DungeonGenerationProposal.model_validate(record.output_payload)
    return PromptedDungeonModelLineage(
        model_run_id=uuid.uuid4(), model_run=record, proposal=proposal
    )


def _tool_run_pins(
    model_lineage: tuple[PromptedDungeonModelLineage, ...],
) -> tuple[ToolRunPin, ...]:
    return tuple(
        ToolRunPin(
            tool_name=invocation.tool_name,
            schema_version=_DUNGEON_SCHEMA_VERSION,
            input_sha256=canonical_json_sha256(invocation.arguments),
            output_sha256=canonical_json_sha256(
                invocation.result.model_dump(mode="json")
            ),
            status="succeeded",
        )
        for lineage in model_lineage
        for invocation in lineage.model_run.tool_invocations
    )


def _remaining_submission_profile(
    profile: ResolvedModelRunProfile,
    record: ModelRunRecord,
    *,
    repair_input: ModelRunInput,
    tool: StructuredSubmissionTool,
) -> ResolvedModelRunProfile:
    """Reserve one fresh repair request from the original cumulative budget."""
    if not record.usage_measured:
        raise ModelRunAbstained("model usage was unavailable; repair budget is unknown")
    assert record.usage_input_tokens is not None
    assert record.usage_output_tokens is not None
    remaining_tokens = (
        profile.token_budget - record.usage_input_tokens - record.usage_output_tokens
    )
    remaining_seconds = profile.time_budget_seconds - (
        (record.duration_ms + 999) // 1000
    )
    estimated_input_tokens = _estimated_submission_input_tokens(repair_input, tool)
    remaining_output_tokens = remaining_tokens - estimated_input_tokens
    if remaining_output_tokens < 1 or remaining_seconds < 1:
        raise ModelRunAbstained("no budget remains for deterministic diagnostic repair")
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


def _estimated_submission_input_tokens(
    run_input: ModelRunInput, tool: StructuredSubmissionTool
) -> int:
    """Estimate repair input from the complete canonical message and tool schema."""
    request_document = {
        "messages": [message.model_dump(mode="json") for message in run_input.messages],
        "tool": tool.gateway_schema().model_dump(mode="json"),
    }
    byte_size = len(_canonical_message(request_document).encode("utf-8"))
    return (
        byte_size + _INPUT_TOKEN_ESTIMATE_BYTES_PER_TOKEN - 1
    ) // _INPUT_TOKEN_ESTIMATE_BYTES_PER_TOKEN + _INPUT_TOKEN_ESTIMATE_OVERHEAD


def _validate_profile(profile: ResolvedModelRunProfile) -> None:
    if profile.output_schema_name != _DUNGEON_SCHEMA_NAME:
        raise ValueError("submission requires the dungeon proposal schema")
    if profile.output_schema_version != _DUNGEON_SCHEMA_VERSION:
        raise ValueError("submission requires proposal schema version 1.0.0")
    if profile.allowed_tools != (_SUBMIT_DUNGEON_PLAN_TOOL,):
        raise ValueError("submission exposes only submit_dungeon_plan")
    if profile.turn_budget != 1 or profile.tool_budget != 1:
        raise ValueError("submission requires exactly one turn and one tool call")
    if profile.require_citation_ids or profile.require_authorized_citations:
        raise ValueError("standalone submission cannot require citations")
    if profile.allow_source_retrieval_tools:
        raise ValueError("standalone submission cannot retrieve sources")


def _canonical_message(value: Mapping[str, object]) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
