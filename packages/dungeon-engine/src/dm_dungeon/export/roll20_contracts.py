"""Versioned Roll20-compatible map bundle contracts."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from dm_dungeon.contracts.common import ContractModel, OpaqueId, VersionedContract
from dm_dungeon.contracts.geometry import GridPoint, PositionAnchorKind
from dm_dungeon.contracts.topology import DoorType
from dm_dungeon.export.contracts import (
    CoverageBasisPoints,
    Dpi,
    ExportDiagnostic,
    PixelsPerCell,
    PositivePixels,
    Sha256Hex,
)
from dm_dungeon.rendering import RenderAudience, SvgThemeName

ROLL20_EXPORT_REQUEST_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"
ROLL20_EXPORT_MANIFEST_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"
ROLL20_EXPORT_RESULT_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"
ROLL20_EXPORTER_VERSION: Literal["roll20-v1"] = "roll20-v1"
SafePrefix = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    ),
]
SafeFilename = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    ),
]
PositiveCells = Annotated[int, Field(ge=1)]
NonNegativeCoordinate = Annotated[int, Field(ge=0)]


class Roll20AssetRole(StrEnum):
    """Roles of raster files in a Roll20 bundle."""

    GRIDLESS_MAP = "gridless_map"
    GRID_ON_MAP = "grid_on_map"


class Roll20ExportRequest(VersionedContract):
    """Pinned request for paired images and safe Roll20 metadata."""

    supported_schema_version = ROLL20_EXPORT_REQUEST_SCHEMA_VERSION

    schema_version: Literal["1.0.0"]
    package_id: OpaqueId
    floor_id: OpaqueId
    audience: RenderAudience
    filename_prefix: SafePrefix
    pixels_per_cell: PixelsPerCell = 70
    dpi: Dpi = 140
    include_token_placements: bool = False
    show_labels: bool = True
    show_markers: bool = True
    theme: SvgThemeName = SvgThemeName.LOW_INK
    maximum_ink_coverage_basis_points: CoverageBasisPoints = 3500

    @model_validator(mode="after")
    def reject_ambiguous_prefix(self) -> Self:
        if ".." in self.filename_prefix or self.filename_prefix.endswith("."):
            raise ValueError("filename_prefix cannot contain '..' or end with '.'")
        return self


class Roll20RasterAsset(ContractModel):
    """Integrity metadata for one bundled PNG."""

    role: Roll20AssetRole
    filename: SafeFilename
    media_type: Literal["image/png"]
    source_svg_sha256: Sha256Hex
    sha256: Sha256Hex
    width_pixels: PositivePixels
    height_pixels: PositivePixels


class Roll20GridMetadata(ContractModel):
    """Roll20 map setup values for a zero-origin square grid."""

    width_cells: PositiveCells
    height_cells: PositiveCells
    pixels_per_cell: PixelsPerCell
    cell_scale_feet: Literal[5]
    origin_x_cells: Literal[0]
    origin_y_cells: Literal[0]
    origin_x_pixels: Literal[0]
    origin_y_pixels: Literal[0]


class Roll20WallPolygon(ContractModel):
    """Visible room wall geometry retained for future adapters."""

    component_id: OpaqueId
    floor_id: OpaqueId
    points: tuple[GridPoint, ...] = Field(min_length=3)


class Roll20DoorSegment(ContractModel):
    """Visible door geometry without gate/trap secrets."""

    component_id: OpaqueId
    floor_id: OpaqueId
    door_type: DoorType
    start: GridPoint
    end: GridPoint


class Roll20TokenPlacement(ContractModel):
    """Explicitly visible stable anchor converted to pixel coordinates."""

    anchor_id: OpaqueId
    kind: PositionAnchorKind
    x_pixels: NonNegativeCoordinate
    y_pixels: NonNegativeCoordinate


class Roll20ExportManifest(VersionedContract):
    """Complete safe metadata for one Roll20-compatible map bundle."""

    supported_schema_version = ROLL20_EXPORT_MANIFEST_SCHEMA_VERSION

    schema_version: Literal["1.0.0"]
    exporter_version: Literal["roll20-v1"]
    package_id: OpaqueId
    floor_id: OpaqueId
    audience: RenderAudience
    theme: SvgThemeName
    grid: Roll20GridMetadata
    assets: tuple[Roll20RasterAsset, Roll20RasterAsset]
    wall_polygons: tuple[Roll20WallPolygon, ...]
    door_segments: tuple[Roll20DoorSegment, ...]
    token_placements: tuple[Roll20TokenPlacement, ...]
    rendered_component_ids: tuple[OpaqueId, ...]
    direct_upload_supported: Literal[False]
    dynamic_lighting_import_supported: Literal[False]

    @model_validator(mode="after")
    def require_consistent_safe_metadata(self) -> Self:
        expected_roles = (
            Roll20AssetRole.GRID_ON_MAP,
            Roll20AssetRole.GRIDLESS_MAP,
        )
        if tuple(asset.role for asset in self.assets) != expected_roles:
            raise ValueError("assets must contain grid-on then gridless PNG metadata")
        if len({asset.filename for asset in self.assets}) != 2:
            raise ValueError("Roll20 asset filenames must be distinct")
        expected_dimensions = (
            self.grid.width_cells * self.grid.pixels_per_cell,
            self.grid.height_cells * self.grid.pixels_per_cell,
        )
        if any(
            (asset.width_pixels, asset.height_pixels) != expected_dimensions
            for asset in self.assets
        ):
            raise ValueError("Roll20 asset dimensions must match grid dimensions")
        visible_ids = set(self.rendered_component_ids)
        if len(visible_ids) != len(self.rendered_component_ids):
            raise ValueError("rendered_component_ids must be unique")
        geometry_ids = [
            *(wall.component_id for wall in self.wall_polygons),
            *(door.component_id for door in self.door_segments),
            *(token.anchor_id for token in self.token_placements),
        ]
        if len(set(geometry_ids)) != len(geometry_ids):
            raise ValueError("Roll20 geometry/token component IDs must be unique")
        if not set(geometry_ids) <= visible_ids:
            raise ValueError("Roll20 geometry/token IDs must be rendered and visible")
        if any(wall.floor_id != self.floor_id for wall in self.wall_polygons) or any(
            door.floor_id != self.floor_id for door in self.door_segments
        ):
            raise ValueError(
                "Roll20 wall/door records must belong to the exported floor"
            )
        if any(
            token.x_pixels >= expected_dimensions[0]
            or token.y_pixels >= expected_dimensions[1]
            for token in self.token_placements
        ):
            raise ValueError("Roll20 token placements must be inside image bounds")
        return self


class Roll20ExportResult(VersionedContract):
    """Manifest-bearing bundle result without embedding binary bytes."""

    supported_schema_version = ROLL20_EXPORT_RESULT_SCHEMA_VERSION

    schema_version: Literal["1.0.0"]
    success: bool
    manifest: Roll20ExportManifest | None
    bundle_sha256: Sha256Hex | None
    diagnostics: tuple[ExportDiagnostic, ...]

    @model_validator(mode="after")
    def require_consistent_result(self) -> Self:
        if self.success:
            if self.manifest is None or self.bundle_sha256 is None or self.diagnostics:
                raise ValueError(
                    "successful Roll20 export requires manifest/bundle hash"
                )
        elif (
            self.manifest is not None
            or self.bundle_sha256 is not None
            or not (self.diagnostics)
        ):
            raise ValueError("failed Roll20 export requires diagnostics only")
        return self


@dataclass(frozen=True, slots=True)
class Roll20BundleFile:
    """One deterministic relative file in a bundle."""

    filename: str
    data: bytes


@dataclass(frozen=True, slots=True)
class Roll20Artifact:
    """Canonical manifest, PNG files, and deterministic ZIP bytes."""

    result: Roll20ExportResult
    files: tuple[Roll20BundleFile, ...]
    zip_data: bytes | None

    def __post_init__(self) -> None:
        if self.result.success != (self.zip_data is not None and bool(self.files)):
            raise ValueError("Roll20 files/ZIP must exist exactly on success")
