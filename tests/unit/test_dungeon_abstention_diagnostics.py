"""Body-free staged dungeon abstention diagnostic coverage."""

import json
from collections.abc import Callable

import pytest
from pydantic import JsonValue

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
from dm_assistant.orchestration.dungeons.puzzle_application import (
    _failure_report as puzzle_failure_report,
)
from dm_assistant.orchestration.dungeons.room_narrative_application import (
    _failure_report as narrative_failure_report,
)
from dm_assistant.orchestration.dungeons.trap_application import (
    _failure_report as trap_failure_report,
)
from dm_assistant.orchestration.modeling import ModelRunAbstained

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
