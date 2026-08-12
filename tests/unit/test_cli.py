"""CLI smoke tests."""

import pytest
from typer.testing import CliRunner

from dm_assistant import __version__
from dm_assistant.adapters.model_gateway import (
    GatewayCatalogModel,
    GatewayLoginEvent,
    GatewayLoginSession,
    GatewayProvider,
)
from dm_assistant.cli.main import _resolve_dungeon_model_selection, app

runner = CliRunner()


class _LoginGateway:
    def __init__(self) -> None:
        self.login_started = False
        self.catalog_calls = 0

    def providers(self) -> tuple[GatewayProvider, ...]:
        self.catalog_calls += 1
        return (_provider(authenticated=self.login_started),)

    def start_login(self, provider: str, auth_type: str) -> GatewayLoginSession:
        assert provider == "openai-codex"
        assert auth_type == "oauth"
        self.login_started = True
        return GatewayLoginSession(
            login_id="login-1",
            provider=provider,
            status="pending",
            events=(GatewayLoginEvent(type="progress", message="Waiting"),),
        )

    def login_status(self, login_id: str) -> GatewayLoginSession:
        assert login_id == "login-1"
        return GatewayLoginSession(
            login_id=login_id,
            provider="openai-codex",
            status="completed",
            events=(GatewayLoginEvent(type="progress", message="Waiting"),),
        )

    def respond_to_login(self, login_id: str, prompt_id: str, value: str) -> None:
        raise AssertionError((login_id, prompt_id, value))


def _provider(*, authenticated: bool) -> GatewayProvider:
    return GatewayProvider(
        id="openai-codex",
        name="OpenAI Codex",
        authenticated=authenticated,
        authModes=("oauth",),
        models=(
            GatewayCatalogModel(
                id="gpt-5.1-codex",
                name="GPT Codex",
                input=("text",),
                capabilities=("text", "thinking", "tool_calls"),
                contextWindow=128_000,
                maxOutputTokens=16_384,
            ),
        ),
    )


def test_help_lists_foundation_commands() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "version" in result.output
    assert "doctor" in result.output
    assert "campaign" in result.output
    assert "dungeon" in result.output
    assert "model" in result.output

    dungeon_help = runner.invoke(app, ["dungeon", "--help"])
    assert dungeon_help.exit_code == 0
    assert "prompt" in dungeon_help.output

    model_help = runner.invoke(app, ["model", "--help"])
    assert model_help.exit_code == 0
    assert "providers" in model_help.output
    assert "login" in model_help.output


def test_prompt_defaults_run_inline_login_and_choose_compatible_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = _LoginGateway()
    monkeypatch.setattr("dm_assistant.cli.main.time.sleep", lambda _: None)

    provider, model, effort = _resolve_dungeon_model_selection(
        gateway=gateway,  # type: ignore[arg-type]
        saved=None,
        provider_override=None,
        model_override=None,
        effort_override=None,
        allow_faux=False,
    )

    assert gateway.login_started is True
    assert provider.id == "openai-codex"
    assert model.id == "gpt-5.1-codex"
    assert effort.value == "standard"


def test_version_prints_package_version() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.output.strip() == __version__
