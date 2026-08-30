"""Provider-free construction of a disposable human DM quality-review packet."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from dm_assistant.orchestration.dungeons.contracts import (
    DungeonGuideContentPlan,
    DungeonStudioSpecification,
)
from dm_assistant.orchestration.dungeons.evals import (
    evaluate_dungeon_guide_quality,
    render_dungeon_guide_quality_report,
)
from dm_assistant.orchestration.dungeons.service import (
    build_dungeon_dm_guide,
    build_dungeon_preparation_readiness,
    render_dungeon_dm_guide_text,
)
from dm_dungeon import (
    DungeonPlan,
    LayoutRequest,
    PngExportRequest,
    RenderAudience,
    SvgRenderRequest,
    SvgThemeName,
    compile_dungeon_plan,
    export_png,
    generate_layout,
    render_svg,
    to_canonical_json,
    validate_geometry,
    validate_topology,
)
from dm_dungeon.layout import ORTHOGONAL_LAYOUT_GENERATOR_VERSION

_REVIEW_PACKET_VERSION = "dungeon-guide-review-packet-v1"


def write_dungeon_guide_review_packet(
    plan: DungeonPlan,
    output_dir: Path,
    *,
    guide_content: DungeonGuideContentPlan | None = None,
    seed: int = 424242,
) -> tuple[Path, ...]:
    """Write exact maps, guide, rubric, and a blank human worksheet atomically.

    This path never contacts a provider, persists preparation state, approves an
    artifact, or writes campaign canon. The destination must not already exist.
    """

    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"review packet destination already exists: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)

    compiled = compile_dungeon_plan(plan)
    if not (
        compiled.accepted
        and compiled.output_hash is not None
        and compiled.brief is not None
        and compiled.topology is not None
        and compiled.certificate is not None
        and compiled.mechanics_plan is not None
    ):
        codes = ", ".join(item.code for item in compiled.diagnostics) or "unknown"
        raise ValueError(f"review plan did not compile: {codes}")

    request = LayoutRequest(
        schema_version="1.0.0",
        package_id=f"review_{compiled.output_hash[:24]}",
        brief=compiled.brief,
        topology=compiled.topology,
        certificate=compiled.certificate,
        seed=seed,
        generator_version=ORTHOGONAL_LAYOUT_GENERATOR_VERSION,
        mechanics_plan=compiled.mechanics_plan,
        floor_bounds=compiled.floor_bounds,
    )
    layout = generate_layout(request)
    if not layout.success or layout.package is None:
        codes = ", ".join(item.code.value for item in layout.diagnostics) or "unknown"
        raise RuntimeError(f"review layout failed: {codes}")
    package = layout.package
    if len(package.floors) != 1:
        raise ValueError("the V1 DM quality packet requires exactly one Tier A floor")
    if (
        not validate_topology(package.topology).valid
        or not validate_geometry(package).valid
    ):
        raise RuntimeError("review package failed independent validation")

    guide = build_dungeon_dm_guide(request, package, plan, guide_content)
    readiness = build_dungeon_preparation_readiness(guide)
    specification = DungeonStudioSpecification(
        schema_version="1.0.0",
        layout_request=request,
        package=package,
        dm_guide=guide,
        preparation_readiness=readiness,
    )
    quality = evaluate_dungeon_guide_quality(specification)

    staging_dir = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}-", dir=output_dir.parent)
    )
    try:
        files: dict[str, bytes] = {
            "dm-guide.md": render_dungeon_dm_guide_text(guide).encode("utf-8"),
            "automated-rubric.txt": render_dungeon_guide_quality_report(quality).encode(
                "utf-8"
            ),
            "review-worksheet.md": _review_worksheet(plan.title).encode("utf-8"),
            "plan.json": to_canonical_json(plan).encode("utf-8"),
            "specification.json": specification.model_dump_json(
                indent=2, by_alias=True
            ).encode("utf-8"),
        }
        if guide_content is not None:
            files["guide-content.json"] = (
                json.dumps(
                    guide_content.model_dump(mode="json"),
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            ).encode("utf-8")

        floor = package.floors[0]
        for audience in RenderAudience:
            prefix = audience.value
            svg = render_svg(
                package,
                SvgRenderRequest(
                    schema_version="1.0.0",
                    package_id=package.id,
                    floor_id=floor.id,
                    audience=audience,
                    pixels_per_cell=64,
                    show_grid=True,
                    show_labels=True,
                    show_markers=True,
                    theme=SvgThemeName.LOW_INK,
                ),
            )
            if not svg.success or svg.svg is None:
                raise RuntimeError(f"{prefix} review SVG rendering failed")
            files[f"{prefix}-map.svg"] = svg.svg.encode("utf-8")

            png = export_png(
                package,
                PngExportRequest(
                    schema_version="1.0.0",
                    package_id=package.id,
                    floor_id=floor.id,
                    audience=audience,
                    pixels_per_cell=70,
                    dpi=140,
                    include_grid=True,
                    show_labels=True,
                    show_markers=True,
                    theme=SvgThemeName.LOW_INK,
                    maximum_ink_coverage_basis_points=5000,
                ),
            )
            if (
                not png.result.success
                or png.data is None
                or png.result.manifest is None
            ):
                raise RuntimeError(f"{prefix} review PNG rendering failed")
            files[f"{prefix}-map.png"] = png.data
            files[f"{prefix}-png-manifest.json"] = to_canonical_json(
                png.result.manifest
            ).encode("utf-8")

        for name, data in files.items():
            (staging_dir / name).write_bytes(data)
        manifest = {
            "packet_version": _REVIEW_PACKET_VERSION,
            "title": plan.title,
            "seed": seed,
            "plan_hash": compiled.output_hash,
            "automated_rubric_pass": quality.automated_pass,
            "human_review_required": quality.human_review_required,
            "files": {
                name: {
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
                for name, data in sorted(files.items())
            },
        }
        (staging_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        staging_dir.rename(output_dir)
    except BaseException:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise
    return tuple(sorted(output_dir.iterdir()))


def _review_worksheet(title: str) -> str:
    return f"""# DM quality review — {title}

This worksheet records human quality evidence only. It does not approve preparation for
play and does not make any dungeon event or detail campaign canon.

Open `dm-map.png`, `player-map.png`, and `dm-guide.md` together. Check that the player
map does not reveal the secret route, trap, or other DM-only details.

For each dimension, select one decision, enter a 1–5 rating, and record concrete findings.

## Progression

Consider the entrance-to-objective arc, whether each mandatory room advances play, and
whether the optional branch and bypass have a clear purpose.

- Decision: [ ] Pass  [ ] Needs work
- Rating (1–5):
- Findings:
- Suggested correction:

## Variety

Consider room identity, pacing, encounter/exploration modes, trap, feature, gate, and
secret-route use. Distinct labels alone do not count as meaningful variety.

- Decision: [ ] Pass  [ ] Needs work
- Rating (1–5):
- Findings:
- Suggested correction:

## Clue logic

Confirm that the key or clue can be found before its barrier, that the guide explains
what it opens, and that discovering the secret route is understandable rather than a
required unsupported guess.

- Decision: [ ] Pass  [ ] Needs work
- Rating (1–5):
- Findings:
- Suggested correction:

## Prep usefulness

Decide whether a DM could run every room without inventing missing triggers, effects,
objectives, map references, or progression details at the table.

- Decision: [ ] Pass  [ ] Needs work
- Rating (1–5):
- Findings:
- Suggested correction:

## Overall review

- Reviewer:
- Review date:
- Overall: [ ] Meets the quality gate  [ ] Revise and review again
- Highest-priority change:
- Additional notes:
"""
