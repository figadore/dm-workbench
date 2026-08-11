"""Narrow deterministic spatial hooks for later encounter orchestration."""

from collections import deque
from collections.abc import Iterable

from dm_dungeon.contracts.geometry import FeatureKind, PositionAnchor
from dm_dungeon.contracts.package import DungeonPackage
from dm_dungeon.validation.diagnostics import DiagnosticSeverity
from dm_dungeon.validation.geometry_contracts import (
    ENCOUNTER_FIT_RESULT_SCHEMA_VERSION,
    EncounterFitMetrics,
    EncounterFitQuery,
    EncounterFitResult,
    GeometryDiagnostic,
    GeometryDiagnosticCode,
)
from dm_dungeon.validation.grid import (
    Cell,
    WalkableGrid,
    build_walkable_grid,
    footprint_cells,
    valid_origins,
)


def evaluate_encounter_fit(
    package: DungeonPackage,
    query: EncounterFitQuery,
) -> EncounterFitResult:
    """Evaluate room space, footprints, anchors, range, cover, and objectives."""
    diagnostics: list[GeometryDiagnostic] = []
    if query.package_id != package.id:
        diagnostics.append(
            _diagnostic(
                GeometryDiagnosticCode.PACKAGE_ID_MISMATCH,
                (package.id, query.package_id),
                f"Encounter-fit query targets package {query.package_id!r}, not "
                f"{package.id!r}.",
                "Use the exact package ID pinned by the query caller.",
            )
        )

    room = next((item for item in package.rooms if item.id == query.room_id), None)
    if room is None:
        diagnostics.append(
            _diagnostic(
                GeometryDiagnosticCode.ENCOUNTER_ROOM_UNKNOWN,
                (query.room_id,),
                f"Encounter-fit query references unknown room {query.room_id!r}.",
                "Reference a declared exact room ID.",
            )
        )
        return _result(package, query, None, diagnostics)

    grid = build_walkable_grid(package)
    usable_cells = grid.room_cells[room.id] & grid.floor_cells[room.floor_id]
    required_cells = sum(
        requirement.footprint.width_cells
        * requirement.footprint.height_cells
        * requirement.count
        for requirement in query.footprints
    )
    if required_cells > len(usable_cells) or not _greedy_footprints_fit(
        room.floor_id,
        usable_cells,
        query,
        grid,
    ):
        diagnostics.append(
            _diagnostic(
                GeometryDiagnosticCode.ENCOUNTER_FOOTPRINT_DOES_NOT_FIT,
                (room.id, *(item.id for item in query.footprints)),
                f"Requested footprints need {required_cells} cells but cannot be "
                f"placed in {len(usable_cells)} usable room cells.",
                "Reduce footprint count/size, remove blockers, or enlarge the room.",
            )
        )

    anchors = {anchor.id: anchor for anchor in package.position_anchors}
    valid_start_ids = _valid_room_anchor_ids(
        query.starting_anchor_ids,
        room.id,
        room.floor_id,
        usable_cells,
        anchors,
        diagnostics,
    )
    valid_objective_ids = _valid_room_anchor_ids(
        query.objective_anchor_ids,
        room.id,
        room.floor_id,
        usable_cells,
        anchors,
        diagnostics,
    )

    reachable_objective_ids = _reachable_objectives(
        query.starting_anchor_ids,
        query.objective_anchor_ids,
        valid_start_ids,
        valid_objective_ids,
        anchors,
        usable_cells,
    )
    unreachable_objective_ids = set(query.objective_anchor_ids) - set(
        reachable_objective_ids
    )
    if unreachable_objective_ids:
        diagnostics.append(
            _diagnostic(
                GeometryDiagnosticCode.ENCOUNTER_OBJECTIVE_UNREACHABLE,
                (room.id, *unreachable_objective_ids),
                "One or more objective anchors are unreachable from valid starts.",
                "Move objectives/starts or clear blocking geometry inside the room.",
            )
        )

    maximum_range = _maximum_manhattan_range(usable_cells)
    if maximum_range < query.minimum_range_cells:
        diagnostics.append(
            _diagnostic(
                GeometryDiagnosticCode.ENCOUNTER_RANGE_INSUFFICIENT,
                (room.id,),
                f"Room maximum open range is {maximum_range} cells; query requires "
                f"{query.minimum_range_cells}.",
                "Use a larger room or lower the required tactical range.",
            )
        )

    cover_feature_ids = tuple(
        sorted(
            feature.id
            for feature in package.features
            if feature.room_id == room.id
            and feature.kind
            in {
                FeatureKind.ALTAR,
                FeatureKind.FURNITURE,
                FeatureKind.PILLAR,
                FeatureKind.STATUE,
            }
        )
    )
    if len(cover_feature_ids) < query.minimum_cover_features:
        diagnostics.append(
            _diagnostic(
                GeometryDiagnosticCode.ENCOUNTER_COVER_INSUFFICIENT,
                (room.id, *cover_feature_ids),
                f"Room has {len(cover_feature_ids)} cover features; query requires "
                f"{query.minimum_cover_features}.",
                "Add validated cover geometry or lower the cover requirement.",
            )
        )

    metrics = EncounterFitMetrics(
        usable_cell_count=len(usable_cells),
        required_footprint_cell_count=required_cells,
        maximum_open_range_cells=maximum_range,
        cover_feature_ids=cover_feature_ids,
        reachable_starting_anchor_ids=valid_start_ids,
        reachable_objective_anchor_ids=reachable_objective_ids,
    )
    return _result(package, query, metrics, diagnostics)


def _greedy_footprints_fit(
    floor_id: str,
    usable_cells: set[Cell],
    query: EncounterFitQuery,
    grid: WalkableGrid,
) -> bool:
    requirements = sorted(
        query.footprints,
        key=lambda item: (
            -(item.footprint.width_cells * item.footprint.height_cells),
            item.id,
        ),
    )
    occupied: set[Cell] = set()
    for requirement in requirements:
        origins = sorted(
            valid_origins(
                grid,
                floor_id,
                requirement.footprint,
                usable_cells,
            )
        )
        for _ in range(requirement.count):
            placement = next(
                (
                    origin
                    for origin in origins
                    if {
                        (cell_x, cell_y)
                        for _, cell_x, cell_y in footprint_cells(
                            (floor_id, origin[0], origin[1]),
                            requirement.footprint,
                        )
                    }.isdisjoint(occupied)
                ),
                None,
            )
            if placement is None:
                return False
            occupied.update(
                (cell_x, cell_y)
                for _, cell_x, cell_y in footprint_cells(
                    (floor_id, placement[0], placement[1]),
                    requirement.footprint,
                )
            )
    return True


def _valid_room_anchor_ids(
    requested_ids: tuple[str, ...],
    room_id: str,
    floor_id: str,
    usable_cells: set[Cell],
    anchors: dict[str, PositionAnchor],
    diagnostics: list[GeometryDiagnostic],
) -> tuple[str, ...]:
    valid: list[str] = []
    for anchor_id in requested_ids:
        anchor = anchors.get(anchor_id)
        if anchor is None or (
            anchor.room_id != room_id
            or anchor.floor_id != floor_id
            or (anchor.position.x, anchor.position.y) not in usable_cells
        ):
            diagnostics.append(
                _diagnostic(
                    GeometryDiagnosticCode.ENCOUNTER_ANCHOR_INVALID,
                    (room_id, anchor_id),
                    f"Anchor {anchor_id!r} is missing, blocked, or outside room "
                    f"{room_id!r}.",
                    "Use an unblocked position anchor declared inside the query room.",
                )
            )
        else:
            valid.append(anchor_id)
    return tuple(valid)


def _reachable_objectives(
    requested_start_ids: tuple[str, ...],
    requested_objective_ids: tuple[str, ...],
    valid_start_ids: tuple[str, ...],
    valid_objective_ids: tuple[str, ...],
    anchors: dict[str, PositionAnchor],
    usable_cells: set[Cell],
) -> tuple[str, ...]:
    if not requested_objective_ids:
        return ()
    if not requested_start_ids:
        return valid_objective_ids
    starts = {
        (anchors[anchor_id].position.x, anchors[anchor_id].position.y)
        for anchor_id in valid_start_ids
    }
    reachable = _flood_room(usable_cells, starts)
    return tuple(
        anchor_id
        for anchor_id in valid_objective_ids
        if (
            anchors[anchor_id].position.x,
            anchors[anchor_id].position.y,
        )
        in reachable
    )


def _flood_room(usable_cells: set[Cell], starts: set[Cell]) -> set[Cell]:
    pending = deque(sorted(starts & usable_cells))
    visited = set(pending)
    while pending:
        x, y = pending.popleft()
        for neighbor in ((x, y - 1), (x - 1, y), (x + 1, y), (x, y + 1)):
            if neighbor in usable_cells and neighbor not in visited:
                visited.add(neighbor)
                pending.append(neighbor)
    return visited


def _maximum_manhattan_range(cells: set[Cell]) -> int:
    if not cells:
        return 0
    return max(
        abs(first[0] - second[0]) + abs(first[1] - second[1])
        for first in cells
        for second in cells
    )


def _result(
    package: DungeonPackage,
    query: EncounterFitQuery,
    metrics: EncounterFitMetrics | None,
    diagnostics: list[GeometryDiagnostic],
) -> EncounterFitResult:
    ordered = tuple(
        sorted(
            diagnostics,
            key=lambda item: (item.code.value, item.affected_ids, item.message),
        )
    )
    fits = not any(item.severity is DiagnosticSeverity.ERROR for item in ordered)
    return EncounterFitResult(
        schema_version=ENCOUNTER_FIT_RESULT_SCHEMA_VERSION,
        package_id=package.id,
        room_id=query.room_id,
        fits=fits,
        metrics=metrics,
        diagnostics=ordered,
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
