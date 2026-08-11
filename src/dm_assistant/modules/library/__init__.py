"""Immutable Library sources, registry reconciliation, and corpus contracts."""

from typing import TYPE_CHECKING, Any

from dm_assistant.modules.library.contracts import (
    AuthorityClass,
    CorpusKind,
    DiscoveredSource,
    DocumentType,
    IngestionOutcome,
    IngestionResult,
    IngestionStatus,
    IngestSource,
    MissingReconciliationResult,
    PathEventKind,
    ReconcileMissingSources,
    ReconciliationAmbiguity,
    ReconciliationAmbiguityReason,
    RevisionClassification,
    Ruleset,
    SnapshotState,
    SourceLocator,
    SourcePresence,
    SourceScope,
    SourceVisibility,
    VisibilityLabel,
)

if TYPE_CHECKING:
    from dm_assistant.modules.library.service import LibraryIngestionService

__all__ = [
    "AuthorityClass",
    "CorpusKind",
    "DiscoveredSource",
    "DocumentType",
    "IngestionOutcome",
    "IngestionResult",
    "IngestionStatus",
    "IngestSource",
    "LibraryIngestionService",
    "MissingReconciliationResult",
    "PathEventKind",
    "ReconcileMissingSources",
    "ReconciliationAmbiguity",
    "ReconciliationAmbiguityReason",
    "RevisionClassification",
    "Ruleset",
    "SnapshotState",
    "SourceLocator",
    "SourcePresence",
    "SourceScope",
    "SourceVisibility",
    "VisibilityLabel",
]


def __getattr__(name: str) -> Any:
    if name == "LibraryIngestionService":
        from dm_assistant.modules.library.service import LibraryIngestionService

        return LibraryIngestionService
    raise AttributeError(name)
