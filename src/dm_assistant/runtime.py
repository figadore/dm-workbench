"""Composition root helpers shared by CLI and HTTP application adapters."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy import Engine

from dm_assistant.adapters.assets import LocalAssetStore
from dm_assistant.adapters.model_gateway import PiGatewayClient
from dm_assistant.adapters.sources import LocalSourceReader
from dm_assistant.campaigns import CampaignCatalog
from dm_assistant.config import ModelGatewayPolicy, Settings, load_settings
from dm_assistant.db import build_engine
from dm_assistant.modules.library.catalog import LibraryDocumentCatalog
from dm_assistant.modules.library.retrieval import LibraryLexicalSearchService
from dm_assistant.modules.library.service import LibraryIngestionService
from dm_assistant.modules.library.snapshots import CorpusSnapshotService
from dm_assistant.modules.library.workflows import LibrarySourceWorkflow
from dm_assistant.modules.modeling import ModelTaskSelectionStore
from dm_assistant.modules.preparation import PreparationService
from dm_assistant.observability import configure_logging
from dm_assistant.orchestration.dungeons import (
    DungeonExplorationPromptApplicationService,
    DungeonExplorationPromptService,
    DungeonFeatureInteractionPromptApplicationService,
    DungeonFeatureInteractionPromptService,
    DungeonObjectivePromptApplicationService,
    DungeonObjectivePromptService,
    DungeonPromptApplicationService,
    DungeonPromptService,
    DungeonPuzzlePromptApplicationService,
    DungeonPuzzlePromptService,
    DungeonRoomNarrativePromptApplicationService,
    DungeonRoomNarrativePromptService,
    DungeonStagedEnrichmentChainCoordinator,
    DungeonStagedEnrichmentCoordinator,
    DungeonStudioService,
    DungeonTierACanaryApplicationService,
    DungeonTierAFixedCaseApplicationService,
    DungeonTrapPromptApplicationService,
    DungeonTrapPromptService,
)


@dataclass(frozen=True, slots=True)
class WorkbenchRuntime:
    settings: Settings
    engine: Engine
    campaigns: CampaignCatalog
    preparation: PreparationService
    dungeons: DungeonStudioService
    model_gateway: PiGatewayClient | None
    dungeon_prompts: DungeonPromptService | None
    dungeon_prompt_application: DungeonPromptApplicationService | None
    dungeon_canary_application: DungeonTierACanaryApplicationService | None
    dungeon_fixed_case_application: DungeonTierAFixedCaseApplicationService | None
    model_selections: ModelTaskSelectionStore
    library_catalog: LibraryDocumentCatalog
    library_ingestion: LibraryIngestionService
    library_search: LibraryLexicalSearchService
    library_sources: LibrarySourceWorkflow


@contextmanager
def workbench_runtime(settings: Settings | None = None) -> Iterator[WorkbenchRuntime]:
    """Compose application services and deterministically dispose the DB engine."""
    resolved = settings if settings is not None else load_settings()
    configure_logging(
        resolved.log_level.value,
        secret_values=resolved.logging_secret_values(),
    )
    engine = build_engine(resolved)
    asset_store = LocalAssetStore(resolved.asset_root, resolved.scratch_root)
    preparation = PreparationService(engine, asset_store)
    source_reader = LocalSourceReader(
        {f"root-{index}": path for index, path in enumerate(resolved.source_roots)}
    )
    library_ingestion = LibraryIngestionService(engine, source_reader)
    library_snapshots = CorpusSnapshotService(engine)
    dungeons = DungeonStudioService(preparation)
    model_gateway = (
        None
        if resolved.model_gateway_policy is ModelGatewayPolicy.DISABLED
        else PiGatewayClient.from_settings(resolved)
    )
    dungeon_prompts = (
        None if model_gateway is None else DungeonPromptService(dungeons, model_gateway)
    )
    dungeon_prompt_application = (
        None
        if dungeon_prompts is None
        else DungeonPromptApplicationService(preparation, dungeon_prompts)
    )
    dungeon_canary_application = None
    dungeon_fixed_case_application = None
    if model_gateway is not None and dungeon_prompt_application is not None:
        one_step = DungeonStagedEnrichmentCoordinator(
            preparation,
            puzzle=DungeonPuzzlePromptApplicationService(
                preparation, DungeonPuzzlePromptService(dungeons, model_gateway)
            ),
            exploration=DungeonExplorationPromptApplicationService(
                preparation, DungeonExplorationPromptService(dungeons, model_gateway)
            ),
            feature_interaction=DungeonFeatureInteractionPromptApplicationService(
                preparation,
                DungeonFeatureInteractionPromptService(dungeons, model_gateway),
            ),
            trap=DungeonTrapPromptApplicationService(
                preparation, DungeonTrapPromptService(dungeons, model_gateway)
            ),
            objective=DungeonObjectivePromptApplicationService(
                preparation, DungeonObjectivePromptService(dungeons, model_gateway)
            ),
            room_narrative=DungeonRoomNarrativePromptApplicationService(
                preparation, DungeonRoomNarrativePromptService(dungeons, model_gateway)
            ),
        )
        dungeon_canary_application = DungeonTierACanaryApplicationService(
            preparation,
            dungeon_prompt_application,
            DungeonStagedEnrichmentChainCoordinator(one_step),
        )
        dungeon_fixed_case_application = DungeonTierAFixedCaseApplicationService(
            preparation,
            dungeons,
            one_step,
        )
    try:
        yield WorkbenchRuntime(
            settings=resolved,
            engine=engine,
            campaigns=CampaignCatalog(engine),
            preparation=preparation,
            dungeons=dungeons,
            model_gateway=model_gateway,
            dungeon_prompts=dungeon_prompts,
            dungeon_prompt_application=dungeon_prompt_application,
            dungeon_canary_application=dungeon_canary_application,
            dungeon_fixed_case_application=dungeon_fixed_case_application,
            model_selections=ModelTaskSelectionStore(engine),
            library_catalog=LibraryDocumentCatalog(engine),
            library_ingestion=library_ingestion,
            library_search=LibraryLexicalSearchService(engine),
            library_sources=LibrarySourceWorkflow(
                library_ingestion,
                library_snapshots,
            ),
        )
    finally:
        engine.dispose()
