"""Authenticated JSON adapter for provider-independent Dungeon Studio services."""

import json
import uuid

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from dm_assistant.auth import BrowserSession, csrf_matches
from dm_assistant.errors import ForbiddenError, InvalidInputError
from dm_assistant.modules.preparation import ArtifactRecord
from dm_assistant.orchestration.dungeons import (
    ApproveDungeonWorkflow,
    CreateDungeonWorkflow,
    DungeonStudioDetail,
    DungeonStudioService,
    DungeonVersionComparison,
    DungeonWorkflowResult,
    ExportDungeonWorkflow,
    RegenerateDungeonWorkflow,
)
from dm_dungeon import load_layout_request_json


class GenerateDungeonApiRequest(BaseModel):
    """JSON transport wrapper; the pure request validates in JSON mode."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    campaign_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    layout_request: dict[str, JsonValue]
    created_by: str = Field(min_length=1, max_length=200)


def create_dungeon_api_router(dungeons: DungeonStudioService) -> APIRouter:
    router = APIRouter(prefix="/api/dungeons", tags=["dungeon-studio"])

    @router.get("")
    def list_artifacts(campaign_id: uuid.UUID) -> tuple[ArtifactRecord, ...]:
        return dungeons.list_artifacts(campaign_id)

    @router.post("/generate")
    def generate(
        command: GenerateDungeonApiRequest,
        request: Request,
    ) -> DungeonWorkflowResult:
        _require_api_csrf(request)
        try:
            layout_request = load_layout_request_json(
                json.dumps(command.layout_request, separators=(",", ":"))
            )
        except ValueError:
            raise InvalidInputError("The layout request is invalid.") from None
        return dungeons.create(
            CreateDungeonWorkflow(
                campaign_id=command.campaign_id,
                title=command.title,
                layout_request=layout_request,
                created_by=command.created_by,
            )
        )

    @router.post("/regenerate")
    def regenerate(
        command: RegenerateDungeonWorkflow,
        request: Request,
    ) -> DungeonWorkflowResult:
        _require_api_csrf(request)
        return dungeons.regenerate(command)

    @router.post("/export")
    def export(
        command: ExportDungeonWorkflow,
        request: Request,
    ) -> dict[str, list[str]]:
        _require_api_csrf(request)
        return {"asset_ids": [str(item) for item in dungeons.export(command)]}

    @router.post("/approve")
    def approve(
        command: ApproveDungeonWorkflow,
        request: Request,
    ) -> DungeonStudioDetail:
        _require_api_csrf(request)
        return dungeons.approve(
            campaign_id=command.campaign_id,
            artifact_id=command.artifact_id,
            artifact_version_id=command.artifact_version_id,
            actor=command.actor,
            reason=command.reason,
        )

    @router.get("/{artifact_id}")
    def inspect_artifact(
        artifact_id: uuid.UUID,
        campaign_id: uuid.UUID,
    ) -> DungeonStudioDetail:
        return dungeons.inspect(campaign_id=campaign_id, artifact_id=artifact_id)

    @router.get("/{artifact_id}/compare")
    def compare(
        artifact_id: uuid.UUID,
        campaign_id: uuid.UUID,
        left: uuid.UUID,
        right: uuid.UUID,
    ) -> DungeonVersionComparison:
        del artifact_id
        return dungeons.compare(
            campaign_id=campaign_id,
            left_version_id=left,
            right_version_id=right,
        )

    return router


def _require_api_csrf(request: Request) -> None:
    if getattr(request.state, "auth_method", None) == "bearer":
        return
    session = getattr(request.state, "browser_session", None)
    supplied = request.headers.get("X-CSRF-Token")
    if not isinstance(session, BrowserSession) or not csrf_matches(supplied, session):
        raise ForbiddenError("CSRF validation failed.")
