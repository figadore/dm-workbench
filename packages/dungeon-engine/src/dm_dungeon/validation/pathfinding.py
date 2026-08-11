"""Deterministic anchor-to-anchor pathfinding over exact dungeon geometry."""

from collections.abc import Iterable

from dm_dungeon.contracts.geometry import GridPoint
from dm_dungeon.contracts.package import DungeonPackage
from dm_dungeon.validation.diagnostics import DiagnosticSeverity
from dm_dungeon.validation.geometry_contracts import (
    PATH_RESULT_SCHEMA_VERSION,
    GeometryDiagnostic,
    GeometryDiagnosticCode,
    PathQuery,
    PathResult,
    PathStep,
)
from dm_dungeon.validation.grid import (
    build_walkable_grid,
    footprint_fits,
    shortest_path,
)


def find_anchor_path(package: DungeonPackage, query: PathQuery) -> PathResult:
    """Find a deterministic shortest path between two declared anchors."""
    diagnostics: list[GeometryDiagnostic] = []
    if query.package_id != package.id:
        diagnostics.append(
            _diagnostic(
                GeometryDiagnosticCode.PACKAGE_ID_MISMATCH,
                (package.id, query.package_id),
                f"Path query targets package {query.package_id!r}, not {package.id!r}.",
                "Use the exact package ID pinned by the query caller.",
            )
        )

    anchors = {anchor.id: anchor for anchor in package.position_anchors}
    start_anchor = anchors.get(query.start_anchor_id)
    end_anchor = anchors.get(query.end_anchor_id)
    for anchor_id, anchor in (
        (query.start_anchor_id, start_anchor),
        (query.end_anchor_id, end_anchor),
    ):
        if anchor is None:
            diagnostics.append(
                _diagnostic(
                    GeometryDiagnosticCode.PATH_ANCHOR_UNKNOWN,
                    (anchor_id,),
                    f"Path query references unknown anchor {anchor_id!r}.",
                    "Reference a declared position anchor in this package.",
                )
            )
    if diagnostics or start_anchor is None or end_anchor is None:
        return _failed_result(package, diagnostics)

    grid = build_walkable_grid(package)
    start = (
        start_anchor.floor_id,
        start_anchor.position.x,
        start_anchor.position.y,
    )
    end = (
        end_anchor.floor_id,
        end_anchor.position.x,
        end_anchor.position.y,
    )
    for anchor, cell in ((start_anchor, start), (end_anchor, end)):
        if not footprint_fits(grid, cell, query.footprint):
            diagnostics.append(
                _diagnostic(
                    GeometryDiagnosticCode.PATH_ANCHOR_BLOCKED,
                    (anchor.id,),
                    f"Footprint does not fit at anchor {anchor.id!r}.",
                    "Move the anchor or use a smaller footprint.",
                )
            )
    if diagnostics:
        return _failed_result(package, diagnostics)

    path = shortest_path(grid, start, end, query.footprint)
    if path is None:
        diagnostics.append(
            _diagnostic(
                GeometryDiagnosticCode.PATH_NOT_FOUND,
                (query.start_anchor_id, query.end_anchor_id),
                f"No walkable path connects anchors {query.start_anchor_id!r} and "
                f"{query.end_anchor_id!r} for the requested footprint.",
                "Connect the regions, clear blockers, or use a smaller footprint.",
            )
        )
        return _failed_result(package, diagnostics)

    return PathResult(
        schema_version=PATH_RESULT_SCHEMA_VERSION,
        package_id=package.id,
        success=True,
        distance_cells=len(path) - 1,
        path=tuple(
            PathStep(
                floor_id=floor_id,
                point=GridPoint(x=x, y=y),
            )
            for floor_id, x, y in path
        ),
        diagnostics=(),
    )


def _failed_result(
    package: DungeonPackage,
    diagnostics: list[GeometryDiagnostic],
) -> PathResult:
    return PathResult(
        schema_version=PATH_RESULT_SCHEMA_VERSION,
        package_id=package.id,
        success=False,
        distance_cells=None,
        path=(),
        diagnostics=tuple(
            sorted(
                diagnostics,
                key=lambda item: (item.code.value, item.affected_ids, item.message),
            )
        ),
    )


def _diagnostic(
    code: GeometryDiagnosticCode,
    affected_ids: Iterable[str],
    message: str,
    repair_hint: str,
) -> GeometryDiagnostic:
    return GeometryDiagnostic(
        code=code,
        severity=DiagnosticSeverity.ERROR,
        message=message,
        affected_ids=tuple(sorted(set(affected_ids))),
        repair_hint=repair_hint,
    )
