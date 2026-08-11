"""Provider-independent embedding adapters, separate from chat transport."""

from dm_assistant.adapters.embeddings.benchmark import (
    EmbeddingBenchmarkResult,
    benchmark_local_embedding_provider,
)
from dm_assistant.adapters.embeddings.contracts import (
    DistanceMetric,
    EmbeddingDocument,
    EmbeddingProfileSpec,
    EmbeddingProvider,
    EmbeddingRuntimeKind,
    EmbeddingVector,
    TransientEmbeddingError,
)
from dm_assistant.adapters.embeddings.fake import DeterministicFakeEmbeddingProvider

__all__ = [
    "DeterministicFakeEmbeddingProvider",
    "DistanceMetric",
    "EmbeddingBenchmarkResult",
    "EmbeddingDocument",
    "EmbeddingProfileSpec",
    "EmbeddingProvider",
    "EmbeddingRuntimeKind",
    "EmbeddingVector",
    "TransientEmbeddingError",
    "benchmark_local_embedding_provider",
]