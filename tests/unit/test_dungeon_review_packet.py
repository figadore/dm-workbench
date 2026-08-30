"""Provider-free fixed-prompt human DM review-packet coverage."""

import hashlib
import io
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from PIL import Image

from dm_assistant.orchestration.dungeons import (
    DungeonGuideContentPlan,
    DungeonStudioSpecification,
)
from dm_assistant.orchestration.dungeons.review import (
    write_dungeon_guide_review_packet,
)
from dm_dungeon import DungeonPlan
from dm_dungeon.export import PngExportManifest
from dm_dungeon.rendering import RenderAudience, build_map_key

_PLAN_PATH = Path(__file__).parents[1] / "evals/golden/dungeon_guide_quality_plan.json"
_CONTENT_PATH = (
    Path(__file__).parents[1] / "evals/golden/dungeon_guide_quality_content.json"
)


def test_review_packet_contains_exact_maps_guide_rubric_and_blank_worksheet(
    tmp_path: Path,
) -> None:
    plan = DungeonPlan.model_validate_json(_PLAN_PATH.read_bytes())
    guide_content = DungeonGuideContentPlan.model_validate_json(
        _CONTENT_PATH.read_bytes()
    )
    output_dir = tmp_path / "review"

    files = write_dungeon_guide_review_packet(
        plan, output_dir, guide_content=guide_content
    )

    assert {item.name for item in files} == {
        "automated-rubric.txt",
        "dm-guide.md",
        "dm-map.png",
        "dm-map.svg",
        "dm-png-manifest.json",
        "guide-content.json",
        "manifest.json",
        "plan.json",
        "player-map.png",
        "player-map.svg",
        "player-png-manifest.json",
        "review-worksheet.md",
        "specification.json",
    }
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["packet_version"] == "dungeon-guide-review-packet-v1"
    assert manifest["automated_rubric_pass"] is True
    assert manifest["human_review_required"] is True
    for name, metadata in manifest["files"].items():
        data = (output_dir / name).read_bytes()
        assert metadata == {
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }

    specification = DungeonStudioSpecification.model_validate_json(
        (output_dir / "specification.json").read_bytes()
    )
    assert specification.dm_guide is not None
    assert specification.preparation_readiness is not None
    assert specification.preparation_readiness.ready
    dm_only_ids = {
        item.id
        for components in (
            specification.package.rooms,
            specification.package.corridors,
            specification.package.composable_doors,
        )
        for item in components
        if item.visibility.value == "dm_only"
    }
    assert dm_only_ids
    dm_svg = (output_dir / "dm-map.svg").read_bytes()
    player_svg = (output_dir / "player-map.svg").read_bytes()
    for component_id in dm_only_ids:
        assert component_id.encode() in dm_svg
        assert component_id.encode() not in player_svg

    dm_root = ET.fromstring(dm_svg)
    player_root = ET.fromstring(player_svg)
    legend_labels = {
        element.attrib["data-legend-label"]
        for element in dm_root.iter()
        if "data-legend-label" in element.attrib
    }
    assert legend_labels == {
        "door",
        "encounter",
        "feature",
        "lock-secret",
        "objective",
        "room",
        "start",
        "trap",
    }
    assert not any(
        "data-legend-label" in element.attrib for element in player_root.iter()
    )
    encounter_labels = [
        element
        for element in dm_root.iter()
        if element.attrib.get("data-encounter-slot-label") == "E"
    ]
    assert len(encounter_labels) == 1
    assert encounter_labels[0].text == "E"
    assert not any(
        element.attrib.get("data-encounter-slot-label") == "E"
        for element in player_root.iter()
    )
    assert not any(
        element.attrib.get("data-kind") == "position-anchor"
        for root in (dm_root, player_root)
        for element in root.iter()
    )
    dm_start_markers = [
        element
        for element in dm_root.iter()
        if element.attrib.get("data-kind") == "dungeon-start"
    ]
    assert len(dm_start_markers) == 1
    assert dm_start_markers[0].attrib["data-anchor-kind"] == "entrance"
    assert not any(
        element.attrib.get("data-kind") == "dungeon-start"
        for element in player_root.iter()
    )
    assert not any("data-callout" in element.attrib for element in player_root.iter())
    objective_rings = {
        element.attrib["data-ring"]
        for element in dm_root.iter()
        if element.attrib.get("data-objective-callout") == "O1"
    }
    assert objective_rings == {"inner", "outer"}
    objective_id = next(
        item.id
        for item in specification.package.room_mechanic_markers
        if item.kind.value == "objective"
    )
    feature_id = next(
        item.id
        for item in specification.package.room_mechanic_markers
        if item.kind.value == "feature"
    )
    assert objective_id.encode() not in player_svg
    assert feature_id.encode() in player_svg
    assert b">F1<" not in player_svg
    assert b">O1<" not in player_svg

    map_key = build_map_key(
        specification.package,
        specification.package.floors[0].id,
        RenderAudience.DM,
        scale=70,
    )
    secret_door = next(
        entry
        for entry in map_key.entries
        if tuple(badge.token for badge in entry.badges) == ("S",)
    )
    assert secret_door.token == "D5"
    secret_badge = secret_door.badges[0]
    callout_box = (
        secret_door.label_x - secret_door.width / 2,
        secret_door.label_y - secret_door.height / 2,
        secret_door.label_x + secret_door.width / 2,
        secret_door.label_y + secret_door.height / 2,
    )
    badge_box = (
        secret_badge.label_x - secret_badge.width / 2,
        secret_badge.label_y - secret_badge.height / 2,
        secret_badge.label_x + secret_badge.width / 2,
        secret_badge.label_y + secret_badge.height / 2,
    )
    assert _boxes_are_disjoint(callout_box, badge_box)

    png_manifests = {
        audience: PngExportManifest.model_validate_json(
            (output_dir / f"{audience.value}-png-manifest.json").read_bytes()
        )
        for audience in RenderAudience
    }
    assert dm_only_ids <= set(png_manifests[RenderAudience.DM].rendered_component_ids)
    assert not dm_only_ids & set(
        png_manifests[RenderAudience.PLAYER].rendered_component_ids
    )
    assert (
        objective_id not in png_manifests[RenderAudience.PLAYER].rendered_component_ids
    )
    assert feature_id in png_manifests[RenderAudience.PLAYER].rendered_component_ids

    public_corridor = next(
        corridor
        for corridor in specification.package.corridors
        if corridor.visibility.value == "player_safe"
        and len(corridor.path.points) == 2
        and corridor.path.points[0].y == corridor.path.points[1].y
    )
    start, end = public_corridor.path.points
    scale = png_manifests[RenderAudience.PLAYER].pixels_per_cell
    left = (min(start.x, end.x) + 1) * scale
    right = max(start.x, end.x) * scale
    top = start.y * scale
    bottom = (start.y + public_corridor.width_cells) * scale
    with Image.open(io.BytesIO((output_dir / "player-map.png").read_bytes())) as image:
        grayscale = image.convert("L")
        for boundary_y in (top, bottom):
            dark_pixels = max(
                sum(grayscale.getpixel((x, row_y)) < 80 for x in range(left, right))
                for row_y in range(boundary_y - 2, boundary_y + 3)
            )
            assert dark_pixels >= (right - left) * 0.9
        interior_dark_pixels = sum(
            grayscale.getpixel((x, (top + bottom) // 2)) < 80
            for x in range(left, right)
        )
        assert interior_dark_pixels <= (right - left) * 0.1

        door = next(
            item
            for item in specification.package.composable_doors
            if item.connection_id == public_corridor.id
        )
        open_passage = next(
            item
            for item in specification.package.passage_openings
            if item.corridor_id == public_corridor.id and item.segment != door.segment
        )
        opening_x = (
            (open_passage.segment.start.x + open_passage.segment.end.x) * scale // 2
        )
        opening_y = (
            (open_passage.segment.start.y + open_passage.segment.end.y) * scale // 2
        )
        assert all(
            grayscale.getpixel((opening_x + dx, opening_y + dy)) > 245
            for dx in range(-1, 2)
            for dy in range(-1, 2)
        )

        door_x = (door.segment.start.x + door.segment.end.x) * scale // 2
        door_y = (door.segment.start.y + door.segment.end.y) * scale // 2
        if door.segment.start.x == door.segment.end.x:
            door_cross_section = [
                grayscale.getpixel((door_x + offset, door_y)) for offset in range(-5, 6)
            ]
        else:
            door_cross_section = [
                grayscale.getpixel((door_x, door_y + offset)) for offset in range(-5, 6)
            ]
        assert sum(pixel < 80 for pixel in door_cross_section) >= 6

    assert "automated checks: pass" in (output_dir / "automated-rubric.txt").read_text()
    guide_text = (output_dir / "dm-guide.md").read_text(encoding="utf-8")
    assert "#### Exploration challenge" in guide_text
    assert "Encounter slot" not in guide_text
    assert "not yet populated" not in guide_text
    assert "discovery DC 13; check method is DM-adjudicated" in guide_text
    assert "unlock DC 13" in guide_text
    assert "#### Three-Wave Brass Key — opens D1" in guide_text
    assert "#### Three-Button Vault Lock" in guide_text
    assert "rear-right floor pivot" in guide_text
    assert "unclip the wire" in guide_text
    assert "rotate the shelf 90 degrees" in guide_text
    assert "wall panel immediately left of the vault door" in guide_text
    assert "lower arm flips the full ink cup" in guide_text
    assert "locks the buttons for 10 minutes" in guide_text
    assert "No guard or creature responds" in guide_text
    assert "**Detect:** DC 13;" in guide_text
    assert "hairline seam around the pivoting threshold plate" in guide_text
    assert "**Disable:** DC 13;" in guide_text
    assert "pull out its coupling pin" in guide_text
    assert "automatically identifies the threshold plate" in guide_text
    assert "visible pull-wire" not in guide_text
    assert guide_text.count("##### Choices and consequences") == 5
    assert len(guide_text.split()) <= 900
    assert not re.search(r"(?i)\b(index|tabs?|holdings?|east-seal)\b", guide_text)
    assert "**Sensory cues:**" not in guide_text
    assert "**Purpose:**" not in guide_text
    assert "**Room mechanics:**" not in guide_text
    assert "Passage:" not in guide_text
    assert "## Map cross-reference" not in guide_text
    for ordinary_door in ("D2", "D3", "D4"):
        assert f"#### {ordinary_door}" not in guide_text
    markdown_lines = guide_text.splitlines()
    for index, line in enumerate(markdown_lines):
        if index and line.startswith(
            ("### ", "#### ", "##### ", "**Read aloud**", "> ")
        ):
            assert markdown_lines[index - 1] == ""

    room_sections = re.findall(
        r"(?ms)^### (\d+)\. ([^\n]+) \(Map ([^)]+)\)\n(.*?)(?=^### |^## Preparation blockers|\Z)",
        guide_text,
    )
    assert [(number, name, token) for number, name, token, _ in room_sections] == [
        ("1", "Archive Entry", "2"),
        ("2", "Record Gallery", "3"),
        ("3", "Flooded Cataloguing Annex", "5"),
        ("4", "Sealed Hall", "4"),
        ("5", "Synthetic Vault", "1"),
    ]
    for _, _, _, body in room_sections:
        assert body.startswith("\n**Read aloud**\n\n> ")

    sections_by_name = {name: body for _, name, _, body in room_sections}
    annex = sections_by_name["Flooded Cataloguing Annex"]
    assert "Three-Wave Brass Key" in annex
    assert "Exploration challenge" in annex
    assert "broken front-left foot" in annex
    assert "rear-right floor pivot" in annex
    assert "brass wire" in annex
    assert "two people or a lever" in annex.lower()
    assert "it was not visible from the doorway" in annex
    annex_read_aloud = annex.split("####", maxsplit=1)[0]
    assert "key" not in annex_read_aloud.lower()
    hall = sections_by_name["Sealed Hall"]
    assert "Synthetic Bell Ward" in hall
    assert "Three-Button Vault Lock" in hall
    assert "Instruction Pedestal" in hall
    assert "Press where a record ENTERS" in hall
    assert "three-step drum" in hall
    assert "wrong third press" in hall
    assert "10 minutes" in hall
    vault = sections_by_name["Synthetic Vault"]
    assert "Synthetic Objective" in vault
    vault_read_aloud = vault.split("####", maxsplit=1)[0]
    assert "latch" not in vault_read_aloud.lower()
    assert "catch" not in vault_read_aloud.lower()
    worksheet = (output_dir / "review-worksheet.md").read_text(encoding="utf-8")
    assert "[ ] Pass  [ ] Needs work" in worksheet
    assert "It does not approve preparation for" in worksheet

    with pytest.raises(FileExistsError, match="already exists"):
        write_dungeon_guide_review_packet(plan, output_dir, guide_content=guide_content)


def _boxes_are_disjoint(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> bool:
    return (
        first[2] <= second[0]
        or second[2] <= first[0]
        or first[3] <= second[1]
        or second[3] <= first[1]
    )
