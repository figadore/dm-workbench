"""Allowlisted file resolution and symlink-escape tests."""

from pathlib import Path

import pytest

from dm_assistant.errors import InvalidInputError
from dm_assistant.paths import resolve_allowlisted_file


def test_resolves_regular_file_beneath_allowlisted_root(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    root.mkdir()
    document = root / "layout.json"
    document.write_text("{}", encoding="utf-8")

    assert resolve_allowlisted_file(document, (root.resolve(),)) == document.resolve()


def test_rejects_outside_missing_directory_and_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    root.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    link = root / "linked.json"
    link.symlink_to(outside)

    with pytest.raises(InvalidInputError, match="outside"):
        resolve_allowlisted_file(outside, (root.resolve(),))
    with pytest.raises(InvalidInputError, match="outside"):
        resolve_allowlisted_file(link, (root.resolve(),))
    with pytest.raises(InvalidInputError, match="does not exist"):
        resolve_allowlisted_file(root / "missing.json", (root.resolve(),))
    with pytest.raises(InvalidInputError, match="regular file"):
        resolve_allowlisted_file(root, (root.resolve(),))
    with pytest.raises(InvalidInputError, match="too large"):
        resolve_allowlisted_file(outside, (tmp_path.resolve(),), maximum_bytes=1)
    with pytest.raises(ValueError, match="cannot be negative"):
        resolve_allowlisted_file(outside, (tmp_path.resolve(),), maximum_bytes=-1)
