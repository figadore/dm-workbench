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
from dm_dungeon.export import (
    ROLL20_EXPORTER_VERSION,
    PngExportManifest,
    Roll20ExportManifest,
)
from dm_dungeon.rendering import RenderAudience

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
    required_bounds = request.floor_bounds[0]
    impossible_bounds = required_bounds.model_copy(
        update={"width_cells": 4, "height_cells": 4, "margin_cells": 1}
    )

    result = dungeon_studio.create(
        CreateDungeonWorkflow(
            campaign_id=campaign_id,
            title="Invalid Synthetic Layout",
            layout_request=request.model_copy(
                update={"floor_bounds": (impossible_bounds,)}
            ),
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
    assert len(first_assets) == 9
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
    dm_only_layout_ids = {
        item.id
        for components in (
            first_specification.package.rooms,
            first_specification.package.corridors,
            first_specification.package.composable_doors,
        )
        for item in components
        if item.visibility.value == "dm_only"
    }
    assert dm_only_layout_ids
    for component_id in dm_only_layout_ids:
        assert component_id.encode() not in player_bytes
        assert component_id.encode() in dm_bytes

    png_manifests = tuple(
        PngExportManifest.model_validate_json(
            preparation.read_asset(campaign_id, asset.asset_id)[1]
        )
        for asset in first_assets
        if asset.role is ArtifactAssetRole.MANIFEST
    )
    player_png_manifest = next(
        item for item in png_manifests if item.audience is RenderAudience.PLAYER
    )
    assert not dm_only_layout_ids & set(player_png_manifest.rendered_component_ids)

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
    # The constructive baseline is intentionally seed-independent until optional
    # compaction/variation exists, so changing only the seed preserves all components.
    assert comparison.changed_component_ids == ()

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
    assert len(exported_asset_ids) == 4
    all_assets = preparation.list_assets(campaign_id, second_version.id)
    assert {item.role for item in all_assets} >= {
        ArtifactAssetRole.DM_ROLL20_BUNDLE,
        ArtifactAssetRole.PLAYER_ROLL20_BUNDLE,
    }
    assert not {
        ArtifactAssetRole.DM_PRINT_PDF,
        ArtifactAssetRole.PLAYER_PRINT_PDF,
    } & {item.role for item in all_assets}
    roll20_manifests: dict[RenderAudience, Roll20ExportManifest] = {}
    for asset in all_assets:
        if asset.role is not ArtifactAssetRole.MANIFEST:
            continue
        _, data = preparation.read_asset(campaign_id, asset.asset_id)
        payload = json.loads(data)
        if payload.get("exporter_version") != ROLL20_EXPORTER_VERSION:
            continue
        manifest = Roll20ExportManifest.model_validate_json(data)
        roll20_manifests[manifest.audience] = manifest
    assert set(roll20_manifests) == {RenderAudience.DM, RenderAudience.PLAYER}
    assert dm_only_layout_ids <= set(
        roll20_manifests[RenderAudience.DM].rendered_component_ids
    )
    assert not dm_only_layout_ids & set(
        roll20_manifests[RenderAudience.PLAYER].rendered_component_ids
    )

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
