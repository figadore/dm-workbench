"""Library source-registry repository port and PostgreSQL implementation."""

import uuid
from typing import Protocol

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.sql.elements import ColumnElement

from dm_assistant.modules.library.contracts import SourceScope
from dm_assistant.modules.library.models import (
    Document,
    DocumentChunk,
    DocumentPathHistory,
    DocumentRevision,
    IngestionRun,
)


class LibraryRepository(Protocol):
    """Persistence operations needed by transactional source reconciliation."""

    def lock_scope(self, scope: SourceScope) -> None: ...

    def add_run(self, run: IngestionRun) -> None: ...

    def get_run(
        self, run_id: uuid.UUID, *, for_update: bool
    ) -> IngestionRun | None: ...

    def documents_at_path(
        self, scope: SourceScope, source_path: str
    ) -> tuple[Document, ...]: ...

    def documents_with_current_hash(
        self, scope: SourceScope, content_sha256: str
    ) -> tuple[Document, ...]: ...

    def active_documents(self, scope: SourceScope) -> tuple[Document, ...]: ...

    def current_path(
        self, document_id: uuid.UUID, *, for_update: bool
    ) -> DocumentPathHistory | None: ...

    def revision_by_hash(
        self, document_id: uuid.UUID, content_sha256: str
    ) -> DocumentRevision | None: ...

    def next_revision_number(self, document_id: uuid.UUID) -> int: ...

    def add_document(self, document: Document) -> None: ...

    def add_path(self, path: DocumentPathHistory) -> None: ...

    def add_revision(self, revision: DocumentRevision) -> None: ...

    def add_chunk(self, chunk: DocumentChunk) -> None: ...

    def flush(self) -> None: ...


class SqlAlchemyLibraryRepository:
    """SQLAlchemy implementation; application service owns all transactions."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def lock_scope(self, scope: SourceScope) -> None:
        campaign_key = (
            str(scope.campaign_id) if scope.campaign_id is not None else "global"
        )
        self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:scope_key, 0))"),
            {"scope_key": f"library:{campaign_key}:{scope.corpus.value}"},
        )

    def add_run(self, run: IngestionRun) -> None:
        self._session.add(run)

    def get_run(
        self,
        run_id: uuid.UUID,
        *,
        for_update: bool,
    ) -> IngestionRun | None:
        statement = select(IngestionRun).where(IngestionRun.id == run_id)
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def documents_at_path(
        self,
        scope: SourceScope,
        source_path: str,
    ) -> tuple[Document, ...]:
        statement = select(Document).where(
            _campaign_condition(Document.campaign_id, scope.campaign_id),
            Document.corpus == scope.corpus.value,
            Document.source_path == source_path,
        )
        return tuple(
            self._session.scalars(
                statement.order_by(Document.created_at, Document.id).with_for_update()
            )
        )

    def documents_with_current_hash(
        self,
        scope: SourceScope,
        content_sha256: str,
    ) -> tuple[Document, ...]:
        statement = (
            select(Document)
            .join(
                DocumentPathHistory,
                DocumentPathHistory.document_id == Document.id,
            )
            .where(
                _campaign_condition(Document.campaign_id, scope.campaign_id),
                Document.corpus == scope.corpus.value,
                DocumentPathHistory.valid_to.is_(None),
                DocumentPathHistory.content_hash_at_event == content_sha256,
            )
            .order_by(Document.created_at, Document.id)
            .with_for_update()
        )
        return tuple(self._session.scalars(statement))

    def active_documents(self, scope: SourceScope) -> tuple[Document, ...]:
        statement = (
            select(Document)
            .where(
                _campaign_condition(Document.campaign_id, scope.campaign_id),
                Document.corpus == scope.corpus.value,
                Document.retired_at.is_(None),
            )
            .order_by(Document.created_at, Document.id)
            .with_for_update()
        )
        return tuple(self._session.scalars(statement))

    def current_path(
        self,
        document_id: uuid.UUID,
        *,
        for_update: bool,
    ) -> DocumentPathHistory | None:
        statement = select(DocumentPathHistory).where(
            DocumentPathHistory.document_id == document_id,
            DocumentPathHistory.valid_to.is_(None),
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def revision_by_hash(
        self,
        document_id: uuid.UUID,
        content_sha256: str,
    ) -> DocumentRevision | None:
        return self._session.scalar(
            select(DocumentRevision).where(
                DocumentRevision.document_id == document_id,
                DocumentRevision.content_hash == content_sha256,
            )
        )

    def next_revision_number(self, document_id: uuid.UUID) -> int:
        maximum = self._session.scalar(
            select(func.max(DocumentRevision.revision_number)).where(
                DocumentRevision.document_id == document_id
            )
        )
        return int(maximum or 0) + 1

    def add_document(self, document: Document) -> None:
        self._session.add(document)

    def add_path(self, path: DocumentPathHistory) -> None:
        self._session.add(path)

    def add_revision(self, revision: DocumentRevision) -> None:
        self._session.add(revision)

    def add_chunk(self, chunk: DocumentChunk) -> None:
        self._session.add(chunk)

    def flush(self) -> None:
        self._session.flush()


def _campaign_condition(
    column: InstrumentedAttribute[uuid.UUID | None],
    campaign_id: uuid.UUID | None,
) -> ColumnElement[bool]:
    if campaign_id is None:
        return column.is_(None)
    return column == campaign_id
