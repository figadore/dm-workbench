"""Final provider-free staged-dungeon validation and read-only review contracts."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Literal

from pydantic import Field, model_validator

from dm_assistant.errors import ConflictError
from dm_assistant.modules.preparation import (
    GenerationContextEnvelope,
    canonical_json_sha256,
)
from dm_assistant.orchestration.dungeons.continuity import (
    derive_dungeon_creative_continuity,
)
from dm_assistant.orchestration.dungeons.contracts import (
    DungeonCreativeContinuityProjection,
    DungeonStudioSpecification,
    ExactDungeonComponentId,
    GuideLocalRef,
    PromptedDungeonExplorationLineage,
    PromptedDungeonFeatureInteractionLineage,
    PromptedDungeonObjectiveLineage,
    PromptedDungeonPuzzleLineage,
    PromptedDungeonRoomNarrativeLineage,
    PromptedDungeonTrapLineage,
    WorkflowModel,
)
from dm_assistant.orchestration.dungeons.service import (
    build_dungeon_preparation_readiness,
)
from dm_assistant.orchestration.dungeons.staged_enrichment import (
    DungeonStagedEnrichmentTaskKind,
    plan_dungeon_staged_enrichment,
)
from dm_dungeon import (
    DungeonPlan,
    DungeonPlanCompileResult,
    RenderAudience,
    SvgRenderRequest,
    compile_dungeon_plan,
    render_svg,
    validate_geometry,
    validate_topology,
)
from dm_dungeon.contracts import RoomMechanicMarkerKind

DungeonFinalValidationCheckKind = Literal[
    "continuity",
    "sources",
    "dependencies",
    "required_content",
    "lineage",
    "cross_task",
    "secrecy",
]

_CHECK_ORDER: tuple[DungeonFinalValidationCheckKind, ...] = (
    "continuity",
    "sources",
    "dependencies",
    "required_content",
    "lineage",
    "cross_task",
    "secrecy",
)


class DungeonFinalValidationDiagnostic(WorkflowModel):
    """One bounded body-free failure from the final deterministic gate."""

    check: DungeonFinalValidationCheckKind
    code: Literal[
        "dungeon_final.continuity_missing",
        "dungeon_final.continuity_mismatch",
        "dungeon_final.source_inheritance_mismatch",
        "dungeon_final.dependency_mismatch",
        "dungeon_final.required_content_missing",
        "dungeon_final.lineage_coverage_mismatch",
        "dungeon_final.lineage_continuity_mismatch",
        "dungeon_final.lineage_source_mismatch",
        "dungeon_final.cross_task_mismatch",
        "dungeon_final.player_render_failed",
        "dungeon_final.player_secret_leak",
    ]
    component_ids: tuple[ExactDungeonComponentId, ...] = Field(default=(), max_length=8)
    detail_code: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9_.-]+$")

    @model_validator(mode="after")
    def require_unique_component_ids(self) -> DungeonFinalValidationDiagnostic:
        if len(self.component_ids) != len(set(self.component_ids)):
            raise ValueError(
                "final validation diagnostics require unique component IDs"
            )
        return self


class DungeonFinalValidationCheck(WorkflowModel):
    """Stable summary for one mandatory deterministic check family."""

    kind: DungeonFinalValidationCheckKind
    passed: bool
    diagnostic_count: int = Field(ge=0, le=64)

    @model_validator(mode="after")
    def require_pass_to_match_count(self) -> DungeonFinalValidationCheck:
        if self.passed != (self.diagnostic_count == 0):
            raise ValueError(
                "final validation check status must match diagnostic count"
            )
        return self


class DungeonFinalValidationResult(WorkflowModel):
    """Read-only evidence required before subjective whole-dungeon review."""

    schema_version: Literal["1.0.0"] = "1.0.0"
    specification_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    creative_continuity_sha256: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    valid: bool
    checks: tuple[DungeonFinalValidationCheck, ...] = Field(min_length=7, max_length=7)
    diagnostics: tuple[DungeonFinalValidationDiagnostic, ...] = Field(
        default=(), max_length=64
    )

    @model_validator(mode="after")
    def require_complete_consistent_checks(self) -> DungeonFinalValidationResult:
        if tuple(item.kind for item in self.checks) != _CHECK_ORDER:
            raise ValueError("final validation requires every check in stable order")
        counts = {
            kind: sum(item.check == kind for item in self.diagnostics)
            for kind in _CHECK_ORDER
        }
        if any(item.diagnostic_count != counts[item.kind] for item in self.checks):
            raise ValueError("final validation check counts must match diagnostics")
        if self.valid != (not self.diagnostics):
            raise ValueError("final validation validity must match diagnostics")
        return self


DungeonCohesionDimension = Literal[
    "thematic_reinforcement",
    "history_environment_causality",
    "mechanic_objective_unity",
    "progression",
    "motif_variation",
    "selected_lore_consistency",
]

_COHESION_DIMENSIONS: tuple[DungeonCohesionDimension, ...] = (
    "thematic_reinforcement",
    "history_environment_causality",
    "mechanic_objective_unity",
    "progression",
    "motif_variation",
    "selected_lore_consistency",
)


class DungeonCohesionTargetedRecommendation(WorkflowModel):
    """A recommendation for one existing seam, never replacement content."""

    task_kind: DungeonStagedEnrichmentTaskKind
    room_ids: tuple[ExactDungeonComponentId, ...] = Field(min_length=1, max_length=8)
    target_ids: tuple[ExactDungeonComponentId, ...] = Field(min_length=1, max_length=8)
    rationale: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def require_exact_target_shape(self) -> DungeonCohesionTargetedRecommendation:
        if len(self.room_ids) != len(set(self.room_ids)) or len(self.target_ids) != len(
            set(self.target_ids)
        ):
            raise ValueError("cohesion recommendations require unique exact IDs")
        if self.task_kind == "room_narrative":
            if self.room_ids != self.target_ids:
                raise ValueError("narrative recommendations target exact room IDs")
        elif len(self.room_ids) != 1 or len(self.target_ids) != 1:
            raise ValueError("mechanic recommendations target one exact seam")
        return self


class DungeonCohesionFinding(WorkflowModel):
    """Bounded subjective concern with exact evidence and optional targeted follow-up."""

    finding_code: GuideLocalRef
    severity: Literal["note", "concern", "blocking_dm_review"]
    summary: str = Field(min_length=1, max_length=500)
    evidence_component_ids: tuple[ExactDungeonComponentId, ...] = Field(
        default=(), max_length=8
    )
    recommendation: DungeonCohesionTargetedRecommendation | None = None

    @model_validator(mode="after")
    def require_unique_evidence(self) -> DungeonCohesionFinding:
        if len(self.evidence_component_ids) != len(set(self.evidence_component_ids)):
            raise ValueError("cohesion finding evidence IDs must be unique")
        return self


class DungeonCohesionAssessment(WorkflowModel):
    """One non-authoritative assessment of a required whole-dungeon dimension."""

    dimension: DungeonCohesionDimension
    decision: Literal["pass", "needs_dm_disposition", "not_applicable"]
    findings: tuple[DungeonCohesionFinding, ...] = Field(default=(), max_length=8)

    @model_validator(mode="after")
    def require_decision_to_match_findings(self) -> DungeonCohesionAssessment:
        if self.decision == "needs_dm_disposition" and not self.findings:
            raise ValueError("a disposition decision requires at least one finding")
        if self.decision != "needs_dm_disposition" and any(
            item.severity == "blocking_dm_review" for item in self.findings
        ):
            raise ValueError("blocking review findings require DM disposition")
        return self


class DungeonCohesionReviewReport(WorkflowModel):
    """Read-only holistic report; this contract has no edit or approval operation."""

    schema_version: Literal["1.0.0"] = "1.0.0"
    specification_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    deterministic_validation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    creative_continuity_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reviewer_kind: Literal["bounded_model", "human_dm"]
    non_authoritative: Literal[True] = True
    assessments: tuple[DungeonCohesionAssessment, ...] = Field(
        min_length=6, max_length=6
    )

    @model_validator(mode="after")
    def require_every_dimension_once(self) -> DungeonCohesionReviewReport:
        if tuple(item.dimension for item in self.assessments) != _COHESION_DIMENSIONS:
            raise ValueError("cohesion report requires every dimension in stable order")
        return self


def validate_final_staged_dungeon(
    specification: DungeonStudioSpecification,
) -> DungeonFinalValidationResult:
    """Recompute final deterministic evidence without editing or persisting state."""

    diagnostics: list[DungeonFinalValidationDiagnostic] = []
    plan = _accepted_plan(specification, diagnostics)
    continuity = _validate_continuity(specification, plan, diagnostics)
    compiled = _validate_dependencies(specification, plan, diagnostics)
    _validate_required_content(specification, diagnostics)
    _validate_lineage(specification, continuity, diagnostics)
    _validate_cross_task(specification, compiled, diagnostics)
    _validate_player_secrecy(specification, diagnostics)
    diagnostics = _deduplicate(diagnostics)
    counts = {
        kind: sum(item.check == kind for item in diagnostics) for kind in _CHECK_ORDER
    }
    return DungeonFinalValidationResult(
        specification_sha256=canonical_json_sha256(
            specification.model_dump(mode="json")
        ),
        creative_continuity_sha256=(
            continuity.projection_sha256 if continuity is not None else None
        ),
        valid=not diagnostics,
        checks=tuple(
            DungeonFinalValidationCheck(
                kind=kind,
                passed=counts[kind] == 0,
                diagnostic_count=counts[kind],
            )
            for kind in _CHECK_ORDER
        ),
        diagnostics=tuple(diagnostics),
    )


def _accepted_plan(
    specification: DungeonStudioSpecification,
    diagnostics: list[DungeonFinalValidationDiagnostic],
) -> DungeonPlan | None:
    proposal = next(
        (
            lineage.proposal
            for lineage in reversed(specification.model_lineage)
            if lineage.proposal is not None and lineage.proposal.plan is not None
        ),
        None,
    )
    if proposal is None or proposal.plan is None:
        diagnostics.append(
            _diagnostic(
                "continuity",
                "dungeon_final.continuity_missing",
                "structural_plan_lineage_missing",
                specification.package.id,
            )
        )
        return None
    return proposal.plan


def _validate_continuity(
    specification: DungeonStudioSpecification,
    plan: DungeonPlan | None,
    diagnostics: list[DungeonFinalValidationDiagnostic],
) -> DungeonCreativeContinuityProjection | None:
    context_pin = specification.structural_context
    continuity = specification.creative_continuity
    if context_pin is None or continuity is None or plan is None:
        if plan is not None:
            diagnostics.append(
                _diagnostic(
                    "continuity",
                    "dungeon_final.continuity_missing",
                    "projection_or_context_missing",
                    specification.package.id,
                )
            )
        return None
    try:
        envelope = GenerationContextEnvelope.model_validate_json(
            json.dumps(context_pin.envelope)
        )
    except ValueError:
        diagnostics.append(
            _diagnostic(
                "sources",
                "dungeon_final.source_inheritance_mismatch",
                "structural_envelope_invalid",
                specification.package.id,
            )
        )
        return continuity
    if (
        envelope.context_kind != context_pin.envelope_kind
        or envelope.payload_version != context_pin.payload_version
        or envelope.payload_sha256 != context_pin.payload_sha256
        or envelope.source_links != context_pin.source_links
    ):
        diagnostics.append(
            _diagnostic(
                "sources",
                "dungeon_final.source_inheritance_mismatch",
                "structural_context_pin_mismatch",
                specification.package.id,
            )
        )
    try:
        expected = derive_dungeon_creative_continuity(envelope, plan)
    except (ConflictError, ValueError):
        diagnostics.append(
            _diagnostic(
                "continuity",
                "dungeon_final.continuity_mismatch",
                "projection_rebuild_failed",
                specification.package.id,
            )
        )
        return continuity
    if expected != continuity:
        diagnostics.append(
            _diagnostic(
                "continuity",
                "dungeon_final.continuity_mismatch",
                "projection_rebuild_mismatch",
                specification.package.id,
            )
        )
    return continuity


def _validate_dependencies(
    specification: DungeonStudioSpecification,
    plan: DungeonPlan | None,
    diagnostics: list[DungeonFinalValidationDiagnostic],
) -> DungeonPlanCompileResult | None:
    topology_report = validate_topology(specification.package.topology)
    geometry_report = validate_geometry(specification.package)
    if not topology_report.valid or not geometry_report.valid:
        affected = tuple(
            dict.fromkeys(
                [
                    *(
                        component_id
                        for item in topology_report.diagnostics
                        for component_id in item.affected_ids
                    ),
                    *(
                        component_id
                        for item in geometry_report.diagnostics
                        for component_id in item.affected_ids
                    ),
                ]
            )
        )[:8]
        diagnostics.append(
            _diagnostic(
                "dependencies",
                "dungeon_final.dependency_mismatch",
                "package_validation_failed",
                *affected,
            )
        )
    if plan is None:
        return None
    compiled = compile_dungeon_plan(plan)
    if (
        not compiled.accepted
        or compiled.certificate is None
        or compiled.topology is None
        or compiled.mechanics_plan is None
        or specification.layout_request.certificate != compiled.certificate
        or specification.layout_request.topology != compiled.topology
        or specification.layout_request.mechanics_plan != compiled.mechanics_plan
        or specification.package.topology != compiled.topology
        or specification.package.id != specification.layout_request.package_id
    ):
        diagnostics.append(
            _diagnostic(
                "dependencies",
                "dungeon_final.dependency_mismatch",
                "structural_projection_mismatch",
                specification.package.id,
            )
        )
        return compiled

    guide = specification.dm_guide
    if guide is None:
        return compiled
    witnesses = {item.gate_id: item for item in compiled.certificate.gates}
    dependencies = {item.target_gate_id: item for item in guide.dependencies}
    guide_gate_ids = {
        item.gate_id for item in guide.connections if item.gate_id is not None
    }
    if set(witnesses) != set(dependencies) or set(witnesses) != guide_gate_ids:
        diagnostics.append(
            _diagnostic(
                "dependencies",
                "dungeon_final.dependency_mismatch",
                "guide_gate_set_mismatch",
                *(set(witnesses) ^ set(dependencies) ^ guide_gate_ids),
            )
        )
    for gate_id, witness in witnesses.items():
        dependency = dependencies.get(gate_id)
        if dependency is None:
            continue
        if (
            dependency.dependency_id != witness.dependency_id
            or dependency.room_id != witness.dependency_room_id
            or dependency.room_map_reference.component_id != dependency.room_id
            or dependency.room_id not in witness.reachable_before_gate_room_ids
        ):
            diagnostics.append(
                _diagnostic(
                    "dependencies",
                    "dungeon_final.dependency_mismatch",
                    "guide_dependency_witness_mismatch",
                    gate_id,
                    dependency.dependency_id,
                )
            )
    return compiled


def _validate_required_content(
    specification: DungeonStudioSpecification,
    diagnostics: list[DungeonFinalValidationDiagnostic],
) -> None:
    guide = specification.dm_guide
    if guide is None:
        diagnostics.append(
            _diagnostic(
                "required_content",
                "dungeon_final.required_content_missing",
                "dm_guide_missing",
                specification.package.id,
            )
        )
        return
    expected = build_dungeon_preparation_readiness(guide)
    if (
        expected is None
        or not expected.ready
        or specification.preparation_readiness != expected
    ):
        component_ids = (
            tuple(item.component_id for item in expected.diagnostics)[:8]
            if expected is not None
            else (specification.package.id,)
        )
        diagnostics.append(
            _diagnostic(
                "required_content",
                "dungeon_final.required_content_missing",
                "preparation_readiness_mismatch",
                *component_ids,
            )
        )
    staged = plan_dungeon_staged_enrichment(specification)
    if staged.status != "complete":
        component_ids = tuple(item.component_id for item in staged.blockers)[:8]
        if staged.next_task is not None:
            component_ids = staged.next_task.target_ids
        diagnostics.append(
            _diagnostic(
                "required_content",
                "dungeon_final.required_content_missing",
                f"staged_plan_{staged.status}",
                *component_ids,
            )
        )


EnrichmentLineage = (
    PromptedDungeonPuzzleLineage
    | PromptedDungeonExplorationLineage
    | PromptedDungeonFeatureInteractionLineage
    | PromptedDungeonTrapLineage
    | PromptedDungeonObjectiveLineage
    | PromptedDungeonRoomNarrativeLineage
)


def _lineages(
    specification: DungeonStudioSpecification,
) -> tuple[EnrichmentLineage, ...]:
    return (
        *specification.puzzle_model_lineage,
        *specification.exploration_model_lineage,
        *specification.feature_interaction_model_lineage,
        *specification.trap_model_lineage,
        *specification.objective_model_lineage,
        *specification.room_narrative_model_lineage,
    )


def _validate_lineage(
    specification: DungeonStudioSpecification,
    continuity: DungeonCreativeContinuityProjection | None,
    diagnostics: list[DungeonFinalValidationDiagnostic],
) -> None:
    staged = plan_dungeon_staged_enrichment(specification)
    if staged.status != "complete":
        diagnostics.append(
            _diagnostic(
                "lineage",
                "dungeon_final.lineage_coverage_mismatch",
                "accepted_slot_coverage_incomplete",
                specification.package.id,
            )
        )
    if continuity is None:
        return
    facts = {fact.fact_id: fact for fact in continuity.selected_facts}
    for lineage in _lineages(specification):
        target_ids = _lineage_target_ids(lineage)
        if (
            lineage.creative_continuity_version != continuity.projection_version
            or lineage.creative_continuity_sha256 != continuity.projection_sha256
            or lineage.model_run.status != "succeeded"
            or lineage.model_run.output_payload
            != lineage.output.model_dump(mode="json")
        ):
            diagnostics.append(
                _diagnostic(
                    "lineage",
                    "dungeon_final.lineage_continuity_mismatch",
                    "accepted_lineage_pin_mismatch",
                    *target_ids,
                )
            )
        selected_ids = lineage.selected_fact_ids
        expected_sources = (
            {
                source_id
                for fact_id in selected_ids
                for source_id in facts[fact_id].source_ids
            }
            if all(fact_id in facts for fact_id in selected_ids)
            else None
        )
        if (
            len(selected_ids) != len(set(selected_ids))
            or len(lineage.source_ids) != len(set(lineage.source_ids))
            or expected_sources is None
            or set(lineage.source_ids) != expected_sources
        ):
            diagnostics.append(
                _diagnostic(
                    "sources",
                    "dungeon_final.lineage_source_mismatch",
                    "accepted_lineage_source_mismatch",
                    *target_ids,
                )
            )


def _validate_cross_task(
    specification: DungeonStudioSpecification,
    compiled: DungeonPlanCompileResult | None,
    diagnostics: list[DungeonFinalValidationDiagnostic],
) -> None:
    package = specification.package
    package_id = package.id
    room_ids = {room.id for room in package.rooms}
    exploration_slots = {slot.id: slot.room_id for slot in package.encounter_slots}
    marker_kind = {
        marker.id: (marker.room_id, marker.kind)
        for marker in package.room_mechanic_markers
    }
    accepted_mechanic_ids = {
        *(item.output.room_id for item in specification.puzzle_model_lineage),
        *(
            item.output.encounter_slot_id
            for item in specification.exploration_model_lineage
        ),
        *(
            item.output.feature_id
            for item in specification.feature_interaction_model_lineage
        ),
        *(item.output.trap_id for item in specification.trap_model_lineage),
    }
    bad_ids: list[str] = []

    for puzzle_lineage in specification.puzzle_model_lineage:
        puzzle_output = puzzle_lineage.output
        if (
            puzzle_output.package_id != package_id
            or puzzle_output.room_id not in room_ids
        ):
            bad_ids.append(puzzle_output.room_id)
        known_locations = room_ids | set(marker_kind)
        known_locations.update(item.id for item in package.features)
        known_locations.update(item.id for item in package.topology.keys)
        known_locations.update(item.id for item in package.topology.clues)
        bad_ids.extend(
            clue.location_id
            for clue in puzzle_output.clue_path
            if clue.location_id not in known_locations
        )
    for exploration_lineage in specification.exploration_model_lineage:
        exploration_output = exploration_lineage.output
        if (
            exploration_output.package_id != package_id
            or exploration_slots.get(exploration_output.encounter_slot_id)
            != exploration_output.room_id
        ):
            bad_ids.append(exploration_output.encounter_slot_id)
        bad_ids.extend(
            affordance_id
            for approach in exploration_output.approaches
            for affordance_id in approach.affordance_ids
            if marker_kind.get(affordance_id)
            != (exploration_output.room_id, RoomMechanicMarkerKind.FEATURE)
        )
    for feature_lineage in specification.feature_interaction_model_lineage:
        feature_output = feature_lineage.output
        if feature_output.package_id != package_id or marker_kind.get(
            feature_output.feature_id
        ) != (feature_output.room_id, RoomMechanicMarkerKind.FEATURE):
            bad_ids.append(feature_output.feature_id)
    for trap_lineage in specification.trap_model_lineage:
        trap_output = trap_lineage.output
        if trap_output.package_id != package_id or marker_kind.get(
            trap_output.trap_id
        ) != (trap_output.room_id, RoomMechanicMarkerKind.TRAP):
            bad_ids.append(trap_output.trap_id)
    for objective_lineage in specification.objective_model_lineage:
        objective_output = objective_lineage.output
        if objective_output.package_id != package_id or marker_kind.get(
            objective_output.objective_id
        ) != (objective_output.room_id, RoomMechanicMarkerKind.OBJECTIVE):
            bad_ids.append(objective_output.objective_id)
        bad_ids.extend(
            mechanic_id
            for resolution in objective_output.resolutions
            for mechanic_id in resolution.mechanic_ids
            if mechanic_id not in accepted_mechanic_ids
        )
    for narrative_lineage in specification.room_narrative_model_lineage:
        narrative_output = narrative_lineage.output
        if narrative_output.package_id != package_id:
            bad_ids.append(narrative_output.package_id)
        bad_ids.extend(
            room.room_id
            for room in narrative_output.rooms
            if room.room_id not in room_ids
        )

    if (
        compiled is not None
        and getattr(compiled, "accepted", False)
        and compiled.certificate is not None
        and compiled.mechanics_plan is not None
    ):
        room_ids_from_certificate = {
            item.room_id for item in compiled.certificate.rooms
        }
        objective_targets = {
            item.id: (item.room_id, item.name)
            for item in compiled.mechanics_plan.room_objectives
        }
        guide = specification.dm_guide
        if guide is not None:
            bad_ids.extend(
                objective.marker_id
                for objective in guide.objectives
                if objective.room_id not in room_ids_from_certificate
                or objective_targets.get(objective.marker_id)
                != (objective.room_id, objective.name)
            )
    if bad_ids:
        diagnostics.append(
            _diagnostic(
                "cross_task",
                "dungeon_final.cross_task_mismatch",
                "typed_reference_mismatch",
                *tuple(dict.fromkeys(bad_ids))[:8],
            )
        )


def _validate_player_secrecy(
    specification: DungeonStudioSpecification,
    diagnostics: list[DungeonFinalValidationDiagnostic],
) -> None:
    package = specification.package
    component_groups = (
        package.rooms,
        package.corridors,
        package.composable_doors,
        package.vertical_endpoint_doors,
        package.stairs,
        package.vertical_links,
        package.features,
        package.terrain,
        package.hazards,
        package.zones,
        package.labels,
        package.room_mechanic_markers,
    )
    protected_ids = {
        component.id
        for components in component_groups
        for component in components
        if component.visibility.value == "dm_only"
    }
    protected_ids.update(item.id for item in package.encounter_slots)
    protected_ids.update(item.id for item in package.position_anchors)
    protected_ids.update(
        item.id
        for item in package.room_mechanic_markers
        if item.kind is not RoomMechanicMarkerKind.FEATURE
    )
    # Retained accepted lineage remains authoritative if a malformed in-memory
    # package attempts to relabel a trap/objective marker as player-safe.
    protected_ids.update(
        item.output.trap_id for item in specification.trap_model_lineage
    )
    protected_ids.update(
        item.output.objective_id for item in specification.objective_model_lineage
    )
    for floor in package.floors:
        result = render_svg(
            package,
            SvgRenderRequest(
                schema_version="1.0.0",
                package_id=package.id,
                floor_id=floor.id,
                audience=RenderAudience.PLAYER,
                show_markers=True,
            ),
        )
        if not result.success or result.svg is None:
            diagnostics.append(
                _diagnostic(
                    "secrecy",
                    "dungeon_final.player_render_failed",
                    "player_svg_render_failed",
                    floor.id,
                )
            )
            continue
        leaked = protected_ids.intersection(result.rendered_component_ids)
        leaked.update(
            component_id for component_id in protected_ids if component_id in result.svg
        )
        if leaked:
            diagnostics.append(
                _diagnostic(
                    "secrecy",
                    "dungeon_final.player_secret_leak",
                    "protected_component_rendered",
                    *tuple(sorted(leaked))[:8],
                )
            )


def _lineage_target_ids(lineage: EnrichmentLineage) -> tuple[str, ...]:
    if isinstance(lineage, PromptedDungeonRoomNarrativeLineage):
        return tuple(room.room_id for room in lineage.output.rooms)
    if isinstance(lineage, PromptedDungeonExplorationLineage):
        return (lineage.output.encounter_slot_id,)
    if isinstance(lineage, PromptedDungeonFeatureInteractionLineage):
        return (lineage.output.feature_id,)
    if isinstance(lineage, PromptedDungeonTrapLineage):
        return (lineage.output.trap_id,)
    if isinstance(lineage, PromptedDungeonObjectiveLineage):
        return (lineage.output.objective_id,)
    return (lineage.output.room_id,)


def _diagnostic(
    check: DungeonFinalValidationCheckKind,
    code: str,
    detail_code: str,
    *component_ids: str,
) -> DungeonFinalValidationDiagnostic:
    return DungeonFinalValidationDiagnostic.model_validate(
        {
            "check": check,
            "code": code,
            "component_ids": tuple(dict.fromkeys(component_ids))[:8],
            "detail_code": detail_code,
        }
    )


def _deduplicate(
    diagnostics: Iterable[DungeonFinalValidationDiagnostic],
) -> list[DungeonFinalValidationDiagnostic]:
    unique = {
        (item.check, item.code, item.detail_code, item.component_ids): item
        for item in diagnostics
    }
    return [unique[key] for key in sorted(unique)]
