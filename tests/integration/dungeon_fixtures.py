"""Shared synthetic proof-carrying Tier A requests for root test suites."""

import json
from pathlib import Path

from dm_dungeon import DungeonPlan, LayoutRequest, compile_dungeon_plan

_REVIEW_PLAN_PATH = (
    Path(__file__).parents[1] / "evals/golden/dungeon_guide_quality_plan.json"
)


def _synthetic_plan() -> dict[str, object]:
    value = json.loads(_REVIEW_PLAN_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def synthetic_prompt_proposal() -> dict[str, object]:
    """Return a disposable structural proposal for faux-provider integration."""

    return {
        "proposal_version": "1",
        "plan": _synthetic_plan(),
    }


def synthetic_layout_request(package_id: str, *, seed: int = 424242) -> LayoutRequest:
    plan = DungeonPlan.model_validate_json(_REVIEW_PLAN_PATH.read_bytes())
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
