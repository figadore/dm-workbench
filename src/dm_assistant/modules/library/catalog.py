"""Read-only immutable Library document views for CLI and API adapters."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import Engine, select

from dm_assistant.db import build_session_factory
from dm_assistant.errors import ResourceNotFoundError
from dm_assistant.modules.library.contracts import SourceScope
from dm_assistant.modules.library.models import Document, DocumentRevision


@dataclass(frozen=True, slots=True)
class LibraryDocumentSummary:
    id: uuid.UUID
    source_path: str
    retired: bool


@dataclass(frozen=True, slots=True)
class LibraryDocumentDetail:
    id: uuid.UUID
    source_path: str
    revision_id: uuid.UUID
    revision_number: int
    content_hash: str
    content_snapshot: str
    title: str
    document_type: str
    authority_class: str
    ruleset: str | None
    visibility_policy: str


class LibraryDocumentCatalog:
    """Read source documents without exposing persistence models to adapters."""

    def __init__(self, engine: Engine) -> None:
        self._factory = build_session_factory(engine)

    def list_documents(self, scope: SourceScope) -> tuple[LibraryDocumentSummary, ...]:
        with self._factory() as session:
            rows = session.execute(
                select(Document.id, Document.source_path, Document.retired_at)
                .where(
                    Document.campaign_id == scope.campaign_id,
                    Document.corpus == scope.corpus.value,
                )
                .order_by(Document.source_path, Document.id)
            )
            return tuple(
                LibraryDocumentSummary(
                    id=row.id,
                    source_path=row.source_path,
                    retired=row.retired_at is not None,
                )
                for row in rows
            )

    def show_document(
        self,
        scope: SourceScope,
        document_id: uuid.UUID,
        revision_id: uuid.UUID | None = None,
    ) -> LibraryDocumentDetail:
        with self._factory() as session:
            statement = (
                select(Document, DocumentRevision)
                .join(DocumentRevision, DocumentRevision.document_id == Document.id)
                .where(
                    Document.id == document_id,
                    Document.campaign_id == scope.campaign_id,
                    Document.corpus == scope.corpus.value,
                )
                .order_by(DocumentRevision.revision_number.desc())
            )
            if revision_id is not None:
                statement = statement.where(DocumentRevision.id == revision_id)
            row = session.execute(statement).first()
        if row is None:
            raise ResourceNotFoundError("The requested document was not found.")
        document, revision = row
        return LibraryDocumentDetail(
            id=document.id,
            source_path=document.source_path,
            revision_id=revision.id,
            revision_number=revision.revision_number,
            content_hash=revision.content_hash,
            content_snapshot=revision.content_snapshot,
            title=revision.title,
            document_type=revision.document_type,
            authority_class=revision.authority_class,
            ruleset=revision.ruleset,
            visibility_policy=revision.visibility_policy,
        )
