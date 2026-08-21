"""Provider-independent Dungeon Studio workflow contracts."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from dm_assistant.modules.modeling import DungeonGenerationIntentV1, ModelRunRecord
from dm_assistant.modules.preparation import GenerationContextPin, ToolRunPin
from dm_assistant.modules.scope import TaskScope, TaskType
from dm_dungeon import (
    DungeonDesignSpecV2,
    DungeonPackage,
    DungeonPackageV2,
    LayoutRequest,
    MapCallout,
)
from dm_dungeon.contracts import (
    BarrierIntent,
    EncounterSlotIntent,
    EndpointDoorKind,
    FeatureIntentKind,
    ObjectiveKind,
    RoomRole,
    VerticalEndpointSide,
)


class WorkflowModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=False)


class PromptedDungeonModelLineage(WorkflowModel):
    """One validated model response retained for prompt replay and review."""

    model_run_id: UUID
    model_run: ModelRunRecord
    intent: DungeonGenerationIntentV1 | None = None
    proposal_v2: DungeonGenerationProposalV2 | None = None

    @model_validator(mode="after")
    def require_one_model_result(self) -> PromptedDungeonModelLineage:
        result_count = sum(
            value is not None for value in (self.intent, self.proposal_v2)
        )
        if self.model_run.status == "abstained":
            if result_count:
                raise ValueError(
                    "abstained lineage cannot claim a validated model result"
                )
        elif result_count != 1:
            raise ValueError("successful lineage requires exactly one model result")
        return self


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
    name: str = Field(min_length=1, max_length=200)
    role: RoomRole
    tags: tuple[str, ...] = ()
    preparation_note: str | None = Field(default=None, min_length=1, max_length=4_000)
    encounter_slot: EncounterSlotIntent | None = None
    encounter_slot_id: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def require_encounter_slot_id_with_intent(self) -> DungeonGuideRoom:
        if (self.encounter_slot is None) != (self.encounter_slot_id is None):
            raise ValueError(
                "encounter slot intent and stable ID must be present together"
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


class DungeonGuideTrap(WorkflowModel):
    marker_id: str = Field(min_length=1, max_length=200)
    room_id: str = Field(min_length=1, max_length=200)
    map_reference: DungeonGuideMapReference
    name: str = Field(min_length=1, max_length=200)
    trigger: str | None = Field(default=None, min_length=1, max_length=4_000)
    effect: str | None = Field(default=None, min_length=1, max_length=4_000)
    detection_difficulty: int = Field(ge=0)
    disable_difficulty: int = Field(ge=0)


class DungeonGuidePuzzle(WorkflowModel):
    marker_id: str = Field(min_length=1, max_length=200)
    room_id: str = Field(min_length=1, max_length=200)
    map_reference: DungeonGuideMapReference
    name: str = Field(min_length=1, max_length=200)
    mechanism: str | None = Field(default=None, min_length=1, max_length=4_000)
    clue_dependency_ids: tuple[str, ...] = ()
    solution: str | None = Field(default=None, min_length=1, max_length=4_000)
    consequence: str | None = Field(default=None, min_length=1, max_length=4_000)
    difficulty: int = Field(ge=0)


class DungeonGuideObjective(WorkflowModel):
    marker_id: str = Field(min_length=1, max_length=200)
    room_id: str = Field(min_length=1, max_length=200)
    map_reference: DungeonGuideMapReference
    kind: ObjectiveKind
    name: str = Field(min_length=1, max_length=200)


class DungeonGuideFeature(WorkflowModel):
    marker_id: str = Field(min_length=1, max_length=200)
    room_id: str = Field(min_length=1, max_length=200)
    map_reference: DungeonGuideMapReference
    kind: FeatureIntentKind
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=4_000)


class DungeonPreparationReadinessDiagnostic(WorkflowModel):
    """One deterministic reason a generated guide must remain a draft."""

    code: Literal[
        "dungeon_preparation.lock_dependency_missing",
        "dungeon_preparation.trap_effect_unknown",
        "dungeon_preparation.puzzle_solution_unknown",
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

    @model_validator(mode="after")
    def require_unique_entries_and_resolved_callouts(self) -> DungeonDmGuide:
        ids = [
            *(item.room_id for item in self.rooms),
            *(item.component_id for item in self.connections),
            *(item.marker_id for item in self.traps),
            *(item.marker_id for item in self.puzzles),
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
    package: DungeonPackage | DungeonPackageV2
    dm_notes: DungeonDmNotes = DungeonDmNotes()
    dm_guide: DungeonDmGuide | None = None
    preparation_readiness: DungeonPreparationReadiness | None = None
    model_lineage: tuple[PromptedDungeonModelLineage, ...] = ()


class CreateDungeonWorkflow(WorkflowModel):
    campaign_id: UUID
    title: str = Field(min_length=1, max_length=200)
    layout_request: LayoutRequest
    created_by: str = Field(min_length=1, max_length=200)


class DungeonProposalAbstentionV2(WorkflowModel):
    """Safe bounded reason for declining a V2 creative design."""

    kind: Literal["insufficient_creative_direction", "conflicting_direction"]


class DungeonGenerationProposalV2(WorkflowModel):
    """Workbench-owned wrapper around pure compact creative design intent."""

    # Keep the design/abstention XOR visible in the exact schema sent to the
    # gateway; the runtime validator remains authoritative fallback.
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=False,
        json_schema_extra={
            "oneOf": [
                {
                    "required": ["design"],
                    "properties": {"abstention": {"type": "null"}},
                },
                {
                    "required": ["abstention"],
                    "properties": {"design": {"type": "null"}},
                },
            ]
        },
    )

    proposal_version: Literal["2"]
    design: DungeonDesignSpecV2 | None = None
    intent_summary: str | None = Field(default=None, min_length=1, max_length=500)
    requested_constraints: tuple[str, ...] = Field(default=(), max_length=16)
    citation_ids: tuple[str, ...] = Field(default=(), max_length=32)
    official_rule_ids: tuple[str, ...] = Field(default=(), max_length=32)
    unknowns: tuple[str, ...] = Field(default=(), max_length=16)
    conflicts: tuple[str, ...] = Field(default=(), max_length=16)
    abstention: DungeonProposalAbstentionV2 | None = None

    @model_validator(mode="before")
    @classmethod
    def decode_pure_design(cls, value: object) -> object:
        if not isinstance(value, dict) or isinstance(
            value.get("design"), DungeonDesignSpecV2
        ):
            return value
        document = dict(value)
        design = document.get("design")
        if isinstance(design, dict):
            import json

            document["design"] = DungeonDesignSpecV2.model_validate_json(
                json.dumps(design)
            )
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
    def require_design_or_safe_abstention(self) -> DungeonGenerationProposalV2:
        if (self.design is None) == (self.abstention is None):
            raise ValueError("proposal requires exactly one of design or abstention")
        if self.abstention is not None and self.intent_summary is not None:
            raise ValueError("abstention cannot include an intent summary")
        return self


class SubmitDungeonIntentV2Input(WorkflowModel):
    """The entire model-controlled input of the sole V2 submission tool."""

    proposal: DungeonGenerationProposalV2


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
