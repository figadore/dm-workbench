"""P7-13d exact package extension for composable barriers and vertical hatches.

The retained 1.1.0 and 1.2.0 package readers deliberately keep their exclusive
``DoorType`` representation.  This root contract is the new exact representation:
mechanics are independent records and an endpoint door/hatch is distinct from the
stairs or ladder that it controls.
"""

from typing import Literal, Self

from pydantic import Field, model_validator

from dm_dungeon.contracts.brief import DungeonBrief
from dm_dungeon.contracts.common import (
    ContractModel,
    OpaqueId,
    VersionedContract,
    Visibility,
    ensure_unique_ids,
)
from dm_dungeon.contracts.design_v2 import BarrierIntent
from dm_dungeon.contracts.design_v3 import EndpointDoorKind, VerticalEndpointSide
from dm_dungeon.contracts.geometry import (
    CorridorLayout,
    EncounterSlot,
    Feature,
    FloorLayout,
    GridPoint,
    GridSegment,
    GridSpec,
    Hazard,
    Label,
    PositionAnchor,
    RenderLayer,
    RoomLayout,
    StairLayout,
    Terrain,
    VerticalLinkLayout,
    Zone,
)
from dm_dungeon.contracts.package import PackageMetadata
from dm_dungeon.contracts.package_v2 import PassageOpening
from dm_dungeon.contracts.topology import (
    DoorConnection,
    DungeonTopology,
    StairConnection,
    VerticalConnection,
)

DUNGEON_PACKAGE_V3_SCHEMA_VERSION = "1.3.0"


class ComposableDoorMechanicsV3(ContractModel):
    """Exact independently retained mechanics on a physical door or hatch."""

    concealed: bool = False
    gate_id: OpaqueId | None = None
    gate_kind: BarrierIntent = BarrierIntent.NONE
    trap_id: OpaqueId | None = None
    discovery_difficulty: int | None = Field(default=None, ge=0)
    unlock_difficulty: int | None = Field(default=None, ge=0)
    disable_difficulty: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def require_complete_independent_mechanics(self) -> Self:
        if (self.gate_id is None) != (self.gate_kind is BarrierIntent.NONE):
            raise ValueError("gate_id and gate_kind must be present together")
        if self.concealed != (self.discovery_difficulty is not None):
            raise ValueError("concealment must have exactly one discovery difficulty")
        if (self.gate_id is not None) != (self.unlock_difficulty is not None):
            raise ValueError("a gate must have exactly one unlock difficulty")
        if (self.trap_id is not None) != (self.disable_difficulty is not None):
            raise ValueError("a trap must have exactly one disable difficulty")
        return self


class DoorLayoutV3(ContractModel):
    """A same-floor direct-door opening with all requested mechanics retained."""

    id: OpaqueId
    layer_id: OpaqueId
    floor_id: OpaqueId
    segment: GridSegment
    connects_room_ids: tuple[OpaqueId, OpaqueId]
    from_hidden: bool = False
    to_hidden: bool = False
    mechanics: ComposableDoorMechanicsV3 = ComposableDoorMechanicsV3()
    visibility: Visibility

    @model_validator(mode="after")
    def require_concealment_to_match_endpoint_discovery(self) -> Self:
        if self.mechanics.concealed != (self.from_hidden or self.to_hidden):
            raise ValueError(
                "same-floor door concealment must match at least one hidden endpoint"
            )
        if self.mechanics.concealed or self.mechanics.trap_id is not None:
            if self.visibility is not Visibility.DM_ONLY:
                raise ValueError("concealed or trapped doors must be dm_only")
        return self


class VerticalEndpointDoorLayoutV3(ContractModel):
    """A door/hatch anchored at exactly one source or destination transition end."""

    id: OpaqueId
    layer_id: OpaqueId
    vertical_link_id: OpaqueId
    endpoint: VerticalEndpointSide
    kind: EndpointDoorKind
    floor_id: OpaqueId
    room_id: OpaqueId
    position: GridPoint
    mechanics: ComposableDoorMechanicsV3 = ComposableDoorMechanicsV3()
    visibility: Visibility = Visibility.DM_ONLY

    @model_validator(mode="after")
    def require_dm_only_mechanics(self) -> Self:
        if self.visibility is not Visibility.DM_ONLY:
            raise ValueError("vertical endpoint doors/hatches must be dm_only")
        return self


class DungeonPackageV3(VersionedContract):
    """Exact P7-13d package; it never reinterprets pre-V3 package JSON."""

    supported_schema_version = DUNGEON_PACKAGE_V3_SCHEMA_VERSION

    schema_version: Literal["1.3.0"]
    id: OpaqueId
    brief: DungeonBrief
    topology: DungeonTopology
    metadata: PackageMetadata
    grid: GridSpec = GridSpec()
    layers: tuple[RenderLayer, ...] = Field(min_length=1)
    floors: tuple[FloorLayout, ...] = Field(min_length=1)
    rooms: tuple[RoomLayout, ...] = Field(min_length=1)
    corridors: tuple[CorridorLayout, ...] = ()
    doors: tuple[DoorLayoutV3, ...] = ()
    stairs: tuple[StairLayout, ...] = ()
    vertical_links: tuple[VerticalLinkLayout, ...] = ()
    vertical_endpoint_doors: tuple[VerticalEndpointDoorLayoutV3, ...] = ()
    passage_openings: tuple[PassageOpening, ...] = ()
    features: tuple[Feature, ...] = ()
    terrain: tuple[Terrain, ...] = ()
    hazards: tuple[Hazard, ...] = ()
    zones: tuple[Zone, ...] = ()
    labels: tuple[Label, ...] = ()
    encounter_slots: tuple[EncounterSlot, ...] = ()
    position_anchors: tuple[PositionAnchor, ...] = ()

    @model_validator(mode="after")
    def require_exact_mechanics_references(self) -> Self:
        ensure_unique_ids(
            {
                "layers": (item.id for item in self.layers),
                "floors": (item.id for item in self.floors),
                "rooms": (item.id for item in self.rooms),
                "corridors": (item.id for item in self.corridors),
                "doors": (item.id for item in self.doors),
                "stairs": (item.id for item in self.stairs),
                "vertical_links": (item.id for item in self.vertical_links),
                "vertical_endpoint_doors": (
                    item.id for item in self.vertical_endpoint_doors
                ),
                "passage_openings": (item.id for item in self.passage_openings),
                "features": (item.id for item in self.features),
                "terrain": (item.id for item in self.terrain),
                "hazards": (item.id for item in self.hazards),
                "zones": (item.id for item in self.zones),
                "labels": (item.id for item in self.labels),
                "encounter_slots": (item.id for item in self.encounter_slots),
                "position_anchors": (item.id for item in self.position_anchors),
            }
        )
        layer_ids = {item.id for item in self.layers}
        floor_ids = {item.id for item in self.floors}
        rooms = {item.id: item for item in self.rooms}
        connections = {item.id: item for item in self.topology.connections}
        links = {item.id: item for item in self.vertical_links}
        for door in self.doors:
            if door.layer_id not in layer_ids or door.floor_id not in floor_ids:
                raise ValueError("door references an unknown layer or floor")
            if any(room_id not in rooms for room_id in door.connects_room_ids):
                raise ValueError("door references an unknown room")
            connection = connections.get(door.id)
            if not isinstance(connection, DoorConnection):
                raise ValueError("door must retain a same-floor door connection ID")
        for endpoint_door in self.vertical_endpoint_doors:
            if endpoint_door.layer_id not in layer_ids:
                raise ValueError("vertical endpoint door references an unknown layer")
            room = rooms.get(endpoint_door.room_id)
            if room is None or room.floor_id != endpoint_door.floor_id:
                raise ValueError("vertical endpoint door must be anchored in its room")
            link = links.get(endpoint_door.vertical_link_id)
            connection = connections.get(endpoint_door.vertical_link_id)
            if link is None or not isinstance(
                connection, StairConnection | VerticalConnection
            ):
                raise ValueError(
                    "vertical endpoint door must retain a vertical topology connection ID"
                )
            expected_floor = (
                connection.from_floor_id
                if endpoint_door.endpoint is VerticalEndpointSide.FROM
                else connection.to_floor_id
            )
            expected_room = (
                connection.from_room_id
                if endpoint_door.endpoint is VerticalEndpointSide.FROM
                else connection.to_room_id
            )
            if (
                endpoint_door.floor_id != expected_floor
                or endpoint_door.room_id != expected_room
            ):
                raise ValueError(
                    "vertical endpoint door endpoint must match its directional connection side"
                )
            matching = [
                item
                for item in link.endpoints
                if item.floor_id == endpoint_door.floor_id
            ]
            if len(matching) != 1 or matching[0].position != endpoint_door.position:
                raise ValueError(
                    "vertical endpoint door must use its link endpoint's exact position"
                )
        endpoint_keys = [
            (item.vertical_link_id, item.endpoint)
            for item in self.vertical_endpoint_doors
        ]
        if len(endpoint_keys) != len(set(endpoint_keys)):
            raise ValueError(
                "each vertical-link endpoint may have at most one door/hatch"
            )
        return self
