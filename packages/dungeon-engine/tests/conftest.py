"""Synthetic fixtures for the pure dungeon package."""

import json
from pathlib import Path

import pytest

from dm_dungeon import (
    DungeonPackage,
    DungeonPlan,
    compile_dungeon_plan,
    read_dungeon_package,
)
from dm_dungeon.contracts.mechanics import (
    CompiledDoorMechanics,
    DungeonMechanicsPlan,
)
from dm_dungeon.layout import LayoutRequest, generate_layout

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sunken_archive.v1.json"


@pytest.fixture
def fixture_path() -> Path:
    return FIXTURE_PATH


@pytest.fixture
def synthetic_package(fixture_path: Path) -> DungeonPackage:
    return read_dungeon_package(fixture_path)


def mechanics_plan(package: DungeonPackage) -> DungeonMechanicsPlan:
    """Rebuild the test-only compiler projection pinned by the synthetic package."""
    door_mechanics = tuple(
        CompiledDoorMechanics(
            id=door.id,
            connection_id=door.connection_id,
            concealed=door.mechanics.concealed,
            gate_id=door.mechanics.gate_id,
            gate_kind=door.mechanics.gate_kind,
            trap_id=door.mechanics.trap_id,
            discovery_difficulty=door.mechanics.discovery_difficulty,
            unlock_difficulty=door.mechanics.unlock_difficulty,
            disable_difficulty=door.mechanics.disable_difficulty,
        )
        for door in package.composable_doors
    )
    return DungeonMechanicsPlan(
        policy_version="dungeon-mechanics-policy-v1",
        connection_ids=tuple(item.id for item in package.topology.connections),
        room_ids=tuple(item.id for item in package.topology.rooms),
        door_mechanics=door_mechanics,
        room_traps=(),
        room_puzzles=(),
        room_features=(),
        room_objectives=(),
        encounter_slots=(),
    )


@pytest.fixture
def layout_request() -> LayoutRequest:
    plan = DungeonPlan.model_validate_json(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "title": "Synthetic Constructive Archive",
                "premise": "A synthetic proof-carrying dungeon used only by tests.",
                "themes": ["synthetic"],
                "rooms": [
                    {
                        "ref": "entry",
                        "name": "Entry",
                        "role": "entrance",
                        "purpose": "Begin.",
                    },
                    {
                        "ref": "hall",
                        "name": "Hall",
                        "role": "exploration",
                        "purpose": "Progress.",
                    },
                    {
                        "ref": "lock",
                        "name": "Lock",
                        "role": "puzzle",
                        "purpose": "Challenge.",
                    },
                    {
                        "ref": "goal",
                        "name": "Goal",
                        "role": "objective",
                        "purpose": "Conclude.",
                    },
                    {
                        "ref": "cache",
                        "name": "Cache",
                        "role": "optional",
                        "purpose": "Reward.",
                    },
                ],
                "critical_path": ["entry", "hall", "lock", "goal"],
                "branches": [
                    {"ref": "cache_branch", "from_room": "hall", "rooms": ["cache"]}
                ],
                "loops": [
                    {
                        "ref": "cache_bypass",
                        "from_room": "cache",
                        "to_room": "goal",
                        "secret": True,
                    }
                ],
                "gates": [
                    {
                        "ref": "seal_gate",
                        "between_rooms": ["hall", "lock"],
                        "kind": "locked",
                        "dependency_kind": "key",
                        "dependency_room": "cache",
                        "dependency_name": "Synthetic Archive Key",
                    }
                ],
                "room_contents": [
                    {"room_ref": "goal", "objective": "Synthetic objective"}
                ],
            }
        )
    )
    compiled = compile_dungeon_plan(plan)
    assert compiled.accepted
    assert compiled.brief is not None
    assert compiled.topology is not None
    assert compiled.certificate is not None
    assert compiled.mechanics_plan is not None
    return LayoutRequest(
        schema_version="1.0.0",
        package_id="package_generated_archive",
        brief=compiled.brief,
        topology=compiled.topology,
        certificate=compiled.certificate,
        seed=424242,
        generator_version="orthogonal-v1",
        mechanics_plan=compiled.mechanics_plan,
        floor_bounds=compiled.floor_bounds,
    )


@pytest.fixture
def generated_package(layout_request: LayoutRequest) -> DungeonPackage:
    result = generate_layout(layout_request)
    assert result.package is not None
    return result.package
