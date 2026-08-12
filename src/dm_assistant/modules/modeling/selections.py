"""Persistent inspectable defaults for bounded model tasks."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Engine, select

from dm_assistant.db import build_session_factory, transactional_session
from dm_assistant.db.models import ModelTaskSelection
from dm_assistant.modules.modeling.contracts import ReasoningEffort


@dataclass(frozen=True, slots=True)
class TaskModelSelection:
    """One saved provider/model/effort default for a named task."""

    task_name: str
    provider_id: str
    model_id: str
    effort: ReasoningEffort
    selection_policy: str


class ModelTaskSelectionStore:
    """Read and replace task defaults without storing provider credentials."""

    def __init__(self, engine: Engine) -> None:
        self._factory = build_session_factory(engine)

    def get(self, task_name: str) -> TaskModelSelection | None:
        with transactional_session(self._factory) as session:
            row = session.scalar(
                select(ModelTaskSelection).where(
                    ModelTaskSelection.task_name == task_name
                )
            )
            return None if row is None else _snapshot(row)

    def save(
        self,
        *,
        task_name: str,
        provider_id: str,
        model_id: str,
        effort: ReasoningEffort,
        selection_policy: str,
    ) -> TaskModelSelection:
        with transactional_session(self._factory) as session:
            row = session.get(ModelTaskSelection, task_name)
            if row is None:
                row = ModelTaskSelection(
                    task_name=task_name,
                    provider_id=provider_id,
                    model_id=model_id,
                    effort=effort.value,
                    selection_policy=selection_policy,
                )
                session.add(row)
            else:
                row.provider_id = provider_id
                row.model_id = model_id
                row.effort = effort.value
                row.selection_policy = selection_policy
            session.flush()
            return _snapshot(row)


def _snapshot(row: ModelTaskSelection) -> TaskModelSelection:
    return TaskModelSelection(
        task_name=row.task_name,
        provider_id=row.provider_id,
        model_id=row.model_id,
        effort=ReasoningEffort(row.effort),
        selection_policy=row.selection_policy,
    )
