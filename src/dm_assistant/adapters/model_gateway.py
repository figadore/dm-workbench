"""Private Node gateway adapter for bounded Python model workflows."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError

from dm_assistant.config import ModelGatewayPolicy, Settings
from dm_assistant.modules.modeling import (
    PromptMessage,
    ResolvedModelRunProfile,
    ToolCall,
)
from dm_assistant.orchestration.modeling import (
    GatewayCompletion,
    GatewayToolSchema,
)


class ModelGatewayTransportError(RuntimeError):
    """Raised when the private gateway cannot return a valid bounded completion."""


class GatewayCatalogModel(BaseModel):
    """Display-safe model metadata returned by the private gateway."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=False)

    id: str
    name: str
    input: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    context_window: int = Field(alias="contextWindow", ge=1)
    max_output_tokens: int = Field(alias="maxOutputTokens", ge=1)


class GatewayProvider(BaseModel):
    """Display-safe provider/authentication/catalog metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=False)

    id: str
    name: str
    authenticated: bool
    auth_modes: tuple[str, ...] = Field(alias="authModes")
    models: tuple[GatewayCatalogModel, ...]


class GatewayLoginEvent(BaseModel):
    """Non-secret provider-login event suitable for a CLI or browser."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=False)

    type: str
    message: str | None = None
    url: str | None = None
    instructions: str | None = None
    user_code: str | None = None
    verification_uri: str | None = None
    interval_seconds: int | None = None
    expires_in_seconds: int | None = None
    prompt_id: str | None = None
    prompt_type: str | None = None
    placeholder: str | None = None
    options: tuple[dict[str, JsonValue], ...] | None = None


class GatewayLoginSession(BaseModel):
    """Current non-secret state for one gateway-owned provider login."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=False)

    login_id: str
    provider: str
    status: str
    events: tuple[GatewayLoginEvent, ...]


@dataclass(frozen=True, slots=True)
class PiGatewayClient:
    """Synchronous private-gateway client with strict normalized SSE decoding."""

    base_url: str
    internal_token: str

    @classmethod
    def from_settings(cls, settings: Settings) -> PiGatewayClient:
        """Construct the adapter only when the private gateway is enabled."""

        if (
            settings.model_gateway_policy is ModelGatewayPolicy.DISABLED
            or settings.model_gateway_url is None
            or settings.model_gateway_internal_token is None
        ):
            raise ValueError("private model gateway is not configured")
        return cls(
            base_url=str(settings.model_gateway_url),
            internal_token=settings.model_gateway_internal_token.get_secret_value(),
        )

    def providers(self) -> tuple[GatewayProvider, ...]:
        """Return the allowlisted provider/model catalog without credentials."""

        document = self._json_request("/v1/providers")
        values = document.get("providers")
        if not isinstance(values, list):
            raise ModelGatewayTransportError(
                "model gateway returned an invalid catalog"
            )
        try:
            return tuple(GatewayProvider.model_validate(value) for value in values)
        except ValidationError as error:
            raise ModelGatewayTransportError(
                "model gateway returned an invalid catalog"
            ) from error

    def start_login(
        self, provider: str, auth_type: str = "oauth"
    ) -> GatewayLoginSession:
        """Start a gateway-owned OAuth/API-key login without returning credentials."""

        return self._login_session(
            self._json_request(
                "/v1/auth/login",
                method="POST",
                body={"provider": provider, "type": auth_type},
                expected_status=202,
            )
        )

    def login_status(self, login_id: str) -> GatewayLoginSession:
        """Poll one gateway-owned login session."""

        return self._login_session(self._json_request(f"/v1/auth/login/{login_id}"))

    def respond_to_login(self, login_id: str, prompt_id: str, value: str) -> None:
        """Answer a non-secret OAuth coordination prompt."""

        self._json_request(
            f"/v1/auth/login/{login_id}/prompts/{prompt_id}",
            method="POST",
            body={"value": value},
            expected_status=204,
        )

    def logout(self, provider: str) -> None:
        """Delete one provider credential in the gateway-owned store."""

        self._json_request(
            "/v1/auth/logout",
            method="POST",
            body={"provider": provider},
            expected_status=204,
        )

    def complete(
        self,
        *,
        profile: ResolvedModelRunProfile,
        messages: tuple[PromptMessage, ...],
        allowed_tools: tuple[str, ...],
        tool_schemas: tuple[GatewayToolSchema, ...],
    ) -> GatewayCompletion:
        if any(message.role != "user" for message in messages):
            raise ModelGatewayTransportError(
                "private gateway accepts only user messages"
            )
        if tuple(schema.name for schema in tool_schemas) != allowed_tools:
            raise ModelGatewayTransportError(
                "gateway tool schemas do not match the allowed tool policy"
            )

        body = json.dumps(
            {
                "provider": profile.provider_id,
                "model": profile.model_id,
                "effort": profile.requested_effort.value,
                "messages": [
                    {"role": message.role, "content": message.content}
                    for message in messages
                ],
                "tools": [schema.model_dump(mode="json") for schema in tool_schemas],
                "output_token_limit": min(profile.token_budget, 16_384),
                "run_id": str(uuid4()),
            },
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        request = Request(
            f"{self.base_url.rstrip('/')}/v1/streams",
            data=body,
            headers={
                "Authorization": f"Bearer {self.internal_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        deadline = time.monotonic() + profile.time_budget_seconds
        try:
            with urlopen(request, timeout=profile.time_budget_seconds) as response:
                if response.status != 200:
                    raise ModelGatewayTransportError(
                        f"model gateway returned HTTP {response.status}"
                    )
                return _decode_sse(response, deadline)
        except HTTPError as error:
            raise ModelGatewayTransportError(
                f"model gateway returned HTTP {error.code}"
            ) from error
        except URLError as error:
            raise ModelGatewayTransportError("model gateway is unavailable") from error
        except TimeoutError as error:
            raise ModelGatewayTransportError(
                "model gateway request timed out"
            ) from error

    def _json_request(
        self,
        path: str,
        *,
        method: str = "GET",
        body: dict[str, str] | None = None,
        expected_status: int = 200,
    ) -> dict[str, object]:
        data = None
        headers = {"Authorization": f"Bearer {self.internal_token}"}
        if body is not None:
            data = json.dumps(
                body, allow_nan=False, separators=(",", ":"), sort_keys=True
            ).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(
            f"{self.base_url.rstrip('/')}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=30) as response:
                if response.status != expected_status:
                    raise ModelGatewayTransportError(
                        f"model gateway returned HTTP {response.status}"
                    )
                if expected_status == 204:
                    return {}
                document = json.loads(response.read())
        except HTTPError as error:
            raise ModelGatewayTransportError(
                f"model gateway returned HTTP {error.code}"
            ) from error
        except (URLError, TimeoutError) as error:
            raise ModelGatewayTransportError("model gateway is unavailable") from error
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ModelGatewayTransportError(
                "model gateway returned invalid JSON"
            ) from error
        if not isinstance(document, dict):
            raise ModelGatewayTransportError("model gateway returned invalid JSON")
        return document

    @staticmethod
    def _login_session(document: dict[str, object]) -> GatewayLoginSession:
        try:
            return GatewayLoginSession.model_validate(document)
        except ValidationError as error:
            raise ModelGatewayTransportError(
                "model gateway returned invalid login status"
            ) from error


def _decode_sse(response: Any, deadline: float) -> GatewayCompletion:
    content: list[str] = []
    tool_calls: list[ToolCall] = []
    input_tokens = 0
    output_tokens = 0
    event_name: str | None = None
    data_lines: list[str] = []
    completed = False

    for raw_line in response:
        if time.monotonic() >= deadline:
            raise ModelGatewayTransportError("model gateway request timed out")
        line = raw_line.decode("utf-8").rstrip("\r\n")
        if not line:
            if event_name is not None:
                payload = _event_payload(event_name, data_lines)
                if event_name == "text_delta":
                    delta = payload.get("delta")
                    if not isinstance(delta, str):
                        raise ModelGatewayTransportError(
                            "model gateway sent invalid text delta"
                        )
                    content.append(delta)
                elif event_name == "tool_call":
                    tool_calls.append(_tool_call(payload))
                elif event_name == "usage":
                    input_tokens, output_tokens = _usage(payload)
                elif event_name == "completion":
                    completed = True
                elif event_name == "error":
                    raise ModelGatewayTransportError("model gateway reported an error")
                elif event_name == "done":
                    break
            event_name = None
            data_lines = []
            continue
        if line.startswith("event:"):
            event_name = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            data_lines.append(line.removeprefix("data:").strip())

    if not completed:
        raise ModelGatewayTransportError(
            "model gateway stream ended without completion"
        )
    return GatewayCompletion(
        content="".join(content) or None,
        tool_calls=tuple(tool_calls),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def _event_payload(event_name: str, data_lines: list[str]) -> dict[str, object]:
    try:
        value = json.loads("\n".join(data_lines))
    except json.JSONDecodeError as error:
        raise ModelGatewayTransportError(
            f"model gateway sent invalid {event_name} event"
        ) from error
    if not isinstance(value, dict):
        raise ModelGatewayTransportError(
            f"model gateway sent invalid {event_name} event"
        )
    return value


def _tool_call(payload: dict[str, object]) -> ToolCall:
    name = payload.get("name")
    call_id = payload.get("id")
    arguments = payload.get("arguments")
    if (
        not isinstance(name, str)
        or not isinstance(call_id, str)
        or not isinstance(arguments, dict)
    ):
        raise ModelGatewayTransportError("model gateway sent invalid tool call")
    try:
        return ToolCall(
            tool_name=name,
            call_id=call_id,
            arguments=arguments,
        )
    except ValueError as error:
        raise ModelGatewayTransportError(
            "model gateway sent invalid tool call"
        ) from error


def _usage(payload: dict[str, object]) -> tuple[int, int]:
    input_tokens = payload.get("input_tokens", 0)
    output_tokens = payload.get("output_tokens", 0)
    if (
        not isinstance(input_tokens, int)
        or isinstance(input_tokens, bool)
        or input_tokens < 0
        or not isinstance(output_tokens, int)
        or isinstance(output_tokens, bool)
        or output_tokens < 0
    ):
        raise ModelGatewayTransportError("model gateway sent invalid usage")
    return input_tokens, output_tokens
