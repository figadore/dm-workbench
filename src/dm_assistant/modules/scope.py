"""Task-scope contracts for bounded prompt-to-dungeon intent resolution."""

from __future__ import annotations

import uuid
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, model_validator

from dm_assistant.modules.preparation import VisibilityPolicy


class TaskType(StrEnum):
    """Named task categories supported by the bounded dungeon workflow."""

    STANDALONE_DUNGEON = "standalone_dungeon"
    GROUNDED_DUNGEON = "grounded_dungeon"
    RULES_ANSWER = "rules_answer"


class TaskScope(BaseModel):
    """Bounded task resolution; scope must stay within the DM's explicit intent."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    dm_principal_id: str = Field(min_length=1, max_length=80)
    campaign_owner_id: str = Field(min_length=1, max_length=80)
    task_type: TaskType
    grounding_enabled: bool = False
    campaign_revision_id: uuid.UUID | None = None
    corpus_snapshot_id: uuid.UUID | None = None
    rules_profile_id: uuid.UUID | None = None
    visibility: VisibilityPolicy = VisibilityPolicy.DM_ONLY
    source_authority: str = "dm_only"

    @model_validator(mode="after")
    def validate_scope_boundaries(self) -> TaskScope:
        if self.dm_principal_id != "dm":
            raise ValueError("only the authenticated DM principal is allowed")
        if self.campaign_owner_id != "dm":
            raise ValueError("only the DM campaign owner is allowed in this task scope")
        if self.grounding_enabled:
            if self.campaign_revision_id is None:
                raise ValueError("grounding requires an explicit campaign revision")
            if self.corpus_snapshot_id is None:
                raise ValueError("grounding requires an explicit corpus snapshot")
            if self.rules_profile_id is None:
                raise ValueError("grounding requires an explicit rules profile")
            object.__setattr__(self, "source_authority", "campaign_owner")
            return self

        if self.campaign_revision_id is not None:
            raise ValueError("standalone task scope cannot include campaign grounding")
        if self.corpus_snapshot_id is not None:
            raise ValueError("standalone task scope cannot include a corpus snapshot")
        if self.rules_profile_id is not None:
            raise ValueError("standalone task scope cannot include a rules profile")
        object.__setattr__(self, "source_authority", "dm_only")
        return self


def resolve_task_scope(
    *,
    dm_principal_id: str,
    task_type: TaskType,
    campaign_owner_id: str,
    grounding_enabled: bool = False,
    campaign_revision_id: uuid.UUID | None = None,
    corpus_snapshot_id: uuid.UUID | None = None,
    rules_profile_id: uuid.UUID | None = None,
) -> TaskScope:
    """Resolve the bounded task scope and reject any broadening beyond explicit consent."""

    return TaskScope(
        dm_principal_id=dm_principal_id,
        campaign_owner_id=campaign_owner_id,
        task_type=task_type,
        grounding_enabled=grounding_enabled,
        campaign_revision_id=campaign_revision_id,
        corpus_snapshot_id=corpus_snapshot_id,
        rules_profile_id=rules_profile_id,
    )
