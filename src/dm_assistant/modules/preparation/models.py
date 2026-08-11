"""SQLAlchemy persistence models for preparation-only state."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from dm_assistant.db.base import Base

_ARTIFACT_TYPES = (
    "'dungeon','map_package','encounter','puzzle','generated_creature','other'"
)
_LIFECYCLES = "'draft','approved_for_play','used','retired'"
_VISIBILITIES = "'dm_only','all_campaign_players','explicit_audience','public'"
_RUN_STATUSES = "'running','succeeded','failed','cancelled'"
_ASSET_ROLES = (
    "'specification','validation_report','dm_svg','player_svg','dm_png',"
    "'player_png','print_pdf','dm_print_pdf','player_print_pdf','roll20_bundle',"
    "'dm_roll20_bundle','player_roll20_bundle','manifest','other'"
)


class GenerationRun(Base):
    """Durable, pin-complete preparation generation attempt."""

    __tablename__ = "generation_run"
    __table_args__ = (
        UniqueConstraint("campaign_id", "id", name="uq_generation_run_campaign_id_id"),
        CheckConstraint(
            f"status IN ({_RUN_STATUSES})",
            name="status_allowed",
        ),
        CheckConstraint(
            "(status = 'running' AND finished_at IS NULL) OR "
            "(status IN ('succeeded','failed','cancelled') AND finished_at IS NOT NULL)",
            name="status_finished_consistent",
        ),
        CheckConstraint(
            "finished_at IS NULL OR finished_at >= started_at",
            name="finished_after_started",
        ),
        CheckConstraint(
            "jsonb_typeof(input_scope) = 'object'",
            name="input_scope_object",
        ),
        CheckConstraint(
            "jsonb_typeof(schema_versions) = 'object' AND schema_versions <> '{}'::jsonb",
            name="schema_versions_nonempty_object",
        ),
        CheckConstraint(
            "jsonb_typeof(generator_versions) = 'object' AND "
            "jsonb_typeof(renderer_versions) = 'object'",
            name="implementation_versions_objects",
        ),
        CheckConstraint(
            "jsonb_typeof(model_run_ids) = 'array' AND "
            "jsonb_typeof(tool_runs) = 'array' AND "
            "jsonb_typeof(context_source_links) = 'array' AND "
            "jsonb_typeof(validation_report) = 'object'",
            name="run_json_shapes",
        ),
        CheckConstraint(
            "(generation_context_envelope IS NULL AND context_envelope_kind IS NULL "
            "AND context_payload_version IS NULL AND context_payload_sha256 IS NULL "
            "AND context_source_links = '[]'::jsonb) OR "
            "(generation_context_envelope IS NOT NULL AND "
            "jsonb_typeof(generation_context_envelope) = 'object' AND "
            "context_envelope_kind IS NOT NULL AND context_payload_version IS NOT NULL "
            "AND context_payload_sha256 ~ '^[0-9a-f]{64}$')",
            name="context_pin_complete",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaign.id", ondelete="RESTRICT"),
        nullable=False,
    )
    generation_kind: Mapped[str] = mapped_column(String(80), nullable=False)
    seed: Mapped[int | None] = mapped_column(BigInteger)
    input_scope: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    input_campaign_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True)
    )
    input_corpus_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True)
    )
    input_rules_profile_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    input_party_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True)
    )
    generation_context_envelope: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB(none_as_null=True)
    )
    context_envelope_kind: Mapped[str | None] = mapped_column(String(80))
    context_payload_version: Mapped[str | None] = mapped_column(String(80))
    context_payload_sha256: Mapped[str | None] = mapped_column(String(64))
    context_source_links: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    schema_versions: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    generator_versions: Mapped[dict[str, str]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    renderer_versions: Mapped[dict[str, str]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    model_task_profile_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    model_run_ids: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    tool_runs: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    validation_report: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PreparationArtifact(Base):
    """Mutable lifecycle pointer over immutable preparation versions."""

    __tablename__ = "prep_artifact"
    __table_args__ = (
        UniqueConstraint("campaign_id", "id", name="uq_prep_artifact_campaign_id_id"),
        ForeignKeyConstraint(
            ("id", "current_version_id"),
            ("prep_artifact_version.artifact_id", "prep_artifact_version.id"),
            name="fk_prep_artifact_current_version",
            ondelete="RESTRICT",
            use_alter=True,
        ),
        CheckConstraint(f"artifact_type IN ({_ARTIFACT_TYPES})", name="type_allowed"),
        CheckConstraint(f"lifecycle IN ({_LIFECYCLES})", name="lifecycle_allowed"),
        CheckConstraint(
            f"visibility_policy IN ({_VISIBILITIES})",
            name="visibility_allowed",
        ),
        CheckConstraint("length(btrim(title)) > 0", name="title_not_blank"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaign.id", ondelete="RESTRICT"),
        nullable=False,
    )
    artifact_type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    lifecycle: Mapped[str] = mapped_column(String(32), nullable=False)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    visibility_policy: Mapped[str] = mapped_column(String(40), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PreparationArtifactVersion(Base):
    """Immutable structured preparation snapshot and complete input lineage."""

    __tablename__ = "prep_artifact_version"
    __table_args__ = (
        UniqueConstraint("artifact_id", "id", name="uq_prep_version_artifact_id_id"),
        UniqueConstraint(
            "artifact_id", "version_number", name="uq_prep_version_artifact_number"
        ),
        ForeignKeyConstraint(
            ("campaign_id", "artifact_id"),
            ("prep_artifact.campaign_id", "prep_artifact.id"),
            name="fk_prep_version_campaign_artifact",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ("artifact_id", "parent_version_id"),
            ("prep_artifact_version.artifact_id", "prep_artifact_version.id"),
            name="fk_prep_version_parent_same_artifact",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ("campaign_id", "generation_run_id"),
            ("generation_run.campaign_id", "generation_run.id"),
            name="fk_prep_version_generation_run_campaign",
            ondelete="RESTRICT",
        ),
        CheckConstraint("version_number > 0", name="version_number_positive"),
        CheckConstraint("length(btrim(change_summary)) > 0", name="summary_not_blank"),
        CheckConstraint(
            "specification_sha256 ~ '^[0-9a-f]{64}$'",
            name="specification_hash_valid",
        ),
        CheckConstraint(
            "jsonb_typeof(specification) = 'object' AND "
            "jsonb_typeof(validation_report) = 'object'",
            name="version_json_objects",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    artifact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    schema_version: Mapped[str] = mapped_column(String(80), nullable=False)
    specification: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    specification_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    validation_report: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    change_summary: Mapped[str] = mapped_column(Text, nullable=False)
    input_campaign_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True)
    )
    input_corpus_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True)
    )
    input_rules_profile_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    input_party_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True)
    )
    generation_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class GeneratedAsset(Base):
    """Generic content-addressed blob metadata, independent of dungeon roles."""

    __tablename__ = "generated_asset"
    __table_args__ = (
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256_valid"),
        CheckConstraint("byte_size >= 0", name="byte_size_nonnegative"),
        CheckConstraint(
            "storage_locator ~ '^sha256/[0-9a-f]{2}/[0-9a-f]{64}$'",
            name="locator_safe",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    media_type: Mapped[str] = mapped_column(String(127), nullable=False)
    storage_locator: Mapped[str] = mapped_column(
        String(80), nullable=False, unique=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ArtifactAsset(Base):
    """Immutable role assignment from an artifact version to a generic blob."""

    __tablename__ = "artifact_asset"
    __table_args__ = (
        CheckConstraint(f"role IN ({_ASSET_ROLES})", name="role_allowed"),
        CheckConstraint("ordinal >= 0", name="ordinal_nonnegative"),
    )

    artifact_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prep_artifact_version.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String(40), primary_key=True)
    ordinal: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=0)
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("generated_asset.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ArtifactLifecycleEvent(Base):
    """Immutable audit trail for preparation-only lifecycle transitions."""

    __tablename__ = "artifact_lifecycle_event"
    __table_args__ = (
        ForeignKeyConstraint(
            ("artifact_id", "artifact_version_id"),
            ("prep_artifact_version.artifact_id", "prep_artifact_version.id"),
            name="fk_lifecycle_event_version_same_artifact",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            f"from_lifecycle IS NULL OR from_lifecycle IN ({_LIFECYCLES})",
            name="from_lifecycle_allowed",
        ),
        CheckConstraint(
            f"to_lifecycle IN ({_LIFECYCLES})", name="to_lifecycle_allowed"
        ),
        CheckConstraint("length(btrim(reason)) > 0", name="reason_not_blank"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prep_artifact.id", ondelete="RESTRICT"),
        nullable=False,
    )
    artifact_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    from_lifecycle: Mapped[str | None] = mapped_column(String(32))
    to_lifecycle: Mapped[str] = mapped_column(String(32), nullable=False)
    actor: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
