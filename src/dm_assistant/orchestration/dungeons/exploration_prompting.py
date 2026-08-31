"""Independently bounded exact-ID exploration enrichment model task."""

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
    DUNGEON_EXPLORATION_ENRICHMENT_SCHEMA_VERSION,
    CreatePromptedDungeonExplorationWorkflow,
    DungeonExplorationEnrichmentInput,
    DungeonExplorationEnrichmentOutput,
    DungeonExplorationEnrichmentValidationResult,
    DungeonWorkflowResult,
    PromptDungeonExplorationWorkflow,
    PromptedDungeonExplorationLineage,
)
from dm_assistant.orchestration.dungeons.prompting import _RunBoundGatewayClient
from dm_assistant.orchestration.dungeons.service import (
    validate_dungeon_exploration_enrichment,
)
from dm_assistant.orchestration.modeling import (
    GatewayClient,
    ModelRunAbstained,
    StructuredSubmissionRejected,
    StructuredSubmissionRunner,
    StructuredSubmissionTool,
)

_EXPLORATION_SCHEMA_NAME = "dungeon_exploration_enrichment"
_SUBMIT_DUNGEON_EXPLORATION_TOOL = "submit_dungeon_exploration"
_OUTPUT_TOKEN_LIMIT = 2_048
_CUMULATIVE_TOKEN_BUDGET = 6_000
_MAX_REPAIR_ARGUMENT_CHARACTERS = 12_000
_INPUT_TOKEN_ESTIMATE_BYTES_PER_TOKEN = 4
_INPUT_TOKEN_ESTIMATE_OVERHEAD = 512


class PromptedExplorationPublisher(Protocol):
    """Structural protocol implemented by ``DungeonStudioService``."""

    def build_exploration_context(
        self, command: PromptDungeonExplorationWorkflow
    ) -> DungeonExplorationEnrichmentInput: ...

    def enrich_prompted_exploration(
        self, command: CreatePromptedDungeonExplorationWorkflow
    ) -> DungeonWorkflowResult: ...


class DungeonExplorationSubmissionResult(BaseModel):
    """Accepted exact-ID exploration result before child-version publication."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    context: DungeonExplorationEnrichmentInput
    validation: DungeonExplorationEnrichmentValidationResult
    model_run: ModelRunRecord
    model_runs: tuple[ModelRunRecord, ...]
    failures: tuple[DungeonExplorationSubmissionFailure, ...] = ()
    repaired: bool = False


ExplorationSubmissionFailureStage = Literal["model_submission", "semantic_validation"]


@dataclass(frozen=True, slots=True)
class DungeonExplorationSubmissionFailure:
    """One bounded exploration rejection suitable for logs and attempt reports."""

    attempt: Literal["initial", "repair"]
    stage: ExplorationSubmissionFailureStage
    diagnostics: tuple[dict[str, JsonValue], ...]

    def report(self) -> dict[str, JsonValue]:
        return {
            "attempt": self.attempt,
            "stage": self.stage,
            "diagnostics": [dict(item) for item in self.diagnostics],
        }


class DungeonExplorationRejectedAfterRepair(Exception):
    """Both independently budgeted exploration submissions were rejected."""

    def __init__(
        self,
        *,
        failures: tuple[DungeonExplorationSubmissionFailure, ...],
    ) -> None:
        super().__init__(
            "exploration enrichment was rejected after its one repair request"
        )
        self.failures = failures


def resolve_dungeon_exploration_prompt_profile(
    *,
    provider_id: str,
    model_id: str,
    capabilities: tuple[str, ...],
    context_window_tokens: int,
    output_token_limit: int,
    requested_effort: ReasoningEffort = ReasoningEffort.STANDARD,
) -> ResolvedModelRunProfile:
    """Resolve the exploration task independently from structural generation."""

    if "tool_calls" not in capabilities:
        raise ValueError("exploration enrichment requires tool-call capability")
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
        profile_id=uuid.UUID("77777777-7777-7777-7777-777777777714"),
        profile_version="1.0.0",
        task_name=_EXPLORATION_SCHEMA_NAME,
        prompt_version="exploration-prompt-1",
        instruction_version="exploration-instructions-1",
        output_schema_name=_EXPLORATION_SCHEMA_NAME,
        output_schema_version=DUNGEON_EXPLORATION_ENRICHMENT_SCHEMA_VERSION,
        allowed_tools=(_SUBMIT_DUNGEON_EXPLORATION_TOOL,),
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


class DungeonExplorationSubmissionService:
    """Run one exploration-only tool call plus at most one bounded repair."""

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
        context: DungeonExplorationEnrichmentInput,
    ) -> DungeonExplorationSubmissionResult:
        _validate_profile(profile)
        runner = StructuredSubmissionRunner(self._gateway_client, debug=self._debug)
        tool = StructuredSubmissionTool(
            name=_SUBMIT_DUNGEON_EXPLORATION_TOOL,
            description=(
                "Submit one exploration challenge for the exact package, room, encounter "
                "slot, and approved affordances in the supplied context. Do not change "
                "topology, geometry, visibility, or arithmetic."
            ),
            input_schema=DungeonExplorationEnrichmentOutput,
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
            return DungeonExplorationSubmissionResult(
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
            raise DungeonExplorationRejectedAfterRepair(
                failures=(initial.failure, repair.failure)
            )
        output, validation, record = repair.accepted
        return DungeonExplorationSubmissionResult(
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
        context: DungeonExplorationEnrichmentInput,
        deadline: float,
        attempt: Literal["initial", "repair"],
    ) -> _ExplorationAttempt:
        validation: DungeonExplorationEnrichmentValidationResult | None = None

        def handle(output: DungeonExplorationEnrichmentOutput) -> ToolResult:
            nonlocal validation
            validation = validate_dungeon_exploration_enrichment(context, output)
            diagnostics = _semantic_diagnostics(validation)
            return ToolResult(
                tool_name=_SUBMIT_DUNGEON_EXPLORATION_TOOL,
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
            return _ExplorationAttempt(
                record=error.record,
                failure=DungeonExplorationSubmissionFailure(
                    attempt=attempt,
                    stage="model_submission",
                    diagnostics=error.diagnostics,
                ),
            )
        assert isinstance(submitted, DungeonExplorationEnrichmentOutput)
        assert validation is not None
        if validation.accepted_output is None:
            return _ExplorationAttempt(
                record=record,
                failure=DungeonExplorationSubmissionFailure(
                    attempt=attempt,
                    stage="semantic_validation",
                    diagnostics=_semantic_diagnostics(validation),
                ),
            )
        return _ExplorationAttempt(
            record=record,
            failure=None,
            accepted=(submitted, validation, record),
        )


@dataclass(frozen=True, slots=True)
class _ExplorationAttempt:
    record: ModelRunRecord
    failure: DungeonExplorationSubmissionFailure | None
    accepted: (
        tuple[
            DungeonExplorationEnrichmentOutput,
            DungeonExplorationEnrichmentValidationResult,
            ModelRunRecord,
        ]
        | None
    ) = None

    def __post_init__(self) -> None:
        if (self.failure is None) == (self.accepted is None):
            raise ValueError("exploration attempt requires exactly one outcome")


class DungeonExplorationPromptService:
    """Run one exact exploration task and publish an immutable guide child version."""

    def __init__(
        self,
        dungeon_studio: PromptedExplorationPublisher,
        gateway_client: GatewayClient,
    ) -> None:
        self._dungeon_studio = dungeon_studio
        self._gateway_client = gateway_client

    def prepare_context(
        self, command: PromptDungeonExplorationWorkflow
    ) -> DungeonExplorationEnrichmentInput:
        return self._dungeon_studio.build_exploration_context(command)

    def create(
        self,
        command: PromptDungeonExplorationWorkflow,
        profile: ResolvedModelRunProfile,
        *,
        context: DungeonExplorationEnrichmentInput | None = None,
        stream_run_id: str | None = None,
        debug: Callable[[str, dict[str, object]], None] | None = None,
    ) -> DungeonWorkflowResult:
        exact_context = context or self.prepare_context(command)
        gateway: GatewayClient = (
            _RunBoundGatewayClient(self._gateway_client, stream_run_id)
            if stream_run_id is not None
            else self._gateway_client
        )
        submitted = DungeonExplorationSubmissionService(gateway, debug=debug).submit(
            profile=profile,
            context=exact_context,
        )
        accepted_output = submitted.validation.accepted_output
        assert accepted_output is not None
        lineage = PromptedDungeonExplorationLineage(
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
        return self._dungeon_studio.enrich_prompted_exploration(
            CreatePromptedDungeonExplorationWorkflow(
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


def _initial_model_input(context: DungeonExplorationEnrichmentInput) -> ModelRunInput:
    return ModelRunInput(
        messages=(
            PromptMessage(
                role="user",
                content=_canonical_message(
                    {
                        "task": _EXPLORATION_SCHEMA_NAME,
                        "instruction": (
                            "Use submit_dungeon_exploration exactly once. Design only the "
                            "requested exploration challenge from the supplied exact context. "
                            "Preserve the package, room, encounter-slot, and approved "
                            "affordance IDs. Propose observable cues, multiple reasonable "
                            "approaches and consequences, escalation, and recovery. Do not "
                            "invent topology, geometry, numeric difficulty, puzzle content, "
                            "approval, or canonical state."
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
        raise ModelRunAbstained("prior exploration exceeds the bounded repair context")
    initial_document = json.loads(initial_input.messages[0].content)
    return ModelRunInput(
        messages=(
            PromptMessage(
                role="user",
                content=_canonical_message(
                    {
                        "task": _EXPLORATION_SCHEMA_NAME,
                        "instruction": (
                            "Submit one complete corrected exploration. Preserve all valid "
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
    validation: DungeonExplorationEnrichmentValidationResult,
) -> tuple[dict[str, JsonValue], ...]:
    paths = {
        "exploration_enrichment.package_mismatch": "/package_id",
        "exploration_enrichment.room_mismatch": "/room_id",
        "exploration_enrichment.encounter_slot_mismatch": "/encounter_slot_id",
        "exploration_enrichment.affordance_invalid": "/approaches",
    }
    repairs = {
        "exploration_enrichment.package_mismatch": "use the exact context package ID",
        "exploration_enrichment.room_mismatch": "use the exact context exploration room ID",
        "exploration_enrichment.encounter_slot_mismatch": (
            "use the exact context encounter-slot ID"
        ),
        "exploration_enrichment.affordance_invalid": (
            "use only affordance IDs supplied in the context"
        ),
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


def _tool_run_pin(lineage: PromptedDungeonExplorationLineage) -> ToolRunPin:
    invocation = lineage.model_run.tool_invocations[0]
    return ToolRunPin(
        tool_name=invocation.tool_name,
        schema_version=DUNGEON_EXPLORATION_ENRICHMENT_SCHEMA_VERSION,
        input_sha256=canonical_json_sha256(invocation.arguments),
        output_sha256=canonical_json_sha256(invocation.result.model_dump(mode="json")),
        status="succeeded",
    )


def _validate_profile(profile: ResolvedModelRunProfile) -> None:
    if profile.output_schema_name != _EXPLORATION_SCHEMA_NAME:
        raise ValueError(
            "exploration submission requires the exploration enrichment schema"
        )
    if profile.output_schema_version != DUNGEON_EXPLORATION_ENRICHMENT_SCHEMA_VERSION:
        raise ValueError("exploration submission requires schema version 1.0.0")
    if profile.allowed_tools != (_SUBMIT_DUNGEON_EXPLORATION_TOOL,):
        raise ValueError(
            "exploration submission exposes only submit_dungeon_exploration"
        )
    if profile.turn_budget != 1 or profile.tool_budget != 1:
        raise ValueError("exploration submission requires one turn and one tool call")
    if profile.require_citation_ids or profile.require_authorized_citations:
        raise ValueError("standalone exploration submission cannot require citations")
    if profile.allow_source_retrieval_tools:
        raise ValueError("standalone exploration submission cannot retrieve sources")
    if profile.override_notes.get("repair_limit") != 1:
        raise ValueError("exploration submission permits exactly one schema repair")


def _canonical_message(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
