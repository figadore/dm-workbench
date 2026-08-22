"""Property tests for the active compact-design-to-layout pipeline."""

import json

from hypothesis import given, settings
from hypothesis import strategies as st

from dm_dungeon import (
    DungeonDesignSpec,
    LayoutRequest,
    compile_dungeon_design,
    generate_layout,
    validate_geometry,
)
from dm_dungeon.layout import ORTHOGONAL_LAYOUT_GENERATOR_VERSION
from dm_dungeon.validation import GeometryDiagnosticCode


def active_chain_request(room_count: int, seed: int) -> LayoutRequest:
    """Compile one connected synthetic chain through the active alpha path."""
    rooms = [
        {
            "local_ref": f"room_{index}",
            "name": f"Room {index}",
            "role": (
                "entrance"
                if index == 0
                else "objective"
                if index == room_count - 1
                else "exploration"
            ),
        }
        for index in range(room_count)
    ]
    payload = {
        "schema_version": "1.0.0",
        "title": "Generated Layout Property",
        "premise": "A synthetic connected dungeon with no campaign content.",
        "themes": ["synthetic"],
        "floors": [
            {
                "local_ref": "main",
                "name": "Generated Floor",
                "floor_scale": "small",
                "rooms": rooms,
            }
        ],
        "connections": [
            {
                "local_ref": f"connection_{index}_{index + 1}",
                "from_ref": f"room_{index}",
                "to_ref": f"room_{index + 1}",
                "passage": "passage",
            }
            for index in range(room_count - 1)
        ],
        "objectives": [
            {
                "room_ref": f"room_{room_count - 1}",
                "kind": "final_objective",
                "name": "Synthetic Objective",
            }
        ],
    }
    design = DungeonDesignSpec.model_validate_json(json.dumps(payload))
    compiled = compile_dungeon_design(design)
    assert compiled.accepted
    assert compiled.brief is not None
    assert compiled.topology is not None
    assert compiled.mechanics_plan is not None
    return LayoutRequest(
        schema_version="1.0.0",
        package_id="package_active_layout_property",
        brief=compiled.brief,
        topology=compiled.topology,
        seed=seed,
        generator_version=ORTHOGONAL_LAYOUT_GENERATOR_VERSION,
        mechanics_plan=compiled.mechanics_plan,
        floor_bounds=compiled.floor_bounds,
    )


@settings(max_examples=40, deadline=None)
@given(
    room_count=st.integers(min_value=2, max_value=5),
    seed=st.integers(min_value=0, max_value=2**32 - 1),
)
def test_active_small_chain_layouts_are_successful_and_repeatable(
    room_count: int,
    seed: int,
) -> None:
    request = active_chain_request(room_count, seed)

    first = generate_layout(request)
    second = generate_layout(request)

    assert first.success is True
    assert first.package is not None
    assert first == second
    assert len(first.package.rooms) == room_count
    assert len(first.package.corridors) == room_count - 1
    assert validate_geometry(first.package).valid is True


@settings(max_examples=20, deadline=None)
@given(
    room_count=st.integers(min_value=2, max_value=5),
    seed=st.integers(min_value=0, max_value=2**32 - 1),
)
def test_overlapping_active_room_mutation_is_always_rejected(
    room_count: int,
    seed: int,
) -> None:
    result = generate_layout(active_chain_request(room_count, seed))
    assert result.package is not None
    first, second, *remaining = result.package.rooms
    overlapping = second.model_copy(update={"boundary": first.boundary})
    broken = result.package.model_copy(
        update={"rooms": (first, overlapping, *remaining)}
    )

    codes = {item.code for item in validate_geometry(broken).diagnostics}

    assert GeometryDiagnosticCode.ROOM_OVERLAP in codes
