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
from sqlalchemy import Engine

from dm_assistant.api import create_app
from dm_assistant.config import ModelGatewayPolicy, RuntimeEnvironment, Settings
from dm_assistant.db import Campaign, build_session_factory, transactional_session
from dm_assistant.modules.modeling import DungeonGenerationIntentV1
from dm_dungeon import read_dungeon_package

pytestmark = pytest.mark.integration
TOKEN = "web-prompt-token-000000000000000"
FIXTURE_PATH = (
    Path(__file__).parents[2]
    / "packages/dungeon-engine/tests/fixtures/sunken_archive.v1.json"
)


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
    package = read_dungeon_package(FIXTURE_PATH)
    intent = DungeonGenerationIntentV1(
        schema_version="1.0.0",
        intent="Synthetic archive",
        brief=package.brief,
        topology=package.topology,
    )

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
            return _Response(
                f'event: text_delta\ndata: {{"delta":{json.dumps(intent.model_dump_json())}}}\n\nevent: completion\ndata: {{}}\n\n'.encode()
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
            await asyncio.sleep(0.5)
            result = await client.get(started.headers["location"])
            assert "Dungeon draft created." in result.text
            assert "Inspect generated draft" in result.text

    asyncio.run(flow())
