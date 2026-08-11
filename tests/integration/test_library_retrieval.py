"""PostgreSQL tests for filtered lexical Library retrieval."""

import uuid
from pathlib import Path

import pytest
from sqlalchemy import Engine

from dm_assistant.adapters.sources import LocalSourceReader
from dm_assistant.db import Campaign, build_session_factory, transactional_session
from dm_assistant.modules.library import (
    AuthorityClass,
    CorpusKind,
    DocumentType,
    IngestSource,
    LexicalSearchQuery,
    LibraryIngestionService,
    LibraryLexicalSearchService,
    RevisionClassification,
    Ruleset,
    SourceLocator,
    SourceScope,
    SourceVisibility,
    VisibilityLabel,
)

pytestmark = pytest.mark.integration


def _campaign(engine: Engine, name: str) -> uuid.UUID:
    campaign_id = uuid.uuid4()
    with transactional_session(build_session_factory(engine)) as session:
        session.add(Campaign(id=campaign_id, name=name))
    return campaign_id


def _service(engine: Engine, root: Path) -> LibraryIngestionService:
    return LibraryIngestionService(
        engine,
        LocalSourceReader({"campaign": root}, maximum_bytes=64 * 1024),
    )


def _ingest(
    service: LibraryIngestionService,
    campaign_id: uuid.UUID,
    path: str,
    *,
    corpus: CorpusKind = CorpusKind.CAMPAIGN,
    authority: AuthorityClass = AuthorityClass.REFERENCE,
    document_type: DocumentType = DocumentType.REFERENCE_LORE,
    visibility: SourceVisibility = SourceVisibility.DM_ONLY,
    ruleset: Ruleset | None = None,
):
    return service.ingest(
        IngestSource(
            scope=SourceScope(
                campaign_id=campaign_id if corpus is CorpusKind.CAMPAIGN else None,
                corpus=corpus,
            ),
            locator=SourceLocator(root_label="campaign", relative_path=path),
            classification=RevisionClassification(
                corpus=corpus,
                document_type=document_type,
                authority_class=authority,
                ruleset=ruleset,
                visibility=VisibilityLabel(policy=visibility),
            ),
            title=path,
            source_metadata={"fixture_kind": "synthetic_markdown"},
        )
    )


def test_lexical_search_filters_scope_visibility_and_preparation(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "facts.md").write_text(
        "# Starfall Amulet\nThe party recovered the amulet beneath the old bridge.\n",
        encoding="utf-8",
    )
    (root / "secret.md").write_text(
        "# Hidden Cache\nThe cache contains the Starfall Amulet.\n",
        encoding="utf-8",
    )
    (root / "plan.md").write_text(
        "# Future Plan\nThe party will recover the Starfall Amulet.\n",
        encoding="utf-8",
    )
    (root / "rules.md").write_text(
        "# Starfall Rule\nA starfall effect uses a reaction.\n",
        encoding="utf-8",
    )
    campaign_id = _campaign(db_engine, "Synthetic Retrieval Campaign")
    other_campaign_id = _campaign(db_engine, "Other Retrieval Campaign")
    service = _service(db_engine, root)
    facts = _ingest(service, campaign_id, "facts.md")
    _ingest(
        service,
        campaign_id,
        "secret.md",
        visibility=SourceVisibility.PUBLIC,
    )
    _ingest(
        service,
        campaign_id,
        "plan.md",
        authority=AuthorityClass.PREPARATION,
        document_type=DocumentType.PLAN_OR_ADVENTURE,
    )
    _ingest(
        service,
        campaign_id,
        "rules.md",
        corpus=CorpusKind.RULES,
        authority=AuthorityClass.OFFICIAL_RULES,
        document_type=DocumentType.RULES_REFERENCE,
        ruleset=Ruleset.DND_5E_2014,
    )
    (root / "other.md").write_text(
        "# Other Campaign\nThe Starfall Amulet is elsewhere.\n",
        encoding="utf-8",
    )
    _ingest(service, other_campaign_id, "other.md")

    from dm_assistant.modules.library import CorpusSnapshotService

    snapshots = CorpusSnapshotService(db_engine)
    snapshots.build_candidate(
        SourceScope(campaign_id=campaign_id, corpus=CorpusKind.CAMPAIGN)
    )
    # Re-ingest the rules source under its global rules scope before snapshotting.
    snapshots.build_candidate(SourceScope(campaign_id=None, corpus=CorpusKind.RULES))
    # Snapshot activation is intentionally explicit for reproducible retrieval.
    campaign_candidate = snapshots.build_candidate(
        SourceScope(campaign_id=campaign_id, corpus=CorpusKind.CAMPAIGN)
    )
    snapshots.activate(
        campaign_candidate,
        SourceScope(campaign_id=campaign_id, corpus=CorpusKind.CAMPAIGN),
    )
    rules_candidate = snapshots.build_candidate(
        SourceScope(campaign_id=None, corpus=CorpusKind.RULES)
    )
    snapshots.activate(rules_candidate, SourceScope(campaign_id=None, corpus=CorpusKind.RULES))

    search = LibraryLexicalSearchService(db_engine)
    campaign_scope = SourceScope(campaign_id=campaign_id, corpus=CorpusKind.CAMPAIGN)
    results = search.search(
        LexicalSearchQuery(
            scope=campaign_scope,
            query="Starfall Amulet",
            visible_policies=(SourceVisibility.DM_ONLY,),
        )
    )
    assert [item.document_id for item in results] == [facts.document_id]
    assert results[0].citation_id == f"chunk:{results[0].chunk_id}"
    assert "Starfall Amulet" in results[0].snippet

    preparation_results = search.search(
        LexicalSearchQuery(
            scope=campaign_scope,
            query="Starfall Amulet",
            include_preparation=True,
        )
    )
    assert len(preparation_results) == 3
    assert all(len(item.snippet) <= 320 for item in preparation_results)

    rules_results = search.search(
        LexicalSearchQuery(
            scope=SourceScope(campaign_id=None, corpus=CorpusKind.RULES),
            query="starfall reaction",
            rulesets=(Ruleset.DND_5E_2014,),
        )
    )
    assert len(rules_results) == 1
    assert rules_results[0].document_id != facts.document_id

    other_results = search.search(
        LexicalSearchQuery(
            scope=SourceScope(campaign_id=other_campaign_id, corpus=CorpusKind.CAMPAIGN),
            query="Starfall Amulet",
        )
    )
    assert len(other_results) == 0
