"""Provider-free bounded repetition over the staged one-step coordinator."""

import uuid
from collections.abc import Callable

from dm_assistant.modules.modeling import ResolvedModelRunProfile
from dm_assistant.orchestration.dungeons import (
    DungeonPuzzleContextSelection,
    DungeonPuzzlePromptAttemptResult,
    DungeonStagedEnrichmentChainCoordinator,
    DungeonStagedEnrichmentDispatch,
    DungeonStagedEnrichmentPlan,
    DungeonStagedEnrichmentStepResult,
    DungeonStagedEnrichmentTask,
    DungeonStagedPuzzlePolicy,
    DungeonWorkflowResult,
    PromptDungeonStagedEnrichmentChainWorkflow,
    PromptDungeonStagedEnrichmentWorkflow,
    resolve_dungeon_puzzle_prompt_profile,
)


def _profile() -> ResolvedModelRunProfile:
    return resolve_dungeon_puzzle_prompt_profile(
        provider_id="faux",
        model_id="faux_deterministic_v1",
        capabilities=("text", "tool_calls"),
        context_window_tokens=16_384,
        output_token_limit=4_096,
    )


def _ready_plan(sequence: int) -> DungeonStagedEnrichmentPlan:
    return DungeonStagedEnrichmentPlan(
        status="ready",
        next_task=DungeonStagedEnrichmentTask(
            kind="puzzle",
            room_ids=(f"room_{sequence}",),
            target_ids=(f"room_{sequence}",),
        ),
    )


def _accepted_step(
    *, parent_sequence: int, child_version_id: uuid.UUID
) -> DungeonStagedEnrichmentStepResult:
    return DungeonStagedEnrichmentStepResult(
        plan_before=_ready_plan(parent_sequence),
        attempt=DungeonPuzzlePromptAttemptResult(
            attempt_run_id=uuid.uuid4(),
            result=DungeonWorkflowResult(
                success=True,
                artifact_id=uuid.uuid4(),
                artifact_version_id=child_version_id,
                generation_run_id=uuid.uuid4(),
                diagnostics=(),
            ),
            public_code="dungeon_puzzle_prompt_completed",
        ),
        plan_after=_ready_plan(parent_sequence + 1),
        public_code="dungeon_puzzle_prompt_completed",
    )


def _accepted_complete_step(
    *, parent_sequence: int, child_version_id: uuid.UUID
) -> DungeonStagedEnrichmentStepResult:
    return DungeonStagedEnrichmentStepResult(
        plan_before=_ready_plan(parent_sequence),
        attempt=DungeonPuzzlePromptAttemptResult(
            attempt_run_id=uuid.uuid4(),
            result=DungeonWorkflowResult(
                success=True,
                artifact_id=uuid.uuid4(),
                artifact_version_id=child_version_id,
                generation_run_id=uuid.uuid4(),
                diagnostics=(),
            ),
            public_code="dungeon_puzzle_prompt_completed",
        ),
        plan_after=DungeonStagedEnrichmentPlan(status="complete"),
        public_code="dungeon_puzzle_prompt_completed",
    )


def _rejected_step(sequence: int) -> DungeonStagedEnrichmentStepResult:
    plan = _ready_plan(sequence)
    return DungeonStagedEnrichmentStepResult(
        plan_before=plan,
        attempt=DungeonPuzzlePromptAttemptResult(
            attempt_run_id=uuid.uuid4(),
            result=None,
            public_code="dungeon_puzzle_prompt_failed",
        ),
        plan_after=plan,
        public_code="dungeon_puzzle_prompt_failed",
    )


class _FakeOneStepCoordinator:
    def __init__(self, steps: tuple[DungeonStagedEnrichmentStepResult, ...]) -> None:
        self._steps = list(steps)
        self.commands: list[PromptDungeonStagedEnrichmentWorkflow] = []

    def execute(
        self,
        command: PromptDungeonStagedEnrichmentWorkflow,
        profile: ResolvedModelRunProfile,
        *,
        surface: str,
        debug: Callable[[str, dict[str, object]], None] | None = None,
    ) -> DungeonStagedEnrichmentStepResult:
        del profile, surface, debug
        self.commands.append(command)
        if not self._steps:
            raise AssertionError("unexpected fourth one-step dispatch")
        return self._steps.pop(0)


def _command(
    *,
    parent_version_id: uuid.UUID,
    dispatch_count: int,
    maximum_tasks: int,
) -> PromptDungeonStagedEnrichmentChainWorkflow:
    dispatch = DungeonStagedEnrichmentDispatch(
        policy=DungeonStagedPuzzlePolicy(
            selection=DungeonPuzzleContextSelection(room_id="room_1")
        ),
        profile=_profile(),
    )
    return PromptDungeonStagedEnrichmentChainWorkflow(
        campaign_id=uuid.uuid4(),
        artifact_id=uuid.uuid4(),
        parent_version_id=parent_version_id,
        dispatches=(dispatch,) * dispatch_count,
        maximum_tasks=maximum_tasks,
        created_by="synthetic-dm",
    )


def test_chain_stops_on_rejection_and_keeps_last_accepted_parent() -> None:
    parent_id = uuid.uuid4()
    first_child_id = uuid.uuid4()
    second_child_id = uuid.uuid4()
    one_step = _FakeOneStepCoordinator(
        (
            _accepted_step(parent_sequence=1, child_version_id=first_child_id),
            _accepted_step(parent_sequence=2, child_version_id=second_child_id),
            _rejected_step(3),
        )
    )

    result = DungeonStagedEnrichmentChainCoordinator(one_step).execute(
        _command(
            parent_version_id=parent_id,
            dispatch_count=4,
            maximum_tasks=4,
        ),
        surface="unit",
    )

    assert result.stop_reason == "task_rejected"
    assert len(result.steps) == 3
    assert result.current_version_id == second_child_id
    assert result.plan_after == result.steps[-1].plan_before
    assert [command.parent_version_id for command in one_step.commands] == [
        parent_id,
        first_child_id,
        second_child_id,
    ]


def test_chain_stops_when_an_accepted_child_completes_the_plan() -> None:
    parent_id = uuid.uuid4()
    first_child_id = uuid.uuid4()
    final_child_id = uuid.uuid4()
    one_step = _FakeOneStepCoordinator(
        (
            _accepted_step(parent_sequence=1, child_version_id=first_child_id),
            _accepted_complete_step(
                parent_sequence=2,
                child_version_id=final_child_id,
            ),
        )
    )

    result = DungeonStagedEnrichmentChainCoordinator(one_step).execute(
        _command(
            parent_version_id=parent_id,
            dispatch_count=3,
            maximum_tasks=3,
        ),
        surface="unit",
    )

    assert result.stop_reason == "complete"
    assert result.plan_after.status == "complete"
    assert result.current_version_id == final_child_id
    assert len(result.steps) == 2
    assert len(one_step.commands) == 2


def test_chain_never_exceeds_explicit_task_limit() -> None:
    parent_id = uuid.uuid4()
    first_child_id = uuid.uuid4()
    second_child_id = uuid.uuid4()
    one_step = _FakeOneStepCoordinator(
        (
            _accepted_step(parent_sequence=1, child_version_id=first_child_id),
            _accepted_step(parent_sequence=2, child_version_id=second_child_id),
            _accepted_step(parent_sequence=3, child_version_id=uuid.uuid4()),
        )
    )

    result = DungeonStagedEnrichmentChainCoordinator(one_step).execute(
        _command(
            parent_version_id=parent_id,
            dispatch_count=3,
            maximum_tasks=2,
        ),
        surface="unit",
    )

    assert result.stop_reason == "task_limit_reached"
    assert len(result.steps) == 2
    assert result.current_version_id == second_child_id
    assert len(one_step.commands) == 2
