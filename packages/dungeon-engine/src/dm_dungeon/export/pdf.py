"""Deterministic exact-scale low-ink tiled PDF export."""

import hashlib
import io
import xml.etree.ElementTree as ET
from collections.abc import Iterable

from reportlab.lib import colors  # type: ignore[import-untyped]
from reportlab.pdfgen.canvas import Canvas  # type: ignore[import-untyped]

from dm_dungeon.contracts.package import DungeonPackage
from dm_dungeon.export.contracts import (
    PDF_EXPORT_MANIFEST_SCHEMA_VERSION,
    PDF_EXPORT_RESULT_SCHEMA_VERSION,
    PDF_EXPORTER_VERSION,
    PRINT_CELL_POINTS,
    ExportDiagnostic,
    ExportDiagnosticCode,
    PaperSize,
    PdfArtifact,
    PdfExportManifest,
    PdfExportRequest,
    PdfExportResult,
    PdfTileMetadata,
    TileNeighbor,
    TileNeighborDirection,
)
from dm_dungeon.export.pdf_drawing import draw_svg
from dm_dungeon.export.raster import ink_coverage_basis_points, rasterize_svg
from dm_dungeon.rendering import SvgRenderRequest, render_svg
from dm_dungeon.validation.diagnostics import DiagnosticSeverity

PAPER_DIMENSIONS = {
    PaperSize.LETTER: (612, 792),
    PaperSize.A4: (595, 842),
}
HEADER_POINTS = 24
FOOTER_POINTS = 90
MARK_LENGTH_POINTS = 9


def export_pdf(package: DungeonPackage, request: PdfExportRequest) -> PdfArtifact:
    """Export overview plus exact-scale tile pages and a stitching manifest."""
    svg_result = render_svg(
        package,
        SvgRenderRequest(
            schema_version="1.0.0",
            package_id=request.package_id,
            floor_id=request.floor_id,
            audience=request.audience,
            pixels_per_cell=PRINT_CELL_POINTS,
            show_grid=request.include_grid,
            show_labels=request.show_labels,
            show_room_ids=request.audience.value == "dm",
            show_markers=request.show_markers,
            theme=request.theme,
        ),
    )
    if not svg_result.success or svg_result.svg is None or svg_result.sha256 is None:
        return _failure(
            tuple(
                _diagnostic(
                    ExportDiagnosticCode.SVG_RENDER_FAILED,
                    finding.affected_ids,
                    finding.message,
                    finding.repair_hint,
                    source_code=finding.code.value,
                )
                for finding in svg_result.diagnostics
            )
        )

    try:
        proxy_png = rasterize_svg(svg_result.svg, dpi=72)
        ink_coverage = ink_coverage_basis_points(proxy_png)
    except (ET.ParseError, OSError, ValueError) as error:
        return _failure(
            (
                _diagnostic(
                    ExportDiagnosticCode.PDF_GENERATION_FAILED,
                    (package.id, request.floor_id),
                    f"Print ink proxy failed: {error}",
                    "Validate the filtered SVG before PDF export.",
                ),
            )
        )
    if ink_coverage > request.maximum_ink_coverage_basis_points:
        return _failure(
            (
                _diagnostic(
                    ExportDiagnosticCode.INK_BUDGET_EXCEEDED,
                    (package.id, request.floor_id),
                    f"PDF ink proxy {ink_coverage} basis points exceeds budget "
                    f"{request.maximum_ink_coverage_basis_points}.",
                    "Use the draft theme, remove dense fills, or raise an explicitly "
                    "reviewed budget.",
                ),
            )
        )

    page_width, page_height = PAPER_DIMENSIONS[request.paper_size]
    viewport_width = (
        (page_width - 2 * request.margin_points) // PRINT_CELL_POINTS
    ) * PRINT_CELL_POINTS
    viewport_height = (
        (page_height - 2 * request.margin_points - HEADER_POINTS - FOOTER_POINTS)
        // PRINT_CELL_POINTS
    ) * PRINT_CELL_POINTS
    if (
        viewport_width <= request.overlap_points
        or viewport_height <= request.overlap_points
    ):
        return _failure(
            (
                _diagnostic(
                    ExportDiagnosticCode.INVALID_PRINT_LAYOUT,
                    (package.id, request.floor_id),
                    "Paper, margins, and overlap leave no usable tile viewport.",
                    "Reduce margins/overlap or choose a larger paper size.",
                ),
            )
        )

    map_width = svg_result.width_pixels
    map_height = svg_result.height_pixels
    assert map_width is not None
    assert map_height is not None
    x_origins = _tile_origins(map_width, viewport_width, request.overlap_points)
    y_origins = _tile_origins(map_height, viewport_height, request.overlap_points)
    overview_offset = 1 if request.include_overview else 0
    tiles = _tile_metadata(
        x_origins,
        y_origins,
        viewport_width,
        viewport_height,
        request.overlap_points,
        overview_offset,
    )

    try:
        data = _build_pdf(
            package,
            request,
            svg_result.svg,
            tiles,
            page_width,
            page_height,
            viewport_width,
            viewport_height,
        )
    except (ET.ParseError, OSError, ValueError) as error:
        return _failure(
            (
                _diagnostic(
                    ExportDiagnosticCode.PDF_GENERATION_FAILED,
                    (package.id, request.floor_id),
                    f"PDF generation failed: {error}",
                    "Validate page settings and the deterministic SVG source.",
                ),
            )
        )

    manifest = PdfExportManifest(
        schema_version=PDF_EXPORT_MANIFEST_SCHEMA_VERSION,
        exporter_version=PDF_EXPORTER_VERSION,
        package_id=package.id,
        floor_id=request.floor_id,
        audience=request.audience,
        theme=request.theme,
        paper_size=request.paper_size,
        assembly_mode=request.assembly_mode,
        page_width_points=page_width,
        page_height_points=page_height,
        margin_points=request.margin_points,
        overlap_points=request.overlap_points,
        cell_scale_points=PRINT_CELL_POINTS,
        calibration_square_points=PRINT_CELL_POINTS,
        map_width_points=map_width,
        map_height_points=map_height,
        tile_rows=len(y_origins),
        tile_columns=len(x_origins),
        overview_page_included=request.include_overview,
        page_count=len(tiles) + overview_offset,
        source_svg_sha256=svg_result.sha256,
        asset_sha256=hashlib.sha256(data).hexdigest(),
        ink_coverage_basis_points=ink_coverage,
        rendered_component_ids=svg_result.rendered_component_ids,
        tiles=tiles,
    )
    return PdfArtifact(
        result=PdfExportResult(
            schema_version=PDF_EXPORT_RESULT_SCHEMA_VERSION,
            success=True,
            manifest=manifest,
            diagnostics=(),
        ),
        data=data,
    )


def _tile_origins(
    map_size: int,
    viewport_size: int,
    overlap: int,
) -> tuple[int, ...]:
    if map_size <= viewport_size:
        return (0,)
    stride = viewport_size - overlap
    origins = [0]
    while origins[-1] + viewport_size < map_size:
        origins.append(origins[-1] + stride)
    return tuple(origins)


def _tile_metadata(
    x_origins: tuple[int, ...],
    y_origins: tuple[int, ...],
    viewport_width: int,
    viewport_height: int,
    requested_overlap: int,
    overview_offset: int,
) -> tuple[PdfTileMetadata, ...]:
    page_ids = {
        (row, column): f"{_row_label(row)}{column + 1}"
        for row in range(len(y_origins))
        for column in range(len(x_origins))
    }
    tiles: list[PdfTileMetadata] = []
    for row, source_y in enumerate(y_origins):
        for column, source_x in enumerate(x_origins):
            neighbors: list[TileNeighbor] = []
            for direction, coordinate in (
                (TileNeighborDirection.UP, (row - 1, column)),
                (TileNeighborDirection.DOWN, (row + 1, column)),
                (TileNeighborDirection.LEFT, (row, column - 1)),
                (TileNeighborDirection.RIGHT, (row, column + 1)),
            ):
                neighbor_id = page_ids.get(coordinate)
                if neighbor_id is not None:
                    neighbors.append(
                        TileNeighbor(direction=direction, page_id=neighbor_id)
                    )
            overlap_left = (
                x_origins[column - 1] + viewport_width - source_x if column > 0 else 0
            )
            overlap_right = (
                source_x + viewport_width - x_origins[column + 1]
                if column + 1 < len(x_origins)
                else 0
            )
            overlap_top = (
                y_origins[row - 1] + viewport_height - source_y if row > 0 else 0
            )
            overlap_bottom = (
                source_y + viewport_height - y_origins[row + 1]
                if row + 1 < len(y_origins)
                else 0
            )
            for value in (
                overlap_left,
                overlap_right,
                overlap_top,
                overlap_bottom,
            ):
                if value < requested_overlap and value != 0:
                    raise ValueError("computed tile overlap is below requested overlap")
            page_index = row * len(x_origins) + column
            tiles.append(
                PdfTileMetadata(
                    page_number=page_index + 1 + overview_offset,
                    row=row,
                    column=column,
                    page_id=page_ids[(row, column)],
                    source_x_points=source_x,
                    source_y_points=source_y,
                    viewport_width_points=viewport_width,
                    viewport_height_points=viewport_height,
                    overlap_left_points=overlap_left,
                    overlap_right_points=overlap_right,
                    overlap_top_points=overlap_top,
                    overlap_bottom_points=overlap_bottom,
                    neighbors=tuple(neighbors),
                )
            )
    return tuple(tiles)


def _build_pdf(
    package: DungeonPackage,
    request: PdfExportRequest,
    svg: str,
    tiles: tuple[PdfTileMetadata, ...],
    page_width: int,
    page_height: int,
    viewport_width: int,
    viewport_height: int,
) -> bytes:
    output = io.BytesIO()
    canvas = Canvas(
        output,
        pagesize=(page_width, page_height),
        pageCompression=0,
        invariant=1,
    )
    canvas.setTitle(f"Dungeon print {package.id} {request.floor_id}")
    canvas.setAuthor("dm-dungeon")
    canvas.setCreator(f"dm-dungeon {PDF_EXPORTER_VERSION}")
    canvas.setSubject(
        f"{request.audience.value} exact-scale {request.paper_size.value} tiled map"
    )

    if request.include_overview:
        _draw_overview(
            canvas,
            package,
            request,
            tiles,
            page_width,
            page_height,
        )
        canvas.showPage()

    for tile in tiles:
        _draw_tile_page(
            canvas,
            package,
            request,
            svg,
            tile,
            page_width,
            page_height,
            viewport_width,
            viewport_height,
        )
        canvas.showPage()
    canvas.save()
    return output.getvalue()


def _draw_overview(
    canvas: Canvas,
    package: DungeonPackage,
    request: PdfExportRequest,
    tiles: tuple[PdfTileMetadata, ...],
    page_width: int,
    page_height: int,
) -> None:
    canvas.setFillColor(colors.black)
    canvas.setFont("Helvetica-Bold", 16)
    canvas.drawString(
        request.margin_points,
        page_height - request.margin_points,
        "ASSEMBLY OVERVIEW — NOT TO SCALE",
    )
    canvas.setFont("Helvetica", 9)
    canvas.drawString(
        request.margin_points,
        page_height - request.margin_points - 18,
        f"Package {package.id} · floor {request.floor_id} · "
        f"{request.audience.value} · {request.assembly_mode.value}",
    )
    canvas.drawString(
        request.margin_points,
        page_height - request.margin_points - 32,
        "Tile pages: print at 100% / Actual Size. Never use Fit to Page.",
    )

    rows = max(tile.row for tile in tiles) + 1
    columns = max(tile.column for tile in tiles) + 1
    diagram_width = min(page_width - 2 * request.margin_points, columns * 90)
    diagram_height = min(page_height - 2 * request.margin_points - 180, rows * 110)
    tile_width = diagram_width / columns
    tile_height = diagram_height / rows
    origin_x = (page_width - diagram_width) / 2
    origin_y = page_height - request.margin_points - 70 - diagram_height
    canvas.setLineWidth(1)
    for tile in tiles:
        x = origin_x + tile.column * tile_width
        y = origin_y + (rows - tile.row - 1) * tile_height
        canvas.rect(x, y, tile_width, tile_height, stroke=1, fill=0)
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawCentredString(
            x + tile_width / 2,
            y + tile_height / 2,
            tile.page_id,
        )
    _draw_calibration(canvas, request.margin_points, request.margin_points)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(
        request.margin_points + PRINT_CELL_POINTS + 12,
        request.margin_points + 30,
        "This square and ruler must measure exactly 1 inch.",
    )


def _draw_tile_page(
    canvas: Canvas,
    package: DungeonPackage,
    request: PdfExportRequest,
    svg: str,
    tile: PdfTileMetadata,
    page_width: int,
    page_height: int,
    viewport_width: int,
    viewport_height: int,
) -> None:
    destination_x = (page_width - viewport_width) / 2
    destination_y = request.margin_points + FOOTER_POINTS
    canvas.setFillColor(colors.black)
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawString(
        request.margin_points,
        page_height - request.margin_points + 4,
        f"{package.id} · {request.floor_id} · page {tile.page_id}",
    )
    canvas.setFont("Helvetica", 7)
    canvas.drawRightString(
        page_width - request.margin_points,
        page_height - request.margin_points + 4,
        f"source ({tile.source_x_points},{tile.source_y_points}) pt · "
        f"{request.assembly_mode.value}",
    )

    canvas.saveState()
    clipping_path = canvas.beginPath()
    clipping_path.rect(destination_x, destination_y, viewport_width, viewport_height)
    canvas.clipPath(clipping_path, stroke=0, fill=0)
    canvas.translate(
        destination_x - tile.source_x_points,
        destination_y + viewport_height + tile.source_y_points,
    )
    canvas.scale(1, -1)
    draw_svg(canvas, svg)
    canvas.restoreState()

    _draw_crop_marks(
        canvas,
        destination_x,
        destination_y,
        viewport_width,
        viewport_height,
    )
    _draw_registration_marks(
        canvas,
        destination_x,
        destination_y,
        viewport_width,
        viewport_height,
        tile,
    )
    _draw_calibration(canvas, request.margin_points, request.margin_points)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(
        request.margin_points + PRINT_CELL_POINTS + 12,
        request.margin_points + 40,
        "Print at 100% / Actual Size — do not fit or scale.",
    )
    canvas.drawString(
        request.margin_points + PRINT_CELL_POINTS + 12,
        request.margin_points + 27,
        f"Neighbors: {_neighbor_summary(tile.neighbors)}",
    )
    canvas.drawString(
        request.margin_points + PRINT_CELL_POINTS + 12,
        request.margin_points + 14,
        f"Overlap L/R/T/B: {tile.overlap_left_points}/"
        f"{tile.overlap_right_points}/{tile.overlap_top_points}/"
        f"{tile.overlap_bottom_points} pt",
    )


def _draw_calibration(canvas: Canvas, x: float, y: float) -> None:
    canvas.saveState()
    canvas.setLineWidth(1)
    canvas.setStrokeColor(colors.black)
    canvas.rect(x, y, PRINT_CELL_POINTS, PRINT_CELL_POINTS, stroke=1, fill=0)
    canvas.line(x, y - 5, x + PRINT_CELL_POINTS, y - 5)
    for offset in (0, 18, 36, 54, 72):
        tick = 6 if offset in {0, 72} else 3
        canvas.line(x + offset, y - 5 - tick, x + offset, y - 5 + tick)
    canvas.setFont("Helvetica", 6)
    canvas.drawString(x, y + PRINT_CELL_POINTS + 3, "1 inch / one 5-foot cell")
    canvas.restoreState()


def _draw_crop_marks(
    canvas: Canvas,
    x: float,
    y: float,
    width: float,
    height: float,
) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.black)
    canvas.setLineWidth(0.5)
    for corner_x, direction_x in ((x, -1), (x + width, 1)):
        for corner_y, direction_y in ((y, -1), (y + height, 1)):
            canvas.line(
                corner_x,
                corner_y,
                corner_x + direction_x * MARK_LENGTH_POINTS,
                corner_y,
            )
            canvas.line(
                corner_x,
                corner_y,
                corner_x,
                corner_y + direction_y * MARK_LENGTH_POINTS,
            )
    canvas.restoreState()


def _draw_registration_marks(
    canvas: Canvas,
    x: float,
    y: float,
    width: float,
    height: float,
    tile: PdfTileMetadata,
) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#555555"))
    canvas.setLineWidth(0.5)
    positions: list[tuple[float, float]] = []
    if tile.overlap_left_points:
        positions.append((x, y + height / 2))
    if tile.overlap_right_points:
        positions.append((x + width, y + height / 2))
    if tile.overlap_top_points:
        positions.append((x + width / 2, y + height))
    if tile.overlap_bottom_points:
        positions.append((x + width / 2, y))
    for center_x, center_y in positions:
        canvas.line(center_x - 6, center_y, center_x + 6, center_y)
        canvas.line(center_x, center_y - 6, center_x, center_y + 6)
        canvas.circle(center_x, center_y, 3, stroke=1, fill=0)
    canvas.restoreState()


def _row_label(row: int) -> str:
    label = ""
    value = row
    while True:
        value, remainder = divmod(value, 26)
        label = chr(ord("A") + remainder) + label
        if value == 0:
            return label
        value -= 1


def _neighbor_summary(neighbors: tuple[TileNeighbor, ...]) -> str:
    if not neighbors:
        return "none"
    return ", ".join(
        f"{neighbor.direction.value}:{neighbor.page_id}" for neighbor in neighbors
    )


def _failure(diagnostics: tuple[ExportDiagnostic, ...]) -> PdfArtifact:
    return PdfArtifact(
        result=PdfExportResult(
            schema_version=PDF_EXPORT_RESULT_SCHEMA_VERSION,
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
