"""Property tests for seeded orthogonal layout generation."""

import json
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from dm_dungeon.contracts import DungeonBrief, DungeonTopology
from dm_dungeon.layout import LayoutRequest, generate_layout
from dm_dungeon.validation import GeometryDiagnosticCode, validate_geometry


def generated_topology(room_count: int) -> DungeonTopology:
    rooms: list[dict[str, Any]] = []
    for index in range(room_count):
        role = (
            "entrance"
            if index == 0
            else "exit"
            if index == room_count - 1
            else "exploration"
        )
        rooms.append(
            {
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
        )
    payload = {
        "schema_version": "1.0.0",
        "id": "topology_layout_property",
        "visibility": "dm_only",
        "floors": [
            {
                "id": "floor_main",
                "name": "Generated Floor",
                "level_index": 0,
                "target_room_count": room_count,
                "visibility": "player_safe",
            }
        ],
        "rooms": rooms,
        "connections": [
            {
                "kind": "corridor",
                "id": f"connection_{index}_{index + 1}",
                "from_room_id": f"room_{index}",
                "to_room_id": f"room_{index + 1}",
                "minimum_width_cells": 1,
                "visibility": "player_safe",
            }
            for index in range(room_count - 1)
        ],
        "gates": [],
        "keys": [],
        "clues": [],
        "loops": [],
        "branches": [],
        "chokepoints": [],
        "secret_bypasses": [],
    }
    return DungeonTopology.model_validate_json(json.dumps(payload))


def generated_brief(room_count: int) -> DungeonBrief:
    payload = {
        "schema_version": "1.0.0",
        "id": "brief_layout_property",
        "title": "Generated Layout Property",
        "purpose": "ruin",
        "summary": "A synthetic property-test dungeon with no campaign content.",
        "visibility": "dm_only",
        "themes": ["synthetic"],
        "tones": [],
        "inhabitants": [],
        "floor_count": 1,
        "target_room_count": room_count,
        "pacing": "balanced",
        "party_scale": None,
        "constraints": [],
        "campaign_hooks": [],
        "tags": ["property-test"],
    }
    return DungeonBrief.model_validate_json(json.dumps(payload))


@settings(max_examples=30, deadline=None)
@given(
    room_count=st.integers(min_value=2, max_value=7),
    seed=st.integers(min_value=0, max_value=2**32 - 1),
)
def test_generated_chain_layouts_are_successful_and_repeatable(
    room_count: int,
    seed: int,
) -> None:
    request = LayoutRequest(
        schema_version="1.0.0",
        package_id="package_layout_property",
        brief=generated_brief(room_count),
        topology=generated_topology(room_count),
        seed=seed,
        generator_version="orthogonal-v1",
    )

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
    room_count=st.integers(min_value=2, max_value=7),
    seed=st.integers(min_value=0, max_value=2**32 - 1),
)
def test_overlapping_generated_room_mutation_is_always_rejected(
    room_count: int,
    seed: int,
) -> None:
    request = LayoutRequest(
        schema_version="1.0.0",
        package_id="package_overlap_property",
        brief=generated_brief(room_count),
        topology=generated_topology(room_count),
        seed=seed,
        generator_version="orthogonal-v1",
    )
    result = generate_layout(request)
    assert result.package is not None
    first, second, *remaining = result.package.rooms
    overlapping = second.model_copy(update={"boundary": first.boundary})
    broken = result.package.model_copy(
        update={"rooms": (first, overlapping, *remaining)}
    )

    codes = {item.code for item in validate_geometry(broken).diagnostics}

    assert GeometryDiagnosticCode.ROOM_OVERLAP in codes
