"""Browser login/session/CSRF and shared-shell security tests."""

import asyncio
import re
import uuid
from unittest.mock import MagicMock

import httpx
from fastapi import FastAPI

from dm_assistant.api import create_app
from dm_assistant.campaigns import CampaignCatalog, CampaignSummary
from dm_assistant.config import Settings
from dm_assistant.modules.preparation import PreparationService
from dm_assistant.orchestration.dungeons import DungeonStudioService
from dm_assistant.readiness import configuration_failure_report

TEST_API_TOKEN = "unit-test-token-000000000000000000"


def web_app(test_settings: Settings) -> tuple[FastAPI, MagicMock, uuid.UUID]:
    campaign_id = uuid.uuid4()
    campaigns = MagicMock(spec=CampaignCatalog)
    campaigns.list_campaigns.return_value = (
        CampaignSummary(id=campaign_id, name="Synthetic <script>alert(1)</script>"),
    )
    preparation = MagicMock(spec=PreparationService)
    preparation.list_artifacts.return_value = ()
    dungeons = MagicMock(spec=DungeonStudioService)
    dungeons.export.return_value = (uuid.uuid4(),)
    application = create_app(
        test_settings,
        readiness_check=configuration_failure_report,
        preparation_service=preparation,
        dungeon_studio=dungeons,
        campaign_catalog=campaigns,
    )
    return application, dungeons, campaign_id


async def browser_flow(
    application: FastAPI,
    campaign_id: uuid.UUID,
    dungeons: MagicMock,
) -> None:
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        follow_redirects=False,
    ) as client:
        redirect = await client.get("/dungeons", headers={"Accept": "text/html"})
        assert redirect.status_code == 303
        assert redirect.headers["location"] == "/login"

        login_page = await client.get("/login", headers={"Accept": "text/html"})
        assert login_page.status_code == 200
        assert "DM login" in login_page.text
        assert "content-security-policy" in login_page.headers

        wrong_value = "wrong-browser-token-000000000000000"
        rejected = await client.post(
            "/login",
            data={"token": wrong_value},
            headers={"Accept": "text/html"},
        )
        assert rejected.status_code == 401
        assert "Authentication failed." in rejected.text
        assert wrong_value not in rejected.text

        accepted = await client.post(
            "/login",
            data={"token": TEST_API_TOKEN},
            headers={"Accept": "text/html"},
        )
        assert accepted.status_code == 303
        cookie_header = accepted.headers["set-cookie"]
        assert "HttpOnly" in cookie_header
        assert "SameSite=strict" in cookie_header
        assert TEST_API_TOKEN not in cookie_header

        page = await client.get(
            f"/dungeons?campaign_id={campaign_id}",
            headers={"Accept": "text/html"},
        )
        assert page.status_code == 200
        assert "Dungeon Studio" in page.text
        assert "<script>alert(1)</script>" not in page.text
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page.text
        csrf_match = re.search(r'name="csrf_token" value="([^"]+)"', page.text)
        assert csrf_match is not None
        csrf_token = csrf_match.group(1)

        no_csrf = await client.post(
            "/api/dungeons/export",
            json={
                "campaign_id": str(campaign_id),
                "artifact_version_id": str(uuid.uuid4()),
            },
        )
        assert no_csrf.status_code == 403
        assert no_csrf.json()["error"]["code"] == "forbidden"
        dungeons.export.assert_not_called()

        with_csrf = await client.post(
            "/api/dungeons/export",
            json={
                "campaign_id": str(campaign_id),
                "artifact_version_id": str(uuid.uuid4()),
            },
            headers={"X-CSRF-Token": csrf_token},
        )
        assert with_csrf.status_code == 200
        dungeons.export.assert_called_once()

        bad_logout = await client.post(
            "/logout",
            data={"csrf_token": "wrong"},
            headers={"Accept": "text/html"},
        )
        assert bad_logout.status_code == 403

        logout = await client.post(
            "/logout",
            data={"csrf_token": csrf_token},
            headers={"Accept": "text/html"},
        )
        assert logout.status_code == 303
        assert "Max-Age=0" in logout.headers["set-cookie"]

        after = await client.get("/dungeons", headers={"Accept": "text/html"})
        assert after.status_code == 303
        assert after.headers["location"] == "/login"


def test_browser_login_signed_session_csrf_and_logout(
    test_settings: Settings,
) -> None:
    application, dungeons, campaign_id = web_app(test_settings)
    asyncio.run(browser_flow(application, campaign_id, dungeons))


async def bearer_api_flow(application: FastAPI, campaign_id: uuid.UUID) -> None:
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/dungeons/export",
            json={
                "campaign_id": str(campaign_id),
                "artifact_version_id": str(uuid.uuid4()),
            },
            headers={"Authorization": f"Bearer {TEST_API_TOKEN}"},
        )
        assert response.status_code == 200


def test_bearer_api_write_does_not_require_browser_csrf(
    test_settings: Settings,
) -> None:
    application, _, campaign_id = web_app(test_settings)
    asyncio.run(bearer_api_flow(application, campaign_id))
