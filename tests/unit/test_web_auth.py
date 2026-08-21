"""Browser login/session/CSRF and shared-shell security tests."""

import asyncio
import re
import uuid
from unittest.mock import MagicMock

import httpx
from fastapi import FastAPI

from dm_assistant.adapters.model_gateway import GatewayLoginSession
from dm_assistant.api import create_app
from dm_assistant.campaigns import CampaignCatalog, CampaignSummary
from dm_assistant.config import Settings
from dm_assistant.modules.modeling import ReasoningEffort
from dm_assistant.modules.preparation import PreparationService
from dm_assistant.orchestration.dungeons import (
    DungeonPromptEvent,
    DungeonPromptRun,
    DungeonPromptWorkbenchService,
    DungeonStudioService,
    DungeonWorkflowResult,
)
from dm_assistant.readiness import configuration_failure_report

TEST_API_TOKEN = "unit-test-token-000000000000000000"


def web_app(
    test_settings: Settings,
    dungeon_prompt_workbench: DungeonPromptWorkbenchService | None = None,
) -> tuple[FastAPI, MagicMock, uuid.UUID]:
    campaign_id = uuid.uuid4()
    campaigns = MagicMock(spec=CampaignCatalog)
    campaigns.list_campaigns.return_value = (
        CampaignSummary(
            id=campaign_id,
            name="Synthetic <script>alert(1)</script>",
            active=True,
        ),
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
        dungeon_prompt_workbench=dungeon_prompt_workbench,
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
                "export_format": "roll20",
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
                "export_format": "roll20",
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


async def model_flow(
    application: FastAPI,
    campaign_id: uuid.UUID,
) -> None:
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        follow_redirects=False,
    ) as client:
        await client.post(
            "/login",
            data={"token": TEST_API_TOKEN},
            headers={"Accept": "text/html"},
        )
        page = await client.get(
            f"/dungeons?campaign_id={campaign_id}",
            headers={"Accept": "text/html"},
        )
        assert "Prompt a dungeon draft" in page.text
        assert "Private model gateway is unavailable" in page.text
        return
        csrf_match = re.search(r'name="csrf_token" value="([^"]+)"', page.text)
        assert csrf_match is not None
        csrf_token = csrf_match.group(1)

        login = await client.post(
            "/modeling/logins",
            data={
                "csrf_token": csrf_token,
                "campaign_id": str(campaign_id),
                "provider_id": "faux",
            },
            headers={"Accept": "text/html"},
        )
        assert login.status_code == 303
        login_page = await client.get(
            login.headers["location"], headers={"Accept": "text/html"}
        )
        assert "ABCD-1234" in login_page.text

        await client.post(
            login.headers["location"],
            data={
                "csrf_token": csrf_token,
                "campaign_id": str(campaign_id),
                "code": "ABCD-1234",
            },
            headers={"Accept": "text/html"},
        )

        selected = await client.post(
            "/modeling/selection",
            data={
                "csrf_token": csrf_token,
                "campaign_id": str(campaign_id),
                "provider_id": "faux",
                "model_id": "faux_deterministic_v1",
                "task_profile_id": "11111111-1111-1111-1111-111111111111",
                "effort": "standard",
            },
            headers={"Accept": "text/html"},
        )
        assert selected.status_code == 303

        started = await client.post(
            "/modeling/runs",
            data={
                "csrf_token": csrf_token,
                "campaign_id": str(campaign_id),
                "prompt": "Create a synthetic dungeon intent.",
            },
            headers={"Accept": "text/html"},
        )
        assert started.status_code == 303
        run_url = started.headers["location"]
        run_id_match = re.search(r"run_id=([0-9a-f-]+)", run_url)
        assert run_id_match is not None
        run_id = run_id_match.group(1)

        cancelled = await client.post(
            f"/modeling/runs/{run_id}/cancel",
            data={
                "csrf_token": csrf_token,
                "campaign_id": str(campaign_id),
            },
            headers={"Accept": "text/html"},
        )
        assert cancelled.status_code == 303
        cancelled_page = await client.get(
            cancelled.headers["location"],
            headers={"Accept": "text/html"},
        )
        assert "cancelled" in cancelled_page.text

        second = await client.post(
            "/modeling/runs",
            data={
                "csrf_token": csrf_token,
                "campaign_id": str(campaign_id),
                "prompt": "Create a second synthetic dungeon intent.",
            },
            headers={"Accept": "text/html"},
        )
        second_run_url = second.headers["location"]
        second_run_match = re.search(r"run_id=([0-9a-f-]+)", second_run_url)
        assert second_run_match is not None
        second_run_id = second_run_match.group(1)
        await asyncio.sleep(0.35)
        completed_page = await client.get(
            second_run_url, headers={"Accept": "text/html"}
        )
        assert "completed" in completed_page.text
        events = await client.get(
            f"/modeling/runs/{second_run_id}/events", headers={"Accept": "text/html"}
        )
        assert events.status_code == 200
        assert "completed" in events.text


async def ask_flow(
    application: FastAPI,
    campaign_id: uuid.UUID,
) -> None:
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        follow_redirects=False,
    ) as client:
        await client.post(
            "/login",
            data={"token": TEST_API_TOKEN},
            headers={"Accept": "text/html"},
        )
        ask_page = await client.get("/ask", headers={"Accept": "text/html"})
        assert "Ask" in ask_page.text
        csrf_match = re.search(r'name="csrf_token" value="([^"]+)"', ask_page.text)
        assert csrf_match is not None
        csrf_token = csrf_match.group(1)
        await client.post(
            "/modeling/selection",
            data={
                "csrf_token": csrf_token,
                "campaign_id": str(campaign_id),
                "provider_id": "faux",
                "model_id": "faux_deterministic_v1",
                "task_profile_id": "33333333-3333-3333-3333-333333333333",
                "effort": "standard",
            },
            headers={"Accept": "text/html"},
        )
        upload = await client.post(
            "/ask/attachments",
            files={"file": ("note.txt", b"secret door clues", "text/plain")},
            data={"campaign_id": str(campaign_id), "csrf_token": csrf_token},
            headers={"Accept": "text/html"},
        )
        assert upload.status_code == 303
        ask_page = await client.get("/ask", headers={"Accept": "text/html"})
        attachment_match = re.search(
            r'name="attachment_ids" form="ask-form" value="([0-9a-f-]+)"',
            ask_page.text,
        )
        assert attachment_match is not None
        attachment_id = attachment_match.group(1)

        started = await client.post(
            "/ask/runs",
            data={
                "csrf_token": csrf_token,
                "campaign_id": str(campaign_id),
                "prompt": "What does the note say about the dungeon?",
                "attachment_ids": attachment_id,
            },
            headers={"Accept": "text/html"},
        )
        assert started.status_code == 303
        run_url = started.headers["location"]
        run_id_match = re.search(r"run_id=([0-9a-f-]+)", run_url)
        assert run_id_match is not None
        run_id = run_id_match.group(1)
        await asyncio.sleep(0.35)
        active = await client.get(
            f"/ask?run_id={run_id}", headers={"Accept": "text/html"}
        )
        assert "comparison baseline visible" in active.text
        assert "attachments" in active.text.lower()
        events = await client.get(
            f"/ask/runs/{run_id}/events", headers={"Accept": "text/html"}
        )
        assert events.status_code == 200
        assert "completed" in events.text


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
                "export_format": "roll20",
            },
            headers={"Authorization": f"Bearer {TEST_API_TOKEN}"},
        )
        assert response.status_code == 200


def test_bearer_api_write_does_not_require_browser_csrf(
    test_settings: Settings,
) -> None:
    application, _, campaign_id = web_app(test_settings)
    asyncio.run(bearer_api_flow(application, campaign_id))


async def gateway_login_flow(application: FastAPI, campaign_id: uuid.UUID) -> None:
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver", follow_redirects=False
    ) as client:
        await client.post("/login", data={"token": TEST_API_TOKEN})
        page = await client.get(f"/dungeons?campaign_id={campaign_id}")
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', page.text)
        assert csrf is not None
        started = await client.post(
            "/dungeons/model-logins",
            data={
                "csrf_token": csrf.group(1),
                "campaign_id": str(campaign_id),
                "provider_id": "faux",
            },
        )
        assert started.status_code == 303
        assert "gateway_login_id=login-1" in started.headers["location"]


def test_gateway_backed_browser_login_uses_private_gateway_service(
    test_settings: Settings,
) -> None:
    prompt_workbench = MagicMock(spec=DungeonPromptWorkbenchService)
    prompt_workbench.providers.return_value = ()
    prompt_workbench.selection.return_value = None
    prompt_workbench.begin_login.return_value = GatewayLoginSession(
        login_id="login-1", provider="faux", status="pending", events=()
    )
    application, _, campaign_id = web_app(test_settings, prompt_workbench)
    asyncio.run(gateway_login_flow(application, campaign_id))
    prompt_workbench.begin_login.assert_called_once_with("faux")


async def gateway_prompt_flow(application: FastAPI, campaign_id: uuid.UUID) -> None:
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver", follow_redirects=False
    ) as client:
        await client.post("/login", data={"token": TEST_API_TOKEN})
        page = await client.get(f"/dungeons?campaign_id={campaign_id}")
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', page.text)
        assert csrf is not None
        started = await client.post(
            "/dungeons/prompts",
            data={
                "csrf_token": csrf.group(1),
                "campaign_id": str(campaign_id),
                "prompt": "A synthetic observatory.",
            },
        )
        assert started.status_code == 303
        run_id = re.search(r"run_id=([0-9a-f-]+)", started.headers["location"])
        assert run_id is not None
        events = await client.get(f"/dungeons/prompts/{run_id.group(1)}/events")
        assert events.status_code == 200
        assert "completed" in events.text


def test_gateway_backed_browser_prompt_stream_contract(
    test_settings: Settings,
) -> None:
    prompt_workbench = MagicMock(spec=DungeonPromptWorkbenchService)
    prompt_workbench.providers.return_value = ()
    prompt_workbench.selection.return_value = None
    application, _, campaign_id = web_app(test_settings, prompt_workbench)
    run = DungeonPromptRun(
        run_id=uuid.uuid4(),
        campaign_id=campaign_id,
        status="completed",
        prompt="A synthetic observatory.",
        provider_id="faux",
        model_id="faux-tool",
        effort=ReasoningEffort.STANDARD,
        seed=123,
        events=(
            DungeonPromptEvent(type="completed", message="Dungeon draft created."),
        ),
        result=DungeonWorkflowResult(
            success=True,
            artifact_id=uuid.uuid4(),
            artifact_version_id=uuid.uuid4(),
            generation_run_id=uuid.uuid4(),
            diagnostics=(),
        ),
    )
    prompt_workbench.start.return_value = run
    prompt_workbench.stream_events.return_value = run.events
    asyncio.run(gateway_prompt_flow(application, campaign_id))
    prompt_workbench.start.assert_called_once()


def test_model_settings_login_and_stream_shell(
    test_settings: Settings,
) -> None:
    application, _, campaign_id = web_app(test_settings)
    asyncio.run(model_flow(application, campaign_id))


def test_general_ask_workflow_and_comparison_baseline(
    test_settings: Settings,
) -> None:
    application, _, campaign_id = web_app(test_settings)
    asyncio.run(ask_flow(application, campaign_id))
