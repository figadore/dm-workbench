"""Independently bounded exact-ID feature interaction enrichment model task."""

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
    DUNGEON_FEATURE_INTERACTION_ENRICHMENT_SCHEMA_VERSION,
    CreatePromptedDungeonFeatureInteractionWorkflow,
    DungeonFeatureInteractionEnrichmentInput,
    DungeonFeatureInteractionEnrichmentOutput,
    DungeonFeatureInteractionValidationResult,
    DungeonWorkflowResult,
    PromptDungeonFeatureInteractionWorkflow,
    PromptedDungeonFeatureInteractionLineage,
)
from dm_assistant.orchestration.dungeons.prompting import (
    _model_call_measurement,
    _RunBoundGatewayClient,
)
from dm_assistant.orchestration.dungeons.service import (
    validate_dungeon_feature_interaction_enrichment,
)
from dm_assistant.orchestration.modeling import (
    GatewayClient,
    ModelRunAbstained,
    StructuredSubmissionRejected,
    StructuredSubmissionRunner,
    StructuredSubmissionTool,
    reserve_structured_submission_repair,
)

_FEATURE_INTERACTION_SCHEMA_NAME = "dungeon_feature_interaction_enrichment"
_SUBMIT_DUNGEON_FEATURE_INTERACTION_TOOL = "submit_dungeon_feature_interaction"
_OUTPUT_TOKEN_LIMIT = 2_048
_CUMULATIVE_TOKEN_BUDGET = 6_000
_MAX_REPAIR_ARGUMENT_CHARACTERS = 12_000


class PromptedFeatureInteractionPublisher(Protocol):
    """Structural protocol implemented by ``DungeonStudioService``."""

    def build_feature_interaction_context(
        self, command: PromptDungeonFeatureInteractionWorkflow
    ) -> DungeonFeatureInteractionEnrichmentInput: ...

    def enrich_prompted_feature_interaction(
        self, command: CreatePromptedDungeonFeatureInteractionWorkflow
    ) -> DungeonWorkflowResult: ...


class DungeonFeatureInteractionSubmissionResult(BaseModel):
    """Accepted exact-ID feature interaction result before child-version publication."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    context: DungeonFeatureInteractionEnrichmentInput
    validation: DungeonFeatureInteractionValidationResult
    model_run: ModelRunRecord
    model_runs: tuple[ModelRunRecord, ...]
    failures: tuple[DungeonFeatureInteractionSubmissionFailure, ...] = ()
    repaired: bool = False


FeatureInteractionSubmissionFailureStage = Literal[
    "model_submission", "semantic_validation"
]


@dataclass(frozen=True, slots=True)
class DungeonFeatureInteractionSubmissionFailure:
    """One bounded feature interaction rejection suitable for logs and attempt reports."""

    attempt: Literal["initial", "repair"]
    stage: FeatureInteractionSubmissionFailureStage
    diagnostics: tuple[dict[str, JsonValue], ...]

    def report(self) -> dict[str, JsonValue]:
        return {
            "attempt": self.attempt,
            "stage": self.stage,
            "diagnostics": [dict(item) for item in self.diagnostics],
        }


class DungeonFeatureInteractionRejectedAfterRepair(Exception):
    """Both independently budgeted feature interaction submissions were rejected."""

    def __init__(
        self,
        *,
        failures: tuple[DungeonFeatureInteractionSubmissionFailure, ...],
    ) -> None:
        super().__init__(
            "feature interaction enrichment was rejected after its one repair request"
        )
        self.failures = failures


def resolve_dungeon_feature_interaction_prompt_profile(
    *,
    provider_id: str,
    model_id: str,
    capabilities: tuple[str, ...],
    context_window_tokens: int,
    output_token_limit: int,
    requested_effort: ReasoningEffort = ReasoningEffort.STANDARD,
) -> ResolvedModelRunProfile:
    """Resolve the feature interaction task independently from structural generation."""

    if "tool_calls" not in capabilities:
        raise ValueError("feature interaction enrichment requires tool-call capability")
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
        profile_id=uuid.UUID("77777777-7777-7777-7777-777777777715"),
        profile_version="1.0.0",
        task_name=_FEATURE_INTERACTION_SCHEMA_NAME,
        prompt_version="feature-interaction-prompt-1",
        instruction_version="feature-interaction-instructions-1",
        output_schema_name=_FEATURE_INTERACTION_SCHEMA_NAME,
        output_schema_version=DUNGEON_FEATURE_INTERACTION_ENRICHMENT_SCHEMA_VERSION,
        allowed_tools=(_SUBMIT_DUNGEON_FEATURE_INTERACTION_TOOL,),
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


class DungeonFeatureInteractionSubmissionService:
    """Run one feature interaction-only tool call plus at most one bounded repair."""

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
        context: DungeonFeatureInteractionEnrichmentInput,
    ) -> DungeonFeatureInteractionSubmissionResult:
        _validate_profile(profile)
        runner = StructuredSubmissionRunner(self._gateway_client, debug=self._debug)
        tool = StructuredSubmissionTool(
            name=_SUBMIT_DUNGEON_FEATURE_INTERACTION_TOOL,
            description=(
                "Submit one interaction for the exact package, room, and feature in the "
                "supplied context. Do not change topology, geometry, visibility, "
                "arithmetic, puzzle content, or exploration content."
            ),
            input_schema=DungeonFeatureInteractionEnrichmentOutput,
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
            return DungeonFeatureInteractionSubmissionResult(
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
            raise DungeonFeatureInteractionRejectedAfterRepair(
                failures=(initial.failure, repair.failure)
            )
        output, validation, record = repair.accepted
        return DungeonFeatureInteractionSubmissionResult(
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
        context: DungeonFeatureInteractionEnrichmentInput,
        deadline: float,
        attempt: Literal["initial", "repair"],
    ) -> _FeatureInteractionAttempt:
        validation: DungeonFeatureInteractionValidationResult | None = None

        def handle(output: DungeonFeatureInteractionEnrichmentOutput) -> ToolResult:
            nonlocal validation
            validation = validate_dungeon_feature_interaction_enrichment(
                context, output
            )
            diagnostics = _semantic_diagnostics(validation)
            return ToolResult(
                tool_name=_SUBMIT_DUNGEON_FEATURE_INTERACTION_TOOL,
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
            return _FeatureInteractionAttempt(
                record=error.record,
                failure=DungeonFeatureInteractionSubmissionFailure(
                    attempt=attempt,
                    stage="model_submission",
                    diagnostics=error.diagnostics,
                ),
            )
        assert isinstance(submitted, DungeonFeatureInteractionEnrichmentOutput)
        assert validation is not None
        if validation.accepted_output is None:
            return _FeatureInteractionAttempt(
                record=record,
                failure=DungeonFeatureInteractionSubmissionFailure(
                    attempt=attempt,
                    stage="semantic_validation",
                    diagnostics=_semantic_diagnostics(validation),
                ),
            )
        return _FeatureInteractionAttempt(
            record=record,
            failure=None,
            accepted=(submitted, validation, record),
        )


@dataclass(frozen=True, slots=True)
class _FeatureInteractionAttempt:
    record: ModelRunRecord
    failure: DungeonFeatureInteractionSubmissionFailure | None
    accepted: (
        tuple[
            DungeonFeatureInteractionEnrichmentOutput,
            DungeonFeatureInteractionValidationResult,
            ModelRunRecord,
        ]
        | None
    ) = None

    def __post_init__(self) -> None:
        if (self.failure is None) == (self.accepted is None):
            raise ValueError("feature interaction attempt requires exactly one outcome")


class DungeonFeatureInteractionPromptService:
    """Run one exact feature interaction task and publish an immutable guide child version."""

    def __init__(
        self,
        dungeon_studio: PromptedFeatureInteractionPublisher,
        gateway_client: GatewayClient,
    ) -> None:
        self._dungeon_studio = dungeon_studio
        self._gateway_client = gateway_client

    def prepare_context(
        self, command: PromptDungeonFeatureInteractionWorkflow
    ) -> DungeonFeatureInteractionEnrichmentInput:
        return self._dungeon_studio.build_feature_interaction_context(command)

    def create(
        self,
        command: PromptDungeonFeatureInteractionWorkflow,
        profile: ResolvedModelRunProfile,
        *,
        context: DungeonFeatureInteractionEnrichmentInput | None = None,
        stream_run_id: str | None = None,
        debug: Callable[[str, dict[str, object]], None] | None = None,
    ) -> DungeonWorkflowResult:
        exact_context = context or self.prepare_context(command)
        gateway: GatewayClient = (
            _RunBoundGatewayClient(self._gateway_client, stream_run_id)
            if stream_run_id is not None
            else self._gateway_client
        )
        submitted = DungeonFeatureInteractionSubmissionService(
            gateway, debug=debug
        ).submit(
            profile=profile,
            context=exact_context,
        )
        accepted_output = submitted.validation.accepted_output
        assert accepted_output is not None
        lineage = PromptedDungeonFeatureInteractionLineage(
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
        result = self._dungeon_studio.enrich_prompted_feature_interaction(
            CreatePromptedDungeonFeatureInteractionWorkflow(
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
        return result.model_copy(
            update={"model_measurement": _model_call_measurement(submitted.model_runs)}
        )


def _initial_model_input(
    context: DungeonFeatureInteractionEnrichmentInput,
) -> ModelRunInput:
    return ModelRunInput(
        messages=(
            PromptMessage(
                role="user",
                content=_canonical_message(
                    {
                        "task": _FEATURE_INTERACTION_SCHEMA_NAME,
                        "instruction": (
                            "Use submit_dungeon_feature_interaction exactly once. Design "
                            "only the requested interaction for the supplied exact feature. "
                            "Preserve the package, room, and feature IDs. Propose observable "
                            "setup, two to four reasonable affordances with consequences, "
                            "and reset or retry guidance only when useful. Do not invent "
                            "topology, geometry, numeric difficulty, puzzle or exploration "
                            "content, approval, or canonical state."
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
        raise ModelRunAbstained(
            "prior feature interaction exceeds the bounded repair context",
            code="repair_context_exceeded",
        )
    initial_document = json.loads(initial_input.messages[0].content)
    return ModelRunInput(
        messages=(
            PromptMessage(
                role="user",
                content=_canonical_message(
                    {
                        "task": _FEATURE_INTERACTION_SCHEMA_NAME,
                        "instruction": (
                            "Submit one complete corrected feature interaction. Preserve all valid "
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
    validation: DungeonFeatureInteractionValidationResult,
) -> tuple[dict[str, JsonValue], ...]:
    paths = {
        "feature_interaction.package_mismatch": "/package_id",
        "feature_interaction.room_mismatch": "/room_id",
        "feature_interaction.feature_mismatch": "/feature_id",
    }
    repairs = {
        "feature_interaction.package_mismatch": "use the exact context package ID",
        "feature_interaction.room_mismatch": "use the exact context feature room ID",
        "feature_interaction.feature_mismatch": "use the exact context feature ID",
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
    return reserve_structured_submission_repair(
        profile, record, repair_input=repair_input, tool=tool
    )


def _tool_run_pin(lineage: PromptedDungeonFeatureInteractionLineage) -> ToolRunPin:
    invocation = lineage.model_run.tool_invocations[0]
    return ToolRunPin(
        tool_name=invocation.tool_name,
        schema_version=DUNGEON_FEATURE_INTERACTION_ENRICHMENT_SCHEMA_VERSION,
        input_sha256=canonical_json_sha256(invocation.arguments),
        output_sha256=canonical_json_sha256(invocation.result.model_dump(mode="json")),
        status="succeeded",
    )


def _validate_profile(profile: ResolvedModelRunProfile) -> None:
    if profile.output_schema_name != _FEATURE_INTERACTION_SCHEMA_NAME:
        raise ValueError(
            "feature interaction submission requires the feature interaction enrichment schema"
        )
    if (
        profile.output_schema_version
        != DUNGEON_FEATURE_INTERACTION_ENRICHMENT_SCHEMA_VERSION
    ):
        raise ValueError("feature interaction submission requires schema version 1.0.0")
    if profile.allowed_tools != (_SUBMIT_DUNGEON_FEATURE_INTERACTION_TOOL,):
        raise ValueError(
            "feature interaction submission exposes only submit_dungeon_feature_interaction"
        )
    if profile.turn_budget != 1 or profile.tool_budget != 1:
        raise ValueError(
            "feature interaction submission requires one turn and one tool call"
        )
    if profile.require_citation_ids or profile.require_authorized_citations:
        raise ValueError(
            "standalone feature interaction submission cannot require citations"
        )
    if profile.allow_source_retrieval_tools:
        raise ValueError(
            "standalone feature interaction submission cannot retrieve sources"
        )
    if profile.override_notes.get("repair_limit") != 1:
        raise ValueError(
            "feature interaction submission permits exactly one schema repair"
        )


def _canonical_message(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
