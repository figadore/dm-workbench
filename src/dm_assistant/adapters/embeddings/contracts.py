"""Embedding contracts that never share the chat-model gateway or its credentials."""

from collections.abc import Sequence
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TransientEmbeddingError(RuntimeError):
    """A provider failure that may be retried within a run's configured bound."""


class EmbeddingRuntimeKind(StrEnum):
    """Execution boundaries for embedding providers."""

    LOCAL = "local"
    HOSTED = "hosted"


class DistanceMetric(StrEnum):
    """Distance metrics supported by a compatible vector partition."""

    COSINE = "cosine"
    EUCLIDEAN = "euclidean"
    INNER_PRODUCT = "inner_product"


class EmbeddingProfileSpec(BaseModel):
    """Versioned, credential-free embedding profile metadata."""

    model_config = ConfigDict(frozen=True)

    runtime_kind: EmbeddingRuntimeKind
    provider: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=200)
    model_revision: str = Field(min_length=1, max_length=200)
    license: str = Field(min_length=1, max_length=200)
    dimensions: int = Field(gt=0, le=16_384)
    distance_metric: DistanceMetric
    normalization_version: str = Field(min_length=1, max_length=100)
    preprocessing_version: str = Field(min_length=1, max_length=100)
    config_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    enabled: bool = False

    @field_validator(
        "provider",
        "model",
        "model_revision",
        "license",
        "normalization_version",
        "preprocessing_version",
    )
    @classmethod
    def reject_blank_metadata(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("embedding profile metadata cannot be blank")
        return value


class EmbeddingDocument(BaseModel):
    """One exact immutable chunk payload sent to an embedding provider."""

    model_config = ConfigDict(frozen=True)

    chunk_id: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class EmbeddingVector(BaseModel):
    """A profile-compatible vector associated with one source payload."""

    model_config = ConfigDict(frozen=True)

    source_id: str = Field(min_length=1, max_length=100)
    values: tuple[float, ...] = Field(min_length=1)


class EmbeddingProvider(Protocol):
    """Narrow synchronous contract for separate document and query embedding calls."""

    profile: EmbeddingProfileSpec

    def embed_documents(
        self, documents: Sequence[EmbeddingDocument]
    ) -> Sequence[EmbeddingVector]:
        """Embed an ordered document batch without persisting it."""

    def embed_query(self, query: str) -> EmbeddingVector:
        """Embed one retrieval query without accessing the model gateway."""