"""Minimal read-only campaign catalog for the initial shared shell."""

import uuid
from dataclasses import dataclass

from sqlalchemy import Engine, select, update
from sqlalchemy.exc import IntegrityError

from dm_assistant.db import Campaign, build_session_factory, transactional_session
from dm_assistant.errors import (
    ConflictError,
    InvalidInputError,
    ResourceNotFoundError,
)


@dataclass(frozen=True, slots=True)
class CampaignSummary:
    id: uuid.UUID
    name: str
    active: bool = False


class CampaignCatalog:
    """Read the existing campaign roots without owning canonical facts."""

    def __init__(self, engine: Engine) -> None:
        self._factory = build_session_factory(engine)

    def create_campaign(self, name: str) -> CampaignSummary:
        normalized = name.strip()
        if not normalized or len(normalized) > 200:
            raise InvalidInputError("Campaign name must contain 1-200 characters.")
        campaign = Campaign(id=uuid.uuid4(), name=normalized)
        try:
            with transactional_session(self._factory) as session:
                campaign.is_active = (
                    session.scalar(select(Campaign.id).where(Campaign.is_active))
                    is None
                )
                session.add(campaign)
        except IntegrityError:
            raise ConflictError("A campaign with that name already exists.") from None
        return CampaignSummary(
            id=campaign.id,
            name=campaign.name,
            active=campaign.is_active,
        )

    def ensure_active_campaign(self) -> CampaignSummary:
        """Return the active campaign, creating an empty first-run owner if needed."""

        with transactional_session(self._factory) as session:
            campaign = session.scalar(
                select(Campaign).where(Campaign.is_active).limit(1)
            )
            if campaign is None:
                campaign = session.scalar(
                    select(Campaign).order_by(Campaign.created_at, Campaign.id).limit(1)
                )
                if campaign is None:
                    campaign = Campaign(name="My Campaign", is_active=True)
                    session.add(campaign)
                    session.flush()
                else:
                    campaign.is_active = True
            return CampaignSummary(
                id=campaign.id,
                name=campaign.name,
                active=True,
            )

    def use_campaign(self, campaign: str) -> CampaignSummary:
        """Select the active campaign by exact UUID or exact name."""

        normalized = campaign.strip()
        if not normalized:
            raise InvalidInputError("Campaign selection cannot be blank.")
        try:
            campaign_id = uuid.UUID(normalized)
        except ValueError:
            campaign_id = None
        with transactional_session(self._factory) as session:
            query = (
                select(Campaign).where(Campaign.id == campaign_id)
                if campaign_id is not None
                else select(Campaign).where(Campaign.name == normalized)
            )
            selected = session.scalar(query)
            if selected is None:
                raise ResourceNotFoundError("The selected campaign was not found.")
            session.execute(update(Campaign).values(is_active=False))
            session.execute(
                update(Campaign)
                .where(Campaign.id == selected.id)
                .values(is_active=True)
            )
            return CampaignSummary(id=selected.id, name=selected.name, active=True)

    def list_campaigns(self) -> tuple[CampaignSummary, ...]:
        with transactional_session(self._factory) as session:
            rows = session.execute(
                select(Campaign.id, Campaign.name, Campaign.is_active).order_by(
                    Campaign.name, Campaign.id
                )
            )
            return tuple(
                CampaignSummary(id=row.id, name=row.name, active=row.is_active)
                for row in rows
            )
