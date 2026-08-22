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
from sqlalchemy import Engine, select

from dm_assistant.api import create_app
from dm_assistant.config import ModelGatewayPolicy, RuntimeEnvironment, Settings
from dm_assistant.db import Campaign, build_session_factory, transactional_session
from dm_assistant.modules.preparation.models import GenerationRun

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
    proposal = {
        "proposal_version": "1",
        "plan": {
            "schema_version": "1.0.0",
            "title": "Synthetic Archive",
            "premise": "A synthetic archive contains a sealed ledger.",
            "themes": ["salt"],
            "rooms": [
                {
                    "ref": "entry",
                    "name": "Entry",
                    "role": "entrance",
                    "purpose": "Establish the archive.",
                },
                {
                    "ref": "stacks",
                    "name": "Stacks",
                    "role": "exploration",
                    "purpose": "Reveal its history.",
                },
                {
                    "ref": "gallery",
                    "name": "Gallery",
                    "role": "exploration",
                    "purpose": "Foreshadow the vault.",
                },
                {
                    "ref": "vault",
                    "name": "Vault",
                    "role": "objective",
                    "purpose": "Hold the ledger.",
                },
            ],
            "critical_path": ["entry", "stacks", "gallery", "vault"],
            "room_contents": [{"room_ref": "vault", "objective": "Sealed Ledger"}],
        },
    }

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
                "arguments": {"proposal": proposal},
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

    asyncio.run(flow())

    with transactional_session(build_session_factory(db_engine)) as session:
        run = session.scalar(
            select(GenerationRun).where(
                GenerationRun.campaign_id == campaign_id,
                GenerationRun.generation_kind == "prompted_dungeon_layout",
            )
        )
        assert run is not None
        assert run.schema_versions["dungeon_package"] == "1.0.0"
        assert run.schema_versions["dungeon_generation_proposal"] == "1.0.0"
        assert (
            run.generator_versions["dungeon_mechanics_policy"]
            == "dungeon-mechanics-policy-v1"
        )
        assert run.generator_versions["plan_compiler"] == "dungeon-plan-compiler-v1"
