"""Real browser -> faux private gateway -> persisted prompted dungeon gate."""

import asyncio
import json
import re
import uuid
from collections.abc import Iterator
from pathlib import Path
from urllib.request import Request

import httpx
import pytest
from dungeon_fixtures import synthetic_prompt_proposal
from sqlalchemy import Engine, select

from dm_assistant.adapters.assets import LocalAssetStore
from dm_assistant.api import create_app
from dm_assistant.config import ModelGatewayPolicy, RuntimeEnvironment, Settings
from dm_assistant.db import Campaign, build_session_factory, transactional_session
from dm_assistant.modules.preparation import (
    ArtifactAssetRole,
    ArtifactLifecycle,
    PreparationService,
)
from dm_assistant.modules.preparation.models import (
    GenerationRun,
    PreparationArtifact,
    PreparationArtifactVersion,
)
from dm_assistant.orchestration.dungeons import DungeonStudioSpecification
from dm_assistant.orchestration.dungeons.evals import (
    evaluate_dungeon_guide_quality,
    render_dungeon_guide_quality_report,
)
from dm_dungeon.export import PngExportManifest
from dm_dungeon.rendering import RenderAudience

pytestmark = pytest.mark.integration
TOKEN = "web-prompt-token-000000000000000"


class _Response:
    def __init__(self, body: bytes) -> None:
        self.status = 200
        self._body = body

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body

    def __iter__(self) -> Iterator[bytes]:
        return iter(self._body.splitlines(keepends=True))


def test_browser_prompt_faux_gateway_persists_draft(
    db_engine: Engine,
    postgres_url: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    campaign_id = uuid.uuid4()
    with transactional_session(build_session_factory(db_engine)) as session:
        session.add(Campaign(id=campaign_id, name="Synthetic Browser Prompt"))
    proposal = synthetic_prompt_proposal()

    def fake_urlopen(request: Request, *, timeout: int) -> _Response:
        del timeout
        if request.full_url.endswith("/v1/providers"):
            return _Response(
                json.dumps(
                    {
                        "providers": [
                            {
                                "id": "faux",
                                "name": "Faux",
                                "authenticated": True,
                                "authModes": [],
                                "models": [
                                    {
                                        "id": "faux-deterministic-v1",
                                        "name": "Faux",
                                        "input": ["text"],
                                        "capabilities": [
                                            "text",
                                            "thinking",
                                            "tool_calls",
                                        ],
                                        "contextWindow": 16384,
                                        "maxOutputTokens": 4096,
                                    }
                                ],
                            }
                        ]
                    }
                ).encode()
            )
        if request.full_url.endswith("/v1/streams"):
            tool_call = {
                "name": "submit_dungeon_plan",
                "id": "submit-browser-v1",
                "arguments": proposal,
            }
            return _Response(
                (
                    f"event: tool_call\ndata: {json.dumps(tool_call)}\n\n"
                    'event: usage\ndata: {"inputTokens":10,"outputTokens":10}\n\n'
                    "event: completion\ndata: {}\n\n"
                ).encode()
            )
        raise AssertionError(request.full_url)

    monkeypatch.setattr("dm_assistant.adapters.model_gateway.urlopen", fake_urlopen)
    settings = Settings(
        environment=RuntimeEnvironment.TEST,
        database_url=postgres_url,
        source_roots=(tmp_path,),
        asset_root=tmp_path / "assets",
        scratch_root=tmp_path / "scratch",
        api_token=TOKEN,
        session_secret="web-prompt-session-secret-000000000000",
        model_gateway_policy=ModelGatewayPolicy.OPTIONAL,
        model_gateway_url="http://faux",
        model_gateway_internal_token="web-prompt-gateway-token-000000000000",
    )
    application = create_app(settings)

    async def flow() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application),
            base_url="http://test",
            follow_redirects=False,
        ) as client:
            await client.post("/login", data={"token": TOKEN})
            page = await client.get(f"/dungeons?campaign_id={campaign_id}")
            assert "application-only output cap" in page.text
            csrf = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)  # type: ignore[union-attr]
            started = await client.post(
                "/dungeons/prompts",
                data={
                    "csrf_token": csrf,
                    "campaign_id": str(campaign_id),
                    "prompt": "Synthetic archive",
                },
            )
            assert started.status_code == 303
            result = await client.get(started.headers["location"])
            for _ in range(100):
                if (
                    "Inspect generated draft" in result.text
                    or "Safe result:" in result.text
                ):
                    break
                await asyncio.sleep(0.05)
                result = await client.get(started.headers["location"])
            safe_result = re.search(r"Safe result:\s*<code>([^<]+)</code>", result.text)
            assert "Dungeon draft created." in result.text, (
                safe_result.group(1) if safe_result else "prompt remained nonterminal"
            )
            assert "Inspect generated draft" in result.text
            detail_url = re.search(
                r'href="(/dungeons/[0-9a-f-]+\?campaign_id=[^"]+)">'
                r"Inspect generated draft",
                result.text,
            )
            assert detail_url is not None
            detail = await client.get(detail_url.group(1))
            assert "Exploration challenge" in detail.text
            assert "Encounter slot:" not in detail.text
            assert "not yet populated" not in detail.text
            assert "Sensory cues:" not in detail.text
            assert "Room mechanics:" not in detail.text
            assert "discovery DC 13; check method is DM-adjudicated" in detail.text
            assert "unlock DC 13" in detail.text
            assert "Preparation incomplete:" in detail.text
            assert "Runnable details are missing." in detail.text
            assert "Three-Button Vault Lock" not in detail.text
            assert "Situation:" not in detail.text
            assert "Run it:" not in detail.text
            assert "Choices and consequences:" not in detail.text
            assert "Synthetic Objective" in detail.text

    asyncio.run(flow())

    with transactional_session(build_session_factory(db_engine)) as session:
        run = session.scalar(
            select(GenerationRun).where(
                GenerationRun.campaign_id == campaign_id,
                GenerationRun.generation_kind == "prompted_dungeon_layout",
            )
        )
        assert run is not None
        version = session.scalar(
            select(PreparationArtifactVersion).where(
                PreparationArtifactVersion.generation_run_id == run.id
            )
        )
        assert version is not None
        artifact = session.scalar(
            select(PreparationArtifact).where(
                PreparationArtifact.id == version.artifact_id
            )
        )
        assert artifact is not None
        run_id = run.id
        version_id = version.id
        artifact_id = artifact.id
        assert run.status == "succeeded"
        assert run.schema_versions["dungeon_package"] == "1.0.0"
        assert run.schema_versions["dungeon_generation_proposal"] == "1.0.0"
        assert (
            run.generator_versions["dungeon_mechanics_policy"]
            == "dungeon-mechanics-policy-v1"
        )
        assert run.generator_versions["plan_compiler"] == "dungeon-plan-compiler-v1"
        assert len(run.model_run_ids) == 1
        assert len(run.tool_runs) == 1
        assert run.tool_runs[0]["tool_name"] == "submit_dungeon_plan"
        assert version.parent_version_id is None
        assert version.validation_report["valid"] is True
        assert artifact.lifecycle == ArtifactLifecycle.DRAFT.value
        assert artifact.current_version_id == version.id

    preparation = PreparationService(
        db_engine,
        LocalAssetStore(settings.asset_root, settings.scratch_root),
    )
    persisted_run = preparation.get_generation_run(campaign_id, run_id)
    persisted_version = preparation.get_version(campaign_id, version_id)
    persisted_artifact = preparation.get_artifact(campaign_id, artifact_id)
    specification = DungeonStudioSpecification.model_validate_json(
        json.dumps(persisted_version.specification)
    )
    assert persisted_run.status.value == "succeeded"
    assert persisted_artifact.current_version_id == persisted_version.id

    guide = specification.dm_guide
    readiness = specification.preparation_readiness
    assert guide is not None
    assert guide.title == "Synthetic Constructive Archive"
    assert len(guide.rooms) == 5
    assert len(guide.dependencies) == 1
    assert guide.dependencies[0].name == "Three-Wave Brass Key"
    assert guide.dependencies[0].content is None
    assert guide.dependencies[0].discovery == (
        "Three-Wave Brass Key is present in Flooded Cataloguing Annex."
    )
    assert guide.traps[0].effect == (
        "The trip lever rings the bell and its clockwork bolt locks the buttons for 10 "
        "minutes. On the first ring only, the hammer's lower arm flips the full ink cup "
        "over the three button labels."
    )
    assert guide.traps[0].detection is not None
    assert "hairline seam around the pivoting threshold plate" in (
        guide.traps[0].detection
    )
    assert guide.traps[0].disable is not None
    assert "pull out its coupling pin" in guide.traps[0].disable
    assert guide.puzzles == ()
    assert guide.features[0].name == "Instruction Pedestal"
    assert guide.features[0].content is None
    assert guide.objectives[0].name == "Synthetic Objective"
    assert guide.objectives[0].content is None
    assert all(room.encounter_content is None for room in guide.rooms)
    assert {item.code for item in guide.content_issues} == {
        "guide_content.required_missing"
    }
    assert all(item.map_reference is not None for item in guide.connections)
    assert readiness is not None and not readiness.ready
    assert {item.code for item in readiness.diagnostics} == {
        "dungeon_preparation.guide_content_missing"
    }
    assert (
        persisted_version.validation_report["preparation_readiness"]["ready"] is False
    )
    quality = evaluate_dungeon_guide_quality(specification)
    assert not quality.automated_pass
    assert quality.human_review_required
    assert {item.dimension for item in quality.checks} == {
        "progression",
        "variety",
        "clue_logic",
        "prep_usefulness",
    }
    quality_report = render_dungeon_guide_quality_report(quality)
    assert "automated checks: fail" in quality_report
    assert "human DM review: required" in quality_report
    assert "Synthetic" not in quality_report

    callout_keys = {
        (item.component_id, item.floor_id, item.token) for item in guide.map_callouts
    }
    guide_references = {
        (
            reference.component_id,
            reference.floor_id,
            reference.token,
        )
        for reference in (
            *(item.map_reference for item in guide.rooms),
            *(item.map_reference for item in guide.connections if item.map_reference),
            *(item.room_map_reference for item in guide.dependencies),
            *(item.map_reference for item in guide.traps),
            *(item.map_reference for item in guide.puzzles),
            *(item.map_reference for item in guide.features),
            *(item.map_reference for item in guide.objectives),
        )
    }
    assert guide_references <= callout_keys

    package = specification.package
    assert len(package.floors) == 1
    secret_loop = next(
        item for item in specification.layout_request.certificate.loops if item.secret
    )
    secret_door = next(
        item
        for item in package.composable_doors
        if item.connection_id == secret_loop.connection_id
    )
    secret_corridors = {
        item.id for item in package.corridors if item.visibility.value == "dm_only"
    }
    secret_component_ids = {secret_door.id, *secret_corridors}
    assert secret_door.visibility.value == "dm_only"
    assert secret_corridors
    secret_guide_entry = next(
        item for item in guide.connections if item.component_id == secret_door.id
    )
    assert secret_guide_entry.concealed
    assert secret_guide_entry.discovery_difficulty is not None
    gated_guide_entry = next(item for item in guide.connections if item.gate_id)
    assert gated_guide_entry.gate_kind.value == "locked"
    assert gated_guide_entry.unlock_difficulty is not None

    assets = preparation.list_assets(campaign_id, version_id)
    assert len(assets) == 9
    assert {item.role for item in assets} == {
        ArtifactAssetRole.SPECIFICATION,
        ArtifactAssetRole.VALIDATION_REPORT,
        ArtifactAssetRole.DM_SVG,
        ArtifactAssetRole.PLAYER_SVG,
        ArtifactAssetRole.DM_PNG,
        ArtifactAssetRole.PLAYER_PNG,
        ArtifactAssetRole.MANIFEST,
        ArtifactAssetRole.OTHER,
    }
    dm_svg_asset = next(
        item for item in assets if item.role is ArtifactAssetRole.DM_SVG
    )
    player_svg_asset = next(
        item for item in assets if item.role is ArtifactAssetRole.PLAYER_SVG
    )
    _, dm_svg = preparation.read_asset(campaign_id, dm_svg_asset.asset_id)
    _, player_svg = preparation.read_asset(campaign_id, player_svg_asset.asset_id)
    for component_id in secret_component_ids:
        assert component_id.encode() in dm_svg
        assert component_id.encode() not in player_svg

    png_manifests: dict[RenderAudience, PngExportManifest] = {}
    for asset in assets:
        if asset.role is not ArtifactAssetRole.MANIFEST:
            continue
        _, manifest_data = preparation.read_asset(campaign_id, asset.asset_id)
        manifest = PngExportManifest.model_validate_json(manifest_data)
        png_manifests[manifest.audience] = manifest
    assert set(png_manifests) == {RenderAudience.DM, RenderAudience.PLAYER}
    dm_rendered_ids = set(png_manifests[RenderAudience.DM].rendered_component_ids)
    player_rendered_ids = set(
        png_manifests[RenderAudience.PLAYER].rendered_component_ids
    )
    assert secret_component_ids <= dm_rendered_ids
    assert not secret_component_ids & player_rendered_ids
