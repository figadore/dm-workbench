"""Atomic SHA-256 local-volume implementation of the AssetStore port."""

import hashlib
import io
import os
import stat
import tempfile
from pathlib import Path
from typing import BinaryIO

from dm_assistant.adapters.assets.port import (
    AssetCorruptionError,
    AssetStorageError,
    StoredBlob,
)

_CHUNK_SIZE = 1024 * 1024


class LocalAssetStore:
    """Store immutable blobs under derived safe paths on one filesystem."""

    def __init__(self, asset_root: Path, scratch_root: Path) -> None:
        if not asset_root.is_absolute() or not scratch_root.is_absolute():
            raise AssetStorageError("asset and scratch roots must be absolute")
        self._asset_root = asset_root.resolve(strict=False)
        self._scratch_root = scratch_root.resolve(strict=False)
        if self._asset_root == self._scratch_root:
            raise AssetStorageError("asset and scratch roots must be distinct")
        self._asset_root.mkdir(parents=True, mode=0o750, exist_ok=True)
        self._scratch_root.mkdir(parents=True, mode=0o750, exist_ok=True)
        if self._asset_root.stat().st_dev != self._scratch_root.stat().st_dev:
            raise AssetStorageError("asset and scratch roots must share a filesystem")

    def put_bytes(self, data: bytes) -> StoredBlob:
        """Publish bytes through the streaming implementation."""
        return self.put(io.BytesIO(data))

    def put(self, source: BinaryIO) -> StoredBlob:
        """Hash/fsync a temporary file, then atomically hard-link if absent."""
        descriptor, temporary_name = tempfile.mkstemp(
            prefix="asset-",
            suffix=".tmp",
            dir=self._scratch_root,
        )
        temporary_path = Path(temporary_name)
        digest = hashlib.sha256()
        byte_size = 0
        try:
            with os.fdopen(descriptor, "wb") as temporary:
                while chunk := source.read(_CHUNK_SIZE):
                    if not isinstance(chunk, bytes):
                        raise AssetStorageError("asset source must return bytes")
                    temporary.write(chunk)
                    digest.update(chunk)
                    byte_size += len(chunk)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.chmod(temporary_path, 0o640)
            sha256 = digest.hexdigest()
            locator = _locator(sha256)
            destination = self._safe_destination(locator)
            destination.parent.mkdir(parents=True, mode=0o750, exist_ok=True)
            _fsync_directory(destination.parent.parent)
            _fsync_directory(destination.parent)
            try:
                os.link(temporary_path, destination, follow_symlinks=False)
                created = True
                _fsync_directory(destination.parent)
            except FileExistsError:
                created = False
                self._verify_path(destination, sha256, byte_size)
            return StoredBlob(
                sha256=sha256,
                byte_size=byte_size,
                storage_locator=locator,
                created=created,
            )
        except OSError as error:
            raise AssetStorageError("asset volume operation failed") from error
        finally:
            temporary_path.unlink(missing_ok=True)
            _fsync_directory(self._scratch_root)

    def read_bytes(
        self,
        blob: StoredBlob,
        *,
        maximum_bytes: int | None = None,
    ) -> bytes:
        """Read only the hash-derived path and verify bytes before returning."""
        if maximum_bytes is not None and maximum_bytes < 0:
            raise ValueError("maximum_bytes cannot be negative")
        if maximum_bytes is not None and blob.byte_size > maximum_bytes:
            raise AssetStorageError("asset exceeds the configured read limit")
        destination = self._safe_destination(blob.storage_locator)
        try:
            data = destination.read_bytes()
        except OSError as error:
            raise AssetStorageError("asset cannot be read") from error
        self._verify_data(data, blob.sha256, blob.byte_size)
        return data

    def verify(self, blob: StoredBlob) -> None:
        """Verify regular-file type, size, and SHA-256 content."""
        self._verify_path(
            self._safe_destination(blob.storage_locator),
            blob.sha256,
            blob.byte_size,
        )

    def _safe_destination(self, locator: str) -> Path:
        parts = Path(locator).parts
        if (
            len(parts) != 3
            or parts[0] != "sha256"
            or parts[1] != parts[2][:2]
            or _locator(parts[2]) != locator
        ):
            raise AssetStorageError("invalid asset storage locator")
        destination = self._asset_root.joinpath(*parts)
        resolved_parent = destination.parent.resolve(strict=False)
        if not resolved_parent.is_relative_to(self._asset_root):
            raise AssetStorageError("asset locator escapes storage root")
        return destination

    def _verify_path(self, path: Path, sha256: str, byte_size: int) -> None:
        try:
            metadata = path.lstat()
            if not stat.S_ISREG(metadata.st_mode):
                raise AssetCorruptionError("stored asset is not a regular file")
            if metadata.st_size != byte_size:
                raise AssetCorruptionError("stored asset size mismatch")
            with path.open("rb") as stored:
                digest = hashlib.file_digest(stored, "sha256").hexdigest()
        except AssetCorruptionError:
            raise
        except OSError as error:
            raise AssetStorageError("stored asset cannot be verified") from error
        if digest != sha256:
            raise AssetCorruptionError("stored asset hash mismatch")

    @staticmethod
    def _verify_data(data: bytes, sha256: str, byte_size: int) -> None:
        if len(data) != byte_size:
            raise AssetCorruptionError("stored asset size mismatch")
        if hashlib.sha256(data).hexdigest() != sha256:
            raise AssetCorruptionError("stored asset hash mismatch")


def _locator(sha256: str) -> str:
    if len(sha256) != 64 or any(
        character not in "0123456789abcdef" for character in sha256
    ):
        raise AssetStorageError("invalid SHA-256 storage identity")
    return f"sha256/{sha256[:2]}/{sha256}"


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    except OSError as error:
        raise AssetStorageError("asset directory cannot be synchronized") from error
    try:
        os.fsync(descriptor)
    except OSError as error:
        raise AssetStorageError("asset directory cannot be synchronized") from error
    finally:
        os.close(descriptor)
