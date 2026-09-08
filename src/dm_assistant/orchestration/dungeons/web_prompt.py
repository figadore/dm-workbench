"""Gateway-backed, reconnectable Dungeon Studio prompt runs for the web shell."""

from __future__ import annotations

import secrets
import threading
import time
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict

from dm_assistant.adapters.model_gateway import (
    GatewayCatalogModel,
    GatewayLoginSession,
    GatewayProvider,
    PiGatewayClient,
)
from dm_assistant.campaigns import CampaignCatalog
from dm_assistant.config import RuntimeEnvironment, Settings
from dm_assistant.errors import InvalidInputError
from dm_assistant.modules.modeling import (
    ModelTaskSelectionStore,
    ReasoningEffort,
    TaskModelSelection,
)
from dm_assistant.modules.preparation import (
    FinishGenerationRun,
    GenerationStatus,
    PreparationService,
)
from dm_assistant.modules.scope import TaskType, resolve_task_scope
from dm_assistant.observability import get_logger
from dm_assistant.orchestration.dungeons.application import (
    DungeonPromptApplicationService,
)
from dm_assistant.orchestration.dungeons.contracts import (
    DungeonWorkflowResult,
    PromptDungeonWorkflow,
)
from dm_assistant.orchestration.dungeons.model_selection import default_dungeon_model
from dm_assistant.orchestration.dungeons.prompting import (
    DungeonPromptService,
    resolve_dungeon_prompt_profile,
)
from dm_assistant.orchestration.modeling import ModelRunAbstained

_TASK_NAME = "dungeon_generation_intent_v1"
_POLICY = "dungeon-task-baseline-v1"
logger = get_logger(__name__)


class DungeonPromptEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    type: Literal["queued", "running", "completed", "cancelled", "failed"]
    message: str


class DungeonPromptRun(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    run_id: uuid.UUID
    campaign_id: uuid.UUID
    status: Literal["queued", "running", "completed", "cancelled", "failed"]
    prompt: str
    provider_id: str | None = None
    model_id: str | None = None
    effort: ReasoningEffort | None = None
    seed: int | None = None
    result: DungeonWorkflowResult | None = None
    error_code: str | None = None
    events: tuple[DungeonPromptEvent, ...]


@dataclass(slots=True)
class _RunState:
    run_id: uuid.UUID
    campaign_id: uuid.UUID
    prompt: str
    status: str = "queued"
    provider_id: str | None = None
    model_id: str | None = None
    effort: ReasoningEffort | None = None
    seed: int | None = None
    result: DungeonWorkflowResult | None = None
    error_code: str | None = None
    events: list[DungeonPromptEvent] = field(default_factory=list)
    cancelled: threading.Event = field(default_factory=threading.Event)


class DungeonPromptWorkbenchService:
    """Thin web adapter over the same prompt/default-resolution services as CLI.

    The successful result pins a Preparation ``generation_run`` through
    ``DungeonPromptService``. The small in-process status record exists only while
    the request is active/inspectable; browser reconnection never replays a model
    request or creates a second artifact.
    """

    def __init__(
        self,
        *,
        settings: Settings,
        campaigns: CampaignCatalog,
        selections: ModelTaskSelectionStore,
        gateway: PiGatewayClient | None,
        prompts: DungeonPromptService | None,
        preparation: PreparationService,
        applications: DungeonPromptApplicationService | None = None,
    ) -> None:
        self._settings = settings
        self._campaigns = campaigns
        self._selections = selections
        self._gateway = gateway
        self._prompts = prompts
        self._preparation = preparation
        self._applications = applications or (
            DungeonPromptApplicationService(preparation, prompts)
            if prompts is not None
            else None
        )
        self._lock = threading.Lock()
        self._runs: dict[uuid.UUID, _RunState] = {}

    def providers(self) -> tuple[GatewayProvider, ...]:
        return () if self._gateway is None else self._gateway.providers()

    def selection(self) -> TaskModelSelection | None:
        return self._selections.get(_TASK_NAME)

    def begin_login(self, provider_id: str) -> GatewayLoginSession:
        if self._gateway is None:
            raise InvalidInputError("Model generation is unavailable.")
        return self._gateway.start_login(provider_id)

    def login_status(self, login_id: str) -> GatewayLoginSession:
        if self._gateway is None:
            raise InvalidInputError("Model generation is unavailable.")
        return self._gateway.login_status(login_id)

    def respond_to_login(self, login_id: str, prompt_id: str, value: str) -> None:
        if self._gateway is None:
            raise InvalidInputError("Model generation is unavailable.")
        self._gateway.respond_to_login(login_id, prompt_id, value)

    def save_selection(
        self, *, provider_id: str, model_id: str, effort: ReasoningEffort
    ) -> TaskModelSelection:
        provider, model = self._find_model(provider_id, model_id)
        if not _compatible(model):
            raise InvalidInputError("The selected model cannot run Dungeon Studio.")
        if effort not in _supported_efforts(model):
            raise InvalidInputError(
                "The selected effort is unavailable for this model."
            )
        del provider
        return self._selections.save(
            task_name=_TASK_NAME,
            provider_id=provider_id,
            model_id=model_id,
            effort=effort,
            selection_policy=_POLICY,
        )

    def start(
        self,
        *,
        campaign_id: uuid.UUID,
        prompt: str,
        provider_id: str | None = None,
        model_id: str | None = None,
        effort: ReasoningEffort | None = None,
        seed: int | None = None,
        title: str | None = None,
        constraints: tuple[str, ...] = (),
    ) -> DungeonPromptRun:
        if self._gateway is None or self._applications is None:
            raise InvalidInputError(
                "Model generation is unavailable; manual Dungeon Studio operations remain available."
            )
        if not prompt.strip():
            raise InvalidInputError("The dungeon prompt is required.")
        resolved_seed = seed if seed is not None else secrets.randbits(63)
        command = self._command(
            campaign_id=campaign_id,
            prompt=prompt,
            seed=resolved_seed,
            title=title,
            constraints=constraints,
        )
        durable_id = self._applications.begin_attempt(command, surface="web")
        state = _RunState(
            run_id=durable_id,
            campaign_id=campaign_id,
            prompt=prompt,
            seed=resolved_seed,
            events=[
                DungeonPromptEvent(type="queued", message="Dungeon prompt queued.")
            ],
        )
        with self._lock:
            self._runs[state.run_id] = state
        thread = threading.Thread(
            target=self._worker,
            args=(
                state.run_id,
                provider_id,
                model_id,
                effort,
                resolved_seed,
                title,
                constraints,
            ),
            daemon=True,
        )
        thread.start()
        return self.get(state.run_id)

    def cancel(self, run_id: uuid.UUID) -> DungeonPromptRun:
        with self._lock:
            state = self._state(run_id)
            if state.status in {"completed", "failed", "cancelled"}:
                return self._snapshot(state)
            state.cancelled.set()
            state.status = "cancelled"
            if self._gateway is not None:
                try:
                    self._gateway.cancel_stream(str(run_id))
                except RuntimeError:
                    pass
            self._finish_durable(state, GenerationStatus.CANCELLED)
            state.events.append(
                DungeonPromptEvent(
                    type="cancelled", message="Dungeon prompt cancelled."
                )
            )
            return self._snapshot(state)

    def get(self, run_id: uuid.UUID) -> DungeonPromptRun:
        with self._lock:
            return self._snapshot(self._state(run_id))

    def stream_events(self, run_id: uuid.UUID) -> Iterable[DungeonPromptEvent]:
        seen = 0
        while True:
            snapshot = self.get(run_id)
            while seen < len(snapshot.events):
                yield snapshot.events[seen]
                seen += 1
            if snapshot.status in {"completed", "failed", "cancelled"}:
                return
            time.sleep(0.05)

    def _worker(
        self,
        run_id: uuid.UUID,
        provider_id: str | None,
        model_id: str | None,
        effort: ReasoningEffort | None,
        seed: int | None,
        title: str | None,
        constraints: tuple[str, ...],
    ) -> None:
        with self._lock:
            state = self._state(run_id)
            if state.cancelled.is_set():
                return
            state.status = "running"
            state.events.append(
                DungeonPromptEvent(
                    type="running",
                    message="Resolving model and generating typed dungeon intent.",
                )
            )
        stage = "model_resolution"
        try:
            provider, model, resolved_effort = self._resolve(
                provider_id, model_id, effort
            )
            resolved_seed = seed
            assert resolved_seed is not None
            with self._lock:
                state = self._state(run_id)
                state.provider_id, state.model_id = provider.id, model.id
                state.effort, state.seed = resolved_effort, resolved_seed
                if state.cancelled.is_set():
                    return
            stage = "profile_resolution"
            profile = resolve_dungeon_prompt_profile(
                provider_id=provider.id,
                model_id=model.id,
                capabilities=model.capabilities,
                context_window_tokens=model.context_window,
                output_token_limit=model.max_output_tokens,
                requested_effort=resolved_effort,
            )
            stage = "command_resolution"
            command = self._command(
                campaign_id=self.get(run_id).campaign_id,
                prompt=self.get(run_id).prompt,
                seed=resolved_seed,
                title=title,
                constraints=constraints,
            )
            stage = "application_execution"
            attempt = self._applications.execute(  # type: ignore[union-attr]
                command, profile, surface="web", attempt_run_id=run_id
            )
            if attempt.result is None:
                self._fail(run_id, attempt.public_code, finish_durable=False)
                return
            result = attempt.result
        except (ModelRunAbstained, ValueError, RuntimeError) as error:
            logger.warning(
                "web dungeon prompt worker stopped",
                extra={
                    "event_data": {
                        "stage": stage,
                        "code": "dungeon_prompt_failed",
                        "exception_class": error.__class__.__name__,
                    }
                },
            )
            self._fail(run_id, "dungeon_prompt_failed")
            return
        with self._lock:
            state = self._state(run_id)
            if state.cancelled.is_set():
                return
            state.result = result
            if result.success:
                state.status = "completed"
                state.events.append(
                    DungeonPromptEvent(
                        type="completed", message="Dungeon draft created."
                    )
                )
            else:
                state.status = "failed"
                state.error_code = "dungeon_validation_failed"
                state.events.append(
                    DungeonPromptEvent(
                        type="failed",
                        message="Deterministic validation did not produce a draft.",
                    )
                )

    @staticmethod
    def _command(
        *,
        campaign_id: uuid.UUID,
        prompt: str,
        seed: int,
        title: str | None,
        constraints: tuple[str, ...],
    ) -> PromptDungeonWorkflow:
        return PromptDungeonWorkflow(
            campaign_id=campaign_id,
            title=title,
            prompt=prompt,
            seed=seed,
            created_by="dm-web",
            scope=resolve_task_scope(
                dm_principal_id="dm",
                campaign_owner_id="dm",
                task_type=TaskType.STANDALONE_DUNGEON,
            ),
            requested_constraints=constraints,
        )

    def _resolve(
        self,
        provider_id: str | None,
        model_id: str | None,
        effort: ReasoningEffort | None,
    ) -> tuple[GatewayProvider, GatewayCatalogModel, ReasoningEffort]:
        providers = self.providers()
        saved = self.selection()
        if saved is not None and saved.selection_policy != _POLICY:
            saved = None
        selected_provider_id = provider_id or (saved.provider_id if saved else None)
        provider = next(
            (item for item in providers if item.id == selected_provider_id), None
        )
        if provider is None:
            provider = next(
                (
                    item
                    for item in providers
                    if item.authenticated
                    and (
                        item.id != "faux"
                        or self._settings.environment is RuntimeEnvironment.TEST
                    )
                    and default_dungeon_model(item.models, item.id) is not None
                ),
                None,
            )
        if provider is None:
            raise InvalidInputError(
                "No authenticated compatible model provider is available. Complete provider login first."
            )
        if not provider.authenticated and not (
            provider.id == "faux"
            and self._settings.environment is RuntimeEnvironment.TEST
        ):
            raise InvalidInputError("The selected model provider requires login.")
        requested_model_id = model_id or (
            saved.model_id if saved and saved.provider_id == provider.id else None
        )
        model = next(
            (item for item in provider.models if item.id == requested_model_id), None
        )
        if model is None:
            model = default_dungeon_model(provider.models, provider.id)
        if model is None:
            raise InvalidInputError("No compatible tool-capable model is available.")
        resolved_effort = effort or (
            saved.effort
            if saved and saved.provider_id == provider.id and saved.model_id == model.id
            else ReasoningEffort.STANDARD
        )
        self.save_selection(
            provider_id=provider.id, model_id=model.id, effort=resolved_effort
        )
        return provider, model, resolved_effort

    def _find_model(
        self, provider_id: str, model_id: str
    ) -> tuple[GatewayProvider, GatewayCatalogModel]:
        provider = next(
            (item for item in self.providers() if item.id == provider_id), None
        )
        model = (
            next((item for item in provider.models if item.id == model_id), None)
            if provider
            else None
        )
        if provider is None or model is None:
            raise InvalidInputError("The selected provider or model is unavailable.")
        return provider, model

    def _fail(
        self, run_id: uuid.UUID, code: str, *, finish_durable: bool = True
    ) -> None:
        with self._lock:
            state = self._state(run_id)
            if state.cancelled.is_set():
                return
            cancelled = code == "dungeon_prompt_cancelled"
            state.status = "cancelled" if cancelled else "failed"
            state.error_code = code
            if finish_durable:
                self._finish_durable(
                    state,
                    GenerationStatus.CANCELLED
                    if cancelled
                    else GenerationStatus.FAILED,
                )
            state.events.append(
                DungeonPromptEvent(
                    type="cancelled" if cancelled else "failed",
                    message=(
                        "Dungeon prompt cancelled."
                        if cancelled
                        else "Dungeon prompt did not complete."
                    ),
                )
            )

    def _finish_durable(self, state: _RunState, status: GenerationStatus) -> None:
        try:
            self._preparation.finish_generation_run(
                FinishGenerationRun(
                    campaign_id=state.campaign_id,
                    run_id=state.run_id,
                    status=cast(
                        Literal[
                            GenerationStatus.SUCCEEDED,
                            GenerationStatus.FAILED,
                            GenerationStatus.CANCELLED,
                        ],
                        status,
                    ),
                    validation_report={"stage": "web_prompt", "status": status.value},
                )
            )
        except RuntimeError:
            # The browser state remains safe if a concurrent terminal transition won.
            pass

    def _state(self, run_id: uuid.UUID) -> _RunState:
        state = self._runs.get(run_id)
        if state is None:
            raise InvalidInputError("The dungeon prompt run was not found.")
        return state

    @staticmethod
    def _snapshot(state: _RunState) -> DungeonPromptRun:
        return DungeonPromptRun(
            run_id=state.run_id,
            campaign_id=state.campaign_id,
            status=cast(
                Literal["queued", "running", "completed", "cancelled", "failed"],
                state.status,
            ),
            prompt=state.prompt,
            provider_id=state.provider_id,
            model_id=state.model_id,
            effort=state.effort,
            seed=state.seed,
            result=state.result,
            error_code=state.error_code,
            events=tuple(state.events),
        )


def _compatible(model: GatewayCatalogModel) -> bool:
    return "text" in model.capabilities and "tool_calls" in model.capabilities


def _supported_efforts(model: GatewayCatalogModel) -> tuple[ReasoningEffort, ...]:
    return (
        (ReasoningEffort.FAST, ReasoningEffort.STANDARD, ReasoningEffort.DEEP)
        if "thinking" in model.capabilities
        else (ReasoningEffort.STANDARD,)
    )
