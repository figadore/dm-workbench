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
    HybridRetrievalMode,
    HybridSearchQuery,
    HybridSearchResponse,
    HybridSearchResult,
    LexicalSearchQuery,
    LexicalSearchResult,
    MissingReconciliationResult,
    PathEventKind,
    ReconcileMissingSources,
    ReconciliationAmbiguity,
    ReconciliationAmbiguityReason,
    RevisionClassification,
    Ruleset,
    NeighboringChunk,
    SnapshotState,
    SourceLocator,
    SourcePresence,
    SourceScope,
    SourceVisibility,
    VectorRetrievalMode,
    VectorSearchQuery,
    VectorSearchResponse,
    VectorSearchResult,
    VisibilityLabel,
)

if TYPE_CHECKING:
    from dm_assistant.modules.library.catalog import LibraryDocumentCatalog
    from dm_assistant.modules.library.embedding_runs import EmbeddingRunService
    from dm_assistant.modules.library.evals import evaluate_retrieval_cases
    from dm_assistant.modules.library.retrieval_runs import LibraryRetrievalAuditService
    from dm_assistant.modules.library.retrieval import (
        LibraryHybridSearchService,
        LibraryLexicalSearchService,
        LibraryVectorSearchService,
    )
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
    "EmbeddingRunService",
    "evaluate_retrieval_cases",
    "IngestionOutcome",
    "IngestionResult",
    "IngestionStatus",
    "IngestSource",
    "HybridRetrievalMode",
    "HybridSearchQuery",
    "HybridSearchResponse",
    "HybridSearchResult",
    "LexicalSearchQuery",
    "LexicalSearchResult",
    "LibraryLexicalSearchService",
    "LibraryRetrievalAuditService",
    "LibraryHybridSearchService",
    "LibraryVectorSearchService",
    "LibrarySourceWorkflow",
    "LibraryIngestionService",
    "MissingReconciliationResult",
    "NeighboringChunk",
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
    "VectorRetrievalMode",
    "VectorSearchQuery",
    "VectorSearchResponse",
    "VectorSearchResult",
]


def __getattr__(name: str) -> Any:
    if name == "LibraryDocumentCatalog":
        from dm_assistant.modules.library.catalog import LibraryDocumentCatalog

        return LibraryDocumentCatalog
    if name == "LibraryIngestionService":
        from dm_assistant.modules.library.service import LibraryIngestionService

        return LibraryIngestionService
    if name == "EmbeddingRunService":
        from dm_assistant.modules.library.embedding_runs import EmbeddingRunService

        return EmbeddingRunService
    if name == "evaluate_retrieval_cases":
        from dm_assistant.modules.library.evals import evaluate_retrieval_cases

        return evaluate_retrieval_cases
    if name == "CorpusSnapshotService":
        from dm_assistant.modules.library.snapshots import CorpusSnapshotService

        return CorpusSnapshotService
    if name == "LibraryLexicalSearchService":
        from dm_assistant.modules.library.retrieval import LibraryLexicalSearchService

        return LibraryLexicalSearchService
    if name == "LibraryRetrievalAuditService":
        from dm_assistant.modules.library.retrieval_runs import (
            LibraryRetrievalAuditService,
        )

        return LibraryRetrievalAuditService
    if name == "LibraryHybridSearchService":
        from dm_assistant.modules.library.retrieval import LibraryHybridSearchService

        return LibraryHybridSearchService
    if name == "LibraryVectorSearchService":
        from dm_assistant.modules.library.retrieval import LibraryVectorSearchService

        return LibraryVectorSearchService
    if name == "LibrarySourceWorkflow":
        from dm_assistant.modules.library.workflows import LibrarySourceWorkflow

        return LibrarySourceWorkflow
    raise AttributeError(name)
