"""Compact, model-independent V2 dungeon-design contracts.

These contracts intentionally contain only creative relative intent.  The compiler,
not a caller or model, assigns every kernel ID, count, visibility classification,
and numeric constraint.
"""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field

from dm_dungeon.contracts.brief import DungeonPurpose, PacingStyle
from dm_dungeon.contracts.common import (
    ContractModel,
    NonEmptyText,
    ShortText,
    VersionedContract,
)
from dm_dungeon.contracts.topology import RoomRole

DUNGEON_DESIGN_V2_SCHEMA_VERSION: Literal["2.0.0"] = "2.0.0"
LocalRef = Annotated[
    str,
    Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_-]*$"),
]
ThemeText = Annotated[str, Field(min_length=1, max_length=96)]


class FloorScale(StrEnum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class RoomSizeBand(StrEnum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class OccupancyBand(StrEnum):
    SOLO = "solo"
    GROUP = "group"
    CROWD = "crowd"


class PassageType(StrEnum):
    PASSAGE = "passage"
    DOOR = "door"
    STAIRS = "stairs"
    LADDER = "ladder"


class Concealment(StrEnum):
    OPEN = "open"
    SECRET = "secret"


class BarrierIntent(StrEnum):
    NONE = "none"
    LOCKED = "locked"
    PUZZLE = "puzzle"


class HazardIntent(StrEnum):
    NONE = "none"
    TRAPPED = "trapped"


class ObjectiveKind(StrEnum):
    FINAL_OBJECTIVE = "final_objective"
    OPTIONAL_OBJECTIVE = "optional_objective"


class DependencyKind(StrEnum):
    KEY = "key"
    CLUE = "clue"


class DesignRoomV2(ContractModel):
    local_ref: LocalRef
    name: ShortText
    role: RoomRole
    room_size: RoomSizeBand = RoomSizeBand.MEDIUM
    occupancy: OccupancyBand = OccupancyBand.GROUP
    optional: bool = False


class DesignFloorV2(ContractModel):
    local_ref: LocalRef
    name: ShortText
    floor_scale: FloorScale = FloorScale.SMALL
    rooms: tuple[DesignRoomV2, ...] = Field(min_length=1, max_length=12)


class DesignConnectionV2(ContractModel):
    local_ref: LocalRef
    from_ref: LocalRef
    to_ref: LocalRef
    passage: PassageType = PassageType.PASSAGE
    # `concealment` is retained only for existing local fixtures; new intent is
    # directional, so a connection can be hidden independently at either end.
    concealment: Concealment = Concealment.OPEN
    from_hidden: bool = False
    to_hidden: bool = False
    barrier: BarrierIntent = BarrierIntent.NONE
    hazard: HazardIntent = HazardIntent.NONE


class DesignObjectiveV2(ContractModel):
    room_ref: LocalRef
    kind: ObjectiveKind


class DesignDependencyV2(ContractModel):
    """A key or clue placed in one room that satisfies a blocked connection."""

    local_ref: LocalRef
    kind: DependencyKind
    connection_ref: LocalRef
    located_in_room_ref: LocalRef
    name: ShortText


class DungeonDesignSpecV2(VersionedContract):
    """Strict compact creative intent accepted by the V2 compiler."""

    supported_schema_version = DUNGEON_DESIGN_V2_SCHEMA_VERSION

    schema_version: Literal["2.0.0"]
    title: ShortText
    premise: NonEmptyText
    purpose: DungeonPurpose = DungeonPurpose.RUIN
    themes: tuple[ThemeText, ...] = Field(min_length=1, max_length=8)
    pacing: PacingStyle = PacingStyle.BALANCED
    floors: tuple[DesignFloorV2, ...] = Field(min_length=1, max_length=4)
    connections: tuple[DesignConnectionV2, ...] = Field(max_length=24)
    objectives: tuple[DesignObjectiveV2, ...] = Field(max_length=4)
    dependencies: tuple[DesignDependencyV2, ...] = Field(max_length=12)
