"""Campaign knowledge contracts for entities, aliases, mentions, and merges."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

ShortText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
SummaryText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
]


class ContractModel(BaseModel):
    """Strict immutable contract baseline."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class EntityKind(StrEnum):
    CHARACTER = "character"
    LOCATION = "location"
    FACTION = "faction"
    ITEM = "item"
    EVENT = "event"
    OTHER = "other"


class EntityStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class EntityMatchKind(StrEnum):
    EXACT_NAME = "exact_name"
    EXACT_ALIAS = "exact_alias"
    REDIRECT = "redirect"
    FUZZY_NAME = "fuzzy_name"
    FUZZY_ALIAS = "fuzzy_alias"


class EntityResolutionState(StrEnum):
    EXACT = "exact"
    FUZZY = "fuzzy"
    AMBIGUOUS = "ambiguous"
    NONE = "none"


class CreateEntity(ContractModel):
    campaign_id: UUID
    canonical_name: ShortText
    kind: EntityKind = EntityKind.OTHER


class AddEntityAlias(ContractModel):
    campaign_id: UUID
    entity_id: UUID
    alias: ShortText


class AddEntityMention(ContractModel):
    campaign_id: UUID
    entity_id: UUID
    source_label: ShortText
    source_excerpt: SummaryText
    source_span_start: int | None = Field(default=None, ge=0)
    source_span_end: int | None = Field(default=None, ge=0)


class MergeEntities(ContractModel):
    campaign_id: UUID
    target_entity_id: UUID
    source_entity_id: UUID
    merge_reason: SummaryText | None = None


class SplitEntity(ContractModel):
    campaign_id: UUID
    source_entity_id: UUID
    corrected_name: ShortText
    split_reason: SummaryText | None = None


class ArchiveEntity(ContractModel):
    campaign_id: UUID
    entity_id: UUID
    archive_reason: SummaryText | None = None


class EntityRecord(ContractModel):
    id: UUID
    campaign_id: UUID
    canonical_name: str
    kind: EntityKind
    status: EntityStatus
    redirect_entity_id: UUID | None
    archived_at: datetime | None
    archive_reason: str | None


class EntityAliasRecord(ContractModel):
    id: UUID
    campaign_id: UUID
    entity_id: UUID
    alias: str


class EntityMentionRecord(ContractModel):
    id: UUID
    campaign_id: UUID
    entity_id: UUID
    source_label: str
    source_excerpt: str
    source_span_start: int | None
    source_span_end: int | None


class EntityMergeRecord(ContractModel):
    id: UUID
    campaign_id: UUID
    source_entity_id: UUID
    target_entity_id: UUID
    event_kind: Literal["merge", "split", "review_correction", "archive"]
    event_note: str | None


class ResolvedEntityCandidate(ContractModel):
    entity_id: UUID
    canonical_name: str
    kind: EntityKind
    status: EntityStatus
    match_kind: EntityMatchKind
    score: float = Field(ge=0.0, le=1.0)
    redirected_from_entity_id: UUID | None = None
    matched_text: str | None = None


class EntityResolutionResult(ContractModel):
    campaign_id: UUID
    query: str
    resolution_state: EntityResolutionState
    candidates: tuple[ResolvedEntityCandidate, ...] = ()
