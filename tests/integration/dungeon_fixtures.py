"""Shared synthetic proof-carrying Tier A requests for root test suites."""

import json

from dm_dungeon import DungeonPlan, LayoutRequest, compile_dungeon_plan

_SYNTHETIC_PLAN = {
    "schema_version": "1.0.0",
    "title": "Synthetic Constructive Archive",
    "premise": "A synthetic archive used only to test deterministic preparation.",
    "themes": ["synthetic"],
    "rooms": [
        {
            "ref": "entry",
            "name": "Archive Entry",
            "role": "entrance",
            "purpose": "Establish the synthetic route.",
        },
        {
            "ref": "gallery",
            "name": "Record Gallery",
            "role": "exploration",
            "purpose": "Provide a progression junction.",
        },
        {
            "ref": "seal",
            "name": "Sealed Hall",
            "role": "puzzle",
            "purpose": "Test deterministic progression.",
        },
        {
            "ref": "vault",
            "name": "Synthetic Vault",
            "role": "objective",
            "purpose": "Hold the synthetic objective.",
        },
        {
            "ref": "cache",
            "name": "Optional Cache",
            "role": "optional",
            "purpose": "Provide an upper branch and secret bypass.",
        },
    ],
    "critical_path": ["entry", "gallery", "seal", "vault"],
    "branches": [{"ref": "cache_branch", "from_room": "gallery", "rooms": ["cache"]}],
    "loops": [
        {
            "ref": "cache_bypass",
            "from_room": "cache",
            "to_room": "vault",
            "secret": True,
        }
    ],
    "gates": [
        {
            "ref": "seal_gate",
            "between_rooms": ["gallery", "seal"],
            "kind": "locked",
            "dependency_kind": "key",
            "dependency_room": "cache",
            "dependency_name": "Synthetic Archive Key",
        }
    ],
    "room_contents": [{"room_ref": "vault", "objective": "Synthetic Objective"}],
}


def synthetic_layout_request(package_id: str, *, seed: int = 424242) -> LayoutRequest:
    plan = DungeonPlan.model_validate_json(json.dumps(_SYNTHETIC_PLAN))
    compiled = compile_dungeon_plan(plan)
    assert compiled.accepted
    assert compiled.brief is not None
    assert compiled.topology is not None
    assert compiled.certificate is not None
    assert compiled.mechanics_plan is not None
    return LayoutRequest(
        schema_version="1.0.0",
        package_id=package_id,
        brief=compiled.brief,
        topology=compiled.topology,
        certificate=compiled.certificate,
        seed=seed,
        generator_version="orthogonal-v1",
        mechanics_plan=compiled.mechanics_plan,
        floor_bounds=compiled.floor_bounds,
    )
