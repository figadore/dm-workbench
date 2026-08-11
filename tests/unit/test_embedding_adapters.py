"""Tests for the provider-independent embedding adapter contract."""

import hashlib
import math

import pytest
from pydantic import ValidationError

from dm_assistant.adapters.embeddings import (
    DeterministicFakeEmbeddingProvider,
    DistanceMetric,
    EmbeddingBenchmarkResult,
    EmbeddingDocument,
    EmbeddingProfileSpec,
    EmbeddingRuntimeKind,
    benchmark_local_embedding_provider,
)


def _profile(**overrides: object) -> EmbeddingProfileSpec:
    values: dict[str, object] = {
        "runtime_kind": EmbeddingRuntimeKind.LOCAL,
        "provider": "synthetic",
        "model": "synthetic-embedding",
        "model_revision": "synthetic-v1",
        "license": "synthetic-test-only",
        "dimensions": 8,
        "distance_metric": DistanceMetric.COSINE,
        "normalization_version": "l2-v1",
        "preprocessing_version": "plain-text-v1",
        "config_hash": hashlib.sha256(b"synthetic-v1").hexdigest(),
        "enabled": True,
        **overrides,
    }
    return EmbeddingProfileSpec.model_validate(values)


def test_profile_captures_vector_compatibility_metadata() -> None:
    profile = _profile()

    assert profile.runtime_kind is EmbeddingRuntimeKind.LOCAL
    assert profile.distance_metric is DistanceMetric.COSINE
    assert profile.dimensions == 8

    with pytest.raises(ValidationError, match="config_hash"):
        _profile(config_hash="not-a-hash")


def test_fake_provider_is_deterministic_for_batches_and_queries() -> None:
    provider = DeterministicFakeEmbeddingProvider(_profile())
    document = EmbeddingDocument(
        chunk_id="synthetic-chunk",
        content="The synthetic obelisk hums at midnight.",
        content_hash=hashlib.sha256(
            b"The synthetic obelisk hums at midnight."
        ).hexdigest(),
    )

    first_batch = provider.embed_documents((document,))
    second_batch = provider.embed_documents((document,))
    query = provider.embed_query("Where is the synthetic obelisk?")

    assert first_batch == second_batch
    assert first_batch[0].source_id == document.chunk_id
    assert len(first_batch[0].values) == provider.profile.dimensions
    assert math.isclose(sum(value * value for value in query.values), 1.0)
    assert query.source_id == "query"


def test_fake_provider_rejects_empty_queries() -> None:
    provider = DeterministicFakeEmbeddingProvider(_profile())

    with pytest.raises(ValueError, match="cannot be empty"):
        provider.embed_query("")


def test_local_benchmark_records_candidate_profile_and_resources() -> None:
    provider = DeterministicFakeEmbeddingProvider(_profile())
    document = EmbeddingDocument(
        chunk_id="benchmark-chunk",
        content="A synthetic benchmark note.",
        content_hash=hashlib.sha256(b"A synthetic benchmark note.").hexdigest(),
    )

    result = benchmark_local_embedding_provider(
        provider,
        documents=(document,),
        queries=("synthetic benchmark",),
    )

    assert isinstance(result, EmbeddingBenchmarkResult)
    assert result.model_revision == "synthetic-v1"
    assert result.license == "synthetic-test-only"
    assert result.dimensions == 8
    assert result.document_count == 1
    assert result.query_count == 1
    assert result.peak_rss_bytes > 0