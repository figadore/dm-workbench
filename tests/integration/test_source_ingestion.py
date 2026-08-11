"""End-to-end Library source registry and idempotent ingestion tests."""

import uuid
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import Engine, func, select

from dm_assistant.adapters.sources import LocalSourceReader
from dm_assistant.db import Campaign, build_session_factory, transactional_session
from dm_assistant.errors import InvalidInputError
from dm_assistant.modules.library import (
    AuthorityClass,
    CorpusKind,
    DocumentType,
    IngestionOutcome,
    IngestionStatus,
    IngestSource,
    LibraryIngestionService,
    ReconcileMissingSources,
    ReconciliationAmbiguityReason,
    RevisionClassification,
    Ruleset,
    SourceLocator,
    SourceScope,
    SourceVisibility,
    VisibilityLabel,
)
from dm_assistant.modules.library.models import (
    Document,
    DocumentChunk,
    DocumentPathHistory,
    DocumentRevision,
    IngestionRun,
)

pytestmark = pytest.mark.integration


def _campaign(engine: Engine, name: str = "Synthetic Source Campaign") -> uuid.UUID:
    campaign_id = uuid.uuid4()
    factory = build_session_factory(engine)
    with transactional_session(factory) as session:
        session.add(Campaign(id=campaign_id, name=name))
    return campaign_id


def _service(engine: Engine, root: Path) -> LibraryIngestionService:
    return LibraryIngestionService(
        engine,
        LocalSourceReader({"campaign": root}, maximum_bytes=64 * 1024),
    )


def _command(
    campaign_id: uuid.UUID,
    relative_path: str,
    *,
    title: str = "Synthetic Source",
) -> IngestSource:
    return IngestSource(
        scope=SourceScope(
            campaign_id=campaign_id,
            corpus=CorpusKind.CAMPAIGN,
        ),
        locator=SourceLocator(
            root_label="campaign",
            relative_path=relative_path,
        ),
        classification=RevisionClassification(
            corpus=CorpusKind.CAMPAIGN,
            document_type=DocumentType.REFERENCE_LORE,
            authority_class=AuthorityClass.REFERENCE,
            ruleset=None,
            visibility=VisibilityLabel(policy=SourceVisibility.DM_ONLY),
        ),
        title=title,
        source_metadata={"fixture_kind": "synthetic_markdown"},
    )


def _retirement_command(campaign_id: uuid.UUID) -> ReconcileMissingSources:
    return ReconcileMissingSources(
        scope=SourceScope(
            campaign_id=campaign_id,
            corpus=CorpusKind.CAMPAIGN,
        ),
        root_label="campaign",
        confirm_retirement=True,
    )


def test_first_unchanged_and_edited_ingestion_are_idempotent(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    root = tmp_path / "vault"
    source_path = root / "sessions" / "arrival.md"
    source_path.parent.mkdir(parents=True)
    first_text = "# Arrival\nÉowyn reached the synthetic gate.\n"
    source_path.write_text(first_text, encoding="utf-8")
    campaign_id = _campaign(db_engine)
    service = _service(db_engine, root)
    command = _command(campaign_id, "sessions/arrival.md", title="Arrival")

    created = service.ingest(command)
    unchanged = service.ingest(command)
    second_text = f"{first_text}A quiet bell rang.\n"
    source_path.write_text(second_text, encoding="utf-8")
    updated = service.ingest(command)

    assert created.outcome is IngestionOutcome.CREATED
    assert created.revision_number == 1
    assert unchanged.outcome is IngestionOutcome.UNCHANGED
    assert unchanged.document_id == created.document_id
    assert unchanged.revision_id == created.revision_id
    assert updated.outcome is IngestionOutcome.UPDATED
    assert updated.document_id == created.document_id
    assert updated.revision_number == 2
    assert updated.revision_id != created.revision_id

    with db_engine.connect() as connection:
        revisions = connection.execute(
            select(
                DocumentRevision.revision_number,
                DocumentRevision.content_snapshot,
                DocumentRevision.byte_size,
            )
            .where(DocumentRevision.document_id == created.document_id)
            .order_by(DocumentRevision.revision_number)
        ).all()
        paths = connection.execute(
            select(
                DocumentPathHistory.event_kind,
                DocumentPathHistory.valid_to,
                DocumentPathHistory.content_hash_at_event,
            )
            .where(DocumentPathHistory.document_id == created.document_id)
            .order_by(DocumentPathHistory.valid_from)
        ).all()
        run_statuses = connection.execute(
            select(IngestionRun.status).order_by(IngestionRun.started_at)
        ).scalars()
        chunks = connection.execute(
            select(
                DocumentChunk.document_revision_id,
                DocumentChunk.start_offset,
                DocumentChunk.end_offset,
                DocumentChunk.content,
            ).order_by(DocumentChunk.document_revision_id, DocumentChunk.ordinal)
        ).all()
    assert revisions == [
        (1, first_text, len(first_text.encode())),
        (2, second_text, len(second_text.encode())),
    ]
    assert [item.event_kind for item in paths] == ["discovered", "content_changed"]
    assert paths[0].valid_to is not None
    assert paths[1].valid_to is None
    assert list(run_statuses) == ["succeeded", "succeeded", "succeeded"]
    assert len(chunks) == 4
    assert all(
        content[start_offset:end_offset] == chunk_content
        for revision_id, start_offset, end_offset, chunk_content in chunks
        for content in (
            first_text if revision_id == created.revision_id else second_text,
        )
    )


def test_copy_is_explicit_duplicate_and_exact_rename_retains_identity(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    content = "# Shared Text\nSynthetic duplicate fixture.\n"
    original_path = root / "original.md"
    duplicate_path = root / "duplicate.md"
    moved_path = root / "archive" / "moved.md"
    original_path.write_text(content, encoding="utf-8")
    campaign_id = _campaign(db_engine)
    service = _service(db_engine, root)

    original = service.ingest(_command(campaign_id, "original.md"))
    duplicate_path.write_text(content, encoding="utf-8")
    duplicate = service.ingest(_command(campaign_id, "duplicate.md"))
    moved_path.parent.mkdir()
    original_path.rename(moved_path)
    moved = service.ingest(_command(campaign_id, "archive/moved.md"))

    assert duplicate.outcome is IngestionOutcome.DUPLICATE_CREATED
    assert duplicate.document_id != original.document_id
    assert duplicate.duplicate_document_ids == (original.document_id,)
    assert moved.outcome is IngestionOutcome.MOVED
    assert moved.document_id == original.document_id
    assert moved.revision_id == original.revision_id
    assert moved.duplicate_document_ids == (duplicate.document_id,)

    with db_engine.connect() as connection:
        documents = dict(
            connection.execute(
                select(Document.id, Document.source_path).order_by(Document.id)
            ).all()
        )
        original_revision_count = connection.scalar(
            select(func.count())
            .select_from(DocumentRevision)
            .where(DocumentRevision.document_id == original.document_id)
        )
        move_events = connection.execute(
            select(DocumentPathHistory.event_kind)
            .where(DocumentPathHistory.document_id == original.document_id)
            .order_by(DocumentPathHistory.valid_from)
        ).scalars()
    assert documents[original.document_id] == "campaign/archive/moved.md"
    assert documents[duplicate.document_id] == "campaign/duplicate.md"
    assert original_revision_count == 1
    assert list(move_events) == ["discovered", "moved"]


def test_moved_and_edited_source_requires_review_without_mutation(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    old_path = root / "old.md"
    new_path = root / "renamed.md"
    old_path.write_text("# Old\nOriginal synthetic text.\n", encoding="utf-8")
    campaign_id = _campaign(db_engine)
    service = _service(db_engine, root)
    original = service.ingest(_command(campaign_id, "old.md"))
    old_path.rename(new_path)
    new_path.write_text("# Renamed\nSubstantially edited text.\n", encoding="utf-8")

    reviewed = service.ingest(_command(campaign_id, "renamed.md"))

    assert reviewed.status is IngestionStatus.REVIEW_REQUIRED
    assert reviewed.outcome is IngestionOutcome.REVIEW_REQUIRED
    assert reviewed.document_id is None
    assert reviewed.ambiguity is not None
    assert reviewed.ambiguity.reason is (
        ReconciliationAmbiguityReason.POSSIBLE_MOVED_AND_EDITED
    )
    assert reviewed.ambiguity.candidate_document_ids == (original.document_id,)
    with db_engine.connect() as connection:
        document_rows = connection.execute(
            select(Document.id, Document.source_path, Document.retired_at)
        ).all()
        revision_count = connection.scalar(
            select(func.count()).select_from(DocumentRevision)
        )
        run = connection.execute(
            select(IngestionRun.status, IngestionRun.summary).where(
                IngestionRun.id == reviewed.run_id
            )
        ).one()
    assert document_rows == [
        (original.document_id, "campaign/old.md", None),
    ]
    assert revision_count == 1
    assert run.status == "review_required"
    assert run.summary["candidate_document_ids"] == [str(original.document_id)]


def test_missing_reconciliation_retires_explicitly_and_restore_reuses_identity(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    source_path = root / "returning.md"
    first_text = "# Departure\nSynthetic source departs.\n"
    source_path.write_text(first_text, encoding="utf-8")
    campaign_id = _campaign(db_engine)
    service = _service(db_engine, root)
    command = _command(campaign_id, "returning.md")
    original = service.ingest(command)
    source_path.unlink()

    with db_engine.connect() as connection:
        assert (
            connection.scalar(
                select(Document.retired_at).where(Document.id == original.document_id)
            )
            is None
        )
    retired = service.reconcile_missing(_retirement_command(campaign_id))
    second_text = "# Return\nSynthetic source returns changed.\n"
    source_path.write_text(second_text, encoding="utf-8")
    restored = service.ingest(command)

    assert retired.retired_document_ids == (original.document_id,)
    assert restored.outcome is IngestionOutcome.RESTORED
    assert restored.document_id == original.document_id
    assert restored.revision_number == 2
    with db_engine.connect() as connection:
        document = connection.execute(
            select(Document.source_path, Document.retired_at).where(
                Document.id == original.document_id
            )
        ).one()
        events = list(
            connection.execute(
                select(DocumentPathHistory.event_kind)
                .where(DocumentPathHistory.document_id == original.document_id)
                .order_by(DocumentPathHistory.valid_from)
            ).scalars()
        )
        snapshots = list(
            connection.execute(
                select(DocumentRevision.content_snapshot)
                .where(DocumentRevision.document_id == original.document_id)
                .order_by(DocumentRevision.revision_number)
            ).scalars()
        )
    assert document == ("campaign/returning.md", None)
    assert events == ["discovered", "retired", "restored"]
    assert snapshots == [first_text, second_text]


def test_multiple_missing_exact_duplicates_require_review(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    content = "# Duplicate\nExact synthetic duplicate.\n"
    first_path = root / "first.md"
    second_path = root / "second.md"
    incoming_path = root / "incoming.md"
    first_path.write_text(content, encoding="utf-8")
    second_path.write_text(content, encoding="utf-8")
    campaign_id = _campaign(db_engine)
    service = _service(db_engine, root)
    first = service.ingest(_command(campaign_id, "first.md"))
    second = service.ingest(_command(campaign_id, "second.md"))
    first_path.unlink()
    second_path.unlink()
    incoming_path.write_text(content, encoding="utf-8")

    reviewed = service.ingest(_command(campaign_id, "incoming.md"))

    assert reviewed.outcome is IngestionOutcome.REVIEW_REQUIRED
    assert reviewed.ambiguity is not None
    assert reviewed.ambiguity.reason is (
        ReconciliationAmbiguityReason.MULTIPLE_EXACT_MOVE_CANDIDATES
    )
    assert set(reviewed.ambiguity.candidate_document_ids) == {
        first.document_id,
        second.document_id,
    }
    with db_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(Document)) == 2


def test_missing_reconciliation_refuses_symlink_replacement_without_retiring(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    source_path = root / "protected.md"
    outside_path = tmp_path / "outside.md"
    source_path.write_text("# Protected\nSynthetic source.\n", encoding="utf-8")
    outside_path.write_text("# Outside\nNot allowlisted.\n", encoding="utf-8")
    campaign_id = _campaign(db_engine)
    service = _service(db_engine, root)
    created = service.ingest(_command(campaign_id, "protected.md"))
    source_path.unlink()
    source_path.symlink_to(outside_path)

    with pytest.raises(InvalidInputError, match="symbolic links"):
        service.reconcile_missing(_retirement_command(campaign_id))

    with db_engine.connect() as connection:
        retired_at = connection.scalar(
            select(Document.retired_at).where(Document.id == created.document_id)
        )
        event_count = connection.scalar(
            select(func.count())
            .select_from(DocumentPathHistory)
            .where(DocumentPathHistory.document_id == created.document_id)
        )
        statuses = list(
            connection.execute(
                select(IngestionRun.status).order_by(IngestionRun.started_at)
            ).scalars()
        )
    assert retired_at is None
    assert event_count == 1
    assert statuses == ["succeeded", "failed"]


def test_global_rules_source_uses_rules_scope_without_campaign_ownership(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    root = tmp_path / "rules"
    root.mkdir()
    (root / "synthetic-rule.md").write_text(
        "# Synthetic Rule\nA wholly invented test mechanic.\n",
        encoding="utf-8",
    )
    service = LibraryIngestionService(
        db_engine,
        LocalSourceReader({"rules": root}),
    )
    result = service.ingest(
        IngestSource(
            scope=SourceScope(campaign_id=None, corpus=CorpusKind.RULES),
            locator=SourceLocator(
                root_label="rules",
                relative_path="synthetic-rule.md",
            ),
            classification=RevisionClassification(
                corpus=CorpusKind.RULES,
                document_type=DocumentType.RULES_REFERENCE,
                authority_class=AuthorityClass.OFFICIAL_RULES,
                ruleset=Ruleset.DND_5E_2024,
                visibility=VisibilityLabel(policy=SourceVisibility.DM_ONLY),
            ),
            title="Synthetic Rule",
        )
    )

    assert result.outcome is IngestionOutcome.CREATED
    with db_engine.connect() as connection:
        row = connection.execute(
            select(
                Document.campaign_id,
                Document.corpus,
                DocumentRevision.ruleset,
            ).join(
                DocumentRevision,
                DocumentRevision.document_id == Document.id,
            )
        ).one()
    assert row == (None, "rules", "dnd_5e_2024")


def test_disallowed_sources_fail_runs_without_creating_documents(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("synthetic outside", encoding="utf-8")
    (root / "escape.md").symlink_to(outside)
    (root / "invalid.md").write_bytes(b"\xff\xfeinvalid")
    (root / "directory").mkdir()
    campaign_id = _campaign(db_engine)
    service = _service(db_engine, root)

    for relative_path in ("escape.md", "invalid.md", "directory"):
        with pytest.raises(InvalidInputError):
            service.ingest(_command(campaign_id, relative_path))
    with pytest.raises(InvalidInputError, match="not configured"):
        service.ingest(
            IngestSource(
                scope=SourceScope(
                    campaign_id=campaign_id,
                    corpus=CorpusKind.CAMPAIGN,
                ),
                locator=SourceLocator(root_label="other", relative_path="source.md"),
                classification=_command(campaign_id, "unused.md").classification,
                title="Unknown Root",
            )
        )
    with pytest.raises(ValidationError):
        SourceLocator(root_label="campaign", relative_path="../outside.md")
    with pytest.raises(ValidationError):
        SourceLocator(root_label="campaign", relative_path=str(outside))

    with db_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(Document)) == 0
        statuses = list(
            connection.execute(
                select(IngestionRun.status).order_by(IngestionRun.started_at)
            ).scalars()
        )
        summaries = list(
            connection.execute(
                select(IngestionRun.summary).order_by(IngestionRun.started_at)
            ).scalars()
        )
    assert statuses == ["failed", "failed", "failed", "failed"]
    assert all(item["outcome"] == "failed" for item in summaries)
