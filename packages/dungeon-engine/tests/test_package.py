"""Alpha V1 composable-mechanics package contract tests."""

import pytest
from pydantic import ValidationError

from dm_dungeon import (
    DoorMechanics,
    DungeonPackage,
    VerticalEndpointDoorLayout,
)
from dm_dungeon.contracts import (
    BarrierIntent,
    EndpointDoorKind,
    VerticalEndpointSide,
    Visibility,
)


def test_composable_mechanics_require_each_active_value() -> None:
    mechanics = DoorMechanics(
        concealed=True,
        gate_id="gate-hatch",
        gate_kind=BarrierIntent.LOCKED,
        trap_id="trap-hatch",
        discovery_difficulty=16,
        unlock_difficulty=16,
        disable_difficulty=16,
    )
    hatch = VerticalEndpointDoorLayout(
        id="endpoint-hatch",
        layer_id="layer-dm",
        vertical_link_id="link-stairs",
        endpoint=VerticalEndpointSide.TO,
        kind=EndpointDoorKind.HATCH,
        floor_id="floor-lower",
        room_id="room-vault",
        position={"x": 3, "y": 4},
        mechanics=mechanics,
        visibility=Visibility.DM_ONLY,
    )

    assert hatch.mechanics.gate_id == "gate-hatch"
    assert hatch.mechanics.trap_id == "trap-hatch"
    with pytest.raises(ValidationError, match="unlock difficulty"):
        DoorMechanics(gate_id="gate", gate_kind=BarrierIntent.LOCKED)


def test_root_round_trips_composable_doors(
    synthetic_package: DungeonPackage,
) -> None:
    package = DungeonPackage.model_validate_json(synthetic_package.model_dump_json())

    assert any(door.mechanics.concealed for door in package.composable_doors)
    assert any(door.mechanics.trap_id is not None for door in package.composable_doors)
    assert package.vertical_endpoint_doors == ()
