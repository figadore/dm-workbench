"""Immutable, source-body-free audit records for bounded retrieval execution."""

import hashlib
import uuid
from collections.abc import Callable
from time import perf_counter_ns

from sqlalchemy import Engine

from dm_assistant.adapters.embeddings import EmbeddingProvider
from dm_assistant.db import build_session_factory, transactional_session
from dm_assistant.modules.library.contracts import (
    HybridRetrievalMode,
    HybridSearchQuery,
    RetrievalCandidateRecord,
    RetrievalRunMode,
    RetrievalRunSnapshot,
    VectorRetrievalMode,
    VectorSearchQuery,
)
from dm_assistant.modules.library.models import RetrievalRun
from dm_assistant.modules.library.retrieval import (
    LibraryHybridSearchService,
    LibraryLexicalSearchService,
    LibraryVectorSearchService,
)

_LEXICAL_RETRIEVAL_VERSION = "postgresql-fts-v1"
_VECTOR_RETRIEVAL_VERSION = "pgvector-v1"
_LEXICAL_FALLBACK_VERSION = "unavailable-v1"


class LibraryRetrievalAuditService:
    """Executes retrieval and persists only reproducible metadata/citation evidence."""

    def __init__(
        self,
        engine: Engine,
        lexical_search: LibraryLexicalSearchService,
        vector_search: LibraryVectorSearchService,
        hybrid_search: LibraryHybridSearchService,
        *,
        id_factory: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        self._session_factory = build_session_factory(engine)
        self._lexical_search = lexical_search
        self._vector_search = vector_search
        self._hybrid_search = hybrid_search
        self._id_factory = id_factory

    def search(
        self,
        request: HybridSearchQuery,
        provider: EmbeddingProvider,
    ) -> RetrievalRunSnapshot:
        """Persist one audit record for the exact resolved retrieval response."""
        started_at = perf_counter_ns()
        lexical_results = self._lexical_search.search(request.lexical)
        vector_response = self._vector_search.search(
            VectorSearchQuery(
                lexical=request.lexical,
                embedding_run_id=request.embedding_run_id,
            ),
            provider,
        )
        response = self._hybrid_search.search(request, provider)
        duration_milliseconds = (perf_counter_ns() - started_at) / 1_000_000
        vector_results = (
            vector_response.results
            if vector_response.mode is VectorRetrievalMode.VECTOR
            else ()
        )
        candidates = _candidate_records(
            lexical_results,
            vector_results,
            rank_constant=request.rrf_rank_constant,
        )
        mode = (
            RetrievalRunMode.HYBRID
            if response.mode is HybridRetrievalMode.HYBRID
            else RetrievalRunMode.LEXICAL_FALLBACK
        )
        retrieval_versions = {
            "lexical": _LEXICAL_RETRIEVAL_VERSION,
            "vector": (
                _VECTOR_RETRIEVAL_VERSION
                if mode is RetrievalRunMode.HYBRID
                else _LEXICAL_FALLBACK_VERSION
            ),
            "fusion": request.rrf_version,
        }
        with transactional_session(self._session_factory) as session:
            run = RetrievalRun(
                id=self._id_factory(),
                corpus_snapshot_id=request.lexical.snapshot_id,
                embedding_run_id=(
                    request.embedding_run_id
                    if mode is RetrievalRunMode.HYBRID
                    else None
                ),
                mode=mode.value,
                query_sha256=hashlib.sha256(
                    request.lexical.query.encode("utf-8")
                ).hexdigest(),
                retrieval_versions=retrieval_versions,
                resolved_scope=_resolved_scope(request),
                candidates=[candidate.model_dump() for candidate in candidates],
                selected_citation_ids=[
                    result.citation_id for result in response.results
                ],
                duration_milliseconds=duration_milliseconds,
            )
            session.add(run)
            session.flush()
        return RetrievalRunSnapshot(
            id=run.id,
            corpus_snapshot_id=run.corpus_snapshot_id,
            embedding_run_id=run.embedding_run_id,
            mode=RetrievalRunMode(run.mode),
            query_sha256=run.query_sha256,
            retrieval_versions=run.retrieval_versions,
            resolved_scope=run.resolved_scope,
            candidates=candidates,
            selected_citation_ids=tuple(run.selected_citation_ids),
            duration_milliseconds=run.duration_milliseconds,
        )


def _candidate_records(
    lexical_results: tuple[object, ...],
    vector_results: tuple[object, ...],
    *,
    rank_constant: int,
) -> tuple[RetrievalCandidateRecord, ...]:
    ranks: dict[str, dict[str, int]] = {}
    for rank, result in enumerate(lexical_results, start=1):
        ranks.setdefault(result.citation_id, {})["lexical"] = rank  # type: ignore[attr-defined]
    for rank, result in enumerate(vector_results, start=1):
        ranks.setdefault(result.citation_id, {})["vector"] = rank  # type: ignore[attr-defined]
    return tuple(
        RetrievalCandidateRecord(
            citation_id=citation_id,
            score=sum(1 / (rank_constant + rank) for rank in result_ranks.values()),
            lexical_rank=result_ranks.get("lexical"),
            vector_rank=result_ranks.get("vector"),
        )
        for citation_id, result_ranks in sorted(ranks.items())
    )


def _resolved_scope(request: HybridSearchQuery) -> dict[str, object]:
    lexical = request.lexical
    return {
        "campaign_id": str(lexical.scope.campaign_id)
        if lexical.scope.campaign_id is not None
        else None,
        "corpus": lexical.scope.corpus.value,
        "corpus_snapshot_id": str(lexical.snapshot_id),
        "authority_classes": [item.value for item in lexical.authority_classes],
        "visible_policies": [item.value for item in lexical.visible_policies],
        "rulesets": [item.value for item in lexical.rulesets],
        "include_preparation": lexical.include_preparation,
        "limit": lexical.limit,
        "snippet_chars": lexical.snippet_chars,
    }