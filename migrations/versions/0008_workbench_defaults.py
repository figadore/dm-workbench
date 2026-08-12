"""Add inspectable active-campaign and task-model defaults.

Revision ID: 0008_workbench_defaults
Revises: 0007_campaign_knowledge_entities
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_workbench_defaults"
down_revision: str | None = "0007_campaign_knowledge_entities"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add one inspectable active campaign and task-specific model selections."""

    op.add_column(
        "campaign",
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.create_index(
        "uq_campaign_single_active",
        "campaign",
        ["is_active"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.execute(
        """
        UPDATE campaign
        SET is_active = true
        WHERE id = (
            SELECT id FROM campaign ORDER BY created_at, id LIMIT 1
        )
        """
    )
    op.create_table(
        "model_task_selection",
        sa.Column("task_name", sa.String(length=80), nullable=False),
        sa.Column("provider_id", sa.String(length=160), nullable=False),
        sa.Column("model_id", sa.String(length=160), nullable=False),
        sa.Column("effort", sa.String(length=20), nullable=False),
        sa.Column("selection_policy", sa.String(length=80), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "effort IN ('fast', 'standard', 'deep')",
            name=op.f("ck_model_task_selection_effort"),
        ),
        sa.PrimaryKeyConstraint("task_name", name=op.f("pk_model_task_selection")),
    )


def downgrade() -> None:
    """Remove Workbench defaults without deleting campaign roots."""

    op.drop_table("model_task_selection")
    op.drop_index("uq_campaign_single_active", table_name="campaign")
    op.drop_column("campaign", "is_active")
