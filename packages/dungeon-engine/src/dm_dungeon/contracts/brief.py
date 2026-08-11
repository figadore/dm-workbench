"""Versioned high-level dungeon intent contracts."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from dm_dungeon.contracts.common import (
    NonEmptyText,
    OpaqueId,
    ShortText,
    VersionedContract,
    Visibility,
    VisibleContract,
)

DUNGEON_BRIEF_SCHEMA_VERSION = "1.0.0"
PositiveCount = Annotated[int, Field(ge=1)]


class DungeonPurpose(StrEnum):
    """Primary fictional use of a dungeon location."""

    CAVERN = "cavern"
    LAIR = "lair"
    MINE = "mine"
    PLANAR_SITE = "planar_site"
    PRISON = "prison"
    RUIN = "ruin"
    STRONGHOLD = "stronghold"
    TEMPLE = "temple"
    TOMB = "tomb"
    OTHER = "other"


class PacingStyle(StrEnum):
    """Coarse pacing intent without encounter arithmetic."""

    BALANCED = "balanced"
    COMBAT_HEAVY = "combat_heavy"
    EXPLORATION_HEAVY = "exploration_heavy"
    PUZZLE_HEAVY = "puzzle_heavy"
    SOCIAL_HEAVY = "social_heavy"


class PartyScale(VersionedContract):
    """Coarse party bounds used only for spatial intent."""

    supported_schema_version = DUNGEON_BRIEF_SCHEMA_VERSION

    schema_version: Literal["1.0.0"]
    minimum_characters: PositiveCount
    maximum_characters: PositiveCount
    minimum_level: PositiveCount
    maximum_level: PositiveCount

    @model_validator(mode="after")
    def validate_bounds(self) -> Self:
        if self.minimum_characters > self.maximum_characters:
            raise ValueError("minimum_characters cannot exceed maximum_characters")
        if self.minimum_level > self.maximum_level:
            raise ValueError("minimum_level cannot exceed maximum_level")
        return self


class ClassifiedBriefText(VisibleContract):
    """Narrative intent whose publication safety is explicit."""

    id: OpaqueId
    text: NonEmptyText


class DungeonBrief(VersionedContract):
    """Constrained, model- and renderer-independent dungeon intent."""

    supported_schema_version = DUNGEON_BRIEF_SCHEMA_VERSION

    schema_version: Literal["1.0.0"]
    id: OpaqueId
    title: ShortText
    purpose: DungeonPurpose
    summary: NonEmptyText
    visibility: Visibility
    themes: tuple[ShortText, ...] = Field(min_length=1)
    tones: tuple[ShortText, ...] = ()
    inhabitants: tuple[ClassifiedBriefText, ...] = ()
    floor_count: PositiveCount
    target_room_count: PositiveCount
    pacing: PacingStyle = PacingStyle.BALANCED
    party_scale: PartyScale | None = None
    constraints: tuple[ClassifiedBriefText, ...] = ()
    campaign_hooks: tuple[ClassifiedBriefText, ...] = ()
    tags: tuple[ShortText, ...] = ()
