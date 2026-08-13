"""Provider-independent Dungeon Studio workflow contracts."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from dm_assistant.modules.modeling import DungeonGenerationIntentV1, ModelRunRecord
from dm_assistant.modules.preparation import GenerationContextPin, ToolRunPin
from dm_assistant.modules.scope import TaskScope, TaskType
from dm_dungeon import DungeonPackage, LayoutRequest


class WorkflowModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=False)


class PromptedDungeonModelLineage(WorkflowModel):
    """One validated model response retained for prompt replay and review."""

    model_run_id: UUID
    model_run: ModelRunRecord
    intent: DungeonGenerationIntentV1


class DungeonStudioSpecification(WorkflowModel):
    """Immutable persisted input plus exact deterministic output and lineage."""

    schema_version: Literal["1.0.0"]
    layout_request: LayoutRequest
    package: DungeonPackage
    model_lineage: tuple[PromptedDungeonModelLineage, ...] = ()


class CreateDungeonWorkflow(WorkflowModel):
    campaign_id: UUID
    title: str = Field(min_length=1, max_length=200)
    layout_request: LayoutRequest
    created_by: str = Field(min_length=1, max_length=200)


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
    artifact_id: UUID
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
