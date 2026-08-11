"""Small local-runtime benchmark probe for candidate CPU/ONNX embedding adapters."""

import resource
from collections.abc import Sequence
from time import perf_counter_ns

from pydantic import BaseModel, ConfigDict, Field

from dm_assistant.adapters.embeddings.contracts import (
    EmbeddingDocument,
    EmbeddingProvider,
    EmbeddingRuntimeKind,
)


class EmbeddingBenchmarkResult(BaseModel):
    """Reproducible observations needed before selecting an embedding profile."""

    model_config = ConfigDict(frozen=True)

    provider: str
    model: str
    model_revision: str
    license: str
    dimensions: int
    document_count: int
    query_count: int
    batch_latency_milliseconds: float = Field(ge=0)
    query_latency_milliseconds: float = Field(ge=0)
    peak_rss_bytes: int = Field(ge=0)


def benchmark_local_embedding_provider(
    provider: EmbeddingProvider,
    documents: Sequence[EmbeddingDocument],
    queries: Sequence[str],
) -> EmbeddingBenchmarkResult:
    """Measure one candidate local embedding adapter without persisting vectors."""

    if provider.profile.runtime_kind is not EmbeddingRuntimeKind.LOCAL:
        raise ValueError("benchmark probe accepts only local embedding providers")
    batch_start = perf_counter_ns()
    document_vectors = provider.embed_documents(documents)
    batch_elapsed = perf_counter_ns() - batch_start
    query_start = perf_counter_ns()
    query_vectors = tuple(provider.embed_query(query) for query in queries)
    query_elapsed = perf_counter_ns() - query_start
    expected_dimensions = provider.profile.dimensions
    if any(
        len(vector.values) != expected_dimensions
        for vector in (*document_vectors, *query_vectors)
    ):
        raise ValueError("embedding provider returned a vector with wrong dimensions")
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return EmbeddingBenchmarkResult(
        provider=provider.profile.provider,
        model=provider.profile.model,
        model_revision=provider.profile.model_revision,
        license=provider.profile.license,
        dimensions=expected_dimensions,
        document_count=len(documents),
        query_count=len(queries),
        batch_latency_milliseconds=batch_elapsed / 1_000_000,
        query_latency_milliseconds=query_elapsed / 1_000_000,
        peak_rss_bytes=usage.ru_maxrss * 1024,
    )