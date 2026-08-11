"""PostgreSQL invariants for immutable Library sources and snapshots."""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import Engine, insert, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError

from dm_assistant.db import Campaign
from dm_assistant.modules.library.models import (
    CorpusSnapshot,
    CorpusSnapshotDocument,
    Document,
    DocumentChunk,
    DocumentPathHistory,
    DocumentRevision,
    IngestionRun,
)

pytestmark = pytest.mark.integration

_DEFAULT_CONTENT = "# Arrival\nThe synthetic party reached the quiet gate."


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _campaign(connection: Any, name: str = "Synthetic Library Campaign") -> uuid.UUID:
    campaign_id = uuid.uuid4()
    connection.execute(insert(Campaign).values(id=campaign_id, name=name))
    return campaign_id


def _run(
    connection: Any,
    *,
    campaign_id: uuid.UUID | None,
    corpus: str,
    status: str = "succeeded",
) -> uuid.UUID:
    run_id = uuid.uuid4()
    started_at = datetime.now(UTC)
    connection.execute(
        insert(IngestionRun).values(
            id=run_id,
            campaign_id=campaign_id,
            corpus=corpus,
            source_root_label="synthetic-fixtures",
            configuration={"include": ["*.md"]},
            parser_version="synthetic-parser-v1",
            chunker_version="synthetic-chunker-v1",
            status=status,
            summary={} if status == "running" else {"documents": 1},
            started_at=started_at,
            finished_at=None if status == "running" else started_at,
        )
    )
    return run_id


def _document(
    connection: Any,
    *,
    campaign_id: uuid.UUID | None,
    corpus: str,
    source_path: str = "notes/synthetic.md",
    logical_key: str | None = None,
) -> uuid.UUID:
    document_id = uuid.uuid4()
    connection.execute(
        insert(Document).values(
            id=document_id,
            campaign_id=campaign_id,
            corpus=corpus,
            logical_key=logical_key or f"synthetic-{document_id}",
            source_path=source_path,
        )
    )
    connection.execute(
        insert(DocumentPathHistory).values(
            id=uuid.uuid4(),
            campaign_id=campaign_id,
            corpus=corpus,
            document_id=document_id,
            source_path=source_path,
            event_kind="discovered",
            content_hash_at_event=_sha256(_DEFAULT_CONTENT),
        )
    )
    return document_id


def _revision(
    connection: Any,
    *,
    campaign_id: uuid.UUID | None,
    corpus: str,
    document_id: uuid.UUID,
    ingestion_run_id: uuid.UUID,
    content: str = _DEFAULT_CONTENT,
    revision_number: int = 1,
    document_type: str = "canon_note",
    authority_class: str = "canonical_claim",
    ruleset: str | None = None,
    visibility_policy: str = "dm_only",
    visibility_audience: list[str] | None = None,
) -> uuid.UUID:
    revision_id = uuid.uuid4()
    source_path = connection.scalar(
        select(Document.source_path).where(Document.id == document_id)
    )
    connection.execute(
        insert(DocumentRevision).values(
            id=revision_id,
            campaign_id=campaign_id,
            corpus=corpus,
            document_id=document_id,
            revision_number=revision_number,
            content_hash=_sha256(content),
            byte_size=len(content.encode()),
            content_snapshot=content,
            title="Synthetic Arrival",
            document_type=document_type,
            authority_class=authority_class,
            ruleset=ruleset,
            visibility_policy=visibility_policy,
            visibility_audience=visibility_audience or [],
            source_path=source_path,
            source_metadata={"format": "markdown"},
            parser_version="synthetic-parser-v1",
            ingestion_run_id=ingestion_run_id,
        )
    )
    return revision_id


def test_document_scope_path_registry_and_global_identity_are_constrained(
    db_engine: Engine,
) -> None:
    with db_engine.begin() as connection:
        campaign_id = _campaign(connection)
        document_id = _document(connection, campaign_id=campaign_id, corpus="campaign")
        path_count = connection.scalar(
            select(text("count(*)")).select_from(DocumentPathHistory)
        )
    assert path_count == 1

    with pytest.raises(IntegrityError):
        with db_engine.begin() as connection:
            connection.execute(
                insert(Document).values(
                    id=uuid.uuid4(),
                    campaign_id=None,
                    corpus="campaign",
                    logical_key="owner-required",
                    source_path="notes/owner-required.md",
                )
            )

    with pytest.raises(IntegrityError):
        with db_engine.begin() as connection:
            connection.execute(
                insert(Document).values(
                    id=uuid.uuid4(),
                    campaign_id=campaign_id,
                    corpus="campaign",
                    logical_key="unsafe-path",
                    source_path="../private.md",
                )
            )

    with db_engine.begin() as connection:
        _document(
            connection,
            campaign_id=None,
            corpus="rules",
            source_path="rules/synthetic.md",
            logical_key="global-rules-document",
        )
    with pytest.raises(IntegrityError):
        with db_engine.begin() as connection:
            connection.execute(
                insert(Document).values(
                    id=uuid.uuid4(),
                    campaign_id=None,
                    corpus="rules",
                    logical_key="global-rules-document",
                    source_path="rules/other-copy.md",
                )
            )

    with pytest.raises(DBAPIError, match="logical document identity is immutable"):
        with db_engine.begin() as connection:
            connection.execute(
                update(Document)
                .where(Document.id == document_id)
                .values(logical_key="rewritten-identity")
            )

    with pytest.raises(DBAPIError, match="path and path history are inconsistent"):
        with db_engine.begin() as connection:
            connection.execute(
                update(Document)
                .where(Document.id == document_id)
                .values(source_path="notes/unregistered-move.md")
            )


def test_revision_hash_classification_uniqueness_and_immutability(
    db_engine: Engine,
) -> None:
    content = _DEFAULT_CONTENT
    with db_engine.begin() as connection:
        campaign_id = _campaign(connection)
        run_id = _run(connection, campaign_id=campaign_id, corpus="campaign")
        document_id = _document(connection, campaign_id=campaign_id, corpus="campaign")
        revision_id = _revision(
            connection,
            campaign_id=campaign_id,
            corpus="campaign",
            document_id=document_id,
            ingestion_run_id=run_id,
            content=content,
        )

    with pytest.raises(IntegrityError):
        with db_engine.begin() as connection:
            _revision(
                connection,
                campaign_id=campaign_id,
                corpus="campaign",
                document_id=document_id,
                ingestion_run_id=run_id,
                content=content,
                revision_number=2,
            )

    edited_content = f"{content}\nA synthetic bell rang."
    changed_at = datetime.now(UTC) + timedelta(seconds=1)
    with db_engine.begin() as connection:
        connection.execute(
            update(DocumentPathHistory)
            .where(
                DocumentPathHistory.document_id == document_id,
                DocumentPathHistory.valid_to.is_(None),
            )
            .values(valid_to=changed_at)
        )
        connection.execute(
            insert(DocumentPathHistory).values(
                id=uuid.uuid4(),
                campaign_id=campaign_id,
                corpus="campaign",
                document_id=document_id,
                source_path="notes/synthetic.md",
                event_kind="content_changed",
                content_hash_at_event=_sha256(edited_content),
                valid_from=changed_at,
            )
        )
        _revision(
            connection,
            campaign_id=campaign_id,
            corpus="campaign",
            document_id=document_id,
            ingestion_run_id=run_id,
            content=edited_content,
            revision_number=2,
        )

    with pytest.raises(DBAPIError, match="content hash does not match source"):
        with db_engine.begin() as connection:
            connection.execute(
                insert(DocumentRevision).values(
                    id=uuid.uuid4(),
                    campaign_id=campaign_id,
                    corpus="campaign",
                    document_id=document_id,
                    revision_number=3,
                    content_hash="0" * 64,
                    byte_size=4,
                    content_snapshot="edit",
                    title="Invalid hash",
                    document_type="reference_lore",
                    authority_class="reference",
                    ruleset=None,
                    visibility_policy="dm_only",
                    visibility_audience=[],
                    source_path="notes/synthetic.md",
                    source_metadata={},
                    parser_version="synthetic-parser-v1",
                    ingestion_run_id=run_id,
                )
            )

    with pytest.raises(IntegrityError):
        with db_engine.begin() as connection:
            rules_run_id = _run(connection, campaign_id=None, corpus="rules")
            rules_document_id = _document(
                connection,
                campaign_id=None,
                corpus="rules",
                source_path="rules/official.md",
            )
            _revision(
                connection,
                campaign_id=None,
                corpus="rules",
                document_id=rules_document_id,
                ingestion_run_id=rules_run_id,
                document_type="rules_reference",
                authority_class="official_rules",
                ruleset="dnd_5e_2024",
                visibility_policy="public",
            )

    with pytest.raises(DBAPIError, match="immutable library record"):
        with db_engine.begin() as connection:
            connection.execute(
                update(DocumentRevision)
                .where(DocumentRevision.id == revision_id)
                .values(title="Rewritten source")
            )


def test_chunks_preserve_exact_offsets_metadata_and_lexical_projection(
    db_engine: Engine,
) -> None:
    content = _DEFAULT_CONTENT
    start = content.index("The")
    chunk_content = content[start:]
    with db_engine.begin() as connection:
        campaign_id = _campaign(connection)
        run_id = _run(connection, campaign_id=campaign_id, corpus="campaign")
        document_id = _document(connection, campaign_id=campaign_id, corpus="campaign")
        revision_id = _revision(
            connection,
            campaign_id=campaign_id,
            corpus="campaign",
            document_id=document_id,
            ingestion_run_id=run_id,
            content=content,
        )
        chunk_id = uuid.uuid4()
        connection.execute(
            insert(DocumentChunk).values(
                id=chunk_id,
                campaign_id=campaign_id,
                corpus="campaign",
                document_revision_id=revision_id,
                ordinal=0,
                heading_path=["Arrival"],
                start_offset=start,
                end_offset=len(content),
                page_start=2,
                page_end=2,
                content=chunk_content,
                content_hash=_sha256(chunk_content),
                fts_config="english",
                chunker_version="synthetic-chunker-v1",
                authority_class="canonical_claim",
                ruleset=None,
                visibility_policy="dm_only",
                visibility_audience=[],
                chunk_metadata={"block": "paragraph"},
            )
        )
        matches = connection.scalar(
            text(
                "SELECT search_vector @@ plainto_tsquery('english', 'quiet gate') "
                "FROM document_chunk WHERE id = :chunk_id"
            ),
            {"chunk_id": chunk_id},
        )
    assert matches is True

    with pytest.raises(DBAPIError, match="does not match exact source span"):
        with db_engine.begin() as connection:
            connection.execute(
                insert(DocumentChunk).values(
                    id=uuid.uuid4(),
                    campaign_id=campaign_id,
                    corpus="campaign",
                    document_revision_id=revision_id,
                    ordinal=1,
                    heading_path=["Arrival"],
                    start_offset=start,
                    end_offset=len(content),
                    page_start=None,
                    page_end=None,
                    content="A fabricated chunk.",
                    content_hash=_sha256("A fabricated chunk."),
                    fts_config="simple",
                    chunker_version="synthetic-chunker-v1",
                    authority_class="canonical_claim",
                    ruleset=None,
                    visibility_policy="dm_only",
                    visibility_audience=[],
                    chunk_metadata={},
                )
            )

    with pytest.raises(DBAPIError, match="immutable library record"):
        with db_engine.begin() as connection:
            connection.execute(
                update(DocumentChunk)
                .where(DocumentChunk.id == chunk_id)
                .values(content="changed")
            )


def test_snapshot_membership_is_scope_safe_isolated_and_immutable(
    db_engine: Engine,
) -> None:
    with db_engine.begin() as connection:
        first_campaign = _campaign(connection, "First Synthetic Campaign")
        second_campaign = _campaign(connection, "Second Synthetic Campaign")
        first_run = _run(connection, campaign_id=first_campaign, corpus="campaign")
        second_run = _run(connection, campaign_id=second_campaign, corpus="campaign")
        first_document = _document(
            connection,
            campaign_id=first_campaign,
            corpus="campaign",
            source_path="notes/first.md",
        )
        second_document = _document(
            connection,
            campaign_id=second_campaign,
            corpus="campaign",
            source_path="notes/second.md",
        )
        first_revision = _revision(
            connection,
            campaign_id=first_campaign,
            corpus="campaign",
            document_id=first_document,
            ingestion_run_id=first_run,
        )
        second_revision = _revision(
            connection,
            campaign_id=second_campaign,
            corpus="campaign",
            document_id=second_document,
            ingestion_run_id=second_run,
        )
        snapshot_id = uuid.uuid4()
        connection.execute(
            insert(CorpusSnapshot).values(
                id=snapshot_id,
                campaign_id=first_campaign,
                corpus="campaign",
                parent_snapshot_id=None,
                ingestion_run_id=first_run,
                state="candidate",
            )
        )
        connection.execute(
            insert(CorpusSnapshotDocument).values(
                corpus_snapshot_id=snapshot_id,
                document_id=first_document,
                document_revision_id=first_revision,
                campaign_id=first_campaign,
                corpus="campaign",
                ordinal=0,
            )
        )

    with pytest.raises(DBAPIError, match="scope/document mismatch"):
        with db_engine.begin() as connection:
            connection.execute(
                insert(CorpusSnapshotDocument).values(
                    corpus_snapshot_id=snapshot_id,
                    document_id=second_document,
                    document_revision_id=second_revision,
                    campaign_id=first_campaign,
                    corpus="campaign",
                    ordinal=1,
                )
            )

    activated_at = datetime.now(UTC) + timedelta(seconds=1)
    with db_engine.begin() as connection:
        connection.execute(
            update(CorpusSnapshot)
            .where(CorpusSnapshot.id == snapshot_id)
            .values(state="active", activated_at=activated_at)
        )

    with pytest.raises(DBAPIError, match="only be added to candidate"):
        with db_engine.begin() as connection:
            connection.execute(
                insert(CorpusSnapshotDocument).values(
                    corpus_snapshot_id=snapshot_id,
                    document_id=uuid.uuid4(),
                    document_revision_id=second_revision,
                    campaign_id=first_campaign,
                    corpus="campaign",
                    ordinal=1,
                )
            )

    with pytest.raises(DBAPIError, match="immutable library record"):
        with db_engine.begin() as connection:
            connection.execute(
                update(CorpusSnapshotDocument)
                .where(CorpusSnapshotDocument.corpus_snapshot_id == snapshot_id)
                .values(ordinal=2)
            )
