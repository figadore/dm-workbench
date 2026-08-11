"""Deterministic grid-on/gridless PNG export from filtered SVG."""

import hashlib
import xml.etree.ElementTree as ET
from collections.abc import Iterable

from dm_dungeon.contracts.package import DungeonPackage
from dm_dungeon.export.contracts import (
    PNG_EXPORT_MANIFEST_SCHEMA_VERSION,
    PNG_EXPORT_RESULT_SCHEMA_VERSION,
    PNG_EXPORTER_VERSION,
    ExportDiagnostic,
    ExportDiagnosticCode,
    PngArtifact,
    PngExportManifest,
    PngExportRequest,
    PngExportResult,
)
from dm_dungeon.export.raster import (
    ink_coverage_basis_points,
    png_dimensions,
    rasterize_svg,
)
from dm_dungeon.rendering import SvgRenderRequest, render_svg
from dm_dungeon.validation.diagnostics import DiagnosticSeverity


def export_png(package: DungeonPackage, request: PngExportRequest) -> PngArtifact:
    """Export a deterministic PNG and integrity manifest."""
    svg_result = render_svg(
        package,
        SvgRenderRequest(
            schema_version="1.0.0",
            package_id=request.package_id,
            floor_id=request.floor_id,
            audience=request.audience,
            pixels_per_cell=request.pixels_per_cell,
            show_grid=request.include_grid,
            show_labels=request.show_labels,
            show_room_ids=False,
            show_markers=request.show_markers,
            theme=request.theme,
        ),
    )
    if not svg_result.success or svg_result.svg is None or svg_result.sha256 is None:
        diagnostics = tuple(
            _diagnostic(
                ExportDiagnosticCode.SVG_RENDER_FAILED,
                finding.affected_ids,
                finding.message,
                finding.repair_hint,
                source_code=finding.code.value,
            )
            for finding in svg_result.diagnostics
        )
        return _failure(diagnostics)

    try:
        data = rasterize_svg(svg_result.svg, request.dpi)
        width, height = png_dimensions(data)
        ink_coverage = ink_coverage_basis_points(data)
    except (ET.ParseError, OSError, ValueError) as error:
        return _failure(
            (
                _diagnostic(
                    ExportDiagnosticCode.RASTERIZATION_FAILED,
                    (package.id, request.floor_id),
                    f"PNG rasterization failed: {error}",
                    "Validate the deterministic SVG renderer and raster settings.",
                ),
            )
        )

    if ink_coverage > request.maximum_ink_coverage_basis_points:
        return _failure(
            (
                _diagnostic(
                    ExportDiagnosticCode.INK_BUDGET_EXCEEDED,
                    (package.id, request.floor_id),
                    f"PNG ink proxy {ink_coverage} basis points exceeds budget "
                    f"{request.maximum_ink_coverage_basis_points}.",
                    "Use the draft theme, remove dense fills, or raise an explicitly "
                    "reviewed budget.",
                ),
            )
        )

    manifest = PngExportManifest(
        schema_version=PNG_EXPORT_MANIFEST_SCHEMA_VERSION,
        exporter_version=PNG_EXPORTER_VERSION,
        package_id=package.id,
        floor_id=request.floor_id,
        audience=request.audience,
        theme=request.theme,
        include_grid=request.include_grid,
        pixels_per_cell=request.pixels_per_cell,
        dpi=request.dpi,
        width_pixels=width,
        height_pixels=height,
        source_svg_sha256=svg_result.sha256,
        asset_sha256=hashlib.sha256(data).hexdigest(),
        ink_coverage_basis_points=ink_coverage,
        rendered_component_ids=svg_result.rendered_component_ids,
    )
    return PngArtifact(
        result=PngExportResult(
            schema_version=PNG_EXPORT_RESULT_SCHEMA_VERSION,
            success=True,
            manifest=manifest,
            diagnostics=(),
        ),
        data=data,
    )


def _failure(diagnostics: tuple[ExportDiagnostic, ...]) -> PngArtifact:
    return PngArtifact(
        result=PngExportResult(
            schema_version=PNG_EXPORT_RESULT_SCHEMA_VERSION,
            success=False,
            manifest=None,
            diagnostics=tuple(
                sorted(
                    diagnostics,
                    key=lambda item: (item.code.value, item.affected_ids, item.message),
                )
            ),
        ),
        data=None,
    )


def _diagnostic(
    code: ExportDiagnosticCode,
    affected_ids: Iterable[str],
    message: str,
    repair_hint: str,
    source_code: str | None = None,
) -> ExportDiagnostic:
    return ExportDiagnostic(
        code=code,
        severity=DiagnosticSeverity.ERROR,
        message=message,
        affected_ids=tuple(sorted(set(affected_ids))),
        repair_hint=repair_hint,
        source_code=source_code,
    )
