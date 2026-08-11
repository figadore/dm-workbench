"""Default-deny API authentication, correlation, and error tests."""

import asyncio
import re

import httpx
import pytest
from fastapi import FastAPI

from dm_assistant import __version__
from dm_assistant.api import create_app
from dm_assistant.config import Settings
from dm_assistant.readiness import (
    EXPECTED_SCHEMA_REVISION,
    ComponentName,
    ComponentReadiness,
    ComponentState,
    ReadinessCode,
    ReadinessReport,
)

TEST_API_TOKEN = "unit-test-token-000000000000000000"


async def request(
    application: FastAPI,
    path: str,
    *,
    token: str | None = None,
    request_id: str | None = None,
) -> httpx.Response:
    headers: dict[str, str] = {}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    if request_id is not None:
        headers["X-Request-ID"] = request_id
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.get(path, headers=headers)


def ready_report() -> ReadinessReport:
    return ReadinessReport(
        ready=True,
        components=(
            ComponentReadiness(
                name=ComponentName.CONFIGURATION,
                state=ComponentState.READY,
            ),
            ComponentReadiness(
                name=ComponentName.DATABASE,
                state=ComponentState.READY,
                version="16",
                expected_version="16",
            ),
            ComponentReadiness(
                name=ComponentName.PGVECTOR,
                state=ComponentState.READY,
                version="0.8.1",
                expected_version="0.8.1",
            ),
            ComponentReadiness(
                name=ComponentName.SCHEMA,
                state=ComponentState.READY,
                version=EXPECTED_SCHEMA_REVISION,
                expected_version=EXPECTED_SCHEMA_REVISION,
            ),
        ),
    )


def test_openapi_is_authenticated_and_exposes_only_health_routes(
    test_settings: Settings,
) -> None:
    application = create_app(test_settings)

    rejected = asyncio.run(request(application, "/openapi.json"))
    response = asyncio.run(request(application, "/openapi.json", token=TEST_API_TOKEN))

    assert rejected.status_code == 401
    assert rejected.headers["www-authenticate"] == "Bearer"
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"] == {
        "title": "DM Assistant",
        "version": __version__,
    }
    assert set(schema["paths"]) == {
        "/health/live",
        "/health/ready",
        "/api/dungeons",
        "/api/dungeons/generate",
        "/api/dungeons/regenerate",
        "/api/dungeons/export",
        "/api/dungeons/approve",
        "/api/dungeons/{artifact_id}",
        "/api/dungeons/{artifact_id}/compare",
    }
    assert "/login" not in schema["paths"]


def test_protected_route_rejects_missing_and_invalid_credentials_generically(
    test_settings: Settings,
) -> None:
    application = create_app(test_settings, include_test_routes=True)

    missing = asyncio.run(request(application, "/__test__/protected"))
    invalid_value = "wrong-token-value-0000000000000000"
    invalid = asyncio.run(
        request(application, "/__test__/protected", token=invalid_value)
    )

    assert missing.status_code == invalid.status_code == 401
    assert missing.json()["error"]["code"] == "authentication_required"
    assert invalid.json()["error"]["message"] == "Authentication required."
    assert invalid_value not in invalid.text
    assert TEST_API_TOKEN not in invalid.text


def test_valid_token_sets_dm_principal_and_preserves_safe_request_id(
    test_settings: Settings,
) -> None:
    application = create_app(test_settings, include_test_routes=True)

    response = asyncio.run(
        request(
            application,
            "/__test__/protected",
            token=TEST_API_TOKEN,
            request_id="req:test-123",
        )
    )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req:test-123"
    assert response.json() == {
        "principal_id": "dm",
        "scope": "dm",
        "request_id": "req:test-123",
    }


def test_invalid_request_id_is_replaced_and_returned_on_auth_failure(
    test_settings: Settings,
) -> None:
    application = create_app(test_settings, include_test_routes=True)

    response = asyncio.run(
        request(
            application,
            "/__test__/protected",
            request_id="bad id with spaces and secret?",
        )
    )

    generated = response.headers["x-request-id"]
    assert response.status_code == 401
    assert re.fullmatch(r"[0-9a-f]{32}", generated)
    assert response.json()["error"]["request_id"] == generated
    assert "bad id" not in response.text


def test_rejected_unmatched_path_is_not_written_to_logs(
    test_settings: Settings,
    capsys: pytest.CaptureFixture[str],
) -> None:
    application = create_app(test_settings)
    sensitive_path = "/unmatched/do-not-log-this-source-text"

    response = asyncio.run(request(application, sensitive_path))
    captured = capsys.readouterr()

    assert response.status_code == 401
    assert sensitive_path not in captured.err
    assert "do-not-log-this-source-text" not in captured.err
    assert '"route":"<unmatched>"' in captured.err


def test_liveness_is_public_and_never_invokes_database_readiness(
    test_settings: Settings,
) -> None:
    def forbidden_readiness() -> ReadinessReport:
        raise AssertionError("liveness must not touch readiness dependencies")

    application = create_app(test_settings, readiness_check=forbidden_readiness)

    response = asyncio.run(request(application, "/health/live"))

    assert response.status_code == 200
    assert response.json() == {"status": "live"}
    assert "x-request-id" in response.headers


def test_readiness_is_public_and_returns_minimal_success(
    test_settings: Settings,
) -> None:
    application = create_app(test_settings, readiness_check=ready_report)

    response = asyncio.run(request(application, "/health/ready"))

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {
            "configuration": "ready",
            "database": "ready",
            "pgvector": "ready",
            "schema": "ready",
        },
    }
    assert "version" not in response.text


def test_readiness_failure_is_distinct_from_liveness_without_leaking_details(
    test_settings: Settings,
) -> None:
    unavailable = ReadinessReport(
        ready=False,
        components=(
            ComponentReadiness(
                name=ComponentName.CONFIGURATION,
                state=ComponentState.READY,
            ),
            ComponentReadiness(
                name=ComponentName.DATABASE,
                state=ComponentState.NOT_READY,
                expected_version="16",
                code=ReadinessCode.UNAVAILABLE,
            ),
            ComponentReadiness(
                name=ComponentName.PGVECTOR,
                state=ComponentState.NOT_CHECKED,
                expected_version="0.8.1",
                code=ReadinessCode.UNAVAILABLE,
            ),
            ComponentReadiness(
                name=ComponentName.SCHEMA,
                state=ComponentState.NOT_CHECKED,
                expected_version=EXPECTED_SCHEMA_REVISION,
                code=ReadinessCode.UNAVAILABLE,
            ),
        ),
    )
    application = create_app(test_settings, readiness_check=lambda: unavailable)

    response = asyncio.run(request(application, "/health/ready"))
    live = asyncio.run(request(application, "/health/live"))

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {
            "configuration": "ready",
            "database": "not_ready",
            "pgvector": "not_checked",
            "schema": "not_checked",
        },
    }
    assert live.status_code == 200
    assert "postgresql" not in response.text
    assert "unavailable" not in response.text


def test_domain_error_handler_uses_same_safe_envelope(
    test_settings: Settings,
) -> None:
    application = create_app(test_settings, include_test_routes=True)

    response = asyncio.run(
        request(
            application,
            "/__test__/missing",
            token=TEST_API_TOKEN,
            request_id="req-missing",
        )
    )

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "The requested resource was not found.",
            "request_id": "req-missing",
        }
    }
