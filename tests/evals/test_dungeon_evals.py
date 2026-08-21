"""Frozen synthetic V2 dungeon-intent evaluation coverage."""

import json
from pathlib import Path

import pytest

from dm_assistant.orchestration.dungeons.evals import (
    DUNGEON_INTENT_V2_EVAL_POLICY,
    DungeonIntentComparisonObservation,
    DungeonIntentV2EvalCase,
    compare_dungeon_intent_versions,
    evaluate_dungeon_intent_v2_cases,
    render_dungeon_intent_v2_eval_report,
    summarize_dungeon_intent_v2_evals,
)

_GOLDEN_PATH = Path(__file__).parent / "golden" / "dungeon_intent_v2.json"


def _cases() -> tuple[DungeonIntentV2EvalCase, ...]:
    values = json.loads(_GOLDEN_PATH.read_text(encoding="utf-8"))
    return tuple(DungeonIntentV2EvalCase.model_validate(value) for value in values)


def test_v2_synthetic_suite_covers_compact_success_repair_and_abstention() -> None:
    cases = _cases()
    results = evaluate_dungeon_intent_v2_cases(cases)
    summary = summarize_dungeon_intent_v2_evals(results)

    assert len(cases) == 10
    assert {case.case_id for case in cases} == {
        "one_floor",
        "two_floor",
        "secret_lower_level",
        "branch_loop",
        "clue_gate",
        "trapped_route",
        "optional_hidden_area",
        "final_relic",
        "invalid_reference_repair",
        "impossible_request",
    }
    assert tuple(result.case_id for result in results) == tuple(
        sorted(case.case_id for case in cases)
    )
    assert (
        next(
            result for result in results if result.case_id == "impossible_request"
        ).first_pass
        == "abstained"
    )
    assert next(
        result for result in results if result.case_id == "invalid_reference_repair"
    ).accepted_after_repair
    assert summary.semantics_preserved_rate == 1.0
    assert summary.deterministic_replay_rate == 1.0
    assert summary.player_secret_leak_count == 0
    assert summary.expected_outcome_match is True
    assert "Synthetic" not in render_dungeon_intent_v2_eval_report(summary)


def test_comparison_uses_only_separate_body_free_observations() -> None:
    observations = tuple(
        DungeonIntentComparisonObservation(
            case_id="one_floor",
            generation_version=version,
            provider_response_sha256=("a" if version == "v1" else "b") * 64,
            tool_compliant=True,
            first_pass_schema_valid=True,
            first_pass_compile_valid=True,
            accepted_after_one_repair=True,
            requested_semantics_preserved=True,
            deterministic_package_valid=True,
            player_secret_leak=False,
            input_tokens=10,
            output_tokens=20,
            latency_milliseconds=30,
            dm_edited=False,
        )
        for version in ("v1", "v2")
    )

    summaries = compare_dungeon_intent_versions(observations)

    assert DUNGEON_INTENT_V2_EVAL_POLICY == "dungeon-intent-v2-eval"
    assert [item.generation_version for item in summaries] == ["v1", "v2"]
    assert all(item.measured_output_tokens == 20 for item in summaries)
    assert all(item.player_secret_leak_count == 0 for item in summaries)

    mismatched = observations[1].model_copy(update={"case_id": "two_floor"})
    with pytest.raises(ValueError, match="matching V1 and V2 case IDs"):
        compare_dungeon_intent_versions((observations[0], mismatched))


def test_v2_eval_summary_passes_only_the_synthetic_thresholds() -> None:
    results = evaluate_dungeon_intent_v2_cases(_cases())
    summary = summarize_dungeon_intent_v2_evals(results)

    # This provider-free fixture check does not replace the required faux,
    # CLI/web/cancellation/publication, or opt-in live-model evidence.
    assert summary.passes_synthetic_thresholds is True

    mismatched = (
        results[0].model_copy(update={"expected_first_pass_matches": False}),
        *results[1:],
    )
    assert (
        summarize_dungeon_intent_v2_evals(mismatched).passes_synthetic_thresholds
        is False
    )
