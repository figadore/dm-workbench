"""Frozen synthetic alpha V1 dungeon-intent evaluation coverage."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from dm_assistant.orchestration.dungeons.evals import (
    DUNGEON_INTENT_EVAL_POLICY,
    DungeonIntentEvalCase,
    DungeonTierAEvalManifest,
    DungeonTierAHumanReview,
    DungeonTierARunMeasurement,
    DungeonTierAScore,
    aggregate_dungeon_tier_a_evidence,
    evaluate_dungeon_intent_cases,
    render_dungeon_intent_eval_report,
    summarize_dungeon_intent_evals,
    validate_dungeon_tier_a_evidence_matrix,
)

_GOLDEN_PATH = Path(__file__).parent / "golden" / "dungeon_intent.json"
_TIER_A_MANIFEST_PATH = (
    Path(__file__).parent / "golden" / "dungeon_tier_a_manifest.json"
)


def _cases() -> tuple[DungeonIntentEvalCase, ...]:
    values = json.loads(_GOLDEN_PATH.read_text(encoding="utf-8"))
    return tuple(DungeonIntentEvalCase.model_validate(value) for value in values)


def test_synthetic_suite_covers_compact_success_repair_and_abstention() -> None:
    cases = _cases()
    results = evaluate_dungeon_intent_cases(cases)
    summary = summarize_dungeon_intent_evals(results)

    assert DUNGEON_INTENT_EVAL_POLICY == "dungeon-intent-eval"
    assert len(cases) == 9
    assert {case.case_id for case in cases} == {
        "one_floor",
        "optional_branch",
        "branch_loop",
        "secret_route",
        "clue_gate",
        "trapped_room",
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


def test_tier_a_manifest_has_distinct_blinded_multi_case_coverage() -> None:
    manifest = DungeonTierAEvalManifest.model_validate_json(
        _TIER_A_MANIFEST_PATH.read_text(encoding="utf-8")
    )

    assert tuple(case.case_id for case in manifest.cases) == (
        "tier_a_case_01",
        "tier_a_case_02",
        "tier_a_case_03",
    )
    assert len({case.setting.casefold() for case in manifest.cases}) == 3
    assert len({case.interaction_style.casefold() for case in manifest.cases}) == 3
    assert tuple(variant.variant_id for variant in manifest.variants) == (
        "variant_01",
        "variant_02",
        "variant_03",
    )
    assert manifest.content_policy == "synthetic-non-copyrighted-only"
    assert manifest.blinding_policy == "variant-assignment-hidden-from-reviewers"
    assert manifest.score_policy.startswith("five-point-quality")
    assert {case.grounding for case in manifest.cases} == {
        "standalone",
        "synthetic_grounded",
    }

    duplicate_style = json.loads(_TIER_A_MANIFEST_PATH.read_text(encoding="utf-8"))
    duplicate_style["cases"][1]["interaction_style"] = duplicate_style["cases"][0][
        "interaction_style"
    ]
    with pytest.raises(ValidationError, match="interaction styles must be distinct"):
        DungeonTierAEvalManifest.model_validate(duplicate_style)


def test_tier_a_evidence_requires_body_free_quality_and_run_fields() -> None:
    run = DungeonTierARunMeasurement(
        measurement_version="dungeon-tier-a-run-measurement-v1",
        run_id="run_01",
        case_id="tier_a_case_01",
        variant_id="variant_01",
        variant_assignment_hash="a" * 64,
        artifact_hash="b" * 64,
        latency_milliseconds=1_250,
        input_tokens=800,
        output_tokens=400,
        first_pass_schema_valid=True,
        first_pass_semantic_valid=False,
        first_pass_valid=False,
        repair_count=1,
        final_valid=True,
    )
    assert run.artifact_hash is not None
    review = DungeonTierAHumanReview(
        rubric_version="dungeon-tier-a-human-rubric-v1",
        review_id="review_01",
        reviewer_id="reviewer_01",
        case_id=run.case_id,
        variant_id=run.variant_id,
        artifact_hash=run.artifact_hash,
        thematic_reinforcement=4,
        history_environment_causality=4,
        mechanic_objective_unity=3,
        progression=4,
        intentional_motif_variation=3,
        lore_consistency=None,
        clue_logic=4,
        player_agency=5,
        puzzle_comprehensibility=4,
        exploration_quality=5,
        dm_prep_usefulness=4,
    )

    assert run.repair_count == 1
    assert review.dm_prep_usefulness == 4
    assert "provider" not in review.model_dump_json()
    assert "response" not in run.model_dump_json()

    with pytest.raises(ValidationError, match="provider_response"):
        DungeonTierAHumanReview.model_validate(
            {**review.model_dump(), "provider_response": "must not be retained"}
        )


def _tier_a_evidence() -> tuple[
    DungeonTierAEvalManifest,
    tuple[DungeonTierARunMeasurement, ...],
    tuple[DungeonTierAHumanReview, ...],
]:
    manifest = DungeonTierAEvalManifest.model_validate_json(
        _TIER_A_MANIFEST_PATH.read_text(encoding="utf-8")
    )
    measurements: list[DungeonTierARunMeasurement] = []
    reviews: list[DungeonTierAHumanReview] = []
    for variant_number, variant in enumerate(manifest.variants, start=1):
        score: DungeonTierAScore = (3, 4, 5)[variant_number - 1]
        assignment_hash = f"{variant_number:x}" * 64
        for case_number, case in enumerate(manifest.cases, start=1):
            artifact_hash = f"{variant_number:x}{case_number:x}" * 32
            measurements.append(
                DungeonTierARunMeasurement(
                    measurement_version=manifest.measurement_version,
                    run_id=f"run_{case_number}_{variant_number}",
                    case_id=case.case_id,
                    variant_id=variant.variant_id,
                    variant_assignment_hash=assignment_hash,
                    artifact_hash=artifact_hash,
                    latency_milliseconds=variant_number * 1_000 + case_number * 100,
                    input_tokens=variant_number * 100 + case_number * 10,
                    output_tokens=variant_number * 50 + case_number * 5,
                    first_pass_schema_valid=case_number != 1,
                    first_pass_semantic_valid=case_number != 1,
                    first_pass_valid=case_number != 1,
                    repair_count=1 if case_number == 1 else 0,
                    final_valid=True,
                )
            )
            reviews.append(
                DungeonTierAHumanReview(
                    rubric_version=manifest.rubric_version,
                    review_id=f"review_{case_number}_{variant_number}",
                    reviewer_id="reviewer_fixture",
                    case_id=case.case_id,
                    variant_id=variant.variant_id,
                    artifact_hash=artifact_hash,
                    thematic_reinforcement=score,
                    history_environment_causality=score,
                    mechanic_objective_unity=score,
                    progression=score,
                    intentional_motif_variation=score,
                    lore_consistency=(
                        score if case.grounding == "synthetic_grounded" else None
                    ),
                    clue_logic=score,
                    player_agency=score,
                    puzzle_comprehensibility=score,
                    exploration_quality=score,
                    dm_prep_usefulness=score,
                )
            )
    return manifest, tuple(measurements), tuple(reviews)


def test_tier_a_evidence_matrix_requires_exact_coherent_coverage() -> None:
    manifest, measurements, reviews = _tier_a_evidence()
    matrix = validate_dungeon_tier_a_evidence_matrix(manifest, measurements, reviews)

    assert len(matrix.run_measurements) == 9
    assert len(matrix.human_reviews) == 9

    with pytest.raises(ValueError, match="missing run evidence"):
        validate_dungeon_tier_a_evidence_matrix(manifest, measurements[:-1], reviews)
    with pytest.raises(ValueError, match="duplicate run evidence"):
        validate_dungeon_tier_a_evidence_matrix(
            manifest, (*measurements, measurements[0]), reviews
        )
    with pytest.raises(ValueError, match="missing review evidence"):
        validate_dungeon_tier_a_evidence_matrix(manifest, measurements, reviews[:-1])
    with pytest.raises(ValueError, match="duplicate review evidence"):
        validate_dungeon_tier_a_evidence_matrix(
            manifest, measurements, (*reviews, reviews[0])
        )

    drifted_runs = (
        measurements[0].model_copy(update={"variant_assignment_hash": "f" * 64}),
        *measurements[1:],
    )
    with pytest.raises(ValueError, match="assignment hash drift"):
        validate_dungeon_tier_a_evidence_matrix(manifest, drifted_runs, reviews)

    mismatched_reviews = (
        reviews[0].model_copy(update={"artifact_hash": "e" * 64}),
        *reviews[1:],
    )
    with pytest.raises(ValueError, match="artifact hash mismatch"):
        validate_dungeon_tier_a_evidence_matrix(
            manifest, measurements, mismatched_reviews
        )


@pytest.mark.parametrize(
    ("review_index", "lore_consistency", "message"),
    (
        (0, 3, "standalone review must omit lore consistency"),
        (1, None, "grounded review requires lore consistency"),
    ),
)
def test_tier_a_evidence_matrix_enforces_lore_applicability(
    review_index: int,
    lore_consistency: int | None,
    message: str,
) -> None:
    manifest, measurements, reviews = _tier_a_evidence()
    invalid_reviews = list(reviews)
    invalid_reviews[review_index] = invalid_reviews[review_index].model_copy(
        update={"lore_consistency": lore_consistency}
    )

    with pytest.raises(ValueError, match=message):
        validate_dungeon_tier_a_evidence_matrix(
            manifest, measurements, tuple(invalid_reviews)
        )


def test_tier_a_blinded_aggregation_includes_all_ratings_and_run_statistics() -> None:
    manifest, measurements, reviews = _tier_a_evidence()
    matrix = validate_dungeon_tier_a_evidence_matrix(manifest, measurements, reviews)
    aggregate = aggregate_dungeon_tier_a_evidence(matrix)

    assert tuple(item.variant_id for item in aggregate.variants) == (
        "variant_01",
        "variant_02",
        "variant_03",
    )
    first = aggregate.variants[0]
    assert first.case_count == 3
    assert first.thematic_reinforcement_mean == 3.0
    assert first.history_environment_causality_mean == 3.0
    assert first.mechanic_objective_unity_mean == 3.0
    assert first.progression_mean == 3.0
    assert first.intentional_motif_variation_mean == 3.0
    assert first.lore_consistency_mean == 3.0
    assert first.lore_consistency_rating_count == 1
    assert first.clue_logic_mean == 3.0
    assert first.player_agency_mean == 3.0
    assert first.puzzle_comprehensibility_mean == 3.0
    assert first.exploration_quality_mean == 3.0
    assert first.dm_prep_usefulness_mean == 3.0
    assert first.mean_latency_milliseconds == 1_200.0
    assert first.mean_input_tokens == 120.0
    assert first.mean_output_tokens == 60.0
    assert first.mean_total_tokens == 180.0
    assert first.first_pass_validity_rate == pytest.approx(2 / 3)
    assert first.repair_rate == pytest.approx(1 / 3)

    # Fixture scores exercise arithmetic only and are not stored quality evidence.
    blinded_json = aggregate.model_dump_json()
    assert "variant_assignment_hash" not in blinded_json
    assert "artifact_hash" not in blinded_json
    assert "reviewer_id" not in blinded_json
    assert "run_id" not in blinded_json


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
