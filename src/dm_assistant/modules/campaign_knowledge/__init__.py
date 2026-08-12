"""Campaign knowledge contracts and services."""

from dm_assistant.modules.campaign_knowledge.contracts import (
    AddEntityAlias,
    AddEntityMention,
    ArchiveEntity,
    CreateEntity,
    EntityAliasRecord,
    EntityKind,
    EntityMatchKind,
    EntityMentionRecord,
    EntityMergeRecord,
    EntityRecord,
    EntityResolutionResult,
    EntityResolutionState,
    EntityStatus,
    MergeEntities,
    ResolvedEntityCandidate,
    SplitEntity,
)
from dm_assistant.modules.campaign_knowledge.service import CampaignKnowledgeService

__all__ = [
    "AddEntityAlias",
    "AddEntityMention",
    "ArchiveEntity",
    "CampaignKnowledgeService",
    "CreateEntity",
    "EntityAliasRecord",
    "EntityKind",
    "EntityMatchKind",
    "EntityMergeRecord",
    "EntityMentionRecord",
    "EntityRecord",
    "EntityResolutionResult",
    "EntityResolutionState",
    "EntityStatus",
    "MergeEntities",
    "ResolvedEntityCandidate",
    "SplitEntity",
]
