"""SQLAlchemy schema for campaign knowledge entities and provenance."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from dm_assistant.db.base import Base


class CampaignEntity(Base):
    """Canonical campaign entity record with explicit redirect history."""

    __tablename__ = "campaign_entity"
    __table_args__ = (
        UniqueConstraint(
            "campaign_id",
            "normalized_name",
            name="uq_campaign_entity_campaign_normalized_name",
        ),
        CheckConstraint(
            "length(btrim(canonical_name)) > 0",
            name="campaign_entity_name_not_blank",
        ),
        CheckConstraint(
            "status IN ('active','archived')",
            name="campaign_entity_status_allowed",
        ),
        CheckConstraint(
            "(status = 'active' AND archived_at IS NULL) OR "
            "(status = 'archived' AND archived_at IS NOT NULL)",
            name="campaign_entity_status_archive_consistent",
        ),
        CheckConstraint(
            "redirect_entity_id IS NULL OR redirect_entity_id <> id",
            name="campaign_entity_redirect_not_self",
        ),
        Index(
            "ix_campaign_entity_campaign_status",
            "campaign_id",
            "status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaign.id", ondelete="RESTRICT"),
        nullable=False,
    )
    canonical_name: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active", server_default=text("'active'")
    )
    redirect_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("campaign_entity.id", ondelete="RESTRICT")
    )
    archive_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CampaignEntityAlias(Base):
    """Alternate label for a campaign entity."""

    __tablename__ = "campaign_entity_alias"
    __table_args__ = (
        UniqueConstraint(
            "campaign_id",
            "normalized_alias",
            name="uq_campaign_entity_alias_campaign_normalized_alias",
        ),
        CheckConstraint(
            "length(btrim(alias)) > 0",
            name="campaign_entity_alias_not_blank",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaign.id", ondelete="RESTRICT"),
        nullable=False,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaign_entity.id", ondelete="RESTRICT"),
        nullable=False,
    )
    alias: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CampaignEntityMention(Base):
    """Source mention captured with exact note-span metadata."""

    __tablename__ = "campaign_entity_mention"
    __table_args__ = (
        CheckConstraint(
            "length(btrim(source_label)) > 0",
            name="campaign_entity_mention_source_label_not_blank",
        ),
        CheckConstraint(
            "length(btrim(source_excerpt)) > 0",
            name="campaign_entity_mention_source_excerpt_not_blank",
        ),
        CheckConstraint(
            "source_span_start IS NULL OR source_span_end IS NULL OR "
            "source_span_end >= source_span_start",
            name="campaign_entity_mention_span_order",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaign.id", ondelete="RESTRICT"),
        nullable=False,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaign_entity.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_label: Mapped[str] = mapped_column(String(200), nullable=False)
    source_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    source_span_start: Mapped[int | None] = mapped_column(Integer)
    source_span_end: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CampaignEntityMergeHistory(Base):
    """Immutable merge/split/archive history for campaign entities."""

    __tablename__ = "campaign_entity_merge_history"
    __table_args__ = (
        CheckConstraint(
            "event_kind IN ('merge','split','review_correction','archive')",
            name="campaign_entity_merge_history_event_kind_allowed",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaign.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaign_entity.id", ondelete="RESTRICT"),
        nullable=False,
    )
    target_entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaign_entity.id", ondelete="RESTRICT"),
        nullable=False,
    )
    event_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    event_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
