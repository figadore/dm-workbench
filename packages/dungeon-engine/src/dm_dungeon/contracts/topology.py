"""Versioned dungeon topology and gating contracts."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from dm_dungeon.contracts.common import (
    ContractModel,
    NonEmptyText,
    OpaqueId,
    ShortText,
    VersionedContract,
    Visibility,
    VisibleContract,
    ensure_unique_ids,
)

DUNGEON_TOPOLOGY_SCHEMA_VERSION = "1.0.0"
PositiveCells = Annotated[int, Field(ge=1)]
NonNegativeCount = Annotated[int, Field(ge=0)]
PositiveCount = Annotated[int, Field(ge=1)]


class RoomRole(StrEnum):
    """Mechanical/narrative role of a topology room."""

    BOSS = "boss"
    COMBAT = "combat"
    ENTRANCE = "entrance"
    EXIT = "exit"
    EXPLORATION = "exploration"
    HUB = "hub"
    OPTIONAL = "optional"
    PUZZLE = "puzzle"
    SET_PIECE = "set_piece"
    SOCIAL = "social"
    TRANSITION = "transition"
    TREASURE = "treasure"
    UTILITY = "utility"


class DoorType(StrEnum):
    """Supported initial door intents."""

    NORMAL = "normal"
    LOCKED = "locked"
    TRAPPED = "trapped"
    SECRET = "secret"


class VerticalLinkKind(StrEnum):
    """Ways two floor positions can connect."""

    CHUTE = "chute"
    ELEVATOR = "elevator"
    LADDER = "ladder"
    PORTAL = "portal"
    SHAFT = "shaft"
    STAIRS = "stairs"


class StairDirection(StrEnum):
    """Direction advertised by a stair marker."""

    BOTH = "both"
    DOWN = "down"
    UP = "up"


class RoomCapacity(ContractModel):
    """Occupancy targets used later by deterministic capacity checks."""

    minimum_occupants: NonNegativeCount
    comfortable_occupants: NonNegativeCount
    maximum_occupants: NonNegativeCount

    @model_validator(mode="after")
    def validate_bounds(self) -> Self:
        if self.minimum_occupants > self.comfortable_occupants:
            raise ValueError("minimum_occupants cannot exceed comfortable_occupants")
        if self.comfortable_occupants > self.maximum_occupants:
            raise ValueError("comfortable_occupants cannot exceed maximum_occupants")
        return self


class RoomSizeConstraints(ContractModel):
    """Orthogonal room-size bounds expressed in whole grid cells."""

    minimum_width_cells: PositiveCells
    maximum_width_cells: PositiveCells | None = None
    minimum_height_cells: PositiveCells
    maximum_height_cells: PositiveCells | None = None
    minimum_area_cells: PositiveCells
    maximum_area_cells: PositiveCells | None = None

    @model_validator(mode="after")
    def validate_bounds(self) -> Self:
        pairs = (
            (
                "minimum_width_cells",
                self.minimum_width_cells,
                "maximum_width_cells",
                self.maximum_width_cells,
            ),
            (
                "minimum_height_cells",
                self.minimum_height_cells,
                "maximum_height_cells",
                self.maximum_height_cells,
            ),
            (
                "minimum_area_cells",
                self.minimum_area_cells,
                "maximum_area_cells",
                self.maximum_area_cells,
            ),
        )
        for minimum_name, minimum, maximum_name, maximum in pairs:
            if maximum is not None and minimum > maximum:
                raise ValueError(f"{minimum_name} cannot exceed {maximum_name}")
        return self


class TopologyFloor(VisibleContract):
    """A floor requested by the topology graph and published on discovery."""

    # Floors are revealed as units. Secrets control access and individual map
    # elements, never whether a discovered floor has a clean player map.
    visibility: Literal[Visibility.PLAYER_SAFE]
    id: OpaqueId
    name: ShortText
    level_index: int
    target_room_count: PositiveCount


class TopologyRoom(VisibleContract):
    """A room node before exact geometry exists."""

    id: OpaqueId
    floor_id: OpaqueId
    # A concise human-facing name; prose-heavy room notes remain in the
    # Workbench preparation layer rather than the deterministic kernel.
    name: ShortText | None = None
    role: RoomRole
    required: bool
    size: RoomSizeConstraints
    capacity: RoomCapacity
    tags: tuple[ShortText, ...] = ()


class ConnectionBase(VisibleContract):
    """Shared room-to-room connection fields."""

    id: OpaqueId
    from_room_id: OpaqueId
    to_room_id: OpaqueId


class CorridorConnection(ConnectionBase):
    """A same-floor corridor intent."""

    kind: Literal["corridor"]
    minimum_width_cells: PositiveCells = 1


class DoorConnection(ConnectionBase):
    """A typed door intent between two rooms."""

    kind: Literal["door"]
    door_type: DoorType
    gate_id: OpaqueId | None = None
    trap_id: OpaqueId | None = None

    @model_validator(mode="after")
    def validate_door_requirements(self) -> Self:
        if self.door_type is DoorType.LOCKED and self.gate_id is None:
            raise ValueError("locked doors require gate_id")
        if self.door_type is DoorType.TRAPPED and self.trap_id is None:
            raise ValueError("trapped doors require trap_id")
        if self.door_type in {DoorType.SECRET, DoorType.TRAPPED}:
            if self.visibility is not Visibility.DM_ONLY:
                raise ValueError("secret and trapped doors must be dm_only")
        return self


class StairConnection(ConnectionBase):
    """A topology connection realized by stairs."""

    kind: Literal["stairs"]
    from_floor_id: OpaqueId
    to_floor_id: OpaqueId
    direction: StairDirection = StairDirection.BOTH


class VerticalConnection(ConnectionBase):
    """A non-stair topology connection between floors."""

    kind: Literal["vertical_link"]
    from_floor_id: OpaqueId
    to_floor_id: OpaqueId
    link_type: VerticalLinkKind


type TopologyConnection = Annotated[
    CorridorConnection | DoorConnection | StairConnection | VerticalConnection,
    Field(discriminator="kind"),
]


class GateDependencyKind(StrEnum):
    """Kinds of prerequisites a gate can require."""

    CLUE = "clue"
    GATE = "gate"
    KEY = "key"


class GateKind(StrEnum):
    """Kinds of progression gates represented in topology."""

    HAZARD = "hazard"
    LOCK = "lock"
    NARRATIVE = "narrative"
    PUZZLE = "puzzle"


class GateDependency(ContractModel):
    """A typed dependency edge evaluated by the P7-03 validator."""

    kind: GateDependencyKind
    target_id: OpaqueId


class Gate(VisibleContract):
    """A progression constraint blocking one or more connections."""

    id: OpaqueId
    name: ShortText
    kind: GateKind
    blocks_connection_ids: tuple[OpaqueId, ...] = Field(min_length=1)
    requires_all: tuple[GateDependency, ...] = ()


class KeyPlacement(VisibleContract):
    """A key-like object placed in a topology room."""

    id: OpaqueId
    name: ShortText
    located_in_room_id: OpaqueId
    opens_gate_ids: tuple[OpaqueId, ...] = Field(min_length=1)


class CluePlacement(VisibleContract):
    """A clue placed in a topology room."""

    id: OpaqueId
    name: ShortText
    text: NonEmptyText
    located_in_room_id: OpaqueId
    supports_gate_ids: tuple[OpaqueId, ...] = Field(min_length=1)


class LoopRequirement(VisibleContract):
    """A requested cycle through a sequence of rooms."""

    id: OpaqueId
    room_ids: tuple[OpaqueId, ...] = Field(min_length=3)


class BranchRequirement(VisibleContract):
    """A requested branch from a junction to multiple destinations."""

    id: OpaqueId
    junction_room_id: OpaqueId
    branch_room_ids: tuple[OpaqueId, ...] = Field(min_length=2)


class ChokepointComponentKind(StrEnum):
    """Kinds of graph components requested as chokepoints."""

    CONNECTION = "connection"
    ROOM = "room"


class ChokepointRequirement(VisibleContract):
    """A component expected to separate two graph regions when removed."""

    id: OpaqueId
    component_kind: ChokepointComponentKind
    component_id: OpaqueId
    separates_room_ids: tuple[OpaqueId, OpaqueId]


class SecretBypass(VisibleContract):
    """A hidden route intended to bypass one or more gates."""

    id: OpaqueId
    entry_room_id: OpaqueId
    exit_room_id: OpaqueId
    connection_ids: tuple[OpaqueId, ...] = Field(min_length=1)
    bypassed_gate_ids: tuple[OpaqueId, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def require_dm_visibility(self) -> Self:
        if self.visibility is not Visibility.DM_ONLY:
            raise ValueError("secret bypasses must be dm_only")
        return self


class DungeonTopology(VersionedContract):
    """A versioned room graph and its progression dependencies."""

    supported_schema_version = DUNGEON_TOPOLOGY_SCHEMA_VERSION

    schema_version: Literal["1.0.0"]
    id: OpaqueId
    visibility: Visibility
    floors: tuple[TopologyFloor, ...] = Field(min_length=1)
    rooms: tuple[TopologyRoom, ...] = Field(min_length=1)
    connections: tuple[TopologyConnection, ...] = ()
    gates: tuple[Gate, ...] = ()
    keys: tuple[KeyPlacement, ...] = ()
    clues: tuple[CluePlacement, ...] = ()
    loops: tuple[LoopRequirement, ...] = ()
    branches: tuple[BranchRequirement, ...] = ()
    chokepoints: tuple[ChokepointRequirement, ...] = ()
    secret_bypasses: tuple[SecretBypass, ...] = ()

    @model_validator(mode="after")
    def require_unique_component_ids(self) -> Self:
        ensure_unique_ids(
            {
                "floors": (item.id for item in self.floors),
                "rooms": (item.id for item in self.rooms),
                "connections": (item.id for item in self.connections),
                "gates": (item.id for item in self.gates),
                "keys": (item.id for item in self.keys),
                "clues": (item.id for item in self.clues),
                "loops": (item.id for item in self.loops),
                "branches": (item.id for item in self.branches),
                "chokepoints": (item.id for item in self.chokepoints),
                "secret_bypasses": (item.id for item in self.secret_bypasses),
            }
        )
        rooms = {room.id: room for room in self.rooms}
        for connection in self.connections:
            if connection.visibility is not Visibility.PLAYER_SAFE:
                continue
            hidden_endpoints = tuple(
                room_id
                for room_id in (connection.from_room_id, connection.to_room_id)
                if (room := rooms.get(room_id)) is not None
                and room.visibility is not Visibility.PLAYER_SAFE
            )
            if hidden_endpoints:
                raise ValueError(
                    "player_safe connections cannot connect to dm_only rooms: "
                    f"{connection.id!r} references {hidden_endpoints!r}"
                )
        return self
