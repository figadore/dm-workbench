"""Versioned request, lock, diagnostic, and result contracts for layout."""

import json
from enum import StrEnum
from hashlib import sha256
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from dm_dungeon.contracts.brief import DungeonBrief
from dm_dungeon.contracts.certificate import TopologyCertificate
from dm_dungeon.contracts.common import (
    ContractModel,
    NonEmptyText,
    OpaqueId,
    VersionedContract,
    ensure_unique_ids,
)
from dm_dungeon.contracts.geometry import (
    CorridorLayout,
    FloorLayout,
    GridSpec,
    RoomLayout,
    StairLayout,
    VerticalLinkLayout,
)
from dm_dungeon.contracts.mechanics import DungeonMechanicsPlan
from dm_dungeon.contracts.package import DungeonPackage, MechanicDoorLayout
from dm_dungeon.contracts.topology import DungeonTopology
from dm_dungeon.validation.diagnostics import DiagnosticSeverity

LAYOUT_REQUEST_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"
LAYOUT_RESULT_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"
ORTHOGONAL_LAYOUT_GENERATOR_VERSION: Literal["orthogonal-v1"] = "orthogonal-v1"
PositiveCells = Annotated[int, Field(ge=1)]
NonNegativeCells = Annotated[int, Field(ge=0)]
NonNegativeCount = Annotated[int, Field(ge=0)]


class LayoutDiagnosticCode(StrEnum):
    """Stable failure codes emitted by the orthogonal layout engine."""

    BRIEF_TOPOLOGY_MISMATCH = "layout.brief_topology_mismatch"
    CONNECTION_ROUTING_FAILED = "layout.connection_routing_failed"
    FLOOR_BOUNDS_INVALID = "layout.floor_bounds_invalid"
    FLOOR_TRANSITION_FAILED = "layout.floor_transition_failed"
    INTERNAL_CONTRACT_FAILURE = "layout.internal_contract_failure"
    LOCKED_COMPONENT_CONFLICT = "layout.locked_component_conflict"
    LOCKED_COMPONENT_UNKNOWN = "layout.locked_component_unknown"
    MECHANICS_PLAN_INVALID = "layout.mechanics_plan_invalid"
    MECHANICS_MARKER_PLACEMENT_FAILED = "layout.mechanics_marker_placement_failed"
    ROOM_PLACEMENT_FAILED = "layout.room_placement_failed"
    TOPOLOGY_INVALID = "layout.topology_invalid"
    UNKNOWN_FLOOR_BOUNDS = "layout.unknown_floor_bounds"


class LayoutDiagnostic(ContractModel):
    """One deterministic layout failure with repair context."""

    code: LayoutDiagnosticCode
    severity: DiagnosticSeverity
    message: NonEmptyText
    affected_ids: tuple[OpaqueId, ...]
    repair_hint: NonEmptyText
    source_code: str | None = None


class FloorLayoutBounds(ContractModel):
    """Computed required bounds or an optional caller-supplied maximum."""

    floor_id: OpaqueId
    width_cells: PositiveCells
    height_cells: PositiveCells
    margin_cells: NonNegativeCells = 1


class LockedLayoutComponents(ContractModel):
    """Exact components that targeted regeneration must preserve byte-for-byte."""

    floors: tuple[FloorLayout, ...] = ()
    rooms: tuple[RoomLayout, ...] = ()
    corridors: tuple[CorridorLayout, ...] = ()
    doors: tuple[MechanicDoorLayout, ...] = ()
    stairs: tuple[StairLayout, ...] = ()
    vertical_links: tuple[VerticalLinkLayout, ...] = ()

    @model_validator(mode="after")
    def require_unique_ids(self) -> Self:
        ensure_unique_ids(
            {
                "floors": (item.id for item in self.floors),
                "rooms": (item.id for item in self.rooms),
                "corridors": (item.id for item in self.corridors),
                "doors": (item.id for item in self.doors),
                "stairs": (item.id for item in self.stairs),
                "vertical_links": (item.id for item in self.vertical_links),
            }
        )
        return self

    def component_ids(self) -> tuple[str, ...]:
        """Return all locked IDs in stable category/order order."""
        return tuple(
            item.id
            for group in (
                self.floors,
                self.rooms,
                self.corridors,
                self.doors,
                self.stairs,
                self.vertical_links,
            )
            for item in group
        )


class LayoutRequest(VersionedContract):
    """All pinned input needed to reproduce one exact layout attempt."""

    supported_schema_version = LAYOUT_REQUEST_SCHEMA_VERSION

    schema_version: Literal["1.0.0"]
    package_id: OpaqueId
    brief: DungeonBrief
    topology: DungeonTopology
    certificate: TopologyCertificate
    seed: int
    generator_version: Literal["orthogonal-v1"]
    mechanics_plan: DungeonMechanicsPlan
    grid: GridSpec = GridSpec()
    floor_bounds: tuple[FloorLayoutBounds, ...] = ()
    locked: LockedLayoutComponents = LockedLayoutComponents()

    @model_validator(mode="after")
    def require_unique_floor_bounds(self) -> Self:
        floor_ids = [item.floor_id for item in self.floor_bounds]
        if len(floor_ids) != len(set(floor_ids)):
            raise ValueError("floor_bounds must contain each floor at most once")
        topology_json = json.dumps(
            self.topology.model_dump(mode="json", round_trip=True),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        if (
            self.certificate.topology_id != self.topology.id
            or self.certificate.topology_hash != sha256(topology_json).hexdigest()
        ):
            raise ValueError(
                "certificate must be bound to the exact requested topology"
            )
        return self


class LayoutResult(VersionedContract):
    """Deterministic all-or-nothing output from a layout request."""

    supported_schema_version = LAYOUT_RESULT_SCHEMA_VERSION

    schema_version: Literal["1.0.0"]
    generator_version: Literal["orthogonal-v1"]
    seed: int
    random_draw_count: NonNegativeCount
    success: bool
    package: DungeonPackage | None
    diagnostics: tuple[LayoutDiagnostic, ...]

    @model_validator(mode="after")
    def require_consistent_result(self) -> Self:
        has_errors = any(
            diagnostic.severity is DiagnosticSeverity.ERROR
            for diagnostic in self.diagnostics
        )
        if self.success:
            if self.package is None or has_errors:
                raise ValueError("successful layout requires a package and no errors")
        elif self.package is not None or not has_errors:
            raise ValueError("failed layout requires error diagnostics and no package")
        return self
