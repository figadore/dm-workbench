"""Synthetic P7-09 prompt-to-dungeon workflow coverage."""

import uuid
from copy import deepcopy
from pathlib import Path

import pytest

from dm_assistant.modules.modeling import (
    DungeonGenerationIntentV1,
    GatewayModelCatalogEntry,
    ModelEndpointProfile,
    ModelRunInput,
    PromptMessage,
    ReasoningEffort,
    ReasoningLevel,
    TaskProfile,
    ToolCall,
    resolve_run_profile,
)
from dm_assistant.modules.preparation import AttachArtifactAsset
from dm_assistant.modules.scope import TaskType, resolve_task_scope
from dm_assistant.orchestration.dungeons import (
    CreatePromptedDungeonWorkflow,
    DungeonGenerationRegressionCase,
    DungeonPromptService,
    DungeonV2SubmissionService,
    DungeonWorkflowResult,
    PromptDungeonWorkflow,
)
from dm_assistant.orchestration.dungeons.prompting import (
    compile_layout_request,
    resolve_dungeon_prompt_profile,
    resolve_dungeon_v2_prompt_profile,
)
from dm_assistant.orchestration.dungeons.service import (
    _build_dm_notes,
    _dm_notes_asset,
    _dm_notes_text,
    _dm_presentation_package,
)
from dm_assistant.orchestration.modeling import GatewayCompletion, GatewayToolSchema
from dm_dungeon import (
    RenderAudience,
    SvgRenderRequest,
    generate_layout,
    read_dungeon_package,
    render_svg,
    to_canonical_json,
)

FIXTURE_PATH = (
    Path(__file__).parents[2]
    / "packages/dungeon-engine/tests/fixtures/sunken_archive.v1.json"
)


class FakeGatewayClient:
    def __init__(self, completions: tuple[GatewayCompletion, ...]) -> None:
        self._completions = list(completions)
        self.tool_schemas: tuple[GatewayToolSchema, ...] = ()

    def complete(
        self,
        *,
        profile: object,
        messages: tuple[PromptMessage, ...],
        allowed_tools: tuple[str, ...],
        tool_schemas: tuple[GatewayToolSchema, ...],
    ) -> GatewayCompletion:
        del profile, messages, allowed_tools
        self.tool_schemas = tool_schemas
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


def test_live_gateway_catalog_resolves_hyphenated_dungeon_profile() -> None:
    profile = resolve_dungeon_prompt_profile(
        provider_id="openai-codex",
        model_id="gpt-5.1-codex",
        capabilities=("text", "thinking", "tool_calls"),
        context_window_tokens=128_000,
        output_token_limit=16_384,
        requested_effort=ReasoningEffort.DEEP,
    )

    assert profile.provider_id == "openai-codex"
    assert profile.model_id == "gpt-5.1-codex"
    assert profile.requested_effort is ReasoningEffort.DEEP
    assert profile.output_schema_name == "dungeon_generation_intent_v1"
    assert profile.require_citation_ids is False
    assert profile.task_profile_version == "1.2.0"
    assert profile.instruction_version == "instructions-3"
    assert profile.turn_budget == 3
    assert profile.time_budget_seconds == 300
    assert profile.tool_budget == len(profile.allowed_tools) == 5
    assert profile.token_budget == 128_000
    assert "generate_dungeon_layout" in profile.allowed_tools


def test_v2_submits_one_compact_tool_call_without_a_second_completion() -> None:
    proposal = {
        "proposal_version": "2",
        "design": {
            "schema_version": "2.0.0",
            "title": "Salt Cellar",
            "premise": "A sealed ledger waits below the tide.",
            "themes": ["salt"],
            "floors": [
                {
                    "local_ref": "cellar",
                    "name": "Salt Cellar",
                    "rooms": [
                        {"local_ref": "entry", "name": "Wet Steps", "role": "entrance"},
                        {
                            "local_ref": "vault",
                            "name": "Ledger Vault",
                            "role": "objective",
                        },
                    ],
                }
            ],
            "connections": [
                {
                    "local_ref": "entry-vault",
                    "from_ref": "entry",
                    "to_ref": "vault",
                    "passage": "door",
                }
            ],
            "objectives": [{"room_ref": "vault", "kind": "final_objective"}],
            "dependencies": [],
        },
    }
    gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_intent_v2",
                        call_id="submit-1",
                        arguments={"proposal": proposal},
                    ),
                ),
                input_tokens=10,
                output_tokens=10,
            ),
        )
    )
    profile = resolve_dungeon_v2_prompt_profile(
        provider_id="faux",
        model_id="faux_deterministic_v1",
        capabilities=("text", "tool_calls"),
        context_window_tokens=16_384,
        output_token_limit=4_096,
    )

    result = DungeonV2SubmissionService(gateway).submit(
        profile=profile,
        run_input=ModelRunInput(
            messages=(PromptMessage(role="user", content="synthetic request"),)
        ),
        seed=1842,
    )

    assert result.compilation is not None and result.compilation.accepted
    assert result.layout_request is not None
    assert result.model_run.turn_count == 1
    assert result.model_run.tool_invocations[0].tool_name == "submit_dungeon_intent_v2"
    assert tuple(schema.name for schema in gateway.tool_schemas) == (
        "submit_dungeon_intent_v2",
    )

    invalid = deepcopy(proposal)
    invalid_design = invalid["design"]
    assert isinstance(invalid_design, dict)
    invalid_design["objectives"] = []
    repair_gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_intent_v2",
                        call_id="submit-invalid",
                        arguments={"proposal": invalid},
                    ),
                ),
                input_tokens=10,
                output_tokens=10,
            ),
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_intent_v2",
                        call_id="submit-repair",
                        arguments={"proposal": proposal},
                    ),
                ),
                input_tokens=10,
                output_tokens=10,
            ),
        )
    )
    repaired = DungeonV2SubmissionService(repair_gateway).submit(
        profile=profile,
        run_input=ModelRunInput(
            messages=(PromptMessage(role="user", content="synthetic request"),)
        ),
        seed=1842,
    )
    assert repaired.repaired is True
    assert len(repaired.model_runs) == 2
    assert repaired.compilation is not None and repaired.compilation.accepted


def test_failed_generation_regression_case_is_self_contained_and_replayable() -> None:
    request = compile_layout_request(_intent(topology_connections=False), 1842)
    failed = generate_layout(request)

    assert failed.success is False
    case = DungeonGenerationRegressionCase(
        stage="layout",
        layout_request=request,
        expected_diagnostics=tuple(
            item.model_dump(mode="json") for item in failed.diagnostics
        ),
    )

    replay = generate_layout(case.layout_request)
    assert replay.success is False
    assert [item.model_dump(mode="json") for item in replay.diagnostics] == list(
        case.expected_diagnostics
    )
    assert "layout_request" in case.model_dump(mode="json")


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
                        arguments={"intent": intent.model_dump(mode="json")},
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
    assert stored.source_prompt == "A flooded archive beneath a lighthouse."
    assert len(stored.model_lineage) == 1
    assert stored.model_lineage[0].model_run.turn_count == 2
    assert stored.tool_runs[0].tool_name == "validate_dungeon_intent"
    assert tuple(schema.name for schema in gateway.tool_schemas) == (
        "review_dungeon_brief",
        "review_dungeon_topology",
        "generate_dungeon_layout",
        "validate_dungeon_intent",
        "regenerate_dungeon_layout",
    )
    schema_properties = {
        schema.name: schema.parameters["properties"] for schema in gateway.tool_schemas
    }
    assert all(
        "seed" not in schema_properties[name]
        for name in (
            "review_dungeon_brief",
            "review_dungeon_topology",
            "generate_dungeon_layout",
            "validate_dungeon_intent",
        )
    )
    assert "baseline_seed" not in schema_properties["regenerate_dungeon_layout"]
    assert "seed" in schema_properties["regenerate_dungeon_layout"]


def test_dm_notes_asset_uses_a_valid_plain_text_media_type() -> None:
    request = compile_layout_request(_intent(), 1842)
    asset = _dm_notes_asset(request, _build_dm_notes(request, "Synthetic request."))

    command = AttachArtifactAsset(
        campaign_id=uuid.uuid4(),
        artifact_version_id=uuid.uuid4(),
        role=asset.role,
        ordinal=asset.ordinal,
        media_type=asset.media_type,
        data=asset.data,
    )

    assert command.media_type == "text/plain"


def test_dm_notes_are_readable_and_dm_map_callouts_never_modify_player_map() -> None:
    package = read_dungeon_package(FIXTURE_PATH)
    request = compile_layout_request(_intent(), 1842)
    notes = _build_dm_notes(
        request,
        "Access to the larger lower level should depend on discovering a secret passage from the upper archive.",
        package,
    )

    assert notes.room_notes[0].name == "Entrance"
    assert "## Original request" in _dm_notes_text(request, notes)
    presented = _dm_presentation_package(package, notes)
    assert len(presented.labels) == len(package.labels) + len(notes.room_notes)
    assert all(
        label.visibility.value == "dm_only"
        for label in presented.labels[-len(notes.room_notes) :]
    )
    dm_svg = render_svg(
        presented,
        SvgRenderRequest(
            schema_version="1.0.0",
            package_id=presented.id,
            floor_id="floor_upper",
            audience=RenderAudience.DM,
        ),
    )
    player_svg = render_svg(
        presented,
        SvgRenderRequest(
            schema_version="1.0.0",
            package_id=presented.id,
            floor_id="floor_upper",
            audience=RenderAudience.PLAYER,
        ),
    )
    assert "[1] Entrance" in (dm_svg.svg or "")
    assert "[1] Entrance" not in (player_svg.svg or "")


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
