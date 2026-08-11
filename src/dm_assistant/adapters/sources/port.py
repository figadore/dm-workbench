"""Read-only source filesystem port for Library ingestion."""

from dataclasses import dataclass
from typing import Protocol

from dm_assistant.modules.library.contracts import (
    SourceLocator,
    SourcePresence,
)


@dataclass(frozen=True, slots=True)
class SourceBytes:
    """Bounded exact bytes read from one validated source locator."""

    source_path: str
    data: bytes


class SourceReader(Protocol):
    """Narrow adapter boundary; domain services never open arbitrary paths."""

    def ensure_root(self, root_label: str) -> None:
        """Fail safely unless the configured root label is available."""
        ...

    def read(self, locator: SourceLocator) -> SourceBytes:
        """Read one bounded regular file without following symlinks."""
        ...

    def probe_registry_path(self, source_path: str) -> SourcePresence:
        """Classify a registered source as present or genuinely missing."""
        ...
