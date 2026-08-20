"""Retained-artifact-safe P7-13d creative intent contract.

V3 deliberately does not replace ``DungeonDesignSpecV2``.  It records the full
connection-mechanics matrix before any geometry is chosen: same-floor doors may
combine concealment, a gate, and a trap; vertical links use explicit endpoint
doors/hatches for those mechanics.  The model supplies only local refs and bounded
creative intent.  A future compiler assigns opaque IDs, geometry, visibility, and
numeric mechanics values.
"""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from dm_dungeon.contracts.brief import DungeonPurpose, PacingStyle
from dm_dungeon.contracts.common import (
    ContractModel,
    NonEmptyText,
    ShortText,
    VersionedContract,
)
from dm_dungeon.contracts.design_v2 import (
    BarrierIntent,
    DependencyKind,
    FloorScale,
    HazardIntent,
    ObjectiveKind,
    OccupancyBand,
    PassageType,
    RoomSizeBand,
)
from dm_dungeon.contracts.topology import RoomRole

DUNGEON_DESIGN_V3_SCHEMA_VERSION: Literal["3.0.0"] = "3.0.0"
LocalRef = Annotated[
    str,
    Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_-]*$"),
]
ThemeText = Annotated[str, Field(min_length=1, max_length=96)]
TagText = Annotated[str, Field(min_length=1, max_length=48)]


class ChallengeBand(StrEnum):
    """Relative challenge chosen by the author, never a numeric DC."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class VerticalEndpointSide(StrEnum):
    """The explicitly named endpoint of a directional vertical transition."""

    FROM = "from"
    TO = "to"


class EndpointDoorKind(StrEnum):
    """Physical barrier at a vertical-link endpoint, never the link itself."""

    DOOR = "door"
    HATCH = "hatch"


class FeatureIntentKind(StrEnum):
    ALTAR = "altar"
    BRIDGE = "bridge"
    FURNITURE = "furniture"
    PILLAR = "pillar"
    PIT = "pit"
    STATUE = "statue"
    OTHER = "other"


class EncounterSlotIntent(StrEnum):
    AMBUSH = "ambush"
    COMBAT = "combat"
    SOCIAL = "social"
    EXPLORATION = "exploration"


class DoorMechanicsIntentV3(ContractModel):
    """Composable mechanics on one physical door or hatch.

    ``concealed`` is local to this physical barrier.  Directional concealment of a
    bare connection is recorded separately by ``from_hidden`` / ``to_hidden``.
    """

    concealed: bool = False
    barrier: BarrierIntent = BarrierIntent.NONE
    hazard: HazardIntent = HazardIntent.NONE
    challenge: ChallengeBand | None = None

    @model_validator(mode="after")
    def require_challenge_for_active_mechanic(self) -> Self:
        active = (
            self.barrier is not BarrierIntent.NONE
            or self.hazard is not HazardIntent.NONE
        )
        if active and self.challenge is None:
            raise ValueError(
                "barrier or trap mechanics require a relative challenge band"
            )
        if not active and self.challenge is not None:
            raise ValueError("a challenge band requires a barrier or trap mechanic")
        return self


class DesignRoomV3(ContractModel):
    local_ref: LocalRef
    name: ShortText
    role: RoomRole
    room_size: RoomSizeBand = RoomSizeBand.MEDIUM
    occupancy: OccupancyBand = OccupancyBand.GROUP
    optional: bool = False
    tags: tuple[TagText, ...] = Field(default=(), max_length=8)
    preparation_note: NonEmptyText | None = None
    encounter_slot: EncounterSlotIntent | None = None


class DesignFloorV3(ContractModel):
    local_ref: LocalRef
    name: ShortText
    floor_scale: FloorScale = FloorScale.SMALL
    rooms: tuple[DesignRoomV3, ...] = Field(min_length=1, max_length=12)


class DesignVerticalEndpointDoorV3(ContractModel):
    """One explicitly located vertical-link endpoint door/hatch intent.

    Its anchor is deterministically selected in the referenced endpoint room by
    the pure layout compiler; callers cannot provide coordinates.  ``local_ref``
    is the dependency target for any lock/puzzle gate at this endpoint.
    """

    local_ref: LocalRef
    endpoint: VerticalEndpointSide
    kind: EndpointDoorKind
    mechanics: DoorMechanicsIntentV3 = DoorMechanicsIntentV3()


class DesignConnectionV3(ContractModel):
    """A bounded creative connection with the P7-13d capability matrix."""

    local_ref: LocalRef
    from_ref: LocalRef
    to_ref: LocalRef
    passage: PassageType = PassageType.PASSAGE
    from_hidden: bool = False
    to_hidden: bool = False
    door_mechanics: DoorMechanicsIntentV3 = DoorMechanicsIntentV3()
    endpoint_doors: tuple[DesignVerticalEndpointDoorV3, ...] = Field(
        default=(), max_length=2
    )

    @model_validator(mode="after")
    def enforce_local_capability_matrix(self) -> Self:
        mechanics_requested = self.door_mechanics != DoorMechanicsIntentV3()
        vertical = self.passage in {PassageType.STAIRS, PassageType.LADDER}
        if self.passage is PassageType.PASSAGE:
            if (
                self.from_hidden
                or self.to_hidden
                or mechanics_requested
                or self.endpoint_doors
            ):
                raise ValueError(
                    "same-floor passages cannot carry hidden, barrier, trap, or endpoint-door mechanics"
                )
        elif self.passage is PassageType.DOOR:
            if self.endpoint_doors:
                raise ValueError(
                    "same-floor doors cannot declare vertical endpoint doors"
                )
            if self.door_mechanics.concealed != (self.from_hidden or self.to_hidden):
                raise ValueError(
                    "same-floor door concealment must name one or more hidden endpoints"
                )
        elif vertical:
            if mechanics_requested:
                raise ValueError(
                    "vertical barriers and traps require explicit endpoint_doors; the transition is not a door"
                )
            endpoints = [item.endpoint for item in self.endpoint_doors]
            if len(endpoints) != len(set(endpoints)):
                raise ValueError(
                    "vertical endpoint doors must name each endpoint at most once"
                )
            for endpoint_door in self.endpoint_doors:
                endpoint_hidden = (
                    self.from_hidden
                    if endpoint_door.endpoint is VerticalEndpointSide.FROM
                    else self.to_hidden
                )
                if endpoint_door.mechanics.concealed and not endpoint_hidden:
                    raise ValueError(
                        "a concealed vertical endpoint door/hatch requires its endpoint to be hidden"
                    )
        return self


class DesignDependencyV3(ContractModel):
    """A key/clue dependency targeting a door or explicit endpoint door/hatch."""

    local_ref: LocalRef
    kind: DependencyKind
    target_ref: LocalRef
    located_in_room_ref: LocalRef
    name: ShortText


class DesignTrapV3(ContractModel):
    """A room-local trap/hazard whose required play details are explicit."""

    local_ref: LocalRef
    room_ref: LocalRef
    name: ShortText
    trigger: NonEmptyText
    effect: NonEmptyText
    challenge: ChallengeBand


class DesignPuzzleV3(ContractModel):
    """A puzzle is incomplete unless the proposal states its solution."""

    local_ref: LocalRef
    room_ref: LocalRef
    name: ShortText
    mechanism: NonEmptyText
    clue_refs: tuple[LocalRef, ...] = Field(max_length=8)
    solution: NonEmptyText
    consequence: NonEmptyText
    challenge: ChallengeBand


class DesignFeatureV3(ContractModel):
    local_ref: LocalRef
    room_ref: LocalRef
    kind: FeatureIntentKind
    name: ShortText
    description: NonEmptyText


class DesignObjectiveV3(ContractModel):
    room_ref: LocalRef
    kind: ObjectiveKind


class DesignLoopRequirementV3(ContractModel):
    local_ref: LocalRef
    room_refs: tuple[LocalRef, ...] = Field(min_length=3, max_length=8)


class DesignBranchRequirementV3(ContractModel):
    local_ref: LocalRef
    junction_room_ref: LocalRef
    branch_room_refs: tuple[LocalRef, ...] = Field(min_length=2, max_length=8)


class DungeonDesignSpecV3(VersionedContract):
    """Strict P7-13d creative intent; retained V2 readers remain unchanged."""

    supported_schema_version = DUNGEON_DESIGN_V3_SCHEMA_VERSION

    schema_version: Literal["3.0.0"]
    title: ShortText
    premise: NonEmptyText
    purpose: DungeonPurpose = DungeonPurpose.RUIN
    themes: tuple[ThemeText, ...] = Field(min_length=1, max_length=8)
    pacing: PacingStyle = PacingStyle.BALANCED
    tones: tuple[ThemeText, ...] = Field(default=(), max_length=4)
    floors: tuple[DesignFloorV3, ...] = Field(min_length=1, max_length=4)
    connections: tuple[DesignConnectionV3, ...] = Field(default=(), max_length=24)
    objectives: tuple[DesignObjectiveV3, ...] = Field(default=(), max_length=4)
    dependencies: tuple[DesignDependencyV3, ...] = Field(default=(), max_length=12)
    traps: tuple[DesignTrapV3, ...] = Field(default=(), max_length=12)
    puzzles: tuple[DesignPuzzleV3, ...] = Field(default=(), max_length=8)
    features: tuple[DesignFeatureV3, ...] = Field(default=(), max_length=24)
    loops: tuple[DesignLoopRequirementV3, ...] = Field(default=(), max_length=4)
    branches: tuple[DesignBranchRequirementV3, ...] = Field(default=(), max_length=4)
