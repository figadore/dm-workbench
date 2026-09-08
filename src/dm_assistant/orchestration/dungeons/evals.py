"""Synthetic, provider-free evaluation for compact alpha V1 dungeon intent.

This deliberately evaluates model-shaped submissions without starting preparation
runs or calling a provider.  Live comparisons are an explicit operator action,
not test-suite behavior.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dm_assistant.modules.modeling import ReasoningEffort, ResolvedModelRunProfile
from dm_assistant.modules.preparation import canonical_json_sha256
from dm_assistant.orchestration.dungeons.canary import DUNGEON_TIER_A_CANARY
from dm_assistant.orchestration.dungeons.contracts import (
    DungeonGenerationProposal,
    DungeonStudioSpecification,
)
from dm_assistant.orchestration.dungeons.exploration_prompting import (
    dungeon_exploration_task_contract_sha256,
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


DungeonTierAGrounding = Literal["standalone", "synthetic_grounded"]
DungeonTierAScore = Literal[1, 2, 3, 4, 5]


class DungeonTierAEvalCase(_EvalModel):
    """One original synthetic Tier A brief, never a retained provider response."""

    case_id: str = Field(pattern=r"^tier_a_case_[0-9]{2}$")
    title: str = Field(min_length=1, max_length=120)
    setting: str = Field(min_length=20, max_length=500)
    interaction_style: str = Field(min_length=20, max_length=300)
    grounding: DungeonTierAGrounding
    authorized_facts: tuple[str, ...] = Field(max_length=8)
    prompt: str = Field(min_length=1, max_length=4_000)

    @model_validator(mode="after")
    def validate_grounding(self) -> Self:
        if self.grounding == "standalone" and self.authorized_facts:
            raise ValueError("standalone eval cases cannot contain authorized facts")
        if self.grounding == "synthetic_grounded" and not self.authorized_facts:
            raise ValueError("grounded eval cases require synthetic authorized facts")
        return self


class DungeonTierAEvalVariant(_EvalModel):
    """A stable blind ID whose assignment stays out of the reviewer packet."""

    variant_id: str = Field(pattern=r"^variant_[0-9]{2}$")


class DungeonTierAEvalManifest(_EvalModel):
    """Frozen provider-free protocol for multi-case Tier A comparison."""

    schema_version: Literal["dungeon-tier-a-eval-manifest-v1"]
    rubric_version: Literal["dungeon-tier-a-human-rubric-v1"]
    measurement_version: Literal["dungeon-tier-a-run-measurement-v1"]
    content_policy: Literal["synthetic-non-copyrighted-only"]
    blinding_policy: Literal["variant-assignment-hidden-from-reviewers"]
    score_policy: Literal["five-point-quality-1-unusable-3-usable-5-excellent"]
    variants: tuple[DungeonTierAEvalVariant, ...] = Field(min_length=2, max_length=8)
    cases: tuple[DungeonTierAEvalCase, ...] = Field(min_length=3, max_length=8)

    @model_validator(mode="after")
    def validate_distinct_cases_and_variants(self) -> Self:
        case_ids = [case.case_id for case in self.cases]
        variant_ids = [variant.variant_id for variant in self.variants]
        if len(set(case_ids)) != len(case_ids):
            raise ValueError("Tier A eval case IDs must be unique")
        if len(set(variant_ids)) != len(variant_ids):
            raise ValueError("Tier A eval variant IDs must be unique")
        if len({case.setting.casefold() for case in self.cases}) != len(self.cases):
            raise ValueError("Tier A eval settings must be distinct")
        if len({case.interaction_style.casefold() for case in self.cases}) != len(
            self.cases
        ):
            raise ValueError("Tier A eval interaction styles must be distinct")
        return self


class DungeonExplorationOverageCasePin(_EvalModel):
    """Body-free binding between one fixed Tier A case and one task contract."""

    case_id: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9_-]+$")
    case_definition_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    task_contract_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class DungeonExplorationOverageProtocol(_EvalModel):
    """Provider-free pins and repeat threshold for exploration-output overages."""

    protocol_version: Literal["dungeon-exploration-overage-protocol-v1"]
    prompt_version: str
    instruction_version: str
    output_schema_name: Literal["dungeon_exploration_enrichment"]
    output_schema_version: Literal["1.0.0"]
    requested_effort: ReasoningEffort
    output_token_limit: Literal[2048]
    cumulative_token_budget: Literal[6000]
    repair_limit: Literal[1]
    repeated_failure_case_threshold: Literal[2]
    variant_assignment_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reference_case: DungeonExplorationOverageCasePin
    cases: tuple[DungeonExplorationOverageCasePin, ...] = Field(
        min_length=3, max_length=8
    )

    @model_validator(mode="after")
    def require_one_contract_and_distinct_cases(self) -> Self:
        all_cases = (self.reference_case, *self.cases)
        case_ids = [case.case_id for case in all_cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("exploration overage protocol case IDs must be unique")
        if len({case.case_definition_sha256 for case in all_cases}) != len(all_cases):
            raise ValueError("exploration overage case definitions must be distinct")
        if len({case.task_contract_sha256 for case in all_cases}) != 1:
            raise ValueError("exploration overage protocol requires one task contract")
        return self


class DungeonExplorationOverageObservation(_EvalModel):
    """One qualifying body-free output-ceiling failure from a fixed eval case."""

    evidence_version: Literal["dungeon-exploration-overage-evidence-v1"]
    attempt_run_id: UUID
    case_id: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9_-]+$")
    case_definition_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    variant_assignment_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    task_contract_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    public_code: Literal["dungeon_exploration_prompt_token_budget_exhausted"]
    stage: Literal["model_submission"]
    limit_kind: Literal["output"]
    output_token_limit: Literal[2048]
    cumulative_token_budget: Literal[6000]
    usage_measured: Literal[True]
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    repair_attempted: Literal[False]
    artifact_published: Literal[False]

    @model_validator(mode="after")
    def require_unconfounded_output_overage(self) -> Self:
        if self.output_tokens <= self.output_token_limit:
            raise ValueError(
                "exploration overage output tokens must be greater than 2,048"
            )
        if self.input_tokens + self.output_tokens > self.cumulative_token_budget:
            raise ValueError(
                "exploration overage must remain within the 6,000-token cumulative budget"
            )
        return self


class DungeonExplorationOverageAssessment(_EvalModel):
    """Body-free result; meeting the repeat gate does not authorize a live call."""

    assessment_version: Literal["dungeon-exploration-overage-assessment-v1"]
    protocol_version: Literal["dungeon-exploration-overage-protocol-v1"]
    task_contract_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    variant_assignment_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    qualifying_case_ids: tuple[str, ...]
    materially_distinct_case_count: int = Field(ge=0)
    repeated_failure_case_threshold: Literal[2]
    matched_comparison_repeat_gate_met: bool

    @model_validator(mode="after")
    def require_count_and_gate_to_match_cases(self) -> Self:
        if self.qualifying_case_ids != tuple(sorted(set(self.qualifying_case_ids))):
            raise ValueError(
                "qualifying exploration overage cases must be unique and sorted"
            )
        if self.materially_distinct_case_count != len(self.qualifying_case_ids):
            raise ValueError("exploration overage case count must match case IDs")
        if (self.variant_assignment_hash is None) == bool(self.qualifying_case_ids):
            raise ValueError("exploration overage assignment hash must match evidence")
        if self.matched_comparison_repeat_gate_met != (
            self.materially_distinct_case_count >= self.repeated_failure_case_threshold
        ):
            raise ValueError("exploration overage repeat gate must match case count")
        return self


class DungeonTierARunMeasurement(_EvalModel):
    """Body-free operational evidence for one case/variant execution."""

    measurement_version: Literal["dungeon-tier-a-run-measurement-v1"]
    run_id: str = Field(pattern=r"^run_[a-z0-9_]+$")
    case_id: str = Field(pattern=r"^tier_a_case_[0-9]{2}$")
    variant_id: str = Field(pattern=r"^variant_[0-9]{2}$")
    variant_assignment_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    latency_milliseconds: int = Field(
        ge=0, description="Cumulative initial-plus-repair wall latency."
    )
    input_tokens: int = Field(
        ge=0, description="Measured cumulative initial-plus-repair input usage."
    )
    output_tokens: int = Field(
        ge=0, description="Measured cumulative initial-plus-repair output usage."
    )
    first_pass_schema_valid: bool
    first_pass_semantic_valid: bool
    first_pass_valid: bool = Field(
        description="Whether the initial output passed both strict validity checks."
    )
    repair_count: int = Field(
        ge=0, le=1, description="The bounded repair count used to compute repair rate."
    )
    final_valid: bool

    @model_validator(mode="after")
    def validate_attempt_outcome(self) -> Self:
        if self.first_pass_semantic_valid and not self.first_pass_schema_valid:
            raise ValueError("semantic validity requires a schema-valid first pass")
        if self.first_pass_valid != (
            self.first_pass_schema_valid and self.first_pass_semantic_valid
        ):
            raise ValueError(
                "first-pass validity must match schema and semantic validity"
            )
        if self.first_pass_valid and self.repair_count:
            raise ValueError("a first-pass-valid run cannot have a repair")
        if self.first_pass_valid and not self.final_valid:
            raise ValueError("a first-pass-valid run must remain valid")
        if not self.first_pass_valid and self.final_valid and self.repair_count != 1:
            raise ValueError("a repaired valid run must record exactly one repair")
        if self.final_valid != (self.artifact_hash is not None):
            raise ValueError("only a final-valid run can identify a review artifact")
        return self


class DungeonTierAHumanReview(_EvalModel):
    """Blinded ratings only; provider prompts, responses, and excerpts are forbidden."""

    rubric_version: Literal["dungeon-tier-a-human-rubric-v1"]
    review_id: str = Field(pattern=r"^review_[a-z0-9_]+$")
    reviewer_id: str = Field(pattern=r"^reviewer_[a-z0-9_]+$")
    case_id: str = Field(pattern=r"^tier_a_case_[0-9]{2}$")
    variant_id: str = Field(pattern=r"^variant_[0-9]{2}$")
    artifact_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    thematic_reinforcement: DungeonTierAScore
    history_environment_causality: DungeonTierAScore
    mechanic_objective_unity: DungeonTierAScore
    progression: DungeonTierAScore
    intentional_motif_variation: DungeonTierAScore
    lore_consistency: DungeonTierAScore | None
    clue_logic: DungeonTierAScore
    player_agency: DungeonTierAScore
    puzzle_comprehensibility: DungeonTierAScore
    exploration_quality: DungeonTierAScore
    dm_prep_usefulness: DungeonTierAScore


class DungeonTierAEvidenceMatrix(_EvalModel):
    """Validated evaluator-side join; this is not a reviewer-facing packet."""

    manifest: DungeonTierAEvalManifest
    run_measurements: tuple[DungeonTierARunMeasurement, ...]
    human_reviews: tuple[DungeonTierAHumanReview, ...]

    @model_validator(mode="after")
    def validate_matrix(self) -> Self:
        _validate_dungeon_tier_a_evidence_matrix(
            self.manifest,
            self.run_measurements,
            self.human_reviews,
        )
        return self


class DungeonTierAVariantAggregate(_EvalModel):
    """Body-free descriptive statistics for one still-opaque variant."""

    variant_id: str = Field(pattern=r"^variant_[0-9]{2}$")
    case_count: int = Field(ge=1)
    thematic_reinforcement_mean: float = Field(ge=1, le=5)
    history_environment_causality_mean: float = Field(ge=1, le=5)
    mechanic_objective_unity_mean: float = Field(ge=1, le=5)
    progression_mean: float = Field(ge=1, le=5)
    intentional_motif_variation_mean: float = Field(ge=1, le=5)
    lore_consistency_mean: float | None = Field(default=None, ge=1, le=5)
    lore_consistency_rating_count: int = Field(ge=0)
    clue_logic_mean: float = Field(ge=1, le=5)
    player_agency_mean: float = Field(ge=1, le=5)
    puzzle_comprehensibility_mean: float = Field(ge=1, le=5)
    exploration_quality_mean: float = Field(ge=1, le=5)
    dm_prep_usefulness_mean: float = Field(ge=1, le=5)
    mean_latency_milliseconds: float = Field(ge=0)
    mean_input_tokens: float = Field(ge=0)
    mean_output_tokens: float = Field(ge=0)
    mean_total_tokens: float = Field(ge=0)
    first_pass_validity_rate: float = Field(ge=0, le=1)
    repair_rate: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_lore_aggregate(self) -> Self:
        if self.lore_consistency_rating_count > self.case_count:
            raise ValueError("lore rating count cannot exceed the case count")
        if (self.lore_consistency_mean is None) != (
            self.lore_consistency_rating_count == 0
        ):
            raise ValueError("lore mean and rating count must be present together")
        return self


class DungeonTierABlindedAggregate(_EvalModel):
    """Comparison statistics with no assignment, artifact, run, or reviewer IDs."""

    aggregation_version: Literal["dungeon-tier-a-blinded-aggregate-v1"]
    rubric_version: Literal["dungeon-tier-a-human-rubric-v1"]
    measurement_version: Literal["dungeon-tier-a-run-measurement-v1"]
    variants: tuple[DungeonTierAVariantAggregate, ...] = Field(
        min_length=2, max_length=8
    )

    @model_validator(mode="after")
    def validate_variants(self) -> Self:
        variant_ids = [item.variant_id for item in self.variants]
        if len(variant_ids) != len(set(variant_ids)):
            raise ValueError("blinded aggregate variant IDs must be unique")
        if variant_ids != sorted(variant_ids):
            raise ValueError("blinded aggregate variants must be sorted by opaque ID")
        return self


def build_dungeon_exploration_overage_protocol(
    manifest: DungeonTierAEvalManifest,
    profile: ResolvedModelRunProfile,
) -> DungeonExplorationOverageProtocol:
    """Bind every fixed Tier A case to the exact exploration task contract."""

    output_limit = profile.override_notes.get("output_token_limit")
    repair_limit = profile.override_notes.get("repair_limit")
    if output_limit != 2_048:
        raise ValueError("exploration overage protocol requires a 2,048-token limit")
    if profile.token_budget != 6_000:
        raise ValueError("exploration overage protocol requires a 6,000-token budget")
    if repair_limit != 1:
        raise ValueError("exploration overage protocol requires one repair")
    contract_hash = dungeon_exploration_task_contract_sha256(profile)
    assignment_hash = canonical_json_sha256(
        {
            "provider_id": profile.provider_id,
            "model_id": profile.model_id,
            "runtime_adapter": profile.runtime_adapter,
            "requested_effort": profile.requested_effort.value,
            "task_contract_sha256": contract_hash,
        }
    )
    return DungeonExplorationOverageProtocol(
        protocol_version="dungeon-exploration-overage-protocol-v1",
        prompt_version=profile.prompt_version,
        instruction_version=profile.instruction_version,
        output_schema_name="dungeon_exploration_enrichment",
        output_schema_version="1.0.0",
        requested_effort=profile.requested_effort,
        output_token_limit=2_048,
        cumulative_token_budget=6_000,
        repair_limit=1,
        repeated_failure_case_threshold=2,
        variant_assignment_sha256=assignment_hash,
        reference_case=DungeonExplorationOverageCasePin(
            case_id=DUNGEON_TIER_A_CANARY.canary_id,
            case_definition_sha256=canonical_json_sha256(
                {
                    "canary_id": DUNGEON_TIER_A_CANARY.canary_id,
                    "prompt": DUNGEON_TIER_A_CANARY.prompt,
                    "seed": DUNGEON_TIER_A_CANARY.seed,
                }
            ),
            task_contract_sha256=contract_hash,
        ),
        cases=tuple(
            DungeonExplorationOverageCasePin(
                case_id=case.case_id,
                case_definition_sha256=canonical_json_sha256(
                    case.model_dump(mode="json")
                ),
                task_contract_sha256=contract_hash,
            )
            for case in manifest.cases
        ),
    )


def assess_dungeon_exploration_overage_evidence(
    protocol: DungeonExplorationOverageProtocol,
    observations: tuple[DungeonExplorationOverageObservation, ...],
) -> DungeonExplorationOverageAssessment:
    """Recognize the same isolated output overage across fixed distinct cases."""

    pins = {case.case_id: case for case in (protocol.reference_case, *protocol.cases)}
    seen_case_ids: set[str] = set()
    seen_attempt_ids: set[UUID] = set()
    assignment_hashes: set[str] = set()
    expected_contract = protocol.cases[0].task_contract_sha256
    for observation in observations:
        pin = pins.get(observation.case_id)
        if pin is None:
            raise ValueError(
                f"unexpected exploration overage case: {observation.case_id}"
            )
        if observation.case_id in seen_case_ids:
            raise ValueError(
                f"duplicate exploration overage evidence: {observation.case_id}"
            )
        if observation.attempt_run_id in seen_attempt_ids:
            raise ValueError(
                f"duplicate exploration overage attempt: {observation.attempt_run_id}"
            )
        seen_case_ids.add(observation.case_id)
        seen_attempt_ids.add(observation.attempt_run_id)
        if observation.case_definition_sha256 != pin.case_definition_sha256:
            raise ValueError(
                f"exploration overage case hash mismatch: {observation.case_id}"
            )
        if observation.task_contract_sha256 != expected_contract:
            raise ValueError(
                f"exploration overage contract hash mismatch: {observation.case_id}"
            )
        if observation.output_token_limit != protocol.output_token_limit:
            raise ValueError("exploration overage output-token limit drift")
        if observation.cumulative_token_budget != protocol.cumulative_token_budget:
            raise ValueError("exploration overage cumulative-token budget drift")
        if observation.variant_assignment_hash != protocol.variant_assignment_sha256:
            raise ValueError("exploration overage variant assignment drift")
        assignment_hashes.add(observation.variant_assignment_hash)

    case_ids = tuple(sorted(seen_case_ids))
    repeat_gate_met = len(case_ids) >= protocol.repeated_failure_case_threshold
    return DungeonExplorationOverageAssessment(
        assessment_version="dungeon-exploration-overage-assessment-v1",
        protocol_version=protocol.protocol_version,
        task_contract_sha256=expected_contract,
        variant_assignment_hash=(
            next(iter(assignment_hashes)) if assignment_hashes else None
        ),
        qualifying_case_ids=case_ids,
        materially_distinct_case_count=len(case_ids),
        repeated_failure_case_threshold=protocol.repeated_failure_case_threshold,
        matched_comparison_repeat_gate_met=repeat_gate_met,
    )


def validate_dungeon_tier_a_evidence_matrix(
    manifest: DungeonTierAEvalManifest,
    run_measurements: tuple[DungeonTierARunMeasurement, ...],
    human_reviews: tuple[DungeonTierAHumanReview, ...],
) -> DungeonTierAEvidenceMatrix:
    """Fail closed unless every manifest pair has one coherent run and review."""

    return DungeonTierAEvidenceMatrix(
        manifest=manifest,
        run_measurements=tuple(
            sorted(
                run_measurements,
                key=lambda item: (item.variant_id, item.case_id),
            )
        ),
        human_reviews=tuple(
            sorted(
                human_reviews,
                key=lambda item: (item.variant_id, item.case_id),
            )
        ),
    )


def aggregate_dungeon_tier_a_evidence(
    matrix: DungeonTierAEvidenceMatrix,
) -> DungeonTierABlindedAggregate:
    """Aggregate validated evidence without revealing the variant assignments."""

    aggregates: list[DungeonTierAVariantAggregate] = []
    for variant in sorted(matrix.manifest.variants, key=lambda item: item.variant_id):
        runs = tuple(
            item
            for item in matrix.run_measurements
            if item.variant_id == variant.variant_id
        )
        reviews = tuple(
            item
            for item in matrix.human_reviews
            if item.variant_id == variant.variant_id
        )
        count = len(runs)
        lore_scores = tuple(
            item.lore_consistency
            for item in reviews
            if item.lore_consistency is not None
        )
        aggregates.append(
            DungeonTierAVariantAggregate(
                variant_id=variant.variant_id,
                case_count=count,
                thematic_reinforcement_mean=_mean(
                    tuple(item.thematic_reinforcement for item in reviews)
                ),
                history_environment_causality_mean=_mean(
                    tuple(item.history_environment_causality for item in reviews)
                ),
                mechanic_objective_unity_mean=_mean(
                    tuple(item.mechanic_objective_unity for item in reviews)
                ),
                progression_mean=_mean(tuple(item.progression for item in reviews)),
                intentional_motif_variation_mean=_mean(
                    tuple(item.intentional_motif_variation for item in reviews)
                ),
                lore_consistency_mean=(_mean(lore_scores) if lore_scores else None),
                lore_consistency_rating_count=len(lore_scores),
                clue_logic_mean=_mean(tuple(item.clue_logic for item in reviews)),
                player_agency_mean=_mean(tuple(item.player_agency for item in reviews)),
                puzzle_comprehensibility_mean=_mean(
                    tuple(item.puzzle_comprehensibility for item in reviews)
                ),
                exploration_quality_mean=_mean(
                    tuple(item.exploration_quality for item in reviews)
                ),
                dm_prep_usefulness_mean=_mean(
                    tuple(item.dm_prep_usefulness for item in reviews)
                ),
                mean_latency_milliseconds=_mean(
                    tuple(item.latency_milliseconds for item in runs)
                ),
                mean_input_tokens=_mean(tuple(item.input_tokens for item in runs)),
                mean_output_tokens=_mean(tuple(item.output_tokens for item in runs)),
                mean_total_tokens=_mean(
                    tuple(item.input_tokens + item.output_tokens for item in runs)
                ),
                first_pass_validity_rate=_rate(
                    tuple(item.first_pass_valid for item in runs)
                ),
                repair_rate=_rate(tuple(item.repair_count == 1 for item in runs)),
            )
        )
    return DungeonTierABlindedAggregate(
        aggregation_version="dungeon-tier-a-blinded-aggregate-v1",
        rubric_version=matrix.manifest.rubric_version,
        measurement_version=matrix.manifest.measurement_version,
        variants=tuple(aggregates),
    )


def _validate_dungeon_tier_a_evidence_matrix(
    manifest: DungeonTierAEvalManifest,
    run_measurements: tuple[DungeonTierARunMeasurement, ...],
    human_reviews: tuple[DungeonTierAHumanReview, ...],
) -> None:
    expected_pairs = {
        (case.case_id, variant.variant_id)
        for case in manifest.cases
        for variant in manifest.variants
    }
    run_by_pair = _index_tier_a_evidence_pairs(run_measurements, "run")
    review_by_pair = _index_tier_a_evidence_pairs(human_reviews, "review")
    _require_exact_tier_a_pairs(expected_pairs, set(run_by_pair), "run")
    _require_exact_tier_a_pairs(expected_pairs, set(review_by_pair), "review")

    if len({item.run_id for item in run_measurements}) != len(run_measurements):
        raise ValueError("Tier A run IDs must be unique")
    if len({item.review_id for item in human_reviews}) != len(human_reviews):
        raise ValueError("Tier A review IDs must be unique")
    if any(
        item.measurement_version != manifest.measurement_version
        for item in run_measurements
    ):
        raise ValueError("Tier A run measurement version does not match manifest")
    if any(item.rubric_version != manifest.rubric_version for item in human_reviews):
        raise ValueError("Tier A human rubric version does not match manifest")

    for variant in manifest.variants:
        assignment_hashes = {
            item.variant_assignment_hash
            for item in run_measurements
            if item.variant_id == variant.variant_id
        }
        if len(assignment_hashes) != 1:
            raise ValueError(
                f"Tier A variant assignment hash drift: {variant.variant_id}"
            )

    cases_by_id = {case.case_id: case for case in manifest.cases}
    for pair in sorted(expected_pairs):
        run = run_by_pair[pair]
        review = review_by_pair[pair]
        if not run.final_valid or run.artifact_hash is None:
            raise ValueError(
                "Tier A reviewed run must be final-valid: "
                f"{run.case_id}/{run.variant_id}"
            )
        if review.artifact_hash != run.artifact_hash:
            raise ValueError(
                f"Tier A artifact hash mismatch: {run.case_id}/{run.variant_id}"
            )
        case = cases_by_id[run.case_id]
        if case.grounding == "standalone" and review.lore_consistency is not None:
            raise ValueError(
                "Tier A standalone review must omit lore consistency: "
                f"{run.case_id}/{run.variant_id}"
            )
        if case.grounding == "synthetic_grounded" and review.lore_consistency is None:
            raise ValueError(
                "Tier A grounded review requires lore consistency: "
                f"{run.case_id}/{run.variant_id}"
            )


def _index_tier_a_evidence_pairs[
    Evidence: (DungeonTierARunMeasurement, DungeonTierAHumanReview)
](
    evidence: tuple[Evidence, ...],
    evidence_kind: Literal["run", "review"],
) -> dict[tuple[str, str], Evidence]:
    indexed: dict[tuple[str, str], Evidence] = {}
    for item in evidence:
        pair = (item.case_id, item.variant_id)
        if pair in indexed:
            raise ValueError(
                f"Tier A duplicate {evidence_kind} evidence: "
                f"{item.case_id}/{item.variant_id}"
            )
        indexed[pair] = item
    return indexed


def _require_exact_tier_a_pairs(
    expected_pairs: set[tuple[str, str]],
    actual_pairs: set[tuple[str, str]],
    evidence_kind: Literal["run", "review"],
) -> None:
    missing = sorted(expected_pairs - actual_pairs)
    if missing:
        case_id, variant_id = missing[0]
        raise ValueError(
            f"Tier A missing {evidence_kind} evidence: {case_id}/{variant_id}"
        )
    unexpected = sorted(actual_pairs - expected_pairs)
    if unexpected:
        case_id, variant_id = unexpected[0]
        raise ValueError(
            f"Tier A unexpected {evidence_kind} evidence: {case_id}/{variant_id}"
        )


def _mean(values: tuple[int, ...]) -> float:
    if not values:
        raise ValueError("cannot aggregate an empty Tier A evidence set")
    return sum(values) / len(values)


def _rate(values: tuple[bool, ...]) -> float:
    return _mean(tuple(int(value) for value in values))


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
