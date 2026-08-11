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
    LexicalSearchQuery,
    LexicalSearchResult,
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
    from dm_assistant.modules.library.catalog import LibraryDocumentCatalog
    from dm_assistant.modules.library.retrieval import LibraryLexicalSearchService
    from dm_assistant.modules.library.service import LibraryIngestionService
    from dm_assistant.modules.library.snapshots import CorpusSnapshotService
    from dm_assistant.modules.library.workflows import LibrarySourceWorkflow

__all__ = [
    "AuthorityClass",
    "CorpusKind",
    "LibraryDocumentCatalog",
    "CorpusSnapshotService",
    "DiscoveredSource",
    "DocumentType",
    "IngestionOutcome",
    "IngestionResult",
    "IngestionStatus",
    "IngestSource",
    "LexicalSearchQuery",
    "LexicalSearchResult",
    "LibraryLexicalSearchService",
    "LibrarySourceWorkflow",
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
    if name == "LibraryDocumentCatalog":
        from dm_assistant.modules.library.catalog import LibraryDocumentCatalog

        return LibraryDocumentCatalog
    if name == "LibraryIngestionService":
        from dm_assistant.modules.library.service import LibraryIngestionService

        return LibraryIngestionService
    if name == "CorpusSnapshotService":
        from dm_assistant.modules.library.snapshots import CorpusSnapshotService

        return CorpusSnapshotService
    if name == "LibraryLexicalSearchService":
        from dm_assistant.modules.library.retrieval import LibraryLexicalSearchService

        return LibraryLexicalSearchService
    if name == "LibrarySourceWorkflow":
        from dm_assistant.modules.library.workflows import LibrarySourceWorkflow

        return LibrarySourceWorkflow
    raise AttributeError(name)
