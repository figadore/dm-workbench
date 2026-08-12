"""Synthetic P7-09 prompt-to-dungeon workflow coverage."""

import uuid
from pathlib import Path

import pytest

from dm_assistant.modules.modeling import (
    DungeonGenerationIntentV1,
    GatewayModelCatalogEntry,
    ModelEndpointProfile,
    PromptMessage,
    ReasoningEffort,
    ReasoningLevel,
    TaskProfile,
    ToolCall,
    resolve_run_profile,
)
from dm_assistant.modules.scope import TaskType, resolve_task_scope
from dm_assistant.orchestration.dungeons import (
    CreatePromptedDungeonWorkflow,
    DungeonPromptService,
    DungeonWorkflowResult,
    PromptDungeonWorkflow,
)
from dm_assistant.orchestration.dungeons.prompting import compile_layout_request
from dm_assistant.orchestration.modeling import GatewayCompletion
from dm_dungeon import read_dungeon_package, to_canonical_json

FIXTURE_PATH = (
    Path(__file__).parents[2]
    / "packages/dungeon-engine/tests/fixtures/sunken_archive.v1.json"
)


class FakeGatewayClient:
    def __init__(self, completions: tuple[GatewayCompletion, ...]) -> None:
        self._completions = list(completions)
        self.tool_schema_names: tuple[str, ...] = ()

    def complete(
        self,
        *,
        profile: object,
        messages: tuple[PromptMessage, ...],
        allowed_tools: tuple[str, ...],
        tool_schemas: tuple[object, ...],
    ) -> GatewayCompletion:
        del profile, messages, allowed_tools
        self.tool_schema_names = tuple(schema.name for schema in tool_schemas)
        if not self._completions:
            raise AssertionError("unexpected extra completion")
        return self._completions.pop(0)


class RecordingDungeonStudio:
    def __init__(self) -> None:
        self.command: CreatePromptedDungeonWorkflow | None = None

    def create_prompted(
        self,
        command: CreatePromptedDungeonWorkflow,
    ) -> DungeonWorkflowResult:
        self.command = command
        return DungeonWorkflowResult(
            success=True,
            artifact_id=uuid.uuid4(),
            artifact_version_id=uuid.uuid4(),
            generation_run_id=uuid.uuid4(),
            diagnostics=(),
        )


def _intent(*, topology_connections: bool = True) -> DungeonGenerationIntentV1:
    package = read_dungeon_package(FIXTURE_PATH)
    topology = package.topology
    if not topology_connections:
        topology = topology.model_copy(update={"connections": ()})
    return DungeonGenerationIntentV1(
        schema_version="1.0.0",
        intent="Generate a synthetic sunken archive.",
        brief=package.brief,
        topology=topology,
        requested_constraints=("retain a secret route",),
    )


def _profile():
    endpoint = ModelEndpointProfile(
        profile_id=uuid.uuid4(),
        profile_version="1.0.0",
        runtime_adapter="pi_ai",
        provider_id="faux",
        model_id="faux_deterministic_v1",
        supported_efforts=(ReasoningEffort.STANDARD,),
        context_window_tokens=16_384,
        output_token_limit=4_096,
    )
    task = TaskProfile(
        profile_id=uuid.uuid4(),
        profile_version="1.0.0",
        task_name="dungeon_generation_intent_v1",
        prompt_version="prompt-1",
        instruction_version="instructions-1",
        output_schema_name="dungeon_generation_intent_v1",
        output_schema_version="1.0.0",
        allowed_tools=(
            "review_dungeon_brief",
            "review_dungeon_topology",
            "generate_dungeon_layout",
            "validate_dungeon_intent",
            "regenerate_dungeon_layout",
        ),
        turn_budget=2,
        tool_budget=1,
        time_budget_seconds=30,
        token_budget=4_096,
        require_citation_ids=False,
        require_authorized_citations=False,
    )
    catalog = GatewayModelCatalogEntry(
        provider_id="faux",
        model_id="faux_deterministic_v1",
        runtime_adapter="pi_ai",
        observed_capabilities=("text", "tool_calls"),
        supported_reasoning_levels=(ReasoningLevel.MEDIUM,),
        context_window_tokens=16_384,
        output_token_limit=4_096,
    )
    return resolve_run_profile(
        endpoint_profile=endpoint,
        task_profile=task,
        catalog_entry=catalog,
    )


def _command() -> PromptDungeonWorkflow:
    return PromptDungeonWorkflow(
        campaign_id=uuid.uuid4(),
        title="Prompted Sunken Archive",
        prompt="A flooded archive beneath a lighthouse.",
        seed=1842,
        created_by="synthetic-dm",
        scope=resolve_task_scope(
            dm_principal_id="dm",
            campaign_owner_id="dm",
            task_type=TaskType.STANDALONE_DUNGEON,
        ),
        requested_constraints=("flooded", "single entrance"),
    )


def test_compiler_derives_stable_layout_request_from_typed_intent() -> None:
    intent = _intent()

    first = compile_layout_request(intent, 1842)
    second = compile_layout_request(intent, 1842)

    assert first.package_id == second.package_id
    assert first.package_id.startswith("dungeon_")
    assert to_canonical_json(first) == to_canonical_json(second)
    assert first.brief == intent.brief
    assert first.topology == intent.topology


def test_prompt_workflow_uses_only_structured_validation_and_persists_lineage() -> None:
    intent = _intent()
    gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="validate_dungeon_intent",
                        call_id="validate-1",
                        arguments={
                            "intent": intent.model_dump(mode="json"),
                            "seed": 1842,
                        },
                    ),
                ),
                input_tokens=10,
                output_tokens=5,
            ),
            GatewayCompletion(
                content=intent.model_dump_json(),
                input_tokens=10,
                output_tokens=20,
            ),
        )
    )
    studio = RecordingDungeonStudio()
    service = DungeonPromptService(studio, gateway)

    result = service.create(_command(), _profile())

    assert result.success is True
    assert studio.command is not None
    stored = studio.command
    assert stored is not None
    context = stored.context
    payload = context.envelope["payload"]
    assert context.envelope_kind == "dungeon_generation"
    assert payload["prompt_input_sha256"] != ""
    assert context.source_links == ()
    assert len(stored.model_lineage) == 1
    assert stored.model_lineage[0].model_run.turn_count == 2
    assert stored.tool_runs[0].tool_name == "validate_dungeon_intent"
    assert gateway.tool_schema_names == (
        "review_dungeon_brief",
        "review_dungeon_topology",
        "generate_dungeon_layout",
        "validate_dungeon_intent",
        "regenerate_dungeon_layout",
    )


def test_prompt_workflow_repairs_invalid_topology_with_remaining_budget() -> None:
    invalid = _intent(topology_connections=False)
    repaired = _intent()
    gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                content=invalid.model_dump_json(), input_tokens=10, output_tokens=20
            ),
            GatewayCompletion(
                content=repaired.model_dump_json(), input_tokens=10, output_tokens=20
            ),
        )
    )
    studio = RecordingDungeonStudio()
    service = DungeonPromptService(studio, gateway)

    service.create(_command(), _profile())

    assert studio.command is not None
    assert len(studio.command.model_lineage) == 2
    assert studio.command.model_lineage[-1].intent.topology == repaired.topology


def test_prompt_workflow_allows_only_code_owned_targeted_regeneration_preview() -> None:
    intent = _intent()
    assert intent.topology is not None
    locked_room_id = intent.topology.rooms[0].id
    gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="regenerate_dungeon_layout",
                        call_id="regenerate-1",
                        arguments={
                            "intent": intent.model_dump(mode="json"),
                            "baseline_seed": 1842,
                            "seed": 999999,
                            "locked_component_ids": [locked_room_id],
                        },
                    ),
                ),
                input_tokens=10,
                output_tokens=5,
            ),
            GatewayCompletion(
                content=intent.model_dump_json(),
                input_tokens=10,
                output_tokens=20,
            ),
        )
    )
    studio = RecordingDungeonStudio()
    service = DungeonPromptService(studio, gateway)

    service.create(_command(), _profile())

    assert studio.command is not None
    assert studio.command.tool_runs[0].tool_name == "regenerate_dungeon_layout"


def test_prompt_workflow_rejects_grounded_scope_before_model_execution() -> None:
    with pytest.raises(ValueError, match="standalone_dungeon"):
        PromptDungeonWorkflow(
            campaign_id=uuid.uuid4(),
            title="Grounded request",
            prompt="Do not permit this path yet.",
            seed=1,
            created_by="synthetic-dm",
            scope=resolve_task_scope(
                dm_principal_id="dm",
                campaign_owner_id="dm",
                task_type=TaskType.GROUNDED_DUNGEON,
                grounding_enabled=True,
                campaign_revision_id=uuid.uuid4(),
                corpus_snapshot_id=uuid.uuid4(),
                rules_profile_id=uuid.uuid4(),
            ),
        )
