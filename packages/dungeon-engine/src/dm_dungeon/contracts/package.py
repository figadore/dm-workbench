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
    ensure_unique_ids,
)
from dm_dungeon.contracts.geometry import (
    CorridorLayout,
    DoorLayout,
    EncounterSlot,
    Feature,
    FloorBoundMapElement,
    FloorLayout,
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
from dm_dungeon.contracts.topology import DoorConnection, DungeonTopology

DUNGEON_PACKAGE_SCHEMA_VERSION = "1.1.0"


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


class DungeonPackage(VersionedContract):
    """Exact renderer-neutral dungeon geometry and semantic layers."""

    supported_schema_version = DUNGEON_PACKAGE_SCHEMA_VERSION

    schema_version: Literal["1.1.0"]
    id: OpaqueId
    brief: DungeonBrief
    topology: DungeonTopology
    metadata: PackageMetadata
    grid: GridSpec = GridSpec()
    layers: tuple[RenderLayer, ...] = Field(min_length=1)
    floors: tuple[FloorLayout, ...] = Field(min_length=1)
    rooms: tuple[RoomLayout, ...] = Field(min_length=1)
    corridors: tuple[CorridorLayout, ...] = ()
    doors: tuple[DoorLayout, ...] = ()
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
                "doors": (item.id for item in self.doors),
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
            *self.doors,
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
        gate_ids = {gate.id for gate in self.topology.gates}
        hazard_ids = {hazard.id for hazard in self.hazards} | {
            connection.trap_id
            for connection in self.topology.connections
            if isinstance(connection, DoorConnection) and connection.trap_id is not None
        }
        zone_ids = {zone.id for zone in self.zones}
        anchor_ids = {anchor.id for anchor in self.position_anchors}
        stair_by_id = {stair.id: stair for stair in self.stairs}
        link_ids = {link.id for link in self.vertical_links}

        floor_elements: tuple[FloorBoundMapElement, ...] = (
            *self.rooms,
            *self.corridors,
            *self.doors,
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
        for door in self.doors:
            self._require_known_rooms(door.id, door.connects_room_ids, room_ids)
            if door.gate_id is not None and door.gate_id not in gate_ids:
                raise ValueError(
                    f"door {door.id!r} references unknown gate {door.gate_id!r}"
                )
            if door.hazard_id is not None and door.hazard_id not in hazard_ids:
                raise ValueError(
                    f"door {door.id!r} references unknown hazard {door.hazard_id!r}"
                )

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
