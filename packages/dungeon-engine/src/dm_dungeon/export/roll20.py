"""Deterministic Roll20-compatible paired-image bundle export."""

import hashlib
import io
import zipfile
from collections.abc import Iterable

from dm_dungeon.contracts.geometry import DoorLayout
from dm_dungeon.contracts.package import DungeonPackage
from dm_dungeon.contracts.package_v2 import DoorLayoutV2, DungeonPackageV2
from dm_dungeon.contracts.topology import DoorType
from dm_dungeon.export.contracts import (
    ExportDiagnostic,
    ExportDiagnosticCode,
    PngExportRequest,
)
from dm_dungeon.export.png import export_png
from dm_dungeon.export.roll20_contracts import (
    ROLL20_EXPORT_MANIFEST_SCHEMA_VERSION,
    ROLL20_EXPORT_RESULT_SCHEMA_VERSION,
    ROLL20_EXPORTER_VERSION,
    Roll20Artifact,
    Roll20AssetRole,
    Roll20BundleFile,
    Roll20DoorSegment,
    Roll20ExportManifest,
    Roll20ExportRequest,
    Roll20ExportResult,
    Roll20GridMetadata,
    Roll20RasterAsset,
    Roll20TokenPlacement,
    Roll20WallPolygon,
)
from dm_dungeon.rendering import RenderAudience
from dm_dungeon.serialization import to_canonical_json
from dm_dungeon.validation.diagnostics import DiagnosticSeverity


def _roll20_door_type(
    door: DoorLayoutV2 | DoorLayout,
    audience: RenderAudience,
) -> DoorType:
    """Expose only player-safe door state in Roll20 metadata."""

    if isinstance(door, DoorLayoutV2):
        if audience is RenderAudience.PLAYER:
            return DoorType.NORMAL
        if door.mechanics.concealed:
            return DoorType.SECRET
        if door.mechanics.trap_id is not None:
            return DoorType.TRAPPED
        if door.mechanics.gate_id is not None:
            return DoorType.LOCKED
        return DoorType.NORMAL
    if audience is RenderAudience.PLAYER and door.door_type is DoorType.SECRET:
        return DoorType.NORMAL
    return door.door_type


def export_roll20_bundle(
    package: DungeonPackage,
    request: Roll20ExportRequest,
) -> Roll20Artifact:
    """Export paired PNGs, safe metadata, and deterministic ZIP bytes."""
    grid_on = export_png(
        package,
        _png_request(request, include_grid=True),
    )
    gridless = export_png(
        package,
        _png_request(request, include_grid=False),
    )
    failed_pngs = tuple(
        artifact for artifact in (grid_on, gridless) if not artifact.result.success
    )
    if failed_pngs:
        return _failure(
            tuple(
                diagnostic
                for artifact in failed_pngs
                for diagnostic in artifact.result.diagnostics
            )
        )

    assert grid_on.data is not None
    assert gridless.data is not None
    assert grid_on.result.manifest is not None
    assert gridless.result.manifest is not None
    grid_manifest = grid_on.result.manifest
    gridless_manifest = gridless.result.manifest
    floor = next(item for item in package.floors if item.id == request.floor_id)
    expected_dimensions = (
        floor.bounds.width_cells * request.pixels_per_cell,
        floor.bounds.height_cells * request.pixels_per_cell,
    )
    if (
        (grid_manifest.width_pixels, grid_manifest.height_pixels) != expected_dimensions
        or (gridless_manifest.width_pixels, gridless_manifest.height_pixels)
        != expected_dimensions
        or grid_manifest.rendered_component_ids
        != gridless_manifest.rendered_component_ids
    ):
        return _failure(
            (
                _diagnostic(
                    ExportDiagnosticCode.BUNDLE_INCONSISTENT,
                    (package.id, request.floor_id),
                    "Roll20 grid-on/gridless assets disagree on dimensions or visible "
                    "components.",
                    "Regenerate both images from one pinned package/request.",
                ),
            )
        )

    grid_filename = f"{request.filename_prefix}.grid.png"
    gridless_filename = f"{request.filename_prefix}.gridless.png"
    manifest_filename = f"{request.filename_prefix}.manifest.json"
    allowed_ids = set(grid_manifest.rendered_component_ids)
    wall_polygons = tuple(
        Roll20WallPolygon(
            component_id=room.id,
            floor_id=room.floor_id,
            points=room.boundary.points,
        )
        for room in package.rooms
        if room.floor_id == request.floor_id and room.id in allowed_ids
    )
    doors = (
        package.composable_doors
        if isinstance(package, DungeonPackageV2)
        else package.doors
    )
    door_segments = tuple(
        Roll20DoorSegment(
            component_id=door.id,
            floor_id=door.floor_id,
            door_type=_roll20_door_type(door, request.audience),
            start=door.segment.start,
            end=door.segment.end,
        )
        for door in doors
        if door.floor_id == request.floor_id and door.id in allowed_ids
    )
    token_placements = (
        tuple(
            Roll20TokenPlacement(
                anchor_id=anchor.id,
                kind=anchor.kind,
                x_pixels=anchor.position.x * request.pixels_per_cell,
                y_pixels=anchor.position.y * request.pixels_per_cell,
            )
            for anchor in package.position_anchors
            if anchor.floor_id == request.floor_id and anchor.id in allowed_ids
        )
        if request.include_token_placements
        else ()
    )
    assets = (
        Roll20RasterAsset(
            role=Roll20AssetRole.GRID_ON_MAP,
            filename=grid_filename,
            media_type="image/png",
            source_svg_sha256=grid_manifest.source_svg_sha256,
            sha256=grid_manifest.asset_sha256,
            width_pixels=grid_manifest.width_pixels,
            height_pixels=grid_manifest.height_pixels,
        ),
        Roll20RasterAsset(
            role=Roll20AssetRole.GRIDLESS_MAP,
            filename=gridless_filename,
            media_type="image/png",
            source_svg_sha256=gridless_manifest.source_svg_sha256,
            sha256=gridless_manifest.asset_sha256,
            width_pixels=gridless_manifest.width_pixels,
            height_pixels=gridless_manifest.height_pixels,
        ),
    )
    manifest = Roll20ExportManifest(
        schema_version=ROLL20_EXPORT_MANIFEST_SCHEMA_VERSION,
        exporter_version=ROLL20_EXPORTER_VERSION,
        package_id=package.id,
        floor_id=request.floor_id,
        audience=request.audience,
        theme=request.theme,
        grid=Roll20GridMetadata(
            width_cells=floor.bounds.width_cells,
            height_cells=floor.bounds.height_cells,
            pixels_per_cell=request.pixels_per_cell,
            cell_scale_feet=5,
            origin_x_cells=0,
            origin_y_cells=0,
            origin_x_pixels=0,
            origin_y_pixels=0,
        ),
        assets=assets,
        wall_polygons=wall_polygons,
        door_segments=door_segments,
        token_placements=token_placements,
        rendered_component_ids=grid_manifest.rendered_component_ids,
        direct_upload_supported=False,
        dynamic_lighting_import_supported=False,
    )
    manifest_data = to_canonical_json(manifest).encode("utf-8")
    files = tuple(
        sorted(
            (
                Roll20BundleFile(filename=grid_filename, data=grid_on.data),
                Roll20BundleFile(
                    filename=gridless_filename,
                    data=gridless.data,
                ),
                Roll20BundleFile(filename=manifest_filename, data=manifest_data),
            ),
            key=lambda item: item.filename,
        )
    )
    zip_data = _deterministic_zip(files)
    result = Roll20ExportResult(
        schema_version=ROLL20_EXPORT_RESULT_SCHEMA_VERSION,
        success=True,
        manifest=manifest,
        bundle_sha256=hashlib.sha256(zip_data).hexdigest(),
        diagnostics=(),
    )
    return Roll20Artifact(result=result, files=files, zip_data=zip_data)


def _png_request(
    request: Roll20ExportRequest,
    include_grid: bool,
) -> PngExportRequest:
    return PngExportRequest(
        schema_version="1.0.0",
        package_id=request.package_id,
        floor_id=request.floor_id,
        audience=request.audience,
        pixels_per_cell=request.pixels_per_cell,
        dpi=request.dpi,
        include_grid=include_grid,
        show_labels=request.show_labels,
        show_markers=request.show_markers,
        theme=request.theme,
        maximum_ink_coverage_basis_points=(request.maximum_ink_coverage_basis_points),
    )


def _deterministic_zip(files: tuple[Roll20BundleFile, ...]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_STORED) as archive:
        for bundle_file in files:
            info = zipfile.ZipInfo(
                filename=bundle_file.filename,
                date_time=(1980, 1, 1, 0, 0, 0),
            )
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, bundle_file.data)
    return output.getvalue()


def _failure(diagnostics: tuple[ExportDiagnostic, ...]) -> Roll20Artifact:
    return Roll20Artifact(
        result=Roll20ExportResult(
            schema_version=ROLL20_EXPORT_RESULT_SCHEMA_VERSION,
            success=False,
            manifest=None,
            bundle_sha256=None,
            diagnostics=tuple(
                sorted(
                    diagnostics,
                    key=lambda item: (item.code.value, item.affected_ids, item.message),
                )
            ),
        ),
        files=(),
        zip_data=None,
    )


def _diagnostic(
    code: ExportDiagnosticCode,
    affected_ids: Iterable[str],
    message: str,
    repair_hint: str,
) -> ExportDiagnostic:
    return ExportDiagnostic(
        code=code,
        severity=DiagnosticSeverity.ERROR,
        message=message,
        affected_ids=tuple(sorted(set(affected_ids))),
        repair_hint=repair_hint,
        source_code=None,
    )
