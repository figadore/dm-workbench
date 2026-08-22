"""Versioned renderer-neutral dungeon package aggregate."""

from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from dm_dungeon.contracts.brief import DungeonBrief
from dm_dungeon.contracts.common import (
    ContractModel,
    OpaqueId,
    ShortText,
    VersionedContract,
    Visibility,
    ensure_unique_ids,
)
from dm_dungeon.contracts.design import (
    BarrierIntent,
    EndpointDoorKind,
    VerticalEndpointSide,
)
from dm_dungeon.contracts.geometry import (
    CorridorLayout,
    EncounterSlot,
    Feature,
    FloorBoundMapElement,
    FloorLayout,
    GridPoint,
    GridSegment,
    GridSpec,
    Hazard,
    Label,
    LayeredMapElement,
    PositionAnchor,
    RenderLayer,
    RoomBoundMapElement,
    RoomLayout,
    StairLayout,
    Terrain,
    VerticalLinkLayout,
    Zone,
)
from dm_dungeon.contracts.topology import (
    DoorConnection,
    DungeonTopology,
    StairConnection,
    VerticalConnection,
)

DUNGEON_PACKAGE_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"


class ComponentIdStrategy(StrEnum):
    """Pinned source of deterministic generated-component identities."""

    INPUT = "input"
    INPUT_WITH_SHA256_V1_AUXILIARY = "input_with_sha256_v1_auxiliary"
    SHA256_V1 = "sha256_v1"


class PackageMetadata(ContractModel):
    """Deterministic package lineage owned by the pure kernel."""

    generator_name: ShortText
    generator_version: ShortText
    seed: int
    component_id_strategy: ComponentIdStrategy
    parent_package_id: OpaqueId | None = None
    locked_component_ids: tuple[OpaqueId, ...] = ()


class _DungeonPackageCore(VersionedContract):
    """Exact renderer-neutral dungeon geometry and semantic layers."""

    supported_schema_version = DUNGEON_PACKAGE_SCHEMA_VERSION

    schema_version: Literal["1.0.0"]
    id: OpaqueId
    brief: DungeonBrief
    topology: DungeonTopology
    metadata: PackageMetadata
    grid: GridSpec = GridSpec()
    layers: tuple[RenderLayer, ...] = Field(min_length=1)
    floors: tuple[FloorLayout, ...] = Field(min_length=1)
    rooms: tuple[RoomLayout, ...] = Field(min_length=1)
    corridors: tuple[CorridorLayout, ...] = ()
    stairs: tuple[StairLayout, ...] = ()
    vertical_links: tuple[VerticalLinkLayout, ...] = ()
    features: tuple[Feature, ...] = ()
    terrain: tuple[Terrain, ...] = ()
    hazards: tuple[Hazard, ...] = ()
    zones: tuple[Zone, ...] = ()
    labels: tuple[Label, ...] = ()
    encounter_slots: tuple[EncounterSlot, ...] = ()
    position_anchors: tuple[PositionAnchor, ...] = ()

    @model_validator(mode="after")
    def validate_aggregate_structure(self) -> Self:
        self._require_unique_exact_ids()
        self._require_topology_layout_alignment()
        self._require_layer_classification()
        self._require_exact_references()
        return self

    def _require_unique_exact_ids(self) -> None:
        ensure_unique_ids(
            {
                "layers": (item.id for item in self.layers),
                "floors": (item.id for item in self.floors),
                "rooms": (item.id for item in self.rooms),
                "corridors": (item.id for item in self.corridors),
                "stairs": (item.id for item in self.stairs),
                "vertical_links": (item.id for item in self.vertical_links),
                "features": (item.id for item in self.features),
                "terrain": (item.id for item in self.terrain),
                "hazards": (item.id for item in self.hazards),
                "zones": (item.id for item in self.zones),
                "labels": (item.id for item in self.labels),
                "encounter_slots": (item.id for item in self.encounter_slots),
                "position_anchors": (item.id for item in self.position_anchors),
            }
        )

    def _require_topology_layout_alignment(self) -> None:
        topology_floors = {floor.id: floor for floor in self.topology.floors}
        layout_floors = {floor.id: floor for floor in self.floors}
        if topology_floors.keys() != layout_floors.keys():
            raise ValueError("layout floor IDs must exactly match topology floor IDs")

        for floor_id, floor_layout in layout_floors.items():
            topology_floor = topology_floors[floor_id]
            if floor_layout.level_index != topology_floor.level_index:
                raise ValueError(
                    f"floor {floor_id!r} level_index differs from topology"
                )
            if floor_layout.visibility is not topology_floor.visibility:
                raise ValueError(f"floor {floor_id!r} visibility differs from topology")

        topology_rooms = {room.id: room for room in self.topology.rooms}
        layout_rooms = {room.id: room for room in self.rooms}
        if topology_rooms.keys() != layout_rooms.keys():
            raise ValueError("layout room IDs must exactly match topology room IDs")

        for room_id, room_layout in layout_rooms.items():
            topology_room = topology_rooms[room_id]
            if room_layout.floor_id != topology_room.floor_id:
                raise ValueError(f"room {room_id!r} floor differs from topology")
            if room_layout.role is not topology_room.role:
                raise ValueError(f"room {room_id!r} role differs from topology")
            if room_layout.visibility is not topology_room.visibility:
                raise ValueError(f"room {room_id!r} visibility differs from topology")

    def _require_layer_classification(self) -> None:
        layers = {layer.id: layer for layer in self.layers}
        layered_elements: tuple[LayeredMapElement, ...] = (
            *self.floors,
            *self.rooms,
            *self.corridors,
            *self.stairs,
            *self.features,
            *self.terrain,
            *self.hazards,
            *self.zones,
            *self.labels,
            *self.encounter_slots,
            *self.position_anchors,
        )
        for element in layered_elements:
            layer = layers.get(element.layer_id)
            if layer is None:
                raise ValueError(
                    f"component {element.id!r} references unknown layer "
                    f"{element.layer_id!r}"
                )
            if element.visibility is not layer.visibility:
                raise ValueError(
                    f"component {element.id!r} visibility does not match layer "
                    f"{layer.id!r}"
                )

    def _require_exact_references(self) -> None:
        floor_ids = {floor.id for floor in self.floors}
        room_ids = {room.id for room in self.rooms}
        zone_ids = {zone.id for zone in self.zones}
        anchor_ids = {anchor.id for anchor in self.position_anchors}
        stair_by_id = {stair.id: stair for stair in self.stairs}
        link_ids = {link.id for link in self.vertical_links}

        floor_elements: tuple[FloorBoundMapElement, ...] = (
            *self.rooms,
            *self.corridors,
            *self.stairs,
            *self.features,
            *self.terrain,
            *self.hazards,
            *self.zones,
            *self.labels,
            *self.encounter_slots,
            *self.position_anchors,
        )
        for element in floor_elements:
            if element.floor_id not in floor_ids:
                raise ValueError(
                    f"component {element.id!r} references unknown floor "
                    f"{element.floor_id!r}"
                )

        room_bound_elements: tuple[RoomBoundMapElement, ...] = (
            *self.features,
            *self.terrain,
            *self.hazards,
            *self.zones,
            *self.position_anchors,
        )
        for room_bound in room_bound_elements:
            if room_bound.room_id is not None and room_bound.room_id not in room_ids:
                raise ValueError(
                    f"component {room_bound.id!r} references unknown room "
                    f"{room_bound.room_id!r}"
                )

        for corridor in self.corridors:
            self._require_known_rooms(corridor.id, corridor.connects_room_ids, room_ids)

        for stair in self.stairs:
            if stair.vertical_link_id not in link_ids:
                raise ValueError(
                    f"stair {stair.id!r} references unknown vertical link "
                    f"{stair.vertical_link_id!r}"
                )

        for link in self.vertical_links:
            for endpoint in link.endpoints:
                if endpoint.floor_id not in floor_ids:
                    raise ValueError(
                        f"vertical link {link.id!r} references unknown floor "
                        f"{endpoint.floor_id!r}"
                    )
                if endpoint.stair_id is None:
                    continue
                endpoint_stair = stair_by_id.get(endpoint.stair_id)
                if endpoint_stair is None:
                    raise ValueError(
                        f"vertical link {link.id!r} references unknown stair "
                        f"{endpoint.stair_id!r}"
                    )
                if endpoint_stair.floor_id != endpoint.floor_id:
                    raise ValueError(
                        f"vertical link {link.id!r} endpoint floor does not match "
                        f"stair {endpoint_stair.id!r}"
                    )

        for slot in self.encounter_slots:
            if slot.room_id not in room_ids:
                raise ValueError(
                    f"encounter slot {slot.id!r} references unknown room "
                    f"{slot.room_id!r}"
                )
            if slot.zone_id is not None and slot.zone_id not in zone_ids:
                raise ValueError(
                    f"encounter slot {slot.id!r} references unknown zone "
                    f"{slot.zone_id!r}"
                )
            unknown_anchor_ids = set(slot.anchor_ids) - anchor_ids
            if unknown_anchor_ids:
                unknown = sorted(unknown_anchor_ids)[0]
                raise ValueError(
                    f"encounter slot {slot.id!r} references unknown anchor {unknown!r}"
                )

    @staticmethod
    def _require_known_rooms(
        component_id: str,
        referenced_room_ids: tuple[str, str],
        room_ids: set[str],
    ) -> None:
        for room_id in referenced_room_ids:
            if room_id not in room_ids:
                raise ValueError(
                    f"component {component_id!r} references unknown room {room_id!r}"
                )


class PassageApproachDirection(StrEnum):
    """Direction from a room wall into the attached passage."""

    NORTH = "north"
    EAST = "east"
    SOUTH = "south"
    WEST = "west"


class PassageOpening(ContractModel):
    """One declared room-wall opening used by a V1 passage.

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


class DoorMechanics(ContractModel):
    """Exact independently retained mechanics on one physical door or hatch.

    This is deliberately separate from the exclusive ``DoorType``. The
    active mechanics-aware layout attaches this shape to exact shared-wall or
    vertical-endpoint geometry without collapsing independent mechanics.
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


class MechanicDoorLayout(FloorBoundMapElement):
    """Exact same-floor direct-door opening with composable mechanics."""

    connection_id: OpaqueId
    segment: GridSegment
    connects_room_ids: tuple[OpaqueId, OpaqueId]
    from_hidden: bool = False
    to_hidden: bool = False
    mechanics: DoorMechanics = DoorMechanics()

    @model_validator(mode="after")
    def require_concealment_to_match_endpoint_discovery(self) -> Self:
        if self.mechanics.concealed != (self.from_hidden or self.to_hidden):
            raise ValueError(
                "same-floor door concealment must match at least one hidden endpoint"
            )
        # Geometry may remain player-publishable while the renderer normalizes all
        # mechanics to an ordinary door. Symmetrically hidden doors are still
        # DM-only because endpoint/room publication makes their layout DM-only.
        return self


class RoomMechanicMarkerKind(StrEnum):
    """Trusted in-room symbols with stable compiler-assigned identities."""

    TRAP = "trap"
    PUZZLE = "puzzle"
    FEATURE = "feature"
    OBJECTIVE = "objective"


class RoomMechanicMarker(FloorBoundMapElement):
    """Exact in-room anchor for a trap, puzzle control, or physical feature.

    The marker contains no model-authored prose or solution. Its stable ID matches
    the compiled mechanics-plan record; the Workbench owns keyed guide text.
    """

    room_id: OpaqueId
    position: GridPoint
    kind: RoomMechanicMarkerKind


class VerticalEndpointDoorLayout(FloorBoundMapElement):
    """A door/hatch at exactly one source or destination vertical endpoint."""

    vertical_link_id: OpaqueId
    endpoint: VerticalEndpointSide
    kind: EndpointDoorKind
    room_id: OpaqueId
    position: GridPoint
    mechanics: DoorMechanics = DoorMechanics()

    @model_validator(mode="after")
    def require_concealed_endpoint_to_be_dm_only(self) -> Self:
        if self.mechanics.concealed and self.visibility is not Visibility.DM_ONLY:
            raise ValueError(
                "concealed vertical endpoint doors/hatches must be dm_only"
            )
        return self


class DungeonPackage(_DungeonPackageCore):
    """Sole alpha V1 exact package with explicit passage and mechanics geometry."""

    supported_schema_version = DUNGEON_PACKAGE_SCHEMA_VERSION

    schema_version: Literal["1.0.0"]
    passage_openings: tuple[PassageOpening, ...] = ()
    composable_doors: tuple[MechanicDoorLayout, ...] = ()
    vertical_endpoint_doors: tuple[VerticalEndpointDoorLayout, ...] = ()
    room_mechanic_markers: tuple[RoomMechanicMarker, ...] = ()

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

        layers = {item.id: item for item in self.layers}
        layer_ids = set(layers)
        floor_ids = {item.id for item in self.floors}
        room_ids = {item.id for item in self.rooms}
        connections = {item.id: item for item in self.topology.connections}
        links = {item.id: item for item in self.vertical_links}
        for door in self.composable_doors:
            if door.layer_id not in layer_ids or door.floor_id not in floor_ids:
                raise ValueError("composable door references an unknown layer or floor")
            if door.visibility is not layers[door.layer_id].visibility:
                raise ValueError(
                    "composable door visibility does not match its render layer"
                )
            if any(room_id not in room_ids for room_id in door.connects_room_ids):
                raise ValueError("composable door references an unknown room")
            if not isinstance(connections.get(door.connection_id), DoorConnection):
                raise ValueError(
                    "composable door must retain a same-floor door connection ID"
                )
        for endpoint_door in self.vertical_endpoint_doors:
            layer = layers.get(endpoint_door.layer_id)
            if layer is None:
                raise ValueError("vertical endpoint door references an unknown layer")
            if endpoint_door.visibility is not layer.visibility:
                raise ValueError(
                    "vertical endpoint door visibility must match its render layer"
                )
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
                    marker.kind is RoomMechanicMarkerKind.TRAP
                    or room.visibility is Visibility.DM_ONLY
                )
                else Visibility.PLAYER_SAFE
            ):
                raise ValueError("room mechanic marker uses an invalid visibility")
        return self
