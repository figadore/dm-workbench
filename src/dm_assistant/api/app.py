"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import Engine

from dm_assistant import __version__
from dm_assistant.adapters.assets import LocalAssetStore
from dm_assistant.adapters.model_gateway import PiGatewayClient
from dm_assistant.adapters.sources import LocalSourceReader
from dm_assistant.api.dungeons import create_dungeon_api_router
from dm_assistant.api.errors import domain_error_handler
from dm_assistant.api.library import create_library_api_router
from dm_assistant.api.middleware import SecurityObservabilityMiddleware
from dm_assistant.campaigns import CampaignCatalog
from dm_assistant.config import ModelGatewayPolicy, Settings, load_settings
from dm_assistant.db import build_engine
from dm_assistant.errors import DomainError, ResourceNotFoundError
from dm_assistant.modules.library.catalog import LibraryDocumentCatalog
from dm_assistant.modules.library.retrieval import LibraryLexicalSearchService
from dm_assistant.modules.library.service import LibraryIngestionService
from dm_assistant.modules.library.snapshots import CorpusSnapshotService
from dm_assistant.modules.library.workflows import LibrarySourceWorkflow
from dm_assistant.modules.modeling import ModelTaskSelectionStore, ModelWorkbenchService
from dm_assistant.modules.preparation import PreparationService
from dm_assistant.observability import configure_logging
from dm_assistant.orchestration.dungeons import (
    DungeonPromptApplicationService,
    DungeonPromptService,
    DungeonPromptWorkbenchService,
    DungeonStudioService,
)
from dm_assistant.readiness import ReadinessCheck, ReadinessReport, check_readiness
from dm_assistant.web import create_web_router

_PUBLIC_PATHS = frozenset({"/health/live", "/health/ready", "/login"})


def create_app(
    settings: Settings | None = None,
    *,
    include_test_routes: bool = False,
    readiness_check: ReadinessCheck | None = None,
    preparation_service: PreparationService | None = None,
    dungeon_studio: DungeonStudioService | None = None,
    campaign_catalog: CampaignCatalog | None = None,
    model_workbench: ModelWorkbenchService | None = None,
    dungeon_prompt_workbench: DungeonPromptWorkbenchService | None = None,
) -> FastAPI:
    """Create the default-authenticated DM Assistant HTTP application."""
    resolved_settings = settings if settings is not None else load_settings()
    configure_logging(
        resolved_settings.log_level.value,
        secret_values=resolved_settings.logging_secret_values(),
    )
    owned_engine: Engine = build_engine(resolved_settings)
    database_engine = owned_engine
    if readiness_check is None:

        def resolved_readiness_check() -> ReadinessReport:
            return check_readiness(database_engine)

    else:
        resolved_readiness_check = readiness_check

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            owned_engine.dispose()

    application = FastAPI(
        title="DM Assistant",
        version=__version__,
        lifespan=lifespan,
    )
    resolved_preparation = preparation_service or PreparationService(
        database_engine,
        LocalAssetStore(resolved_settings.asset_root, resolved_settings.scratch_root),
    )
    resolved_dungeons = dungeon_studio or DungeonStudioService(resolved_preparation)
    resolved_campaigns = campaign_catalog or CampaignCatalog(database_engine)
    resolved_model_workbench = model_workbench or ModelWorkbenchService(
        asset_store=LocalAssetStore(
            resolved_settings.asset_root, resolved_settings.scratch_root
        )
    )
    gateway = (
        None
        if resolved_settings.model_gateway_policy is ModelGatewayPolicy.DISABLED
        else PiGatewayClient.from_settings(resolved_settings)
    )
    resolved_dungeon_prompt_workbench = dungeon_prompt_workbench or (
        DungeonPromptWorkbenchService(
            settings=resolved_settings,
            campaigns=resolved_campaigns,
            selections=ModelTaskSelectionStore(database_engine),
            gateway=gateway,
            prompts=DungeonPromptService(resolved_dungeons, gateway),
            preparation=resolved_preparation,
            applications=DungeonPromptApplicationService(
                resolved_preparation, DungeonPromptService(resolved_dungeons, gateway)
            ),
        )
        if gateway is not None
        else None
    )
    library_catalog = LibraryDocumentCatalog(database_engine)
    library_search = LibraryLexicalSearchService(database_engine)
    library_ingestion = LibraryIngestionService(
        database_engine,
        LocalSourceReader(
            {
                f"root-{index}": path
                for index, path in enumerate(resolved_settings.source_roots)
            }
        ),
    )
    library_sources = LibrarySourceWorkflow(
        library_ingestion,
        CorpusSnapshotService(database_engine),
    )
    application.state.settings = resolved_settings
    application.state.readiness_check = resolved_readiness_check
    application.state.preparation_service = resolved_preparation
    application.state.dungeon_studio = resolved_dungeons
    application.state.model_workbench = resolved_model_workbench
    application.state.dungeon_prompt_workbench = resolved_dungeon_prompt_workbench
    application.add_middleware(
        SecurityObservabilityMiddleware,
        settings=resolved_settings,
        public_paths=_PUBLIC_PATHS,
    )
    application.add_exception_handler(DomainError, domain_error_handler)
    application.include_router(create_dungeon_api_router(resolved_dungeons))
    application.include_router(
        create_library_api_router(
            library_catalog,
            library_search,
            library_sources,
        )
    )
    application.include_router(
        create_web_router(
            settings=resolved_settings,
            campaigns=resolved_campaigns,
            dungeons=resolved_dungeons,
            preparation=resolved_preparation,
            model_workbench=resolved_model_workbench,
            dungeon_prompt_workbench=resolved_dungeon_prompt_workbench,
        )
    )

    @application.get("/health/live", tags=["health"])
    def health_live() -> dict[str, str]:
        return {"status": "live"}

    @application.get("/health/ready", tags=["health"])
    def health_ready() -> JSONResponse:
        report = resolved_readiness_check()
        return JSONResponse(
            status_code=200 if report.ready else 503,
            content=report.health_payload(),
        )

    if include_test_routes:

        @application.get("/__test__/protected", include_in_schema=False)
        async def protected_test_route(request: Request) -> dict[str, str]:
            principal = request.state.principal
            return {
                "principal_id": principal.id,
                "scope": principal.scope,
                "request_id": request.state.request_id,
            }

        @application.get("/__test__/missing", include_in_schema=False)
        async def missing_test_route() -> None:
            raise ResourceNotFoundError()

    return application
