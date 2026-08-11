"""Application workflow composition for Library source publication."""

from __future__ import annotations

from dm_assistant.modules.library.contracts import (
    IngestionResult,
    IngestionStatus,
    IngestSource,
)
from dm_assistant.modules.library.service import LibraryIngestionService
from dm_assistant.modules.library.snapshots import CorpusSnapshotService


class LibrarySourceWorkflow:
    """Publish successful source ingestion through an active immutable snapshot."""

    def __init__(
        self,
        ingestion: LibraryIngestionService,
        snapshots: CorpusSnapshotService,
    ) -> None:
        self._ingestion = ingestion
        self._snapshots = snapshots

    def ingest(self, command: IngestSource) -> IngestionResult:
        """Ingest one source, then atomically publish the complete current heads."""
        result = self._ingestion.ingest(command)
        if result.status is IngestionStatus.SUCCEEDED:
            candidate_id = self._snapshots.build_candidate(command.scope)
            self._snapshots.activate(candidate_id, command.scope)
        return result
