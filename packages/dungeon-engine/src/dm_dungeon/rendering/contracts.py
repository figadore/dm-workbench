"""Versioned deterministic SVG render request and result contracts."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from dm_dungeon.contracts.common import (
    ContractModel,
    NonEmptyText,
    OpaqueId,
    VersionedContract,
)
from dm_dungeon.validation.diagnostics import DiagnosticSeverity

SVG_RENDER_REQUEST_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"
SVG_RENDER_RESULT_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"
SVG_RENDERER_VERSION: Literal["svg-v1"] = "svg-v1"
PixelsPerCell = Annotated[int, Field(ge=8, le=512)]
PositivePixels = Annotated[int, Field(ge=1)]
Sha256Hex = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class RenderAudience(StrEnum):
    """Information audience selected before SVG element construction."""

    DM = "dm"
    PLAYER = "player"


class SvgThemeName(StrEnum):
    """Code-owned initial SVG style themes."""

    LOW_INK = "low_ink"
    DRAFT = "draft"


class SvgRenderDiagnosticCode(StrEnum):
    """Stable render failure codes."""

    FLOOR_NOT_PUBLISHABLE = "render.floor_not_publishable"
    FLOOR_UNKNOWN = "render.floor_unknown"
    GEOMETRY_INVALID = "render.geometry_invalid"
    PACKAGE_ID_MISMATCH = "render.package_id_mismatch"


class SvgRenderDiagnostic(ContractModel):
    """One structured all-or-nothing SVG render failure."""

    code: SvgRenderDiagnosticCode
    severity: DiagnosticSeverity
    message: NonEmptyText
    affected_ids: tuple[OpaqueId, ...]
    repair_hint: NonEmptyText
    source_code: str | None = None


class SvgRenderRequest(VersionedContract):
    """Pinned selection and presentation controls for one floor SVG."""

    supported_schema_version = SVG_RENDER_REQUEST_SCHEMA_VERSION

    schema_version: Literal["1.0.0"]
    package_id: OpaqueId
    floor_id: OpaqueId
    audience: RenderAudience
    pixels_per_cell: PixelsPerCell = 64
    show_grid: bool = True
    show_labels: bool = True
    show_room_ids: bool = False
    show_markers: bool = True
    theme: SvgThemeName = SvgThemeName.LOW_INK


class SvgRenderResult(VersionedContract):
    """Deterministic SVG document or structured render failure."""

    supported_schema_version = SVG_RENDER_RESULT_SCHEMA_VERSION

    schema_version: Literal["1.0.0"]
    renderer_version: Literal["svg-v1"]
    package_id: OpaqueId
    floor_id: OpaqueId
    audience: RenderAudience
    success: bool
    width_pixels: PositivePixels | None
    height_pixels: PositivePixels | None
    svg: str | None
    sha256: Sha256Hex | None
    rendered_component_ids: tuple[OpaqueId, ...]
    diagnostics: tuple[SvgRenderDiagnostic, ...]

    @model_validator(mode="after")
    def require_consistent_result(self) -> Self:
        has_errors = any(
            diagnostic.severity is DiagnosticSeverity.ERROR
            for diagnostic in self.diagnostics
        )
        if self.success:
            if (
                self.width_pixels is None
                or self.height_pixels is None
                or self.svg is None
                or self.sha256 is None
                or has_errors
            ):
                raise ValueError(
                    "successful SVG render requires dimensions/document/hash"
                )
        elif (
            self.width_pixels is not None
            or self.height_pixels is not None
            or self.svg is not None
            or self.sha256 is not None
            or self.rendered_component_ids
            or not has_errors
        ):
            raise ValueError("failed SVG render requires diagnostics and no document")
        return self
