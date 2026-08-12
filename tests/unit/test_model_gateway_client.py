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

    completion = client.complete(
        profile=_profile(),
        messages=(PromptMessage(role="user", content="Create a synthetic dungeon."),),
        allowed_tools=("validate_dungeon_intent",),
        tool_schemas=(schema,),
    )

    assert completion.content == '{"intent":"synthetic"}'
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
    assert payload["tools"] == [schema.model_dump(mode="json")]


def test_private_gateway_client_rejects_error_events_without_echoing_provider_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = FakeSseResponse(
        (
            b"event: error\n",
            b'data: {"message":"provider secret must not appear"}\n',
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
