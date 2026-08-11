"""Allowlisted read-path resolution for trusted local Workbench adapters."""

from pathlib import Path

from dm_assistant.errors import InvalidInputError


def resolve_allowlisted_file(
    path: Path,
    roots: tuple[Path, ...],
    *,
    maximum_bytes: int | None = None,
) -> Path:
    """Resolve one bounded regular file beneath an allowlisted source root."""
    if maximum_bytes is not None and maximum_bytes < 0:
        raise ValueError("maximum_bytes cannot be negative")
    try:
        resolved = path.expanduser().resolve(strict=True)
    except OSError:
        raise InvalidInputError("The input file does not exist.") from None
    if not resolved.is_file():
        raise InvalidInputError("The input path must be a regular file.")
    if not any(resolved.is_relative_to(root) for root in roots):
        raise InvalidInputError("The input file is outside configured source roots.")
    if maximum_bytes is not None and resolved.stat().st_size > maximum_bytes:
        raise InvalidInputError("The input file is too large.")
    return resolved
