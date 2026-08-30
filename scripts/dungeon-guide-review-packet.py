#!/usr/bin/env python3
"""Generate the fixed synthetic P7-14e DM quality-review packet."""

from __future__ import annotations

import argparse
from pathlib import Path

from dm_assistant.orchestration.dungeons import DungeonGuideContentPlan
from dm_assistant.orchestration.dungeons.review import (
    write_dungeon_guide_review_packet,
)
from dm_dungeon import DungeonPlan

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAN = ROOT / "tests/evals/golden/dungeon_guide_quality_plan.json"
DEFAULT_GUIDE_CONTENT = ROOT / "tests/evals/golden/dungeon_guide_quality_content.json"
DEFAULT_OUTPUT = ROOT / "generated/dungeon-guide-review"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate DM/player maps, an exact guide, an automated rubric, and a blank "
            "human-review worksheet without PostgreSQL or a model provider."
        )
    )
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--guide-content", type=Path, default=DEFAULT_GUIDE_CONTENT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=424242)
    arguments = parser.parse_args()

    plan = DungeonPlan.model_validate_json(arguments.plan.read_bytes())
    guide_content = DungeonGuideContentPlan.model_validate_json(
        arguments.guide_content.read_bytes()
    )
    files = write_dungeon_guide_review_packet(
        plan,
        arguments.output,
        guide_content=guide_content,
        seed=arguments.seed,
    )
    print(f"Review packet: {arguments.output.resolve()}")
    for path in files:
        print(f"- {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
