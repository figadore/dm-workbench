"""Properties for certificate-driven constructive Tier A geometry."""

import json

from hypothesis import given, settings
from hypothesis import strategies as st

from dm_dungeon import (
    DungeonPlan,
    LayoutRequest,
    RenderAudience,
    SvgRenderRequest,
    compile_dungeon_plan,
    generate_layout,
    render_svg,
    validate_geometry,
)
from dm_dungeon.layout import ORTHOGONAL_LAYOUT_GENERATOR_VERSION
from dm_dungeon.validation import GeometryDiagnosticCode


def active_chain_request(room_count: int, seed: int) -> LayoutRequest:
    rooms = [
        {
            "ref": f"room_{index}",
            "name": f"Room {index}",
            "role": (
                "entrance"
                if index == 0
                else "objective"
                if index == room_count - 1
                else "exploration"
            ),
            "purpose": f"Serve synthetic progression step {index}.",
        }
        for index in range(room_count)
    ]
    payload = {
        "schema_version": "1.0.0",
        "title": "Generated Layout Property",
        "premise": "A synthetic connected dungeon with no campaign content.",
        "themes": ["synthetic"],
        "rooms": rooms,
        "critical_path": [item["ref"] for item in rooms],
        "room_contents": [
            {
                "room_ref": f"room_{room_count - 1}",
                "objective": "Synthetic Objective",
            }
        ],
    }
    plan = DungeonPlan.model_validate_json(json.dumps(payload))
    compiled = compile_dungeon_plan(plan)
    assert compiled.accepted
    assert compiled.brief is not None
    assert compiled.topology is not None
    assert compiled.mechanics_plan is not None
    assert compiled.certificate is not None
    return LayoutRequest(
        schema_version="1.0.0",
        package_id="package_active_layout_property",
        brief=compiled.brief,
        topology=compiled.topology,
        certificate=compiled.certificate,
        seed=seed,
        generator_version=ORTHOGONAL_LAYOUT_GENERATOR_VERSION,
        mechanics_plan=compiled.mechanics_plan,
        floor_bounds=compiled.floor_bounds,
    )


@settings(max_examples=30, deadline=None)
@given(
    room_count=st.integers(min_value=4, max_value=5),
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
    assert len(first.package.composable_doors) == room_count - 1
    assert validate_geometry(first.package).valid is True


@settings(max_examples=80, deadline=None)
@given(
    room_count=st.integers(min_value=4, max_value=8),
    first_branch=st.integers(min_value=0, max_value=3),
    second_branch=st.integers(min_value=0, max_value=3),
    with_loop=st.booleans(),
    secret_loop=st.booleans(),
    seed=st.integers(min_value=0, max_value=2**32 - 1),
)
def test_all_tier_a_bands_construct_valid_exact_geometry(
    room_count: int,
    first_branch: int,
    second_branch: int,
    with_loop: bool,
    secret_loop: bool,
    seed: int,
) -> None:
    available = room_count - 2
    first_branch = min(first_branch, available)
    second_branch = min(second_branch, available - first_branch)
    if first_branch == 0:
        second_branch = 0
    critical_count = room_count - first_branch - second_branch
    rooms = [
        {
            "ref": f"room_{index}",
            "name": f"Room {index}",
            "role": (
                "entrance"
                if index == 0
                else "objective"
                if index == critical_count - 1
                else "optional"
                if index >= critical_count
                else "exploration"
            ),
            "size": "small",
            "purpose": f"Serve synthetic progression step {index}.",
            "encounter": "combat" if index % 2 else None,
        }
        for index in range(room_count)
    ]
    branches: list[dict[str, object]] = []
    cursor = critical_count
    if first_branch:
        branches.append(
            {
                "ref": "upper_branch",
                "from_room": "room_1" if critical_count > 2 else "room_0",
                "rooms": [
                    f"room_{index}" for index in range(cursor, cursor + first_branch)
                ],
            }
        )
        cursor += first_branch
    if second_branch:
        branches.append(
            {
                "ref": "lower_branch",
                "from_room": f"room_{max(0, critical_count - 2)}",
                "rooms": [f"room_{index}" for index in range(cursor, room_count)],
            }
        )
    loops = []
    if with_loop:
        loops.append(
            {
                "ref": "outer_loop",
                "from_room": (f"room_{room_count - 1}" if branches else "room_0"),
                "to_room": f"room_{critical_count - 1}",
                "secret": secret_loop,
            }
        )
    payload = {
        "schema_version": "1.0.0",
        "title": "Generated Constructive Property",
        "premise": "A synthetic proof-carrying Tier A dungeon.",
        "themes": ["synthetic"],
        "rooms": rooms,
        "critical_path": [f"room_{index}" for index in range(critical_count)],
        "branches": branches,
        "loops": loops,
        "room_contents": [
            {
                "room_ref": f"room_{critical_count - 1}",
                "objective": "Synthetic Objective",
            }
        ],
    }
    plan = DungeonPlan.model_validate_json(json.dumps(payload))
    compiled = compile_dungeon_plan(plan)
    assert compiled.accepted
    assert compiled.brief is not None
    assert compiled.topology is not None
    assert compiled.certificate is not None
    assert compiled.mechanics_plan is not None
    request = LayoutRequest(
        schema_version="1.0.0",
        package_id="package_constructive_property",
        brief=compiled.brief,
        topology=compiled.topology,
        certificate=compiled.certificate,
        seed=seed,
        generator_version=ORTHOGONAL_LAYOUT_GENERATOR_VERSION,
        mechanics_plan=compiled.mechanics_plan,
        floor_bounds=compiled.floor_bounds,
    )

    result = generate_layout(request)

    assert result.success is True
    assert result.package is not None
    assert result.random_draw_count == 0
    assert validate_geometry(result.package).valid
    assert len(result.package.rooms) == room_count
    assert len(result.package.corridors) == len(compiled.topology.connections)
    assert len(result.package.passage_openings) == 2 * len(
        compiled.topology.connections
    )
    assert (
        result.package.floors[0].bounds.width_cells
        == compiled.floor_bounds[0].width_cells
    )
    assert (
        result.package.floors[0].bounds.height_cells
        == compiled.floor_bounds[0].height_cells
    )
    occupied: set[tuple[int, int]] = set()
    for corridor in result.package.corridors:
        cells: set[tuple[int, int]] = set()
        for first, second in zip(
            corridor.path.points, corridor.path.points[1:], strict=False
        ):
            if first.x == second.x:
                cells.update(
                    (first.x, y)
                    for y in range(min(first.y, second.y), max(first.y, second.y) + 1)
                )
            else:
                cells.update(
                    (x, first.y)
                    for x in range(min(first.x, second.x), max(first.x, second.x) + 1)
                )
        assert cells.isdisjoint(occupied)
        occupied.update(cells)

    player = render_svg(
        result.package,
        SvgRenderRequest(
            schema_version="1.0.0",
            package_id=result.package.id,
            floor_id=result.package.floors[0].id,
            audience=RenderAudience.PLAYER,
            pixels_per_cell=8,
        ),
    )
    assert player.success
    assert player.svg is not None
    hidden_ids = {
        item.id
        for item in (*result.package.corridors, *result.package.composable_doors)
        if item.visibility.value == "dm_only"
    }
    assert all(component_id not in player.svg for component_id in hidden_ids)


@settings(max_examples=15, deadline=None)
@given(
    room_count=st.integers(min_value=4, max_value=5),
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
