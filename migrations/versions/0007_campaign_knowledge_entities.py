"""Add campaign entities, aliases, mentions, and merge history."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_campaign_knowledge_entities"
down_revision: str | None = "0006_library_retrieval_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "campaign_entity",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("canonical_name", sa.String(length=200), nullable=False),
        sa.Column("normalized_name", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'active'"),
            nullable=False,
        ),
        sa.Column("redirect_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("archive_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "length(btrim(canonical_name)) > 0",
            name=op.f("ck_campaign_entity_name_not_blank"),
        ),
        sa.CheckConstraint(
            "status IN ('active','archived')",
            name=op.f("ck_campaign_entity_status_allowed"),
        ),
        sa.CheckConstraint(
            "(status = 'active' AND archived_at IS NULL) OR "
            "(status = 'archived' AND archived_at IS NOT NULL)",
            name=op.f("ck_campaign_entity_status_archive_consistent"),
        ),
        sa.CheckConstraint(
            "redirect_entity_id IS NULL OR redirect_entity_id <> id",
            name=op.f("ck_campaign_entity_redirect_not_self"),
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaign.id"],
            name=op.f("fk_campaign_entity_campaign_id_campaign"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["redirect_entity_id"],
            ["campaign_entity.id"],
            name=op.f("fk_campaign_entity_redirect_entity_id_campaign_entity"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaign_entity")),
        sa.UniqueConstraint(
            "campaign_id",
            "normalized_name",
            name=op.f("uq_campaign_entity_campaign_normalized_name"),
        ),
    )
    op.create_index(
        op.f("ix_campaign_entity_campaign_status"),
        "campaign_entity",
        ["campaign_id", "status"],
        unique=False,
    )
    op.create_table(
        "campaign_entity_alias",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("alias", sa.String(length=200), nullable=False),
        sa.Column("normalized_alias", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(btrim(alias)) > 0",
            name=op.f("ck_campaign_entity_alias_not_blank"),
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaign.id"],
            name=op.f("fk_campaign_entity_alias_campaign_id_campaign"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["entity_id"],
            ["campaign_entity.id"],
            name=op.f("fk_campaign_entity_alias_entity_id_campaign_entity"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaign_entity_alias")),
        sa.UniqueConstraint(
            "campaign_id",
            "normalized_alias",
            name=op.f("uq_campaign_entity_alias_campaign_normalized_alias"),
        ),
    )
    op.create_table(
        "campaign_entity_mention",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_label", sa.String(length=200), nullable=False),
        sa.Column("source_excerpt", sa.Text(), nullable=False),
        sa.Column("source_span_start", sa.Integer(), nullable=True),
        sa.Column("source_span_end", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(btrim(source_label)) > 0",
            name=op.f("ck_campaign_entity_mention_source_label_not_blank"),
        ),
        sa.CheckConstraint(
            "length(btrim(source_excerpt)) > 0",
            name=op.f("ck_campaign_entity_mention_source_excerpt_not_blank"),
        ),
        sa.CheckConstraint(
            "source_span_start IS NULL OR source_span_end IS NULL OR "
            "source_span_end >= source_span_start",
            name=op.f("ck_campaign_entity_mention_span_order"),
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaign.id"],
            name=op.f("fk_campaign_entity_mention_campaign_id_campaign"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["entity_id"],
            ["campaign_entity.id"],
            name=op.f("fk_campaign_entity_mention_entity_id_campaign_entity"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaign_entity_mention")),
    )
    op.create_table(
        "campaign_entity_merge_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_kind", sa.String(length=24), nullable=False),
        sa.Column("event_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "event_kind IN ('merge','split','review_correction','archive')",
            name=op.f("ck_campaign_entity_merge_history_event_kind_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaign.id"],
            name=op.f("fk_campaign_entity_merge_history_campaign_id_campaign"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_entity_id"],
            ["campaign_entity.id"],
            name=op.f("fk_campaign_entity_merge_history_source_entity_id_campaign_entity"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["target_entity_id"],
            ["campaign_entity.id"],
            name=op.f("fk_campaign_entity_merge_history_target_entity_id_campaign_entity"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaign_entity_merge_history")),
    )


def downgrade() -> None:
    op.drop_table("campaign_entity_merge_history")
    op.drop_table("campaign_entity_mention")
    op.drop_table("campaign_entity_alias")
    op.drop_index(op.f("ix_campaign_entity_campaign_status"), table_name="campaign_entity")
    op.drop_table("campaign_entity")
