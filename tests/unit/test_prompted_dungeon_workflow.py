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
from dm_assistant.orchestration.dungeons.application import (
    _failure_code,
    _failure_report,
)
from dm_assistant.orchestration.dungeons.evals import evaluate_dungeon_guide_quality
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
    ModelTransportError,
    StructuredSubmissionBudgetExceeded,
)
from dm_dungeon import (
    DungeonPlan,
    LayoutRequest,
    compile_dungeon_plan,
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


def _fixture_layout_request(*, topology_connections: bool = True) -> LayoutRequest:
    proposal = _tier_a_proposal()
    plan = DungeonPlan.model_validate_json(json.dumps(proposal["plan"]))
    compiled = compile_dungeon_plan(plan)
    assert compiled.accepted
    assert compiled.brief is not None
    assert compiled.topology is not None
    assert compiled.certificate is not None
    assert compiled.mechanics_plan is not None
    request = LayoutRequest(
        schema_version="1.0.0",
        package_id="package_prompted_fixture",
        brief=compiled.brief,
        topology=compiled.topology,
        certificate=compiled.certificate,
        seed=1842,
        generator_version="orthogonal-v1",
        mechanics_plan=compiled.mechanics_plan,
        floor_bounds=compiled.floor_bounds,
    )
    if topology_connections:
        return request
    impossible_bounds = request.floor_bounds[0].model_copy(
        update={"width_cells": 1, "height_cells": 1, "margin_cells": 0}
    )
    return request.model_copy(update={"floor_bounds": (impossible_bounds,)})


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
    assert "directly at the tool-argument root" in message
    assert "do not add a proposal envelope" in message
    assert "DungeonPlan schema version 1.0.0" in message
    assert "room_contents[].objective" in message
    assert "typed content slots" in message
    assert "conservative spatial demand" in message
    assert (
        "each non-null rooms[].encounter creates a separate later authoring task"
        in message
    )
    assert "leave it null in every room without a requested encounter" in message
    assert "do not repeat an encounter kind" in message
    assert "Do not design puzzle solutions" in message
    assert "exploration approaches or outcomes" in message
    assert "guide_content" not in message


def test_submits_one_compact_tool_call_without_a_second_completion() -> None:
    proposal = _tier_a_proposal()
    gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_plan",
                        call_id="submit-1",
                        arguments=proposal,
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
    assert profile.output_schema_version == "1.0.0"
    assert profile.prompt_version == "prompt-1"
    assert profile.instruction_version == "instructions-1"

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
    assert tool_payload["content_slots"] == {
        "puzzles": 0,
        "exploration_challenges": 0,
        "other_encounters": 0,
        "traps": 0,
        "features": 0,
        "objectives": 1,
    }
    assert tuple(schema.name for schema in gateway.tool_schemas) == (
        "submit_dungeon_plan",
    )
    assert gateway.tool_schemas[0].constrained_sampling == "prefer"
    schema_document = gateway.tool_schemas[0].parameters
    schema_text = json.dumps(schema_document)
    assert "DungeonPlan" in schema_text
    assert "DungeonGuideContentPlan" not in schema_text
    assert '"guide_content"' not in schema_text
    assert "DungeonGuidePuzzleContent" not in schema_text
    assert '"connections"' not in schema_text
    assert "proposal" not in schema_document["properties"]
    assert "plan" in schema_document["properties"]
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
                        arguments=invalid,
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
                        arguments=proposal,
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
    assert repair_document["previous_arguments"] == invalid
    repair_profile = repair_gateway.profiles[1]
    estimated_input = repair_profile.override_notes["estimated_input_tokens"]
    assert isinstance(estimated_input, int) and estimated_input > 0
    assert repair_profile.override_notes["output_token_limit"] <= (
        repair_profile.token_budget - estimated_input
    )

    exhausted_gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_plan",
                        call_id="bad-1",
                        arguments=invalid,
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
                        arguments=invalid,
                    ),
                ),
                input_tokens=10,
                output_tokens=10,
            ),
        )
    )
    with pytest.raises(DungeonProposalRejectedAfterRepair) as rejected:
        DungeonSubmissionService(exhausted_gateway).submit(
            profile=profile,
            run_input=ModelRunInput(
                messages=(PromptMessage(role="user", content="synthetic request"),)
            ),
            seed=1842,
        )
    assert [failure.attempt for failure in rejected.value.failures] == [
        "initial",
        "repair",
    ]
    assert [failure.stage for failure in rejected.value.failures] == [
        "intent_compile",
        "intent_compile",
    ]
    assert all(
        failure.diagnostics[0]["code"] == "plan.gate_dependency_unreachable"
        for failure in rejected.value.failures
    )
    report = _failure_report(rejected.value, "dungeon_prompt_rejected_after_repair")
    assert report["stage"] == "intent_compile"
    assert report["repair_attempted"] is True
    attempts = report["submission_attempts"]
    assert isinstance(attempts, list)
    assert attempts[1]["diagnostics"][0]["code"] == ("plan.gate_dependency_unreachable")

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
                        arguments=schema_invalid,
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
                        arguments=proposal,
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

    schema_exhausted_gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_plan",
                        call_id="schema-bad-initial",
                        arguments=schema_invalid,
                    ),
                ),
                input_tokens=10,
                output_tokens=10,
            ),
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_plan",
                        call_id="schema-bad-repair",
                        arguments=schema_invalid,
                    ),
                ),
                input_tokens=10,
                output_tokens=10,
            ),
        )
    )
    with pytest.raises(DungeonProposalRejectedAfterRepair) as schema_rejected:
        DungeonSubmissionService(schema_exhausted_gateway).submit(
            profile=profile,
            run_input=ModelRunInput(
                messages=(PromptMessage(role="user", content="synthetic request"),)
            ),
            seed=1842,
        )
    assert [failure.stage for failure in schema_rejected.value.failures] == [
        "model_submission",
        "model_submission",
    ]
    final_schema_diagnostic = schema_rejected.value.failures[1].diagnostics[0]
    assert final_schema_diagnostic["code"] == "submission.schema_invalid"
    assert final_schema_diagnostic["path"].endswith("/encounter")
    assert "allowed values" in final_schema_diagnostic["repair"]


def test_structural_schema_repair_removes_legacy_guide_content_only() -> None:
    proposal = _tier_a_proposal()
    malformed = deepcopy(proposal)
    malformed["guide_content"] = {"schema_version": "1.0.0", "entries": []}
    gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_plan",
                        call_id="guide-shape-bad",
                        arguments=malformed,
                    ),
                ),
                input_tokens=10,
                output_tokens=10,
            ),
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_plan",
                        call_id="guide-shape-repair",
                        arguments=proposal,
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

    assert result.repaired
    repair_document = json.loads(gateway.messages[1][0].content)
    assert repair_document["previous_arguments"] == malformed
    diagnostics = repair_document["diagnostics"]
    assert any(item["path"] == "/guide_content" for item in diagnostics)
    assert all(not item["path"].startswith("/proposal") for item in diagnostics)
    assert any(
        item.get("repair")
        == "remove this field because it is not in the submitted schema"
        for item in diagnostics
    )
    assert repair_document["previous_arguments"]["plan"] == proposal["plan"]


def test_structured_submission_fails_closed_on_measured_token_overages() -> None:
    proposal = _tier_a_proposal()
    profile = resolve_dungeon_prompt_profile(
        provider_id="faux",
        model_id="faux_deterministic_v1",
        capabilities=("text", "tool_calls"),
        context_window_tokens=16_384,
        output_token_limit=4_096,
    )

    for input_tokens, output_tokens, expected_kind in (
        (3_885, 7_747, "output"),
        (9_000, 3_500, "cumulative"),
    ):
        gateway = FakeGatewayClient(
            (
                GatewayCompletion(
                    tool_calls=(
                        ToolCall(
                            tool_name="submit_dungeon_plan",
                            call_id=f"over-{expected_kind}",
                            arguments=proposal,
                        ),
                    ),
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                ),
            )
        )
        with pytest.raises(StructuredSubmissionBudgetExceeded) as captured:
            DungeonSubmissionService(gateway).submit(
                profile=profile,
                run_input=ModelRunInput(
                    messages=(PromptMessage(role="user", content="synthetic request"),)
                ),
                seed=1842,
            )
        assert captured.value.limit_kind == expected_kind
        assert _failure_code(captured.value) == "dungeon_prompt_token_budget_exhausted"
        report = _failure_report(
            captured.value, "dungeon_prompt_token_budget_exhausted"
        )
        assert report["usage"]["input_tokens"] == input_tokens
        assert report["usage"]["output_tokens"] == output_tokens


def test_prompt_failure_report_retains_only_safe_transport_category() -> None:
    error = ModelTransportError(
        "The selected model provider rejected the request contract.",
        code="provider_request_rejected",
    )

    assert _failure_report(error, "dungeon_prompt_failed") == {
        "stage": "model_submission",
        "code": "dungeon_prompt_failed",
        "transport_error_code": "provider_request_rejected",
    }
    assert ModelTransportError("safe", code="private-provider-detail").code == (
        "model_transport_error"
    )


def test_repair_does_not_start_when_estimated_input_cannot_fit() -> None:
    proposal = _tier_a_proposal()
    malformed = deepcopy(proposal)
    malformed["unexpected"] = "schema error"
    gateway = FakeGatewayClient(
        (
            GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="submit_dungeon_plan",
                        call_id="nearly-exhausted",
                        arguments=malformed,
                    ),
                ),
                input_tokens=7_900,
                output_tokens=3_700,
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

    with pytest.raises(
        ModelRunAbstained,
        match="no budget remains for deterministic diagnostic repair",
    ):
        DungeonSubmissionService(gateway).submit(
            profile=profile,
            run_input=ModelRunInput(
                messages=(PromptMessage(role="user", content="synthetic request"),)
            ),
            seed=1842,
        )

    assert len(gateway.messages) == 1


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
                "detection": "Notice a hairline glyph around the chain staple.",
                "disable": "Lift the staple while grounding the copper chain.",
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
                        arguments=proposal,
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
    assert guide.traps[0].detection == (
        "Notice a hairline glyph around the chain staple."
    )
    assert guide.traps[0].disable == (
        "Lift the staple while grounding the copper chain."
    )
    assert guide.traps[0].detection_difficulty == 16
    assert guide.features[0].name == "Fallen Lens"
    assert guide.objectives[0].name == "Astral Lens"
    text = _dm_guide_text(guide)
    assert "## Room-by-room guide" in text
    assert "Astral Lens" in text
    assert "#### Ambush scene pressure" in text
    assert "not yet populated" not in text
    assert "unlock DC 13" in text
    assert "**Consequence:** A thunderous ward sounds." in text
    readiness = _build_preparation_readiness(guide)
    assert readiness is not None and not readiness.ready
    assert len(readiness.diagnostics) == len(guide.content_issues)
    assert {item.code for item in readiness.diagnostics} == {
        "dungeon_preparation.guide_content_missing"
    }
    ready_specification = DungeonStudioSpecification(
        schema_version="1.0.0",
        layout_request=result.layout_request,
        package=layout.package,
        dm_guide=guide,
        preparation_readiness=readiness,
        model_lineage=(_lineage(result.model_run),),
    )
    quality = evaluate_dungeon_guide_quality(ready_specification)
    assert not quality.automated_pass
    prep_check = next(
        item for item in quality.checks if item.dimension == "prep_usefulness"
    )
    assert prep_check.diagnostics == (
        "guide_quality.prep.dependency_content_missing",
        "guide_quality.prep.encounter_content_missing",
        "guide_quality.prep.feature_content_missing",
        "guide_quality.prep.objective_content_missing",
        "guide_quality.prep.readiness_blocked",
        "guide_quality.prep.room_narrative_missing",
    )

    incomplete = guide.model_copy(
        update={
            "dependencies": (),
            "traps": (guide.traps[0].model_copy(update={"effect": None}),),
        }
    )
    blocked = _build_preparation_readiness(incomplete)
    assert blocked is not None and not blocked.ready
    assert {item.code for item in blocked.diagnostics} == {
        "dungeon_preparation.guide_content_missing",
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
    quality = evaluate_dungeon_guide_quality(specification)
    assert not quality.automated_pass
    failed_dimensions = {item.dimension for item in quality.checks if not item.passed}
    assert failed_dimensions == {"clue_logic", "prep_usefulness"}
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

    assert notes.room_notes[0].name == "Wet Steps"
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
