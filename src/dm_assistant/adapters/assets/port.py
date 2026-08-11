"""Platform-owned content-addressed asset storage port."""

import re
from dataclasses import dataclass
from typing import BinaryIO, Protocol

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class AssetStoreError(Exception):
    """Base class for safe asset-store failures."""


class AssetCorruptionError(AssetStoreError):
    """Stored bytes do not match their content identity."""


class AssetStorageError(AssetStoreError):
    """The configured volume cannot safely publish an asset."""


@dataclass(frozen=True, slots=True)
class StoredBlob:
    """Generic immutable blob identity; media/roles belong in PostgreSQL."""

    sha256: str
    byte_size: int
    storage_locator: str
    created: bool

    def __post_init__(self) -> None:
        expected_locator = f"sha256/{self.sha256[:2]}/{self.sha256}"
        if _SHA256_PATTERN.fullmatch(self.sha256) is None:
            raise ValueError("invalid SHA-256 identity")
        if self.byte_size < 0:
            raise ValueError("byte_size cannot be negative")
        if self.storage_locator != expected_locator:
            raise ValueError("storage locator does not match SHA-256 identity")


class AssetStore(Protocol):
    """Narrow replaceable port shared by generated assets and attachments."""

    def put(self, source: BinaryIO) -> StoredBlob:
        """Publish stream bytes idempotently and return their verified identity."""
        ...

    def put_bytes(self, data: bytes) -> StoredBlob:
        """Publish in-memory bytes through the same atomic path."""
        ...

    def read_bytes(
        self,
        blob: StoredBlob,
        *,
        maximum_bytes: int | None = None,
    ) -> bytes:
        """Read and verify bytes without exposing an arbitrary filesystem path."""
        ...

    def verify(self, blob: StoredBlob) -> None:
        """Fail if the stored bytes no longer match identity/size."""
        ...
