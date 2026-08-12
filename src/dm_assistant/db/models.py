"""Minimal foundation models used to prove migrations and transactions."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from dm_assistant.db.base import Base


class Campaign(Base):
    """Root campaign aggregate; domain fields arrive in later migrations."""

    __tablename__ = "campaign"
    __table_args__ = (
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
        Index(
            "uq_campaign_single_active",
            "is_active",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ModelTaskSelection(Base):
    """Inspectable Workbench default for one bounded model task."""

    __tablename__ = "model_task_selection"
    __table_args__ = (
        CheckConstraint(
            "effort IN ('fast', 'standard', 'deep')",
            name="effort",
        ),
    )

    task_name: Mapped[str] = mapped_column(String(80), primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(160), nullable=False)
    model_id: Mapped[str] = mapped_column(String(160), nullable=False)
    effort: Mapped[str] = mapped_column(String(20), nullable=False)
    selection_policy: Mapped[str] = mapped_column(String(80), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
