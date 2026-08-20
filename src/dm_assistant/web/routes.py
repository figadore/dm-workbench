"""Thin authenticated server-rendered Workbench and Dungeon Studio routes."""

import uuid
from collections.abc import Iterable
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import (
    HTMLResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)
from fastapi.templating import Jinja2Templates

from dm_assistant.auth import (
    SESSION_COOKIE_NAME,
    BrowserSession,
    SessionCodec,
    authenticate_bearer_token,
    csrf_matches,
)
from dm_assistant.campaigns import CampaignCatalog
from dm_assistant.config import RuntimeEnvironment, Settings
from dm_assistant.errors import ForbiddenError, InvalidInputError
from dm_assistant.modules.modeling import ReasoningEffort
from dm_assistant.modules.modeling.workbench import ModelWorkbenchService
from dm_assistant.modules.preparation import PreparationService
from dm_assistant.orchestration.dungeons import (
    CreateDungeonWorkflow,
    DungeonPromptWorkbenchService,
    DungeonStudioService,
    ExportDungeonWorkflow,
    RegenerateDungeonWorkflow,
)
from dm_dungeon import load_layout_request_json

_TEMPLATES = Jinja2Templates(directory=Path(__file__).parent / "templates")
_MAX_LAYOUT_DOCUMENT_CHARS = 2_000_000


def create_web_router(
    *,
    settings: Settings,
    campaigns: CampaignCatalog,
    dungeons: DungeonStudioService,
    preparation: PreparationService,
    model_workbench: ModelWorkbenchService | None = None,
    dungeon_prompt_workbench: DungeonPromptWorkbenchService | None = None,
) -> APIRouter:
    """Build the shared shell using injected application services only."""
    router = APIRouter(include_in_schema=False)
    session_codec = SessionCodec(settings.session_secret)
    resolved_model_workbench = model_workbench or ModelWorkbenchService()
    resolved_dungeon_prompt_workbench = dungeon_prompt_workbench

    @router.get("/login", response_class=HTMLResponse)
    def login_page(request: Request) -> HTMLResponse:
        return _template(request, "login.html", {})

    @router.post("/login", response_class=HTMLResponse)
    def login_submit(request: Request, token: Annotated[str, Form()]) -> Response:
        principal = authenticate_bearer_token(
            f"Bearer {token}",
            settings.api_token,
        )
        if principal is None:
            return _template(
                request,
                "login.html",
                {"error": "Authentication failed."},
                status_code=401,
            )
        cookie, _ = session_codec.issue()
        response = RedirectResponse("/dungeons", status_code=303)
        response.set_cookie(
            SESSION_COOKIE_NAME,
            cookie,
            max_age=12 * 60 * 60,
            httponly=True,
            secure=settings.environment is RuntimeEnvironment.PRODUCTION,
            samesite="strict",
            path="/",
        )
        return response

    @router.post("/logout")
    def logout(
        request: Request,
        csrf_token: Annotated[str, Form()],
    ) -> Response:
        _require_csrf(request, csrf_token)
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie(SESSION_COOKIE_NAME, path="/")
        return response

    @router.get("/")
    def home() -> RedirectResponse:
        return RedirectResponse("/dungeons", status_code=303)

    @router.get("/dungeons", response_class=HTMLResponse)
    def dungeon_list(
        request: Request,
        campaign_id: uuid.UUID | None = None,
        login_id: uuid.UUID | None = None,
        gateway_login_id: str | None = None,
        run_id: uuid.UUID | None = None,
    ) -> HTMLResponse:
        available = campaigns.list_campaigns()
        active = next((item for item in available if item.active), None)
        if active is None:
            active = campaigns.ensure_active_campaign()
            available = campaigns.list_campaigns()
        selected = campaign_id or active.id
        artifacts = preparation.list_artifacts(selected)
        login = (
            resolved_model_workbench.get_login(login_id)
            if login_id is not None
            else None
        )
        active_run = None
        return _template(
            request,
            "dungeons.html",
            {
                "campaigns": available,
                "selected_campaign_id": selected,
                "artifacts": artifacts,
                "model_providers": resolved_model_workbench.providers(),
                "model_selection": resolved_model_workbench.selection(),
                "model_task_profiles": resolved_model_workbench.task_profiles(),
                "model_login": login,
                "model_active_run": active_run.model_dump(mode="json")
                if active_run
                else None,
                "dungeon_prompt_available": resolved_dungeon_prompt_workbench
                is not None,
                "dungeon_prompt_providers": (
                    resolved_dungeon_prompt_workbench.providers()
                    if resolved_dungeon_prompt_workbench is not None
                    else ()
                ),
                "dungeon_prompt_selection": (
                    resolved_dungeon_prompt_workbench.selection()
                    if resolved_dungeon_prompt_workbench is not None
                    else None
                ),
                "dungeon_prompt_run": (
                    resolved_dungeon_prompt_workbench.get(run_id)
                    if resolved_dungeon_prompt_workbench is not None
                    and run_id is not None
                    else None
                ),
                "dungeon_prompt_login": (
                    resolved_dungeon_prompt_workbench.login_status(gateway_login_id)
                    if resolved_dungeon_prompt_workbench is not None
                    and gateway_login_id is not None
                    else None
                ),
            },
        )

    @router.get("/ask", response_class=HTMLResponse)
    def ask_page(
        request: Request,
        campaign_id: uuid.UUID | None = None,
        run_id: uuid.UUID | None = None,
    ) -> HTMLResponse:
        active_run = (
            resolved_model_workbench.get_ask_run(run_id) if run_id is not None else None
        )
        return _template(
            request,
            "ask.html",
            {
                "campaign_id": campaign_id,
                "model_providers": resolved_model_workbench.providers(),
                "model_selection": resolved_model_workbench.selection(),
                "model_task_profiles": resolved_model_workbench.task_profiles(),
                "attachments": resolved_model_workbench.list_attachments(),
                "ask_history": [
                    item.model_dump(mode="json")
                    for item in resolved_model_workbench.list_ask_runs()
                ],
                "ask_active_run": active_run.model_dump(mode="json")
                if active_run
                else None,
            },
        )

    @router.post("/ask/attachments")
    async def ask_upload_attachment(
        request: Request,
        file: Annotated[UploadFile, File()],
        csrf_token: Annotated[str, Form()],
        campaign_id: Annotated[uuid.UUID | None, Form()] = None,
    ) -> RedirectResponse:
        _require_csrf(request, csrf_token)
        data = await file.read()
        resolved_model_workbench.upload_attachment(
            filename=file.filename or "upload.bin",
            media_type=file.content_type or "application/octet-stream",
            data=data,
        )
        return RedirectResponse(
            _ask_url(campaign_id=campaign_id),
            status_code=303,
        )

    @router.get("/ask/attachments/{attachment_id}")
    def ask_download_attachment(attachment_id: uuid.UUID) -> Response:
        record = resolved_model_workbench.get_attachment(attachment_id)
        if record is None:
            raise InvalidInputError("The attachment was not found.")
        data = resolved_model_workbench.read_attachment(attachment_id)
        disposition = (
            "inline" if record.media_type.startswith("image/") else "attachment"
        )
        return Response(
            content=data,
            media_type=record.media_type,
            headers={
                "Content-Disposition": (f'{disposition}; filename="{record.filename}"'),
                "X-Content-Type-Options": "nosniff",
            },
        )

    @router.post("/ask/runs")
    def ask_start(
        request: Request,
        prompt: Annotated[str, Form()],
        csrf_token: Annotated[str, Form()],
        attachment_ids: Annotated[list[uuid.UUID] | None, Form()] = None,
        campaign_id: Annotated[uuid.UUID | None, Form()] = None,
    ) -> RedirectResponse:
        _require_csrf(request, csrf_token)
        run = resolved_model_workbench.ask(
            prompt=prompt,
            attachment_ids=tuple(attachment_ids or ()),
        )
        return RedirectResponse(
            _ask_url(campaign_id=campaign_id, run_id=run.run_id),
            status_code=303,
        )

    @router.post("/ask/runs/{run_id}/cancel")
    def ask_cancel(
        request: Request,
        run_id: uuid.UUID,
        csrf_token: Annotated[str, Form()],
        campaign_id: Annotated[uuid.UUID | None, Form()] = None,
    ) -> RedirectResponse:
        _require_csrf(request, csrf_token)
        resolved_model_workbench.cancel_ask_run(run_id)
        return RedirectResponse(
            _ask_url(campaign_id=campaign_id, run_id=run_id),
            status_code=303,
        )

    @router.get("/ask/runs/{run_id}/events")
    def ask_events(run_id: uuid.UUID) -> StreamingResponse:
        def iterator() -> Iterable[bytes]:
            for event in resolved_model_workbench.stream_ask_run_events(run_id):
                yield f"data: {event.model_dump_json()}\n\n".encode()

        return StreamingResponse(
            iterator(),
            media_type="text/event-stream; charset=utf-8",
            headers={"Cache-Control": "no-store"},
        )

    @router.post("/modeling/logins")
    def model_login_start(
        request: Request,
        provider_id: Annotated[str, Form()],
        csrf_token: Annotated[str, Form()],
        campaign_id: Annotated[uuid.UUID | None, Form()] = None,
    ) -> RedirectResponse:
        _require_csrf(request, csrf_token)
        login = resolved_model_workbench.begin_login(provider_id)
        return RedirectResponse(
            _dungeons_url(campaign_id=campaign_id, login_id=login.login_id),
            status_code=303,
        )

    @router.post("/modeling/logins/{login_id}")
    def model_login_complete(
        request: Request,
        login_id: uuid.UUID,
        code: Annotated[str, Form()],
        csrf_token: Annotated[str, Form()],
        campaign_id: Annotated[uuid.UUID | None, Form()] = None,
    ) -> RedirectResponse:
        _require_csrf(request, csrf_token)
        login = resolved_model_workbench.complete_login(login_id, code)
        return RedirectResponse(
            _dungeons_url(campaign_id=campaign_id, login_id=login.login_id),
            status_code=303,
        )

    @router.post("/modeling/logout")
    def model_logout(
        request: Request,
        provider_id: Annotated[str, Form()],
        csrf_token: Annotated[str, Form()],
        campaign_id: Annotated[uuid.UUID | None, Form()] = None,
    ) -> RedirectResponse:
        _require_csrf(request, csrf_token)
        resolved_model_workbench.logout(provider_id)
        return RedirectResponse(
            _dungeons_url(campaign_id=campaign_id),
            status_code=303,
        )

    @router.post("/modeling/selection")
    def model_selection(
        request: Request,
        provider_id: Annotated[str, Form()],
        model_id: Annotated[str, Form()],
        task_profile_id: Annotated[uuid.UUID, Form()],
        effort: Annotated[str, Form()],
        csrf_token: Annotated[str, Form()],
        campaign_id: Annotated[uuid.UUID | None, Form()] = None,
    ) -> RedirectResponse:
        _require_csrf(request, csrf_token)
        resolved_model_workbench.set_selection(
            provider_id=provider_id,
            model_id=model_id,
            task_profile_id=task_profile_id,
            effort=ReasoningEffort(effort),
        )
        return RedirectResponse(
            _dungeons_url(campaign_id=campaign_id),
            status_code=303,
        )

    @router.post("/modeling/runs")
    def model_run_start(
        request: Request,
        prompt: Annotated[str, Form()],
        csrf_token: Annotated[str, Form()],
        campaign_id: Annotated[uuid.UUID | None, Form()] = None,
    ) -> RedirectResponse:
        _require_csrf(request, csrf_token)
        run = resolved_model_workbench.start_run(prompt=prompt)
        return RedirectResponse(
            _dungeons_url(campaign_id=campaign_id, run_id=run.run_id),
            status_code=303,
        )

    @router.post("/modeling/runs/{run_id}/cancel")
    def model_run_cancel(
        request: Request,
        run_id: uuid.UUID,
        csrf_token: Annotated[str, Form()],
        campaign_id: Annotated[uuid.UUID | None, Form()] = None,
    ) -> RedirectResponse:
        _require_csrf(request, csrf_token)
        resolved_model_workbench.cancel_run(run_id)
        return RedirectResponse(
            _dungeons_url(campaign_id=campaign_id, run_id=run_id),
            status_code=303,
        )

    @router.get("/modeling/runs/{run_id}/events")
    def model_run_events(run_id: uuid.UUID) -> StreamingResponse:
        def iterator() -> Iterable[bytes]:
            for event in resolved_model_workbench.stream_run_events(run_id):
                yield f"data: {event.model_dump_json()}\n\n".encode()

        return StreamingResponse(
            iterator(),
            media_type="text/event-stream; charset=utf-8",
            headers={"Cache-Control": "no-store"},
        )

    @router.post("/dungeons/model-logins")
    def dungeon_model_login_start(
        request: Request,
        campaign_id: Annotated[uuid.UUID, Form()],
        provider_id: Annotated[str, Form()],
        csrf_token: Annotated[str, Form()],
    ) -> RedirectResponse:
        _require_csrf(request, csrf_token)
        if resolved_dungeon_prompt_workbench is None:
            raise InvalidInputError("Model generation is unavailable.")
        login = resolved_dungeon_prompt_workbench.begin_login(provider_id)
        return RedirectResponse(
            _dungeons_url(campaign_id=campaign_id, gateway_login_id=login.login_id),
            status_code=303,
        )

    @router.post("/dungeons/model-logins/{login_id}/prompts/{prompt_id}")
    def dungeon_model_login_respond(
        request: Request,
        login_id: str,
        prompt_id: str,
        campaign_id: Annotated[uuid.UUID, Form()],
        value: Annotated[str, Form()],
        csrf_token: Annotated[str, Form()],
    ) -> RedirectResponse:
        _require_csrf(request, csrf_token)
        if resolved_dungeon_prompt_workbench is None:
            raise InvalidInputError("Model generation is unavailable.")
        resolved_dungeon_prompt_workbench.respond_to_login(login_id, prompt_id, value)
        return RedirectResponse(
            _dungeons_url(campaign_id=campaign_id, gateway_login_id=login_id),
            status_code=303,
        )

    @router.post("/dungeons/prompts")
    def dungeon_prompt_start(
        request: Request,
        campaign_id: Annotated[uuid.UUID, Form()],
        prompt: Annotated[str, Form()],
        csrf_token: Annotated[str, Form()],
        provider_id: Annotated[str | None, Form()] = None,
        model_id: Annotated[str | None, Form()] = None,
        effort: Annotated[str | None, Form()] = None,
        seed: Annotated[int | None, Form()] = None,
        title: Annotated[str | None, Form()] = None,
        constraint: Annotated[list[str] | None, Form()] = None,
    ) -> RedirectResponse:
        _require_csrf(request, csrf_token)
        if resolved_dungeon_prompt_workbench is None:
            raise InvalidInputError(
                "Model generation is unavailable; manual Dungeon Studio operations remain available."
            )
        run = resolved_dungeon_prompt_workbench.start(
            campaign_id=campaign_id,
            prompt=prompt,
            provider_id=provider_id or None,
            model_id=model_id or None,
            effort=ReasoningEffort(effort) if effort else None,
            seed=seed,
            title=title or None,
            constraints=tuple(constraint or ()),
        )
        return RedirectResponse(
            _dungeons_url(campaign_id=campaign_id, run_id=run.run_id), status_code=303
        )

    @router.post("/dungeons/prompts/{run_id}/cancel")
    def dungeon_prompt_cancel(
        request: Request,
        run_id: uuid.UUID,
        csrf_token: Annotated[str, Form()],
        campaign_id: Annotated[uuid.UUID, Form()],
    ) -> RedirectResponse:
        _require_csrf(request, csrf_token)
        if resolved_dungeon_prompt_workbench is None:
            raise InvalidInputError("Model generation is unavailable.")
        resolved_dungeon_prompt_workbench.cancel(run_id)
        return RedirectResponse(
            _dungeons_url(campaign_id=campaign_id, run_id=run_id), status_code=303
        )

    @router.get("/dungeons/prompts/{run_id}/events")
    def dungeon_prompt_events(run_id: uuid.UUID) -> StreamingResponse:
        if resolved_dungeon_prompt_workbench is None:
            raise InvalidInputError("Model generation is unavailable.")

        def iterator() -> Iterable[bytes]:
            for event in resolved_dungeon_prompt_workbench.stream_events(run_id):
                yield f"data: {event.model_dump_json()}\\n\\n".encode()

        return StreamingResponse(
            iterator(),
            media_type="text/event-stream; charset=utf-8",
            headers={"Cache-Control": "no-store"},
        )

    @router.post("/dungeons/model-selection")
    def dungeon_model_selection(
        request: Request,
        campaign_id: Annotated[uuid.UUID, Form()],
        provider_id: Annotated[str, Form()],
        model_id: Annotated[str, Form()],
        effort: Annotated[str, Form()],
        csrf_token: Annotated[str, Form()],
    ) -> RedirectResponse:
        _require_csrf(request, csrf_token)
        if resolved_dungeon_prompt_workbench is None:
            raise InvalidInputError("Model generation is unavailable.")
        resolved_dungeon_prompt_workbench.save_selection(
            provider_id=provider_id, model_id=model_id, effort=ReasoningEffort(effort)
        )
        return RedirectResponse(_dungeons_url(campaign_id=campaign_id), status_code=303)

    @router.post("/campaigns")
    def campaign_create(
        request: Request,
        name: Annotated[str, Form()],
        csrf_token: Annotated[str, Form()],
    ) -> RedirectResponse:
        _require_csrf(request, csrf_token)
        campaign = campaigns.create_campaign(name)
        return RedirectResponse(
            f"/dungeons?campaign_id={campaign.id}",
            status_code=303,
        )

    @router.post("/dungeons/generate", response_class=HTMLResponse)
    def dungeon_generate(
        request: Request,
        campaign_id: Annotated[uuid.UUID, Form()],
        title: Annotated[str, Form()],
        layout_request_json: Annotated[str, Form()],
        csrf_token: Annotated[str, Form()],
    ) -> Response:
        _require_csrf(request, csrf_token)
        if len(layout_request_json) > _MAX_LAYOUT_DOCUMENT_CHARS:
            raise InvalidInputError("The layout request is too large.")
        try:
            layout_request = load_layout_request_json(layout_request_json)
        except ValueError:
            raise InvalidInputError("The layout request is invalid.") from None
        result = dungeons.create(
            CreateDungeonWorkflow(
                campaign_id=campaign_id,
                title=title,
                layout_request=layout_request,
                created_by="dm",
            )
        )
        if result.artifact_version_id is None:
            return _template(
                request,
                "workflow_failure.html",
                {"result": result},
                status_code=422,
            )
        return RedirectResponse(
            f"/dungeons/{result.artifact_id}?campaign_id={campaign_id}",
            status_code=303,
        )

    @router.get("/dungeons/{artifact_id}", response_class=HTMLResponse)
    def dungeon_detail(
        request: Request,
        artifact_id: uuid.UUID,
        campaign_id: uuid.UUID,
    ) -> HTMLResponse:
        detail = dungeons.inspect(campaign_id=campaign_id, artifact_id=artifact_id)
        versions = preparation.list_versions(campaign_id, artifact_id)
        version_assets = {
            version.id: preparation.list_assets(campaign_id, version.id)
            for version in versions
        }
        dm_notes_by_version = {
            version.id: dungeons.notes_for_version(
                campaign_id=campaign_id, artifact_version_id=version.id
            )
            for version in versions
        }
        dm_guides_by_version = {
            version.id: dungeons.guide_for_version(
                campaign_id=campaign_id, artifact_version_id=version.id
            )
            for version in versions
        }
        generation_runs = {
            version.id: (
                preparation.get_generation_run(campaign_id, version.generation_run_id)
                if version.generation_run_id is not None
                else None
            )
            for version in versions
        }
        return _template(
            request,
            "dungeon_detail.html",
            {
                "campaign_id": campaign_id,
                "detail": detail,
                "versions": versions,
                "version_assets": version_assets,
                "dm_notes_by_version": dm_notes_by_version,
                "dm_guides_by_version": dm_guides_by_version,
                "generation_runs": generation_runs,
            },
        )

    @router.post("/dungeons/{artifact_id}/regenerate")
    def dungeon_regenerate(
        request: Request,
        artifact_id: uuid.UUID,
        campaign_id: Annotated[uuid.UUID, Form()],
        parent_version_id: Annotated[uuid.UUID, Form()],
        seed: Annotated[int, Form()],
        locked_component_ids: Annotated[str, Form()] = "",
        change_summary: Annotated[str, Form()] = "Regenerate dungeon.",
        csrf_token: Annotated[str, Form()] = "",
    ) -> Response:
        _require_csrf(request, csrf_token)
        locks = tuple(
            item.strip() for item in locked_component_ids.split(",") if item.strip()
        )
        result = dungeons.regenerate(
            RegenerateDungeonWorkflow(
                campaign_id=campaign_id,
                artifact_id=artifact_id,
                parent_version_id=parent_version_id,
                seed=seed,
                locked_component_ids=locks,
                change_summary=change_summary,
                created_by="dm",
            )
        )
        if result.artifact_version_id is None:
            return _template(
                request,
                "workflow_failure.html",
                {"result": result},
                status_code=422,
            )
        return RedirectResponse(
            f"/dungeons/{artifact_id}?campaign_id={campaign_id}",
            status_code=303,
        )

    @router.post("/dungeons/{artifact_id}/export")
    def dungeon_export(
        request: Request,
        artifact_id: uuid.UUID,
        campaign_id: Annotated[uuid.UUID, Form()],
        artifact_version_id: Annotated[uuid.UUID, Form()],
        export_format: Annotated[Literal["roll20", "pdf"], Form()] = "roll20",
        csrf_token: Annotated[str, Form()] = "",
    ) -> RedirectResponse:
        _require_csrf(request, csrf_token)
        dungeons.export(
            ExportDungeonWorkflow(
                campaign_id=campaign_id,
                artifact_version_id=artifact_version_id,
                export_format=export_format,
            )
        )
        return RedirectResponse(
            f"/dungeons/{artifact_id}?campaign_id={campaign_id}",
            status_code=303,
        )

    @router.post("/dungeons/{artifact_id}/approve")
    def dungeon_approve(
        request: Request,
        artifact_id: uuid.UUID,
        campaign_id: Annotated[uuid.UUID, Form()],
        artifact_version_id: Annotated[uuid.UUID, Form()],
        reason: Annotated[str, Form()],
        csrf_token: Annotated[str, Form()],
    ) -> RedirectResponse:
        _require_csrf(request, csrf_token)
        dungeons.approve(
            campaign_id=campaign_id,
            artifact_id=artifact_id,
            artifact_version_id=artifact_version_id,
            actor="dm",
            reason=reason,
        )
        return RedirectResponse(
            f"/dungeons/{artifact_id}?campaign_id={campaign_id}",
            status_code=303,
        )

    @router.get("/dungeons/{artifact_id}/compare", response_class=HTMLResponse)
    def dungeon_compare(
        request: Request,
        artifact_id: uuid.UUID,
        campaign_id: uuid.UUID,
        left: uuid.UUID,
        right: uuid.UUID,
    ) -> HTMLResponse:
        comparison = dungeons.compare(
            campaign_id=campaign_id,
            left_version_id=left,
            right_version_id=right,
        )
        return _template(
            request,
            "dungeon_compare.html",
            {
                "artifact_id": artifact_id,
                "campaign_id": campaign_id,
                "comparison": comparison,
            },
        )

    @router.get("/assets/{asset_id}")
    def download_asset(
        asset_id: uuid.UUID,
        campaign_id: uuid.UUID,
    ) -> Response:
        record, data = preparation.read_asset(
            campaign_id,
            asset_id,
            maximum_bytes=100 * 1024 * 1024,
        )
        disposition = (
            "inline" if record.media_type.startswith("image/") else "attachment"
        )
        extension = _media_extension(record.media_type)
        return Response(
            content=data,
            media_type=record.media_type,
            headers={
                "Content-Disposition": (
                    f'{disposition}; filename="asset-{record.id}.{extension}"'
                ),
                "X-Content-Type-Options": "nosniff",
            },
        )

    return router


def _require_csrf(request: Request, supplied: str | None) -> None:
    if getattr(request.state, "auth_method", None) == "bearer":
        return
    session = getattr(request.state, "browser_session", None)
    if not isinstance(session, BrowserSession) or not csrf_matches(supplied, session):
        raise ForbiddenError("CSRF validation failed.")


def _template(
    request: Request,
    name: str,
    context: dict[str, object],
    *,
    status_code: int = 200,
) -> HTMLResponse:
    session = getattr(request.state, "browser_session", None)
    rendered_context = {
        "request": request,
        "csrf_token": session.csrf_token if isinstance(session, BrowserSession) else "",
        **context,
    }
    response = _TEMPLATES.TemplateResponse(
        request=request,
        name=name,
        context=rendered_context,
        status_code=status_code,
    )
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self'; connect-src 'self'; "
        "script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
        "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    )
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def _dungeons_url(
    *,
    campaign_id: uuid.UUID | None = None,
    login_id: uuid.UUID | None = None,
    gateway_login_id: str | None = None,
    run_id: uuid.UUID | None = None,
) -> str:
    params: list[str] = []
    if campaign_id is not None:
        params.append(f"campaign_id={campaign_id}")
    if login_id is not None:
        params.append(f"login_id={login_id}")
    if gateway_login_id is not None:
        params.append(f"gateway_login_id={quote(gateway_login_id, safe='')}")
    if run_id is not None:
        params.append(f"run_id={run_id}")
    query = f"?{'&'.join(params)}" if params else ""
    return f"/dungeons{query}"


def _ask_url(
    *,
    campaign_id: uuid.UUID | None = None,
    run_id: uuid.UUID | None = None,
) -> str:
    params: list[str] = []
    if campaign_id is not None:
        params.append(f"campaign_id={campaign_id}")
    if run_id is not None:
        params.append(f"run_id={run_id}")
    query = f"?{'&'.join(params)}" if params else ""
    return f"/ask{query}"


def _media_extension(media_type: str) -> str:
    return {
        "application/json": "json",
        "application/pdf": "pdf",
        "application/zip": "zip",
        "image/png": "png",
        "image/svg+xml": "svg",
    }.get(media_type, "bin")
