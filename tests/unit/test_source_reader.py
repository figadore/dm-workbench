"""Allowlisted source locator and local reader security tests."""

import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from dm_assistant.adapters.sources import LocalSourceReader
from dm_assistant.errors import InvalidInputError
from dm_assistant.modules.library import (
    DiscoveredSource,
    SourceLocator,
    SourcePresence,
)


def test_source_locator_uses_stable_safe_registry_paths() -> None:
    locator = SourceLocator(
        root_label="campaign-vault",
        relative_path="sessions/arrival.md",
    )

    assert locator.registry_path == "campaign-vault/sessions/arrival.md"
    assert SourceLocator.from_registry_path(locator.registry_path) == locator


@pytest.mark.parametrize(
    "relative_path",
    (
        "/absolute.md",
        "../escape.md",
        "notes/../escape.md",
        "notes\\windows.md",
        "notes//double.md",
        "C:/absolute.md",
    ),
)
def test_source_locator_rejects_absolute_traversal_and_unnormalized_paths(
    relative_path: str,
) -> None:
    with pytest.raises(ValidationError):
        SourceLocator(root_label="campaign-vault", relative_path=relative_path)


@pytest.mark.parametrize("root_label", ("UPPER", "has/slash", "-prefix", "has space"))
def test_source_locator_rejects_unsafe_root_labels(root_label: str) -> None:
    with pytest.raises(ValidationError):
        SourceLocator(root_label=root_label, relative_path="source.md")


def test_discovered_source_verifies_exact_utf8_size_and_hash() -> None:
    locator = SourceLocator(root_label="campaign", relative_path="names.md")
    content = "# Éowyn\nSynthetic text.\n"
    encoded = content.encode()
    source = DiscoveredSource(
        locator=locator,
        source_path=locator.registry_path,
        content_sha256=hashlib.sha256(encoded).hexdigest(),
        byte_size=len(encoded),
        content=content,
    )
    assert source.byte_size > len(content)

    with pytest.raises(ValidationError, match="hash does not match"):
        DiscoveredSource(
            locator=locator,
            source_path=locator.registry_path,
            content_sha256="0" * 64,
            byte_size=len(encoded),
            content=content,
        )


def test_local_source_reader_reads_only_regular_files_without_symlinks(
    tmp_path: Path,
) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    notes = root / "notes"
    notes.mkdir()
    source_path = notes / "arrival.md"
    source_path.write_text("# Arrival\nSynthetic text.\n", encoding="utf-8")
    reader = LocalSourceReader({"campaign": root})
    locator = SourceLocator(root_label="campaign", relative_path="notes/arrival.md")

    source = reader.read(locator)
    assert source.source_path == "campaign/notes/arrival.md"
    assert source.data == source_path.read_bytes()
    assert reader.probe_registry_path(source.source_path) is SourcePresence.PRESENT

    source_path.unlink()
    assert reader.probe_registry_path(source.source_path) is SourcePresence.MISSING
    with pytest.raises(InvalidInputError, match="does not exist"):
        reader.read(locator)


def test_local_source_reader_rejects_symlink_components_and_non_files(
    tmp_path: Path,
) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / "secret.md"
    target.write_text("synthetic secret", encoding="utf-8")
    (root / "file-link.md").symlink_to(target)
    (root / "directory-link").symlink_to(outside, target_is_directory=True)
    (root / "directory").mkdir()
    reader = LocalSourceReader({"campaign": root})

    for relative_path in (
        "file-link.md",
        "directory-link/secret.md",
        "directory",
    ):
        locator = SourceLocator(
            root_label="campaign",
            relative_path=relative_path,
        )
        with pytest.raises(InvalidInputError):
            reader.read(locator)


def test_local_source_reader_enforces_root_and_size_configuration(
    tmp_path: Path,
) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "large.md").write_bytes(b"12345")
    reader = LocalSourceReader({"campaign": root}, maximum_bytes=4)

    with pytest.raises(InvalidInputError, match="not configured"):
        reader.read(SourceLocator(root_label="other", relative_path="source.md"))
    with pytest.raises(InvalidInputError, match="too large"):
        reader.read(SourceLocator(root_label="campaign", relative_path="large.md"))

    symlink_root = tmp_path / "root-link"
    symlink_root.symlink_to(root, target_is_directory=True)
    with pytest.raises(ValueError, match="real directories"):
        LocalSourceReader({"campaign": symlink_root})
