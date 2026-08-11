"""Deterministic hybrid ranking behavior without database or provider calls."""

import uuid

from dm_assistant.modules.library.contracts import (
    LexicalSearchResult,
    VectorSearchResult,
)
from dm_assistant.modules.library.retrieval import _fuse_rankings


def _lexical_result(
    *,
    document_revision_id: uuid.UUID,
    start_offset: int,
    end_offset: int,
    snippet: str,
) -> LexicalSearchResult:
    chunk_id = uuid.uuid4()
    return LexicalSearchResult(
        citation_id=f"chunk:{chunk_id}",
        document_id=uuid.uuid4(),
        document_revision_id=document_revision_id,
        chunk_id=chunk_id,
        heading_path=("Synthetic Heading",),
        start_offset=start_offset,
        end_offset=end_offset,
        snippet=snippet,
        score=1.0,
    )


def _vector_result(
    *,
    document_id: uuid.UUID,
    document_revision_id: uuid.UUID,
    chunk_id: uuid.UUID,
    start_offset: int,
    end_offset: int,
    snippet: str,
) -> VectorSearchResult:
    return VectorSearchResult(
        citation_id=f"chunk:{chunk_id}",
        document_id=document_id,
        document_revision_id=document_revision_id,
        chunk_id=chunk_id,
        heading_path=("Synthetic Heading",),
        start_offset=start_offset,
        end_offset=end_offset,
        snippet=snippet,
        score=1.0,
    )


def test_rrf_fusion_boosts_exact_names_and_eliminates_overlapping_spans() -> None:
    revision_id = uuid.uuid4()
    exact_match = _lexical_result(
        document_revision_id=revision_id,
        start_offset=0,
        end_offset=100,
        snippet="The party recovered the Moonwell Key.",
    )
    shared_id = uuid.uuid4()
    shared_document_id = uuid.uuid4()
    shared = _lexical_result(
        document_revision_id=uuid.uuid4(),
        start_offset=0,
        end_offset=40,
        snippet="The party found an unrelated object.",
    ).model_copy(
        update={
            "citation_id": f"chunk:{shared_id}",
            "chunk_id": shared_id,
            "document_id": shared_document_id,
        }
    )
    shared_vector = _vector_result(
        document_id=shared_document_id,
        document_revision_id=shared.document_revision_id,
        chunk_id=shared_id,
        start_offset=0,
        end_offset=40,
        snippet=shared.snippet,
    )
    overlapping_vector = _vector_result(
        document_id=uuid.uuid4(),
        document_revision_id=revision_id,
        chunk_id=uuid.uuid4(),
        start_offset=50,
        end_offset=150,
        snippet="A semantically similar passage.",
    )

    fused = _fuse_rankings(
        (exact_match, shared),
        (shared_vector, overlapping_vector),
        query="Moonwell Key",
        rank_constant=60,
        exact_name_boost=0.1,
        limit=10,
    )

    assert [result.chunk_id for result in fused] == [exact_match.chunk_id, shared_id]
    assert fused[0].lexical_rank == 1
    assert fused[0].vector_rank is None
    assert fused[1].lexical_rank == 2
    assert fused[1].vector_rank == 1
    assert fused[0].score > fused[1].score