"""Private model-gateway SSE adapter tests without a live provider."""

import json
import uuid
from collections.abc import Iterator
from urllib.request import Request

import pytest
from pydantic import SecretStr

from dm_assistant.adapters.model_gateway import (
    ModelGatewayTransportError,
    PiGatewayClient,
)
from dm_assistant.config import ModelGatewayPolicy, Settings
from dm_assistant.modules.modeling import (
    GatewayModelCatalogEntry,
    ModelEndpointProfile,
    PromptMessage,
    ReasoningEffort,
    ReasoningLevel,
    TaskProfile,
    resolve_run_profile,
)
from dm_assistant.orchestration.modeling import GatewayToolSchema


class FakeJsonResponse:
    def __init__(self, status: int, document: object | None = None) -> None:
        self.status = status
        self._document = document

    def __enter__(self) -> "FakeJsonResponse":
        return self

    def __exit__(self, *args: object) -> None:
        del args

    def read(self) -> bytes:
        return json.dumps(self._document).encode("utf-8")


class FakeSseResponse:
    status = 200

    def __init__(self, lines: tuple[bytes, ...]) -> None:
        self._lines = lines

    def __enter__(self) -> "FakeSseResponse":
        return self

    def __exit__(self, *args: object) -> None:
        del args

    def __iter__(self) -> Iterator[bytes]:
        return iter(self._lines)


def _profile():
    endpoint = ModelEndpointProfile(
        profile_id=uuid.uuid4(),
        profile_version="1.0.0",
        runtime_adapter="pi_ai",
        provider_id="faux",
        model_id="faux_deterministic_v1",
        supported_efforts=(ReasoningEffort.STANDARD,),
        context_window_tokens=16_384,
        output_token_limit=4_096,
    )
    task = TaskProfile(
        profile_id=uuid.uuid4(),
        profile_version="1.0.0",
        task_name="dungeon_generation_intent_v1",
        prompt_version="prompt-1",
        instruction_version="instructions-1",
        output_schema_name="dungeon_generation_intent_v1",
        output_schema_version="1.0.0",
        allowed_tools=("validate_dungeon_intent",),
        turn_budget=2,
        tool_budget=1,
        time_budget_seconds=30,
        token_budget=4_096,
        require_citation_ids=False,
        require_authorized_citations=False,
    )
    catalog = GatewayModelCatalogEntry(
        provider_id="faux",
        model_id="faux_deterministic_v1",
        runtime_adapter="pi_ai",
        observed_capabilities=("text", "tool_calls"),
        supported_reasoning_levels=(ReasoningLevel.MEDIUM,),
        context_window_tokens=16_384,
        output_token_limit=4_096,
    )
    return resolve_run_profile(
        endpoint_profile=endpoint,
        task_profile=task,
        catalog_entry=catalog,
    )


def test_private_gateway_client_sends_only_policy_bound_input_and_decodes_sse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[Request] = []
    response = FakeSseResponse(
        (
            b"event: text_delta\n",
            b'data: {"delta":"{\\"intent\\":\\"synthetic\\"}"}\n',
            b"\n",
            b"event: tool_call\n",
            b'data: {"id":"call-1","name":"validate_dungeon_intent","arguments":{}}\n',
            b"\n",
            b"event: usage\n",
            b'data: {"input_tokens":12,"output_tokens":7}\n',
            b"\n",
            b"event: completion\n",
            b'data: {"reason":"stop"}\n',
            b"\n",
            b"event: done\n",
            b"data: {}\n",
            b"\n",
        )
    )

    def fake_urlopen(request: Request, *, timeout: int) -> FakeSseResponse:
        assert timeout == 30
        captured.append(request)
        return response

    monkeypatch.setattr("dm_assistant.adapters.model_gateway.urlopen", fake_urlopen)
    client = PiGatewayClient(
        base_url="http://model-gateway:3000",
        internal_token="gateway-test-token-00000000000000",
    )
    schema = GatewayToolSchema(
        name="validate_dungeon_intent",
        description="Validate typed dungeon intent.",
        parameters={"type": "object"},
    )

    profile = _profile().model_copy(
        update={"override_notes": {"output_token_limit": 512}}
    )
    events: list[tuple[str, dict[str, object]]] = []
    completion = client.complete(
        profile=profile,
        messages=(PromptMessage(role="user", content="Create a synthetic dungeon."),),
        allowed_tools=("validate_dungeon_intent",),
        tool_schemas=(schema,),
        debug=lambda kind, data: events.append((kind, data)),
    )

    assert completion.content == '{"intent":"synthetic"}'
    assert events[0][0] == "harness_request"
    assert events[0][1]["messages"] == [
        {"role": "user", "content": "Create a synthetic dungeon."}
    ]
    assert [kind for kind, _ in events[1:]] == [
        "gateway_event",
        "gateway_event",
        "gateway_event",
        "gateway_event",
        "gateway_event",
    ]
    assert events[1][1] == {
        "event": "text_delta",
        "data": {"delta": '{"intent":"synthetic"}'},
    }
    assert completion.tool_calls[0].tool_name == "validate_dungeon_intent"
    assert completion.input_tokens == 12
    assert completion.output_tokens == 7
    assert len(captured) == 1
    request = captured[0]
    assert request.full_url == "http://model-gateway:3000/v1/streams"
    assert (
        request.get_header("Authorization")
        == "Bearer gateway-test-token-00000000000000"
    )
    payload = json.loads(request.data or b"{}")
    assert payload["provider"] == "faux"
    assert payload["time_limit_seconds"] == 30
    assert payload["output_token_limit"] == 512
    assert payload["tools"] == [schema.model_dump(mode="json", exclude_none=True)]
    assert "constrained_sampling" not in payload["tools"][0]


def test_private_gateway_client_lists_live_catalog_and_coordinates_login(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[Request] = []
    responses = iter(
        (
            FakeJsonResponse(
                200,
                {
                    "providers": [
                        {
                            "id": "openai-codex",
                            "name": "OpenAI Codex",
                            "authenticated": False,
                            "authModes": ["oauth"],
                            "models": [
                                {
                                    "id": "gpt-5.1-codex",
                                    "name": "GPT Codex",
                                    "input": ["text"],
                                    "capabilities": ["text", "thinking", "tool_calls"],
                                    "contextWindow": 128000,
                                    "maxOutputTokens": 16384,
                                }
                            ],
                        }
                    ]
                },
            ),
            FakeJsonResponse(
                202,
                {
                    "login_id": "11111111-1111-1111-1111-111111111111",
                    "provider": "openai-codex",
                    "status": "pending",
                    "events": [
                        {
                            "type": "device_code",
                            "user_code": "ABCD-EFGH",
                            "verification_uri": "https://example.invalid/device",
                        }
                    ],
                },
            ),
        )
    )

    def fake_urlopen(request: Request, *, timeout: int) -> FakeJsonResponse:
        assert timeout == 30
        requests.append(request)
        return next(responses)

    monkeypatch.setattr("dm_assistant.adapters.model_gateway.urlopen", fake_urlopen)
    client = PiGatewayClient(
        base_url="http://model-gateway:3000",
        internal_token="gateway-test-token-00000000000000",
    )

    providers = client.providers()
    login = client.start_login("openai-codex")

    assert providers[0].models[0].id == "gpt-5.1-codex"
    assert providers[0].models[0].context_window == 128000
    assert login.events[0].user_code == "ABCD-EFGH"
    assert requests[0].full_url.endswith("/v1/providers")
    assert json.loads(requests[1].data or b"{}") == {
        "provider": "openai-codex",
        "type": "oauth",
    }


def test_private_gateway_client_rejects_error_events_without_echoing_provider_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = FakeSseResponse(
        (
            b"event: error\n",
            b'data: {"code":"usage_limit","message":"provider secret must not appear"}\n',
            b"\n",
        )
    )

    def fake_urlopen(request: Request, *, timeout: int) -> FakeSseResponse:
        del request, timeout
        return response

    monkeypatch.setattr("dm_assistant.adapters.model_gateway.urlopen", fake_urlopen)
    client = PiGatewayClient(
        base_url="http://model-gateway:3000",
        internal_token="gateway-test-token-00000000000000",
    )

    with pytest.raises(ModelGatewayTransportError) as captured:
        client.complete(
            profile=_profile(),
            messages=(
                PromptMessage(role="user", content="Create a synthetic dungeon."),
            ),
            allowed_tools=(),
            tool_schemas=(),
        )

    assert "provider secret" not in str(captured.value)
    assert "usage limit has been reached" in str(captured.value)


def test_private_gateway_client_requires_enabled_private_settings(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "dm_assistant.config._POSTGRES_DSN_ADAPTER.validate_python",
        lambda _: None,
    )
    settings = Settings.model_construct(
        database_url="postgresql+psycopg://unit:unit-password@db/app",
        source_roots=(tmp_path,),
        asset_root=tmp_path / "assets",
        scratch_root=tmp_path / "scratch",
        api_token="gateway-client-api-token-000000000000",
        session_secret="gateway-client-session-secret-00000000",
        model_gateway_policy=ModelGatewayPolicy.OPTIONAL,
        model_gateway_url="http://model-gateway:3000",
        model_gateway_internal_token="gateway-client-internal-token-0000000",
    )

    object.__setattr__(
        settings,
        "model_gateway_internal_token",
        SecretStr("gateway-client-internal-token-0000000"),
    )
    object.__setattr__(
        settings,
        "api_token",
        SecretStr("gateway-client-api-token-000000000000"),
    )
    object.__setattr__(
        settings,
        "session_secret",
        SecretStr("gateway-client-session-secret-00000000"),
    )
    client = PiGatewayClient.from_settings(settings)

    assert client.base_url.rstrip("/") == "http://model-gateway:3000"


def test_private_gateway_client_reads_enabled_private_settings(tmp_path) -> None:
    settings = Settings.model_construct(
        database_url=SecretStr("postgresql+psycopg://unit:unit-password@db/app"),
        source_roots=(tmp_path,),
        asset_root=tmp_path / "assets",
        scratch_root=tmp_path / "scratch",
        api_token=SecretStr("gateway-client-api-token-000000000000"),
        session_secret=SecretStr("gateway-client-session-secret-00000000"),
        model_gateway_policy=ModelGatewayPolicy.OPTIONAL,
        model_gateway_url="http://model-gateway:3000/",
        model_gateway_internal_token=SecretStr("gateway-client-internal-token-0000000"),
    )

    client = PiGatewayClient.from_settings(settings)

    assert client.base_url == "http://model-gateway:3000/"
