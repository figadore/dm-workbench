"""Property-based tests over generated synthetic topology graphs."""

import json
from collections.abc import Sequence
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from dm_dungeon import DungeonPlan, compile_dungeon_plan, validate_topology_certificate
from dm_dungeon.contracts import DungeonTopology
from dm_dungeon.validation import TopologyDiagnosticCode, validate_topology


def room_payload(index: int, count: int) -> dict[str, Any]:
    if index == 0:
        role = "entrance"
    elif index == count - 1:
        role = "exit"
    else:
        role = "exploration"
    return {
        "id": f"room_{index}",
        "floor_id": "floor_main",
        "role": role,
        "required": True,
        "size": {
            "minimum_width_cells": 3,
            "maximum_width_cells": 5,
            "minimum_height_cells": 3,
            "maximum_height_cells": 5,
            "minimum_area_cells": 9,
            "maximum_area_cells": 25,
        },
        "capacity": {
            "minimum_occupants": 0,
            "comfortable_occupants": 4,
            "maximum_occupants": 8,
        },
        "tags": [],
        "visibility": "player_safe",
    }


def connection_payload(first: int, second: int) -> dict[str, Any]:
    low, high = sorted((first, second))
    return {
        "kind": "corridor",
        "id": f"connection_{low}_{high}",
        "from_room_id": f"room_{low}",
        "to_room_id": f"room_{high}",
        "minimum_width_cells": 1,
        "visibility": "player_safe",
    }


def topology_payload(
    room_count: int,
    edges: Sequence[tuple[int, int]],
) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "id": "topology_generated",
        "visibility": "dm_only",
        "floors": [
            {
                "id": "floor_main",
                "name": "Synthetic Floor",
                "level_index": 0,
                "target_room_count": room_count,
                "visibility": "player_safe",
            }
        ],
        "rooms": [room_payload(index, room_count) for index in range(room_count)],
        "connections": [connection_payload(*edge) for edge in edges],
        "gates": [],
        "keys": [],
        "clues": [],
        "loops": [],
        "branches": [],
        "chokepoints": [],
        "secret_bypasses": [],
    }


def parse_topology(payload: dict[str, Any]) -> DungeonTopology:
    return DungeonTopology.model_validate_json(json.dumps(payload))


@st.composite
def connected_topologies(draw: st.DrawFn) -> DungeonTopology:
    room_count = draw(st.integers(min_value=2, max_value=16))
    chain_edges = {(index, index + 1) for index in range(room_count - 1)}
    possible_extra_edges = [
        (first, second)
        for first in range(room_count)
        for second in range(first + 2, room_count)
    ]
    if possible_extra_edges:
        extra_edges = draw(
            st.sets(
                st.sampled_from(possible_extra_edges),
                max_size=min(12, len(possible_extra_edges)),
            )
        )
    else:
        extra_edges = set()
    return parse_topology(
        topology_payload(room_count, sorted(chain_edges | extra_edges))
    )


@st.composite
def disconnected_chain_topologies(draw: st.DrawFn) -> DungeonTopology:
    room_count = draw(st.integers(min_value=3, max_value=16))
    removed_index = draw(st.integers(min_value=0, max_value=room_count - 2))
    edges = [
        (index, index + 1) for index in range(room_count - 1) if index != removed_index
    ]
    return parse_topology(topology_payload(room_count, edges))


@settings(max_examples=60, deadline=None)
@given(connected_topologies())
def test_generated_connected_graphs_reach_every_required_room(
    topology: DungeonTopology,
) -> None:
    report = validate_topology(topology)

    assert report.valid is True
    assert report.diagnostics == ()


@settings(max_examples=40, deadline=None)
@given(disconnected_chain_topologies())
def test_removing_any_chain_edge_reports_unreachable_required_rooms(
    topology: DungeonTopology,
) -> None:
    codes = {item.code for item in validate_topology(topology).diagnostics}

    assert TopologyDiagnosticCode.REQUIRED_ROOM_UNREACHABLE_FROM_ENTRANCE in codes
    assert TopologyDiagnosticCode.REQUIRED_ROOM_UNREACHABLE_FROM_EXIT in codes


@settings(max_examples=60, deadline=None)
@given(
    room_count=st.integers(min_value=4, max_value=8),
    branch_length=st.integers(min_value=0, max_value=2),
    secret_loop=st.booleans(),
)
def test_tier_a_compiler_carries_recomputable_graph_proofs(
    room_count: int,
    branch_length: int,
    secret_loop: bool,
) -> None:
    branch_length = min(branch_length, room_count - 3)
    critical_count = room_count - branch_length
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
            "purpose": f"Exercise synthetic progression step {index}.",
        }
        for index in range(room_count)
    ]
    critical = [f"room_{index}" for index in range(critical_count)]
    branches = (
        [
            {
                "ref": "side_branch",
                "from_room": "room_1",
                "rooms": [
                    f"room_{index}" for index in range(critical_count, room_count)
                ],
            }
        ]
        if branch_length
        else []
    )
    loop_from = f"room_{room_count - 1}" if branch_length else "room_0"
    loop_to = f"room_{critical_count - 1}"
    loops = (
        [
            {
                "ref": "single_loop",
                "from_room": loop_from,
                "to_room": loop_to,
                "secret": secret_loop,
            }
        ]
        if loop_from not in {f"room_{critical_count - 2}", loop_to}
        else []
    )
    plan = DungeonPlan.model_validate_json(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "title": "Generated Certificate Property",
                "premise": "A synthetic proof-carrying Tier A dungeon.",
                "themes": ["synthetic"],
                "rooms": rooms,
                "critical_path": critical,
                "branches": branches,
                "loops": loops,
                "room_contents": [
                    {
                        "room_ref": f"room_{critical_count - 1}",
                        "objective": "Synthetic Objective",
                    }
                ],
            }
        )
    )

    compiled = compile_dungeon_plan(plan)

    assert compiled.accepted
    assert compiled.topology is not None
    assert compiled.mechanics_plan is not None
    assert compiled.certificate is not None
    assert validate_topology(compiled.topology).valid
    assert validate_topology_certificate(
        plan, compiled.topology, compiled.mechanics_plan, compiled.certificate
    ).valid
    assert compiled.certificate.component_count == 1
    assert compiled.certificate.cycle_rank == len(loops)
    assert len(compiled.certificate.branches) == len(branches)
    assert all(
        demand.degree == demand.required_ports
        for demand in compiled.certificate.room_demands
    )
