"""Exact, non-geometric mechanics-plan contracts shared by compiler and layout.

The compiler assigns stable component IDs and policy-derived difficulties here.  The
layout consumes this pure contract to attach those mechanics to exact package
geometry without importing compiler implementation code.
"""

from typing import Literal

from pydantic import Field, model_validator

from dm_dungeon.contracts.common import ContractModel, OpaqueId
from dm_dungeon.contracts.design import (
    BarrierIntent,
    EncounterSlotIntent,
    EndpointDoorKind,
    FeatureIntentKind,
    ObjectiveKind,
    VerticalEndpointSide,
)

DUNGEON_MECHANICS_POLICY_VERSION: Literal["dungeon-mechanics-policy-v1"] = (
    "dungeon-mechanics-policy-v1"
)


class CompiledDoorMechanics(ContractModel):
    """Exact mechanics attached to one same-floor door or vertical hatch."""

    id: OpaqueId
    connection_id: OpaqueId
    endpoint: VerticalEndpointSide | None = None
    endpoint_kind: EndpointDoorKind | None = None
    concealed: bool
    gate_id: OpaqueId | None = None
    gate_kind: BarrierIntent = BarrierIntent.NONE
    trap_id: OpaqueId | None = None
    discovery_difficulty: int | None = Field(default=None, ge=0)
    unlock_difficulty: int | None = Field(default=None, ge=0)
    disable_difficulty: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def require_complete_mechanics_and_endpoint_shape(
        self,
    ) -> "CompiledDoorMechanics":
        if (self.endpoint is None) != (self.endpoint_kind is None):
            raise ValueError("endpoint and endpoint_kind must be present together")
        if self.concealed and self.discovery_difficulty is None:
            raise ValueError("concealed mechanics require discovery_difficulty")
        if (self.gate_id is None) != (self.gate_kind is BarrierIntent.NONE):
            raise ValueError("gate_id and gate_kind must be present together")
        if self.gate_id is not None and self.unlock_difficulty is None:
            raise ValueError("gates require unlock_difficulty")
        if self.trap_id is not None and self.disable_difficulty is None:
            raise ValueError("traps require disable_difficulty")
        return self


class CompiledRoomTrap(ContractModel):
    id: OpaqueId
    room_id: OpaqueId
    detection_difficulty: int = Field(ge=0)
    disable_difficulty: int = Field(ge=0)


class CompiledRoomPuzzle(ContractModel):
    """One room-local puzzle/control with deterministic marker identity."""

    id: OpaqueId
    room_id: OpaqueId
    difficulty: int = Field(ge=0)


class CompiledRoomFeature(ContractModel):
    """One visible physical feature with deterministic marker identity."""

    id: OpaqueId
    room_id: OpaqueId
    kind: FeatureIntentKind


class CompiledRoomObjective(ContractModel):
    """One stable objective marker derived from bounded objective intent."""

    id: OpaqueId
    room_id: OpaqueId
    kind: ObjectiveKind
    name: str


class CompiledEncounterSlot(ContractModel):
    """One stable room-local slot for later independent encounter design."""

    id: OpaqueId
    room_id: OpaqueId
    intent: EncounterSlotIntent


class DungeonMechanicsPlan(ContractModel):
    """Stable policy-pinned mechanics consumed by exact layout and DM guidance."""

    policy_version: Literal["dungeon-mechanics-policy-v1"]
    connection_ids: tuple[OpaqueId, ...]
    room_ids: tuple[OpaqueId, ...]
    door_mechanics: tuple[CompiledDoorMechanics, ...]
    room_traps: tuple[CompiledRoomTrap, ...]
    room_puzzles: tuple[CompiledRoomPuzzle, ...]
    room_features: tuple[CompiledRoomFeature, ...]
    room_objectives: tuple[CompiledRoomObjective, ...]
    encounter_slots: tuple[CompiledEncounterSlot, ...]

    @model_validator(mode="after")
    def require_unique_room_mechanic_ids(self) -> "DungeonMechanicsPlan":
        marker_ids = (
            *(item.id for item in self.room_traps),
            *(item.id for item in self.room_puzzles),
            *(item.id for item in self.room_features),
            *(item.id for item in self.room_objectives),
            *(item.id for item in self.encounter_slots),
        )
        if len(marker_ids) != len(set(marker_ids)):
            raise ValueError("room mechanics require globally unique stable IDs")
        return self
