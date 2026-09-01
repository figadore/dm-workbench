"""CLI adapter smoke test over the shared Dungeon Studio service."""

import json
import uuid
from collections.abc import Iterator
from copy import deepcopy
from pathlib import Path
from urllib.request import Request

import pytest
from dungeon_fixtures import synthetic_layout_request, synthetic_prompt_proposal
from sqlalchemy import Engine, text
from typer.testing import CliRunner

from dm_assistant.adapters.assets import LocalAssetStore
from dm_assistant.cli.main import app
from dm_assistant.modules.preparation import PreparationService
from dm_assistant.orchestration.dungeons import DungeonStudioSpecification
from dm_assistant.orchestration.dungeons.evals import evaluate_dungeon_guide_quality
from dm_dungeon import to_canonical_json

pytestmark = pytest.mark.integration
runner = CliRunner()


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

    def __init__(
        self,
        proposal: dict[str, object],
        *,
        input_tokens: int = 10,
        output_tokens: int = 20,
    ) -> None:
        payload = json.dumps(
            {
                "name": "submit_dungeon_plan",
                "id": "submit-cli-v1",
                "arguments": proposal,
            },
            separators=(",", ":"),
        )
        self._lines = (
            b"event: tool_call\n",
            f"data: {payload}\n".encode(),
            b"\n",
            b"event: usage\n",
            (
                f'data: {{"input_tokens":{input_tokens},'
                f'"output_tokens":{output_tokens}}}\n'
            ).encode(),
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
    request = synthetic_layout_request("package_cli_archive")
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
    assert len(_output_document(roll20_export.output)["asset_ids"]) == 4

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
    proposal = synthetic_prompt_proposal()
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
                        },
                        {
                            "id": "openai-codex",
                            "name": "Synthetic Codex",
                            "authenticated": True,
                            "authModes": ["oauth"],
                            "models": [
                                {
                                    "id": "synthetic-codex",
                                    "name": "Synthetic Codex model",
                                    "input": ["text"],
                                    "capabilities": ["text", "thinking", "tool_calls"],
                                    "contextWindow": 128000,
                                    "maxOutputTokens": 16384,
                                }
                            ],
                        },
                    ]
                }
            )
        if request.full_url.endswith("/v1/streams"):
            request_document = json.loads(request.data or b"{}")
            if request_document.get("provider") == "openai-codex":
                return _SseResponse(
                    proposal,
                    input_tokens=3_885,
                    output_tokens=7_747,
                )
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
    assert result["resolved"]["title"] == "Synthetic Constructive Archive"
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
    assert detail["title"] == "Synthetic Constructive Archive"

    preparation = PreparationService(
        db_engine,
        LocalAssetStore(
            tmp_path / "prompt-assets",
            tmp_path / "prompt-scratch",
        ),
    )
    version = preparation.get_version(
        uuid.UUID(campaign_id), uuid.UUID(str(result["artifact_version_id"]))
    )
    specification = DungeonStudioSpecification.model_validate_json(
        json.dumps(version.specification)
    )
    assert len(preparation.list_assets(uuid.UUID(campaign_id), version.id)) == 9
    assert specification.dm_guide is not None
    assert specification.preparation_readiness is not None
    assert not specification.preparation_readiness.ready
    assert {item.code for item in specification.preparation_readiness.diagnostics} == {
        "dungeon_preparation.guide_content_missing"
    }
    assert not evaluate_dungeon_guide_quality(specification).automated_pass
    assert specification.model_lineage[0].proposal is not None
    assert "guide_content" not in specification.model_lineage[0].proposal.model_dump()
    assert version.generation_run_id is not None
    run = preparation.get_generation_run(
        uuid.UUID(campaign_id), version.generation_run_id
    )
    assert len(run.tool_runs) == 1
    assert run.tool_runs[0]["tool_name"] == "submit_dungeon_plan"

    with db_engine.connect() as connection:
        selection = connection.execute(
            text(
                "SELECT provider_id, model_id, effort "
                "FROM model_task_selection "
                "WHERE task_name = 'dungeon_generation_intent_v1'"
            )
        ).one()
    assert tuple(selection) == ("faux", "faux-deterministic-v1", "standard")

    canary = runner.invoke(
        app,
        [
            "dungeon",
            "canary",
            "--provider",
            "openai-codex",
            "--model",
            "synthetic-codex",
        ],
    )
    assert canary.exit_code == 1, canary.output
    canary_result = _output_document(canary.output)
    assert canary_result["success"] is False
    assert canary_result["public_code"] == "dungeon_prompt_token_budget_exhausted"
    assert canary_result["artifact_id"] is None
    assert canary_result["artifact_version_id"] is None
    assert canary_result["task_attempt_run_ids"] == []
    assert canary_result["validation_codes"] == []
    assert canary_result["resolved"]["seed"] == 714_000_001
    with db_engine.connect() as connection:
        canary_attempt = connection.execute(
            text(
                "SELECT input_scope, validation_report FROM generation_run "
                "WHERE campaign_id = :campaign_id AND generation_kind = 'dungeon_prompt' "
                "AND input_scope->>'surface' = 'tier-a-live-canary-v1'"
            ),
            {"campaign_id": uuid.UUID(campaign_id)},
        ).one()
    assert canary_attempt.input_scope["surface"] == "tier-a-live-canary-v1"
    assert "run_policy" not in canary_attempt.validation_report

    invalid_proposal = deepcopy(proposal)
    invalid_plan = invalid_proposal["plan"]
    assert isinstance(invalid_plan, dict)
    invalid_rooms = invalid_plan["rooms"]
    assert isinstance(invalid_rooms, list)
    invalid_rooms[0]["encounter"] = "set_piece"
    proposal = invalid_proposal
    rejected = runner.invoke(
        app,
        [
            "dungeon",
            "prompt",
            "A schema-invalid synthetic archive.",
            "--campaign",
            campaign_id,
            "--provider",
            "faux",
            "--model",
            "faux-deterministic-v1",
        ],
    )
    assert rejected.exit_code == 1, rejected.output
    attempt_line = next(
        line
        for line in rejected.output.splitlines()
        if line.startswith("Attempt run: ")
    )
    failed_attempt = uuid.UUID(attempt_line.removeprefix("Attempt run: "))
    assert f"Inspect with: dm dungeon run inspect {failed_attempt}" in rejected.output
    inspected_attempt = runner.invoke(
        app,
        [
            "dungeon",
            "run",
            "inspect",
            str(failed_attempt),
            "--campaign",
            campaign_id,
        ],
    )
    assert inspected_attempt.exit_code == 0, inspected_attempt.output
    attempt_report = _output_document(inspected_attempt.output)["validation_report"]
    assert attempt_report["stage"] == "model_submission"
    assert attempt_report["code"] == "dungeon_prompt_rejected_after_repair"
    assert attempt_report["repair_attempted"] is True
    assert [item["attempt"] for item in attempt_report["submission_attempts"]] == [
        "initial",
        "repair",
    ]
    final_diagnostic = attempt_report["submission_attempts"][1]["diagnostics"][0]
    assert final_diagnostic["code"] == "submission.schema_invalid"
    assert final_diagnostic["path"].endswith("/encounter")
    assert "set_piece" not in json.dumps(attempt_report)
