"""P7-13d active V2 composable-mechanics package contract tests."""

import json

import pytest
from pydantic import ValidationError

from dm_dungeon import (
    ComposableDoorMechanicsV2,
    DungeonPackage,
    DungeonPackageV2,
    VerticalEndpointDoorLayoutV2,
)
from dm_dungeon.contracts import (
    BarrierIntent,
    EndpointDoorKind,
    VerticalEndpointSide,
    Visibility,
)


def _composable_payload(package: DungeonPackage) -> dict[str, object]:
    payload = package.model_dump(mode="json", round_trip=True)
    payload["schema_version"] = "1.3.0"
    doors: list[dict[str, object]] = []
    for door in package.doors:
        mechanics: dict[str, object] = {}
        if door.door_type.value == "secret":
            mechanics.update({"concealed": True, "discovery_difficulty": 13})
        if door.gate_id is not None:
            mechanics.update(
                {
                    "gate_id": door.gate_id,
                    "gate_kind": "locked",
                    "unlock_difficulty": 13,
                }
            )
        if door.hazard_id is not None:
            mechanics.update({"trap_id": door.hazard_id, "disable_difficulty": 13})
        doors.append(
            {
                "id": door.id,
                "layer_id": door.layer_id,
                "floor_id": door.floor_id,
                "segment": door.segment.model_dump(mode="json"),
                "connects_room_ids": door.connects_room_ids,
                "from_hidden": door.from_hidden,
                "to_hidden": door.to_hidden,
                "mechanics": mechanics,
                "visibility": door.visibility.value,
            }
        )
    payload["doors"] = doors
    payload["vertical_endpoint_doors"] = []
    return payload


def test_v2_composable_mechanics_require_each_active_value() -> None:
    mechanics = ComposableDoorMechanicsV2(
        concealed=True,
        gate_id="gate-hatch",
        gate_kind=BarrierIntent.LOCKED,
        trap_id="trap-hatch",
        discovery_difficulty=16,
        unlock_difficulty=16,
        disable_difficulty=16,
    )
    hatch = VerticalEndpointDoorLayoutV2(
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
        ComposableDoorMechanicsV2(gate_id="gate", gate_kind=BarrierIntent.LOCKED)


def test_v2_root_retains_composable_doors(
    synthetic_package: DungeonPackage,
) -> None:
    payload = _composable_payload(synthetic_package)
    payload["schema_version"] = "1.3.0"
    composable_doors = payload.pop("doors")
    assert isinstance(composable_doors, list)
    for door in composable_doors:
        assert isinstance(door, dict)
        door["connection_id"] = door["id"]
    payload["composable_doors"] = composable_doors
    payload["doors"] = []
    payload["corridors"] = []
    package = DungeonPackageV2.model_validate_json(json.dumps(payload))

    assert package.composable_doors[1].mechanics.concealed
    assert package.composable_doors[2].mechanics.trap_id == "hazard_needle_lock"
    assert package.vertical_endpoint_doors == ()
