"""Diffable synthetic retrieval evaluation helpers."""

import json
from collections.abc import Callable, Sequence

from pydantic import Field

from dm_assistant.modules.library.contracts import LibraryContract, RetrievalRunMode


class RetrievalGoldenCase(LibraryContract):
    """Synthetic expected evidence for one pinned retrieval behavior."""

    case_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,79}$")
    query: str = Field(min_length=1, max_length=500)
    expected_citation_ids: tuple[str, ...] = Field(min_length=1)
    expected_mode: RetrievalRunMode


class RetrievalEvalObservation(LibraryContract):
    """Source-body-free output captured from one eval execution."""

    mode: RetrievalRunMode
    selected_citation_ids: tuple[str, ...]
    duration_milliseconds: float = Field(ge=0)
    retrieval_versions: dict[str, str]


class RetrievalEvalResult(LibraryContract):
    """Diffable recall and latency outcome for one synthetic golden case."""

    case_id: str
    expected_mode: RetrievalRunMode
    observed_mode: RetrievalRunMode
    expected_citation_ids: tuple[str, ...]
    selected_citation_ids: tuple[str, ...]
    source_recall: float = Field(ge=0, le=1)
    exact_selection_match: bool
    duration_milliseconds: float = Field(ge=0)
    retrieval_versions: dict[str, str]


def evaluate_retrieval_cases(
    cases: Sequence[RetrievalGoldenCase],
    execute: Callable[[RetrievalGoldenCase], RetrievalEvalObservation],
) -> tuple[RetrievalEvalResult, ...]:
    """Evaluate golden source recall without retaining query/source bodies in reports."""

    outcomes: list[RetrievalEvalResult] = []
    for case in sorted(cases, key=lambda item: item.case_id):
        observation = execute(case)
        expected = set(case.expected_citation_ids)
        selected = set(observation.selected_citation_ids)
        outcomes.append(
            RetrievalEvalResult(
                case_id=case.case_id,
                expected_mode=case.expected_mode,
                observed_mode=observation.mode,
                expected_citation_ids=case.expected_citation_ids,
                selected_citation_ids=observation.selected_citation_ids,
                source_recall=len(expected & selected) / len(expected),
                exact_selection_match=(
                    case.expected_citation_ids == observation.selected_citation_ids
                ),
                duration_milliseconds=observation.duration_milliseconds,
                retrieval_versions=observation.retrieval_versions,
            )
        )
    return tuple(outcomes)


def render_retrieval_eval_report(results: Sequence[RetrievalEvalResult]) -> str:
    """Render canonical JSON so retrieval changes have reviewable diffs."""

    payload = [result.model_dump(mode="json") for result in results]
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"