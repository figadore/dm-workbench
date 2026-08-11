"""PostgreSQL tests for atomic corpus snapshot construction and activation."""

import uuid
from pathlib import Path

import pytest
from sqlalchemy import Engine, select

from dm_assistant.adapters.sources import LocalSourceReader
from dm_assistant.db import Campaign, build_session_factory, transactional_session
from dm_assistant.errors import InvalidInputError
from dm_assistant.modules.library import (
    AuthorityClass,
    CorpusKind,
    CorpusSnapshotService,
    DocumentType,
    IngestSource,
    LibraryIngestionService,
    RevisionClassification,
    SourceLocator,
    SourceScope,
    SourceVisibility,
    VisibilityLabel,
)
from dm_assistant.modules.library.models import (
    CorpusSnapshot,
    CorpusSnapshotDocument,
)

pytestmark = pytest.mark.integration


def _campaign(engine: Engine, name: str) -> uuid.UUID:
    campaign_id = uuid.uuid4()
    factory = build_session_factory(engine)
    with transactional_session(factory) as session:
        session.add(Campaign(id=campaign_id, name=name))
    return campaign_id


def _ingest_service(engine: Engine, root: Path) -> LibraryIngestionService:
    return LibraryIngestionService(
        engine,
        LocalSourceReader({"campaign": root}, maximum_bytes=64 * 1024),
    )


def _command(campaign_id: uuid.UUID, relative_path: str) -> IngestSource:
    return IngestSource(
        scope=SourceScope(campaign_id=campaign_id, corpus=CorpusKind.CAMPAIGN),
        locator=SourceLocator(root_label="campaign", relative_path=relative_path),
        classification=RevisionClassification(
            corpus=CorpusKind.CAMPAIGN,
            document_type=DocumentType.REFERENCE_LORE,
            authority_class=AuthorityClass.REFERENCE,
            ruleset=None,
            visibility=VisibilityLabel(policy=SourceVisibility.DM_ONLY),
        ),
        title="Synthetic Snapshot Source",
        source_metadata={"fixture_kind": "synthetic_markdown"},
    )


def test_snapshot_pins_current_heads_and_replaces_active_snapshot(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    source_path = root / "lore.md"
    source_path.write_text("# First\nA synthetic fact.\n", encoding="utf-8")
    campaign_id = _campaign(db_engine, "Synthetic Snapshot Campaign")
    scope = SourceScope(campaign_id=campaign_id, corpus=CorpusKind.CAMPAIGN)
    ingestion = _ingest_service(db_engine, root)

    first = ingestion.ingest(_command(campaign_id, "lore.md"))
    snapshots = CorpusSnapshotService(db_engine)
    candidate_id = snapshots.build_candidate(scope)

    with db_engine.connect() as connection:
        candidate_state = connection.scalar(
            select(CorpusSnapshot.state).where(CorpusSnapshot.id == candidate_id)
        )
        memberships = connection.execute(
            select(
                CorpusSnapshotDocument.document_id,
                CorpusSnapshotDocument.document_revision_id,
            ).where(CorpusSnapshotDocument.corpus_snapshot_id == candidate_id)
        ).all()
    assert candidate_state == "candidate"
    assert memberships == [(first.document_id, first.revision_id)]

    assert snapshots.activate(candidate_id, scope) == candidate_id
    source_path.write_text(
        "# First\nA synthetic fact.\n# Second\nAnother fact.\n",
        encoding="utf-8",
    )
    second = ingestion.ingest(_command(campaign_id, "lore.md"))
    next_candidate_id = snapshots.build_candidate(scope)
    snapshots.activate(next_candidate_id, scope)

    with db_engine.connect() as connection:
        states = connection.execute(
            select(CorpusSnapshot.id, CorpusSnapshot.state).order_by(
                CorpusSnapshot.created_at
            )
        ).all()
        next_memberships = connection.execute(
            select(CorpusSnapshotDocument.document_revision_id).where(
                CorpusSnapshotDocument.corpus_snapshot_id == next_candidate_id
            )
        ).all()
    assert states == [(candidate_id, "superseded"), (next_candidate_id, "active")]
    assert next_memberships == [(second.revision_id,)]


def test_snapshot_activation_rejects_wrong_scope_without_changing_active_snapshot(
    db_engine: Engine,
) -> None:
    campaign_id = _campaign(db_engine, "Synthetic Snapshot Scope Campaign")
    other_campaign_id = _campaign(db_engine, "Other Synthetic Snapshot Campaign")
    snapshots = CorpusSnapshotService(db_engine)
    scope = SourceScope(campaign_id=campaign_id, corpus=CorpusKind.CAMPAIGN)
    other_scope = SourceScope(
        campaign_id=other_campaign_id,
        corpus=CorpusKind.CAMPAIGN,
    )
    candidate_id = snapshots.build_candidate(scope)

    with pytest.raises(InvalidInputError):
        snapshots.activate(candidate_id, other_scope)

    with db_engine.connect() as connection:
        state = connection.scalar(
            select(CorpusSnapshot.state).where(CorpusSnapshot.id == candidate_id)
        )
    assert state == "candidate"
