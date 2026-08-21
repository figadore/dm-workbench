"""CLI adapter smoke test over the shared Dungeon Studio service."""

import json
from collections.abc import Iterator
from pathlib import Path
from urllib.request import Request

import pytest
from sqlalchemy import Engine, text
from typer.testing import CliRunner

from dm_assistant.cli.main import app
from dm_dungeon import LayoutRequest, read_dungeon_package, to_canonical_json

pytestmark = pytest.mark.integration
runner = CliRunner()
FIXTURE_PATH = (
    Path(__file__).parents[2]
    / "packages/dungeon-engine/tests/fixtures/sunken_archive.v1.json"
)


class _JsonResponse:
    status = 200

    def __init__(self, document: object) -> None:
        self._document = document

    def __enter__(self) -> "_JsonResponse":
        return self

    def __exit__(self, *args: object) -> None:
        del args

    def read(self) -> bytes:
        return json.dumps(self._document).encode("utf-8")


class _SseResponse:
    status = 200

    def __init__(self, proposal: dict[str, object]) -> None:
        payload = json.dumps(
            {
                "name": "submit_dungeon_intent_v2",
                "id": "submit-cli-v2",
                "arguments": {"proposal": proposal},
            },
            separators=(",", ":"),
        )
        self._lines = (
            b"event: tool_call\n",
            f"data: {payload}\n".encode(),
            b"\n",
            b"event: usage\n",
            b'data: {"input_tokens":10,"output_tokens":20}\n',
            b"\n",
            b"event: completion\n",
            b'data: {"reason":"stop"}\n',
            b"\n",
            b"event: done\n",
            b"data: {}\n",
            b"\n",
        )

    def __enter__(self) -> "_SseResponse":
        return self

    def __exit__(self, *args: object) -> None:
        del args

    def __iter__(self) -> Iterator[bytes]:
        return iter(self._lines)


def _output_document(output: str) -> dict[str, object]:
    for line in reversed(output.splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise AssertionError("CLI output did not contain a JSON document")


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
        generator_version="orthogonal-v2",
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
        {"active": True, "id": campaign_id, "name": "Synthetic CLI Campaign"}
    ]
    second_campaign = runner.invoke(app, ["campaign", "create", "Second Workspace"])
    assert second_campaign.exit_code == 0, second_campaign.output
    second_id = json.loads(second_campaign.output)["id"]
    switched = runner.invoke(app, ["campaign", "use", second_id])
    assert switched.exit_code == 0, switched.output
    assert json.loads(switched.output)["active"] is True
    switched_back = runner.invoke(app, ["campaign", "use", campaign_id])
    assert switched_back.exit_code == 0, switched_back.output

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
    result = _output_document(generated.output)
    artifact_id = result["artifact_id"]
    version_id = result["artifact_version_id"]
    print_export = runner.invoke(
        app,
        [
            "dungeon",
            "export",
            version_id,
            "--format",
            "pdf",
            "--campaign",
            campaign_id,
        ],
    )
    assert print_export.exit_code == 1
    assert "dungeon_print_export_disabled" in print_export.output

    roll20_export = runner.invoke(
        app,
        [
            "dungeon",
            "export",
            version_id,
            "--format",
            "roll20",
            "--campaign",
            campaign_id,
        ],
    )
    assert roll20_export.exit_code == 0, roll20_export.output
    assert len(_output_document(roll20_export.output)["asset_ids"]) == 8

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
    assert _output_document(inspected.output)["versions"] == [version_id]

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
    assert _output_document(approved.output)["lifecycle"] == "approved_for_play"


def test_cli_prompt_uses_private_gateway_and_persists_package(
    postgres_url: str,
    db_engine: Engine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = read_dungeon_package(FIXTURE_PATH)
    proposal: dict[str, object] = {
        "proposal_version": "2",
        "design": {
            "schema_version": "2.4.0",
            "title": package.brief.title,
            "premise": "A synthetic flooded archive lies beneath a lighthouse.",
            "themes": ["flooded archive"],
            "floors": [
                {
                    "local_ref": "archive",
                    "name": "Archive",
                    "rooms": [
                        {"local_ref": "entry", "name": "Entry", "role": "entrance"},
                        {"local_ref": "vault", "name": "Vault", "role": "objective"},
                    ],
                }
            ],
            "connections": [
                {
                    "local_ref": "entry-vault",
                    "from_ref": "entry",
                    "to_ref": "vault",
                    "passage": "door",
                }
            ],
            "objectives": [
                {
                    "room_ref": "vault",
                    "kind": "final_objective",
                    "name": "Sealed Ledger",
                }
            ],
            "dependencies": [],
        },
    }
    source_root = tmp_path / "prompt-sources"
    source_root.mkdir()
    environment = {
        "DM_ENVIRONMENT": "test",
        "DM_DATABASE_URL": postgres_url,
        "DM_SOURCE_ROOTS": json.dumps([str(source_root)]),
        "DM_ASSET_ROOT": str(tmp_path / "prompt-assets"),
        "DM_SCRATCH_ROOT": str(tmp_path / "prompt-scratch"),
        "DM_API_TOKEN": "prompt-cli-api-token-000000000000000",
        "DM_SESSION_SECRET": "prompt-cli-session-token-000000000000",
        "DM_MODEL_GATEWAY_POLICY": "optional",
        "DM_MODEL_GATEWAY_URL": "http://model-gateway:3000",
        "DM_MODEL_GATEWAY_INTERNAL_TOKEN": "prompt-cli-gateway-token-00000000000",
    }
    for name, value in environment.items():
        monkeypatch.setenv(name, value)

    def fake_urlopen(request: Request, *, timeout: int) -> _JsonResponse | _SseResponse:
        del timeout
        if request.full_url.endswith("/v1/providers"):
            return _JsonResponse(
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
                                    "name": "Faux deterministic",
                                    "input": ["text"],
                                    "capabilities": ["text", "thinking", "tool_calls"],
                                    "contextWindow": 16384,
                                    "maxOutputTokens": 4096,
                                }
                            ],
                        }
                    ]
                }
            )
        if request.full_url.endswith("/v1/streams"):
            return _SseResponse(proposal)
        raise AssertionError(f"unexpected gateway URL: {request.full_url}")

    monkeypatch.setattr("dm_assistant.adapters.model_gateway.urlopen", fake_urlopen)
    prompted = runner.invoke(
        app,
        [
            "dungeon",
            "prompt",
            "A flooded archive beneath a lighthouse.",
            "--constraint",
            "flooded",
        ],
    )

    assert prompted.exit_code == 0, prompted.output
    result = _output_document(prompted.output)
    assert result["success"] is True
    assert result["resolved"]["provider"] == "faux"
    assert result["resolved"]["model"] == "faux-deterministic-v1"
    assert result["resolved"]["title"] == package.brief.title
    assert isinstance(result["resolved"]["seed"], int)
    campaigns = runner.invoke(app, ["campaign", "list"])
    assert campaigns.exit_code == 0, campaigns.output
    campaign_list = json.loads(campaigns.output)
    assert campaign_list[0]["active"] is True
    assert campaign_list[0]["name"] == "My Campaign"
    campaign_id = campaign_list[0]["id"]
    inspected = runner.invoke(
        app,
        [
            "dungeon",
            "inspect",
            result["artifact_id"],
            "--campaign",
            campaign_id,
        ],
    )
    assert inspected.exit_code == 0, inspected.output
    detail = _output_document(inspected.output)
    assert detail["versions"] == [result["artifact_version_id"]]
    assert detail["title"] == package.brief.title
    with db_engine.connect() as connection:
        selection = connection.execute(
            text(
                "SELECT provider_id, model_id, effort "
                "FROM model_task_selection "
                "WHERE task_name = 'dungeon_generation_intent_v1'"
            )
        ).one()
    assert tuple(selection) == ("faux", "faux-deterministic-v1", "standard")
