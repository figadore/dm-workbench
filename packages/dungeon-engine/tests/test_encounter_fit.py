"""Narrow deterministic encounter spatial-fit tests."""

from dm_dungeon import DungeonPackage
from dm_dungeon.validation import (
    CreatureFootprint,
    EncounterFitQuery,
    FootprintRequirement,
    GeometryDiagnosticCode,
    evaluate_encounter_fit,
)


def test_synthetic_entrance_satisfies_small_spatial_query(
    synthetic_package: DungeonPackage,
) -> None:
    start_anchor = next(
        anchor
        for anchor in synthetic_package.position_anchors
        if anchor.room_id == "room_entrance"
    )
    query = EncounterFitQuery(
        schema_version="1.0.0",
        package_id=synthetic_package.id,
        room_id="room_entrance",
        footprints=(
            FootprintRequirement(
                id="guardian_group",
                footprint=CreatureFootprint(width_cells=1, height_cells=1),
                count=4,
            ),
        ),
        starting_anchor_ids=(start_anchor.id,),
        objective_anchor_ids=(),
        minimum_range_cells=2,
        minimum_cover_features=0,
    )

    result = evaluate_encounter_fit(synthetic_package, query)

    assert result.fits is True
    assert result.metrics is not None
    assert result.metrics.usable_cell_count >= 4
    assert result.metrics.required_footprint_cell_count == 4
    assert result.metrics.cover_feature_ids == ()
    assert result.metrics.reachable_starting_anchor_ids == (start_anchor.id,)


def test_oversized_footprint_fails_conservatively(
    synthetic_package: DungeonPackage,
) -> None:
    query = EncounterFitQuery(
        schema_version="1.0.0",
        package_id=synthetic_package.id,
        room_id="room_sanctum",
        footprints=(
            FootprintRequirement(
                id="oversized_creature",
                footprint=CreatureFootprint(width_cells=20, height_cells=20),
                count=1,
            ),
        ),
    )

    result = evaluate_encounter_fit(synthetic_package, query)

    assert result.fits is False
    assert GeometryDiagnosticCode.ENCOUNTER_FOOTPRINT_DOES_NOT_FIT in {
        item.code for item in result.diagnostics
    }


def test_range_cover_and_anchor_failures_are_explicit(
    synthetic_package: DungeonPackage,
) -> None:
    query = EncounterFitQuery(
        schema_version="1.0.0",
        package_id=synthetic_package.id,
        room_id="room_entrance",
        footprints=(
            FootprintRequirement(
                id="scout",
                footprint=CreatureFootprint(),
                count=1,
            ),
        ),
        starting_anchor_ids=("anchor_archive_exit",),
        objective_anchor_ids=("anchor_guardian_start",),
        minimum_range_cells=100,
        minimum_cover_features=3,
    )

    result = evaluate_encounter_fit(synthetic_package, query)
    codes = {item.code for item in result.diagnostics}

    assert result.fits is False
    assert GeometryDiagnosticCode.ENCOUNTER_ANCHOR_INVALID in codes
    assert GeometryDiagnosticCode.ENCOUNTER_OBJECTIVE_UNREACHABLE in codes
    assert GeometryDiagnosticCode.ENCOUNTER_RANGE_INSUFFICIENT in codes
    assert GeometryDiagnosticCode.ENCOUNTER_COVER_INSUFFICIENT in codes


def test_unknown_room_fails_without_metrics(
    synthetic_package: DungeonPackage,
) -> None:
    query = EncounterFitQuery(
        schema_version="1.0.0",
        package_id=synthetic_package.id,
        room_id="room_missing",
        footprints=(
            FootprintRequirement(
                id="creature",
                footprint=CreatureFootprint(),
            ),
        ),
    )

    result = evaluate_encounter_fit(synthetic_package, query)

    assert result.fits is False
    assert result.metrics is None
    assert {item.code for item in result.diagnostics} == {
        GeometryDiagnosticCode.ENCOUNTER_ROOM_UNKNOWN
    }
