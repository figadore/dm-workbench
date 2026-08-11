"""Enable pgvector and create the minimal campaign foundation.

Revision ID: 0001_foundation
Revises: None
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_foundation"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Install vector support and the first aggregate root table."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "campaign",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(btrim(name)) > 0",
            name=op.f("ck_campaign_name_not_blank"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_campaign"),
        sa.UniqueConstraint("name", name="uq_campaign_name"),
    )


def downgrade() -> None:
    """Return an isolated foundation database to Alembic base."""
    op.drop_table("campaign")
    op.execute("DROP EXTENSION IF EXISTS vector")
