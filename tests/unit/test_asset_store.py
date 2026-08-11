"""Atomic local content-addressed AssetStore tests."""

import hashlib
import io
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from dm_assistant.adapters.assets import (
    AssetCorruptionError,
    AssetStorageError,
    LocalAssetStore,
    StoredBlob,
)


def make_store(tmp_path: Path) -> LocalAssetStore:
    return LocalAssetStore(tmp_path / "assets", tmp_path / "scratch")


def test_put_read_and_verify_derive_content_identity(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    data = b"synthetic generated map bytes"
    expected_hash = hashlib.sha256(data).hexdigest()

    blob = store.put(io.BytesIO(data))

    assert blob == StoredBlob(
        sha256=expected_hash,
        byte_size=len(data),
        storage_locator=f"sha256/{expected_hash[:2]}/{expected_hash}",
        created=True,
    )
    assert store.read_bytes(blob) == data
    store.verify(blob)
    destination = tmp_path / "assets" / blob.storage_locator
    assert destination.is_file()
    assert destination.stat().st_mode & 0o777 == 0o640
    assert list((tmp_path / "scratch").iterdir()) == []


def test_repeated_and_concurrent_writes_deduplicate_without_overwrite(
    tmp_path: Path,
) -> None:
    store = make_store(tmp_path)
    data = b"same immutable content" * 1000

    with ThreadPoolExecutor(max_workers=8) as pool:
        blobs = list(pool.map(store.put_bytes, (data,) * 16))

    assert len({blob.sha256 for blob in blobs}) == 1
    assert sum(blob.created for blob in blobs) == 1
    assert all(store.read_bytes(blob) == data for blob in blobs)
    assert len(list((tmp_path / "assets" / "sha256").glob("*/*"))) == 1
    assert list((tmp_path / "scratch").iterdir()) == []


def test_corruption_fails_closed_for_existing_and_read_assets(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    blob = store.put_bytes(b"original")
    destination = tmp_path / "assets" / blob.storage_locator
    destination.write_bytes(b"longer-tampered")

    with pytest.raises(AssetCorruptionError, match="size mismatch"):
        store.verify(blob)
    with pytest.raises(AssetCorruptionError):
        store.read_bytes(blob)
    with pytest.raises(AssetCorruptionError):
        store.put_bytes(b"original")


def test_same_size_hash_corruption_is_detected(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    blob = store.put_bytes(b"original")
    destination = tmp_path / "assets" / blob.storage_locator
    destination.write_bytes(b"tampered")

    with pytest.raises(AssetCorruptionError, match="hash mismatch"):
        store.verify(blob)


def test_read_limit_and_locator_validation_fail_before_exposure(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    blob = store.put_bytes(b"12345")

    with pytest.raises(AssetStorageError, match="read limit"):
        store.read_bytes(blob, maximum_bytes=4)
    with pytest.raises(ValueError, match="cannot be negative"):
        store.read_bytes(blob, maximum_bytes=-1)
    with pytest.raises(ValueError, match="locator"):
        StoredBlob(
            sha256=blob.sha256,
            byte_size=blob.byte_size,
            storage_locator="../../outside",
            created=False,
        )


def test_symlink_substitution_is_rejected(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    blob = store.put_bytes(b"safe")
    destination = tmp_path / "assets" / blob.storage_locator
    outside = tmp_path / "outside"
    outside.write_bytes(b"safe")
    destination.unlink()
    destination.symlink_to(outside)

    with pytest.raises(AssetCorruptionError, match="regular file"):
        store.verify(blob)


def test_failed_stream_removes_temporary_bytes_without_publication(
    tmp_path: Path,
) -> None:
    store = make_store(tmp_path)

    class FailingStream(io.BytesIO):
        calls = 0

        def read(self, size: int = -1) -> bytes:
            self.calls += 1
            if self.calls == 1:
                return b"partial private bytes"
            raise RuntimeError("synthetic stream failure")

    with pytest.raises(RuntimeError, match="synthetic stream failure"):
        store.put(FailingStream())

    assert list((tmp_path / "scratch").iterdir()) == []
    assert not (tmp_path / "assets" / "sha256").exists()


def test_roots_must_be_absolute_distinct_and_same_filesystem(tmp_path: Path) -> None:
    with pytest.raises(AssetStorageError, match="absolute"):
        LocalAssetStore(Path("relative-assets"), tmp_path / "scratch")
    with pytest.raises(AssetStorageError, match="distinct"):
        LocalAssetStore(tmp_path, tmp_path)
