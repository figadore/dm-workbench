"""PostgreSQL tests for filtered lexical Library retrieval."""

import uuid
from pathlib import Path

import pytest
from sqlalchemy import Engine, insert, text
from sqlalchemy.exc import DBAPIError

from dm_assistant.adapters.embeddings import (
    DeterministicFakeEmbeddingProvider,
    DistanceMetric,
    EmbeddingProfileSpec,
    EmbeddingRuntimeKind,
)
from dm_assistant.adapters.sources import LocalSourceReader
from dm_assistant.db import Campaign, build_session_factory, transactional_session
from dm_assistant.modules.library import (
    AuthorityClass,
    CorpusKind,
    DocumentType,
    IngestSource,
    LexicalSearchQuery,
    HybridRetrievalMode,
    HybridSearchQuery,
    LibraryHybridSearchService,
    LibraryVectorSearchService,
    LibraryIngestionService,
    LibraryLexicalSearchService,
    LibraryRetrievalAuditService,
    RevisionClassification,
    Ruleset,
    SourceLocator,
    SourceScope,
    SourceVisibility,
    VectorRetrievalMode,
    VectorSearchQuery,
    VisibilityLabel,
)
from dm_assistant.modules.library.embedding_runs import EmbeddingRunService
from dm_assistant.modules.library.models import EmbeddingProfile, RetrievalRun

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


def test_vector_search_requires_completed_pinned_run_and_preserves_scope_filters(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "fact.md").write_text(
        "# Moonwell Key\nThe party recovered the Moonwell Key.\n",
        encoding="utf-8",
    )
    (root / "secret.md").write_text(
        "# Moonwell Secret\nThe Moonwell Key opens the hidden cache.\n",
        encoding="utf-8",
    )
    (root / "plan.md").write_text(
        "# Moonwell Plan\nThe party will recover the Moonwell Key.\n",
        encoding="utf-8",
    )
    campaign_id = _campaign(db_engine, "Synthetic Vector Retrieval Campaign")
    service = _service(db_engine, root)
    fact = _ingest(service, campaign_id, "fact.md")
    _ingest(service, campaign_id, "secret.md", visibility=SourceVisibility.PUBLIC)
    _ingest(
        service,
        campaign_id,
        "plan.md",
        authority=AuthorityClass.PREPARATION,
        document_type=DocumentType.PLAN_OR_ADVENTURE,
    )
    from dm_assistant.modules.library import CorpusSnapshotService

    scope = SourceScope(campaign_id=campaign_id, corpus=CorpusKind.CAMPAIGN)
    snapshots = CorpusSnapshotService(db_engine)
    snapshot_id = snapshots.build_candidate(scope)
    snapshots.activate(snapshot_id, scope)
    profile = EmbeddingProfileSpec(
        runtime_kind=EmbeddingRuntimeKind.LOCAL,
        provider="synthetic",
        model="synthetic-embedding",
        model_revision="synthetic-v1",
        license="synthetic-test-only",
        dimensions=8,
        distance_metric=DistanceMetric.COSINE,
        normalization_version="l2-v1",
        preprocessing_version="plain-text-v1",
        config_hash="f" * 64,
        enabled=True,
    )
    profile_id = uuid.uuid4()
    with transactional_session(build_session_factory(db_engine)) as session:
        session.execute(insert(EmbeddingProfile).values(id=profile_id, **profile.model_dump()))
    provider = DeterministicFakeEmbeddingProvider(profile)
    embedding_runs = EmbeddingRunService(db_engine)
    run = embedding_runs.create_run(
        corpus_snapshot_id=snapshot_id,
        embedding_profile_id=profile_id,
        batch_size=10,
        max_attempts=2,
    )
    completed_run = embedding_runs.execute(run.id, provider)
    assert completed_run.status == "succeeded"

    lexical = LibraryLexicalSearchService(db_engine)
    vector = LibraryVectorSearchService(db_engine, lexical)
    request = VectorSearchQuery(
        lexical=LexicalSearchQuery(
            scope=scope,
            snapshot_id=snapshot_id,
            query="Moonwell Key",
            visible_policies=(SourceVisibility.DM_ONLY,),
        ),
        embedding_run_id=run.id,
    )
    vector_result = vector.search(request, provider)

    assert vector_result.mode is VectorRetrievalMode.VECTOR
    assert [result.document_id for result in vector_result.results] == [fact.document_id]
    assert vector_result.results[0].citation_id == (
        f"chunk:{vector_result.results[0].chunk_id}"
    )
    assert "Moonwell Key" in vector_result.results[0].snippet

    fallback_result = vector.search(
        request.model_copy(update={"embedding_run_id": uuid.uuid4()}),
        provider,
    )
    assert fallback_result.mode is VectorRetrievalMode.LEXICAL_FALLBACK
    assert [result.document_id for result in fallback_result.results] == [fact.document_id]

    hybrid = LibraryHybridSearchService(db_engine, lexical, vector)
    hybrid_request = HybridSearchQuery(
        lexical=request.lexical,
        embedding_run_id=run.id,
        neighboring_chunks_each_side=1,
    )
    hybrid_result = hybrid.search(hybrid_request, provider)

    assert hybrid_result.mode is HybridRetrievalMode.HYBRID
    assert [result.document_id for result in hybrid_result.results] == [fact.document_id]
    assert hybrid_result.results[0].neighboring_chunks == ()

    hybrid_fallback = hybrid.search(
        hybrid_request.model_copy(update={"embedding_run_id": uuid.uuid4()}),
        provider,
    )
    assert hybrid_fallback.mode is HybridRetrievalMode.LEXICAL_FALLBACK
    assert [result.document_id for result in hybrid_fallback.results] == [fact.document_id]

    audit = LibraryRetrievalAuditService(db_engine, lexical, vector, hybrid)
    audited = audit.search(hybrid_request, provider)

    assert audited.mode.value == "hybrid"
    assert audited.embedding_run_id == run.id
    assert audited.query_sha256 != request.lexical.query
    assert audited.selected_citation_ids == (
        f"chunk:{hybrid_result.results[0].chunk_id}",
    )
    assert audited.candidates[0].citation_id == audited.selected_citation_ids[0]
    with db_engine.begin() as connection:
        stored = connection.get(RetrievalRun, audited.id)
        candidate_keys = connection.scalar(
            text(
                "SELECT array_agg(key ORDER BY key) "
                "FROM retrieval_run, jsonb_object_keys(candidates->0) AS key "
                "WHERE id = :id"
            ),
            {"id": audited.id},
        )
    assert stored is not None
    assert stored.resolved_scope["corpus_snapshot_id"] == str(snapshot_id)
    assert stored.query_sha256 not in {request.lexical.query, "Moonwell Key"}
    assert candidate_keys == ["citation_id", "lexical_rank", "score", "vector_rank"]

    with pytest.raises(DBAPIError, match="retrieval runs are immutable"):
        with db_engine.begin() as connection:
            connection.execute(
                text("UPDATE retrieval_run SET mode = 'lexical_fallback' WHERE id = :id"),
                {"id": audited.id},
            )

    with pytest.raises(DBAPIError, match="candidate record is invalid"):
        with db_engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO retrieval_run "
                    "(id, corpus_snapshot_id, embedding_run_id, mode, query_sha256, "
                    "retrieval_versions, resolved_scope, candidates, "
                    "selected_citation_ids, duration_milliseconds) "
                    "VALUES (:id, :snapshot_id, NULL, 'lexical_fallback', :query_hash, "
                    "CAST(:versions AS jsonb), CAST(:scope AS jsonb), "
                    "CAST(:candidates AS jsonb), CAST(:selected AS jsonb), 1.0)"
                ),
                {
                    "id": uuid.uuid4(),
                    "snapshot_id": snapshot_id,
                    "query_hash": "a" * 64,
                    "versions": '{"lexical":"postgresql-fts-v1"}',
                    "scope": (
                        '{"campaign_id":"'
                        + str(campaign_id)
                        + '","corpus":"campaign","corpus_snapshot_id":"'
                        + str(snapshot_id)
                        + '","authority_classes":[],"visible_policies":["dm_only"],'
                        '"rulesets":[],"include_preparation":false,'
                        '"limit":10,"snippet_chars":320}'
                    ),
                    "candidates": (
                        '[{"citation_id":"chunk:'
                        + str(uuid.uuid4())
                        + '","score":1.0,"snippet":"forbidden source body"}]'
                    ),
                    "selected": '["chunk:' + str(uuid.uuid4()) + '"]',
                },
            )

    fallback_audit = audit.search(
        hybrid_request.model_copy(update={"embedding_run_id": uuid.uuid4()}),
        provider,
    )
    assert fallback_audit.mode.value == "lexical_fallback"
    assert fallback_audit.embedding_run_id is None
