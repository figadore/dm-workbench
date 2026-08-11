"""Deterministic anchor pathfinding tests."""

from dm_dungeon import DungeonPackage, to_canonical_json
from dm_dungeon.validation import (
    CreatureFootprint,
    GeometryDiagnosticCode,
    PathQuery,
    find_anchor_path,
)


def entrance_and_exit_ids(package: DungeonPackage) -> tuple[str, str]:
    entrance = next(
        anchor.id for anchor in package.position_anchors if anchor.kind == "entrance"
    )
    exit_id = next(
        anchor.id for anchor in package.position_anchors if anchor.kind == "exit"
    )
    return entrance, exit_id


def test_pathfinding_crosses_paired_floor_transition_deterministically(
    generated_package: DungeonPackage,
) -> None:
    entrance, exit_id = entrance_and_exit_ids(generated_package)
    query = PathQuery(
        schema_version="1.0.0",
        package_id=generated_package.id,
        start_anchor_id=entrance,
        end_anchor_id=exit_id,
    )

    first = find_anchor_path(generated_package, query)
    second = find_anchor_path(generated_package, query)

    assert first.success is True
    assert first.distance_cells == len(first.path) - 1
    assert {step.floor_id for step in first.path} == {"floor_upper", "floor_lower"}
    assert first == second
    assert to_canonical_json(first) == to_canonical_json(second)


def test_unknown_anchor_returns_structured_failure(
    generated_package: DungeonPackage,
) -> None:
    _, exit_id = entrance_and_exit_ids(generated_package)
    query = PathQuery(
        schema_version="1.0.0",
        package_id=generated_package.id,
        start_anchor_id="anchor_missing",
        end_anchor_id=exit_id,
    )

    result = find_anchor_path(generated_package, query)

    assert result.success is False
    assert {item.code for item in result.diagnostics} == {
        GeometryDiagnosticCode.PATH_ANCHOR_UNKNOWN
    }


def test_large_footprint_fails_at_anchor(generated_package: DungeonPackage) -> None:
    entrance, exit_id = entrance_and_exit_ids(generated_package)
    query = PathQuery(
        schema_version="1.0.0",
        package_id=generated_package.id,
        start_anchor_id=entrance,
        end_anchor_id=exit_id,
        footprint=CreatureFootprint(width_cells=20, height_cells=20),
    )

    result = find_anchor_path(generated_package, query)

    assert result.success is False
    assert GeometryDiagnosticCode.PATH_ANCHOR_BLOCKED in {
        item.code for item in result.diagnostics
    }


def test_removed_floor_transition_has_no_cross_floor_path(
    generated_package: DungeonPackage,
) -> None:
    entrance, exit_id = entrance_and_exit_ids(generated_package)
    broken = generated_package.model_copy(update={"vertical_links": ()})
    query = PathQuery(
        schema_version="1.0.0",
        package_id=broken.id,
        start_anchor_id=entrance,
        end_anchor_id=exit_id,
    )

    result = find_anchor_path(broken, query)

    assert result.success is False
    assert GeometryDiagnosticCode.PATH_NOT_FOUND in {
        item.code for item in result.diagnostics
    }
