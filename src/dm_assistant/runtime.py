"""Composition root helpers shared by CLI and HTTP application adapters."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy import Engine

from dm_assistant.adapters.assets import LocalAssetStore
from dm_assistant.campaigns import CampaignCatalog
from dm_assistant.config import Settings, load_settings
from dm_assistant.db import build_engine
from dm_assistant.modules.preparation import PreparationService
from dm_assistant.orchestration.dungeons import DungeonStudioService


@dataclass(frozen=True, slots=True)
class WorkbenchRuntime:
    settings: Settings
    engine: Engine
    campaigns: CampaignCatalog
    preparation: PreparationService
    dungeons: DungeonStudioService


@contextmanager
def workbench_runtime(settings: Settings | None = None) -> Iterator[WorkbenchRuntime]:
    """Compose application services and deterministically dispose the DB engine."""
    resolved = settings if settings is not None else load_settings()
    engine = build_engine(resolved)
    asset_store = LocalAssetStore(resolved.asset_root, resolved.scratch_root)
    preparation = PreparationService(engine, asset_store)
    try:
        yield WorkbenchRuntime(
            settings=resolved,
            engine=engine,
            campaigns=CampaignCatalog(engine),
            preparation=preparation,
            dungeons=DungeonStudioService(preparation),
        )
    finally:
        engine.dispose()
