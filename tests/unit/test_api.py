"""API application smoke tests."""

import asyncio

import httpx

from dm_assistant import __version__
from dm_assistant.api import create_app


async def get_openapi_schema() -> httpx.Response:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.get("/openapi.json")


def test_app_factory_exposes_metadata_without_business_routes() -> None:
    response = asyncio.run(get_openapi_schema())

    assert response.status_code == 200
    schema = response.json()
    assert schema["info"] == {
        "title": "DM Assistant",
        "version": __version__,
    }
    assert schema["paths"] == {}
