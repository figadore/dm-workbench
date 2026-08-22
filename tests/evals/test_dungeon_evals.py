"""Frozen synthetic alpha V1 dungeon-intent evaluation coverage."""

import json
from pathlib import Path

from dm_assistant.orchestration.dungeons.evals import (
    DUNGEON_INTENT_EVAL_POLICY,
    DungeonIntentEvalCase,
    evaluate_dungeon_intent_cases,
    render_dungeon_intent_eval_report,
    summarize_dungeon_intent_evals,
)

_GOLDEN_PATH = Path(__file__).parent / "golden" / "dungeon_intent.json"


def _cases() -> tuple[DungeonIntentEvalCase, ...]:
    values = json.loads(_GOLDEN_PATH.read_text(encoding="utf-8"))
    return tuple(DungeonIntentEvalCase.model_validate(value) for value in values)


def test_synthetic_suite_covers_compact_success_repair_and_abstention() -> None:
    cases = _cases()
    results = evaluate_dungeon_intent_cases(cases)
    summary = summarize_dungeon_intent_evals(results)

    assert DUNGEON_INTENT_EVAL_POLICY == "dungeon-intent-eval"
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
    assert "Synthetic" not in render_dungeon_intent_eval_report(summary)


def test_eval_summary_passes_only_the_synthetic_thresholds() -> None:
    results = evaluate_dungeon_intent_cases(_cases())
    summary = summarize_dungeon_intent_evals(results)

    # This provider-free fixture check does not replace the required faux,
    # CLI/web/cancellation/publication, or opt-in live-model evidence.
    assert summary.passes_synthetic_thresholds is True

    mismatched = (
        results[0].model_copy(update={"expected_first_pass_matches": False}),
        *results[1:],
    )
    assert (
        summarize_dungeon_intent_evals(mismatched).passes_synthetic_thresholds is False
    )
