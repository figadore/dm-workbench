"""Provider-free Dungeon Studio end-to-end generation, export, and approval."""

import json
import uuid
from pathlib import Path

import pytest
from dungeon_fixtures import synthetic_layout_request
from sqlalchemy import Engine, select

from dm_assistant.adapters.assets import LocalAssetStore
from dm_assistant.db import Campaign, build_session_factory, transactional_session
from dm_assistant.errors import ConflictError, DungeonPrintExportDisabledError
from dm_assistant.modules.preparation import (
    ArtifactAssetRole,
    ArtifactLifecycle,
    PreparationService,
)
from dm_assistant.modules.preparation.models import GenerationRun
from dm_assistant.orchestration.dungeons import (
    CreateDungeonWorkflow,
    DungeonStudioService,
    DungeonStudioSpecification,
    ExportDungeonWorkflow,
    RegenerateDungeonWorkflow,
)
from dm_dungeon import LayoutRequest

pytestmark = pytest.mark.integration


def create_campaign(engine: Engine) -> uuid.UUID:
    campaign_id = uuid.uuid4()
    with transactional_session(build_session_factory(engine)) as session:
        session.add(Campaign(id=campaign_id, name="Synthetic Dungeon Studio Campaign"))
    return campaign_id


def studio(
    engine: Engine, tmp_path: Path
) -> tuple[DungeonStudioService, PreparationService]:
    preparation = PreparationService(
        engine,
        LocalAssetStore(tmp_path / "studio-assets", tmp_path / "studio-scratch"),
    )
    return DungeonStudioService(preparation), preparation


def request_fixture() -> LayoutRequest:
    return synthetic_layout_request("package_studio_archive")


def test_failed_layout_retains_diagnostics_run_without_partial_version(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    campaign_id = create_campaign(db_engine)
    dungeon_studio, preparation = studio(db_engine, tmp_path)
    request = request_fixture()
    broken_topology = request.topology.model_copy(update={"connections": ()})

    result = dungeon_studio.create(
        CreateDungeonWorkflow(
            campaign_id=campaign_id,
            title="Invalid Synthetic Layout",
            layout_request=request.model_copy(update={"topology": broken_topology}),
            created_by="synthetic-dm",
        )
    )

    assert result.success is False
    assert result.artifact_id is None
    assert result.artifact_version_id is None
    assert result.diagnostics
    with db_engine.connect() as connection:
        run = connection.execute(
            select(GenerationRun.status, GenerationRun.validation_report).where(
                GenerationRun.id == result.generation_run_id
            )
        ).one()
    assert run.status == "failed"
    assert run.validation_report["valid"] is False
    assert run.validation_report["stage"] == "layout"


def test_provider_free_dungeon_workflow_persists_previews_exports_and_approval(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    campaign_id = create_campaign(db_engine)
    dungeon_studio, preparation = studio(db_engine, tmp_path)

    created = dungeon_studio.create(
        CreateDungeonWorkflow(
            campaign_id=campaign_id,
            title="Provider-Free Synthetic Archive",
            layout_request=request_fixture(),
            created_by="synthetic-dm",
        )
    )

    assert created.success is True
    assert created.artifact_id is not None
    assert created.artifact_version_id is not None
    first_version = preparation.get_version(
        campaign_id,
        created.artifact_version_id,
    )
    first_specification = DungeonStudioSpecification.model_validate_json(
        json.dumps(first_version.specification)
    )
    assert first_version.parent_version_id is None
    assert first_version.validation_report["valid"] is True
    assert first_specification.package.metadata.seed == 424242
    first_assets = preparation.list_assets(campaign_id, first_version.id)
    assert len(first_assets) == 15
    assert {item.role for item in first_assets} >= {
        ArtifactAssetRole.SPECIFICATION,
        ArtifactAssetRole.VALIDATION_REPORT,
        ArtifactAssetRole.DM_SVG,
        ArtifactAssetRole.PLAYER_SVG,
        ArtifactAssetRole.DM_PNG,
        ArtifactAssetRole.PLAYER_PNG,
        ArtifactAssetRole.MANIFEST,
    }

    player_svg = next(
        item for item in first_assets if item.role is ArtifactAssetRole.PLAYER_SVG
    )
    dm_svg = next(
        item for item in first_assets if item.role is ArtifactAssetRole.DM_SVG
    )
    _, player_bytes = preparation.read_asset(campaign_id, player_svg.asset_id)
    _, dm_bytes = preparation.read_asset(campaign_id, dm_svg.asset_id)
    assert b"room_vault" not in player_bytes
    assert b"connection_vault_secret" not in player_bytes
    assert b"room_vault" in dm_bytes

    original = first_specification.package
    locked_ids = (
        original.rooms[0].id,
        original.rooms[1].id,
    )
    regenerated = dungeon_studio.regenerate(
        RegenerateDungeonWorkflow(
            campaign_id=campaign_id,
            artifact_id=created.artifact_id,
            parent_version_id=first_version.id,
            seed=888888,
            locked_component_ids=locked_ids,
            change_summary="Regenerate unlocked geometry while preserving selected locks.",
            created_by="synthetic-dm",
        )
    )
    assert regenerated.success is True
    assert regenerated.artifact_version_id is not None
    second_version = preparation.get_version(
        campaign_id,
        regenerated.artifact_version_id,
    )
    second_specification = DungeonStudioSpecification.model_validate_json(
        json.dumps(second_version.specification)
    )
    assert second_version.parent_version_id == first_version.id
    assert second_specification.package.metadata.seed == 888888
    for component_id in locked_ids:
        assert (
            component_id in second_specification.package.metadata.locked_component_ids
        )

    comparison = dungeon_studio.compare(
        campaign_id=campaign_id,
        left_version_id=first_version.id,
        right_version_id=second_version.id,
    )
    assert comparison.left_version_id == first_version.id
    assert comparison.right_version_id == second_version.id
    assert set(locked_ids) <= set(comparison.unchanged_component_ids)
    assert comparison.changed_component_ids

    assert dungeon_studio.print_capability.status == "disabled"
    with pytest.raises(DungeonPrintExportDisabledError) as disabled:
        dungeon_studio.export(
            ExportDungeonWorkflow(
                campaign_id=campaign_id,
                artifact_version_id=second_version.id,
                export_format="pdf",
            )
        )
    assert disabled.value.code.value == "dungeon_print_export_disabled"

    exported_asset_ids = dungeon_studio.export(
        ExportDungeonWorkflow(
            campaign_id=campaign_id,
            artifact_version_id=second_version.id,
            export_format="roll20",
        )
    )
    assert len(exported_asset_ids) == 8
    all_assets = preparation.list_assets(campaign_id, second_version.id)
    assert {item.role for item in all_assets} >= {
        ArtifactAssetRole.DM_ROLL20_BUNDLE,
        ArtifactAssetRole.PLAYER_ROLL20_BUNDLE,
    }
    assert not {
        ArtifactAssetRole.DM_PRINT_PDF,
        ArtifactAssetRole.PLAYER_PRINT_PDF,
    } & {item.role for item in all_assets}
    for asset in all_assets:
        if asset.role is ArtifactAssetRole.PLAYER_ROLL20_BUNDLE:
            _, data = preparation.read_asset(campaign_id, asset.asset_id)
            assert b"room_vault" not in data
            assert b"connection_vault_secret" not in data

    detail = dungeon_studio.approve(
        campaign_id=campaign_id,
        artifact_id=created.artifact_id,
        artifact_version_id=second_version.id,
        actor="synthetic-dm",
        reason="Review complete; approve this preparation version for play.",
    )
    assert detail.lifecycle == ArtifactLifecycle.APPROVED_FOR_PLAY.value
    assert detail.current_version_id == second_version.id
    assert detail.versions == (first_version.id, second_version.id)
    with pytest.raises(ConflictError, match="current draft"):
        dungeon_studio.export(
            ExportDungeonWorkflow(
                campaign_id=campaign_id,
                artifact_version_id=second_version.id,
                export_format="roll20",
            )
        )
