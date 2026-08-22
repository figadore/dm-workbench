"""Synthetic P7-09 prompt-to-dungeon workflow coverage."""

import json
import uuid
from copy import deepcopy
from pathlib import Path

import pytest

from dm_assistant.errors import ConflictError
from dm_assistant.modules.modeling import (
    ModelRunInput,
    PromptMessage,
    ResolvedModelRunProfile,
    ToolCall,
)
from dm_assistant.modules.preparation import AttachArtifactAsset
from dm_assistant.modules.scope import TaskType, resolve_task_scope
from dm_assistant.orchestration.dungeons import (
    DungeonGenerationRegressionCase,
    DungeonStudioSpecification,
    DungeonSubmissionService,
    PromptDungeonWorkflow,
)
from dm_assistant.orchestration.dungeons.application import _failure_code
from dm_assistant.orchestration.dungeons.prompting import (
    DungeonProposalRejectedAfterRepair,
    _build_standalone_context,
    _initial_model_input,
    _lineage,
    resolve_dungeon_prompt_profile,
)
from dm_assistant.orchestration.dungeons.service import (
    _build_dm_guide,
    _build_dm_notes,
    _build_preparation_readiness,
    _dm_guide_text,
    _dm_notes_asset,
    _dm_notes_text,
    _dm_presentation_package,
    _require_preparation_ready,
)
from dm_assistant.orchestration.modeling import (
    GatewayCompletion,
    GatewayToolSchema,
    ModelRunAbstained,
)
from dm_dungeon import (
    CompiledDoorMechanics,
    DungeonMechanicsPlan,
    LayoutRequest,
    generate_layout,
    read_dungeon_package,
)

FIXTURE_PATH = (
    Path(__file__).parents[2]
    / "packages/dungeon-engine/tests/fixtures/sunken_archive.v1.json"
)


class FakeGatewayClient:
    def __init__(self, completions: tuple[GatewayCompletion, ...]) -> None:
        self._completions = list(completions)
        self.tool_schemas: tuple[GatewayToolSchema, ...] = ()
        self.messages: list[tuple[PromptMessage, ...]] = []
        self.profiles: list[ResolvedModelRunProfile] = []

    def complete(
        self,
        *,
        profile: object,
        messages: tuple[PromptMessage, ...],
        allowed_tools: tuple[str, ...],
        tool_schemas: tuple[GatewayToolSchema, ...],
    ) -> GatewayCompletion:
        del allowed_tools
        assert isinstance(profile, ResolvedModelRunProfile)
        self.profiles.append(profile)
        self.messages.append(messages)
        self.tool_schemas = tool_schemas
        if not self._completions:
            raise AssertionError("unexpected extra completion")
        return self._completions.pop(0)


def test_prompt_attempt_classifies_missing_usage_repair_without_abstention() -> None:
    assert (
        _failure_code(
            ModelRunAbstained("model usage was unavailable; repair budget is unknown")
        )
        == "dungeon_prompt_repair_usage_unavailable"
    )
    assert _failure_code(ModelRunAbstained("model rejected the proposal")) == (
        "dungeon_prompt_failed"
    )
    assert _failure_code(DungeonProposalRejectedAfterRepair()) == (
        "dungeon_prompt_rejected_after_repair"
    )


def _fixture_layout_request(*, topology_connections: bool = True):
    package = read_dungeon_package(FIXTURE_PATH)
    topology = package.topology
    if not topology_connections:
        topology = topology.model_copy(update={"connections": ()})
    mechanics_plan = DungeonMechanicsPlan(
        policy_version="dungeon-mechanics-policy-v1",
        connection_ids=tuple(item.id for item in topology.connections),
        room_ids=tuple(item.id for item in topology.rooms),
        door_mechanics=tuple(
            CompiledDoorMechanics(
                id=door.id,
                connection_id=door.connection_id,
                concealed=door.mechanics.concealed,
                gate_id=door.mechanics.gate_id,
                gate_kind=door.mechanics.gate_kind,
                trap_id=door.mechanics.trap_id,
                discovery_difficulty=door.mechanics.discovery_difficulty,
                unlock_difficulty=door.mechanics.unlock_difficulty,
                disable_difficulty=door.mechanics.disable_difficulty,
            )
            for door in package.composable_doors
            if topology_connections
        ),
        room_traps=(),
        room_puzzles=(),
        room_features=(),
        room_objectives=(),
        encounter_slots=(),
    )
    return LayoutRequest(
        schema_version="1.0.0",
        package_id="package_prompted_fixture",
        brief=package.brief,
        topology=topology,
        seed=1842,
        generator_version="orthogonal-v1",
        mechanics_plan=mechanics_plan,
    )


def _tier_a_proposal() -> dict[str, object]:
    return {
        "proposal_version": "1",
        "plan": {
            "schema_version": "1.0.0",
            "title": "Salt Cellar",
            "premise": "A sealed ledger waits below the tide.",
            "themes": ["salt"],
            "rooms": [
                {
                    "ref": "entry",
                    "name": "Wet Steps",
                    "role": "entrance",
                    "purpose": "Establish the descent.",
                },
                {
                    "ref": "stacks",
                    "name": "Drowned Stacks",
                    "role": "exploration",
                    "purpose": "Reveal the archive.",
                },
                {
                    "ref": "gallery",
                    "name": "Salt Gallery",
                    "role": "exploration",
                    "purpose": "Foreshadow the vault.",
                },
                {
                    "ref": "vault",
                    "name": "Ledger Vault",
                    "role": "objective",
                    "purpose": "Hold the ledger.",
                },
            ],
            "critical_path": ["entry", "stacks", "gallery", "vault"],
            "room_contents": [{"room_ref": "vault", "objective": "Sealed Ledger"}],
        },
    }


def test_prompt_explains_tier_a_plan_constraints() -> None:
    command = PromptDungeonWorkflow(
        campaign_id=uuid.UUID("10000000-0000-0000-0000-000000000001"),
        prompt="Synthetic hidden archive.",
        seed=1842,
        created_by="dm",
        scope=resolve_task_scope(
            dm_principal_id="dm",
            campaign_owner_id="dm",
            task_type=TaskType.STANDALONE_DUNGEON,
        ),
    )

    message = (
        _initial_model_input(command, _build_standalone_context(command))
        .messages[0]
        .content
    )

    assert "one floor and 4–8 rooms" in message
    assert "critical_path starts at the entrance" in message
    assert "at most two ordered branches" in message
    assert "at most one loop" in message
    assert "key or clue" in message
    assert "Do not author edges" in message
    assert "DungeonPlan schema version 1.0.0" in message
    assert "room_contents[].objective" in message


def test_submits_one_compact_tool_call_without_a_second_completion() -> None:
    proposal = _tier_a_proposal()
    gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_plan",
                        call_id="submit-1",
                        arguments={"proposal": proposal},
                    ),
                ),
                input_tokens=10,
                output_tokens=10,
            ),
        )
    )
    profile = resolve_dungeon_prompt_profile(
        provider_id="faux",
        model_id="faux_deterministic_v1",
        capabilities=("text", "tool_calls", "json_schema_constrained_sampling"),
        context_window_tokens=16_384,
        output_token_limit=4_096,
    )

    result = DungeonSubmissionService(gateway).submit(
        profile=profile,
        run_input=ModelRunInput(
            messages=(PromptMessage(role="user", content="synthetic request"),)
        ),
        seed=1842,
    )

    assert result.compilation is not None and result.compilation.accepted
    assert result.compilation.certificate is not None
    assert result.layout_request is not None
    assert result.model_run.turn_count == 1
    assert result.model_run.tool_invocations[0].tool_name == "submit_dungeon_plan"
    tool_payload = result.model_run.tool_invocations[0].result.payload
    assert tool_payload["certificate_version"] == "topology-certificate-v1"
    assert tool_payload["topology"] == {
        "rooms": 4,
        "connections": 3,
        "branches": 0,
        "cycle_rank": 0,
        "secret_routes": 0,
        "gates": 0,
    }
    assert tuple(schema.name for schema in gateway.tool_schemas) == (
        "submit_dungeon_plan",
    )
    assert gateway.tool_schemas[0].constrained_sampling == "prefer"
    schema_text = json.dumps(gateway.tool_schemas[0].parameters)
    assert "DungeonPlan" in schema_text
    assert '"connections"' not in schema_text
    layout = generate_layout(result.layout_request)
    assert layout.success and layout.package is not None
    guide = _build_dm_guide(
        result.layout_request, layout.package, (_lineage(result.model_run),)
    )
    assert guide is not None
    assert {item.map_reference.token for item in guide.rooms} == {"1", "2", "3", "4"}
    assert len(guide.connections) == 3

    invalid = deepcopy(proposal)
    invalid_plan = invalid["plan"]
    assert isinstance(invalid_plan, dict)
    invalid_plan["gates"] = [
        {
            "ref": "vault_gate",
            "between_rooms": ["gallery", "vault"],
            "kind": "locked",
            "dependency_kind": "key",
            "dependency_room": "vault",
            "dependency_name": "Impossible Key",
        }
    ]
    repair_gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_plan",
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
                        tool_name="submit_dungeon_plan",
                        call_id="submit-repair",
                        arguments={"proposal": proposal},
                    ),
                ),
                input_tokens=10,
                output_tokens=10,
            ),
        )
    )
    repaired = DungeonSubmissionService(repair_gateway).submit(
        profile=profile,
        run_input=ModelRunInput(
            messages=(PromptMessage(role="user", content="synthetic request"),)
        ),
        seed=1842,
    )
    assert repaired.repaired
    assert len(repaired.model_runs) == 2
    repair_document = json.loads(repair_gateway.messages[1][0].content)
    assert (
        repair_document["diagnostics"][0]["code"] == "plan.gate_dependency_unreachable"
    )
    assert repair_document["previous_arguments"] == {"proposal": invalid}

    exhausted_gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_plan",
                        call_id="bad-1",
                        arguments={"proposal": invalid},
                    ),
                ),
                input_tokens=10,
                output_tokens=10,
            ),
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_plan",
                        call_id="bad-2",
                        arguments={"proposal": invalid},
                    ),
                ),
                input_tokens=10,
                output_tokens=10,
            ),
        )
    )
    with pytest.raises(DungeonProposalRejectedAfterRepair):
        DungeonSubmissionService(exhausted_gateway).submit(
            profile=profile,
            run_input=ModelRunInput(
                messages=(PromptMessage(role="user", content="synthetic request"),)
            ),
            seed=1842,
        )

    schema_invalid = deepcopy(proposal)
    schema_plan = schema_invalid["plan"]
    assert isinstance(schema_plan, dict)
    schema_rooms = schema_plan["rooms"]
    assert isinstance(schema_rooms, list)
    schema_rooms[0]["encounter"] = "set_piece"
    schema_gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_plan",
                        call_id="schema-bad",
                        arguments={"proposal": schema_invalid},
                    ),
                ),
                input_tokens=10,
                output_tokens=10,
            ),
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_plan",
                        call_id="schema-repair",
                        arguments={"proposal": proposal},
                    ),
                ),
                input_tokens=10,
                output_tokens=10,
            ),
        )
    )
    schema_repaired = DungeonSubmissionService(schema_gateway).submit(
        profile=profile,
        run_input=ModelRunInput(
            messages=(PromptMessage(role="user", content="synthetic request"),)
        ),
        seed=1842,
    )
    assert schema_repaired.repaired
    assert schema_repaired.model_runs[0].status == "abstained"
    assert "submission.schema_invalid" in schema_gateway.messages[1][0].content


def test_dm_guide_retains_tier_a_gate_content_and_creative_details() -> None:
    proposal = _tier_a_proposal()
    plan = proposal["plan"]
    assert isinstance(plan, dict)
    rooms = plan["rooms"]
    assert isinstance(rooms, list)
    rooms[0]["tags"] = ["flooded"]
    rooms[0]["encounter"] = "ambush"
    rooms[0]["purpose"] = "Drips conceal soft footsteps."
    plan["gates"] = [
        {
            "ref": "vault_gate",
            "between_rooms": ["gallery", "vault"],
            "kind": "locked",
            "dependency_kind": "key",
            "dependency_room": "entry",
            "dependency_name": "Brass Key",
        }
    ]
    plan["room_contents"] = [
        {
            "room_ref": "gallery",
            "trap": {
                "name": "Thunder Glyph",
                "trigger": "Touch the chained folio.",
                "effect": "A thunderous ward sounds.",
                "challenge": "high",
            },
            "feature": {
                "kind": "altar",
                "name": "Fallen Lens",
                "description": "A cracked brass lens fills the alcove.",
            },
        },
        {"room_ref": "vault", "objective": "Astral Lens"},
    ]
    gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_plan",
                        call_id="submit-guide",
                        arguments={"proposal": proposal},
                    ),
                ),
                input_tokens=10,
                output_tokens=10,
            ),
        )
    )
    profile = resolve_dungeon_prompt_profile(
        provider_id="faux",
        model_id="faux_deterministic_v1",
        capabilities=("text", "tool_calls"),
        context_window_tokens=16_384,
        output_token_limit=4_096,
    )
    result = DungeonSubmissionService(gateway).submit(
        profile=profile,
        run_input=ModelRunInput(
            messages=(PromptMessage(role="user", content="synthetic request"),)
        ),
        seed=1842,
    )
    assert result.layout_request is not None
    layout = generate_layout(result.layout_request)
    assert layout.success and layout.package is not None

    guide = _build_dm_guide(
        result.layout_request, layout.package, (_lineage(result.model_run),)
    )

    assert guide is not None
    entry = next(item for item in guide.rooms if item.name == "Wet Steps")
    assert entry.preparation_note == "Drips conceal soft footsteps."
    assert entry.encounter_slot is not None and entry.encounter_slot_id is not None
    gated = next(item for item in guide.connections if item.gate_id is not None)
    assert gated.gate_kind.value == "locked"
    assert gated.unlock_difficulty == 13
    assert guide.dependencies[0].name == "Brass Key"
    assert guide.traps[0].trigger == "Touch the chained folio."
    assert guide.traps[0].effect == "A thunderous ward sounds."
    assert guide.traps[0].detection_difficulty == 16
    assert guide.features[0].name == "Fallen Lens"
    assert guide.objectives[0].name == "Astral Lens"
    text = _dm_guide_text(guide)
    assert "## Objectives" in text
    assert "Effect: A thunderous ward sounds." in text
    readiness = _build_preparation_readiness(guide)
    assert readiness is not None and readiness.ready

    incomplete = guide.model_copy(
        update={
            "dependencies": (),
            "traps": (guide.traps[0].model_copy(update={"effect": None}),),
        }
    )
    blocked = _build_preparation_readiness(incomplete)
    assert blocked is not None and not blocked.ready
    assert {item.code for item in blocked.diagnostics} == {
        "dungeon_preparation.lock_dependency_missing",
        "dungeon_preparation.trap_effect_unknown",
    }
    specification = DungeonStudioSpecification(
        schema_version="1.0.0",
        layout_request=result.layout_request,
        package=layout.package,
        dm_guide=incomplete,
        preparation_readiness=blocked,
        model_lineage=(_lineage(result.model_run),),
    )
    with pytest.raises(ConflictError, match="preparation is incomplete"):
        _require_preparation_ready(specification)


def test_failed_generation_regression_case_is_self_contained_and_replayable() -> None:
    request = _fixture_layout_request(topology_connections=False)
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


def test_dm_notes_asset_uses_a_valid_plain_text_media_type() -> None:
    request = _fixture_layout_request()
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


def test_dm_notes_are_readable_without_mutating_the_exact_package() -> None:
    package = read_dungeon_package(FIXTURE_PATH)
    request = _fixture_layout_request()
    notes = _build_dm_notes(
        request,
        "Access to the larger lower level should depend on discovering a secret passage from the upper archive.",
        package,
    )

    assert notes.room_notes[0].name == "Entrance"
    assert "## Original request" in _dm_notes_text(request, notes)
    assert _dm_presentation_package(package, notes) == package


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
