"""Small file-oriented CLI for the independently runnable dungeon package."""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from dm_dungeon.contracts.package import DungeonPackage
from dm_dungeon.contracts.package_v2 import DungeonPackageV2
from dm_dungeon.export import (
    AssemblyMode,
    PaperSize,
    PdfExportRequest,
    PngExportRequest,
    Roll20ExportRequest,
    export_pdf,
    export_png,
    export_roll20_bundle,
    write_pdf_artifact,
    write_png_artifact,
    write_roll20_directory,
    write_roll20_zip,
)
from dm_dungeon.layout import generate_layout, read_layout_request
from dm_dungeon.rendering import (
    RenderAudience,
    SvgAnnotationMode,
    SvgRenderRequest,
    SvgThemeName,
    render_svg,
    write_svg,
)
from dm_dungeon.serialization import (
    dungeon_package_json_schema,
    read_dungeon_package,
    to_canonical_json,
)
from dm_dungeon.validation import validate_geometry, validate_topology


def build_parser() -> argparse.ArgumentParser:
    """Build the dm-dungeon argument parser."""
    parser = argparse.ArgumentParser(
        prog="dm-dungeon",
        description="Validate and canonicalize renderer-neutral dungeon packages.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="validate a package JSON file")
    validate.add_argument("input", type=Path)

    canonicalize = subparsers.add_parser(
        "canonicalize",
        help="validate and emit canonical package JSON",
    )
    canonicalize.add_argument("input", type=Path)
    canonicalize.add_argument("--output", "-o", type=Path)

    layout = subparsers.add_parser(
        "layout",
        help="generate an exact package from a versioned layout request",
    )
    layout.add_argument("input", type=Path)
    layout.add_argument("--output", "-o", type=Path)

    render = subparsers.add_parser(
        "render-svg",
        help="render one validated floor as deterministic SVG",
    )
    render.add_argument("input", type=Path)
    render.add_argument("--floor", required=True)
    render.add_argument(
        "--audience",
        choices=[item.value for item in RenderAudience],
        required=True,
    )
    render.add_argument("--output", "-o", type=Path, required=True)
    render.add_argument("--pixels-per-cell", type=int, default=64)
    render.add_argument("--no-grid", action="store_false", dest="show_grid")
    render.add_argument("--no-labels", action="store_false", dest="show_labels")
    render.add_argument(
        "--annotations",
        choices=[item.value for item in SvgAnnotationMode],
        default=SvgAnnotationMode.CALLOUTS.value,
        help="trusted map annotation projection (developer_ids is inspection-only)",
    )
    render.add_argument("--no-markers", action="store_false", dest="show_markers")
    render.add_argument(
        "--theme",
        choices=[item.value for item in SvgThemeName],
        default=SvgThemeName.LOW_INK.value,
    )

    png = subparsers.add_parser("export-png", help="export PNG plus manifest")
    _add_common_export_arguments(png)
    png.add_argument("--pixels-per-cell", type=int, default=70)
    png.add_argument("--dpi", type=int, default=140)

    pdf = subparsers.add_parser(
        "export-pdf",
        help="export exact-scale tiled print PDF plus manifest",
    )
    _add_common_export_arguments(pdf)
    pdf.add_argument(
        "--paper",
        choices=[item.value for item in PaperSize],
        default=PaperSize.LETTER.value,
    )
    pdf.add_argument(
        "--assembly",
        choices=[item.value for item in AssemblyMode],
        default=AssemblyMode.OVERLAP_AND_TAPE.value,
    )
    pdf.add_argument("--margin-points", type=int, default=36)
    pdf.add_argument("--overlap-points", type=int)
    pdf.add_argument("--no-overview", action="store_false", dest="include_overview")

    roll20 = subparsers.add_parser(
        "export-roll20",
        help="export paired PNGs and a Roll20 setup manifest as a ZIP",
    )
    roll20.add_argument("input", type=Path)
    roll20.add_argument("--floor", required=True)
    roll20.add_argument(
        "--audience",
        choices=[item.value for item in RenderAudience],
        required=True,
    )
    roll20.add_argument("--prefix", required=True)
    roll20.add_argument("--output", "-o", type=Path, required=True)
    roll20.add_argument("--directory", type=Path)
    roll20.add_argument("--pixels-per-cell", type=int, default=70)
    roll20.add_argument("--dpi", type=int, default=140)
    roll20.add_argument("--include-token-placements", action="store_true")
    roll20.add_argument("--no-labels", action="store_false", dest="show_labels")
    roll20.add_argument("--no-markers", action="store_false", dest="show_markers")
    roll20.add_argument(
        "--theme",
        choices=[item.value for item in SvgThemeName],
        default=SvgThemeName.LOW_INK.value,
    )
    roll20.add_argument("--maximum-ink-basis-points", type=int, default=3500)

    schema = subparsers.add_parser("schema", help="emit the current JSON Schema")
    schema.add_argument("--output", "-o", type=Path)
    return parser


def _add_common_export_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("input", type=Path)
    parser.add_argument("--floor", required=True)
    parser.add_argument(
        "--audience",
        choices=[item.value for item in RenderAudience],
        required=True,
    )
    parser.add_argument("--output", "-o", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--no-grid", action="store_false", dest="include_grid")
    parser.add_argument("--no-labels", action="store_false", dest="show_labels")
    parser.add_argument("--no-markers", action="store_false", dest="show_markers")
    parser.add_argument(
        "--theme",
        choices=[item.value for item in SvgThemeName],
        default=SvgThemeName.LOW_INK.value,
    )
    parser.add_argument("--maximum-ink-basis-points", type=int, default=3500)


def _require_renderable_package(
    package: DungeonPackage | DungeonPackageV2,
) -> DungeonPackage | DungeonPackageV2:
    """Narrow the reader result to packages supported by all CLI operations."""
    return package


def _emit(document: str, output: Path | None) -> None:
    if output is None:
        sys.stdout.write(f"{document}\n")
    else:
        output.write_text(document, encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the file-oriented dungeon package CLI."""
    parser = build_parser()
    arguments = parser.parse_args(list(argv) if argv is not None else None)

    try:
        if arguments.command == "validate":
            package = _require_renderable_package(read_dungeon_package(arguments.input))
            topology_report = validate_topology(package.topology)
            if not topology_report.valid:
                sys.stderr.write(f"{to_canonical_json(topology_report)}\n")
                return 1
            geometry_report = validate_geometry(package)
            if not geometry_report.valid:
                sys.stderr.write(f"{to_canonical_json(geometry_report)}\n")
                return 1
            print(
                f"valid DungeonPackage {package.schema_version}: {package.id}",
                file=sys.stdout,
            )
            return 0

        if arguments.command == "canonicalize":
            canonical_package = read_dungeon_package(arguments.input)
            _emit(to_canonical_json(canonical_package), arguments.output)
            return 0

        if arguments.command == "layout":
            layout_request = read_layout_request(arguments.input)
            layout_result = generate_layout(layout_request)
            _emit(to_canonical_json(layout_result), arguments.output)
            return 0 if layout_result.success else 1

        if arguments.command == "render-svg":
            package = _require_renderable_package(read_dungeon_package(arguments.input))
            render_request = SvgRenderRequest(
                schema_version="1.0.0",
                package_id=package.id,
                floor_id=arguments.floor,
                audience=RenderAudience(arguments.audience),
                pixels_per_cell=arguments.pixels_per_cell,
                show_grid=arguments.show_grid,
                show_labels=arguments.show_labels,
                annotation_mode=SvgAnnotationMode(arguments.annotations),
                show_markers=arguments.show_markers,
                theme=SvgThemeName(arguments.theme),
            )
            render_result = render_svg(package, render_request)
            if not render_result.success:
                sys.stderr.write(f"{to_canonical_json(render_result)}\n")
                return 1
            write_svg(arguments.output, render_result)
            return 0

        if arguments.command == "export-png":
            package = _require_renderable_package(read_dungeon_package(arguments.input))
            png_request = PngExportRequest(
                schema_version="1.0.0",
                package_id=package.id,
                floor_id=arguments.floor,
                audience=RenderAudience(arguments.audience),
                pixels_per_cell=arguments.pixels_per_cell,
                dpi=arguments.dpi,
                include_grid=arguments.include_grid,
                show_labels=arguments.show_labels,
                show_markers=arguments.show_markers,
                theme=SvgThemeName(arguments.theme),
                maximum_ink_coverage_basis_points=(arguments.maximum_ink_basis_points),
            )
            png_artifact = export_png(package, png_request)
            if not png_artifact.result.success:
                sys.stderr.write(f"{to_canonical_json(png_artifact.result)}\n")
                return 1
            write_png_artifact(
                arguments.output,
                arguments.manifest,
                png_artifact,
            )
            return 0

        if arguments.command == "export-pdf":
            package = _require_renderable_package(read_dungeon_package(arguments.input))
            assembly_mode = AssemblyMode(arguments.assembly)
            overlap_points = arguments.overlap_points
            if overlap_points is None:
                overlap_points = (
                    0 if assembly_mode is AssemblyMode.TRIM_AND_BUTT else 18
                )
            pdf_request = PdfExportRequest(
                schema_version="1.0.0",
                package_id=package.id,
                floor_id=arguments.floor,
                audience=RenderAudience(arguments.audience),
                paper_size=PaperSize(arguments.paper),
                assembly_mode=assembly_mode,
                margin_points=arguments.margin_points,
                overlap_points=overlap_points,
                include_overview=arguments.include_overview,
                include_grid=arguments.include_grid,
                show_labels=arguments.show_labels,
                show_markers=arguments.show_markers,
                theme=SvgThemeName(arguments.theme),
                maximum_ink_coverage_basis_points=(arguments.maximum_ink_basis_points),
            )
            pdf_artifact = export_pdf(package, pdf_request)
            if not pdf_artifact.result.success:
                sys.stderr.write(f"{to_canonical_json(pdf_artifact.result)}\n")
                return 1
            write_pdf_artifact(
                arguments.output,
                arguments.manifest,
                pdf_artifact,
            )
            return 0

        if arguments.command == "export-roll20":
            package = _require_renderable_package(read_dungeon_package(arguments.input))
            roll20_request = Roll20ExportRequest(
                schema_version="1.0.0",
                package_id=package.id,
                floor_id=arguments.floor,
                audience=RenderAudience(arguments.audience),
                filename_prefix=arguments.prefix,
                pixels_per_cell=arguments.pixels_per_cell,
                dpi=arguments.dpi,
                include_token_placements=arguments.include_token_placements,
                show_labels=arguments.show_labels,
                show_markers=arguments.show_markers,
                theme=SvgThemeName(arguments.theme),
                maximum_ink_coverage_basis_points=(arguments.maximum_ink_basis_points),
            )
            roll20_artifact = export_roll20_bundle(package, roll20_request)
            if not roll20_artifact.result.success:
                sys.stderr.write(f"{to_canonical_json(roll20_artifact.result)}\n")
                return 1
            write_roll20_zip(arguments.output, roll20_artifact)
            if arguments.directory is not None:
                write_roll20_directory(arguments.directory, roll20_artifact)
            return 0

        if arguments.command == "schema":
            document = json.dumps(
                dungeon_package_json_schema(),
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            _emit(document, arguments.output)
            return 0
    except (OSError, ValueError) as error:
        parser.exit(2, f"dm-dungeon: error: {error}\n")

    parser.error(f"unknown command: {arguments.command}")


if __name__ == "__main__":
    raise SystemExit(main())
