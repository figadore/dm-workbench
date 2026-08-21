"""Workbench-facing model settings, login, selection, and run state."""

from __future__ import annotations

import hashlib
import threading
import time
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field

from dm_assistant.adapters.assets import AssetStore, StoredBlob
from dm_assistant.modules.modeling import (
    AskResponseV1,
    DungeonIntentV1,
    GatewayModelCatalogEntry,
    GatewayModelKey,
    ModelEndpointProfile,
    ModelRunInput,
    ModelRunRecord,
    PromptMessage,
    ReasoningEffort,
    ReasoningLevel,
    ResolvedModelRunProfile,
    TaskProfile,
    ToolCall,
    resolve_run_profile,
)
from dm_assistant.orchestration.modeling import (
    GatewayCompletion,
    GatewayToolSchema,
    ModelRunAbstained,
    ModelTaskRunner,
    ServerTool,
    build_dungeon_intent_tool_result,
)


class WorkbenchModelSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    provider_id: str
    model_id: str
    name: str
    capabilities: tuple[str, ...] = ()


class _ProviderState(TypedDict):
    name: str
    authenticated: bool
    auth_modes: tuple[str, ...]
    models: tuple[WorkbenchModelSummary, ...]


class WorkbenchProviderSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    provider_id: str
    name: str
    authenticated: bool
    auth_modes: tuple[str, ...] = ()
    models: tuple[WorkbenchModelSummary, ...] = ()


class LoginEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    type: Literal["device_code", "prompt", "info", "progress", "complete"]
    message: str | None = None
    user_code: str | None = None
    verification_uri: str | None = None
    prompt_id: str | None = None


class LoginSession(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    login_id: uuid.UUID
    provider_id: str
    status: Literal["pending", "completed"]
    events: tuple[LoginEvent, ...]


class RunEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    type: Literal["queued", "running", "tool_call", "completed", "cancelled", "failed"]
    message: str | None = None
    tool_name: str | None = None
    call_id: str | None = None


class RunSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    run_id: uuid.UUID
    status: Literal["queued", "running", "completed", "cancelled", "failed"]
    prompt: str
    selection: dict[str, str]
    events: tuple[RunEvent, ...]
    output: DungeonIntentV1 | None = None
    resolved_profile: ResolvedModelRunProfile | None = None
    error: str | None = None


class AskAttachmentRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    attachment_id: uuid.UUID
    filename: str
    media_type: str
    byte_size: int
    sha256: str
    storage_locator: str
    retention_policy: Literal["ask_session"]
    created_at: datetime


class AskComparisonReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    primary_model_id: str
    baseline_model_id: str
    prompt_digest: str
    primary_answer: str
    baseline_answer: str
    summary: str


class AskRunSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    run_id: uuid.UUID
    status: Literal["queued", "running", "completed", "cancelled", "failed"]
    prompt: str
    attachment_ids: tuple[uuid.UUID, ...] = ()
    events: tuple[RunEvent, ...]
    response: AskResponseV1 | None = None
    comparison: AskComparisonReport | None = None
    resolved_profile: ResolvedModelRunProfile | None = None
    error: str | None = None


class SelectionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    provider_id: str
    model_id: str
    task_profile_id: uuid.UUID
    effort: ReasoningEffort


@dataclass(slots=True)
class _RunState:
    run_id: uuid.UUID
    prompt: str
    selection: SelectionSnapshot
    status: str = "queued"
    events: list[RunEvent] = field(default_factory=list)
    output: DungeonIntentV1 | None = None
    resolved_profile: ResolvedModelRunProfile | None = None
    error: str | None = None
    cancelled: threading.Event = field(default_factory=threading.Event)


@dataclass(slots=True)
class _AskRunState:
    run_id: uuid.UUID
    prompt: str
    attachment_ids: tuple[uuid.UUID, ...]
    selection: SelectionSnapshot
    status: str = "queued"
    events: list[RunEvent] = field(default_factory=list)
    response: AskResponseV1 | None = None
    comparison: AskComparisonReport | None = None
    resolved_profile: ResolvedModelRunProfile | None = None
    error: str | None = None
    cancelled: threading.Event = field(default_factory=threading.Event)


class ModelWorkbenchService:
    """Shared model settings and bounded run orchestration for the Workbench."""

    def __init__(self, *, asset_store: AssetStore | None = None) -> None:
        self._lock = threading.Lock()
        self._asset_store = asset_store
        self._providers: dict[str, _ProviderState] = {
            "faux": {
                "name": "Faux provider",
                "authenticated": False,
                "auth_modes": ("device_code",),
                "models": (
                    WorkbenchModelSummary(
                        provider_id="faux",
                        model_id="faux_deterministic_v1",
                        name="Faux deterministic contract model",
                        capabilities=("text", "tool_calls"),
                    ),
                    WorkbenchModelSummary(
                        provider_id="faux",
                        model_id="faux_baseline_v1",
                        name="Faux baseline comparison model",
                        capabilities=("text",),
                    ),
                ),
            }
        }
        self._dungeon_task_profile = TaskProfile(
            profile_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            profile_version="1.0.0",
            task_name="dungeon_intent_v1",
            prompt_version="prompt-1",
            instruction_version="instructions-1",
            output_schema_name="dungeon_intent_v1",
            output_schema_version="1.0.0",
            allowed_tools=("set_brief",),
            turn_budget=2,
            tool_budget=1,
            time_budget_seconds=30,
            token_budget=512,
        )
        self._ask_task_profile = TaskProfile(
            profile_id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
            profile_version="1.0.0",
            task_name="general_ask_v1",
            prompt_version="prompt-1",
            instruction_version="instructions-1",
            output_schema_name="general_ask_v1",
            output_schema_version="1.0.0",
            allowed_tools=(),
            turn_budget=1,
            tool_budget=0,
            time_budget_seconds=30,
            token_budget=512,
            require_citation_ids=True,
            require_authorized_citations=True,
            allow_source_retrieval_tools=False,
        )
        self._task_profiles = {
            self._dungeon_task_profile.profile_id: self._dungeon_task_profile,
            self._ask_task_profile.profile_id: self._ask_task_profile,
        }
        self._endpoint_profile = ModelEndpointProfile(
            profile_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
            profile_version="1.0.0",
            runtime_adapter="pi_ai",
            provider_id="faux",
            model_id="faux_deterministic_v1",
            supported_efforts=(ReasoningEffort.FAST, ReasoningEffort.STANDARD),
            default_effort=ReasoningEffort.STANDARD,
            observed_capabilities=("text", "tool_calls"),
            context_window_tokens=16_384,
            output_token_limit=4_096,
            fallback_order=(GatewayModelKey(provider_id="faux", model_id="fallback"),),
        )
        self._ask_primary_endpoint_profile = self._endpoint_profile
        self._ask_baseline_endpoint_profile = ModelEndpointProfile(
            profile_id=uuid.UUID("44444444-4444-4444-4444-444444444444"),
            profile_version="1.0.0",
            runtime_adapter="pi_ai",
            provider_id="faux",
            model_id="faux_baseline_v1",
            supported_efforts=(ReasoningEffort.FAST, ReasoningEffort.STANDARD),
            default_effort=ReasoningEffort.STANDARD,
            observed_capabilities=("text",),
            context_window_tokens=16_384,
            output_token_limit=4_096,
            fallback_order=(),
        )
        self._catalog_entry = GatewayModelCatalogEntry(
            provider_id="faux",
            model_id="faux_deterministic_v1",
            runtime_adapter="pi_ai",
            observed_capabilities=("text", "tool_calls"),
            supported_reasoning_levels=(ReasoningLevel.LOW, ReasoningLevel.MEDIUM),
            context_window_tokens=16_384,
            output_token_limit=4_096,
        )
        self._ask_baseline_catalog_entry = GatewayModelCatalogEntry(
            provider_id="faux",
            model_id="faux_baseline_v1",
            runtime_adapter="pi_ai",
            observed_capabilities=("text",),
            supported_reasoning_levels=(ReasoningLevel.LOW, ReasoningLevel.MEDIUM),
            context_window_tokens=16_384,
            output_token_limit=4_096,
        )
        self._selection = SelectionSnapshot(
            provider_id="faux",
            model_id="faux_deterministic_v1",
            task_profile_id=self._dungeon_task_profile.profile_id,
            effort=ReasoningEffort.STANDARD,
        )
        self._logins: dict[uuid.UUID, LoginSession] = {}
        self._runs: dict[uuid.UUID, _RunState] = {}
        self._ask_runs: dict[uuid.UUID, _AskRunState] = {}
        self._attachments: dict[uuid.UUID, AskAttachmentRecord] = {}
        self._threads: dict[uuid.UUID, threading.Thread] = {}

    def providers(self) -> tuple[WorkbenchProviderSummary, ...]:
        with self._lock:
            return tuple(
                WorkbenchProviderSummary(
                    provider_id=provider_id,
                    name=data["name"],
                    authenticated=data["authenticated"],
                    auth_modes=data["auth_modes"],
                    models=data["models"],
                )
                for provider_id, data in self._providers.items()
            )

    def task_profiles(self) -> tuple[TaskProfile, ...]:
        return tuple(self._task_profiles.values())

    def selection(self) -> SelectionSnapshot:
        with self._lock:
            return self._selection

    def get_login(self, login_id: uuid.UUID) -> LoginSession | None:
        with self._lock:
            return self._logins.get(login_id)

    def begin_login(self, provider_id: str) -> LoginSession:
        with self._lock:
            if provider_id not in self._providers:
                raise ValueError("unknown provider")
            login = LoginSession(
                login_id=uuid.uuid4(),
                provider_id=provider_id,
                status="pending",
                events=(
                    LoginEvent(
                        type="device_code",
                        user_code="ABCD-1234",
                        verification_uri="https://example.test/device",
                    ),
                    LoginEvent(
                        type="prompt",
                        prompt_id="prompt-1",
                        message="Enter the displayed device code.",
                    ),
                ),
            )
            self._logins[login.login_id] = login
            return login

    def complete_login(self, login_id: uuid.UUID, code: str) -> LoginSession:
        if code.strip() != "ABCD-1234":
            raise ValueError("device code did not match the pending login")
        with self._lock:
            login = self._logins.get(login_id)
            if login is None:
                raise ValueError("unknown login")
            self._providers[login.provider_id]["authenticated"] = True
            completed = LoginSession(
                login_id=login.login_id,
                provider_id=login.provider_id,
                status="completed",
                events=login.events
                + (LoginEvent(type="complete", message="Login complete."),),
            )
            self._logins[login_id] = completed
            return completed

    def logout(self, provider_id: str) -> None:
        with self._lock:
            if provider_id not in self._providers:
                raise ValueError("unknown provider")
            self._providers[provider_id]["authenticated"] = False

    def set_selection(
        self,
        *,
        provider_id: str,
        model_id: str,
        task_profile_id: uuid.UUID,
        effort: ReasoningEffort,
    ) -> SelectionSnapshot:
        with self._lock:
            provider = self._providers.get(provider_id)
            if provider is None:
                raise ValueError("unknown provider")
            if not any(model.model_id == model_id for model in provider["models"]):
                raise ValueError("unknown model")
            if task_profile_id not in self._task_profiles:
                raise ValueError("unknown task profile")
            if effort not in self._endpoint_profile.supported_efforts:
                raise ValueError("unsupported effort")
            self._selection = SelectionSnapshot(
                provider_id=provider_id,
                model_id=model_id,
                task_profile_id=task_profile_id,
                effort=effort,
            )
            return self._selection

    def start_run(self, *, prompt: str) -> RunSnapshot:
        selection = self.selection()
        if selection.task_profile_id != self._dungeon_task_profile.profile_id:
            raise ValueError("unknown task profile")
        run_state = _RunState(
            run_id=uuid.uuid4(),
            prompt=prompt,
            selection=selection,
            status="queued",
            events=[RunEvent(type="queued", message="Run queued.")],
        )
        with self._lock:
            self._runs[run_state.run_id] = run_state
        thread = threading.Thread(
            target=self._run_worker, args=(run_state.run_id,), daemon=True
        )
        self._threads[run_state.run_id] = thread
        thread.start()
        return self.get_run(run_state.run_id)

    def list_attachments(self) -> tuple[AskAttachmentRecord, ...]:
        with self._lock:
            return tuple(
                sorted(
                    self._attachments.values(),
                    key=lambda attachment: attachment.created_at,
                )
            )

    def get_attachment(self, attachment_id: uuid.UUID) -> AskAttachmentRecord | None:
        with self._lock:
            return self._attachments.get(attachment_id)

    def read_attachment(self, attachment_id: uuid.UUID) -> bytes:
        if self._asset_store is None:
            raise ValueError("attachment storage is unavailable")
        record = self.get_attachment(attachment_id)
        if record is None:
            raise ValueError("unknown attachment")
        blob = StoredBlob(
            sha256=record.sha256,
            byte_size=record.byte_size,
            storage_locator=record.storage_locator,
            created=False,
        )
        return self._asset_store.read_bytes(blob)

    def upload_attachment(
        self,
        *,
        filename: str,
        media_type: str,
        data: bytes,
    ) -> AskAttachmentRecord:
        if self._asset_store is None:
            raise ValueError("attachment storage is unavailable")
        if len(data) > 1_000_000:
            raise ValueError("attachment exceeds the allowed size")
        if not (
            media_type.startswith("image/")
            or media_type.startswith("text/")
            or media_type in {"application/json", "application/pdf"}
        ):
            raise ValueError("unsupported attachment media type")
        blob = self._asset_store.put_bytes(data)
        record = AskAttachmentRecord(
            attachment_id=uuid.uuid4(),
            filename=filename,
            media_type=media_type,
            byte_size=blob.byte_size,
            sha256=blob.sha256,
            storage_locator=blob.storage_locator,
            retention_policy="ask_session",
            created_at=datetime.now(UTC),
        )
        with self._lock:
            self._attachments[record.attachment_id] = record
        return record

    def ask(
        self, *, prompt: str, attachment_ids: tuple[uuid.UUID, ...] = ()
    ) -> AskRunSnapshot:
        selection = self.selection()
        with self._lock:
            attachments = tuple(
                self._attachments[attachment_id] for attachment_id in attachment_ids
            )
        run_state = _AskRunState(
            run_id=uuid.uuid4(),
            prompt=prompt,
            attachment_ids=attachment_ids,
            selection=selection,
            status="queued",
            events=[RunEvent(type="queued", message="Ask request queued.")],
        )
        with self._lock:
            self._ask_runs[run_state.run_id] = run_state
        thread = threading.Thread(
            target=self._ask_run_worker,
            args=(run_state.run_id, attachments),
            daemon=True,
        )
        self._threads[run_state.run_id] = thread
        thread.start()
        return self.get_ask_run(run_state.run_id)

    def get_ask_run(self, run_id: uuid.UUID) -> AskRunSnapshot:
        with self._lock:
            run = self._ask_runs.get(run_id)
            if run is None:
                raise ValueError("unknown ask run")
            return self._ask_snapshot(run)

    def list_ask_runs(self) -> tuple[AskRunSnapshot, ...]:
        with self._lock:
            runs = tuple(self._ask_runs.values())
        return tuple(
            sorted(
                (self._ask_snapshot(run) for run in runs), key=lambda item: item.run_id
            )
        )

    def cancel_ask_run(self, run_id: uuid.UUID) -> AskRunSnapshot:
        with self._lock:
            run = self._ask_runs.get(run_id)
            if run is None:
                raise ValueError("unknown ask run")
            if run.status in {"completed", "cancelled", "failed"}:
                return self._ask_snapshot(run)
            run.cancelled.set()
            run.status = "cancelled"
            run.events.append(
                RunEvent(type="cancelled", message="Ask request cancelled.")
            )
            return self._ask_snapshot(run)

    def stream_ask_run_events(self, run_id: uuid.UUID) -> Iterable[RunEvent]:
        seen = 0
        while True:
            snapshot = self.get_ask_run(run_id)
            while seen < len(snapshot.events):
                yield snapshot.events[seen]
                seen += 1
            if snapshot.status in {"completed", "cancelled", "failed"}:
                return
            time.sleep(0.05)

    def cancel_run(self, run_id: uuid.UUID) -> RunSnapshot:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                raise ValueError("unknown run")
            if run.status in {"completed", "cancelled", "failed"}:
                return self._snapshot(run)
            run.cancelled.set()
            run.status = "cancelled"
            run.events.append(RunEvent(type="cancelled", message="Run cancelled."))
            return self._snapshot(run)

    def get_run(self, run_id: uuid.UUID) -> RunSnapshot:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                raise ValueError("unknown run")
            return self._snapshot(run)

    def stream_run_events(self, run_id: uuid.UUID) -> Iterable[RunEvent]:
        seen = 0
        while True:
            snapshot = self.get_run(run_id)
            while seen < len(snapshot.events):
                yield snapshot.events[seen]
                seen += 1
            if snapshot.status in {"completed", "cancelled", "failed"}:
                return
            time.sleep(0.05)

    def _run_worker(self, run_id: uuid.UUID) -> None:
        time.sleep(0.2)
        with self._lock:
            run = self._runs.get(run_id)
            if run is None or run.cancelled.is_set():
                return
            run.status = "running"
            run.events.append(RunEvent(type="running", message="Run started."))
        try:
            output, record = self._execute_bounded_run(run_id)
        except ModelRunAbstained as error:
            with self._lock:
                run = self._runs.get(run_id)
                if run is None:
                    return
                if run.cancelled.is_set():
                    return
                run.status = "failed"
                run.error = str(error)
                run.events.append(RunEvent(type="failed", message=str(error)))
            return
        with self._lock:
            run = self._runs.get(run_id)
            if run is None or run.cancelled.is_set():
                return
            run.status = "completed"
            run.output = output
            run.resolved_profile = record.resolved_profile
            run.events.append(RunEvent(type="completed", message="Run completed."))

    def _execute_bounded_run(
        self, run_id: uuid.UUID
    ) -> tuple[DungeonIntentV1, ModelRunRecord]:
        with self._lock:
            run = self._runs[run_id]
            prompt = run.prompt
            selection = run.selection
        resolved = resolve_run_profile(
            endpoint_profile=self._endpoint_profile,
            task_profile=self._dungeon_task_profile,
            catalog_entry=self._catalog_entry,
            requested_effort=selection.effort,
        )
        input_citations = ("cite-1", "rules-1")
        run_input = ModelRunInput(
            messages=(PromptMessage(role="user", content=prompt),),
            authorized_citation_ids=input_citations,
        )
        client = _SyntheticGatewayClient(prompt=prompt)
        tool = ServerTool(
            name="set_brief",
            description="Validate a synthetic dungeon brief.",
            input_schema=_BriefInput,
            handler=lambda _: build_dungeon_intent_tool_result(
                tool_name="set_brief",
                call_id="call-1",
                payload={"status": "ok"},
                citation_ids=input_citations,
                official_rule_ids=("rules-1",),
            ),
        )
        runner = ModelTaskRunner(client)
        return runner.run(
            profile=resolved,
            run_input=run_input,
            output_schema=DungeonIntentV1,
            tools={tool.name: tool},
        )

    def _ask_run_worker(
        self, run_id: uuid.UUID, attachments: tuple[AskAttachmentRecord, ...]
    ) -> None:
        time.sleep(0.2)
        with self._lock:
            run = self._ask_runs.get(run_id)
            if run is None or run.cancelled.is_set():
                return
            run.status = "running"
            run.events.append(RunEvent(type="running", message="Ask run started."))
        try:
            response, comparison, record = self._execute_ask_run(run_id, attachments)
        except ModelRunAbstained as error:
            with self._lock:
                run = self._ask_runs.get(run_id)
                if run is None or run.cancelled.is_set():
                    return
                run.status = "failed"
                run.error = str(error)
                run.events.append(RunEvent(type="failed", message=str(error)))
            return
        with self._lock:
            run = self._ask_runs.get(run_id)
            if run is None or run.cancelled.is_set():
                return
            run.status = "completed"
            run.response = response
            run.comparison = comparison
            run.resolved_profile = record.resolved_profile
            run.events.append(RunEvent(type="completed", message="Ask run completed."))

    def _execute_ask_run(
        self,
        run_id: uuid.UUID,
        attachments: tuple[AskAttachmentRecord, ...],
    ) -> tuple[AskResponseV1, AskComparisonReport, ModelRunRecord]:
        with self._lock:
            run = self._ask_runs[run_id]
            prompt = run.prompt
            selection = run.selection
        if selection.task_profile_id != self._ask_task_profile.profile_id:
            raise ModelRunAbstained("ask workflow requires the ask task profile")
        selected_model = selection.model_id
        primary_profile = resolve_run_profile(
            endpoint_profile=self._ask_primary_endpoint_profile
            if selected_model == "faux_deterministic_v1"
            else self._ask_baseline_endpoint_profile,
            task_profile=self._ask_task_profile,
            catalog_entry=(
                self._catalog_entry
                if selected_model == "faux_deterministic_v1"
                else self._ask_baseline_catalog_entry
            ),
            requested_effort=selection.effort,
        )
        attachment_ids = tuple(item.attachment_id for item in attachments)
        prompt_digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        response = self._ask_answer(
            model_id=selected_model,
            prompt=prompt,
            attachment_ids=attachment_ids,
            comparison_summary=None,
        )
        baseline_model_id = (
            "faux_baseline_v1"
            if selected_model == "faux_deterministic_v1"
            else "faux_deterministic_v1"
        )
        baseline_profile = resolve_run_profile(
            endpoint_profile=(
                self._ask_baseline_endpoint_profile
                if baseline_model_id == "faux_baseline_v1"
                else self._ask_primary_endpoint_profile
            ),
            task_profile=self._ask_task_profile,
            catalog_entry=(
                self._ask_baseline_catalog_entry
                if baseline_model_id == "faux_baseline_v1"
                else self._catalog_entry
            ),
            requested_effort=selection.effort,
        )
        baseline_answer = self._ask_answer(
            model_id=baseline_model_id,
            prompt=prompt,
            attachment_ids=attachment_ids,
            comparison_summary=None,
        )
        comparison = AskComparisonReport(
            primary_model_id=selected_model,
            baseline_model_id=baseline_model_id,
            prompt_digest=prompt_digest,
            primary_answer=response.answer,
            baseline_answer=baseline_answer.answer,
            summary=(
                f"Primary {selected_model} vs baseline {baseline_model_id}: "
                f"{response.answer} / {baseline_answer.answer}"
            ),
        )
        response = response.model_copy(
            update={"comparison_summary": comparison.summary}
        )
        runner = ModelTaskRunner(_SingleTurnGatewayClient(response))
        primary_run, record = runner.run(
            profile=primary_profile,
            run_input=ModelRunInput(
                messages=(PromptMessage(role="user", content=prompt),),
                authorized_citation_ids=tuple(
                    str(item.attachment_id) for item in attachments
                ),
            ),
            output_schema=AskResponseV1,
            tools={},
        )
        del primary_run, baseline_profile
        return response, comparison, record

    def _snapshot(self, run: _RunState) -> RunSnapshot:
        return RunSnapshot(
            run_id=run.run_id,
            status=run.status,  # type: ignore[arg-type]
            prompt=run.prompt,
            selection={
                "provider_id": run.selection.provider_id,
                "model_id": run.selection.model_id,
                "task_profile_id": str(run.selection.task_profile_id),
                "effort": run.selection.effort.value,
            },
            events=tuple(run.events),
            output=run.output,
            resolved_profile=run.resolved_profile,
            error=run.error,
        )

    def _ask_snapshot(self, run: _AskRunState) -> AskRunSnapshot:
        return AskRunSnapshot(
            run_id=run.run_id,
            status=run.status,  # type: ignore[arg-type]
            prompt=run.prompt,
            attachment_ids=run.attachment_ids,
            events=tuple(run.events),
            response=run.response,
            comparison=run.comparison,
            resolved_profile=run.resolved_profile,
            error=run.error,
        )

    def _ask_answer(
        self,
        *,
        model_id: str,
        prompt: str,
        attachment_ids: tuple[uuid.UUID, ...],
        comparison_summary: str | None,
    ) -> AskResponseV1:
        attachment_labels = ", ".join(str(item) for item in attachment_ids) or "none"
        answer = f"{model_id} answer for: {prompt}. Attachments: {attachment_labels}."
        if comparison_summary is not None:
            answer = f"{answer} {comparison_summary}"
        return AskResponseV1(
            answer=answer,
            citation_ids=tuple(str(item) for item in attachment_ids),
            official_rules=("citation-backed prompt",),
            house_rule_overrides=("comparison baseline visible",),
            unknowns=(),
            conflicts=(),
            attachment_ids=attachment_ids,
        )


class _BriefInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    rooms: int = Field(default=3, ge=1)


class _SyntheticGatewayClient:
    def __init__(self, *, prompt: str) -> None:
        self._prompt = prompt
        self._calls = 0

    def complete(
        self,
        *,
        profile: ResolvedModelRunProfile,
        messages: tuple[PromptMessage, ...],
        allowed_tools: tuple[str, ...],
        tool_schemas: tuple[GatewayToolSchema, ...],
    ) -> GatewayCompletion:
        del profile, allowed_tools, tool_schemas
        self._calls += 1
        if self._calls == 1:
            return GatewayCompletion(
                tool_calls=(
                    ToolCall(
                        tool_name="set_brief",
                        call_id="call-1",
                        arguments={"rooms": 3},
                    ),
                ),
                input_tokens=8,
                output_tokens=4,
            )
        return GatewayCompletion(
            content=DungeonIntentV1(
                intent=f"Synthetic dungeon: {self._prompt}",
                requested_constraints=("single entrance", "low light"),
                citation_ids=("cite-1", "rules-1"),
                official_rules=("five-foot grid",),
                house_rule_overrides=("wider corridors",),
            ).model_dump_json(),
            input_tokens=6,
            output_tokens=12,
        )


class _SingleTurnGatewayClient:
    def __init__(self, final_output: AskResponseV1) -> None:
        self._final_output = final_output
        self._calls = 0

    def complete(
        self,
        *,
        profile: ResolvedModelRunProfile,
        messages: tuple[PromptMessage, ...],
        allowed_tools: tuple[str, ...],
        tool_schemas: tuple[GatewayToolSchema, ...],
    ) -> GatewayCompletion:
        del profile, messages, allowed_tools, tool_schemas
        self._calls += 1
        if self._calls > 1:
            return GatewayCompletion(
                content=self._final_output.model_dump_json(),
                input_tokens=1,
                output_tokens=1,
            )
        return GatewayCompletion(
            content=self._final_output.model_dump_json(),
            input_tokens=8,
            output_tokens=20,
        )
