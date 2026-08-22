"""Synthetic fixtures for the pure dungeon package."""

from pathlib import Path

import pytest

from dm_dungeon import DungeonPackage, read_dungeon_package
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
def layout_request(synthetic_package: DungeonPackage) -> LayoutRequest:
    return LayoutRequest(
        schema_version="1.0.0",
        package_id="package_generated_archive",
        brief=synthetic_package.brief,
        topology=synthetic_package.topology,
        seed=424242,
        generator_version="orthogonal-v1",
        mechanics_plan=mechanics_plan(synthetic_package),
    )


@pytest.fixture
def generated_package(layout_request: LayoutRequest) -> DungeonPackage:
    result = generate_layout(layout_request)
    assert result.package is not None
    return result.package
