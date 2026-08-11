"""End-to-end CLI and API coverage for the immutable Library source surface."""

import asyncio
import json
from pathlib import Path

import httpx
import pytest
from sqlalchemy import Engine
from typer.testing import CliRunner

from dm_assistant.api import create_app
from dm_assistant.campaigns import CampaignCatalog
from dm_assistant.cli.main import app
from dm_assistant.config import RuntimeEnvironment, Settings

pytestmark = pytest.mark.integration
runner = CliRunner()
_TOKEN = "library-integration-token-00000000000000"
_SESSION_SECRET = "library-session-secret-000000000000000"


def _settings(postgres_url: str, source_root: Path, tmp_path: Path) -> Settings:
    return Settings(
        environment=RuntimeEnvironment.TEST,
        database_url=postgres_url,
        source_roots=(source_root,),
        asset_root=tmp_path / "assets",
        scratch_root=tmp_path / "scratch",
        api_token=_TOKEN,
        session_secret=_SESSION_SECRET,
    )


def test_library_cli_ingest_documents_show_and_search(
    postgres_url: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "sources"
    source_root.mkdir()
    (source_root / "note.md").write_text(
        "# Silver Gate\nThe party opened the Silver Gate after the bell rang.\n",
        encoding="utf-8",
    )
    environment = {
        "DM_ENVIRONMENT": "test",
        "DM_DATABASE_URL": postgres_url,
        "DM_SOURCE_ROOTS": json.dumps([str(source_root)]),
        "DM_ASSET_ROOT": str(tmp_path / "assets"),
        "DM_SCRATCH_ROOT": str(tmp_path / "scratch"),
        "DM_API_TOKEN": _TOKEN,
        "DM_SESSION_SECRET": _SESSION_SECRET,
    }
    for name, value in environment.items():
        monkeypatch.setenv(name, value)

    campaign = runner.invoke(app, ["campaign", "create", "Library CLI Campaign"])
    assert campaign.exit_code == 0, campaign.output
    campaign_id = json.loads(campaign.output)["id"]

    ingested = runner.invoke(
        app,
        [
            "library",
            "ingest",
            "note.md",
            "--campaign",
            campaign_id,
            "--title",
            "Silver Gate Note",
        ],
    )
    assert ingested.exit_code == 0, ingested.output
    ingestion_result = json.loads(ingested.output)

    documents = runner.invoke(
        app,
        ["library", "documents", "--campaign", campaign_id],
    )
    assert documents.exit_code == 0, documents.output
    assert json.loads(documents.output) == [
        {
            "id": ingestion_result["document_id"],
            "retired": False,
            "source_path": "root-0/note.md",
        }
    ]

    shown = runner.invoke(
        app,
        [
            "library",
            "show-document",
            ingestion_result["document_id"],
            "--campaign",
            campaign_id,
        ],
    )
    assert shown.exit_code == 0, shown.output
    assert json.loads(shown.output)["content"] == (
        "# Silver Gate\nThe party opened the Silver Gate after the bell rang.\n"
    )

    searched = runner.invoke(
        app,
        ["library", "search", "Silver Gate", "--campaign", campaign_id],
    )
    assert searched.exit_code == 0, searched.output
    search_result = json.loads(searched.output)
    assert search_result["scope"] == {"campaign_id": campaign_id, "corpus": "campaign"}
    assert search_result["results"][0]["citation_id"].startswith("chunk:")


def test_library_api_ingest_documents_show_and_search(
    db_engine: Engine,
    postgres_url: str,
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "sources"
    source_root.mkdir()
    (source_root / "api-note.md").write_text(
        "# Echo Lantern\nThe lantern glows when the tide retreats.\n",
        encoding="utf-8",
    )
    settings = _settings(postgres_url, source_root, tmp_path)
    campaign = CampaignCatalog(db_engine).create_campaign("Library API Campaign")
    application = create_app(settings)

    async def exercise_api() -> tuple[httpx.Response, httpx.Response, httpx.Response, httpx.Response]:
        transport = httpx.ASGITransport(app=application)
        headers = {"Authorization": f"Bearer {_TOKEN}"}
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            ingested = await client.post(
                "/api/library/ingest",
                headers=headers,
                json={
                    "campaign_id": str(campaign.id),
                    "root_label": "root-0",
                    "relative_path": "api-note.md",
                    "title": "Echo Lantern Note",
                    "document_type": "reference_lore",
                    "authority_class": "reference",
                },
            )
            document_id = ingested.json()["document_id"]
            documents = await client.get(
                "/api/library/documents",
                headers=headers,
                params={"campaign_id": str(campaign.id)},
            )
            shown = await client.get(
                f"/api/library/documents/{document_id}",
                headers=headers,
                params={"campaign_id": str(campaign.id)},
            )
            searched = await client.get(
                "/api/library/search",
                headers=headers,
                params={"campaign_id": str(campaign.id), "query": "Echo Lantern"},
            )
        return ingested, documents, shown, searched

    ingested, documents, shown, searched = asyncio.run(exercise_api())
    assert ingested.status_code == 200
    assert documents.status_code == shown.status_code == searched.status_code == 200
    assert documents.json()[0]["id"] == ingested.json()["document_id"]
    assert shown.json()["content"] == (
        "# Echo Lantern\nThe lantern glows when the tide retreats.\n"
    )
    payload = searched.json()
    assert payload["scope"] == {"campaign_id": str(campaign.id), "corpus": "campaign"}
    assert payload["results"][0]["citation_id"].startswith("chunk:")
