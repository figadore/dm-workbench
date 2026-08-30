"""Synthetic, provider-free evaluation for compact alpha V1 dungeon intent.

This deliberately evaluates model-shaped submissions without starting preparation
runs or calling a provider.  Live comparisons are an explicit operator action,
not test-suite behavior.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from dm_assistant.orchestration.dungeons.contracts import (
    DungeonGenerationProposal,
    DungeonStudioSpecification,
)
from dm_dungeon import (
    DungeonPlanCompileResult,
    LayoutRequest,
    RenderAudience,
    SvgRenderRequest,
    compile_dungeon_plan,
    generate_layout,
    render_svg,
    validate_geometry,
    validate_topology,
)
from dm_dungeon.layout import ORTHOGONAL_LAYOUT_GENERATOR_VERSION


class _EvalModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


DUNGEON_INTENT_EVAL_POLICY = "dungeon-intent-eval"
"""Explicit non-default policy name for isolated model comparison evidence."""


class DungeonIntentEvalCase(_EvalModel):
    """One synthetic model submission and, optionally, its bounded repair."""

    case_id: str = Field(pattern=r"^[a-z0-9_]+$")
    prompt: str = Field(min_length=1, max_length=4_000)
    proposal: DungeonGenerationProposal
    repair_proposal: DungeonGenerationProposal | None = None
    expected_first_pass: Literal["accepted", "rejected", "abstained"]
    expected_semantics: tuple[str, ...] = ()


class DungeonIntentEvalResult(_EvalModel):
    case_id: str
    # Fixture parsing proves the tool payload/schema contract; `first_pass`
    # separately records compiler/preflight acceptance.
    first_pass_schema_valid: bool
    first_pass: Literal["accepted", "rejected", "abstained"]
    expected_first_pass_matches: bool
    requested_semantics_preserved: bool
    accepted_after_repair: bool
    deterministic_replay: bool
    package_valid: bool
    player_secret_leak: bool
    diagnostics: tuple[str, ...]


class DungeonIntentEvalSummary(_EvalModel):
    case_count: int
    first_pass_schema_valid_rate: float
    first_pass_compile_valid_rate: float
    accepted_after_one_repair_rate: float
    semantics_preserved_rate: float
    deterministic_replay_rate: float
    player_secret_leak_count: int
    expected_outcome_match: bool
    passes_synthetic_thresholds: bool


DungeonGuideQualityDimension = Literal[
    "progression",
    "variety",
    "clue_logic",
    "prep_usefulness",
]


class DungeonGuideQualityCheck(_EvalModel):
    """One objective check in the fixed-prompt DM-review rubric."""

    dimension: DungeonGuideQualityDimension
    passed: bool
    diagnostics: tuple[str, ...] = ()


class DungeonGuideQualityResult(_EvalModel):
    """Automated evidence that still requires a DM's qualitative review."""

    rubric_version: Literal["dungeon-guide-quality-rubric-v1"]
    checks: tuple[DungeonGuideQualityCheck, ...] = Field(min_length=4, max_length=4)
    automated_pass: bool
    human_review_required: Literal[True] = True


def evaluate_dungeon_guide_quality(
    specification: DungeonStudioSpecification,
) -> DungeonGuideQualityResult:
    """Score a fixed prompted draft without pretending to replace DM judgment."""

    guide = specification.dm_guide
    if guide is None:
        dimensions: tuple[DungeonGuideQualityDimension, ...] = (
            "progression",
            "variety",
            "clue_logic",
            "prep_usefulness",
        )
        checks = tuple(
            DungeonGuideQualityCheck(
                dimension=dimension,
                passed=False,
                diagnostics=("guide_quality.guide_missing",),
            )
            for dimension in dimensions
        )
        return DungeonGuideQualityResult(
            rubric_version="dungeon-guide-quality-rubric-v1",
            checks=checks,
            automated_pass=False,
        )

    certificate = specification.layout_request.certificate
    guide_rooms = {item.room_id: item for item in guide.rooms}
    guide_connections = {item.connection_id: item for item in guide.connections}

    progression: list[str] = []
    if [item.presentation_number for item in guide.rooms] != list(
        range(1, len(guide.rooms) + 1)
    ):
        progression.append("guide_quality.progression.presentation_order_invalid")
    critical_room_ids = certificate.critical_path.room_ids
    if not set(critical_room_ids) <= set(guide_rooms):
        progression.append("guide_quality.progression.room_missing")
    if not set(certificate.critical_path.connection_ids) <= set(guide_connections):
        progression.append("guide_quality.progression.connection_missing")
    if critical_room_ids and set(critical_room_ids) <= set(guide_rooms):
        if (
            guide_rooms[critical_room_ids[0]].role.value != "entrance"
            or guide_rooms[critical_room_ids[-1]].role.value != "objective"
        ):
            progression.append("guide_quality.progression.endpoints_invalid")
        if any(
            _unknown_quality_text(guide_rooms[room_id].preparation_note)
            for room_id in critical_room_ids
        ):
            progression.append("guide_quality.progression.purpose_unknown")

    variety: list[str] = []
    role_count = len({item.role for item in guide.rooms})
    if role_count < 3:
        variety.append("guide_quality.variety.room_roles_narrow")
    content_modes: set[str] = set()
    if any(item.encounter_slot is not None for item in guide.rooms):
        content_modes.add("encounter")
    if any(item.role.value == "optional" for item in guide.rooms):
        content_modes.add("optional")
    if guide.traps:
        content_modes.add("trap")
    if guide.features:
        content_modes.add("feature")
    if guide.objectives:
        content_modes.add("objective")
    if any(item.gate_id is not None for item in guide.connections):
        content_modes.add("gate")
    if any(item.concealed for item in guide.connections):
        content_modes.add("secret")
    if len(content_modes) < 3:
        variety.append("guide_quality.variety.content_modes_narrow")
    distinct_purposes = {
        item.preparation_note.strip().casefold()
        for item in guide.rooms
        if not _unknown_quality_text(item.preparation_note)
        and item.preparation_note is not None
    }
    if len(distinct_purposes) < min(3, len(guide.rooms)):
        variety.append("guide_quality.variety.room_purposes_repetitive")

    clue_logic: list[str] = []
    gate_connections = {
        item.gate_id: item for item in guide.connections if item.gate_id is not None
    }
    dependencies = {item.target_gate_id: item for item in guide.dependencies}
    witnesses = {item.gate_id: item for item in certificate.gates}
    if not witnesses:
        clue_logic.append("guide_quality.clue_logic.not_exercised")
    if set(gate_connections) != set(witnesses):
        clue_logic.append("guide_quality.clue_logic.gate_projection_mismatch")
    if set(dependencies) != set(witnesses):
        clue_logic.append("guide_quality.clue_logic.dependency_missing")
    for gate_id, witness in witnesses.items():
        dependency = dependencies.get(gate_id)
        if dependency is None:
            continue
        if (
            dependency.dependency_id != witness.dependency_id
            or dependency.room_id != witness.dependency_room_id
        ):
            clue_logic.append("guide_quality.clue_logic.dependency_mismatch")
        if dependency.room_id not in witness.reachable_before_gate_room_ids:
            clue_logic.append("guide_quality.clue_logic.dependency_unreachable")
        if (
            dependency.room_map_reference.component_id != dependency.room_id
            or dependency.room_map_reference.component_id not in guide_rooms
        ):
            clue_logic.append("guide_quality.clue_logic.map_reference_invalid")

    prep: list[str] = []
    readiness = specification.preparation_readiness
    if readiness is None or not readiness.ready:
        prep.append("guide_quality.prep.readiness_blocked")
    if len(guide.objectives) != 1:
        prep.append("guide_quality.prep.final_objective_missing")
    if any(_unknown_quality_text(item.preparation_note) for item in guide.rooms):
        prep.append("guide_quality.prep.room_note_unknown")
    if any(
        _unknown_quality_text(item.read_aloud) or len(item.sensory_details) < 2
        for item in guide.rooms
    ):
        prep.append("guide_quality.prep.room_narrative_missing")
    if any(item.map_reference is None for item in guide.connections):
        prep.append("guide_quality.prep.connection_reference_missing")
    if any(
        _unknown_quality_text(item.trigger) or _unknown_quality_text(item.effect)
        for item in guide.traps
    ):
        prep.append("guide_quality.prep.trap_incomplete")
    if any(
        issue.code == "guide_content.target_invalid" for issue in guide.content_issues
    ):
        prep.append("guide_quality.prep.runnable_content_invalid")
    if any(
        room.encounter_slot is not None and room.encounter_content is None
        for room in guide.rooms
    ):
        prep.append("guide_quality.prep.encounter_content_missing")
    if any(
        dependency.discovery is None or dependency.content is None
        for dependency in guide.dependencies
    ):
        prep.append("guide_quality.prep.dependency_content_missing")
    puzzle_room_ids = {
        room.room_id for room in guide.rooms if room.role.value == "puzzle"
    }
    if puzzle_room_ids != {puzzle.room_id for puzzle in guide.puzzles}:
        prep.append("guide_quality.prep.puzzle_content_missing")
    if any(feature.content is None for feature in guide.features):
        prep.append("guide_quality.prep.feature_content_missing")
    if any(objective.content is None for objective in guide.objectives):
        prep.append("guide_quality.prep.objective_content_missing")

    diagnostic_sets: tuple[tuple[DungeonGuideQualityDimension, list[str]], ...] = (
        ("progression", progression),
        ("variety", variety),
        ("clue_logic", clue_logic),
        ("prep_usefulness", prep),
    )
    checks = tuple(
        DungeonGuideQualityCheck(
            dimension=dimension,
            passed=not diagnostics,
            diagnostics=tuple(sorted(set(diagnostics))),
        )
        for dimension, diagnostics in diagnostic_sets
    )
    return DungeonGuideQualityResult(
        rubric_version="dungeon-guide-quality-rubric-v1",
        checks=checks,
        automated_pass=all(item.passed for item in checks),
    )


def render_dungeon_guide_quality_report(result: DungeonGuideQualityResult) -> str:
    """Render body-free automated evidence and an explicit human-review warning."""

    lines = [
        f"Dungeon guide quality rubric {result.rubric_version}",
        *(
            f"{item.dimension}: {'pass' if item.passed else 'fail'}"
            for item in result.checks
        ),
        f"automated checks: {'pass' if result.automated_pass else 'fail'}",
        "human DM review: required",
    ]
    return "\n".join(lines)


def _unknown_quality_text(value: str | None) -> bool:
    if value is None:
        return True
    return value.strip().casefold() in {
        "unknown",
        "unspecified",
        "not specified",
        "tbd",
    }


def evaluate_dungeon_intent_cases(
    cases: tuple[DungeonIntentEvalCase, ...],
) -> tuple[DungeonIntentEvalResult, ...]:
    """Run only pure compiler/layout validation against frozen synthetic inputs."""
    return tuple(
        _evaluate_case(case) for case in sorted(cases, key=lambda case: case.case_id)
    )


def summarize_dungeon_intent_evals(
    results: tuple[DungeonIntentEvalResult, ...],
) -> DungeonIntentEvalSummary:
    """Apply the documented objective gates; no live/provider metric is invented."""
    if not results:
        raise ValueError("at least one dungeon eval result is required")
    count = len(results)
    schema_rate = sum(item.first_pass_schema_valid for item in results) / count
    compile_rate = sum(item.first_pass == "accepted" for item in results) / count
    non_abstentions = [item for item in results if item.first_pass != "abstained"]
    repaired_rate = (
        sum(item.accepted_after_repair for item in non_abstentions)
        / len(non_abstentions)
        if non_abstentions
        else 0.0
    )
    semantics_rate = sum(item.requested_semantics_preserved for item in results) / count
    replay_rate = sum(item.deterministic_replay for item in results) / count
    leaks = sum(item.player_secret_leak for item in results)
    outcomes_match = all(item.expected_first_pass_matches for item in results)
    return DungeonIntentEvalSummary(
        case_count=count,
        first_pass_schema_valid_rate=schema_rate,
        first_pass_compile_valid_rate=compile_rate,
        accepted_after_one_repair_rate=repaired_rate,
        semantics_preserved_rate=semantics_rate,
        deterministic_replay_rate=replay_rate,
        player_secret_leak_count=leaks,
        expected_outcome_match=outcomes_match,
        passes_synthetic_thresholds=(
            schema_rate >= 0.90
            and repaired_rate >= 0.95
            and semantics_rate == 1.0
            and replay_rate == 1.0
            and leaks == 0
            and outcomes_match
        ),
    )


def render_dungeon_intent_eval_report(
    summary: DungeonIntentEvalSummary,
) -> str:
    """Produce a stable body-free report suitable for review or CI artifacts."""
    return "\n".join(
        (
            "Dungeon intent V1 synthetic evaluation",
            f"cases: {summary.case_count}",
            f"first-pass schema-valid rate: {summary.first_pass_schema_valid_rate:.0%}",
            f"first-pass compile-valid rate: {summary.first_pass_compile_valid_rate:.0%}",
            f"accepted after one repair rate: {summary.accepted_after_one_repair_rate:.0%}",
            f"requested-semantics preservation rate: {summary.semantics_preserved_rate:.0%}",
            f"deterministic replay rate: {summary.deterministic_replay_rate:.0%}",
            f"player-secret leaks: {summary.player_secret_leak_count}",
            "passes synthetic thresholds: "
            f"{'yes' if summary.passes_synthetic_thresholds else 'no'}",
        )
    )


def _evaluate_case(case: DungeonIntentEvalCase) -> DungeonIntentEvalResult:
    first_pass = _proposal_status(case.proposal)
    proposal = case.proposal
    if first_pass == "rejected" and case.repair_proposal is not None:
        proposal = case.repair_proposal
    if proposal.abstention is not None:
        return DungeonIntentEvalResult(
            case_id=case.case_id,
            first_pass_schema_valid=True,
            first_pass="abstained",
            expected_first_pass_matches=case.expected_first_pass == "abstained",
            requested_semantics_preserved="abstention" in case.expected_semantics,
            accepted_after_repair=False,
            deterministic_replay=True,
            package_valid=False,
            player_secret_leak=False,
            diagnostics=("proposal.abstained",),
        )
    assert proposal.plan is not None
    compiled = compile_dungeon_plan(proposal.plan)
    if not compiled.accepted:
        return DungeonIntentEvalResult(
            case_id=case.case_id,
            first_pass_schema_valid=True,
            first_pass=first_pass,
            expected_first_pass_matches=first_pass == case.expected_first_pass,
            requested_semantics_preserved=False,
            accepted_after_repair=False,
            deterministic_replay=True,
            package_valid=False,
            player_secret_leak=False,
            diagnostics=tuple(item.code for item in compiled.diagnostics),
        )
    replay = compile_dungeon_plan(proposal.plan)
    assert compiled.topology is not None and compiled.brief is not None
    request = _layout_request(compiled, case.case_id)
    layout = generate_layout(request)
    package_valid = bool(
        layout.success
        and layout.package is not None
        and validate_topology(compiled.topology).valid
        and validate_geometry(layout.package).valid
    )
    # Player output must omit every component the compiler classified as DM-only,
    # including hidden room geometry rather than only secret marker IDs.
    player_secret_leak = False
    if layout.package is not None:
        rendered_ids: set[str] = set()
        for floor in layout.package.floors:
            rendered = render_svg(
                layout.package,
                SvgRenderRequest(
                    schema_version="1.0.0",
                    package_id=layout.package.id,
                    floor_id=floor.id,
                    audience=RenderAudience.PLAYER,
                ),
            )
            rendered_ids.update(rendered.rendered_component_ids)
        dm_only_ids = {
            component.id
            for components in (
                layout.package.rooms,
                layout.package.corridors,
                layout.package.composable_doors,
                layout.package.stairs,
                layout.package.vertical_links,
                layout.package.features,
                layout.package.hazards,
                layout.package.labels,
            )
            for component in components
            if component.visibility.value == "dm_only"
        }
        player_secret_leak = bool(rendered_ids & dm_only_ids)
    return DungeonIntentEvalResult(
        case_id=case.case_id,
        first_pass_schema_valid=True,
        first_pass=first_pass,
        expected_first_pass_matches=first_pass == case.expected_first_pass,
        requested_semantics_preserved=_preserves_expected_semantics(
            case, compiled, first_pass
        ),
        accepted_after_repair=package_valid,
        deterministic_replay=compiled.output_hash == replay.output_hash,
        package_valid=package_valid,
        player_secret_leak=player_secret_leak,
        diagnostics=(),
    )


def _preserves_expected_semantics(
    case: DungeonIntentEvalCase,
    compiled: DungeonPlanCompileResult,
    first_pass: Literal["accepted", "rejected", "abstained"],
) -> bool:
    """Check the frozen suite's compact structural semantic vocabulary."""
    proposal = (
        case.repair_proposal
        if first_pass == "rejected" and case.repair_proposal is not None
        else case.proposal
    )
    if proposal.plan is None or compiled.topology is None:
        return False
    plan = proposal.plan
    flags: set[str] = {"one_floor"}
    if plan.branches:
        flags.add("branch")
    if plan.loops:
        flags.add("loop")
    if any(item.secret for item in plan.loops):
        flags.update(("secret", "hidden"))
    if any(item.dependency_kind.value == "clue" for item in plan.gates):
        flags.add("clue")
    if plan.gates:
        flags.add("gate")
    if any(item.trap is not None for item in plan.room_contents):
        flags.add("trap")
    if any(room.role.value == "optional" for room in plan.rooms):
        flags.add("optional")
    searchable_text = " ".join(
        (plan.title, plan.premise, *(room.name for room in plan.rooms))
    ).lower()
    if "relic" in searchable_text:
        flags.add("final_relic")
    if any(item.objective is not None for item in plan.room_contents):
        flags.add("named_final_objective")
    if first_pass == "rejected":
        flags.add("repair")
    return set(case.expected_semantics) <= flags


def _proposal_status(
    proposal: DungeonGenerationProposal,
) -> Literal["accepted", "rejected", "abstained"]:
    if proposal.abstention is not None:
        return "abstained"
    assert proposal.plan is not None
    return "accepted" if compile_dungeon_plan(proposal.plan).accepted else "rejected"


def _layout_request(result: DungeonPlanCompileResult, case_id: str) -> LayoutRequest:
    """Build a stable kernel request without treating fixture data as server input."""
    assert (
        result.accepted
        and result.output_hash
        and result.brief
        and result.topology
        and result.certificate
        and result.mechanics_plan
    )
    seed = int.from_bytes(sha256(case_id.encode()).digest()[:8], "big")
    return LayoutRequest(
        schema_version="1.0.0",
        package_id=f"eval_{result.output_hash[:24]}",
        brief=result.brief,
        topology=result.topology,
        certificate=result.certificate,
        seed=seed,
        generator_version=ORTHOGONAL_LAYOUT_GENERATOR_VERSION,
        mechanics_plan=result.mechanics_plan,
        floor_bounds=result.floor_bounds,
    )
