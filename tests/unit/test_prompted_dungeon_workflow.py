"""Synthetic P7-09 prompt-to-dungeon workflow coverage."""

import json
import uuid
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

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
    DungeonStudioService,
    DungeonStudioSpecification,
    DungeonV2SubmissionService,
    PromptDungeonWorkflow,
)
from dm_assistant.orchestration.dungeons.application import _failure_code
from dm_assistant.orchestration.dungeons.prompting import (
    DungeonProposalRejectedAfterRepair,
    _build_standalone_context,
    _initial_v2_model_input,
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
    _select_locks,
)
from dm_assistant.orchestration.modeling import (
    GatewayCompletion,
    GatewayToolSchema,
    ModelRunAbstained,
)
from dm_dungeon import (
    DungeonPackageV2,
    LayoutRequest,
    RenderAudience,
    SvgRenderRequest,
    generate_layout,
    read_dungeon_package,
    render_svg,
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
    return LayoutRequest(
        schema_version="1.0.0",
        package_id="package_prompted_fixture",
        brief=package.brief,
        topology=topology,
        seed=1842,
        generator_version="orthogonal-v2",
    )


def test_v2_prompt_explains_connection_constraints() -> None:
    command = PromptDungeonWorkflow(
        campaign_id=uuid.UUID("10000000-0000-0000-0000-000000000001"),
        prompt="Synthetic hidden lower level.",
        seed=1842,
        created_by="dm",
        scope=resolve_task_scope(
            dm_principal_id="dm",
            campaign_owner_id="dm",
            task_type=TaskType.STANDALONE_DUNGEON,
        ),
    )

    message = (
        _initial_v2_model_input(command, _build_standalone_context(command))
        .messages[0]
        .content
    )

    assert "use passage or door only between rooms on one floor" in message
    assert "use stairs or ladder only between different floors" in message
    assert "from_hidden and to_hidden independently" in message
    assert "from_hidden true and to_hidden false" in message
    assert "vertical lock, puzzle, or trap" in message
    assert "explicit endpoint_doors item" in message
    assert "target its local_ref with the dependency" in message
    assert "design schema version 2.4.0" in message
    assert "objectives[].name" in message


def test_v2_submits_one_compact_tool_call_without_a_second_completion() -> None:
    proposal = {
        "proposal_version": "2",
        "design": {
            "schema_version": "2.4.0",
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
            "objectives": [
                {
                    "room_ref": "vault",
                    "kind": "final_objective",
                    "name": "Sealed Ledger",
                }
            ],
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
    profile = resolve_dungeon_prompt_profile(
        provider_id="faux",
        model_id="faux_deterministic_v1",
        capabilities=("text", "tool_calls", "json_schema_constrained_sampling"),
        context_window_tokens=16_384,
        output_token_limit=4_096,
    )
    assert profile.token_budget == 12_000
    assert profile.override_notes["output_token_limit"] == 4_096

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
    assert gateway.tool_schemas[0].constrained_sampling == "prefer"
    layout = generate_layout(result.layout_request)
    assert layout.success and layout.package is not None
    guide = _build_dm_guide(
        result.layout_request, layout.package, (_lineage(result.model_run),)
    )
    assert guide is not None
    assert {item.map_reference.token for item in guide.rooms} == {"1", "2"}
    assert guide.connections[0].map_reference is not None
    assert guide.connections[0].map_reference.token == "D1"
    assert "# Salt Cellar — DM guide" in _dm_guide_text(guide)
    assert "D1 — door." in _dm_guide_text(guide)
    assert _dm_notes_asset(
        result.layout_request, _build_dm_notes(result.layout_request, None), guide
    ).data == _dm_guide_text(guide).encode("utf-8")

    invalid = deepcopy(proposal)
    invalid_design = invalid["design"]
    assert isinstance(invalid_design, dict)
    invalid_connections = invalid_design["connections"]
    assert isinstance(invalid_connections, list)
    invalid_connection = invalid_connections[0]
    assert isinstance(invalid_connection, dict)
    invalid_connection["door_mechanics"] = {"barrier": "locked"}
    invalid_design["dependencies"] = [
        {
            "local_ref": "bad-key",
            "kind": "key",
            "target_ref": "unknown-door",
            "located_in_room_ref": "entry",
            "name": "Bad Key",
        }
    ]
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
    assert len(repair_gateway.profiles) == 2
    assert repair_gateway.profiles[1].token_budget == profile.token_budget - 20
    assert (
        repair_gateway.profiles[1].token_budget
        < repair_gateway.profiles[0].token_budget
    )
    assert (
        repaired.model_runs[0].output_payload != repaired.model_runs[1].output_payload
    )
    first_lineage, repaired_lineage = (_lineage(run) for run in repaired.model_runs)
    assert first_lineage.proposal_v2 is not None
    assert first_lineage.proposal_v2 != repaired_lineage.proposal_v2
    repair_document = json.loads(repair_gateway.messages[1][0].content)
    assert repair_document["diagnostics"][0]["code"] == "design.unneeded_dependency"
    assert repair_document["prompt"] == "synthetic request"
    assert repair_document["previous_arguments"] == {"proposal": invalid}
    assert "Preserve the original requested dungeon" in repair_document["instruction"]

    exhausted_repair_gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_intent_v2",
                        call_id="submit-invalid-again",
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
                        call_id="submit-repair-invalid-again",
                        arguments={"proposal": invalid},
                    ),
                ),
                input_tokens=10,
                output_tokens=10,
            ),
        )
    )
    with pytest.raises(DungeonProposalRejectedAfterRepair) as exhausted:
        DungeonV2SubmissionService(exhausted_repair_gateway).submit(
            profile=profile,
            run_input=ModelRunInput(
                messages=(PromptMessage(role="user", content="synthetic request"),)
            ),
            seed=1842,
        )
    assert not isinstance(exhausted.value, ModelRunAbstained)

    schema_invalid = deepcopy(proposal)
    invalid_schema_design = schema_invalid["design"]
    assert isinstance(invalid_schema_design, dict)
    schema_floors = invalid_schema_design["floors"]
    assert isinstance(schema_floors, list)
    schema_floor = schema_floors[0]
    assert isinstance(schema_floor, dict)
    schema_rooms = schema_floor["rooms"]
    assert isinstance(schema_rooms, list)
    schema_room = schema_rooms[0]
    assert isinstance(schema_room, dict)
    schema_room["encounter_slot"] = "set_piece"
    schema_repair_gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_intent_v2",
                        call_id="submit-schema-invalid",
                        arguments={"proposal": schema_invalid},
                    ),
                ),
                input_tokens=10,
                output_tokens=10,
            ),
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_intent_v2",
                        call_id="submit-schema-repair",
                        arguments={"proposal": proposal},
                    ),
                ),
                input_tokens=10,
                output_tokens=10,
            ),
        )
    )

    schema_repaired = DungeonV2SubmissionService(schema_repair_gateway).submit(
        profile=profile,
        run_input=ModelRunInput(
            messages=(PromptMessage(role="user", content="synthetic request"),)
        ),
        seed=1842,
    )

    assert schema_repaired.repaired is True
    assert schema_repaired.compilation is not None
    assert schema_repaired.compilation.accepted
    assert schema_repaired.model_runs[0].status == "abstained"
    assert schema_repaired.model_runs[0].output_payload is None
    invalid_lineage, valid_lineage = (
        _lineage(run) for run in schema_repaired.model_runs
    )
    assert invalid_lineage.proposal_v2 is None
    assert valid_lineage.proposal_v2 == schema_repaired.proposal
    repair_message = schema_repair_gateway.messages[1][0].content
    assert "submission.schema_invalid" in repair_message
    assert "Salt Cellar" in repair_message
    assert '"previous_arguments"' in repair_message
    assert '"prompt":"synthetic request"' in repair_message
    schema_repair_document = json.loads(repair_message)
    assert "allowed values" in schema_repair_document["diagnostics"][0]["repair"]


def test_v2_dm_guide_retains_requested_mechanics_and_creative_details() -> None:
    proposal = {
        "proposal_version": "2",
        "design": {
            "schema_version": "2.4.0",
            "title": "Star Vault",
            "premise": "A drowned observatory seals its lens below a trapped door.",
            "themes": ["salt"],
            "floors": [
                {
                    "local_ref": "upper",
                    "name": "Upper Archive",
                    "rooms": [
                        {
                            "local_ref": "entry",
                            "name": "Wet Steps",
                            "role": "entrance",
                            "tags": ["flooded"],
                            "preparation_note": "Drips conceal soft footsteps.",
                            "encounter_slot": "ambush",
                        },
                        {"local_ref": "vault", "name": "Chart Vault", "role": "puzzle"},
                    ],
                },
                {
                    "local_ref": "lower",
                    "name": "Lower Lens",
                    "rooms": [
                        {
                            "local_ref": "lens",
                            "name": "Lens Chamber",
                            "role": "objective",
                        }
                    ],
                },
            ],
            "connections": [
                {
                    "local_ref": "vault-door",
                    "from_ref": "entry",
                    "to_ref": "vault",
                    "passage": "door",
                    "from_hidden": True,
                    "door_mechanics": {
                        "concealed": True,
                        "barrier": "locked",
                        "hazard": "trapped",
                        "challenge": "moderate",
                        "trap_trigger": "Opening the vault door.",
                        "trap_effect": "A thunderous ward sounds.",
                    },
                },
                {
                    "local_ref": "vault-stairs",
                    "from_ref": "vault",
                    "to_ref": "lens",
                    "passage": "stairs",
                    "to_hidden": True,
                    "endpoint_doors": [
                        {
                            "local_ref": "lens-hatch",
                            "endpoint": "to",
                            "kind": "hatch",
                            "mechanics": {
                                "concealed": True,
                                "barrier": "puzzle",
                                "hazard": "trapped",
                                "challenge": "high",
                                "trap_trigger": "Lifting the lens hatch.",
                                "trap_effect": "The chamber begins to flood.",
                            },
                        }
                    ],
                },
            ],
            "objectives": [
                {
                    "room_ref": "lens",
                    "kind": "final_objective",
                    "name": "Astral Lens",
                }
            ],
            "dependencies": [
                {
                    "local_ref": "vault-key",
                    "kind": "key",
                    "target_ref": "vault-door",
                    "located_in_room_ref": "entry",
                    "name": "Brass Key",
                },
                {
                    "local_ref": "lens-clue",
                    "kind": "clue",
                    "target_ref": "lens-hatch",
                    "located_in_room_ref": "vault",
                    "name": "Star Chart",
                },
            ],
            "traps": [
                {
                    "local_ref": "vault-glyph",
                    "room_ref": "vault",
                    "name": "Thunder Glyph",
                    "trigger": "Touch the star chart.",
                    "effect": "A thunderous ward sounds.",
                    "challenge": "high",
                }
            ],
            "puzzles": [
                {
                    "local_ref": "star-dial",
                    "room_ref": "lens",
                    "name": "Star Dial",
                    "mechanism": "Three rotating rings.",
                    "clue_refs": ["lens-clue"],
                    "solution": "Align the summer constellation.",
                    "consequence": "The hatch releases.",
                    "challenge": "moderate",
                }
            ],
            "features": [
                {
                    "local_ref": "fallen-lens",
                    "room_ref": "lens",
                    "kind": "altar",
                    "name": "Fallen Lens",
                    "description": "A cracked brass lens fills the chamber.",
                }
            ],
        },
    }
    gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_intent_v2",
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
    result = DungeonV2SubmissionService(gateway).submit(
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
    entry_room = next(item for item in guide.rooms if item.name == "Wet Steps")
    assert entry_room.preparation_note == "Drips conceal soft footsteps."
    assert entry_room.encounter_slot is not None
    assert entry_room.encounter_slot_id is not None
    door = next(item for item in guide.connections if item.passage == "door")
    hatch = next(item for item in guide.connections if item.endpoint is not None)
    assert door.concealed and door.gate_id and door.trap_id
    assert door.trap_trigger == "Opening the vault door."
    assert door.trap_effect == "A thunderous ward sounds."
    assert (
        door.discovery_difficulty
        == door.unlock_difficulty
        == door.disable_difficulty
        == 13
    )
    assert hatch.endpoint_kind is not None and hatch.endpoint_kind.value == "hatch"
    assert hatch.concealed and hatch.gate_id and hatch.trap_id
    assert hatch.map_reference is not None
    assert hatch.map_reference.component_id == hatch.component_id
    assert hatch.trap_trigger == "Lifting the lens hatch."
    assert hatch.trap_effect == "The chamber begins to flood."
    assert (
        hatch.discovery_difficulty
        == hatch.unlock_difficulty
        == hatch.disable_difficulty
        == 16
    )
    assert guide.dependencies[0].name == "Brass Key"
    assert guide.traps[0].trigger == "Touch the star chart."
    assert guide.traps[0].effect == "A thunderous ward sounds."
    assert guide.puzzles[0].solution == "Align the summer constellation."
    assert guide.objectives[0].kind.value == "final_objective"
    assert guide.objectives[0].name == "Astral Lens"
    assert guide.objectives[0].map_reference.token.startswith("O")
    assert guide.features[0].description == "A cracked brass lens fills the chamber."
    text = _dm_guide_text(guide)
    assert "trigger: Opening the vault door." in text
    assert "effect: The chamber begins to flood." in text
    assert "disable 13" in text
    assert "## Objectives" in text
    assert "Solution: Align the summer constellation." in text
    assert "Effect: A thunderous ward sounds." in text
    complete_readiness = _build_preparation_readiness(guide)
    assert complete_readiness is not None
    assert complete_readiness.ready

    package = layout.package
    assert isinstance(package, DungeonPackageV2)
    locked_door = _select_locks(package, (door.component_id,))
    assert locked_door.doors[0].id == door.connection_id
    assert locked_door.doors[0].segment == package.composable_doors[0].segment
    regenerated = generate_layout(
        result.layout_request.model_copy(
            update={"seed": 999_999, "locked": locked_door}
        )
    )
    assert isinstance(regenerated.package, DungeonPackageV2)
    assert regenerated.package.composable_doors[0].segment == (
        package.composable_doors[0].segment
    )
    locked_hatch = _select_locks(package, (hatch.component_id,))
    assert locked_hatch.vertical_links[0].id == hatch.connection_id
    locked_marker = _select_locks(package, (guide.traps[0].marker_id,))
    assert locked_marker.rooms[0].id == guide.traps[0].room_id

    incomplete = guide.model_copy(
        update={
            "dependencies": (),
            "connections": tuple(
                item.model_copy(update={"trap_effect": None})
                if item.trap_id is not None and item.endpoint is None
                else item
                for item in guide.connections
            ),
            "traps": (guide.traps[0].model_copy(update={"effect": None}),),
            "puzzles": (guide.puzzles[0].model_copy(update={"solution": None}),),
        }
    )
    readiness = _build_preparation_readiness(incomplete)
    assert readiness is not None
    assert readiness.ready is False
    assert [item.code for item in readiness.diagnostics] == [
        "dungeon_preparation.lock_dependency_missing",
        "dungeon_preparation.lock_dependency_missing",
        "dungeon_preparation.trap_effect_unknown",
        "dungeon_preparation.trap_effect_unknown",
        "dungeon_preparation.puzzle_solution_unknown",
    ]
    specification = DungeonStudioSpecification(
        schema_version="1.0.0",
        layout_request=result.layout_request,
        package=layout.package,
        dm_guide=incomplete,
        preparation_readiness=readiness,
        model_lineage=(_lineage(result.model_run),),
    )
    with pytest.raises(ConflictError, match="preparation is incomplete"):
        _require_preparation_ready(specification)

    class IncompletePreparation:
        def get_version(
            self, campaign_id: uuid.UUID, artifact_version_id: uuid.UUID
        ) -> SimpleNamespace:
            del campaign_id, artifact_version_id
            return SimpleNamespace(specification=specification.model_dump(mode="json"))

        def transition_artifact(self, command: object) -> None:
            del command
            raise AssertionError("incomplete preparation must not be transitioned")

    with pytest.raises(ConflictError, match="preparation is incomplete"):
        DungeonStudioService(IncompletePreparation()).approve(
            campaign_id=uuid.uuid4(),
            artifact_id=uuid.uuid4(),
            artifact_version_id=uuid.uuid4(),
            actor="synthetic-dm",
            reason="This must remain a draft.",
        )


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


def test_dm_notes_are_readable_and_dm_map_callouts_never_modify_player_map() -> None:
    package = read_dungeon_package(FIXTURE_PATH)
    request = _fixture_layout_request()
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
