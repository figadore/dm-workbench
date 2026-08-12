"""Campaign knowledge entity, alias, mention, merge, and resolution tests."""

import uuid

import pytest
from sqlalchemy import Engine

from dm_assistant.db import Campaign, build_session_factory, transactional_session
from dm_assistant.errors import ConflictError
from dm_assistant.modules.campaign_knowledge import (
    AddEntityAlias,
    AddEntityMention,
    ArchiveEntity,
    CampaignKnowledgeService,
    CreateEntity,
    EntityMatchKind,
    EntityResolutionState,
    MergeEntities,
    SplitEntity,
)

pytestmark = pytest.mark.integration


def create_campaign(engine: Engine, name: str = "Synthetic Knowledge Campaign") -> uuid.UUID:
    campaign_id = uuid.uuid4()
    factory = build_session_factory(engine)
    with transactional_session(factory) as session:
        session.add(Campaign(id=campaign_id, name=name))
    return campaign_id


def test_entity_alias_mention_merge_split_and_archive_flow(db_engine: Engine) -> None:
    campaign_id = create_campaign(db_engine)
    service = CampaignKnowledgeService(db_engine)

    mara = service.create_entity(
        CreateEntity(campaign_id=campaign_id, canonical_name="Mara Stone")
    )
    service.add_alias(
        AddEntityAlias(
            campaign_id=campaign_id,
            entity_id=mara.id,
            alias="Mother Mara",
        )
    )
    mention = service.add_mention(
        AddEntityMention(
            campaign_id=campaign_id,
            entity_id=mara.id,
            source_label="chapter-1",
            source_excerpt="Mother Mara warned them about the lower crypts.",
            source_span_start=12,
            source_span_end=56,
        )
    )
    assert mention.source_excerpt.startswith("Mother Mara")

    mira = service.create_entity(
        CreateEntity(campaign_id=campaign_id, canonical_name="Mira Stone")
    )
    old_statue = service.create_entity(
        CreateEntity(campaign_id=campaign_id, canonical_name="Old Statue")
    )

    exact = service.resolve_candidates(campaign_id, "Mara Stone")
    assert exact.resolution_state is EntityResolutionState.EXACT
    assert exact.candidates[0].entity_id == mara.id
    assert exact.candidates[0].match_kind is EntityMatchKind.EXACT_NAME

    alias = service.resolve_candidates(campaign_id, "Mother Mara")
    assert alias.resolution_state is EntityResolutionState.EXACT
    assert alias.candidates[0].entity_id == mara.id
    assert alias.candidates[0].match_kind is EntityMatchKind.EXACT_ALIAS

    fuzzy = service.resolve_candidates(campaign_id, "Mara Ston")
    assert fuzzy.resolution_state in {
        EntityResolutionState.FUZZY,
        EntityResolutionState.AMBIGUOUS,
    }
    assert fuzzy.candidates[0].entity_id == mara.id

    merge = service.merge_entities(
        MergeEntities(
            campaign_id=campaign_id,
            target_entity_id=mara.id,
            source_entity_id=mira.id,
            merge_reason="same person, alternate spelling",
        )
    )
    assert merge.event_kind == "merge"

    redirected = service.resolve_candidates(campaign_id, "Mira Stone")
    assert redirected.resolution_state is EntityResolutionState.EXACT
    assert redirected.candidates[0].entity_id == mara.id
    assert redirected.candidates[0].match_kind is EntityMatchKind.REDIRECT
    assert redirected.candidates[0].redirected_from_entity_id == mira.id

    split = service.split_entity(
        SplitEntity(
            campaign_id=campaign_id,
            source_entity_id=mara.id,
            corrected_name="Mara Stone (Corrected)",
            split_reason="review correction from session note",
        )
    )
    assert split.event_kind == "split"

    corrected = service.resolve_candidates(campaign_id, "Mara Stone")
    assert corrected.candidates[0].canonical_name == "Mara Stone (Corrected)"
    assert corrected.candidates[0].match_kind is EntityMatchKind.REDIRECT
    assert corrected.candidates[0].redirected_from_entity_id == mara.id

    archived = service.archive_entity(
        ArchiveEntity(
            campaign_id=campaign_id,
            entity_id=old_statue.id,
            archive_reason="retired scene prop",
        )
    )
    assert archived.status.name == "ARCHIVED"


def test_alias_collisions_reject_duplicate_names_without_auto_merge(
    db_engine: Engine,
) -> None:
    campaign_id = create_campaign(db_engine)
    service = CampaignKnowledgeService(db_engine)

    mara = service.create_entity(
        CreateEntity(campaign_id=campaign_id, canonical_name="Mara Stone")
    )
    service.create_entity(
        CreateEntity(campaign_id=campaign_id, canonical_name="Mira Stone")
    )

    with pytest.raises(ConflictError, match="already exists"):
        service.add_alias(
            AddEntityAlias(
                campaign_id=campaign_id,
                entity_id=mara.id,
                alias="Mira Stone",
            )
        )

