"""Bounded, synchronous, and restart-safe embedding derivation execution."""

import resource
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter_ns

from sqlalchemy import Engine, func, select, update
from sqlalchemy.orm import Session

from dm_assistant.adapters.embeddings import (
    EmbeddingDocument,
    EmbeddingProvider,
    TransientEmbeddingError,
)
from dm_assistant.db import build_session_factory, transactional_session
from dm_assistant.errors import ConflictError, ResourceNotFoundError
from dm_assistant.modules.library.models import (
    CorpusSnapshot,
    CorpusSnapshotDocument,
    DocumentChunk,
    DocumentChunkEmbedding,
    EmbeddingProfile,
    EmbeddingRun,
    EmbeddingRunItem,
)

_PENDING_ITEM_STATUSES = ("pending", "retryable_failed")
_SUCCESSFUL_ITEM_STATUSES = ("succeeded", "skipped")


@dataclass(frozen=True)
class EmbeddingRunSnapshot:
    """Read-only progress summary for one durable embedding run."""

    id: uuid.UUID
    corpus_snapshot_id: uuid.UUID
    embedding_profile_id: uuid.UUID
    status: str
    item_counts: dict[str, int]


@dataclass(frozen=True)
class _ClaimedItem:
    item_id: uuid.UUID
    chunk_id: uuid.UUID
    content_hash: str
    content: str


class EmbeddingRunService:
    """Executes profile-pinned chunk derivations without changing source identity."""

    def __init__(
        self,
        engine: Engine,
        *,
        id_factory: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        self._session_factory = build_session_factory(engine)
        self._id_factory = id_factory

    def create_run(
        self,
        *,
        corpus_snapshot_id: uuid.UUID,
        embedding_profile_id: uuid.UUID,
        batch_size: int,
        max_attempts: int,
    ) -> EmbeddingRunSnapshot:
        with transactional_session(self._session_factory) as session:
            snapshot = session.get(CorpusSnapshot, corpus_snapshot_id)
            if snapshot is None:
                raise ResourceNotFoundError("The corpus snapshot was not found.")
            profile = session.get(EmbeddingProfile, embedding_profile_id)
            if profile is None:
                raise ResourceNotFoundError("The embedding profile was not found.")
            run = EmbeddingRun(
                id=self._id_factory(),
                corpus_snapshot_id=snapshot.id,
                embedding_profile_id=profile.id,
                runtime_kind=profile.runtime_kind,
                provider=profile.provider,
                model_revision=profile.model_revision,
                dimensions=profile.dimensions,
                batch_size=batch_size,
                max_attempts=max_attempts,
                status="running",
            )
            session.add(run)
            session.flush()
            chunks = tuple(
                session.scalars(
                    select(DocumentChunk)
                    .join(
                        CorpusSnapshotDocument,
                        CorpusSnapshotDocument.document_revision_id
                        == DocumentChunk.document_revision_id,
                    )
                    .where(
                        CorpusSnapshotDocument.corpus_snapshot_id == snapshot.id
                    )
                    .order_by(DocumentChunk.id)
                )
            )
            for chunk in chunks:
                existing_embedding = session.scalar(
                    select(DocumentChunkEmbedding).where(
                        DocumentChunkEmbedding.document_chunk_id == chunk.id,
                        DocumentChunkEmbedding.embedding_profile_id == profile.id,
                        DocumentChunkEmbedding.chunk_content_hash == chunk.content_hash,
                    )
                )
                session.add(
                    EmbeddingRunItem(
                        id=self._id_factory(),
                        embedding_run_id=run.id,
                        document_chunk_id=chunk.id,
                        chunk_content_hash=chunk.content_hash,
                        document_chunk_embedding_id=(
                            existing_embedding.id if existing_embedding is not None else None
                        ),
                        status="skipped" if existing_embedding is not None else "pending",
                        attempt_count=0,
                    )
                )
            session.flush()
            return _run_snapshot(session, run)

    def execute(
        self,
        run_id: uuid.UUID,
        provider: EmbeddingProvider,
    ) -> EmbeddingRunSnapshot:
        self._resume(run_id, provider)
        while claimed_items := self._claim_batch(run_id):
            documents = tuple(
                EmbeddingDocument(
                    chunk_id=str(item.chunk_id),
                    content=item.content,
                    content_hash=item.content_hash,
                )
                for item in claimed_items
            )
            started_at = perf_counter_ns()
            try:
                vectors = provider.embed_documents(documents)
            except TransientEmbeddingError as error:
                self._record_failure(
                    run_id,
                    tuple(item.item_id for item in claimed_items),
                    error_code=type(error).__name__,
                    retryable=True,
                )
                continue
            except Exception as error:
                self._record_failure(
                    run_id,
                    tuple(item.item_id for item in claimed_items),
                    error_code=type(error).__name__,
                    retryable=False,
                )
                continue
            self._record_success(
                run_id,
                claimed_items,
                vectors,
                elapsed_nanoseconds=perf_counter_ns() - started_at,
            )
        return self._finish(run_id)

    def cancel(self, run_id: uuid.UUID) -> EmbeddingRunSnapshot:
        with transactional_session(self._session_factory) as session:
            run = _locked_run(session, run_id)
            if run.status != "running":
                raise ConflictError("Only a running embedding run can be cancelled.")
            run.status = "cancelled"
            run.finished_at = datetime.now(UTC)
            return _run_snapshot(session, run)

    def _resume(self, run_id: uuid.UUID, provider: EmbeddingProvider) -> None:
        with transactional_session(self._session_factory) as session:
            run = _locked_run(session, run_id)
            if (
                run.runtime_kind != provider.profile.runtime_kind.value
                or run.provider != provider.profile.provider
                or run.model_revision != provider.profile.model_revision
                or run.dimensions != provider.profile.dimensions
            ):
                raise ConflictError("The embedding provider does not match the run profile.")
            if run.status == "succeeded":
                return
            if run.status in ("failed", "cancelled"):
                run.status = "running"
                run.finished_at = None
            session.execute(
                update(EmbeddingRunItem)
                .where(
                    EmbeddingRunItem.embedding_run_id == run.id,
                    EmbeddingRunItem.status.in_(("processing", "cancelled")),
                    EmbeddingRunItem.attempt_count >= run.max_attempts,
                )
                .values(
                    status="failed",
                    error_code="interrupted_at_retry_limit",
                    finished_at=datetime.now(UTC),
                )
            )
            session.execute(
                update(EmbeddingRunItem)
                .where(
                    EmbeddingRunItem.embedding_run_id == run.id,
                    EmbeddingRunItem.status.in_(("processing", "cancelled")),
                    EmbeddingRunItem.attempt_count < run.max_attempts,
                )
                .values(status="pending", started_at=None, finished_at=None)
            )
            session.execute(
                update(EmbeddingRunItem)
                .where(
                    EmbeddingRunItem.embedding_run_id == run.id,
                    EmbeddingRunItem.status == "retryable_failed",
                    EmbeddingRunItem.attempt_count < run.max_attempts,
                )
                .values(status="pending", started_at=None, finished_at=None)
            )

    def _claim_batch(self, run_id: uuid.UUID) -> tuple[_ClaimedItem, ...]:
        with transactional_session(self._session_factory) as session:
            run = _locked_run(session, run_id)
            if run.status != "running":
                return ()
            items = tuple(
                session.scalars(
                    select(EmbeddingRunItem)
                    .where(
                        EmbeddingRunItem.embedding_run_id == run.id,
                        EmbeddingRunItem.status.in_(_PENDING_ITEM_STATUSES),
                        EmbeddingRunItem.attempt_count < run.max_attempts,
                    )
                    .order_by(EmbeddingRunItem.id)
                    .limit(run.batch_size)
                    .with_for_update(skip_locked=True)
                )
            )
            if not items:
                return ()
            chunks = {
                chunk.id: chunk
                for chunk in session.scalars(
                    select(DocumentChunk).where(
                        DocumentChunk.id.in_(
                            tuple(item.document_chunk_id for item in items)
                        )
                    )
                )
            }
            started_at = datetime.now(UTC)
            for item in items:
                item.status = "processing"
                item.attempt_count += 1
                item.error_code = None
                item.started_at = started_at
                item.finished_at = None
            return tuple(
                _ClaimedItem(
                    item_id=item.id,
                    chunk_id=item.document_chunk_id,
                    content_hash=item.chunk_content_hash,
                    content=chunks[item.document_chunk_id].content,
                )
                for item in items
            )

    def _record_success(
        self,
        run_id: uuid.UUID,
        claimed_items: Sequence[_ClaimedItem],
        vectors: Sequence[object],
        *,
        elapsed_nanoseconds: int,
    ) -> None:
        vector_values = {
            vector.source_id: vector.values
            for vector in vectors
            if hasattr(vector, "source_id") and hasattr(vector, "values")
        }
        expected_source_ids = {str(item.chunk_id) for item in claimed_items}
        if set(vector_values) != expected_source_ids:
            self._record_failure(
                run_id,
                tuple(item.item_id for item in claimed_items),
                error_code="invalid_provider_response",
                retryable=False,
            )
            return
        with transactional_session(self._session_factory) as session:
            run = _locked_run(session, run_id)
            completed_at = datetime.now(UTC)
            items = tuple(
                session.scalars(
                    select(EmbeddingRunItem)
                    .where(EmbeddingRunItem.id.in_(tuple(item.item_id for item in claimed_items)))
                    .with_for_update()
                )
            )
            for item in items:
                values = vector_values[str(item.document_chunk_id)]
                if len(values) != run.dimensions:
                    self._mark_items_failed(
                        items,
                        error_code="invalid_vector_dimensions",
                        retryable=False,
                        max_attempts=run.max_attempts,
                    )
                    return
                embedding = session.scalar(
                    select(DocumentChunkEmbedding).where(
                        DocumentChunkEmbedding.document_chunk_id
                        == item.document_chunk_id,
                        DocumentChunkEmbedding.embedding_profile_id
                        == run.embedding_profile_id,
                        DocumentChunkEmbedding.chunk_content_hash
                        == item.chunk_content_hash,
                    )
                )
                if embedding is None:
                    embedding = DocumentChunkEmbedding(
                        id=self._id_factory(),
                        document_chunk_id=item.document_chunk_id,
                        embedding_profile_id=run.embedding_profile_id,
                        chunk_content_hash=item.chunk_content_hash,
                        embedding=_vector_literal(values),
                    )
                    session.add(embedding)
                    session.flush()
                item.document_chunk_embedding_id = embedding.id
                item.status = "succeeded"
                item.error_code = None
                item.finished_at = completed_at
            observations = dict(run.resource_observations)
            observations["peak_rss_bytes"] = resource.getrusage(
                resource.RUSAGE_SELF
            ).ru_maxrss * 1024
            observations["batches"] = int(observations.get("batches", 0)) + 1
            observations["embedding_latency_milliseconds"] = (
                float(observations.get("embedding_latency_milliseconds", 0))
                + elapsed_nanoseconds / 1_000_000
            )
            run.resource_observations = observations

    def _record_failure(
        self,
        run_id: uuid.UUID,
        item_ids: tuple[uuid.UUID, ...],
        *,
        error_code: str,
        retryable: bool,
    ) -> None:
        with transactional_session(self._session_factory) as session:
            run = _locked_run(session, run_id)
            items = tuple(
                session.scalars(
                    select(EmbeddingRunItem)
                    .where(EmbeddingRunItem.id.in_(item_ids))
                    .with_for_update()
                )
            )
            self._mark_items_failed(
                items,
                error_code=error_code,
                retryable=retryable,
                max_attempts=run.max_attempts,
            )

    def _finish(self, run_id: uuid.UUID) -> EmbeddingRunSnapshot:
        with transactional_session(self._session_factory) as session:
            run = _locked_run(session, run_id)
            if run.status != "running":
                return _run_snapshot(session, run)
            counts = _item_counts(session, run.id)
            if any(
                counts.get(status, 0)
                for status in ("pending", "processing", "retryable_failed")
            ):
                return _run_snapshot(session, run)
            run.status = "failed" if counts.get("failed", 0) else "succeeded"
            run.finished_at = datetime.now(UTC)
            return _run_snapshot(session, run)


def _locked_run(session: Session, run_id: uuid.UUID) -> EmbeddingRun:
    run = session.scalar(
        select(EmbeddingRun).where(EmbeddingRun.id == run_id).with_for_update()
    )
    if run is None:
        raise ResourceNotFoundError("The embedding run was not found.")
    return run


def _mark_items_failed(
    items: Sequence[EmbeddingRunItem],
    *,
    error_code: str,
    retryable: bool,
    max_attempts: int,
) -> None:
    finished_at = datetime.now(UTC)
    for item in items:
        item.status = (
            "retryable_failed" if retryable and item.attempt_count < max_attempts else "failed"
        )
        item.error_code = error_code
        item.finished_at = finished_at


def _run_snapshot(session: Session, run: EmbeddingRun) -> EmbeddingRunSnapshot:
    return EmbeddingRunSnapshot(
        id=run.id,
        corpus_snapshot_id=run.corpus_snapshot_id,
        embedding_profile_id=run.embedding_profile_id,
        status=run.status,
        item_counts=_item_counts(session, run.id),
    )


def _item_counts(session: Session, run_id: uuid.UUID) -> dict[str, int]:
    rows = session.execute(
        select(EmbeddingRunItem.status, func.count())
        .where(EmbeddingRunItem.embedding_run_id == run_id)
        .group_by(EmbeddingRunItem.status)
    )
    return {status: int(count) for status, count in rows}


def _vector_literal(values: Sequence[float]) -> str:
    return "[" + ",".join(format(value, ".17g") for value in values) + "]"