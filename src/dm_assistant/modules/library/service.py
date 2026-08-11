"""Transactional, idempotent Library source-registry reconciliation."""

import hashlib
import uuid
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from dm_assistant.adapters.sources import SourceReader
from dm_assistant.db import build_session_factory, transactional_session
from dm_assistant.errors import ConflictError, DomainError, InvalidInputError
from dm_assistant.modules.library.contracts import (
    DiscoveredSource,
    IngestionOutcome,
    IngestionResult,
    IngestionStatus,
    IngestSource,
    MissingReconciliationResult,
    PathEventKind,
    ReconcileMissingSources,
    ReconciliationAmbiguity,
    ReconciliationAmbiguityReason,
    SourceLocator,
    SourcePresence,
    SourceScope,
)
from dm_assistant.modules.library.models import (
    Document,
    DocumentPathHistory,
    DocumentRevision,
    IngestionRun,
)
from dm_assistant.modules.library.repository import (
    LibraryRepository,
    SqlAlchemyLibraryRepository,
)

RepositoryFactory = Callable[[Session], LibraryRepository]
IdFactory = Callable[[], uuid.UUID]
Clock = Callable[[], datetime]
_EXACT_UTF8_VERSION = "exact-utf8-v1"
_NO_CHUNKER_VERSION = "not-run"


class LibraryIngestionService:
    """Own filesystem-to-registry decisions without parsing or canonical writes."""

    def __init__(
        self,
        engine: Engine,
        source_reader: SourceReader,
        *,
        repository_factory: RepositoryFactory = SqlAlchemyLibraryRepository,
        id_factory: IdFactory = uuid.uuid4,
        clock: Clock | None = None,
    ) -> None:
        self._session_factory = build_session_factory(engine)
        self._source_reader = source_reader
        self._repository_factory = repository_factory
        self._id_factory = id_factory
        self._clock = clock or (lambda: datetime.now(UTC))

    def ingest(self, command: IngestSource) -> IngestionResult:
        source_path = command.locator.registry_path
        run_id = self._start_run(
            command.scope,
            root_label=command.locator.root_label,
            action="ingest_source",
            configuration={
                "source_path": source_path,
                "document_type": command.classification.document_type.value,
                "authority_class": command.classification.authority_class.value,
                "ruleset": (
                    command.classification.ruleset.value
                    if command.classification.ruleset is not None
                    else None
                ),
                "visibility_policy": command.classification.visibility.policy.value,
            },
        )
        try:
            return self._reconcile_source(run_id, command)
        except DomainError as error:
            self._mark_run_failed(run_id, error_code=error.code.value)
            raise
        except Exception:
            self._mark_run_failed(run_id, error_code="unexpected_failure")
            raise

    def reconcile_missing(
        self,
        command: ReconcileMissingSources,
    ) -> MissingReconciliationResult:
        run_id = self._start_run(
            command.scope,
            root_label=command.root_label,
            action="reconcile_missing",
            configuration={"confirm_retirement": command.confirm_retirement},
        )
        try:
            self._source_reader.ensure_root(command.root_label)
            with transactional_session(self._session_factory) as session:
                repository = self._repository_factory(session)
                repository.lock_scope(command.scope)
                run = self._require_running_run(repository, run_id)
                retired_ids: list[uuid.UUID] = []
                for document in repository.active_documents(command.scope):
                    locator = self._registered_locator(document.source_path)
                    if locator.root_label != command.root_label:
                        continue
                    presence = self._source_reader.probe_registry_path(
                        document.source_path
                    )
                    if presence is SourcePresence.PRESENT:
                        continue
                    current_path = self._require_current_path(repository, document.id)
                    event_time = self._next_event_time(current_path)
                    self._replace_current_path(
                        repository,
                        document,
                        source_path=document.source_path,
                        content_sha256=current_path.content_hash_at_event,
                        event_kind=PathEventKind.RETIRED,
                        event_time=event_time,
                        retired_at=event_time,
                    )
                    retired_ids.append(document.id)
                stable_ids = _stable_ids(retired_ids)
                self._finish_run(
                    repository,
                    run,
                    status=IngestionStatus.SUCCEEDED,
                    summary={
                        "outcome": "missing_reconciled",
                        "retired_document_ids": [str(item) for item in stable_ids],
                    },
                )
                return MissingReconciliationResult(
                    run_id=run_id,
                    status=IngestionStatus.SUCCEEDED,
                    root_label=command.root_label,
                    retired_document_ids=stable_ids,
                )
        except DomainError as error:
            self._mark_run_failed(run_id, error_code=error.code.value)
            raise
        except Exception:
            self._mark_run_failed(run_id, error_code="unexpected_failure")
            raise

    def _reconcile_source(
        self,
        run_id: uuid.UUID,
        command: IngestSource,
    ) -> IngestionResult:
        with transactional_session(self._session_factory) as session:
            repository = self._repository_factory(session)
            repository.lock_scope(command.scope)
            run = self._require_running_run(repository, run_id)
            source = self._read_source(command.locator)
            at_path = repository.documents_at_path(command.scope, source.source_path)
            active_at_path = tuple(item for item in at_path if item.retired_at is None)
            if len(active_at_path) > 1:
                raise ConflictError(
                    "The source registry contains duplicate active paths."
                )
            if active_at_path:
                return self._ingest_active_document(
                    repository,
                    run,
                    active_at_path[0],
                    command,
                    source,
                )

            retired_at_path = tuple(
                item for item in at_path if item.retired_at is not None
            )
            if retired_at_path:
                exact_retired = tuple(
                    item
                    for item in retired_at_path
                    if self._require_current_path(
                        repository, item.id
                    ).content_hash_at_event
                    == source.content_sha256
                )
                if len(exact_retired) == 1:
                    return self._restore_document(
                        repository,
                        run,
                        exact_retired[0],
                        command,
                        source,
                    )
                if len(exact_retired) > 1 or len(retired_at_path) > 1:
                    return self._review_required(
                        repository,
                        run,
                        source,
                        reason=(
                            ReconciliationAmbiguityReason.MULTIPLE_RETIRED_PATH_CANDIDATES
                        ),
                        candidates=(exact_retired or retired_at_path),
                    )
                return self._restore_document(
                    repository,
                    run,
                    retired_at_path[0],
                    command,
                    source,
                )

            exact_documents = repository.documents_with_current_hash(
                command.scope,
                source.content_sha256,
            )
            move_candidates: list[Document] = []
            present_duplicates: list[Document] = []
            probed: dict[uuid.UUID, SourcePresence] = {}
            for document in exact_documents:
                if document.retired_at is not None:
                    move_candidates.append(document)
                    continue
                presence = self._source_reader.probe_registry_path(document.source_path)
                probed[document.id] = presence
                if presence is SourcePresence.MISSING:
                    move_candidates.append(document)
                else:
                    present_duplicates.append(document)

            if len(move_candidates) > 1:
                return self._review_required(
                    repository,
                    run,
                    source,
                    reason=(
                        ReconciliationAmbiguityReason.MULTIPLE_EXACT_MOVE_CANDIDATES
                    ),
                    candidates=tuple(move_candidates),
                )
            if move_candidates:
                return self._move_document(
                    repository,
                    run,
                    move_candidates[0],
                    source,
                    duplicate_documents=tuple(present_duplicates),
                )

            possible_edited_moves: list[Document] = []
            exact_ids = {item.id for item in exact_documents}
            for document in repository.active_documents(command.scope):
                if document.id in exact_ids:
                    presence = probed.get(document.id, SourcePresence.PRESENT)
                else:
                    presence = self._source_reader.probe_registry_path(
                        document.source_path
                    )
                if presence is SourcePresence.MISSING:
                    possible_edited_moves.append(document)
            if possible_edited_moves:
                return self._review_required(
                    repository,
                    run,
                    source,
                    reason=ReconciliationAmbiguityReason.POSSIBLE_MOVED_AND_EDITED,
                    candidates=tuple(possible_edited_moves),
                )

            return self._create_document(
                repository,
                run,
                command,
                source,
                duplicate_documents=tuple(present_duplicates),
            )

    def _read_source(self, locator: SourceLocator) -> DiscoveredSource:
        source_bytes = self._source_reader.read(locator)
        try:
            content = source_bytes.data.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            raise InvalidInputError(
                "The source file must contain valid UTF-8 text."
            ) from None
        return DiscoveredSource(
            locator=locator,
            source_path=source_bytes.source_path,
            content_sha256=hashlib.sha256(source_bytes.data).hexdigest(),
            byte_size=len(source_bytes.data),
            content=content,
        )

    def _ingest_active_document(
        self,
        repository: LibraryRepository,
        run: IngestionRun,
        document: Document,
        command: IngestSource,
        source: DiscoveredSource,
    ) -> IngestionResult:
        current_path = self._require_current_path(repository, document.id)
        if current_path.content_hash_at_event == source.content_sha256:
            unchanged_revision = self._require_revision(
                repository,
                document.id,
                source.content_sha256,
            )
            return self._complete_result(
                repository,
                run,
                source,
                document,
                unchanged_revision,
                outcome=IngestionOutcome.UNCHANGED,
            )

        event_time = self._next_event_time(current_path)
        self._replace_current_path(
            repository,
            document,
            source_path=source.source_path,
            content_sha256=source.content_sha256,
            event_kind=PathEventKind.CONTENT_CHANGED,
            event_time=event_time,
            retired_at=None,
        )
        revision = repository.revision_by_hash(
            document.id,
            source.content_sha256,
        )
        if revision is None:
            revision = self._create_revision(
                repository,
                run,
                document,
                command,
                source,
            )
        return self._complete_result(
            repository,
            run,
            source,
            document,
            revision,
            outcome=IngestionOutcome.UPDATED,
        )

    def _create_document(
        self,
        repository: LibraryRepository,
        run: IngestionRun,
        command: IngestSource,
        source: DiscoveredSource,
        *,
        duplicate_documents: tuple[Document, ...],
    ) -> IngestionResult:
        document_id = self._id_factory()
        event_time = self._timestamp()
        document = Document(
            id=document_id,
            campaign_id=command.scope.campaign_id,
            corpus=command.scope.corpus.value,
            logical_key=str(document_id),
            source_path=source.source_path,
            created_at=event_time,
            retired_at=None,
        )
        repository.add_document(document)
        repository.flush()
        repository.add_path(
            DocumentPathHistory(
                id=self._id_factory(),
                campaign_id=command.scope.campaign_id,
                corpus=command.scope.corpus.value,
                document_id=document.id,
                source_path=source.source_path,
                event_kind=PathEventKind.DISCOVERED.value,
                content_hash_at_event=source.content_sha256,
                valid_from=event_time,
                valid_to=None,
            )
        )
        repository.flush()
        revision = self._create_revision(
            repository,
            run,
            document,
            command,
            source,
        )
        return self._complete_result(
            repository,
            run,
            source,
            document,
            revision,
            outcome=(
                IngestionOutcome.DUPLICATE_CREATED
                if duplicate_documents
                else IngestionOutcome.CREATED
            ),
            duplicate_documents=duplicate_documents,
        )

    def _move_document(
        self,
        repository: LibraryRepository,
        run: IngestionRun,
        document: Document,
        source: DiscoveredSource,
        *,
        duplicate_documents: tuple[Document, ...],
    ) -> IngestionResult:
        was_retired = document.retired_at is not None
        current_path = self._require_current_path(repository, document.id)
        event_time = self._next_event_time(current_path)
        self._replace_current_path(
            repository,
            document,
            source_path=source.source_path,
            content_sha256=source.content_sha256,
            event_kind=(PathEventKind.RESTORED if was_retired else PathEventKind.MOVED),
            event_time=event_time,
            retired_at=None,
        )
        revision = self._require_revision(
            repository,
            document.id,
            source.content_sha256,
        )
        return self._complete_result(
            repository,
            run,
            source,
            document,
            revision,
            outcome=(
                IngestionOutcome.RESTORED if was_retired else IngestionOutcome.MOVED
            ),
            duplicate_documents=duplicate_documents,
        )

    def _restore_document(
        self,
        repository: LibraryRepository,
        run: IngestionRun,
        document: Document,
        command: IngestSource,
        source: DiscoveredSource,
    ) -> IngestionResult:
        current_path = self._require_current_path(repository, document.id)
        event_time = self._next_event_time(current_path)
        self._replace_current_path(
            repository,
            document,
            source_path=source.source_path,
            content_sha256=source.content_sha256,
            event_kind=PathEventKind.RESTORED,
            event_time=event_time,
            retired_at=None,
        )
        revision = repository.revision_by_hash(
            document.id,
            source.content_sha256,
        )
        if revision is None:
            revision = self._create_revision(
                repository,
                run,
                document,
                command,
                source,
            )
        return self._complete_result(
            repository,
            run,
            source,
            document,
            revision,
            outcome=IngestionOutcome.RESTORED,
        )

    def _replace_current_path(
        self,
        repository: LibraryRepository,
        document: Document,
        *,
        source_path: str,
        content_sha256: str,
        event_kind: PathEventKind,
        event_time: datetime,
        retired_at: datetime | None,
    ) -> None:
        current = self._require_current_path(repository, document.id)
        current.valid_to = event_time
        repository.flush()
        document.source_path = source_path
        document.retired_at = retired_at
        repository.flush()
        repository.add_path(
            DocumentPathHistory(
                id=self._id_factory(),
                campaign_id=document.campaign_id,
                corpus=document.corpus,
                document_id=document.id,
                source_path=source_path,
                event_kind=event_kind.value,
                content_hash_at_event=content_sha256,
                valid_from=event_time,
                valid_to=None,
            )
        )
        repository.flush()

    def _create_revision(
        self,
        repository: LibraryRepository,
        run: IngestionRun,
        document: Document,
        command: IngestSource,
        source: DiscoveredSource,
    ) -> DocumentRevision:
        classification = command.classification
        revision = DocumentRevision(
            id=self._id_factory(),
            campaign_id=command.scope.campaign_id,
            corpus=command.scope.corpus.value,
            document_id=document.id,
            revision_number=repository.next_revision_number(document.id),
            content_hash=source.content_sha256,
            byte_size=source.byte_size,
            content_snapshot=source.content,
            title=command.title,
            document_type=classification.document_type.value,
            authority_class=classification.authority_class.value,
            ruleset=(
                classification.ruleset.value
                if classification.ruleset is not None
                else None
            ),
            visibility_policy=classification.visibility.policy.value,
            visibility_audience=list(classification.visibility.audience_ids),
            source_path=source.source_path,
            source_metadata=dict(command.source_metadata),
            parser_version=_EXACT_UTF8_VERSION,
            ingestion_run_id=run.id,
            ingested_at=self._timestamp(),
        )
        repository.add_revision(revision)
        repository.flush()
        return revision

    def _review_required(
        self,
        repository: LibraryRepository,
        run: IngestionRun,
        source: DiscoveredSource,
        *,
        reason: ReconciliationAmbiguityReason,
        candidates: tuple[Document, ...],
    ) -> IngestionResult:
        candidate_ids = _stable_ids(item.id for item in candidates)
        ambiguity = ReconciliationAmbiguity(
            reason=reason,
            candidate_document_ids=candidate_ids,
        )
        self._finish_run(
            repository,
            run,
            status=IngestionStatus.REVIEW_REQUIRED,
            summary={
                "outcome": IngestionOutcome.REVIEW_REQUIRED.value,
                "source_path": source.source_path,
                "content_sha256": source.content_sha256,
                "ambiguity_reason": reason.value,
                "candidate_document_ids": [str(item) for item in candidate_ids],
            },
        )
        return IngestionResult(
            run_id=run.id,
            status=IngestionStatus.REVIEW_REQUIRED,
            outcome=IngestionOutcome.REVIEW_REQUIRED,
            source_path=source.source_path,
            content_sha256=source.content_sha256,
            ambiguity=ambiguity,
        )

    def _complete_result(
        self,
        repository: LibraryRepository,
        run: IngestionRun,
        source: DiscoveredSource,
        document: Document,
        revision: DocumentRevision,
        *,
        outcome: IngestionOutcome,
        duplicate_documents: tuple[Document, ...] = (),
    ) -> IngestionResult:
        duplicate_ids = _stable_ids(item.id for item in duplicate_documents)
        self._finish_run(
            repository,
            run,
            status=IngestionStatus.SUCCEEDED,
            summary={
                "outcome": outcome.value,
                "source_path": source.source_path,
                "content_sha256": source.content_sha256,
                "document_id": str(document.id),
                "revision_id": str(revision.id),
                "revision_number": revision.revision_number,
                "duplicate_document_ids": [str(item) for item in duplicate_ids],
            },
        )
        return IngestionResult(
            run_id=run.id,
            status=IngestionStatus.SUCCEEDED,
            outcome=outcome,
            source_path=source.source_path,
            content_sha256=source.content_sha256,
            document_id=document.id,
            revision_id=revision.id,
            revision_number=revision.revision_number,
            duplicate_document_ids=duplicate_ids,
        )

    def _start_run(
        self,
        scope: SourceScope,
        *,
        root_label: str,
        action: str,
        configuration: dict[str, object],
    ) -> uuid.UUID:
        run_id = self._id_factory()
        started_at = self._timestamp()
        with transactional_session(self._session_factory) as session:
            repository = self._repository_factory(session)
            repository.add_run(
                IngestionRun(
                    id=run_id,
                    campaign_id=scope.campaign_id,
                    corpus=scope.corpus.value,
                    source_root_label=root_label,
                    configuration={"action": action, **configuration},
                    parser_version=_EXACT_UTF8_VERSION,
                    chunker_version=_NO_CHUNKER_VERSION,
                    status=IngestionStatus.RUNNING.value,
                    summary={},
                    started_at=started_at,
                    finished_at=None,
                )
            )
            repository.flush()
        return run_id

    def _mark_run_failed(self, run_id: uuid.UUID, *, error_code: str) -> None:
        with transactional_session(self._session_factory) as session:
            repository = self._repository_factory(session)
            run = repository.get_run(run_id, for_update=True)
            if run is None or run.status != IngestionStatus.RUNNING.value:
                return
            self._finish_run(
                repository,
                run,
                status=IngestionStatus.FAILED,
                summary={"outcome": "failed", "error_code": error_code},
            )

    def _finish_run(
        self,
        repository: LibraryRepository,
        run: IngestionRun,
        *,
        status: IngestionStatus,
        summary: dict[str, object],
    ) -> None:
        if run.status != IngestionStatus.RUNNING.value:
            raise ConflictError("The ingestion run is already terminal.")
        run.status = status.value
        run.summary = summary
        run.finished_at = max(self._timestamp(), run.started_at)
        repository.flush()

    @staticmethod
    def _require_running_run(
        repository: LibraryRepository,
        run_id: uuid.UUID,
    ) -> IngestionRun:
        run = repository.get_run(run_id, for_update=True)
        if run is None:
            raise ConflictError("The ingestion run was not found.")
        if run.status != IngestionStatus.RUNNING.value:
            raise ConflictError("The ingestion run is already terminal.")
        return run

    @staticmethod
    def _require_current_path(
        repository: LibraryRepository,
        document_id: uuid.UUID,
    ) -> DocumentPathHistory:
        current = repository.current_path(document_id, for_update=True)
        if current is None:
            raise ConflictError("The document has no current source path.")
        return current

    @staticmethod
    def _require_revision(
        repository: LibraryRepository,
        document_id: uuid.UUID,
        content_sha256: str,
    ) -> DocumentRevision:
        revision = repository.revision_by_hash(document_id, content_sha256)
        if revision is None:
            raise ConflictError("The source registry is missing an exact revision.")
        return revision

    @staticmethod
    def _registered_locator(source_path: str) -> SourceLocator:
        try:
            return SourceLocator.from_registry_path(source_path)
        except ValueError:
            raise ConflictError(
                "The source registry contains an invalid path."
            ) from None

    def _next_event_time(self, current_path: DocumentPathHistory) -> datetime:
        return max(
            self._timestamp(),
            current_path.valid_from + timedelta(microseconds=1),
        )

    def _timestamp(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise RuntimeError("Library clock must return a timezone-aware timestamp")
        return value


def _stable_ids(values: Iterable[uuid.UUID]) -> tuple[uuid.UUID, ...]:
    return tuple(sorted(values, key=str))
