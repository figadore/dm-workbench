"""Task scope contracts keep prompt intent bounded to the explicit DM scope."""

import uuid

import pytest
from pydantic import ValidationError

from dm_assistant.modules.preparation import VisibilityPolicy
from dm_assistant.modules.scope import TaskScope, TaskType, resolve_task_scope


def test_standalone_dungeon_scope_defaults_to_dm_only_and_ungrounded() -> None:
    scope = resolve_task_scope(
        dm_principal_id="dm",
        task_type=TaskType.STANDALONE_DUNGEON,
        campaign_owner_id="dm",
    )

    assert scope.dm_principal_id == "dm"
    assert scope.campaign_owner_id == "dm"
    assert scope.grounding_enabled is False
    assert scope.visibility is VisibilityPolicy.DM_ONLY
    assert scope.campaign_revision_id is None
    assert scope.corpus_snapshot_id is None
    assert scope.rules_profile_id is None
    assert scope.source_authority == "dm_only"


def test_grounded_scope_requires_explicit_grounding_and_supported_ids() -> None:
    revision_id = uuid.uuid4()
    snapshot_id = uuid.uuid4()
    rules_id = uuid.uuid4()

    scope = resolve_task_scope(
        dm_principal_id="dm",
        task_type=TaskType.GROUNDED_DUNGEON,
        campaign_owner_id="dm",
        grounding_enabled=True,
        campaign_revision_id=revision_id,
        corpus_snapshot_id=snapshot_id,
        rules_profile_id=rules_id,
    )

    assert scope.grounding_enabled is True
    assert scope.campaign_revision_id == revision_id
    assert scope.corpus_snapshot_id == snapshot_id
    assert scope.rules_profile_id == rules_id
    assert scope.source_authority == "campaign_owner"


def test_standalone_scope_rejects_broadening_fields() -> None:
    with pytest.raises(ValueError, match="campaign grounding"):
        resolve_task_scope(
            dm_principal_id="dm",
            task_type=TaskType.STANDALONE_DUNGEON,
            campaign_owner_id="dm",
            campaign_revision_id=uuid.uuid4(),
        )

    with pytest.raises(ValueError, match="corpus snapshot"):
        resolve_task_scope(
            dm_principal_id="dm",
            task_type=TaskType.STANDALONE_DUNGEON,
            campaign_owner_id="dm",
            corpus_snapshot_id=uuid.uuid4(),
        )


def test_contract_rejects_non_dm_principal_or_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="dm"):
        TaskScope(
            dm_principal_id="player-1",
            campaign_owner_id="dm",
            task_type=TaskType.STANDALONE_DUNGEON,
            source_authority="campaign_owner",
        )

    with pytest.raises(ValidationError):
        TaskScope.model_validate({
            "dm_principal_id": "dm",
            "campaign_owner_id": "dm",
            "task_type": TaskType.STANDALONE_DUNGEON,
            "unexpected": "field",
        })
