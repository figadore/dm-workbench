"""Synthetic fixtures for the pure dungeon package."""

from pathlib import Path

import pytest

from dm_dungeon import DungeonPackage, read_dungeon_package
from dm_dungeon.layout import LayoutRequest, generate_layout

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sunken_archive.v1.json"


@pytest.fixture
def fixture_path() -> Path:
    return FIXTURE_PATH


@pytest.fixture
def synthetic_package(fixture_path: Path) -> DungeonPackage:
    return read_dungeon_package(fixture_path)


@pytest.fixture
def layout_request(synthetic_package: DungeonPackage) -> LayoutRequest:
    return LayoutRequest(
        schema_version="1.0.0",
        package_id="package_generated_archive",
        brief=synthetic_package.brief,
        topology=synthetic_package.topology,
        seed=424242,
        generator_version="orthogonal-v1",
    )


@pytest.fixture
def generated_package(layout_request: LayoutRequest) -> DungeonPackage:
    result = generate_layout(layout_request)
    assert result.package is not None
    return result.package
