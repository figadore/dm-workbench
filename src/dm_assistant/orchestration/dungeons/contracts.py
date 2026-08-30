"""Provider-independent Dungeon Studio workflow contracts."""

from __future__ import annotations

import re
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from dm_assistant.modules.modeling import ModelRunRecord
from dm_assistant.modules.preparation import (
    GenerationContextPin,
    ToolRunPin,
    canonical_json_sha256,
)
from dm_assistant.modules.scope import TaskScope, TaskType
from dm_dungeon import (
    DungeonPackage,
    DungeonPlan,
    LayoutRequest,
    MapCallout,
)
from dm_dungeon.contracts import (
    BarrierIntent,
    EncounterSlotIntent,
    EndpointDoorKind,
    FeatureIntentKind,
    GridPoint,
    ObjectiveKind,
    PolygonGeometry,
    RoomCapacity,
    RoomRole,
    VerticalEndpointSide,
)

DUNGEON_GENERATION_PROPOSAL_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"
DUNGEON_EXPLORATION_ENRICHMENT_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"
DUNGEON_FEATURE_INTERACTION_ENRICHMENT_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"
DUNGEON_OBJECTIVE_ENRICHMENT_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"
DUNGEON_TRAP_ENRICHMENT_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"
DUNGEON_PUZZLE_ENRICHMENT_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"


class WorkflowModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=False)


class PromptedDungeonModelLineage(WorkflowModel):
    """One validated structural model response retained for replay and review."""

    model_run_id: UUID
    model_run: ModelRunRecord
    proposal: DungeonGenerationProposal | None = None

    @model_validator(mode="after")
    def require_model_result_for_success(self) -> PromptedDungeonModelLineage:
        if self.model_run.status == "abstained":
            if self.proposal is not None:
                raise ValueError(
                    "abstained lineage cannot claim a validated model result"
                )
        elif self.proposal is None:
            raise ValueError("successful lineage requires one validated model result")
        return self


GuideLocalRef = Annotated[
    str,
    Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_-]*$"),
]
GuideContentText = Annotated[str, Field(min_length=1, max_length=2_000)]


ExactDungeonComponentId = Annotated[str, Field(min_length=1, max_length=200)]


class DungeonExplorationAffordanceApproval(WorkflowModel):
    """Trusted room-local feature selected as an environmental affordance."""

    affordance_id: ExactDungeonComponentId
    use: GuideContentText


class DungeonExplorationContextSelection(WorkflowModel):
    """Trusted IDs and policy used to build one exploration-only context."""

    room_id: ExactDungeonComponentId
    affordances: tuple[DungeonExplorationAffordanceApproval, ...] = Field(
        min_length=1, max_length=6
    )
    pacing_role: Literal[
        "discovery",
        "rising_tension",
        "resource_pressure",
        "transition",
        "respite",
    ]
    stakes: GuideContentText
    constraints: tuple[GuideContentText, ...] = Field(default=(), max_length=8)

    @model_validator(mode="after")
    def require_unique_affordance_approvals(
        self,
    ) -> DungeonExplorationContextSelection:
        affordance_ids = [item.affordance_id for item in self.affordances]
        if len(affordance_ids) != len(set(affordance_ids)):
            raise ValueError(
                "exploration context selection requires unique affordance IDs"
            )
        return self


class DungeonExplorationRoomContext(WorkflowModel):
    """Exact local geometry exposed to one post-layout exploration task."""

    room_id: ExactDungeonComponentId
    floor_id: ExactDungeonComponentId
    boundary: PolygonGeometry
    capacity: RoomCapacity
    encounter_slot_id: ExactDungeonComponentId


class DungeonExplorationAffordance(WorkflowModel):
    """One approved exact feature marker usable in the selected room."""

    affordance_id: ExactDungeonComponentId
    room_id: ExactDungeonComponentId
    floor_id: ExactDungeonComponentId
    position: GridPoint
    use: GuideContentText


class DungeonExplorationEnrichmentInput(WorkflowModel):
    """Narrow Workbench payload for exploration design after exact geometry exists."""

    schema_version: Literal["1.0.0"]
    package_id: ExactDungeonComponentId
    room: DungeonExplorationRoomContext
    affordances: tuple[DungeonExplorationAffordance, ...] = Field(
        min_length=1, max_length=6
    )
    pacing_role: Literal[
        "discovery",
        "rising_tension",
        "resource_pressure",
        "transition",
        "respite",
    ]
    stakes: GuideContentText
    constraints: tuple[GuideContentText, ...] = Field(default=(), max_length=8)

    @model_validator(mode="after")
    def require_unique_local_affordances(
        self,
    ) -> DungeonExplorationEnrichmentInput:
        affordance_ids = [item.affordance_id for item in self.affordances]
        if len(affordance_ids) != len(set(affordance_ids)):
            raise ValueError("exploration enrichment requires unique affordance IDs")
        if any(
            item.room_id != self.room.room_id or item.floor_id != self.room.floor_id
            for item in self.affordances
        ):
            raise ValueError(
                "exploration enrichment affordances must belong to the local room"
            )
        return self


class DungeonExplorationApproach(WorkflowModel):
    """One actionable use of approved room-local affordances."""

    affordance_ids: tuple[ExactDungeonComponentId, ...] = Field(
        min_length=1, max_length=4
    )
    action: GuideContentText
    adjudication: GuideContentText
    consequence: GuideContentText

    @model_validator(mode="after")
    def require_unique_affordance_ids(self) -> DungeonExplorationApproach:
        if len(self.affordance_ids) != len(set(self.affordance_ids)):
            raise ValueError("exploration approach requires unique affordance IDs")
        return self


class DungeonExplorationEnrichmentOutput(WorkflowModel):
    """Exploration-only proposal that cannot mutate package-owned structure."""

    schema_version: Literal["1.0.0"]
    package_id: ExactDungeonComponentId
    room_id: ExactDungeonComponentId
    encounter_slot_id: ExactDungeonComponentId
    observable_cues: tuple[GuideContentText, ...] = Field(min_length=2, max_length=6)
    approaches: tuple[DungeonExplorationApproach, ...] = Field(
        min_length=2, max_length=4
    )
    escalation: GuideContentText
    recovery: GuideContentText

    @model_validator(mode="after")
    def require_bounded_guide_projection(
        self,
    ) -> DungeonExplorationEnrichmentOutput:
        projected_fields = (
            " ".join(self.observable_cues),
            f"Escalation: {self.escalation} Recovery: {self.recovery}",
            *(
                f"{approach.adjudication} Consequence: {approach.consequence}"
                for approach in self.approaches
            ),
        )
        if any(len(value) > 2_000 for value in projected_fields):
            raise ValueError(
                "exploration enrichment exceeds bounded guide projection text"
            )
        return self


class DungeonExplorationEnrichmentIssue(WorkflowModel):
    """Body-free exact-ID mismatch that blocks exploration enrichment."""

    code: Literal[
        "exploration_enrichment.package_mismatch",
        "exploration_enrichment.room_mismatch",
        "exploration_enrichment.encounter_slot_mismatch",
        "exploration_enrichment.affordance_invalid",
    ]
    component_id: ExactDungeonComponentId
    message: str = Field(min_length=1, max_length=300)


class DungeonExplorationEnrichmentValidationResult(WorkflowModel):
    """Provider-free semantic validation of one exploration-only proposal."""

    schema_version: Literal["1.0.0"]
    accepted_output: DungeonExplorationEnrichmentOutput | None = None
    issues: tuple[DungeonExplorationEnrichmentIssue, ...] = ()

    @model_validator(mode="after")
    def require_acceptance_to_match_issues(
        self,
    ) -> DungeonExplorationEnrichmentValidationResult:
        if (self.accepted_output is not None) == bool(self.issues):
            raise ValueError(
                "accepted exploration enrichment must match semantic issues"
            )
        return self


class PromptedDungeonExplorationLineage(WorkflowModel):
    """Accepted exploration content retained with its authorized dungeon version."""

    model_run_id: UUID
    context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_run: ModelRunRecord
    output: DungeonExplorationEnrichmentOutput

    @model_validator(mode="after")
    def require_successful_matching_output(
        self,
    ) -> PromptedDungeonExplorationLineage:
        if self.model_run.status != "succeeded":
            raise ValueError("exploration lineage requires a successful model run")
        if self.model_run.output_payload != self.output.model_dump(mode="json"):
            raise ValueError("exploration lineage output must match the model run")
        return self


class DungeonFeatureInteractionContextSelection(WorkflowModel):
    """Trusted exact feature and policy for one post-layout interaction task."""

    room_id: ExactDungeonComponentId
    feature_id: ExactDungeonComponentId
    interaction_goal: GuideContentText
    stakes: GuideContentText
    constraints: tuple[GuideContentText, ...] = Field(default=(), max_length=8)


class DungeonFeatureInteractionRoomContext(WorkflowModel):
    """Exact local geometry exposed to one feature-interaction task."""

    room_id: ExactDungeonComponentId
    floor_id: ExactDungeonComponentId
    boundary: PolygonGeometry
    capacity: RoomCapacity


class DungeonFeatureInteractionFeature(WorkflowModel):
    """One exact guide feature joined to its package-owned marker geometry."""

    feature_id: ExactDungeonComponentId
    room_id: ExactDungeonComponentId
    floor_id: ExactDungeonComponentId
    position: GridPoint
    kind: FeatureIntentKind
    name: str = Field(min_length=1, max_length=200)
    description: GuideContentText


class DungeonFeatureInteractionEnrichmentInput(WorkflowModel):
    """Narrow feature payload built from an exact package and current guide."""

    schema_version: Literal["1.0.0"]
    package_id: ExactDungeonComponentId
    room: DungeonFeatureInteractionRoomContext
    feature: DungeonFeatureInteractionFeature
    interaction_goal: GuideContentText
    stakes: GuideContentText
    constraints: tuple[GuideContentText, ...] = Field(default=(), max_length=8)

    @model_validator(mode="after")
    def require_feature_in_local_room(
        self,
    ) -> DungeonFeatureInteractionEnrichmentInput:
        if (
            self.feature.room_id != self.room.room_id
            or self.feature.floor_id != self.room.floor_id
        ):
            raise ValueError(
                "feature interaction requires one feature in the exact local room"
            )
        return self


class DungeonFeatureInteractionAffordance(WorkflowModel):
    """One actionable use and consequence for the selected exact feature."""

    action: GuideContentText
    adjudication: GuideContentText
    consequence: GuideContentText


class DungeonFeatureInteractionEnrichmentOutput(WorkflowModel):
    """Feature-only proposal that cannot mutate structure or another task."""

    schema_version: Literal["1.0.0"]
    package_id: ExactDungeonComponentId
    room_id: ExactDungeonComponentId
    feature_id: ExactDungeonComponentId
    observable_setup: tuple[GuideContentText, ...] = Field(min_length=1, max_length=5)
    affordances: tuple[DungeonFeatureInteractionAffordance, ...] = Field(
        min_length=2, max_length=4
    )
    reset_or_retry: GuideContentText | None = None

    @model_validator(mode="after")
    def require_bounded_guide_projection(
        self,
    ) -> DungeonFeatureInteractionEnrichmentOutput:
        projected_fields = (
            " ".join(self.observable_setup),
            " ".join(
                f"{item.adjudication} Consequence: {item.consequence}"
                for item in self.affordances
            ),
            self.reset_or_retry or "",
        )
        if any(len(value) > 2_000 for value in projected_fields):
            raise ValueError(
                "feature interaction exceeds bounded guide projection text"
            )
        return self


class DungeonFeatureInteractionIssue(WorkflowModel):
    """Body-free exact-ID mismatch that blocks one feature interaction."""

    code: Literal[
        "feature_interaction.package_mismatch",
        "feature_interaction.room_mismatch",
        "feature_interaction.feature_mismatch",
    ]
    component_id: ExactDungeonComponentId
    message: str = Field(min_length=1, max_length=300)


class DungeonFeatureInteractionValidationResult(WorkflowModel):
    """Provider-free semantic validation for one feature-only proposal."""

    schema_version: Literal["1.0.0"]
    accepted_output: DungeonFeatureInteractionEnrichmentOutput | None = None
    issues: tuple[DungeonFeatureInteractionIssue, ...] = ()

    @model_validator(mode="after")
    def require_acceptance_to_match_issues(
        self,
    ) -> DungeonFeatureInteractionValidationResult:
        if (self.accepted_output is not None) == bool(self.issues):
            raise ValueError("accepted feature interaction must match semantic issues")
        return self


class PromptedDungeonFeatureInteractionLineage(WorkflowModel):
    """Accepted feature content retained with its authorized dungeon version."""

    model_run_id: UUID
    context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_run: ModelRunRecord
    output: DungeonFeatureInteractionEnrichmentOutput

    @model_validator(mode="after")
    def require_successful_matching_output(
        self,
    ) -> PromptedDungeonFeatureInteractionLineage:
        if self.model_run.status != "succeeded":
            raise ValueError(
                "feature interaction lineage requires a successful model run"
            )
        if self.model_run.output_payload != self.output.model_dump(mode="json"):
            raise ValueError(
                "feature interaction lineage output must match the model run"
            )
        return self


class DungeonTrapContextSelection(WorkflowModel):
    """Trusted exact trap and bounded policy for one post-layout trap task."""

    room_id: ExactDungeonComponentId
    trap_id: ExactDungeonComponentId
    stakes: GuideContentText
    constraints: tuple[GuideContentText, ...] = Field(default=(), max_length=8)


class DungeonTrapRoomContext(WorkflowModel):
    """Exact local geometry exposed to one trap-only task."""

    room_id: ExactDungeonComponentId
    floor_id: ExactDungeonComponentId
    boundary: PolygonGeometry
    capacity: RoomCapacity


class DungeonTrapMechanic(WorkflowModel):
    """Exact marker, current guide text, and code-owned trap arithmetic."""

    trap_id: ExactDungeonComponentId
    room_id: ExactDungeonComponentId
    floor_id: ExactDungeonComponentId
    position: GridPoint
    name: str = Field(min_length=1, max_length=200)
    current_warning: GuideContentText | None = None
    current_trigger: GuideContentText | None = None
    current_effect: GuideContentText | None = None
    current_detection: GuideContentText | None = None
    current_disable: GuideContentText | None = None
    current_consequences: tuple[GuideContentText, ...] = Field(default=(), max_length=4)
    current_reset_or_recovery: GuideContentText | None = None
    detection_difficulty: int = Field(ge=0)
    disable_difficulty: int = Field(ge=0)


class DungeonTrapEnrichmentInput(WorkflowModel):
    """Narrow trap payload built after exact geometry and mechanics exist."""

    schema_version: Literal["1.0.0"]
    package_id: ExactDungeonComponentId
    room: DungeonTrapRoomContext
    trap: DungeonTrapMechanic
    stakes: GuideContentText
    constraints: tuple[GuideContentText, ...] = Field(default=(), max_length=8)

    @model_validator(mode="after")
    def require_trap_in_local_room(self) -> DungeonTrapEnrichmentInput:
        if (
            self.trap.room_id != self.room.room_id
            or self.trap.floor_id != self.room.floor_id
        ):
            raise ValueError(
                "trap enrichment requires one trap in the exact local room"
            )
        return self


class DungeonTrapEnrichmentOutput(WorkflowModel):
    """Trap-only proposal with no model-authored arithmetic or structural fields."""

    schema_version: Literal["1.0.0"]
    package_id: ExactDungeonComponentId
    room_id: ExactDungeonComponentId
    trap_id: ExactDungeonComponentId
    observable_warning: GuideContentText
    trigger: GuideContentText
    effect_narration: GuideContentText
    detection_method: GuideContentText
    disable_operation: GuideContentText
    consequences: tuple[GuideContentText, ...] = Field(min_length=1, max_length=4)
    reset_or_recovery: GuideContentText | None = None

    @model_validator(mode="after")
    def require_bounded_guide_projection(self) -> DungeonTrapEnrichmentOutput:
        projected_fields = (
            self.observable_warning,
            self.trigger,
            self.effect_narration,
            self.detection_method,
            self.disable_operation,
            " ".join(self.consequences),
            self.reset_or_recovery or "",
        )
        if any(len(value) > 2_000 for value in projected_fields):
            raise ValueError("trap enrichment exceeds bounded guide projection text")
        if any(
            re.search(
                r"(?i)\b(?:DC|difficulty(?:\s+class)?)\s*[:=]?\s*\d+\b",
                value,
            )
            for value in projected_fields
        ):
            raise ValueError("trap enrichment cannot author numeric difficulty values")
        return self


class DungeonTrapIssue(WorkflowModel):
    """Body-free exact-ID mismatch that blocks accepting trap content."""

    code: Literal[
        "trap_enrichment.package_mismatch",
        "trap_enrichment.room_mismatch",
        "trap_enrichment.trap_mismatch",
    ]
    component_id: ExactDungeonComponentId
    message: str = Field(min_length=1, max_length=300)


class DungeonTrapValidationResult(WorkflowModel):
    """Provider-free semantic validation for one trap-only proposal."""

    schema_version: Literal["1.0.0"]
    accepted_output: DungeonTrapEnrichmentOutput | None = None
    issues: tuple[DungeonTrapIssue, ...] = ()

    @model_validator(mode="after")
    def require_acceptance_to_match_issues(self) -> DungeonTrapValidationResult:
        if (self.accepted_output is not None) == bool(self.issues):
            raise ValueError("accepted trap enrichment must match semantic issues")
        return self


class PromptedDungeonTrapLineage(WorkflowModel):
    """Accepted trap content retained with its authorized dungeon version."""

    model_run_id: UUID
    context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_run: ModelRunRecord
    output: DungeonTrapEnrichmentOutput

    @model_validator(mode="after")
    def require_successful_matching_output(self) -> PromptedDungeonTrapLineage:
        if self.model_run.status != "succeeded":
            raise ValueError("trap lineage requires a successful model run")
        if self.model_run.output_payload != self.output.model_dump(mode="json"):
            raise ValueError("trap lineage output must match the model run")
        return self


class DungeonObjectiveContextSelection(WorkflowModel):
    """Trusted exact objective, accepted mechanics, and bounded task policy."""

    room_id: ExactDungeonComponentId
    objective_id: ExactDungeonComponentId
    mechanic_ids: tuple[ExactDungeonComponentId, ...] = Field(default=(), max_length=8)
    stakes: GuideContentText
    constraints: tuple[GuideContentText, ...] = Field(default=(), max_length=8)

    @model_validator(mode="after")
    def require_unique_mechanic_ids(self) -> DungeonObjectiveContextSelection:
        if len(self.mechanic_ids) != len(set(self.mechanic_ids)):
            raise ValueError("objective context requires unique accepted mechanic IDs")
        return self


class DungeonObjectiveRoomContext(WorkflowModel):
    """Exact local geometry exposed to one objective-only task."""

    room_id: ExactDungeonComponentId
    floor_id: ExactDungeonComponentId
    boundary: PolygonGeometry
    capacity: RoomCapacity


class DungeonObjectiveCurrentResolution(WorkflowModel):
    """One already accepted objective resolution, if this entry is complete."""

    action: GuideContentText
    outcome: GuideContentText


class DungeonObjectiveTarget(WorkflowModel):
    """Exact objective marker joined to its current DM-guide entry."""

    objective_id: ExactDungeonComponentId
    room_id: ExactDungeonComponentId
    floor_id: ExactDungeonComponentId
    position: GridPoint
    kind: ObjectiveKind
    name: str = Field(min_length=1, max_length=200)
    current_situation: GuideContentText | None = None
    current_adjudication: GuideContentText | None = None
    current_resolutions: tuple[DungeonObjectiveCurrentResolution, ...] = Field(
        default=(), max_length=4
    )

    @model_validator(mode="after")
    def require_complete_current_content(self) -> DungeonObjectiveTarget:
        has_text = (
            self.current_situation is not None or self.current_adjudication is not None
        )
        if has_text != bool(self.current_resolutions):
            raise ValueError(
                "objective current content must be present as one complete set"
            )
        if has_text and (
            self.current_situation is None
            or self.current_adjudication is None
            or len(self.current_resolutions) < 2
        ):
            raise ValueError(
                "accepted objective content requires at least two resolutions"
            )
        return self


class DungeonObjectiveAcceptedMechanic(WorkflowModel):
    """Bounded summary copied only from one already accepted guide mechanic."""

    mechanic_id: ExactDungeonComponentId
    room_id: ExactDungeonComponentId
    kind: Literal["puzzle", "exploration", "feature", "trap"]
    name: str = Field(min_length=1, max_length=200)
    observable_summary: GuideContentText
    resolution_summary: GuideContentText
    outcome_summaries: tuple[GuideContentText, ...] = Field(min_length=1, max_length=5)


class DungeonObjectiveEnrichmentInput(WorkflowModel):
    """Narrow objective payload built after selected mechanics are accepted."""

    schema_version: Literal["1.0.0"]
    package_id: ExactDungeonComponentId
    room: DungeonObjectiveRoomContext
    objective: DungeonObjectiveTarget
    accepted_mechanics: tuple[DungeonObjectiveAcceptedMechanic, ...] = Field(
        default=(), max_length=8
    )
    stakes: GuideContentText
    constraints: tuple[GuideContentText, ...] = Field(default=(), max_length=8)

    @model_validator(mode="after")
    def require_exact_local_objective_and_unique_mechanics(
        self,
    ) -> DungeonObjectiveEnrichmentInput:
        if (
            self.objective.room_id != self.room.room_id
            or self.objective.floor_id != self.room.floor_id
        ):
            raise ValueError(
                "objective enrichment requires one objective in the exact room"
            )
        mechanic_ids = [item.mechanic_id for item in self.accepted_mechanics]
        if len(mechanic_ids) != len(set(mechanic_ids)):
            raise ValueError("objective enrichment requires unique accepted mechanics")
        return self


class DungeonObjectiveResolution(WorkflowModel):
    """One credible objective resolution, optionally grounded in accepted mechanics."""

    mechanic_ids: tuple[ExactDungeonComponentId, ...] = Field(default=(), max_length=4)
    action: GuideContentText
    outcome: GuideContentText

    @model_validator(mode="after")
    def require_unique_mechanic_ids(self) -> DungeonObjectiveResolution:
        if len(self.mechanic_ids) != len(set(self.mechanic_ids)):
            raise ValueError("objective resolution requires unique mechanic IDs")
        return self


class DungeonObjectiveEnrichmentOutput(WorkflowModel):
    """Objective-only proposal that cannot rename or structurally mutate its target."""

    schema_version: Literal["1.0.0"]
    package_id: ExactDungeonComponentId
    room_id: ExactDungeonComponentId
    objective_id: ExactDungeonComponentId
    observable_goal: GuideContentText
    resolution_guidance: GuideContentText
    resolutions: tuple[DungeonObjectiveResolution, ...] = Field(
        min_length=2, max_length=4
    )
    setback_or_aftermath: GuideContentText

    @model_validator(mode="after")
    def require_bounded_guide_projection(self) -> DungeonObjectiveEnrichmentOutput:
        adjudication = (
            f"{self.resolution_guidance} "
            f"Setback or aftermath: {self.setback_or_aftermath}"
        )
        if len(adjudication) > 2_000:
            raise ValueError(
                "objective enrichment exceeds bounded guide projection text"
            )
        return self


class DungeonObjectiveIssue(WorkflowModel):
    """Body-free exact-ID mismatch that blocks accepting objective content."""

    code: Literal[
        "objective_enrichment.package_mismatch",
        "objective_enrichment.room_mismatch",
        "objective_enrichment.objective_mismatch",
        "objective_enrichment.mechanic_invalid",
    ]
    component_id: ExactDungeonComponentId
    message: str = Field(min_length=1, max_length=300)


class DungeonObjectiveValidationResult(WorkflowModel):
    """Provider-free semantic validation for one objective-only proposal."""

    schema_version: Literal["1.0.0"]
    accepted_output: DungeonObjectiveEnrichmentOutput | None = None
    issues: tuple[DungeonObjectiveIssue, ...] = ()

    @model_validator(mode="after")
    def require_acceptance_to_match_issues(self) -> DungeonObjectiveValidationResult:
        if (self.accepted_output is not None) == bool(self.issues):
            raise ValueError("accepted objective enrichment must match semantic issues")
        return self


class PromptedDungeonObjectiveLineage(WorkflowModel):
    """Accepted objective content retained with its authorized dungeon version."""

    model_run_id: UUID
    context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_run: ModelRunRecord
    output: DungeonObjectiveEnrichmentOutput

    @model_validator(mode="after")
    def require_successful_matching_output(self) -> PromptedDungeonObjectiveLineage:
        if self.model_run.status != "succeeded":
            raise ValueError("objective lineage requires a successful model run")
        if self.model_run.output_payload != self.output.model_dump(mode="json"):
            raise ValueError("objective lineage output must match the model run")
        return self


class DungeonPuzzleClueApproval(WorkflowModel):
    """Server-approved exact location selected for one puzzle context."""

    location_id: ExactDungeonComponentId
    purpose: GuideContentText


class DungeonPuzzleObjectiveApproval(WorkflowModel):
    """Server-approved exact objective relationship for one puzzle task."""

    objective_id: ExactDungeonComponentId
    relationship: Literal["guards_access", "reveals_access", "supports_objective"]


class DungeonPuzzleDependencyApproval(WorkflowModel):
    """Server-approved exact gate dependency relationship for one puzzle task."""

    gate_id: ExactDungeonComponentId
    dependency_id: ExactDungeonComponentId
    relationship: Literal["controls_gate", "reveals_dependency", "uses_dependency"]


class DungeonPuzzleContextSelection(WorkflowModel):
    """Trusted IDs and policy text used to construct a model-visible context."""

    room_id: ExactDungeonComponentId
    clue_locations: tuple[DungeonPuzzleClueApproval, ...] = Field(
        default=(), max_length=6
    )
    objective: DungeonPuzzleObjectiveApproval | None = None
    dependency: DungeonPuzzleDependencyApproval | None = None
    tone: tuple[GuideContentText, ...] = Field(default=(), max_length=4)
    constraints: tuple[GuideContentText, ...] = Field(default=(), max_length=8)

    @model_validator(mode="after")
    def require_unique_clue_approvals(self) -> DungeonPuzzleContextSelection:
        location_ids = [item.location_id for item in self.clue_locations]
        if len(location_ids) != len(set(location_ids)):
            raise ValueError(
                "puzzle context selection requires unique clue location IDs"
            )
        return self


class DungeonPuzzleRoomContext(WorkflowModel):
    """Exact local geometry exposed to one post-layout puzzle task."""

    room_id: ExactDungeonComponentId
    floor_id: ExactDungeonComponentId
    boundary: PolygonGeometry
    capacity: RoomCapacity
    connection_ids: tuple[ExactDungeonComponentId, ...] = Field(max_length=8)
    feature_ids: tuple[ExactDungeonComponentId, ...] = Field(max_length=8)


class DungeonPuzzleClueLocation(WorkflowModel):
    """One server-approved exact location where puzzle evidence may appear."""

    location_id: ExactDungeonComponentId
    room_id: ExactDungeonComponentId
    floor_id: ExactDungeonComponentId
    purpose: GuideContentText


class DungeonPuzzleObjectiveRelationship(WorkflowModel):
    """Approved relationship between the puzzle slot and an exact objective."""

    objective_id: ExactDungeonComponentId
    objective_room_id: ExactDungeonComponentId
    relationship: Literal["guards_access", "reveals_access", "supports_objective"]


class DungeonPuzzleDependencyRelationship(WorkflowModel):
    """Approved relationship between the puzzle slot and an exact gate dependency."""

    gate_id: ExactDungeonComponentId
    dependency_id: ExactDungeonComponentId
    relationship: Literal["controls_gate", "reveals_dependency", "uses_dependency"]


class DungeonPuzzleEnrichmentInput(WorkflowModel):
    """Narrow Workbench payload for puzzle design after exact geometry exists."""

    schema_version: Literal["1.0.0"]
    package_id: ExactDungeonComponentId
    room: DungeonPuzzleRoomContext
    objective_relationship: DungeonPuzzleObjectiveRelationship | None = None
    dependency_relationship: DungeonPuzzleDependencyRelationship | None = None
    clue_locations: tuple[DungeonPuzzleClueLocation, ...] = Field(
        default=(), max_length=6
    )
    tone: tuple[GuideContentText, ...] = Field(default=(), max_length=4)
    constraints: tuple[GuideContentText, ...] = Field(default=(), max_length=8)

    @model_validator(mode="after")
    def require_unique_exact_context_ids(self) -> DungeonPuzzleEnrichmentInput:
        for label, values in (
            ("connection", self.room.connection_ids),
            ("feature", self.room.feature_ids),
            ("clue location", tuple(item.location_id for item in self.clue_locations)),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"puzzle enrichment requires unique {label} IDs")
        return self


class DungeonPuzzleClue(WorkflowModel):
    """One ordered observable clue and its intended inference."""

    location_id: ExactDungeonComponentId
    observation: GuideContentText
    inference: GuideContentText


class DungeonPuzzleAlternateHandling(WorkflowModel):
    """One reasonable non-primary approach and deterministic adjudication guidance."""

    approach: GuideContentText
    adjudication: GuideContentText


class DungeonPuzzleEnrichmentOutput(WorkflowModel):
    """Puzzle-only proposal that cannot mutate package structure or arithmetic."""

    schema_version: Literal["1.0.0"]
    package_id: ExactDungeonComponentId
    room_id: ExactDungeonComponentId
    name: str = Field(min_length=1, max_length=200)
    observable_elements: tuple[GuideContentText, ...] = Field(
        min_length=2, max_length=6
    )
    solution_steps: tuple[GuideContentText, ...] = Field(min_length=1, max_length=6)
    clue_path: tuple[DungeonPuzzleClue, ...] = Field(min_length=1, max_length=6)
    hints: tuple[GuideContentText, ...] = Field(default=(), max_length=3)
    alternate_handling: tuple[DungeonPuzzleAlternateHandling, ...] = Field(
        min_length=1, max_length=3
    )
    success_outcome: GuideContentText
    failure_consequence: GuideContentText
    reset_or_retry: GuideContentText | None = None

    @model_validator(mode="after")
    def require_unique_clues_and_bounded_guide_projection(
        self,
    ) -> DungeonPuzzleEnrichmentOutput:
        location_ids = [item.location_id for item in self.clue_path]
        if len(location_ids) != len(set(location_ids)):
            raise ValueError("puzzle enrichment clue path requires unique location IDs")
        projected_fields = (
            self.guide_situation(),
            self.guide_solution(),
            self.guide_adjudication(),
        )
        if any(len(value) > 2_000 for value in projected_fields):
            raise ValueError("puzzle enrichment exceeds bounded guide projection text")
        return self

    def guide_situation(self) -> str:
        """Deterministically group the complete observable puzzle setup."""

        return " ".join(self.observable_elements)

    def guide_solution(self) -> str:
        """Deterministically group the ordered intended solution."""

        return " ".join(
            f"{index}. {step}"
            for index, step in enumerate(self.solution_steps, start=1)
        )

    def guide_adjudication(self) -> str:
        """Deterministically group clues, hints, failure, and retry behavior."""

        sections = [
            "Clue path: "
            + " ".join(
                f"{clue.observation} Intended inference: {clue.inference}"
                for clue in self.clue_path
            )
        ]
        if self.hints:
            sections.append("Hints: " + " ".join(self.hints))
        sections.append(f"Failure: {self.failure_consequence}")
        if self.reset_or_retry is not None:
            sections.append(f"Reset or retry: {self.reset_or_retry}")
        return " ".join(sections)


class DungeonPuzzleEnrichmentIssue(WorkflowModel):
    """Body-free exact-ID mismatch that blocks accepting puzzle enrichment."""

    code: Literal[
        "puzzle_enrichment.package_mismatch",
        "puzzle_enrichment.room_mismatch",
        "puzzle_enrichment.clue_location_invalid",
    ]
    component_id: ExactDungeonComponentId
    message: str = Field(min_length=1, max_length=300)


class DungeonPuzzleEnrichmentValidationResult(WorkflowModel):
    """Provider-free semantic validation of one puzzle-only proposal."""

    schema_version: Literal["1.0.0"]
    accepted_output: DungeonPuzzleEnrichmentOutput | None = None
    issues: tuple[DungeonPuzzleEnrichmentIssue, ...] = ()

    @model_validator(mode="after")
    def require_acceptance_to_match_issues(
        self,
    ) -> DungeonPuzzleEnrichmentValidationResult:
        if (self.accepted_output is not None) == bool(self.issues):
            raise ValueError("accepted puzzle enrichment must match semantic issues")
        return self


class PromptedDungeonPuzzleLineage(WorkflowModel):
    """Accepted puzzle content retained with its authorized dungeon version."""

    model_run_id: UUID
    context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_run: ModelRunRecord
    output: DungeonPuzzleEnrichmentOutput

    @model_validator(mode="after")
    def require_successful_matching_output(self) -> PromptedDungeonPuzzleLineage:
        if self.model_run.status != "succeeded":
            raise ValueError("puzzle lineage requires a successful model run")
        if self.model_run.output_payload != self.output.model_dump(mode="json"):
            raise ValueError("puzzle lineage output must match the model run")
        return self


class DungeonGuidePlayerChoice(WorkflowModel):
    """One runnable player approach and its table-facing result."""

    action: GuideContentText
    outcome: GuideContentText


class DungeonGuideRunnableContent(WorkflowModel):
    """Validated table-facing play content after target resolution."""

    situation: GuideContentText
    adjudication: GuideContentText
    player_choices: tuple[DungeonGuidePlayerChoice, ...] = Field(
        min_length=2, max_length=4
    )


class _DungeonGuideContentEntry(WorkflowModel):
    """Common bounded play content before exact package IDs exist."""

    ref: GuideLocalRef
    room_ref: GuideLocalRef
    situation: GuideContentText
    adjudication: GuideContentText
    player_choices: tuple[DungeonGuidePlayerChoice, ...] = Field(
        min_length=2, max_length=4
    )


class DungeonGuideGateContent(_DungeonGuideContentEntry):
    """Runnable discovery and use of one gate dependency."""

    kind: Literal["gate_dependency"]
    gate_ref: GuideLocalRef
    dependency_name: str = Field(min_length=1, max_length=200)
    discovery: GuideContentText


class DungeonGuideEncounterContent(_DungeonGuideContentEntry):
    """Runnable content for a reserved encounter slot, not an encounter package."""

    kind: Literal["encounter"]
    encounter_intent: EncounterSlotIntent


class DungeonGuidePuzzleContent(_DungeonGuideContentEntry):
    """Runnable room puzzle with an explicit solution."""

    kind: Literal["puzzle"]
    name: str = Field(min_length=1, max_length=200)
    solution: GuideContentText


class DungeonGuideFeatureContent(_DungeonGuideContentEntry):
    """Runnable interaction with one named room feature."""

    kind: Literal["feature"]
    feature_name: str = Field(min_length=1, max_length=200)


class DungeonGuideObjectiveContent(_DungeonGuideContentEntry):
    """Runnable resolution choices for the named final objective."""

    kind: Literal["objective"]
    objective_name: str = Field(min_length=1, max_length=200)


DungeonGuideContentEntry = Annotated[
    DungeonGuideGateContent
    | DungeonGuideEncounterContent
    | DungeonGuidePuzzleContent
    | DungeonGuideFeatureContent
    | DungeonGuideObjectiveContent,
    Field(discriminator="kind"),
]


class DungeonGuideRoomNarrative(WorkflowModel):
    """Sensory arrival material for one plan-local room."""

    room_ref: GuideLocalRef
    read_aloud: GuideContentText
    sensory_details: tuple[GuideContentText, ...] = Field(min_length=2, max_length=4)


class DungeonGuideContentPlan(WorkflowModel):
    """Workbench-owned runnable prose keyed to ``DungeonPlan`` local refs.

    The server validates and projects this content onto exact package IDs only after
    geometry exists. It never enters topology, demand, layout, or rendering decisions.
    Missing or invalid content leaves a structurally valid draft with truthful review
    blockers instead of causing deterministic regeneration.
    """

    schema_version: Literal["1.0.0"]
    room_narratives: tuple[DungeonGuideRoomNarrative, ...] = Field(
        min_length=1, max_length=8
    )
    entries: tuple[DungeonGuideContentEntry, ...] = Field(min_length=1, max_length=16)

    @model_validator(mode="after")
    def require_unique_refs_and_targets(self) -> DungeonGuideContentPlan:
        room_refs = [item.room_ref for item in self.room_narratives]
        if len(room_refs) != len(set(room_refs)):
            raise ValueError("guide room narratives require unique room refs")
        refs = [entry.ref for entry in self.entries]
        if len(refs) != len(set(refs)):
            raise ValueError("guide content entries require unique local refs")
        targets = [(entry.kind, entry.room_ref) for entry in self.entries]
        if len(targets) != len(set(targets)):
            raise ValueError(
                "guide content permits at most one entry of each kind per room"
            )
        return self


class DungeonGuideContentIssue(WorkflowModel):
    """Body-free semantic failure that cannot invalidate structural generation."""

    code: Literal[
        "guide_content.required_missing",
        "guide_content.target_invalid",
    ]
    kind: Literal[
        "room",
        "gate_dependency",
        "encounter",
        "puzzle",
        "feature",
        "objective",
    ]
    entry_ref: GuideLocalRef | None = None
    room_ref: GuideLocalRef
    target_ref: GuideLocalRef | None = None
    message: str = Field(min_length=1, max_length=300)


class DungeonGuideContentValidationResult(WorkflowModel):
    """Accepted guide entries plus independently blocking semantic issues."""

    schema_version: Literal["1.0.0"]
    accepted_room_narratives: tuple[DungeonGuideRoomNarrative, ...]
    accepted_entries: tuple[DungeonGuideContentEntry, ...]
    issues: tuple[DungeonGuideContentIssue, ...]


class DungeonRoomDmNote(WorkflowModel):
    """DM-facing prose linked to one stable generated room."""

    room_id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=4_000)


class DungeonDmNotes(WorkflowModel):
    """Readable preparation material kept outside the pure dungeon package."""

    source_prompt: str | None = Field(default=None, min_length=1, max_length=4_000)
    room_notes: tuple[DungeonRoomDmNote, ...] = ()


class DungeonGuideMapReference(WorkflowModel):
    """One human-facing reference into the exact shared DM map-key projection."""

    component_id: str = Field(min_length=1, max_length=200)
    floor_id: str = Field(min_length=1, max_length=200)
    token: str = Field(min_length=1, max_length=32)


class DungeonGuideRoom(WorkflowModel):
    room_id: str = Field(min_length=1, max_length=200)
    floor_id: str = Field(min_length=1, max_length=200)
    map_reference: DungeonGuideMapReference
    presentation_number: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=200)
    role: RoomRole
    tags: tuple[str, ...] = ()
    read_aloud: str | None = Field(default=None, min_length=1, max_length=2_000)
    sensory_details: tuple[str, ...] = Field(default=(), max_length=4)
    preparation_note: str | None = Field(default=None, min_length=1, max_length=4_000)
    encounter_slot: EncounterSlotIntent | None = None
    encounter_slot_id: str | None = Field(default=None, min_length=1, max_length=200)
    encounter_content: DungeonGuideRunnableContent | None = None

    @model_validator(mode="after")
    def require_encounter_slot_id_with_intent(self) -> DungeonGuideRoom:
        if (self.encounter_slot is None) != (self.encounter_slot_id is None):
            raise ValueError(
                "encounter slot intent and stable ID must be present together"
            )
        if self.encounter_content is not None and self.encounter_slot is None:
            raise ValueError("encounter content requires a reserved encounter slot")
        if self.read_aloud is None and self.sensory_details:
            raise ValueError("sensory details require room read-aloud material")
        if self.read_aloud is not None and len(self.sensory_details) < 2:
            raise ValueError(
                "room read-aloud material requires at least two sensory details"
            )
        return self


class DungeonGuideConnection(WorkflowModel):
    """DM-only mechanics for one exact door, hatch, or transition."""

    component_id: str = Field(min_length=1, max_length=200)
    connection_id: str = Field(min_length=1, max_length=200)
    map_reference: DungeonGuideMapReference | None = None
    passage: str = Field(min_length=1, max_length=32)
    from_room_id: str = Field(min_length=1, max_length=200)
    to_room_id: str = Field(min_length=1, max_length=200)
    endpoint: VerticalEndpointSide | None = None
    endpoint_kind: EndpointDoorKind | None = None
    concealed: bool = False
    discovery_difficulty: int | None = Field(default=None, ge=0)
    gate_id: str | None = Field(default=None, min_length=1, max_length=200)
    gate_kind: BarrierIntent = BarrierIntent.NONE
    unlock_difficulty: int | None = Field(default=None, ge=0)
    trap_id: str | None = Field(default=None, min_length=1, max_length=200)
    trap_trigger: str | None = Field(default=None, min_length=1, max_length=4_000)
    trap_effect: str | None = Field(default=None, min_length=1, max_length=4_000)
    disable_difficulty: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def require_complete_mechanics(self) -> DungeonGuideConnection:
        if (self.endpoint is None) != (self.endpoint_kind is None):
            raise ValueError("endpoint and endpoint_kind must be present together")
        if self.concealed != (self.discovery_difficulty is not None):
            raise ValueError("concealment requires exactly one discovery difficulty")
        if (self.gate_id is None) != (self.gate_kind is BarrierIntent.NONE):
            raise ValueError("gate ID and kind must be present together")
        if (self.gate_id is not None) != (self.unlock_difficulty is not None):
            raise ValueError("gates require exactly one unlock difficulty")
        trap_fields = (
            self.trap_trigger,
            self.trap_effect,
            self.disable_difficulty,
        )
        if self.trap_id is not None and self.disable_difficulty is None:
            raise ValueError("traps require one disable difficulty")
        if self.trap_id is None and any(value is not None for value in trap_fields):
            raise ValueError("trap details require a trap ID")
        return self


class DungeonGuideDependency(WorkflowModel):
    dependency_id: str = Field(min_length=1, max_length=200)
    target_gate_id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    kind: str = Field(min_length=1, max_length=32)
    room_id: str = Field(min_length=1, max_length=200)
    room_map_reference: DungeonGuideMapReference
    discovery: str | None = Field(default=None, min_length=1, max_length=2_000)
    content: DungeonGuideRunnableContent | None = None


class DungeonGuideTrap(WorkflowModel):
    marker_id: str = Field(min_length=1, max_length=200)
    room_id: str = Field(min_length=1, max_length=200)
    map_reference: DungeonGuideMapReference
    name: str = Field(min_length=1, max_length=200)
    warning: str | None = Field(default=None, min_length=1, max_length=2_000)
    trigger: str | None = Field(default=None, min_length=1, max_length=4_000)
    effect: str | None = Field(default=None, min_length=1, max_length=4_000)
    detection: str | None = Field(default=None, min_length=1, max_length=4_000)
    disable: str | None = Field(default=None, min_length=1, max_length=4_000)
    consequences: tuple[GuideContentText, ...] = Field(default=(), max_length=4)
    reset_or_recovery: str | None = Field(default=None, min_length=1, max_length=2_000)
    detection_difficulty: int = Field(ge=0)
    disable_difficulty: int = Field(ge=0)


class DungeonGuidePuzzle(WorkflowModel):
    content_ref: GuideLocalRef
    room_id: str = Field(min_length=1, max_length=200)
    map_reference: DungeonGuideMapReference
    name: str = Field(min_length=1, max_length=200)
    solution: str = Field(min_length=1, max_length=2_000)
    content: DungeonGuideRunnableContent


class DungeonGuideObjective(WorkflowModel):
    marker_id: str = Field(min_length=1, max_length=200)
    room_id: str = Field(min_length=1, max_length=200)
    map_reference: DungeonGuideMapReference
    kind: ObjectiveKind
    name: str = Field(min_length=1, max_length=200)
    content: DungeonGuideRunnableContent | None = None


class DungeonGuideFeature(WorkflowModel):
    marker_id: str = Field(min_length=1, max_length=200)
    room_id: str = Field(min_length=1, max_length=200)
    map_reference: DungeonGuideMapReference
    kind: FeatureIntentKind
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=4_000)
    content: DungeonGuideRunnableContent | None = None


class DungeonPreparationReadinessDiagnostic(WorkflowModel):
    """One deterministic reason a generated guide must remain a draft."""

    code: Literal[
        "dungeon_preparation.lock_dependency_missing",
        "dungeon_preparation.trap_effect_unknown",
        "dungeon_preparation.trap_method_unknown",
        "dungeon_preparation.puzzle_solution_unknown",
        "dungeon_preparation.guide_content_missing",
        "dungeon_preparation.guide_content_invalid",
    ]
    component_id: str = Field(min_length=1, max_length=200)
    map_reference: DungeonGuideMapReference | None = None
    message: str = Field(min_length=1, max_length=300)


class DungeonPreparationReadiness(WorkflowModel):
    """Versioned DM-only approval readiness derived from an exact DM guide."""

    schema_version: Literal["1.0.0"]
    ready: bool
    diagnostics: tuple[DungeonPreparationReadinessDiagnostic, ...] = ()

    @model_validator(mode="after")
    def require_ready_to_match_diagnostics(self) -> DungeonPreparationReadiness:
        if self.ready != (not self.diagnostics):
            raise ValueError("preparation readiness must match its diagnostics")
        return self


class DungeonDmGuide(WorkflowModel):
    """Versioned Workbench-owned prose keyed to pure package geometry/markers."""

    schema_version: Literal["1.0.0"]
    title: str = Field(min_length=1, max_length=200)
    premise: str = Field(min_length=1, max_length=4_000)
    map_callouts: tuple[MapCallout, ...]
    rooms: tuple[DungeonGuideRoom, ...]
    connections: tuple[DungeonGuideConnection, ...]
    dependencies: tuple[DungeonGuideDependency, ...]
    traps: tuple[DungeonGuideTrap, ...]
    puzzles: tuple[DungeonGuidePuzzle, ...]
    objectives: tuple[DungeonGuideObjective, ...]
    features: tuple[DungeonGuideFeature, ...]
    content_issues: tuple[DungeonGuideContentIssue, ...] = ()

    @model_validator(mode="after")
    def require_unique_entries_and_resolved_callouts(self) -> DungeonDmGuide:
        presentation_numbers = [item.presentation_number for item in self.rooms]
        if presentation_numbers != list(range(1, len(self.rooms) + 1)):
            raise ValueError(
                "DM guide rooms require entry-first sequential presentation numbers"
            )
        ids = [
            *(item.room_id for item in self.rooms),
            *(item.component_id for item in self.connections),
            *(item.marker_id for item in self.traps),
            *(f"guide_puzzle:{item.content_ref}" for item in self.puzzles),
            *(item.marker_id for item in self.objectives),
            *(item.marker_id for item in self.features),
        ]
        if len(ids) != len(set(ids)):
            raise ValueError("DM guide entries require unique stable IDs")
        callouts = {
            (item.component_id, item.floor_id, item.token) for item in self.map_callouts
        }
        entries: tuple[
            DungeonGuideRoom
            | DungeonGuideConnection
            | DungeonGuideTrap
            | DungeonGuidePuzzle
            | DungeonGuideObjective
            | DungeonGuideFeature,
            ...,
        ] = (
            *self.rooms,
            *self.connections,
            *self.traps,
            *self.puzzles,
            *self.objectives,
            *self.features,
        )
        for entry in entries:
            reference = entry.map_reference
            if (
                reference is not None
                and (
                    reference.component_id,
                    reference.floor_id,
                    reference.token,
                )
                not in callouts
            ):
                raise ValueError("DM guide entry references an unknown map callout")
        return self


class DungeonStudioSpecification(WorkflowModel):
    """Immutable persisted input plus exact deterministic output and lineage."""

    schema_version: Literal["1.0.0"]
    layout_request: LayoutRequest
    package: DungeonPackage
    dm_notes: DungeonDmNotes = DungeonDmNotes()
    dm_guide: DungeonDmGuide | None = None
    preparation_readiness: DungeonPreparationReadiness | None = None
    model_lineage: tuple[PromptedDungeonModelLineage, ...] = ()
    puzzle_model_lineage: tuple[PromptedDungeonPuzzleLineage, ...] = ()
    exploration_model_lineage: tuple[PromptedDungeonExplorationLineage, ...] = ()
    feature_interaction_model_lineage: tuple[
        PromptedDungeonFeatureInteractionLineage, ...
    ] = ()
    trap_model_lineage: tuple[PromptedDungeonTrapLineage, ...] = ()
    objective_model_lineage: tuple[PromptedDungeonObjectiveLineage, ...] = ()


class CreateDungeonWorkflow(WorkflowModel):
    campaign_id: UUID
    title: str = Field(min_length=1, max_length=200)
    layout_request: LayoutRequest
    created_by: str = Field(min_length=1, max_length=200)


class DungeonProposalAbstention(WorkflowModel):
    """Safe bounded reason for declining an alpha V1 creative design."""

    kind: Literal["insufficient_creative_direction", "conflicting_direction"]


class DungeonGenerationProposal(WorkflowModel):
    """Workbench-owned structural submission around compact creative intent."""

    # Keep the design/abstention XOR visible in the exact schema sent to the
    # gateway; the runtime validator remains authoritative fallback.
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=False,
        json_schema_extra={
            "oneOf": [
                {
                    "required": ["plan"],
                    "properties": {"abstention": {"type": "null"}},
                },
                {
                    "required": ["abstention"],
                    "properties": {"plan": {"type": "null"}},
                },
            ]
        },
    )

    proposal_version: Literal["1"]
    plan: DungeonPlan | None = None
    intent_summary: str | None = Field(default=None, min_length=1, max_length=500)
    requested_constraints: tuple[str, ...] = Field(default=(), max_length=16)
    citation_ids: tuple[str, ...] = Field(default=(), max_length=32)
    official_rule_ids: tuple[str, ...] = Field(default=(), max_length=32)
    unknowns: tuple[str, ...] = Field(default=(), max_length=16)
    conflicts: tuple[str, ...] = Field(default=(), max_length=16)
    abstention: DungeonProposalAbstention | None = None

    @model_validator(mode="before")
    @classmethod
    def decode_pure_plan(cls, value: object) -> object:
        if not isinstance(value, dict) or isinstance(value.get("plan"), DungeonPlan):
            return value
        document = dict(value)
        plan = document.get("plan")
        if isinstance(plan, dict):
            import json

            document["plan"] = DungeonPlan.model_validate_json(json.dumps(plan))
        for name in (
            "requested_constraints",
            "citation_ids",
            "official_rule_ids",
            "unknowns",
            "conflicts",
        ):
            if isinstance(document.get(name), list):
                document[name] = tuple(document[name])
        return document

    @model_validator(mode="after")
    def require_plan_or_safe_abstention(self) -> DungeonGenerationProposal:
        if (self.plan is None) == (self.abstention is None):
            raise ValueError("proposal requires exactly one of plan or abstention")
        if self.abstention is not None and self.intent_summary is not None:
            raise ValueError("abstention cannot include an intent summary")
        return self


class PromptDungeonWorkflow(WorkflowModel):
    """DM request for standalone model-assisted dungeon generation."""

    campaign_id: UUID
    title: str | None = Field(default=None, min_length=1, max_length=200)
    prompt: str = Field(min_length=1, max_length=4_000)
    seed: int
    created_by: str = Field(min_length=1, max_length=200)
    scope: TaskScope
    requested_constraints: tuple[str, ...] = ()

    @model_validator(mode="after")
    def require_standalone_scope(self) -> PromptDungeonWorkflow:
        if self.scope.task_type is not TaskType.STANDALONE_DUNGEON:
            raise ValueError(
                "prompted dungeon workflow requires standalone_dungeon scope"
            )
        if self.scope.grounding_enabled:
            raise ValueError(
                "standalone prompted dungeon workflow cannot use grounding"
            )
        return self


class CreatePromptedDungeonWorkflow(WorkflowModel):
    """Validated model intent ready for deterministic generation and persistence."""

    campaign_id: UUID
    title: str = Field(min_length=1, max_length=200)
    layout_request: LayoutRequest
    created_by: str = Field(min_length=1, max_length=200)
    context: GenerationContextPin
    model_task_profile_id: UUID
    model_lineage: tuple[PromptedDungeonModelLineage, ...] = Field(min_length=1)
    tool_runs: tuple[ToolRunPin, ...] = ()
    source_prompt: str = Field(min_length=1, max_length=4_000)


class PromptDungeonExplorationWorkflow(WorkflowModel):
    """DM request for one exact-room exploration enrichment child version."""

    campaign_id: UUID
    artifact_id: UUID
    parent_version_id: UUID
    selection: DungeonExplorationContextSelection
    created_by: str = Field(min_length=1, max_length=200)


class CreatePromptedDungeonExplorationWorkflow(WorkflowModel):
    """Accepted exploration result ready for deterministic child publication."""

    campaign_id: UUID
    artifact_id: UUID
    parent_version_id: UUID
    context: DungeonExplorationEnrichmentInput
    validation: DungeonExplorationEnrichmentValidationResult
    model_task_profile_id: UUID
    model_lineage: PromptedDungeonExplorationLineage
    tool_runs: tuple[ToolRunPin, ...] = ()
    created_by: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def require_matching_accepted_lineage(
        self,
    ) -> CreatePromptedDungeonExplorationWorkflow:
        if self.validation.accepted_output != self.model_lineage.output:
            raise ValueError(
                "exploration publication requires matching accepted lineage"
            )
        context_hash = canonical_json_sha256(self.context.model_dump(mode="json"))
        if self.model_lineage.context_sha256 != context_hash:
            raise ValueError(
                "exploration publication requires matching context lineage"
            )
        return self


class PromptDungeonFeatureInteractionWorkflow(WorkflowModel):
    """DM request for one exact-feature interaction enrichment child version."""

    campaign_id: UUID
    artifact_id: UUID
    parent_version_id: UUID
    selection: DungeonFeatureInteractionContextSelection
    created_by: str = Field(min_length=1, max_length=200)


class CreatePromptedDungeonFeatureInteractionWorkflow(WorkflowModel):
    """Accepted feature interaction ready for deterministic child publication."""

    campaign_id: UUID
    artifact_id: UUID
    parent_version_id: UUID
    context: DungeonFeatureInteractionEnrichmentInput
    validation: DungeonFeatureInteractionValidationResult
    model_task_profile_id: UUID
    model_lineage: PromptedDungeonFeatureInteractionLineage
    tool_runs: tuple[ToolRunPin, ...] = ()
    created_by: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def require_matching_accepted_lineage(
        self,
    ) -> CreatePromptedDungeonFeatureInteractionWorkflow:
        if self.validation.accepted_output != self.model_lineage.output:
            raise ValueError(
                "feature interaction publication requires matching accepted lineage"
            )
        context_hash = canonical_json_sha256(self.context.model_dump(mode="json"))
        if self.model_lineage.context_sha256 != context_hash:
            raise ValueError(
                "feature interaction publication requires matching context lineage"
            )
        return self


class PromptDungeonTrapWorkflow(WorkflowModel):
    """DM request for one exact-trap enrichment child version."""

    campaign_id: UUID
    artifact_id: UUID
    parent_version_id: UUID
    selection: DungeonTrapContextSelection
    created_by: str = Field(min_length=1, max_length=200)


class CreatePromptedDungeonTrapWorkflow(WorkflowModel):
    """Accepted trap result ready for deterministic child publication."""

    campaign_id: UUID
    artifact_id: UUID
    parent_version_id: UUID
    context: DungeonTrapEnrichmentInput
    validation: DungeonTrapValidationResult
    model_task_profile_id: UUID
    model_lineage: PromptedDungeonTrapLineage
    tool_runs: tuple[ToolRunPin, ...] = ()
    created_by: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def require_matching_accepted_lineage(self) -> CreatePromptedDungeonTrapWorkflow:
        if self.validation.accepted_output != self.model_lineage.output:
            raise ValueError("trap publication requires matching accepted lineage")
        context_hash = canonical_json_sha256(self.context.model_dump(mode="json"))
        if self.model_lineage.context_sha256 != context_hash:
            raise ValueError("trap publication requires matching context lineage")
        return self


class PromptDungeonObjectiveWorkflow(WorkflowModel):
    """DM request for one exact-objective enrichment child version."""

    campaign_id: UUID
    artifact_id: UUID
    parent_version_id: UUID
    selection: DungeonObjectiveContextSelection
    created_by: str = Field(min_length=1, max_length=200)


class CreatePromptedDungeonObjectiveWorkflow(WorkflowModel):
    """Accepted objective result ready for deterministic child publication."""

    campaign_id: UUID
    artifact_id: UUID
    parent_version_id: UUID
    context: DungeonObjectiveEnrichmentInput
    validation: DungeonObjectiveValidationResult
    model_task_profile_id: UUID
    model_lineage: PromptedDungeonObjectiveLineage
    tool_runs: tuple[ToolRunPin, ...] = ()
    created_by: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def require_matching_accepted_lineage(
        self,
    ) -> CreatePromptedDungeonObjectiveWorkflow:
        if self.validation.accepted_output != self.model_lineage.output:
            raise ValueError("objective publication requires matching accepted lineage")
        context_hash = canonical_json_sha256(self.context.model_dump(mode="json"))
        if self.model_lineage.context_sha256 != context_hash:
            raise ValueError("objective publication requires matching context lineage")
        return self


class PromptDungeonPuzzleWorkflow(WorkflowModel):
    """DM request for one exact-room puzzle enrichment child version."""

    campaign_id: UUID
    artifact_id: UUID
    parent_version_id: UUID
    selection: DungeonPuzzleContextSelection
    created_by: str = Field(min_length=1, max_length=200)


class CreatePromptedDungeonPuzzleWorkflow(WorkflowModel):
    """Accepted puzzle model result ready for deterministic child publication."""

    campaign_id: UUID
    artifact_id: UUID
    parent_version_id: UUID
    context: DungeonPuzzleEnrichmentInput
    validation: DungeonPuzzleEnrichmentValidationResult
    model_task_profile_id: UUID
    model_lineage: PromptedDungeonPuzzleLineage
    tool_runs: tuple[ToolRunPin, ...] = ()
    created_by: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def require_matching_accepted_lineage(self) -> CreatePromptedDungeonPuzzleWorkflow:
        if self.validation.accepted_output != self.model_lineage.output:
            raise ValueError("puzzle publication requires matching accepted lineage")
        context_hash = canonical_json_sha256(self.context.model_dump(mode="json"))
        if self.model_lineage.context_sha256 != context_hash:
            raise ValueError("puzzle publication requires matching context lineage")
        return self


class RegenerateDungeonWorkflow(WorkflowModel):
    campaign_id: UUID
    artifact_id: UUID
    parent_version_id: UUID
    seed: int
    locked_component_ids: tuple[str, ...] = ()
    change_summary: str = Field(min_length=1, max_length=2000)
    created_by: str = Field(min_length=1, max_length=200)


class DungeonPrintCapability(WorkflowModel):
    """Centralized availability state for new print exports."""

    status: Literal["disabled"] = "disabled"
    reason: str = "Exact-scale print maps are temporarily disabled while sparse-page output is redesigned."


class ExportDungeonWorkflow(WorkflowModel):
    """Request exactly one export family; PDF is guarded by capability policy."""

    campaign_id: UUID
    artifact_version_id: UUID
    export_format: Literal["roll20", "pdf"]


class ApproveDungeonWorkflow(WorkflowModel):
    campaign_id: UUID
    artifact_id: UUID
    artifact_version_id: UUID
    actor: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=2000)


class DungeonGenerationRegressionCase(WorkflowModel):
    """Self-contained deterministic failure input retained for regression replay."""

    schema_version: Literal["1.0.0"] = "1.0.0"
    stage: str = Field(min_length=1)
    layout_request: LayoutRequest
    expected_diagnostics: tuple[dict[str, JsonValue], ...] = Field(min_length=1)


class DungeonWorkflowResult(WorkflowModel):
    success: bool
    artifact_id: UUID | None
    artifact_version_id: UUID | None
    generation_run_id: UUID
    diagnostics: tuple[dict[str, JsonValue], ...]
    regression_case: DungeonGenerationRegressionCase | None = None


class DungeonVersionComparison(WorkflowModel):
    left_version_id: UUID
    right_version_id: UUID
    added_component_ids: tuple[str, ...]
    removed_component_ids: tuple[str, ...]
    changed_component_ids: tuple[str, ...]
    unchanged_component_ids: tuple[str, ...]


class DungeonStudioDetail(WorkflowModel):
    artifact_id: UUID
    current_version_id: UUID | None
    lifecycle: str
    title: str
    versions: tuple[UUID, ...]
