"""Compact, model-independent V2 dungeon-design contracts.

These contracts intentionally contain only bounded creative relative intent. The
compiler, not a caller or model, assigns every kernel ID, exact geometry,
visibility classification, and numeric mechanics value.
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
from dm_dungeon.contracts.topology import RoomRole

DUNGEON_DESIGN_V2_SCHEMA_VERSION: Literal["2.2.0"] = "2.2.0"
LocalRef = Annotated[
    str,
    Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_-]*$"),
]
ThemeText = Annotated[str, Field(min_length=1, max_length=96)]
TagText = Annotated[str, Field(min_length=1, max_length=48)]


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


class BarrierIntent(StrEnum):
    NONE = "none"
    LOCKED = "locked"
    PUZZLE = "puzzle"


class HazardIntent(StrEnum):
    NONE = "none"
    TRAPPED = "trapped"


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


class ObjectiveKind(StrEnum):
    FINAL_OBJECTIVE = "final_objective"
    OPTIONAL_OBJECTIVE = "optional_objective"


class DependencyKind(StrEnum):
    KEY = "key"
    CLUE = "clue"


class DoorMechanicsIntentV2(ContractModel):
    """Composable mechanics on one physical door or hatch.

    ``concealed`` describes the physical barrier. Directional concealment of a
    bare vertical connection remains on ``from_hidden`` / ``to_hidden``.
    """

    concealed: bool = False
    barrier: BarrierIntent = BarrierIntent.NONE
    hazard: HazardIntent = HazardIntent.NONE
    challenge: ChallengeBand | None = None

    @model_validator(mode="after")
    def require_challenge_for_active_mechanic(self) -> Self:
        active = (
            self.concealed
            or self.barrier is not BarrierIntent.NONE
            or self.hazard is not HazardIntent.NONE
        )
        if active and self.challenge is None:
            raise ValueError(
                "concealed, barrier, or trap mechanics require a relative challenge band"
            )
        if not active and self.challenge is not None:
            raise ValueError(
                "a challenge band requires a concealed, barrier, or trap mechanic"
            )
        return self


class DesignRoomV2(ContractModel):
    local_ref: LocalRef
    name: ShortText
    role: RoomRole
    room_size: RoomSizeBand = RoomSizeBand.MEDIUM
    occupancy: OccupancyBand = OccupancyBand.GROUP
    optional: bool = False
    tags: tuple[TagText, ...] = Field(default=(), max_length=8)
    preparation_note: NonEmptyText | None = None
    encounter_slot: EncounterSlotIntent | None = None


class DesignFloorV2(ContractModel):
    local_ref: LocalRef
    name: ShortText
    floor_scale: FloorScale = FloorScale.SMALL
    rooms: tuple[DesignRoomV2, ...] = Field(min_length=1, max_length=12)


class DesignVerticalEndpointDoorV2(ContractModel):
    """One explicitly located vertical-link endpoint door/hatch intent.

    Pure deterministic code selects its anchor in the named endpoint room. The
    local ref is the dependency target for any lock or puzzle gate.
    """

    local_ref: LocalRef
    endpoint: VerticalEndpointSide
    kind: EndpointDoorKind
    mechanics: DoorMechanicsIntentV2 = DoorMechanicsIntentV2()


class DesignConnectionV2(ContractModel):
    """A bounded creative connection with the P7-13d capability matrix."""

    local_ref: LocalRef
    from_ref: LocalRef
    to_ref: LocalRef
    passage: PassageType = PassageType.PASSAGE
    from_hidden: bool = False
    to_hidden: bool = False
    door_mechanics: DoorMechanicsIntentV2 = DoorMechanicsIntentV2()
    endpoint_doors: tuple[DesignVerticalEndpointDoorV2, ...] = Field(
        default=(), max_length=2
    )

    @model_validator(mode="after")
    def enforce_local_capability_matrix(self) -> Self:
        mechanics_requested = self.door_mechanics != DoorMechanicsIntentV2()
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


class DesignObjectiveV2(ContractModel):
    room_ref: LocalRef
    kind: ObjectiveKind


class DesignDependencyV2(ContractModel):
    """A key or clue targeting a door or explicit endpoint door/hatch."""

    local_ref: LocalRef
    kind: DependencyKind
    target_ref: LocalRef
    located_in_room_ref: LocalRef
    name: ShortText


class DesignTrapV2(ContractModel):
    """A room-local trap/hazard whose required play details are explicit."""

    local_ref: LocalRef
    room_ref: LocalRef
    name: ShortText
    trigger: NonEmptyText
    effect: NonEmptyText
    challenge: ChallengeBand


class DesignPuzzleV2(ContractModel):
    """A puzzle is incomplete unless the proposal states its solution."""

    local_ref: LocalRef
    room_ref: LocalRef
    name: ShortText
    mechanism: NonEmptyText
    clue_refs: tuple[LocalRef, ...] = Field(max_length=8)
    solution: NonEmptyText
    consequence: NonEmptyText
    challenge: ChallengeBand


class DesignFeatureV2(ContractModel):
    local_ref: LocalRef
    room_ref: LocalRef
    kind: FeatureIntentKind
    name: ShortText
    description: NonEmptyText


class DesignLoopRequirementV2(ContractModel):
    local_ref: LocalRef
    room_refs: tuple[LocalRef, ...] = Field(min_length=3, max_length=8)


class DesignBranchRequirementV2(ContractModel):
    local_ref: LocalRef
    junction_room_ref: LocalRef
    branch_room_refs: tuple[LocalRef, ...] = Field(min_length=2, max_length=8)


class DungeonDesignSpecV2(VersionedContract):
    """Strict compact creative intent accepted by the active V2 compiler."""

    supported_schema_version = DUNGEON_DESIGN_V2_SCHEMA_VERSION

    schema_version: Literal["2.2.0"]
    title: ShortText
    premise: NonEmptyText
    purpose: DungeonPurpose = DungeonPurpose.RUIN
    themes: tuple[ThemeText, ...] = Field(min_length=1, max_length=8)
    pacing: PacingStyle = PacingStyle.BALANCED
    tones: tuple[ThemeText, ...] = Field(default=(), max_length=4)
    floors: tuple[DesignFloorV2, ...] = Field(min_length=1, max_length=4)
    connections: tuple[DesignConnectionV2, ...] = Field(default=(), max_length=24)
    objectives: tuple[DesignObjectiveV2, ...] = Field(default=(), max_length=4)
    dependencies: tuple[DesignDependencyV2, ...] = Field(default=(), max_length=12)
    traps: tuple[DesignTrapV2, ...] = Field(default=(), max_length=12)
    puzzles: tuple[DesignPuzzleV2, ...] = Field(default=(), max_length=8)
    features: tuple[DesignFeatureV2, ...] = Field(default=(), max_length=24)
    loops: tuple[DesignLoopRequirementV2, ...] = Field(default=(), max_length=4)
    branches: tuple[DesignBranchRequirementV2, ...] = Field(default=(), max_length=4)
