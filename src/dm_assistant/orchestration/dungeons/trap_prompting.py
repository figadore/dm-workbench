"""Independently bounded exact-ID trap enrichment model task."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, JsonValue

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
from dm_assistant.modules.preparation import ToolRunPin, canonical_json_sha256
from dm_assistant.orchestration.dungeons.contracts import (
    DUNGEON_TRAP_ENRICHMENT_SCHEMA_VERSION,
    CreatePromptedDungeonTrapWorkflow,
    DungeonTrapEnrichmentInput,
    DungeonTrapEnrichmentOutput,
    DungeonTrapValidationResult,
    DungeonWorkflowResult,
    PromptDungeonTrapWorkflow,
    PromptedDungeonTrapLineage,
)
from dm_assistant.orchestration.dungeons.prompting import _RunBoundGatewayClient
from dm_assistant.orchestration.dungeons.service import (
    validate_dungeon_trap_enrichment,
)
from dm_assistant.orchestration.modeling import (
    GatewayClient,
    ModelRunAbstained,
    StructuredSubmissionRejected,
    StructuredSubmissionRunner,
    StructuredSubmissionTool,
)

_TRAP_SCHEMA_NAME = "dungeon_trap_enrichment"
_SUBMIT_DUNGEON_TRAP_TOOL = "submit_dungeon_trap"
_OUTPUT_TOKEN_LIMIT = 2_048
_CUMULATIVE_TOKEN_BUDGET = 6_000
_MAX_REPAIR_ARGUMENT_CHARACTERS = 12_000
_INPUT_TOKEN_ESTIMATE_BYTES_PER_TOKEN = 4
_INPUT_TOKEN_ESTIMATE_OVERHEAD = 512


class PromptedTrapPublisher(Protocol):
    """Structural protocol implemented by ``DungeonStudioService``."""

    def build_trap_context(
        self, command: PromptDungeonTrapWorkflow
    ) -> DungeonTrapEnrichmentInput: ...

    def enrich_prompted_trap(
        self, command: CreatePromptedDungeonTrapWorkflow
    ) -> DungeonWorkflowResult: ...


class DungeonTrapSubmissionResult(BaseModel):
    """Accepted exact-ID trap result before child-version publication."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    context: DungeonTrapEnrichmentInput
    validation: DungeonTrapValidationResult
    model_run: ModelRunRecord
    model_runs: tuple[ModelRunRecord, ...]
    failures: tuple[DungeonTrapSubmissionFailure, ...] = ()
    repaired: bool = False


TrapSubmissionFailureStage = Literal["model_submission", "semantic_validation"]


@dataclass(frozen=True, slots=True)
class DungeonTrapSubmissionFailure:
    """One bounded trap rejection suitable for logs and attempt reports."""

    attempt: Literal["initial", "repair"]
    stage: TrapSubmissionFailureStage
    diagnostics: tuple[dict[str, JsonValue], ...]

    def report(self) -> dict[str, JsonValue]:
        return {
            "attempt": self.attempt,
            "stage": self.stage,
            "diagnostics": [dict(item) for item in self.diagnostics],
        }


class DungeonTrapRejectedAfterRepair(Exception):
    """Both independently budgeted trap submissions were rejected."""

    def __init__(
        self,
        *,
        failures: tuple[DungeonTrapSubmissionFailure, ...],
    ) -> None:
        super().__init__("trap enrichment was rejected after its one repair request")
        self.failures = failures


def resolve_dungeon_trap_prompt_profile(
    *,
    provider_id: str,
    model_id: str,
    capabilities: tuple[str, ...],
    context_window_tokens: int,
    output_token_limit: int,
    requested_effort: ReasoningEffort = ReasoningEffort.STANDARD,
) -> ResolvedModelRunProfile:
    """Resolve the trap task independently from structural generation."""

    if "tool_calls" not in capabilities:
        raise ValueError("trap enrichment requires tool-call capability")
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
        profile_id=uuid.UUID("77777777-7777-7777-7777-777777777716"),
        profile_version="1.0.0",
        task_name=_TRAP_SCHEMA_NAME,
        prompt_version="trap-prompt-1",
        instruction_version="trap-instructions-1",
        output_schema_name=_TRAP_SCHEMA_NAME,
        output_schema_version=DUNGEON_TRAP_ENRICHMENT_SCHEMA_VERSION,
        allowed_tools=(_SUBMIT_DUNGEON_TRAP_TOOL,),
        turn_budget=1,
        tool_budget=1,
        time_budget_seconds=180,
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
        override_notes={"output_token_limit": _OUTPUT_TOKEN_LIMIT, "repair_limit": 1},
    )


class DungeonTrapSubmissionService:
    """Run one trap-only tool call plus at most one bounded repair."""

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
        context: DungeonTrapEnrichmentInput,
    ) -> DungeonTrapSubmissionResult:
        _validate_profile(profile)
        runner = StructuredSubmissionRunner(self._gateway_client, debug=self._debug)
        tool = StructuredSubmissionTool(
            name=_SUBMIT_DUNGEON_TRAP_TOOL,
            description=(
                "Submit warning, trigger/effect, counterplay, consequences, and optional "
                "recovery for the exact package, room, and trap in the supplied context. "
                "Do not change topology, geometry, visibility, deterministic arithmetic, "
                "or content accepted by another task."
            ),
            input_schema=DungeonTrapEnrichmentOutput,
        )
        deadline = time.monotonic() + profile.time_budget_seconds
        initial_input = _initial_model_input(context)
        initial = self._run_once(
            runner=runner,
            tool=tool,
            profile=profile,
            run_input=initial_input,
            context=context,
            deadline=deadline,
            attempt="initial",
        )
        if initial.accepted is not None:
            output, validation, record = initial.accepted
            return DungeonTrapSubmissionResult(
                context=context,
                validation=validation,
                model_run=record,
                model_runs=(record,),
            )

        assert initial.failure is not None
        repair_input = _repair_model_input(
            initial_input=initial_input,
            prior_arguments=initial.record.tool_invocations[0].arguments,
            diagnostics=initial.failure.diagnostics,
        )
        repair_profile = _remaining_profile(
            profile,
            initial.record,
            repair_input=repair_input,
            tool=tool,
        )
        repair = self._run_once(
            runner=runner,
            tool=tool,
            profile=repair_profile,
            run_input=repair_input,
            context=context,
            deadline=deadline,
            attempt="repair",
        )
        if repair.accepted is None:
            assert repair.failure is not None
            raise DungeonTrapRejectedAfterRepair(
                failures=(initial.failure, repair.failure)
            )
        output, validation, record = repair.accepted
        return DungeonTrapSubmissionResult(
            context=context,
            validation=validation,
            model_run=record,
            model_runs=(initial.record, record),
            failures=(initial.failure,),
            repaired=True,
        )

    def _run_once(
        self,
        *,
        runner: StructuredSubmissionRunner,
        tool: StructuredSubmissionTool,
        profile: ResolvedModelRunProfile,
        run_input: ModelRunInput,
        context: DungeonTrapEnrichmentInput,
        deadline: float,
        attempt: Literal["initial", "repair"],
    ) -> _TrapAttempt:
        validation: DungeonTrapValidationResult | None = None

        def handle(output: DungeonTrapEnrichmentOutput) -> ToolResult:
            nonlocal validation
            validation = validate_dungeon_trap_enrichment(context, output)
            diagnostics = _semantic_diagnostics(validation)
            return ToolResult(
                tool_name=_SUBMIT_DUNGEON_TRAP_TOOL,
                call_id="server_submit",
                payload={
                    "accepted": validation.accepted_output is not None,
                    "diagnostics": list(diagnostics),
                },
            )

        try:
            submitted, record = runner.run(
                profile=profile,
                run_input=run_input,
                tool=tool,
                handler=handle,
                deadline_monotonic=deadline,
            )
        except StructuredSubmissionRejected as error:
            return _TrapAttempt(
                record=error.record,
                failure=DungeonTrapSubmissionFailure(
                    attempt=attempt,
                    stage="model_submission",
                    diagnostics=error.diagnostics,
                ),
            )
        assert isinstance(submitted, DungeonTrapEnrichmentOutput)
        assert validation is not None
        if validation.accepted_output is None:
            return _TrapAttempt(
                record=record,
                failure=DungeonTrapSubmissionFailure(
                    attempt=attempt,
                    stage="semantic_validation",
                    diagnostics=_semantic_diagnostics(validation),
                ),
            )
        return _TrapAttempt(
            record=record,
            failure=None,
            accepted=(submitted, validation, record),
        )


@dataclass(frozen=True, slots=True)
class _TrapAttempt:
    record: ModelRunRecord
    failure: DungeonTrapSubmissionFailure | None
    accepted: (
        tuple[
            DungeonTrapEnrichmentOutput,
            DungeonTrapValidationResult,
            ModelRunRecord,
        ]
        | None
    ) = None

    def __post_init__(self) -> None:
        if (self.failure is None) == (self.accepted is None):
            raise ValueError("trap attempt requires exactly one outcome")


class DungeonTrapPromptService:
    """Run one exact trap task and publish an immutable guide child version."""

    def __init__(
        self,
        dungeon_studio: PromptedTrapPublisher,
        gateway_client: GatewayClient,
    ) -> None:
        self._dungeon_studio = dungeon_studio
        self._gateway_client = gateway_client

    def prepare_context(
        self, command: PromptDungeonTrapWorkflow
    ) -> DungeonTrapEnrichmentInput:
        return self._dungeon_studio.build_trap_context(command)

    def create(
        self,
        command: PromptDungeonTrapWorkflow,
        profile: ResolvedModelRunProfile,
        *,
        context: DungeonTrapEnrichmentInput | None = None,
        stream_run_id: str | None = None,
        debug: Callable[[str, dict[str, object]], None] | None = None,
    ) -> DungeonWorkflowResult:
        exact_context = context or self.prepare_context(command)
        gateway: GatewayClient = (
            _RunBoundGatewayClient(self._gateway_client, stream_run_id)
            if stream_run_id is not None
            else self._gateway_client
        )
        submitted = DungeonTrapSubmissionService(gateway, debug=debug).submit(
            profile=profile,
            context=exact_context,
        )
        accepted_output = submitted.validation.accepted_output
        assert accepted_output is not None
        lineage = PromptedDungeonTrapLineage(
            model_run_id=uuid.uuid4(),
            context_sha256=canonical_json_sha256(exact_context.model_dump(mode="json")),
            creative_continuity_version=(exact_context.continuity.projection_version),
            creative_continuity_sha256=(exact_context.continuity.projection_sha256),
            selected_fact_ids=tuple(
                fact.fact_id for fact in exact_context.continuity.selected_facts
            ),
            source_ids=tuple(
                source.source_id for source in exact_context.continuity.source_links
            ),
            model_run=submitted.model_run.model_copy(
                update={"run_input": _initial_model_input(exact_context)}
            ),
            output=accepted_output,
        )
        return self._dungeon_studio.enrich_prompted_trap(
            CreatePromptedDungeonTrapWorkflow(
                campaign_id=command.campaign_id,
                artifact_id=command.artifact_id,
                parent_version_id=command.parent_version_id,
                context=exact_context,
                validation=submitted.validation,
                model_task_profile_id=profile.task_profile_id,
                model_lineage=lineage,
                tool_runs=(_tool_run_pin(lineage),),
                created_by=command.created_by,
            )
        )


def _initial_model_input(
    context: DungeonTrapEnrichmentInput,
) -> ModelRunInput:
    return ModelRunInput(
        messages=(
            PromptMessage(
                role="user",
                content=_canonical_message(
                    {
                        "task": _TRAP_SCHEMA_NAME,
                        "instruction": (
                            "Use submit_dungeon_trap exactly once. Design only the requested "
                            "trap for the supplied exact marker. Preserve the package, room, "
                            "and trap IDs. Supply an observable warning, the actual trigger "
                            "and effect, practical detection and disable counterplay, one to "
                            "four consequences, and reset or recovery only when useful. Do "
                            "not state numeric difficulties or invent topology, geometry, "
                            "other task content, approval, or canonical state."
                        ),
                        "context": context.model_dump(mode="json"),
                    }
                ),
            ),
        )
    )


def _repair_model_input(
    *,
    initial_input: ModelRunInput,
    prior_arguments: dict[str, JsonValue],
    diagnostics: tuple[dict[str, JsonValue], ...],
) -> ModelRunInput:
    prior_json = _canonical_message(prior_arguments)
    if len(prior_json) > _MAX_REPAIR_ARGUMENT_CHARACTERS:
        raise ModelRunAbstained("prior trap exceeds the bounded repair context")
    initial_document = json.loads(initial_input.messages[0].content)
    return ModelRunInput(
        messages=(
            PromptMessage(
                role="user",
                content=_canonical_message(
                    {
                        "task": _TRAP_SCHEMA_NAME,
                        "instruction": (
                            "Submit one complete corrected trap. Preserve all valid "
                            "fields and exact IDs; change only fields named by diagnostics."
                        ),
                        "context": initial_document["context"],
                        "previous_arguments": prior_arguments,
                        "diagnostics": list(diagnostics[:8]),
                    }
                ),
            ),
        )
    )


def _semantic_diagnostics(
    validation: DungeonTrapValidationResult,
) -> tuple[dict[str, JsonValue], ...]:
    paths = {
        "trap_enrichment.package_mismatch": "/package_id",
        "trap_enrichment.room_mismatch": "/room_id",
        "trap_enrichment.trap_mismatch": "/trap_id",
    }
    repairs = {
        "trap_enrichment.package_mismatch": "use the exact context package ID",
        "trap_enrichment.room_mismatch": "use the exact context trap room ID",
        "trap_enrichment.trap_mismatch": "use the exact context trap ID",
    }
    return tuple(
        {
            "code": issue.code,
            "path": paths[issue.code],
            "repair": repairs[issue.code],
        }
        for issue in validation.issues[:8]
    )


def _remaining_profile(
    profile: ResolvedModelRunProfile,
    record: ModelRunRecord,
    *,
    repair_input: ModelRunInput,
    tool: StructuredSubmissionTool,
) -> ResolvedModelRunProfile:
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
    estimated_input_tokens = _estimated_input_tokens(repair_input, tool)
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


def _estimated_input_tokens(
    run_input: ModelRunInput, tool: StructuredSubmissionTool
) -> int:
    request_document = {
        "messages": [message.model_dump(mode="json") for message in run_input.messages],
        "tool": tool.gateway_schema().model_dump(mode="json"),
    }
    byte_size = len(_canonical_message(request_document).encode("utf-8"))
    return (
        byte_size + _INPUT_TOKEN_ESTIMATE_BYTES_PER_TOKEN - 1
    ) // _INPUT_TOKEN_ESTIMATE_BYTES_PER_TOKEN + _INPUT_TOKEN_ESTIMATE_OVERHEAD


def _tool_run_pin(lineage: PromptedDungeonTrapLineage) -> ToolRunPin:
    invocation = lineage.model_run.tool_invocations[0]
    return ToolRunPin(
        tool_name=invocation.tool_name,
        schema_version=DUNGEON_TRAP_ENRICHMENT_SCHEMA_VERSION,
        input_sha256=canonical_json_sha256(invocation.arguments),
        output_sha256=canonical_json_sha256(invocation.result.model_dump(mode="json")),
        status="succeeded",
    )


def _validate_profile(profile: ResolvedModelRunProfile) -> None:
    if profile.output_schema_name != _TRAP_SCHEMA_NAME:
        raise ValueError("trap submission requires the trap enrichment schema")
    if profile.output_schema_version != DUNGEON_TRAP_ENRICHMENT_SCHEMA_VERSION:
        raise ValueError("trap submission requires schema version 1.0.0")
    if profile.allowed_tools != (_SUBMIT_DUNGEON_TRAP_TOOL,):
        raise ValueError("trap submission exposes only submit_dungeon_trap")
    if profile.turn_budget != 1 or profile.tool_budget != 1:
        raise ValueError("trap submission requires one turn and one tool call")
    if profile.require_citation_ids or profile.require_authorized_citations:
        raise ValueError("standalone trap submission cannot require citations")
    if profile.allow_source_retrieval_tools:
        raise ValueError("standalone trap submission cannot retrieve sources")
    if profile.override_notes.get("repair_limit") != 1:
        raise ValueError("trap submission permits exactly one schema repair")


def _canonical_message(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
