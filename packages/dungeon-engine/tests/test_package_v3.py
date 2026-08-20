"""P7-13d exact composable-mechanics package contract tests."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from dm_dungeon import (
    DungeonPackage,
    DungeonPackageV3,
    load_dungeon_package_json,
    to_canonical_json,
)
from dm_dungeon.cli import main


def _v3_payload(package: DungeonPackage) -> dict[str, object]:
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


def test_v3_preserves_composable_door_and_endpoint_hatch_mechanics(
    synthetic_package: DungeonPackage,
) -> None:
    payload = _v3_payload(synthetic_package)
    ladder = next(
        item
        for item in synthetic_package.vertical_links
        if item.id == "connection_secret_ladder"
    )
    endpoint = ladder.endpoints[0]
    payload["vertical_endpoint_doors"] = [
        {
            "id": "v3-endpoint-hatch",
            "layer_id": "layer_dm_secrets",
            "vertical_link_id": ladder.id,
            "endpoint": "from",
            "kind": "hatch",
            "floor_id": endpoint.floor_id,
            "room_id": "room_vault",
            "position": endpoint.position.model_dump(mode="json"),
            "mechanics": {
                "concealed": True,
                "gate_id": "v3-gate-hatch",
                "gate_kind": "puzzle",
                "trap_id": "v3-trap-hatch",
                "discovery_difficulty": 16,
                "unlock_difficulty": 16,
                "disable_difficulty": 16,
            },
        }
    ]

    package = DungeonPackageV3.model_validate_json(json.dumps(payload))

    assert package.doors[1].mechanics.concealed
    assert package.doors[2].mechanics.trap_id == "hazard_needle_lock"
    assert package.doors[3].mechanics.gate_id == "gate_sanctum"
    hatch = package.vertical_endpoint_doors[0]
    assert hatch.mechanics.gate_id and hatch.mechanics.trap_id
    assert load_dungeon_package_json(to_canonical_json(package)) == package


def test_v3_rejects_vertical_hatch_at_the_wrong_directional_endpoint(
    synthetic_package: DungeonPackage,
) -> None:
    payload = _v3_payload(synthetic_package)
    ladder = next(
        item
        for item in synthetic_package.vertical_links
        if item.id == "connection_secret_ladder"
    )
    endpoint = ladder.endpoints[0]
    payload["vertical_endpoint_doors"] = [
        {
            "id": "v3-endpoint-hatch",
            "layer_id": "layer_dm_secrets",
            "vertical_link_id": ladder.id,
            "endpoint": "to",
            "kind": "hatch",
            "floor_id": endpoint.floor_id,
            "room_id": "room_vault",
            "position": endpoint.position.model_dump(mode="json"),
            "mechanics": {},
        }
    ]

    with pytest.raises(ValidationError, match="directional connection side"):
        DungeonPackageV3.model_validate_json(json.dumps(payload))


def test_cli_fails_closed_until_v3_validation_and_rendering_exist(
    synthetic_package: DungeonPackage,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # The dedicated reader/canonicalizer may inspect V3, but package operations
    # cannot accidentally omit its composable mechanics before their V3 support.
    path = tmp_path / "v3-package.json"
    package = DungeonPackageV3.model_validate_json(
        json.dumps(_v3_payload(synthetic_package))
    )
    path.write_text(to_canonical_json(package), encoding="utf-8")

    with pytest.raises(SystemExit) as exit_info:
        main(["validate", str(path)])
    assert exit_info.value.code == 2
    assert "readable but not renderable yet" in capsys.readouterr().err


def test_v3_reader_does_not_reinterpret_a_retained_package(
    synthetic_package: DungeonPackage,
) -> None:
    retained_json = to_canonical_json(synthetic_package)
    assert load_dungeon_package_json(retained_json) == synthetic_package

    v3_payload = _v3_payload(synthetic_package)
    v3_payload["doors"] = []
    with pytest.raises(ValueError, match="DungeonPackageV3 schema version"):
        DungeonPackageV3.model_validate_json(retained_json)
    # The V3 input is only accepted by its dedicated root reader.
    assert isinstance(
        load_dungeon_package_json(
            to_canonical_json(
                DungeonPackageV3.model_validate_json(json.dumps(v3_payload))
            )
        ),
        DungeonPackageV3,
    )
