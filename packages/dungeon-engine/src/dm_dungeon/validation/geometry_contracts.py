"""Versioned exact-geometry validation and query contracts."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from dm_dungeon.contracts.common import (
    ContractModel,
    NonEmptyText,
    OpaqueId,
    VersionedContract,
)
from dm_dungeon.contracts.geometry import GridPoint
from dm_dungeon.validation.diagnostics import DiagnosticSeverity

GEOMETRY_VALIDATOR_VERSION: Literal["1.0.0"] = "1.0.0"
PATH_QUERY_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"
PATH_RESULT_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"
ENCOUNTER_FIT_QUERY_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"
ENCOUNTER_FIT_RESULT_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"
PositiveCells = Annotated[int, Field(ge=1)]
NonNegativeCount = Annotated[int, Field(ge=0)]
PositiveCount = Annotated[int, Field(ge=1)]


class GeometryDiagnosticCode(StrEnum):
    """Stable exact-geometry, path, and fit diagnostic codes."""

    CORRIDOR_BLOCKED = "geometry.corridor_blocked"
    CORRIDOR_ENDPOINT_MISALIGNED = "geometry.corridor_endpoint_misaligned"
    CORRIDOR_ROOM_INTERIOR_OVERLAP = "geometry.corridor_room_interior_overlap"
    CORRIDOR_UNDECLARED_WALL_CONTACT = "geometry.corridor_undeclared_wall_contact"
    CORRIDOR_NON_ORTHOGONAL = "geometry.corridor_non_orthogonal"
    CORRIDOR_OVERLAP = "geometry.corridor_overlap"
    CORRIDOR_WIDTH_INSUFFICIENT = "geometry.corridor_width_insufficient"
    DIRECT_DOOR_NOT_SHARED_WALL = "geometry.direct_door_not_shared_wall"
    DOOR_ALIGNMENT_INVALID = "geometry.door_alignment_invalid"
    DOOR_WIDTH_INSUFFICIENT = "geometry.door_width_insufficient"
    ENCOUNTER_ANCHOR_INVALID = "geometry.encounter_anchor_invalid"
    ENCOUNTER_COVER_INSUFFICIENT = "geometry.encounter_cover_insufficient"
    ENCOUNTER_FOOTPRINT_DOES_NOT_FIT = "geometry.encounter_footprint_does_not_fit"
    ENCOUNTER_OBJECTIVE_UNREACHABLE = "geometry.encounter_objective_unreachable"
    ENCOUNTER_RANGE_INSUFFICIENT = "geometry.encounter_range_insufficient"
    ENCOUNTER_ROOM_UNKNOWN = "geometry.encounter_room_unknown"
    FLOOR_BOUNDS_INVALID = "geometry.floor_bounds_invalid"
    FLOOR_TRANSITION_UNPAIRED = "geometry.floor_transition_unpaired"
    GEOMETRY_OUT_OF_BOUNDS = "geometry.out_of_bounds"
    GRID_SCALE_INVALID = "geometry.grid_scale_invalid"
    PACKAGE_ID_MISMATCH = "geometry.package_id_mismatch"
    PASSAGE_ENDPOINT_APPROACH_INVALID = "geometry.passage_endpoint_approach_invalid"
    PASSAGE_OPENING_INVALID = "geometry.passage_opening_invalid"
    PATH_ANCHOR_BLOCKED = "geometry.path_anchor_blocked"
    PATH_ANCHOR_UNKNOWN = "geometry.path_anchor_unknown"
    PATH_NOT_FOUND = "geometry.path_not_found"
    ROOM_CAPACITY_INSUFFICIENT = "geometry.room_capacity_insufficient"
    ROOM_MECHANIC_MARKER_INVALID = "geometry.room_mechanic_marker_invalid"
    ROOM_OVERLAP = "geometry.room_overlap"
    ROOM_POLYGON_INVALID = "geometry.room_polygon_invalid"
    ROOM_SIZE_CONSTRAINT_VIOLATION = "geometry.room_size_constraint_violation"
    STAIR_ALIGNMENT_INVALID = "geometry.stair_alignment_invalid"
    WALKABLE_REGION_DISCONNECTED = "geometry.walkable_region_disconnected"


class GeometryDiagnostic(ContractModel):
    """One deterministic exact-geometry or fit finding."""

    code: GeometryDiagnosticCode
    severity: DiagnosticSeverity
    message: NonEmptyText
    affected_ids: tuple[OpaqueId, ...]
    repair_hint: NonEmptyText


class GeometryValidationReport(ContractModel):
    """Complete deterministic geometry validation for one exact package."""

    validator_version: Literal["1.0.0"]
    package_id: OpaqueId
    valid: bool
    walkable_cell_count: NonNegativeCount
    diagnostics: tuple[GeometryDiagnostic, ...]

    @model_validator(mode="after")
    def valid_matches_diagnostics(self) -> Self:
        has_errors = any(
            diagnostic.severity is DiagnosticSeverity.ERROR
            for diagnostic in self.diagnostics
        )
        if self.valid == has_errors:
            raise ValueError("valid must be false exactly when error diagnostics exist")
        return self


class CreatureFootprint(ContractModel):
    """Axis-aligned tactical footprint measured in grid cells."""

    width_cells: PositiveCells = 1
    height_cells: PositiveCells = 1


class PathQuery(VersionedContract):
    """Shortest-path query between two declared position anchors."""

    supported_schema_version = PATH_QUERY_SCHEMA_VERSION

    schema_version: Literal["1.0.0"]
    package_id: OpaqueId
    start_anchor_id: OpaqueId
    end_anchor_id: OpaqueId
    footprint: CreatureFootprint = CreatureFootprint()


class PathStep(ContractModel):
    """One floor-local cell in a deterministic path."""

    floor_id: OpaqueId
    point: GridPoint


class PathResult(VersionedContract):
    """All-or-nothing pathfinding result."""

    supported_schema_version = PATH_RESULT_SCHEMA_VERSION

    schema_version: Literal["1.0.0"]
    package_id: OpaqueId
    success: bool
    distance_cells: NonNegativeCount | None
    path: tuple[PathStep, ...]
    diagnostics: tuple[GeometryDiagnostic, ...]

    @model_validator(mode="after")
    def require_consistent_result(self) -> Self:
        has_errors = any(
            diagnostic.severity is DiagnosticSeverity.ERROR
            for diagnostic in self.diagnostics
        )
        if self.success:
            if self.distance_cells is None or not self.path or has_errors:
                raise ValueError(
                    "successful path requires steps, distance, and no errors"
                )
        elif self.distance_cells is not None or self.path or not has_errors:
            raise ValueError("failed path requires diagnostics and no path/distance")
        return self


class FootprintRequirement(ContractModel):
    """One counted creature-footprint requirement for encounter fit."""

    id: OpaqueId
    footprint: CreatureFootprint
    count: PositiveCount = 1


class EncounterFitQuery(VersionedContract):
    """Narrow deterministic spatial query consumed later by Encounter Studio."""

    supported_schema_version = ENCOUNTER_FIT_QUERY_SCHEMA_VERSION

    schema_version: Literal["1.0.0"]
    package_id: OpaqueId
    room_id: OpaqueId
    footprints: tuple[FootprintRequirement, ...] = Field(min_length=1)
    starting_anchor_ids: tuple[OpaqueId, ...] = ()
    objective_anchor_ids: tuple[OpaqueId, ...] = ()
    minimum_range_cells: NonNegativeCount = 0
    minimum_cover_features: NonNegativeCount = 0


class EncounterFitMetrics(ContractModel):
    """Measured spatial facts without encounter difficulty arithmetic."""

    usable_cell_count: NonNegativeCount
    required_footprint_cell_count: NonNegativeCount
    maximum_open_range_cells: NonNegativeCount
    cover_feature_ids: tuple[OpaqueId, ...]
    reachable_starting_anchor_ids: tuple[OpaqueId, ...]
    reachable_objective_anchor_ids: tuple[OpaqueId, ...]


class EncounterFitResult(VersionedContract):
    """Deterministic spatial-fit result for one room and typed query."""

    supported_schema_version = ENCOUNTER_FIT_RESULT_SCHEMA_VERSION

    schema_version: Literal["1.0.0"]
    package_id: OpaqueId
    room_id: OpaqueId
    fits: bool
    metrics: EncounterFitMetrics | None
    diagnostics: tuple[GeometryDiagnostic, ...]

    @model_validator(mode="after")
    def require_consistent_result(self) -> Self:
        has_errors = any(
            diagnostic.severity is DiagnosticSeverity.ERROR
            for diagnostic in self.diagnostics
        )
        if self.fits:
            if self.metrics is None or has_errors:
                raise ValueError("fitting query requires metrics and no errors")
        elif not has_errors:
            raise ValueError("non-fitting query requires at least one error diagnostic")
        return self
