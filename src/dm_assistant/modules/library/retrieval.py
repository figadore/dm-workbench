"""Filtered PostgreSQL lexical retrieval over active corpus snapshots."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TypeAlias

from sqlalchemy import Engine, Text, and_, case, cast, func, select

from dm_assistant.adapters.embeddings import EmbeddingProvider
from dm_assistant.db import build_session_factory
from dm_assistant.modules.library.contracts import (
    AuthorityClass,
    HybridRetrievalMode,
    HybridSearchQuery,
    HybridSearchResponse,
    HybridSearchResult,
    LexicalSearchQuery,
    LexicalSearchResult,
    NeighboringChunk,
    SnapshotState,
    VectorRetrievalMode,
    VectorSearchQuery,
    VectorSearchResponse,
    VectorSearchResult,
)

_RankedResult: TypeAlias = LexicalSearchResult | VectorSearchResult


@dataclass(frozen=True)
class _FusionCandidate:
    result: _RankedResult
    score: float
    lexical_rank: int | None
    vector_rank: int | None
from dm_assistant.modules.library.models import (
    CorpusSnapshot,
    CorpusSnapshotDocument,
    DocumentChunk,
    DocumentChunkEmbedding,
    DocumentRevision,
    EmbeddingProfile,
    EmbeddingRun,
    EmbeddingRunItem,
    Vector,
)


class LibraryLexicalSearchService:
    """Search only evidence authorized by scope and active snapshot state."""

    def __init__(self, engine: Engine) -> None:
        self._session_factory = build_session_factory(engine)

    def search(self, request: LexicalSearchQuery) -> tuple[LexicalSearchResult, ...]:
        """Return bounded lexical evidence from one active snapshot."""
        with self._session_factory() as session:
            tsquery = func.websearch_to_tsquery("simple", request.query)
            conditions = _authorized_chunk_conditions(request)
            conditions.append(DocumentChunk.search_vector.op("@@")(tsquery))

            heading_text = cast(DocumentChunk.heading_path, Text)
            exact_query = f"%{request.query}%"
            score = (
                func.ts_rank_cd(DocumentChunk.search_vector, tsquery)
                + case((heading_text.ilike(exact_query), 0.5), else_=0.0)
                + case((DocumentChunk.content.ilike(exact_query), 0.25), else_=0.0)
            ).label("score")
            statement = (
                select(
                    DocumentChunk.id,
                    CorpusSnapshotDocument.document_id,
                    DocumentChunk.document_revision_id,
                    DocumentChunk.heading_path,
                    DocumentChunk.start_offset,
                    DocumentChunk.end_offset,
                    DocumentChunk.content,
                    score,
                )
                .join(
                    CorpusSnapshotDocument,
                    CorpusSnapshotDocument.document_revision_id
                    == DocumentChunk.document_revision_id,
                )
                .join(
                    CorpusSnapshot,
                    CorpusSnapshot.id
                    == CorpusSnapshotDocument.corpus_snapshot_id,
                )
                .join(
                    DocumentRevision,
                    DocumentRevision.id == DocumentChunk.document_revision_id,
                )
                .where(and_(*conditions))
                .order_by(score.desc(), DocumentChunk.id)
                .limit(request.limit)
            )
            rows = session.execute(statement).all()

        return tuple(
            LexicalSearchResult(
                citation_id=f"chunk:{chunk_id}",
                document_id=document_id,
                document_revision_id=revision_id,
                chunk_id=chunk_id,
                heading_path=tuple(heading_path),
                start_offset=start_offset,
                end_offset=end_offset,
                snippet=_bounded_snippet(content, request.query, request.snippet_chars),
                score=float(score),
            )
            for (
                chunk_id,
                document_id,
                revision_id,
                heading_path,
                start_offset,
                end_offset,
                content,
                score,
            ) in rows
        )


class LibraryVectorSearchService:
    """Rank only pre-filtered snapshot chunks covered by a completed embedding run."""

    def __init__(self, engine: Engine, lexical_search: LibraryLexicalSearchService) -> None:
        self._session_factory = build_session_factory(engine)
        self._lexical_search = lexical_search

    def search(
        self,
        request: VectorSearchQuery,
        provider: EmbeddingProvider,
    ) -> VectorSearchResponse:
        """Return vector evidence, or safe filtered lexical evidence on any fallback path."""
        with self._session_factory() as session:
            run_and_profile = session.execute(
                select(EmbeddingRun, EmbeddingProfile)
                .join(
                    EmbeddingProfile,
                    EmbeddingProfile.id == EmbeddingRun.embedding_profile_id,
                )
                .join(
                    CorpusSnapshot,
                    CorpusSnapshot.id == EmbeddingRun.corpus_snapshot_id,
                )
                .where(
                    EmbeddingRun.id == request.embedding_run_id,
                    EmbeddingRun.status == "succeeded",
                    EmbeddingRun.corpus_snapshot_id == request.lexical.snapshot_id,
                    CorpusSnapshot.state == SnapshotState.ACTIVE.value,
                    CorpusSnapshot.campaign_id == request.lexical.scope.campaign_id,
                    CorpusSnapshot.corpus == request.lexical.scope.corpus.value,
                    EmbeddingProfile.enabled.is_(True),
                )
            ).one_or_none()
            if run_and_profile is None:
                return self._lexical_fallback(request.lexical)
            run, profile = run_and_profile
            if not _provider_matches_profile(provider, profile):
                return self._lexical_fallback(request.lexical)
            try:
                query_vector = provider.embed_query(request.lexical.query)
            except Exception:
                return self._lexical_fallback(request.lexical)
            if len(query_vector.values) != run.dimensions:
                return self._lexical_fallback(request.lexical)

            distance = _distance_expression(profile.distance_metric, query_vector.values)
            conditions = _authorized_chunk_conditions(request.lexical)
            conditions.extend(
                (
                    EmbeddingRun.id == run.id,
                    EmbeddingRun.status == "succeeded",
                    EmbeddingRunItem.status.in_(("succeeded", "skipped")),
                    DocumentChunkEmbedding.embedding_profile_id
                    == run.embedding_profile_id,
                )
            )
            statement = (
                select(
                    DocumentChunk.id,
                    CorpusSnapshotDocument.document_id,
                    DocumentChunk.document_revision_id,
                    DocumentChunk.heading_path,
                    DocumentChunk.start_offset,
                    DocumentChunk.end_offset,
                    DocumentChunk.content,
                    distance,
                )
                .join(
                    CorpusSnapshotDocument,
                    CorpusSnapshotDocument.document_revision_id
                    == DocumentChunk.document_revision_id,
                )
                .join(
                    CorpusSnapshot,
                    CorpusSnapshot.id == CorpusSnapshotDocument.corpus_snapshot_id,
                )
                .join(
                    EmbeddingRun,
                    EmbeddingRun.corpus_snapshot_id == CorpusSnapshot.id,
                )
                .join(
                    EmbeddingRunItem,
                    and_(
                        EmbeddingRunItem.embedding_run_id == EmbeddingRun.id,
                        EmbeddingRunItem.document_chunk_id == DocumentChunk.id,
                        EmbeddingRunItem.chunk_content_hash == DocumentChunk.content_hash,
                    ),
                )
                .join(
                    DocumentChunkEmbedding,
                    and_(
                        DocumentChunkEmbedding.id
                        == EmbeddingRunItem.document_chunk_embedding_id,
                        DocumentChunkEmbedding.document_chunk_id == DocumentChunk.id,
                        DocumentChunkEmbedding.chunk_content_hash
                        == DocumentChunk.content_hash,
                    ),
                )
                .join(
                    DocumentRevision,
                    DocumentRevision.id == DocumentChunk.document_revision_id,
                )
                .where(and_(*conditions))
                .order_by(distance, DocumentChunk.id)
                .limit(request.lexical.limit)
            )
            rows = session.execute(statement).all()

        return VectorSearchResponse(
            mode=VectorRetrievalMode.VECTOR,
            results=tuple(
                VectorSearchResult(
                    citation_id=f"chunk:{chunk_id}",
                    document_id=document_id,
                    document_revision_id=revision_id,
                    chunk_id=chunk_id,
                    heading_path=tuple(heading_path),
                    start_offset=start_offset,
                    end_offset=end_offset,
                    snippet=_bounded_snippet(
                        content,
                        request.lexical.query,
                        request.lexical.snippet_chars,
                    ),
                    score=-float(distance),
                )
                for (
                    chunk_id,
                    document_id,
                    revision_id,
                    heading_path,
                    start_offset,
                    end_offset,
                    content,
                    distance,
                ) in rows
            ),
        )

    def _lexical_fallback(self, request: LexicalSearchQuery) -> VectorSearchResponse:
        return VectorSearchResponse(
            mode=VectorRetrievalMode.LEXICAL_FALLBACK,
            results=tuple(
                VectorSearchResult.model_validate(result.model_dump())
                for result in self._lexical_search.search(request)
            ),
        )


class LibraryHybridSearchService:
    """Fuse bounded, authorized rankings without exposing raw vector candidates."""

    def __init__(
        self,
        engine: Engine,
        lexical_search: LibraryLexicalSearchService,
        vector_search: LibraryVectorSearchService,
    ) -> None:
        self._session_factory = build_session_factory(engine)
        self._lexical_search = lexical_search
        self._vector_search = vector_search

    def search(
        self,
        request: HybridSearchQuery,
        provider: EmbeddingProvider,
    ) -> HybridSearchResponse:
        """Fuse lexical/vector ranks or retain lexical-only behavior on fallback."""
        lexical_results = self._lexical_search.search(request.lexical)
        vector_response = self._vector_search.search(
            VectorSearchQuery(
                lexical=request.lexical,
                embedding_run_id=request.embedding_run_id,
            ),
            provider,
        )
        vector_results: tuple[VectorSearchResult, ...] = ()
        mode = HybridRetrievalMode.LEXICAL_FALLBACK
        if vector_response.mode is VectorRetrievalMode.VECTOR:
            vector_results = vector_response.results
            mode = HybridRetrievalMode.HYBRID
        fused = _fuse_rankings(
            lexical_results,
            vector_results,
            query=request.lexical.query,
            rank_constant=request.rrf_rank_constant,
            exact_name_boost=request.exact_name_boost,
            limit=request.lexical.limit,
        )
        return HybridSearchResponse(
            mode=mode,
            rrf_version=request.rrf_version,
            results=tuple(
                result.model_copy(
                    update={
                        "neighboring_chunks": self._neighboring_chunks(
                            result,
                            request.lexical,
                            request.neighboring_chunks_each_side,
                        )
                    }
                )
                for result in fused
            ),
        )

    def _neighboring_chunks(
        self,
        selected: HybridSearchResult,
        request: LexicalSearchQuery,
        each_side: int,
    ) -> tuple[NeighboringChunk, ...]:
        if each_side == 0:
            return ()
        with self._session_factory() as session:
            selected_chunk = session.get(DocumentChunk, selected.chunk_id)
            if selected_chunk is None:
                return ()
            conditions = _authorized_chunk_conditions(request)
            conditions.append(
                DocumentChunk.document_revision_id == selected.document_revision_id
            )
            base_statement = (
                select(
                    DocumentChunk.id,
                    DocumentChunk.heading_path,
                    DocumentChunk.start_offset,
                    DocumentChunk.end_offset,
                    DocumentChunk.content,
                )
                .join(
                    CorpusSnapshotDocument,
                    CorpusSnapshotDocument.document_revision_id
                    == DocumentChunk.document_revision_id,
                )
                .join(
                    CorpusSnapshot,
                    CorpusSnapshot.id == CorpusSnapshotDocument.corpus_snapshot_id,
                )
                .join(
                    DocumentRevision,
                    DocumentRevision.id == DocumentChunk.document_revision_id,
                )
                .where(and_(*conditions))
            )
            before = session.execute(
                base_statement.where(DocumentChunk.ordinal < selected_chunk.ordinal)
                .order_by(DocumentChunk.ordinal.desc())
                .limit(each_side)
            ).all()
            after = session.execute(
                base_statement.where(DocumentChunk.ordinal > selected_chunk.ordinal)
                .order_by(DocumentChunk.ordinal)
                .limit(each_side)
            ).all()
        ordered_rows = (*reversed(before), *after)
        return tuple(
            NeighboringChunk(
                citation_id=f"chunk:{chunk_id}",
                chunk_id=chunk_id,
                heading_path=tuple(heading_path),
                start_offset=start_offset,
                end_offset=end_offset,
                snippet=_bounded_snippet(content, request.query, request.snippet_chars),
            )
            for chunk_id, heading_path, start_offset, end_offset, content in ordered_rows
        )


def _authorized_chunk_conditions(request: LexicalSearchQuery) -> list[object]:
    conditions: list[object] = [
        CorpusSnapshot.state == SnapshotState.ACTIVE.value,
        CorpusSnapshot.campaign_id == request.scope.campaign_id,
        CorpusSnapshot.corpus == request.scope.corpus.value,
        CorpusSnapshotDocument.campaign_id == request.scope.campaign_id,
        CorpusSnapshotDocument.corpus == request.scope.corpus.value,
        DocumentChunk.campaign_id == request.scope.campaign_id,
        DocumentChunk.corpus == request.scope.corpus.value,
        DocumentChunk.visibility_policy.in_(
            policy.value for policy in request.visible_policies
        ),
    ]
    if request.snapshot_id is not None:
        conditions.append(CorpusSnapshot.id == request.snapshot_id)
    if request.authority_classes:
        conditions.append(
            DocumentChunk.authority_class.in_(
                authority.value for authority in request.authority_classes
            )
        )
    if request.rulesets:
        conditions.append(
            DocumentChunk.ruleset.in_(ruleset.value for ruleset in request.rulesets)
        )
    if not request.include_preparation:
        conditions.append(DocumentChunk.authority_class != AuthorityClass.PREPARATION.value)
    return conditions


def _fuse_rankings(
    lexical_results: tuple[LexicalSearchResult, ...],
    vector_results: tuple[VectorSearchResult, ...],
    *,
    query: str,
    rank_constant: int,
    exact_name_boost: float,
    limit: int,
) -> tuple[HybridSearchResult, ...]:
    candidates: dict[str, _FusionCandidate] = {}
    for rank, result in enumerate(lexical_results, start=1):
        candidates[result.citation_id] = _merge_fusion_candidate(
            candidates.get(result.citation_id),
            result,
            lexical_rank=rank,
            vector_rank=None,
            rank_constant=rank_constant,
        )
    for rank, result in enumerate(vector_results, start=1):
        candidates[result.citation_id] = _merge_fusion_candidate(
            candidates.get(result.citation_id),
            result,
            lexical_rank=None,
            vector_rank=rank,
            rank_constant=rank_constant,
        )
    ordered = sorted(
        candidates.values(),
        key=lambda candidate: (
            -(
                candidate.score
                + _exact_name_bonus(candidate.result, query, exact_name_boost)
            ),
            candidate.result.citation_id,
        ),
    )
    selected: list[_FusionCandidate] = []
    for candidate in ordered:
        if any(_overlapping_spans(candidate.result, kept.result) for kept in selected):
            continue
        selected.append(candidate)
        if len(selected) == limit:
            break
    return tuple(
        HybridSearchResult(
            citation_id=candidate.result.citation_id,
            document_id=candidate.result.document_id,
            document_revision_id=candidate.result.document_revision_id,
            chunk_id=candidate.result.chunk_id,
            heading_path=candidate.result.heading_path,
            start_offset=candidate.result.start_offset,
            end_offset=candidate.result.end_offset,
            snippet=candidate.result.snippet,
            score=candidate.score
            + _exact_name_bonus(candidate.result, query, exact_name_boost),
            lexical_rank=candidate.lexical_rank,
            vector_rank=candidate.vector_rank,
        )
        for candidate in selected
    )


def _merge_fusion_candidate(
    existing: _FusionCandidate | None,
    result: _RankedResult,
    *,
    lexical_rank: int | None,
    vector_rank: int | None,
    rank_constant: int,
) -> _FusionCandidate:
    lexical_score = 0.0 if lexical_rank is None else 1 / (rank_constant + lexical_rank)
    vector_score = 0.0 if vector_rank is None else 1 / (rank_constant + vector_rank)
    if existing is None:
        return _FusionCandidate(
            result=result,
            score=lexical_score + vector_score,
            lexical_rank=lexical_rank,
            vector_rank=vector_rank,
        )
    return _FusionCandidate(
        result=existing.result,
        score=existing.score + lexical_score + vector_score,
        lexical_rank=existing.lexical_rank or lexical_rank,
        vector_rank=existing.vector_rank or vector_rank,
    )


def _exact_name_bonus(
    result: _RankedResult,
    query: str,
    boost: float,
) -> float:
    normalized_query = query.casefold().strip()
    if not normalized_query:
        return 0.0
    heading = " ".join(result.heading_path).casefold()
    return boost if normalized_query in heading or normalized_query in result.snippet.casefold() else 0.0


def _overlapping_spans(first: _RankedResult, second: _RankedResult) -> bool:
    return (
        first.document_revision_id == second.document_revision_id
        and first.start_offset < second.end_offset
        and second.start_offset < first.end_offset
    )


def _provider_matches_profile(
    provider: EmbeddingProvider,
    profile: EmbeddingProfile,
) -> bool:
    return (
        provider.profile.runtime_kind.value == profile.runtime_kind
        and provider.profile.provider == profile.provider
        and provider.profile.model == profile.model
        and provider.profile.model_revision == profile.model_revision
        and provider.profile.dimensions == profile.dimensions
        and provider.profile.distance_metric.value == profile.distance_metric
        and provider.profile.normalization_version == profile.normalization_version
        and provider.profile.preprocessing_version == profile.preprocessing_version
        and provider.profile.config_hash == profile.config_hash
    )


def _distance_expression(distance_metric: str, values: tuple[float, ...]):
    query_vector = cast(_vector_literal(values), Vector())
    operator = {
        "cosine": "<=>",
        "euclidean": "<->",
        "inner_product": "<#>",
    }[distance_metric]
    return DocumentChunkEmbedding.embedding.op(operator)(query_vector).label("distance")


def _vector_literal(values: tuple[float, ...]) -> str:
    return "[" + ",".join(format(value, ".17g") for value in values) + "]"


def _bounded_snippet(content: str, query: str, limit: int) -> str:
    if len(content) <= limit:
        return content
    terms = [term for term in re.findall(r"\w+", query, flags=re.UNICODE) if term]
    lowered = content.casefold()
    position = min(
        (lowered.find(term.casefold()) for term in terms if lowered.find(term.casefold()) >= 0),
        default=0,
    )
    start = max(0, position - limit // 3)
    end = min(len(content), start + limit)
    snippet = content[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(content):
        snippet += "..."
    return snippet
