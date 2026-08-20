"""P7-13 exact package contract with explicit passage endpoint openings.

This contract is deliberately separate from the retained ``DungeonPackage`` 1.1.0
reader.  New generation records the opening in each room wall and the direction a
passage must travel away from that wall; old packages remain byte-for-byte
round-trippable through their original model.
"""

from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from dm_dungeon.contracts.common import (
    ContractModel,
    OpaqueId,
    Visibility,
    ensure_unique_ids,
)
from dm_dungeon.contracts.design_v2 import (
    BarrierIntent,
    EndpointDoorKind,
    VerticalEndpointSide,
)
from dm_dungeon.contracts.geometry import (
    FloorBoundMapElement,
    GridPoint,
    GridSegment,
)
from dm_dungeon.contracts.package import DungeonPackage
from dm_dungeon.contracts.topology import (
    DoorConnection,
    StairConnection,
    VerticalConnection,
)

DUNGEON_PACKAGE_V2_SCHEMA_VERSION = "1.2.0"


class PassageApproachDirection(StrEnum):
    """Direction from a room wall into the attached passage."""

    NORTH = "north"
    EAST = "east"
    SOUTH = "south"
    WEST = "west"


class PassageOpening(ContractModel):
    """One declared room-wall opening used by a P7-13 passage.

    The opening is a one-cell wall segment. ``approach_direction`` points from
    the room through that segment to the first exterior corridor cell.
    """

    id: OpaqueId
    corridor_id: OpaqueId
    room_id: OpaqueId
    segment: GridSegment
    approach_direction: PassageApproachDirection

    @model_validator(mode="after")
    def require_one_cell_directional_segment(self) -> Self:
        dx = self.segment.end.x - self.segment.start.x
        dy = self.segment.end.y - self.segment.start.y
        if abs(dx) + abs(dy) != 1:
            raise ValueError("passage openings require one-cell wall segments")
        if (
            self.approach_direction
            in {
                PassageApproachDirection.NORTH,
                PassageApproachDirection.SOUTH,
            }
            and dy != 0
        ):
            raise ValueError("north/south passage openings require horizontal segments")
        if (
            self.approach_direction
            in {
                PassageApproachDirection.EAST,
                PassageApproachDirection.WEST,
            }
            and dx != 0
        ):
            raise ValueError("east/west passage openings require vertical segments")
        return self


class ComposableDoorMechanicsV2(ContractModel):
    """Exact independently retained mechanics on one physical door or hatch.

    This is deliberately separate from the legacy exclusive ``DoorType``. The
    active P7-13d package compiler will consume this shape when it advances the
    root package/generator pin after endpoint-anchor generation exists.
    """

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


class DoorLayoutV2(FloorBoundMapElement):
    """Exact same-floor direct-door opening with composable mechanics."""

    connection_id: OpaqueId
    segment: GridSegment
    connects_room_ids: tuple[OpaqueId, OpaqueId]
    from_hidden: bool = False
    to_hidden: bool = False
    mechanics: ComposableDoorMechanicsV2 = ComposableDoorMechanicsV2()

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


class RoomMechanicMarkerKindV2(StrEnum):
    """Trusted in-room symbols with stable compiler-assigned identities."""

    TRAP = "trap"
    PUZZLE = "puzzle"
    FEATURE = "feature"


class RoomMechanicMarkerV2(FloorBoundMapElement):
    """Exact in-room anchor for a trap, puzzle control, or physical feature.

    The marker contains no model-authored prose or solution. Its stable ID matches
    the compiled mechanics-plan record; the Workbench owns keyed guide text.
    """

    room_id: OpaqueId
    position: GridPoint
    kind: RoomMechanicMarkerKindV2


class VerticalEndpointDoorLayoutV2(ContractModel):
    """A door/hatch at exactly one source or destination vertical endpoint."""

    id: OpaqueId
    layer_id: OpaqueId
    vertical_link_id: OpaqueId
    endpoint: VerticalEndpointSide
    kind: EndpointDoorKind
    floor_id: OpaqueId
    room_id: OpaqueId
    position: GridPoint
    mechanics: ComposableDoorMechanicsV2 = ComposableDoorMechanicsV2()
    visibility: Visibility = Visibility.DM_ONLY

    @model_validator(mode="after")
    def require_dm_only_mechanics(self) -> Self:
        if self.visibility is not Visibility.DM_ONLY:
            raise ValueError("vertical endpoint doors/hatches must be dm_only")
        return self


class DungeonPackageV2(DungeonPackage):
    """New exact package with retained-artifact-safe passage semantics."""

    supported_schema_version = DUNGEON_PACKAGE_V2_SCHEMA_VERSION

    schema_version: Literal["1.2.0"]  # type: ignore[assignment]
    passage_openings: tuple[PassageOpening, ...] = ()
    # The legacy ``doors`` projection remains available only for the already
    # generated P7-13c packages. New mechanics-aware layout will populate these
    # exact records instead, so no requested independent mechanic is collapsed
    # into the old exclusive DoorType.
    composable_doors: tuple[DoorLayoutV2, ...] = ()
    vertical_endpoint_doors: tuple[VerticalEndpointDoorLayoutV2, ...] = ()
    room_mechanic_markers: tuple[RoomMechanicMarkerV2, ...] = ()

    @model_validator(mode="after")
    def require_complete_passage_openings(self) -> Self:
        ensure_unique_ids(
            {
                "passage_openings": (item.id for item in self.passage_openings),
                "composable_doors": (item.id for item in self.composable_doors),
                "vertical_endpoint_doors": (
                    item.id for item in self.vertical_endpoint_doors
                ),
                "room_mechanic_markers": (
                    item.id for item in self.room_mechanic_markers
                ),
            }
        )
        corridors = {corridor.id: corridor for corridor in self.corridors}
        openings_by_corridor: dict[str, list[PassageOpening]] = {}
        for opening in self.passage_openings:
            corridor = corridors.get(opening.corridor_id)
            if corridor is None:
                raise ValueError(
                    f"passage opening {opening.id!r} references unknown corridor "
                    f"{opening.corridor_id!r}"
                )
            if opening.room_id not in corridor.connects_room_ids:
                raise ValueError(
                    f"passage opening {opening.id!r} room is not connected by "
                    f"corridor {corridor.id!r}"
                )
            openings_by_corridor.setdefault(corridor.id, []).append(opening)

        for corridor in self.corridors:
            openings = openings_by_corridor.get(corridor.id, [])
            if len(openings) != 2 or {item.room_id for item in openings} != set(
                corridor.connects_room_ids
            ):
                raise ValueError(
                    f"corridor {corridor.id!r} requires one passage opening for "
                    "each connected room"
                )

        if self.composable_doors and self.doors:
            raise ValueError(
                "a mechanics-aware package cannot mix legacy and composable door records"
            )
        layers = {item.id: item for item in self.layers}
        layer_ids = set(layers)
        floor_ids = {item.id for item in self.floors}
        room_ids = {item.id for item in self.rooms}
        connections = {item.id: item for item in self.topology.connections}
        links = {item.id: item for item in self.vertical_links}
        for door in self.composable_doors:
            if door.layer_id not in layer_ids or door.floor_id not in floor_ids:
                raise ValueError("composable door references an unknown layer or floor")
            if any(room_id not in room_ids for room_id in door.connects_room_ids):
                raise ValueError("composable door references an unknown room")
            if not isinstance(connections.get(door.connection_id), DoorConnection):
                raise ValueError(
                    "composable door must retain a same-floor door connection ID"
                )
        for endpoint_door in self.vertical_endpoint_doors:
            if endpoint_door.layer_id not in layer_ids:
                raise ValueError("vertical endpoint door references an unknown layer")
            if endpoint_door.room_id not in room_ids:
                raise ValueError("vertical endpoint door references an unknown room")
            link = links.get(endpoint_door.vertical_link_id)
            connection = connections.get(endpoint_door.vertical_link_id)
            if link is None or not isinstance(
                connection, StairConnection | VerticalConnection
            ):
                raise ValueError(
                    "vertical endpoint door must retain a vertical connection ID"
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
            matching_endpoints = [
                endpoint
                for endpoint in link.endpoints
                if endpoint.floor_id == endpoint_door.floor_id
            ]
            if (
                len(matching_endpoints) != 1
                or matching_endpoints[0].position != endpoint_door.position
            ):
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
        for marker in self.room_mechanic_markers:
            room = next(
                (item for item in self.rooms if item.id == marker.room_id), None
            )
            if room is None or room.floor_id != marker.floor_id:
                raise ValueError("room mechanic marker must be anchored in its room")
            layer = layers.get(marker.layer_id)
            if layer is None:
                raise ValueError("room mechanic marker references an unknown layer")
            if marker.visibility is not layer.visibility:
                raise ValueError(
                    "room mechanic marker visibility must match its render layer"
                )
            if marker.visibility is not (
                Visibility.DM_ONLY
                if (
                    marker.kind is RoomMechanicMarkerKindV2.TRAP
                    or room.visibility is Visibility.DM_ONLY
                )
                else Visibility.PLAYER_SAFE
            ):
                raise ValueError("room mechanic marker uses an invalid visibility")
        return self
