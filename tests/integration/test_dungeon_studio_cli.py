"""CLI adapter smoke test over the shared Dungeon Studio service."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dm_assistant.cli.main import app
from dm_dungeon import LayoutRequest, read_dungeon_package, to_canonical_json

pytestmark = pytest.mark.integration
runner = CliRunner()
FIXTURE_PATH = (
    Path(__file__).parents[2]
    / "packages/dungeon-engine/tests/fixtures/sunken_archive.v1.json"
)


def test_cli_generate_inspect_and_approve_use_shared_workflow(
    postgres_url: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = read_dungeon_package(FIXTURE_PATH)
    request = LayoutRequest(
        schema_version="1.0.0",
        package_id="package_cli_archive",
        brief=package.brief,
        topology=package.topology,
        seed=424242,
        generator_version="orthogonal-v1",
    )
    source_root = tmp_path / "sources"
    source_root.mkdir()
    request_path = source_root / "layout.json"
    request_path.write_text(to_canonical_json(request), encoding="utf-8")
    environment = {
        "DM_ENVIRONMENT": "test",
        "DM_DATABASE_URL": postgres_url,
        "DM_SOURCE_ROOTS": json.dumps([str(source_root)]),
        "DM_ASSET_ROOT": str(tmp_path / "cli-assets"),
        "DM_SCRATCH_ROOT": str(tmp_path / "cli-scratch"),
        "DM_API_TOKEN": "cli-integration-token-000000000000000",
        "DM_SESSION_SECRET": "cli-session-secret-0000000000000000",
    }
    for name, value in environment.items():
        monkeypatch.setenv(name, value)

    created_campaign = runner.invoke(
        app,
        ["campaign", "create", "Synthetic CLI Campaign"],
    )
    assert created_campaign.exit_code == 0, created_campaign.output
    campaign_id = json.loads(created_campaign.output)["id"]
    listed_campaigns = runner.invoke(app, ["campaign", "list"])
    assert listed_campaigns.exit_code == 0
    assert json.loads(listed_campaigns.output) == [
        {"id": campaign_id, "name": "Synthetic CLI Campaign"}
    ]

    generated = runner.invoke(
        app,
        [
            "dungeon",
            "generate",
            str(request_path),
            "--campaign",
            str(campaign_id),
            "--title",
            "Synthetic CLI Archive",
        ],
    )

    assert generated.exit_code == 0, generated.output
    result = json.loads(generated.output)
    artifact_id = result["artifact_id"]
    version_id = result["artifact_version_id"]
    inspected = runner.invoke(
        app,
        [
            "dungeon",
            "inspect",
            artifact_id,
            "--campaign",
            str(campaign_id),
        ],
    )
    assert inspected.exit_code == 0, inspected.output
    assert json.loads(inspected.output)["versions"] == [version_id]

    approved = runner.invoke(
        app,
        [
            "dungeon",
            "approve",
            artifact_id,
            version_id,
            "--campaign",
            str(campaign_id),
            "--reason",
            "Synthetic CLI review complete.",
        ],
    )
    assert approved.exit_code == 0, approved.output
    assert json.loads(approved.output)["lifecycle"] == "approved_for_play"
