"""Versioned PNG and exact-scale PDF export contracts."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from dm_dungeon.contracts.common import (
    ContractModel,
    NonEmptyText,
    OpaqueId,
    VersionedContract,
)
from dm_dungeon.rendering import RenderAudience, SvgThemeName
from dm_dungeon.validation.diagnostics import DiagnosticSeverity

PNG_EXPORT_REQUEST_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"
PNG_EXPORT_MANIFEST_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"
PNG_EXPORT_RESULT_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"
PDF_EXPORT_REQUEST_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"
PDF_EXPORT_MANIFEST_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"
PDF_EXPORT_RESULT_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"
PNG_EXPORTER_VERSION: Literal["png-v1"] = "png-v1"
PDF_EXPORTER_VERSION: Literal["pdf-v1"] = "pdf-v1"
PRINT_CELL_POINTS: Literal[72] = 72
Sha256Hex = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
PixelsPerCell = Annotated[int, Field(ge=8, le=512)]
Dpi = Annotated[int, Field(ge=72, le=600)]
PositivePixels = Annotated[int, Field(ge=1)]
Points = Annotated[int, Field(ge=0)]
PositivePoints = Annotated[int, Field(ge=1)]
CoverageBasisPoints = Annotated[int, Field(ge=0, le=10000)]
PositiveCount = Annotated[int, Field(ge=1)]
NonNegativeInt = Annotated[int, Field(ge=0)]


class ExportDiagnosticCode(StrEnum):
    """Stable PNG/PDF export failure codes."""

    BUNDLE_INCONSISTENT = "export.bundle_inconsistent"
    INK_BUDGET_EXCEEDED = "export.ink_budget_exceeded"
    INVALID_PRINT_LAYOUT = "export.invalid_print_layout"
    PDF_GENERATION_FAILED = "export.pdf_generation_failed"
    RASTERIZATION_FAILED = "export.rasterization_failed"
    SVG_RENDER_FAILED = "export.svg_render_failed"


class ExportDiagnostic(ContractModel):
    """One all-or-nothing export failure."""

    code: ExportDiagnosticCode
    severity: DiagnosticSeverity
    message: NonEmptyText
    affected_ids: tuple[OpaqueId, ...]
    repair_hint: NonEmptyText
    source_code: str | None = None


class PngExportRequest(VersionedContract):
    """Pinned deterministic raster export request."""

    supported_schema_version = PNG_EXPORT_REQUEST_SCHEMA_VERSION

    schema_version: Literal["1.0.0"]
    package_id: OpaqueId
    floor_id: OpaqueId
    audience: RenderAudience
    pixels_per_cell: PixelsPerCell = 70
    dpi: Dpi = 140
    include_grid: bool = True
    show_labels: bool = True
    show_markers: bool = True
    theme: SvgThemeName = SvgThemeName.LOW_INK
    maximum_ink_coverage_basis_points: CoverageBasisPoints = 3500


class PngExportManifest(VersionedContract):
    """Reproducibility and integrity metadata for one PNG asset."""

    supported_schema_version = PNG_EXPORT_MANIFEST_SCHEMA_VERSION

    schema_version: Literal["1.0.0"]
    exporter_version: Literal["png-v1"]
    package_id: OpaqueId
    floor_id: OpaqueId
    audience: RenderAudience
    theme: SvgThemeName
    include_grid: bool
    pixels_per_cell: PixelsPerCell
    dpi: Dpi
    width_pixels: PositivePixels
    height_pixels: PositivePixels
    source_svg_sha256: Sha256Hex
    asset_sha256: Sha256Hex
    ink_coverage_basis_points: CoverageBasisPoints
    rendered_component_ids: tuple[OpaqueId, ...]


class PngExportResult(VersionedContract):
    """Manifest-bearing PNG success/failure without embedding binary bytes."""

    supported_schema_version = PNG_EXPORT_RESULT_SCHEMA_VERSION

    schema_version: Literal["1.0.0"]
    success: bool
    manifest: PngExportManifest | None
    diagnostics: tuple[ExportDiagnostic, ...]

    @model_validator(mode="after")
    def require_consistent_result(self) -> Self:
        has_errors = any(
            diagnostic.severity is DiagnosticSeverity.ERROR
            for diagnostic in self.diagnostics
        )
        if self.success:
            if self.manifest is None or has_errors:
                raise ValueError("successful PNG export requires a manifest")
        elif self.manifest is not None or not has_errors:
            raise ValueError("failed PNG export requires diagnostics and no manifest")
        return self


@dataclass(frozen=True, slots=True)
class PngArtifact:
    """In-memory PNG bytes paired with their serializable result."""

    result: PngExportResult
    data: bytes | None

    def __post_init__(self) -> None:
        if self.result.success != (self.data is not None):
            raise ValueError("PNG data must exist exactly for successful results")


class PaperSize(StrEnum):
    """Supported initial print paper sizes."""

    A4 = "a4"
    LETTER = "letter"


class AssemblyMode(StrEnum):
    """Supported physical page assembly workflows."""

    OVERLAP_AND_TAPE = "overlap_and_tape"
    TRIM_AND_BUTT = "trim_and_butt"


class PdfExportRequest(VersionedContract):
    """Pinned exact-scale tiled PDF request."""

    supported_schema_version = PDF_EXPORT_REQUEST_SCHEMA_VERSION

    schema_version: Literal["1.0.0"]
    package_id: OpaqueId
    floor_id: OpaqueId
    audience: RenderAudience
    paper_size: PaperSize = PaperSize.LETTER
    assembly_mode: AssemblyMode = AssemblyMode.OVERLAP_AND_TAPE
    margin_points: PositivePoints = 36
    overlap_points: Points = 18
    include_overview: bool = True
    include_grid: bool = True
    show_labels: bool = True
    show_markers: bool = True
    theme: SvgThemeName = SvgThemeName.LOW_INK
    maximum_ink_coverage_basis_points: CoverageBasisPoints = 3500

    @model_validator(mode="after")
    def validate_assembly_settings(self) -> Self:
        if self.assembly_mode is AssemblyMode.TRIM_AND_BUTT:
            if self.overlap_points != 0:
                raise ValueError("trim_and_butt requires overlap_points=0")
        elif self.overlap_points <= 0:
            raise ValueError("overlap_and_tape requires positive overlap_points")
        return self


class TileNeighborDirection(StrEnum):
    """Direction from one tile to an adjacent tile."""

    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    UP = "up"


class TileNeighbor(ContractModel):
    """One deterministic adjacency used during page assembly."""

    direction: TileNeighborDirection
    page_id: OpaqueId


class PdfTileMetadata(ContractModel):
    """Source viewport and assembly metadata for one exact-scale tile page."""

    page_number: PositiveCount
    row: NonNegativeInt
    column: NonNegativeInt
    page_id: OpaqueId
    source_x_points: Points
    source_y_points: Points
    viewport_width_points: PositivePoints
    viewport_height_points: PositivePoints
    overlap_left_points: Points
    overlap_right_points: Points
    overlap_top_points: Points
    overlap_bottom_points: Points
    neighbors: tuple[TileNeighbor, ...]


class PdfExportManifest(VersionedContract):
    """Complete print scale, tiling, and integrity metadata."""

    supported_schema_version = PDF_EXPORT_MANIFEST_SCHEMA_VERSION

    schema_version: Literal["1.0.0"]
    exporter_version: Literal["pdf-v1"]
    package_id: OpaqueId
    floor_id: OpaqueId
    audience: RenderAudience
    theme: SvgThemeName
    paper_size: PaperSize
    assembly_mode: AssemblyMode
    page_width_points: PositivePoints
    page_height_points: PositivePoints
    margin_points: PositivePoints
    overlap_points: Points
    cell_scale_points: Literal[72]
    calibration_square_points: Literal[72]
    map_width_points: PositivePoints
    map_height_points: PositivePoints
    tile_rows: PositiveCount
    tile_columns: PositiveCount
    overview_page_included: bool
    page_count: PositiveCount
    source_svg_sha256: Sha256Hex
    asset_sha256: Sha256Hex
    ink_coverage_basis_points: CoverageBasisPoints
    rendered_component_ids: tuple[OpaqueId, ...]
    tiles: tuple[PdfTileMetadata, ...]


class PdfExportResult(VersionedContract):
    """Manifest-bearing PDF success/failure without embedding binary bytes."""

    supported_schema_version = PDF_EXPORT_RESULT_SCHEMA_VERSION

    schema_version: Literal["1.0.0"]
    success: bool
    manifest: PdfExportManifest | None
    diagnostics: tuple[ExportDiagnostic, ...]

    @model_validator(mode="after")
    def require_consistent_result(self) -> Self:
        has_errors = any(
            diagnostic.severity is DiagnosticSeverity.ERROR
            for diagnostic in self.diagnostics
        )
        if self.success:
            if self.manifest is None or has_errors:
                raise ValueError("successful PDF export requires a manifest")
        elif self.manifest is not None or not has_errors:
            raise ValueError("failed PDF export requires diagnostics and no manifest")
        return self


@dataclass(frozen=True, slots=True)
class PdfArtifact:
    """In-memory PDF bytes paired with their serializable result."""

    result: PdfExportResult
    data: bytes | None

    def __post_init__(self) -> None:
        if self.result.success != (self.data is not None):
            raise ValueError("PDF data must exist exactly for successful results")
