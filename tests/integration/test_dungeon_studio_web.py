"""Authenticated server-rendered Dungeon Studio vertical-slice test."""

import asyncio
import json
import re
import uuid
from pathlib import Path

import httpx
import pytest
from dungeon_fixtures import synthetic_layout_request
from fastapi import FastAPI
from sqlalchemy import Engine

from dm_assistant.api import create_app
from dm_assistant.config import RuntimeEnvironment, Settings
from dm_assistant.db import Campaign, build_session_factory, transactional_session
from dm_assistant.readiness import check_readiness
from dm_dungeon import to_canonical_json

pytestmark = pytest.mark.integration
FIXTURE_PATH = (
    Path(__file__).parents[2]
    / "packages/dungeon-engine/tests/fixtures/sunken_archive.v1.json"
)
TOKEN = "web-integration-token-000000000000000"


def create_campaign(engine: Engine) -> uuid.UUID:
    campaign_id = uuid.uuid4()
    with transactional_session(build_session_factory(engine)) as session:
        session.add(Campaign(id=campaign_id, name="Synthetic Web Campaign"))
    return campaign_id


def layout_document() -> str:
    return to_canonical_json(synthetic_layout_request("package_web_archive"))


class _GatewayResponse:
    def __init__(self, body: bytes) -> None:
        self.status = 200
        self._lines = body.splitlines(keepends=True)

    def __enter__(self) -> "_GatewayResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self._lines)

    def read(self) -> bytes:
        return b"".join(self._lines)


async def run_web_workflow(
    application: FastAPI,
    campaign_id: uuid.UUID,
) -> None:
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        follow_redirects=False,
    ) as client:
        login = await client.post(
            "/login",
            data={"token": TOKEN},
            headers={"Accept": "text/html"},
        )
        assert login.status_code == 303
        listing = await client.get(
            f"/dungeons?campaign_id={campaign_id}",
            headers={"Accept": "text/html"},
        )
        csrf_match = re.search(r'name="csrf_token" value="([^"]+)"', listing.text)
        assert csrf_match is not None
        csrf = csrf_match.group(1)

        generated = await client.post(
            "/dungeons/generate",
            data={
                "campaign_id": str(campaign_id),
                "title": "Synthetic Web Archive",
                "layout_request_json": layout_document(),
                "csrf_token": csrf,
            },
            headers={"Accept": "text/html"},
        )
        assert generated.status_code == 303
        location = generated.headers["location"]
        artifact_match = re.search(r"/dungeons/([0-9a-f-]+)", location)
        assert artifact_match is not None
        artifact_id = uuid.UUID(artifact_match.group(1))

        detail = await client.get(location, headers={"Accept": "text/html"})
        assert detail.status_code == 200
        assert "Synthetic Web Archive" in detail.text
        # Freeze the persistence-shaped baseline for P7-13e: role/ordinal labels
        # and one ambiguous Open/download action are deliberate current defects.
        assert "player_png #0" in detail.text
        assert "dm_png #0" in detail.text
        assert "Open/download (image/png)" in detail.text
        assert "Exact-scale print maps are temporarily disabled" in detail.text
        assert "Create Roll20 exports" in detail.text
        assert "does not establish planned events as campaign canon" in detail.text
        version_match = re.search(
            r'name="artifact_version_id" value="([0-9a-f-]+)"', detail.text
        )
        assert version_match is not None
        version_id = uuid.UUID(version_match.group(1))

        web_print = await client.post(
            f"/dungeons/{artifact_id}/export",
            data={
                "campaign_id": str(campaign_id),
                "artifact_version_id": str(version_id),
                "export_format": "pdf",
                "csrf_token": csrf,
            },
            headers={"Accept": "text/html"},
        )
        assert web_print.status_code == 409
        assert "dungeon_print_export_disabled" in web_print.text

        rejected = await client.post(
            f"/dungeons/{artifact_id}/approve",
            data={
                "campaign_id": str(campaign_id),
                "artifact_version_id": str(version_id),
                "reason": "Synthetic approval.",
                "csrf_token": "wrong",
            },
            headers={"Accept": "text/html"},
        )
        assert rejected.status_code == 403

        approved = await client.post(
            f"/dungeons/{artifact_id}/approve",
            data={
                "campaign_id": str(campaign_id),
                "artifact_version_id": str(version_id),
                "reason": "Reviewed clean and DM previews for synthetic play.",
                "csrf_token": csrf,
            },
            headers={"Accept": "text/html"},
        )
        assert approved.status_code == 303
        approved_detail = await client.get(
            approved.headers["location"],
            headers={"Accept": "text/html"},
        )
        assert "approved_for_play" in approved_detail.text
        assert "Approve preparation for play (not canon)" not in approved_detail.text

        api_generated = await client.post(
            "/api/dungeons/generate",
            json={
                "campaign_id": str(campaign_id),
                "title": "Synthetic API Archive",
                "layout_request": json.loads(layout_document()),
                "created_by": "synthetic-dm",
            },
            headers={"Authorization": f"Bearer {TOKEN}"},
        )
        assert api_generated.status_code == 200, api_generated.text
        assert api_generated.json()["success"] is True
        api_print = await client.post(
            "/api/dungeons/export",
            json={
                "campaign_id": str(campaign_id),
                "artifact_version_id": api_generated.json()["artifact_version_id"],
                "export_format": "pdf",
            },
            headers={"Authorization": f"Bearer {TOKEN}"},
        )
        assert api_print.status_code == 409
        assert api_print.json()["error"]["code"] == "dungeon_print_export_disabled"


def test_authenticated_web_generation_and_explicit_approval(
    db_engine: Engine,
    postgres_url: str,
    tmp_path: Path,
) -> None:
    campaign_id = create_campaign(db_engine)
    settings = Settings(
        environment=RuntimeEnvironment.TEST,
        database_url=postgres_url,
        source_roots=(FIXTURE_PATH.parent,),
        asset_root=tmp_path / "web-assets",
        scratch_root=tmp_path / "web-scratch",
        api_token=TOKEN,
        session_secret="web-session-secret-00000000000000000",
    )
    application = create_app(
        settings,
        readiness_check=lambda: check_readiness(db_engine),
    )

    asyncio.run(run_web_workflow(application, campaign_id))
