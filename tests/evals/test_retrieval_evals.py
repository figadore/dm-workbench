"""Synthetic, deterministic golden retrieval evaluation coverage."""

import json
from pathlib import Path

from dm_assistant.modules.library.evals import (
    RetrievalEvalObservation,
    RetrievalGoldenCase,
    evaluate_retrieval_cases,
    render_retrieval_eval_report,
)

_GOLDEN_PATH = Path(__file__).parent / "golden" / "retrieval_v1.json"


def _golden_cases() -> tuple[RetrievalGoldenCase, ...]:
    values = json.loads(_GOLDEN_PATH.read_text(encoding="utf-8"))
    return tuple(
        RetrievalGoldenCase.model_validate_json(json.dumps(value)) for value in values
    )


def test_retrieval_golden_cases_report_deterministic_recall_and_latency() -> None:
    cases = _golden_cases()

    def execute(case: RetrievalGoldenCase) -> RetrievalEvalObservation:
        return RetrievalEvalObservation(
            mode=case.expected_mode,
            selected_citation_ids=case.expected_citation_ids,
            duration_milliseconds=12.5,
            retrieval_versions={
                "fusion": "rrf-v1",
                "lexical": "postgresql-fts-v1",
                "vector": "pgvector-v1",
            },
        )

    first = evaluate_retrieval_cases(cases, execute)
    second = evaluate_retrieval_cases(cases, execute)

    assert tuple(result.case_id for result in first) == tuple(
        sorted(case.case_id for case in cases)
    )
    assert all(result.source_recall == 1.0 for result in first)
    assert all(result.exact_selection_match for result in first)
    assert render_retrieval_eval_report(first) == render_retrieval_eval_report(second)
    assert "the token recovered" not in render_retrieval_eval_report(first)


def test_retrieval_eval_reports_missing_expected_sources() -> None:
    case = _golden_cases()[0]

    results = evaluate_retrieval_cases(
        (case,),
        lambda _: RetrievalEvalObservation(
            mode=case.expected_mode,
            selected_citation_ids=(),
            duration_milliseconds=1.0,
            retrieval_versions={"lexical": "postgresql-fts-v1"},
        ),
    )

    assert results[0].source_recall == 0.0
    assert not results[0].exact_selection_match