"""Body-free staged dungeon abstention diagnostic coverage."""

import json
from collections.abc import Callable

import pytest
from pydantic import JsonValue

from dm_assistant.modules.modeling import ModelRunRecord
from dm_assistant.orchestration.dungeons.application import (
    _failure_code as structural_failure_code,
)
from dm_assistant.orchestration.dungeons.application import (
    _failure_report as structural_failure_report,
)
from dm_assistant.orchestration.dungeons.exploration_application import (
    _failure_report as exploration_failure_report,
)
from dm_assistant.orchestration.dungeons.feature_interaction_application import (
    _failure_report as feature_failure_report,
)
from dm_assistant.orchestration.dungeons.objective_application import (
    _failure_report as objective_failure_report,
)
from dm_assistant.orchestration.dungeons.prompting import (
    resolve_dungeon_prompt_profile,
)
from dm_assistant.orchestration.dungeons.puzzle_application import (
    _failure_report as puzzle_failure_report,
)
from dm_assistant.orchestration.dungeons.room_narrative_application import (
    _failure_report as narrative_failure_report,
)
from dm_assistant.orchestration.dungeons.trap_application import (
    _failure_report as trap_failure_report,
)
from dm_assistant.orchestration.modeling import (
    ModelRunAbstained,
    StructuredSubmissionRepairBudgetExhausted,
)

FailureReport = Callable[[Exception], tuple[str, dict[str, JsonValue]]]


@pytest.mark.parametrize(
    ("failure_report", "expected_public_code"),
    (
        (puzzle_failure_report, "dungeon_puzzle_prompt_failed"),
        (exploration_failure_report, "dungeon_exploration_prompt_failed"),
        (
            feature_failure_report,
            "dungeon_feature_interaction_prompt_failed",
        ),
        (trap_failure_report, "dungeon_trap_prompt_failed"),
        (objective_failure_report, "dungeon_objective_prompt_failed"),
        (narrative_failure_report, "dungeon_room_narrative_prompt_failed"),
    ),
)
def test_staged_abstentions_retain_only_allowlisted_reason_code(
    failure_report: FailureReport,
    expected_public_code: str,
) -> None:
    error = ModelRunAbstained(
        "provider-specific text must not persist",
        code="repair_context_exceeded",
    )

    public_code, report = failure_report(error)

    assert public_code == expected_public_code
    assert report == {
        "stage": "model_submission",
        "code": expected_public_code,
        "abstention_code": "repair_context_exceeded",
    }
    assert "provider-specific text" not in json.dumps(report)


@pytest.mark.parametrize(
    ("failure_report", "expected_public_code"),
    (
        (
            puzzle_failure_report,
            "dungeon_puzzle_prompt_repair_budget_exhausted",
        ),
        (
            exploration_failure_report,
            "dungeon_exploration_prompt_repair_budget_exhausted",
        ),
        (
            feature_failure_report,
            "dungeon_feature_interaction_prompt_repair_budget_exhausted",
        ),
        (trap_failure_report, "dungeon_trap_prompt_repair_budget_exhausted"),
        (
            objective_failure_report,
            "dungeon_objective_prompt_repair_budget_exhausted",
        ),
        (
            narrative_failure_report,
            "dungeon_room_narrative_prompt_repair_budget_exhausted",
        ),
    ),
)
def test_staged_repair_budget_reports_retain_measured_arithmetic(
    failure_report: FailureReport,
    expected_public_code: str,
) -> None:
    profile = resolve_dungeon_prompt_profile(
        provider_id="faux",
        model_id="faux_deterministic_v1",
        capabilities=("text", "tool_calls"),
        context_window_tokens=16_384,
        output_token_limit=4_096,
    ).model_copy(update={"time_budget_seconds": 1})
    record = ModelRunRecord.model_construct(
        usage_measured=True,
        usage_input_tokens=7_900,
        usage_output_tokens=3_700,
        duration_ms=1_001,
    )
    error = StructuredSubmissionRepairBudgetExhausted(
        profile=profile,
        record=record,
        estimated_input_tokens=650,
    )

    public_code, report = failure_report(error)

    assert public_code == expected_public_code
    assert report["abstention_code"] == "repair_budget_exhausted"
    reserve = report["repair_reserve"]
    assert isinstance(reserve, dict)
    assert reserve["blockers"] == ["output_token_reserve", "time_reserve"]
    assert reserve["token_arithmetic"] == {
        "workflow_token_budget": 12_000,
        "initial_input_tokens": 7_900,
        "initial_output_tokens": 3_700,
        "initial_total_tokens": 11_600,
        "request_token_budget": 400,
        "estimated_input_tokens": 650,
        "output_tokens_available": -250,
        "configured_output_token_limit": 4_096,
        "effective_output_token_limit": 0,
    }
    assert reserve["time_arithmetic"] == {
        "workflow_time_budget_seconds": 1,
        "initial_duration_ms": 1_001,
        "charged_initial_seconds": 2,
        "request_time_budget_seconds": -1,
    }


def test_structural_abstention_report_uses_the_same_safe_code() -> None:
    error = ModelRunAbstained(
        "bounded repair could not run",
        code="repair_usage_unavailable",
    )
    public_code = structural_failure_code(error)

    assert public_code == "dungeon_prompt_repair_usage_unavailable"
    assert structural_failure_report(error, public_code) == {
        "stage": "model_submission",
        "code": public_code,
        "abstention_code": "repair_usage_unavailable",
    }


def test_unknown_abstention_code_falls_back_without_persisting_message() -> None:
    error = ModelRunAbstained(
        "untrusted provider response text",
        code="untrusted-provider-category",
    )

    _, report = puzzle_failure_report(error)

    assert error.code == "model_run_abstained"
    assert report["abstention_code"] == "model_run_abstained"
    assert "untrusted provider response text" not in json.dumps(report)
