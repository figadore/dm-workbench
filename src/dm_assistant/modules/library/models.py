"""SQLAlchemy schema for immutable Library sources and corpus snapshots."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import UserDefinedType

from dm_assistant.db.base import Base

_CORPORA = "'campaign','rules'"
_DOCUMENT_TYPES = (
    "'canon_note','raw_session_record','plan_or_adventure','reference_lore',"
    "'player_handout','character_sheet','important_item_record',"
    "'creature_or_bestiary_record','dungeon_or_encounter_brief',"
    "'house_rule_or_ruling','rules_reference'"
)
_AUTHORITIES = (
    "'canonical_claim','raw_record','preparation','reference','official_rules',"
    "'user_authored_rules'"
)
_RULESETS = "'dnd_5e_2014','dnd_5e_2024','system_agnostic','other'"
_VISIBILITIES = "'dm_only','all_campaign_players','explicit_audience','public'"
_PATH_EVENTS = "'discovered','moved','content_changed','restored','retired'"
_INGESTION_STATUSES = "'running','succeeded','failed','review_required'"
_SNAPSHOT_STATES = "'candidate','active','superseded'"
_EMBEDDING_RUN_STATUSES = "'running','succeeded','failed','cancelled'"
_EMBEDDING_ITEM_STATUSES = (
    "'pending','processing','succeeded','skipped','retryable_failed','failed',"
    "'cancelled'"
)
_RETRIEVAL_RUN_MODES = "'hybrid','lexical_fallback'"
_SAFE_PATH_CHECK = (
    "length(source_path) > 0 AND source_path !~ '(^/|(^|/)\\.\\.(/|$)|\\\\)'"
)


class Vector(UserDefinedType[Any]):
    """PostgreSQL pgvector type without coupling the application to a provider SDK."""

    cache_ok = True

    def get_col_spec(self, **kwargs: Any) -> str:
        return "vector"


class Document(Base):
    """Stable logical identity independent from mutable filesystem location."""

    __tablename__ = "document"
    __table_args__ = (
        UniqueConstraint(
            "campaign_id",
            "corpus",
            "logical_key",
            name="uq_document_owner_corpus_logical_key",
            postgresql_nulls_not_distinct=True,
        ),
        UniqueConstraint(
            "campaign_id",
            "corpus",
            "id",
            name="uq_document_owner_corpus_id",
            postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint(f"corpus IN ({_CORPORA})", name="corpus_allowed"),
        CheckConstraint(
            "corpus <> 'campaign' OR campaign_id IS NOT NULL",
            name="campaign_corpus_has_owner",
        ),
        CheckConstraint(_SAFE_PATH_CHECK, name="source_path_safe_relative"),
        CheckConstraint("length(btrim(logical_key)) > 0", name="logical_key_not_blank"),
        Index(
            "uq_document_active_source_path",
            "campaign_id",
            "corpus",
            "source_path",
            unique=True,
            postgresql_where=text("retired_at IS NULL"),
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaign.id", ondelete="RESTRICT"),
    )
    corpus: Mapped[str] = mapped_column(String(20), nullable=False)
    logical_key: Mapped[str] = mapped_column(String(200), nullable=False)
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DocumentPathHistory(Base):
    """Immutable locator history except for closing the current interval."""

    __tablename__ = "document_path_history"
    __table_args__ = (
        ForeignKeyConstraint(
            ("campaign_id", "corpus", "document_id"),
            ("document.campaign_id", "document.corpus", "document.id"),
            name="fk_document_path_owner_document",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "document_id", "source_path", "valid_from", name="uq_document_path_event"
        ),
        CheckConstraint(f"corpus IN ({_CORPORA})", name="corpus_allowed"),
        CheckConstraint(_SAFE_PATH_CHECK, name="source_path_safe_relative"),
        CheckConstraint(f"event_kind IN ({_PATH_EVENTS})", name="event_kind_allowed"),
        CheckConstraint(
            "content_hash_at_event ~ '^[0-9a-f]{64}$'",
            name="content_hash_valid",
        ),
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from", name="valid_interval"
        ),
        Index(
            "uq_document_path_current",
            "document_id",
            unique=True,
            postgresql_where=text("valid_to IS NULL"),
        ),
        Index(
            "ix_document_path_scope_content_hash",
            "campaign_id",
            "corpus",
            "content_hash_at_event",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    corpus: Mapped[str] = mapped_column(String(20), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    event_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    content_hash_at_event: Mapped[str] = mapped_column(String(64), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IngestionRun(Base):
    """Durable source discovery/parse run metadata without source bodies."""

    __tablename__ = "ingestion_run"
    __table_args__ = (
        UniqueConstraint(
            "campaign_id",
            "corpus",
            "id",
            name="uq_ingestion_run_owner_corpus_id",
            postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint(f"corpus IN ({_CORPORA})", name="corpus_allowed"),
        CheckConstraint(
            "corpus <> 'campaign' OR campaign_id IS NOT NULL",
            name="campaign_corpus_has_owner",
        ),
        CheckConstraint(f"status IN ({_INGESTION_STATUSES})", name="status_allowed"),
        CheckConstraint(
            "(status = 'running' AND finished_at IS NULL) OR "
            "(status IN ('succeeded','failed','review_required') AND "
            "finished_at IS NOT NULL)",
            name="status_finished_consistent",
        ),
        CheckConstraint(
            "finished_at IS NULL OR finished_at >= started_at",
            name="finished_after_started",
        ),
        CheckConstraint(
            "jsonb_typeof(configuration) = 'object' AND "
            "jsonb_typeof(summary) = 'object'",
            name="json_objects",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaign.id", ondelete="RESTRICT")
    )
    corpus: Mapped[str] = mapped_column(String(20), nullable=False)
    source_root_label: Mapped[str] = mapped_column(String(200), nullable=False)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    parser_version: Mapped[str] = mapped_column(String(80), nullable=False)
    chunker_version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DocumentRevision(Base):
    """Immutable exact source snapshot and revision-level classification."""

    __tablename__ = "document_revision"
    __table_args__ = (
        ForeignKeyConstraint(
            ("campaign_id", "corpus", "document_id"),
            ("document.campaign_id", "document.corpus", "document.id"),
            name="fk_document_revision_owner_document",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "campaign_id",
            "corpus",
            "id",
            name="uq_document_revision_owner_corpus_id",
            postgresql_nulls_not_distinct=True,
        ),
        UniqueConstraint(
            "document_id", "revision_number", name="uq_document_revision_number"
        ),
        UniqueConstraint(
            "document_id", "content_hash", name="uq_document_revision_content_hash"
        ),
        Index(
            "ix_document_revision_scope_content_hash",
            "campaign_id",
            "corpus",
            "content_hash",
        ),
        CheckConstraint(f"corpus IN ({_CORPORA})", name="corpus_allowed"),
        CheckConstraint("revision_number > 0", name="revision_number_positive"),
        CheckConstraint("content_hash ~ '^[0-9a-f]{64}$'", name="content_hash_valid"),
        CheckConstraint("byte_size >= 0", name="byte_size_nonnegative"),
        CheckConstraint(
            "octet_length(convert_to(content_snapshot, 'UTF8')) = byte_size",
            name="byte_size_matches_utf8_content",
        ),
        CheckConstraint(_SAFE_PATH_CHECK, name="source_path_safe_relative"),
        CheckConstraint(
            f"document_type IN ({_DOCUMENT_TYPES})", name="document_type_allowed"
        ),
        CheckConstraint(
            f"authority_class IN ({_AUTHORITIES})", name="authority_allowed"
        ),
        CheckConstraint(
            f"ruleset IS NULL OR ruleset IN ({_RULESETS})", name="ruleset_allowed"
        ),
        CheckConstraint(
            f"visibility_policy IN ({_VISIBILITIES})", name="visibility_allowed"
        ),
        CheckConstraint(
            "(visibility_policy = 'explicit_audience' AND "
            "jsonb_typeof(visibility_audience) = 'array' AND "
            "jsonb_array_length(visibility_audience) > 0) OR "
            "(visibility_policy <> 'explicit_audience' AND "
            "visibility_audience = '[]'::jsonb)",
            name="visibility_audience_consistent",
        ),
        CheckConstraint(
            "corpus <> 'rules' OR ruleset IS NOT NULL",
            name="rules_corpus_has_ruleset",
        ),
        CheckConstraint(
            "authority_class NOT IN ('canonical_claim','raw_record','preparation') "
            "OR corpus = 'campaign'",
            name="campaign_authority_scope",
        ),
        CheckConstraint(
            "authority_class <> 'official_rules' OR "
            "(corpus = 'rules' AND visibility_policy = 'dm_only')",
            name="official_rules_safe",
        ),
        CheckConstraint(
            "authority_class <> 'user_authored_rules' OR ruleset IS NOT NULL",
            name="user_rules_has_ruleset",
        ),
        CheckConstraint(
            "document_type NOT IN ('plan_or_adventure',"
            "'dungeon_or_encounter_brief') OR "
            "(corpus = 'campaign' AND authority_class = 'preparation' AND "
            "visibility_policy = 'dm_only')",
            name="preparation_classification_safe",
        ),
        CheckConstraint(
            "document_type <> 'canon_note' OR authority_class = 'canonical_claim'",
            name="canon_note_authority",
        ),
        CheckConstraint(
            "document_type <> 'raw_session_record' OR authority_class = 'raw_record'",
            name="raw_record_authority",
        ),
        CheckConstraint(
            "document_type <> 'rules_reference' OR corpus = 'rules'",
            name="rules_reference_corpus",
        ),
        CheckConstraint(
            "document_type NOT IN "
            "('creature_or_bestiary_record','house_rule_or_ruling') "
            "OR ruleset IS NOT NULL",
            name="mechanics_record_has_ruleset",
        ),
        CheckConstraint(
            "document_type <> 'house_rule_or_ruling' OR "
            "authority_class = 'user_authored_rules'",
            name="house_rule_authority",
        ),
        CheckConstraint(
            "jsonb_typeof(source_metadata) = 'object'",
            name="source_metadata_object",
        ),
        CheckConstraint("length(btrim(title)) > 0", name="title_not_blank"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    corpus: Mapped[str] = mapped_column(String(20), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document.id", ondelete="RESTRICT"),
        nullable=False,
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    authority_class: Mapped[str] = mapped_column(String(40), nullable=False)
    ruleset: Mapped[str | None] = mapped_column(String(40))
    visibility_policy: Mapped[str] = mapped_column(String(40), nullable=False)
    visibility_audience: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    source_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    parser_version: Mapped[str] = mapped_column(String(80), nullable=False)
    ingestion_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ingestion_run.id", ondelete="RESTRICT"),
        nullable=False,
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DocumentChunk(Base):
    """Immutable exact source span with lexical search projection."""

    __tablename__ = "document_chunk"
    __table_args__ = (
        UniqueConstraint(
            "document_revision_id", "ordinal", name="uq_document_chunk_ordinal"
        ),
        CheckConstraint(f"corpus IN ({_CORPORA})", name="corpus_allowed"),
        CheckConstraint("ordinal >= 0", name="ordinal_nonnegative"),
        CheckConstraint(
            "start_offset >= 0 AND end_offset > start_offset",
            name="offsets_valid",
        ),
        CheckConstraint("content_hash ~ '^[0-9a-f]{64}$'", name="content_hash_valid"),
        CheckConstraint(
            "jsonb_typeof(heading_path) = 'array' AND "
            "jsonb_typeof(metadata) = 'object'",
            name="chunk_json_shapes",
        ),
        CheckConstraint(
            "(page_start IS NULL AND page_end IS NULL) OR "
            "(page_start >= 1 AND page_end >= page_start)",
            name="page_range_valid",
        ),
        CheckConstraint(
            "fts_config IN ('english','simple')", name="fts_config_allowed"
        ),
        Index(
            "ix_document_chunk_search_vector",
            "search_vector",
            postgresql_using="gin",
        ),
        Index(
            "ix_document_chunk_scope_visibility",
            "campaign_id",
            "corpus",
            "visibility_policy",
            "ruleset",
        ),
        CheckConstraint(
            f"authority_class IN ({_AUTHORITIES})", name="authority_allowed"
        ),
        CheckConstraint(
            f"ruleset IS NULL OR ruleset IN ({_RULESETS})", name="ruleset_allowed"
        ),
        CheckConstraint(
            f"visibility_policy IN ({_VISIBILITIES})", name="visibility_allowed"
        ),
        CheckConstraint(
            "(visibility_policy = 'explicit_audience' AND "
            "jsonb_typeof(visibility_audience) = 'array' AND "
            "jsonb_array_length(visibility_audience) > 0) OR "
            "(visibility_policy <> 'explicit_audience' AND "
            "visibility_audience = '[]'::jsonb)",
            name="visibility_audience_consistent",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    corpus: Mapped[str] = mapped_column(String(20), nullable=False)
    document_revision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_revision.id", ondelete="RESTRICT"),
        nullable=False,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    heading_path: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    search_vector: Mapped[Any] = mapped_column(TSVECTOR, nullable=False)
    fts_config: Mapped[str] = mapped_column(String(50), nullable=False)
    chunker_version: Mapped[str] = mapped_column(String(80), nullable=False)
    authority_class: Mapped[str] = mapped_column(String(40), nullable=False)
    ruleset: Mapped[str | None] = mapped_column(String(40))
    visibility_policy: Mapped[str] = mapped_column(String(40), nullable=False)
    visibility_audience: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    chunk_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )


class EmbeddingProfile(Base):
    """Versioned, credential-free compatibility profile for a vector partition."""

    __tablename__ = "embedding_profile"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "model",
            "model_revision",
            "config_hash",
            name="uq_embedding_profile_identity",
        ),
        CheckConstraint("runtime_kind IN ('local','hosted')", name="runtime_kind_allowed"),
        CheckConstraint("dimensions > 0", name="dimensions_positive"),
        CheckConstraint(
            "distance_metric IN ('cosine','euclidean','inner_product')",
            name="distance_metric_allowed",
        ),
        CheckConstraint("config_hash ~ '^[0-9a-f]{64}$'", name="config_hash_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    runtime_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    model_revision: Mapped[str] = mapped_column(String(200), nullable=False)
    license: Mapped[str] = mapped_column(String(200), nullable=False)
    dimensions: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    distance_metric: Mapped[str] = mapped_column(String(20), nullable=False)
    normalization_version: Mapped[str] = mapped_column(String(100), nullable=False)
    preprocessing_version: Mapped[str] = mapped_column(String(100), nullable=False)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DocumentChunkEmbedding(Base):
    """Immutable vector derived from one exact chunk hash and profile."""

    __tablename__ = "document_chunk_embedding"
    __table_args__ = (
        UniqueConstraint(
            "document_chunk_id",
            "embedding_profile_id",
            "chunk_content_hash",
            name="uq_document_chunk_embedding_derivation",
        ),
        CheckConstraint(
            "chunk_content_hash ~ '^[0-9a-f]{64}$'", name="chunk_content_hash_valid"
        ),
        Index(
            "ix_document_chunk_embedding_profile_chunk",
            "embedding_profile_id",
            "document_chunk_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    document_chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_chunk.id", ondelete="RESTRICT"),
        nullable=False,
    )
    embedding_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("embedding_profile.id", ondelete="RESTRICT"),
        nullable=False,
    )
    chunk_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding: Mapped[Any] = mapped_column(Vector(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class EmbeddingRun(Base):
    """Durable, restart-safe derivation attempt for one snapshot/profile pair."""

    __tablename__ = "embedding_run"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({_EMBEDDING_RUN_STATUSES})", name="status_allowed"
        ),
        CheckConstraint(
            "(status = 'running' AND finished_at IS NULL) OR "
            "(status IN ('succeeded','failed','cancelled') AND "
            "finished_at IS NOT NULL)",
            name="status_finished_consistent",
        ),
        CheckConstraint("batch_size > 0", name="batch_size_positive"),
        CheckConstraint("max_attempts > 0", name="max_attempts_positive"),
        CheckConstraint("dimensions > 0", name="dimensions_positive"),
        CheckConstraint(
            "jsonb_typeof(resource_observations) = 'object' AND "
            "jsonb_typeof(usage_metadata) = 'object'",
            name="observations_and_usage_objects",
        ),
        CheckConstraint(
            "finished_at IS NULL OR finished_at >= started_at",
            name="finished_after_started",
        ),
        Index(
            "ix_embedding_run_snapshot_profile_status",
            "corpus_snapshot_id",
            "embedding_profile_id",
            "status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    corpus_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("corpus_snapshot.id", ondelete="RESTRICT"),
        nullable=False,
    )
    embedding_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("embedding_profile.id", ondelete="RESTRICT"),
        nullable=False,
    )
    runtime_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model_revision: Mapped[str] = mapped_column(String(200), nullable=False)
    dimensions: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    batch_size: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    max_attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    resource_observations: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    usage_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EmbeddingRunItem(Base):
    """One exact snapshot chunk's resumable derivation state within a run."""

    __tablename__ = "embedding_run_item"
    __table_args__ = (
        UniqueConstraint(
            "embedding_run_id",
            "document_chunk_id",
            "chunk_content_hash",
            name="uq_embedding_run_item_derivation",
        ),
        CheckConstraint(
            f"status IN ({_EMBEDDING_ITEM_STATUSES})", name="status_allowed"
        ),
        CheckConstraint("attempt_count >= 0", name="attempt_count_nonnegative"),
        CheckConstraint(
            "chunk_content_hash ~ '^[0-9a-f]{64}$'", name="chunk_content_hash_valid"
        ),
        CheckConstraint(
            "(status IN ('succeeded','skipped') AND "
            "document_chunk_embedding_id IS NOT NULL) OR "
            "(status NOT IN ('succeeded','skipped') AND "
            "document_chunk_embedding_id IS NULL)",
            name="terminal_derivation_consistent",
        ),
        Index("ix_embedding_run_item_run_status", "embedding_run_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    embedding_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("embedding_run.id", ondelete="RESTRICT"),
        nullable=False,
    )
    document_chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_chunk.id", ondelete="RESTRICT"),
        nullable=False,
    )
    chunk_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document_chunk_embedding_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_chunk_embedding.id", ondelete="RESTRICT"),
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    attempt_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(100))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RetrievalRun(Base):
    """Immutable source-body-free audit record for one resolved retrieval request."""

    __tablename__ = "retrieval_run"
    __table_args__ = (
        CheckConstraint(f"mode IN ({_RETRIEVAL_RUN_MODES})", name="mode_allowed"),
        CheckConstraint("query_sha256 ~ '^[0-9a-f]{64}$'", name="query_hash_valid"),
        CheckConstraint(
            "duration_milliseconds >= 0", name="duration_milliseconds_nonnegative"
        ),
        CheckConstraint(
            "jsonb_typeof(resolved_scope) = 'object' AND "
            "jsonb_typeof(retrieval_versions) = 'object' AND "
            "jsonb_typeof(candidates) = 'array' AND "
            "jsonb_typeof(selected_citation_ids) = 'array'",
            name="audit_json_shapes",
        ),
        Index("ix_retrieval_run_snapshot_created", "corpus_snapshot_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    corpus_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("corpus_snapshot.id", ondelete="RESTRICT"),
        nullable=False,
    )
    embedding_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("embedding_run.id", ondelete="RESTRICT")
    )
    mode: Mapped[str] = mapped_column(String(24), nullable=False)
    query_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    retrieval_versions: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    resolved_scope: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    candidates: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    selected_citation_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    duration_milliseconds: Mapped[float] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CorpusSnapshot(Base):
    """Exact candidate/serving revision set for one owner/corpus scope."""

    __tablename__ = "corpus_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "campaign_id",
            "corpus",
            "id",
            name="uq_corpus_snapshot_owner_corpus_id",
            postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint(f"corpus IN ({_CORPORA})", name="corpus_allowed"),
        CheckConstraint(
            "corpus <> 'campaign' OR campaign_id IS NOT NULL",
            name="campaign_corpus_has_owner",
        ),
        CheckConstraint(f"state IN ({_SNAPSHOT_STATES})", name="state_allowed"),
        CheckConstraint(
            "(state = 'candidate' AND activated_at IS NULL) OR "
            "(state IN ('active','superseded') AND activated_at IS NOT NULL)",
            name="state_activation_consistent",
        ),
        ForeignKeyConstraint(
            ("campaign_id", "corpus", "parent_snapshot_id"),
            (
                "corpus_snapshot.campaign_id",
                "corpus_snapshot.corpus",
                "corpus_snapshot.id",
            ),
            name="fk_corpus_snapshot_parent_same_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ("campaign_id", "corpus", "ingestion_run_id"),
            (
                "ingestion_run.campaign_id",
                "ingestion_run.corpus",
                "ingestion_run.id",
            ),
            name="fk_corpus_snapshot_ingestion_same_scope",
            ondelete="RESTRICT",
        ),
        Index(
            "uq_corpus_snapshot_active_scope",
            "campaign_id",
            "corpus",
            unique=True,
            postgresql_where=text("state = 'active'"),
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    corpus: Mapped[str] = mapped_column(String(20), nullable=False)
    parent_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("corpus_snapshot.id", ondelete="RESTRICT"),
    )
    ingestion_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ingestion_run.id", ondelete="RESTRICT"),
        nullable=False,
    )
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CorpusSnapshotDocument(Base):
    """Immutable exact document-revision membership in a corpus snapshot."""

    __tablename__ = "corpus_snapshot_document"
    __table_args__ = (
        ForeignKeyConstraint(
            ("campaign_id", "corpus", "corpus_snapshot_id"),
            (
                "corpus_snapshot.campaign_id",
                "corpus_snapshot.corpus",
                "corpus_snapshot.id",
            ),
            name="fk_snapshot_document_snapshot_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ("campaign_id", "corpus", "document_revision_id"),
            (
                "document_revision.campaign_id",
                "document_revision.corpus",
                "document_revision.id",
            ),
            name="fk_snapshot_document_revision_scope",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "corpus_snapshot_id",
            "document_revision_id",
            name="uq_snapshot_document_revision",
        ),
        UniqueConstraint(
            "corpus_snapshot_id", "ordinal", name="uq_snapshot_document_ordinal"
        ),
        CheckConstraint("ordinal >= 0", name="ordinal_nonnegative"),
    )

    corpus_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("corpus_snapshot.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    document_revision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_revision.id", ondelete="RESTRICT"),
        nullable=False,
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    corpus: Mapped[str] = mapped_column(String(20), nullable=False)
    ordinal: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
