"""Candidate corpus snapshot construction and atomic activation."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session

from dm_assistant.db import build_session_factory, transactional_session
from dm_assistant.errors import ConflictError, InvalidInputError
from dm_assistant.modules.library.contracts import (
    SnapshotState,
    SourceScope,
)
from dm_assistant.modules.library.markdown import chunker_version, parser_version
from dm_assistant.modules.library.models import (
    CorpusSnapshot,
    CorpusSnapshotDocument,
    Document,
    DocumentRevision,
    IngestionRun,
)

IdFactory = Callable[[], uuid.UUID]
Clock = Callable[[], datetime]


class CorpusSnapshotService:
    """Build and activate immutable, revision-pinned corpus snapshots."""

    def __init__(
        self,
        engine: Engine,
        *,
        id_factory: IdFactory = uuid.uuid4,
        clock: Clock | None = None,
    ) -> None:
        self._session_factory = build_session_factory(engine)
        self._id_factory = id_factory
        self._clock = clock or (lambda: datetime.now(UTC))

    def build_candidate(self, scope: SourceScope) -> uuid.UUID:
        """Pin every current revision into a candidate snapshot."""
        with transactional_session(self._session_factory) as session:
            self._lock_scope(session, scope)
            run = IngestionRun(
                id=self._id_factory(),
                campaign_id=scope.campaign_id,
                corpus=scope.corpus.value,
                source_root_label="snapshot",
                configuration={"action": "build_snapshot"},
                parser_version=parser_version(),
                chunker_version=chunker_version(),
                status="running",
                summary={},
                started_at=self._clock(),
                finished_at=None,
            )
            session.add(run)
            session.flush()

            heads = self._current_heads(session, scope)
            run.status = "succeeded"
            run.summary = {
                "outcome": "candidate_built",
                "document_count": len(heads),
            }
            run.finished_at = self._clock()
            session.flush()

            snapshot = CorpusSnapshot(
                id=self._id_factory(),
                campaign_id=scope.campaign_id,
                corpus=scope.corpus.value,
                parent_snapshot_id=self._active_snapshot_id(session, scope),
                ingestion_run_id=run.id,
                state=SnapshotState.CANDIDATE.value,
                created_at=self._clock(),
                activated_at=None,
            )
            session.add(snapshot)
            session.flush()

            for ordinal, (document, revision) in enumerate(heads):
                session.add(
                    CorpusSnapshotDocument(
                        corpus_snapshot_id=snapshot.id,
                        document_id=document.id,
                        document_revision_id=revision.id,
                        campaign_id=scope.campaign_id,
                        corpus=scope.corpus.value,
                        ordinal=ordinal,
                        added_at=self._clock(),
                    )
                )

            run.summary["snapshot_id"] = str(snapshot.id)
            return snapshot.id

    def activate(self, snapshot_id: uuid.UUID, scope: SourceScope) -> uuid.UUID:
        """Atomically replace the active snapshot for a scope."""
        with transactional_session(self._session_factory) as session:
            self._lock_scope(session, scope)
            snapshot = session.scalar(
                select(CorpusSnapshot)
                .where(
                    CorpusSnapshot.id == snapshot_id,
                    CorpusSnapshot.campaign_id == scope.campaign_id,
                    CorpusSnapshot.corpus == scope.corpus.value,
                )
                .with_for_update()
            )
            if snapshot is None:
                raise InvalidInputError("snapshot does not exist in the requested scope")
            if snapshot.state != SnapshotState.CANDIDATE.value:
                raise ConflictError("only candidate snapshots can be activated")

            active = session.scalar(
                select(CorpusSnapshot)
                .where(
                    CorpusSnapshot.campaign_id == scope.campaign_id,
                    CorpusSnapshot.corpus == scope.corpus.value,
                    CorpusSnapshot.state == SnapshotState.ACTIVE.value,
                )
                .with_for_update()
            )
            activated_at = self._clock()
            if active is not None:
                active.state = SnapshotState.SUPERSEDED.value
                session.flush()
            snapshot.state = SnapshotState.ACTIVE.value
            snapshot.activated_at = activated_at
            session.flush()
            return snapshot.id

    @staticmethod
    def _lock_scope(session: Session, scope: SourceScope) -> None:
        campaign_key = str(scope.campaign_id) if scope.campaign_id else "global"
        session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:scope_key, 0))"),
            {"scope_key": f"library:{campaign_key}:{scope.corpus.value}:snapshot"},
        )

    @staticmethod
    def _active_snapshot_id(session: Session, scope: SourceScope) -> uuid.UUID | None:
        snapshot = session.scalar(
            select(CorpusSnapshot.id).where(
                CorpusSnapshot.campaign_id == scope.campaign_id,
                CorpusSnapshot.corpus == scope.corpus.value,
                CorpusSnapshot.state == SnapshotState.ACTIVE.value,
            )
        )
        return snapshot

    @staticmethod
    def _current_heads(
        session: Session, scope: SourceScope
    ) -> tuple[tuple[Document, DocumentRevision], ...]:
        latest_revision = (
            select(
                DocumentRevision.document_id,
                func.max(DocumentRevision.revision_number).label("revision_number"),
            )
            .group_by(DocumentRevision.document_id)
            .subquery()
        )
        statement = (
            select(Document, DocumentRevision)
            .join(
                DocumentRevision,
                DocumentRevision.document_id == Document.id,
            )
            .join(
                latest_revision,
                (latest_revision.c.document_id == DocumentRevision.document_id)
                & (latest_revision.c.revision_number == DocumentRevision.revision_number),
            )
            .where(
                Document.campaign_id == scope.campaign_id,
                Document.corpus == scope.corpus.value,
                Document.retired_at.is_(None),
            )
            .order_by(Document.id)
        )
        return tuple(
            (row[0], row[1]) for row in session.execute(statement)
        )
