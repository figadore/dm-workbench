"""Network-free deterministic embedding provider for tests and local contracts."""

import hashlib
import math
from collections.abc import Sequence

from dm_assistant.adapters.embeddings.contracts import (
    EmbeddingDocument,
    EmbeddingProfileSpec,
    EmbeddingVector,
)


class DeterministicFakeEmbeddingProvider:
    """Produces reproducible unit vectors from content and profile metadata."""

    def __init__(self, profile: EmbeddingProfileSpec) -> None:
        self.profile = profile

    def embed_documents(
        self, documents: Sequence[EmbeddingDocument]
    ) -> Sequence[EmbeddingVector]:
        return tuple(
            EmbeddingVector(
                source_id=document.chunk_id,
                values=self._embed(document.content),
            )
            for document in documents
        )

    def embed_query(self, query: str) -> EmbeddingVector:
        if not query:
            raise ValueError("embedding query cannot be empty")
        return EmbeddingVector(source_id="query", values=self._embed(query))

    def _embed(self, content: str) -> tuple[float, ...]:
        digest_input = (
            f"{self.profile.config_hash}:{self.profile.model_revision}:{content}"
        ).encode()
        samples = bytearray()
        counter = 0
        while len(samples) < self.profile.dimensions:
            samples.extend(
                hashlib.sha256(digest_input + counter.to_bytes(4, "big")).digest()
            )
            counter += 1
        raw_values = tuple(
            (sample - 127.5) / 127.5 for sample in samples[: self.profile.dimensions]
        )
        length = math.sqrt(sum(value * value for value in raw_values))
        return tuple(value / length for value in raw_values)