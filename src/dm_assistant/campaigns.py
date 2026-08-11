"""Minimal read-only campaign catalog for the initial shared shell."""

import uuid
from dataclasses import dataclass

from sqlalchemy import Engine, select
from sqlalchemy.exc import IntegrityError

from dm_assistant.db import Campaign, build_session_factory, transactional_session
from dm_assistant.errors import ConflictError, InvalidInputError


@dataclass(frozen=True, slots=True)
class CampaignSummary:
    id: uuid.UUID
    name: str


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
                session.add(campaign)
        except IntegrityError:
            raise ConflictError("A campaign with that name already exists.") from None
        return CampaignSummary(id=campaign.id, name=campaign.name)

    def list_campaigns(self) -> tuple[CampaignSummary, ...]:
        with transactional_session(self._factory) as session:
            rows = session.execute(
                select(Campaign.id, Campaign.name).order_by(Campaign.name, Campaign.id)
            )
            return tuple(CampaignSummary(id=row.id, name=row.name) for row in rows)
