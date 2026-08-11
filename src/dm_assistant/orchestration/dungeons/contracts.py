"""Provider-independent Dungeon Studio workflow contracts."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from dm_dungeon import DungeonPackage, LayoutRequest


class WorkflowModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=False)


class DungeonStudioSpecification(WorkflowModel):
    """Immutable persisted input plus exact deterministic output."""

    schema_version: Literal["1.0.0"]
    layout_request: LayoutRequest
    package: DungeonPackage


class CreateDungeonWorkflow(WorkflowModel):
    campaign_id: UUID
    title: str = Field(min_length=1, max_length=200)
    layout_request: LayoutRequest
    created_by: str = Field(min_length=1, max_length=200)


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


class DungeonWorkflowResult(WorkflowModel):
    success: bool
    artifact_id: UUID
    artifact_version_id: UUID | None
    generation_run_id: UUID
    diagnostics: tuple[dict[str, JsonValue], ...]


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
