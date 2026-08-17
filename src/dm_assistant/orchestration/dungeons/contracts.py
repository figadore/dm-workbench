"""Provider-independent Dungeon Studio workflow contracts."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from dm_assistant.modules.modeling import DungeonGenerationIntentV1, ModelRunRecord
from dm_assistant.modules.preparation import GenerationContextPin, ToolRunPin
from dm_assistant.modules.scope import TaskScope, TaskType
from dm_dungeon import DungeonDesignSpecV2, DungeonPackage, LayoutRequest


class WorkflowModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=False)


class PromptedDungeonModelLineage(WorkflowModel):
    """One validated model response retained for prompt replay and review."""

    model_run_id: UUID
    model_run: ModelRunRecord
    intent: DungeonGenerationIntentV1


class DungeonRoomDmNote(WorkflowModel):
    """DM-facing prose linked to one stable generated room."""

    room_id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=4_000)


class DungeonDmNotes(WorkflowModel):
    """Readable preparation material kept outside the pure dungeon package."""

    source_prompt: str | None = Field(default=None, min_length=1, max_length=4_000)
    room_notes: tuple[DungeonRoomDmNote, ...] = ()


class DungeonStudioSpecification(WorkflowModel):
    """Immutable persisted input plus exact deterministic output and lineage."""

    schema_version: Literal["1.0.0"]
    layout_request: LayoutRequest
    package: DungeonPackage
    dm_notes: DungeonDmNotes = DungeonDmNotes()
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
    def require_design_or_safe_abstention(self) -> "DungeonGenerationProposalV2":
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
    def require_standalone_scope(self) -> "PromptDungeonWorkflow":
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


class ExportDungeonWorkflow(WorkflowModel):
    campaign_id: UUID
    artifact_version_id: UUID


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
