"""Provider-free Dungeon Studio end-to-end generation, export, and approval."""

import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy import Engine, select

from dm_assistant.adapters.assets import LocalAssetStore
from dm_assistant.db import Campaign, build_session_factory, transactional_session
from dm_assistant.errors import ConflictError, DungeonPrintExportDisabledError
from dm_assistant.modules.modeling import (
    DungeonGenerationIntentV1,
    GatewayModelCatalogEntry,
    ModelEndpointProfile,
    PromptMessage,
    ReasoningEffort,
    ReasoningLevel,
    TaskProfile,
    resolve_run_profile,
)
from dm_assistant.modules.preparation import (
    ArtifactAssetRole,
    ArtifactLifecycle,
    PreparationService,
)
from dm_assistant.modules.preparation.models import GenerationRun
from dm_assistant.modules.scope import TaskType, resolve_task_scope
from dm_assistant.orchestration.dungeons import (
    CreateDungeonWorkflow,
    DungeonPromptService,
    DungeonStudioService,
    DungeonStudioSpecification,
    ExportDungeonWorkflow,
    PromptDungeonWorkflow,
    RegenerateDungeonWorkflow,
)
from dm_assistant.orchestration.modeling import GatewayCompletion
from dm_dungeon import LayoutRequest, read_dungeon_package

pytestmark = pytest.mark.integration
FIXTURE_PATH = (
    Path(__file__).parents[2]
    / "packages/dungeon-engine/tests/fixtures/sunken_archive.v1.json"
)


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
    package = read_dungeon_package(FIXTURE_PATH)
    return LayoutRequest(
        schema_version="1.0.0",
        package_id="package_studio_archive",
        brief=package.brief,
        topology=package.topology,
        seed=424242,
        generator_version="orthogonal-v2",
    )


class FakeGatewayClient:
    def __init__(self, completion: GatewayCompletion) -> None:
        self._completion = completion

    def complete(
        self,
        *,
        profile: object,
        messages: tuple[PromptMessage, ...],
        allowed_tools: tuple[str, ...],
        tool_schemas: tuple[object, ...],
    ) -> GatewayCompletion:
        del profile, messages, allowed_tools, tool_schemas
        completion = self._completion
        self._completion = GatewayCompletion()
        if completion.content is None:
            raise AssertionError("unexpected extra gateway completion")
        return completion


def prompted_profile():
    endpoint = ModelEndpointProfile(
        profile_id=uuid.uuid4(),
        profile_version="1.0.0",
        runtime_adapter="pi_ai",
        provider_id="faux",
        model_id="faux_deterministic_v1",
        supported_efforts=(ReasoningEffort.STANDARD,),
        context_window_tokens=16_384,
        output_token_limit=4_096,
    )
    task = TaskProfile(
        profile_id=uuid.uuid4(),
        profile_version="1.0.0",
        task_name="dungeon_generation_intent_v1",
        prompt_version="prompt-1",
        instruction_version="instructions-1",
        output_schema_name="dungeon_generation_intent_v1",
        output_schema_version="1.0.0",
        allowed_tools=(
            "review_dungeon_brief",
            "review_dungeon_topology",
            "generate_dungeon_layout",
            "validate_dungeon_intent",
            "regenerate_dungeon_layout",
        ),
        turn_budget=2,
        tool_budget=1,
        time_budget_seconds=30,
        token_budget=4_096,
        require_citation_ids=False,
        require_authorized_citations=False,
    )
    catalog = GatewayModelCatalogEntry(
        provider_id="faux",
        model_id="faux_deterministic_v1",
        runtime_adapter="pi_ai",
        observed_capabilities=("text", "tool_calls"),
        supported_reasoning_levels=(ReasoningLevel.MEDIUM,),
        context_window_tokens=16_384,
        output_token_limit=4_096,
    )
    return resolve_run_profile(
        endpoint_profile=endpoint,
        task_profile=task,
        catalog_entry=catalog,
    )


def test_prompted_dungeon_persists_context_and_model_lineage(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    campaign_id = create_campaign(db_engine)
    dungeon_studio, preparation = studio(db_engine, tmp_path)
    layout_request = request_fixture()
    intent = DungeonGenerationIntentV1(
        schema_version="1.0.0",
        intent="Generate a synthetic flooded archive.",
        brief=layout_request.brief,
        topology=layout_request.topology,
        requested_constraints=("flooded",),
    )
    prompted = DungeonPromptService(
        dungeon_studio,
        FakeGatewayClient(
            GatewayCompletion(content=intent.model_dump_json(), input_tokens=10)
        ),
    )

    result = prompted.create(
        PromptDungeonWorkflow(
            campaign_id=campaign_id,
            title="Prompted Synthetic Archive",
            prompt="A flooded archive beneath a lighthouse.",
            seed=1842,
            created_by="synthetic-dm",
            scope=resolve_task_scope(
                dm_principal_id="dm",
                campaign_owner_id="dm",
                task_type=TaskType.STANDALONE_DUNGEON,
            ),
            requested_constraints=("flooded",),
        ),
        prompted_profile(),
    )

    assert result.success is True
    assert result.artifact_version_id is not None
    run = preparation.get_generation_run(campaign_id, result.generation_run_id)
    assert run.generation_kind == "prompted_dungeon_layout"
    assert run.context_envelope_kind == "dungeon_generation"
    assert run.context_payload_version == "1.0.0"
    assert run.model_task_profile_id is not None
    assert len(run.model_run_ids) == 1
    version = preparation.get_version(campaign_id, result.artifact_version_id)
    specification = DungeonStudioSpecification.model_validate_json(
        json.dumps(version.specification)
    )
    assert specification.layout_request.seed == 1842
    assert len(specification.model_lineage) == 1
    assert specification.model_lineage[0].intent == intent


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
