#!/usr/bin/env python3
"""Render the body-free fixed-fixture P7-10b Dungeon Studio evaluation report."""

import json
from pathlib import Path

fixture = Path(__file__).parents[1] / "tests/evals/golden/dungeon_studio_v1.json"
observations = json.loads(fixture.read_text())
if not isinstance(observations, list) or not observations:
    raise SystemExit("dungeon evaluation fixture must be a non-empty list")
count = len(observations)
required = (
    "first_pass_valid",
    "repair_count",
    "targeted_edit_preserved",
    "render_export_valid",
    "context_relevant",
    "dm_edited",
)
if any(any(key not in item for key in required) for item in observations if isinstance(item, dict)):
    raise SystemExit("dungeon evaluation fixture is incomplete")
report = {
    "case_count": count,
    "first_pass_valid_rate": sum(item["first_pass_valid"] for item in observations) / count,
    "mean_repair_count": sum(item["repair_count"] for item in observations) / count,
    "targeted_edit_preservation_rate": sum(item["targeted_edit_preserved"] for item in observations) / count,
    "render_export_correctness_rate": sum(item["render_export_valid"] for item in observations) / count,
    "context_relevance_rate": sum(item["context_relevant"] for item in observations) / count,
    "dm_edit_rate": sum(item["dm_edited"] for item in observations) / count,
}
print(json.dumps(report, sort_keys=True, separators=(",", ":")))
