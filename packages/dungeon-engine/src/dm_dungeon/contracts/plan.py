"""Small provider-visible creative contract for a Tier A dungeon plan.

The model names rooms and progression primitives. Deterministic code owns graph edges,
component IDs, exact mechanics, geometry, validation, rendering, and publication.
"""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field

from dm_dungeon.contracts.common import (
    ContractModel,
    NonEmptyText,
    ShortText,
    VersionedContract,
)
from dm_dungeon.contracts.topology import RoomRole

DUNGEON_PLAN_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"
LocalRef = Annotated[
    str,
    Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_-]*$"),
]
ThemeText = Annotated[str, Field(min_length=1, max_length=96)]
TagText = Annotated[str, Field(min_length=1, max_length=48)]


class RoomSizeBand(StrEnum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class EncounterSlotIntent(StrEnum):
    AMBUSH = "ambush"
    COMBAT = "combat"
    SOCIAL = "social"
    EXPLORATION = "exploration"


class ChallengeBand(StrEnum):
    """Relative challenge chosen by the author, never a numeric DC."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class FeatureIntentKind(StrEnum):
    ALTAR = "altar"
    BRIDGE = "bridge"
    FURNITURE = "furniture"
    PILLAR = "pillar"
    PIT = "pit"
    STATUE = "statue"
    OTHER = "other"


class GateIntentKind(StrEnum):
    LOCKED = "locked"
    PUZZLE = "puzzle"


class DependencyKind(StrEnum):
    KEY = "key"
    CLUE = "clue"


class PlanRoom(ContractModel):
    """One narrative room identity without a server ID or geometry."""

    ref: LocalRef
    name: ShortText
    role: RoomRole
    size: RoomSizeBand = RoomSizeBand.MEDIUM
    purpose: NonEmptyText
    tags: tuple[TagText, ...] = Field(default=(), max_length=6)
    encounter: EncounterSlotIntent | None = None


class PlanBranch(ContractModel):
    """An ordered spur attached to an already introduced room."""

    ref: LocalRef
    from_room: LocalRef
    rooms: tuple[LocalRef, ...] = Field(min_length=1, max_length=3)


class PlanLoop(ContractModel):
    """One extra edge between existing rooms, optionally concealed."""

    ref: LocalRef
    from_room: LocalRef
    to_room: LocalRef
    secret: bool = False


class PlanGate(ContractModel):
    """At most one gate and its key/clue placement intent."""

    ref: LocalRef
    between_rooms: tuple[LocalRef, ...] = Field(min_length=2, max_length=2)
    kind: GateIntentKind
    dependency_kind: DependencyKind
    dependency_room: LocalRef
    dependency_name: ShortText


class PlanTrap(ContractModel):
    name: ShortText
    trigger: NonEmptyText | None = None
    effect: NonEmptyText | None = None
    detection: NonEmptyText | None = None
    disable: NonEmptyText | None = None
    challenge: ChallengeBand = ChallengeBand.MODERATE


class PlanFeature(ContractModel):
    kind: FeatureIntentKind
    name: ShortText
    description: NonEmptyText


class PlanRoomContent(ContractModel):
    """Bounded room-local content and spatial demand."""

    room_ref: LocalRef
    trap: PlanTrap | None = None
    feature: PlanFeature | None = None
    objective: ShortText | None = None


class DungeonPlan(VersionedContract):
    """The sole model-authored Tier A creative contract."""

    supported_schema_version = DUNGEON_PLAN_SCHEMA_VERSION

    schema_version: Literal["1.0.0"]
    title: ShortText
    premise: NonEmptyText
    themes: tuple[ThemeText, ...] = Field(min_length=1, max_length=4)
    rooms: tuple[PlanRoom, ...] = Field(min_length=4, max_length=8)
    critical_path: tuple[LocalRef, ...] = Field(min_length=2, max_length=8)
    branches: tuple[PlanBranch, ...] = Field(default=(), max_length=2)
    loops: tuple[PlanLoop, ...] = Field(default=(), max_length=1)
    gates: tuple[PlanGate, ...] = Field(default=(), max_length=1)
    room_contents: tuple[PlanRoomContent, ...] = Field(default=(), max_length=8)
