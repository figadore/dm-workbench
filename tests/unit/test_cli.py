"""CLI smoke tests."""

import pytest
from typer.testing import CliRunner

from dm_assistant import __version__
from dm_assistant.adapters.assets import AssetCorruptionError, AssetStorageError
from dm_assistant.adapters.model_gateway import (
    GatewayCatalogModel,
    GatewayLoginEvent,
    GatewayLoginSession,
    GatewayProvider,
)
from dm_assistant.cli.main import (
    _default_login_provider,
    _default_model,
    _emit_debug_event,
    _emit_dungeon_failure_summary,
    _model_run_rejected_error,
    _prompt_execution_error,
    _provider_smoke_profile,
    _render_login_event,
    _resolve_dungeon_model_selection,
    app,
)
from dm_assistant.modules.modeling import ReasoningEffort
from dm_assistant.orchestration.dungeons import DUNGEON_TIER_A_CANARY
from dm_assistant.orchestration.modeling import ModelRunAbstained

runner = CliRunner()


def test_debug_event_is_json_on_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    _emit_debug_event("gateway_event", {"event": "text_delta", "data": {"delta": "x"}})

    assert capsys.readouterr().err == (
        '{"data":{"data":{"delta":"x"},"event":"text_delta"},"debug":"gateway_event"}\n'
    )


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


def _provider(
    *,
    authenticated: bool,
    provider_id: str = "openai-codex",
    name: str = "OpenAI Codex",
) -> GatewayProvider:
    return GatewayProvider(
        id=provider_id,
        name=name,
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
    assert "canary" in dungeon_help.output

    model_help = runner.invoke(app, ["model", "--help"])
    assert model_help.exit_code == 0
    assert "providers" in model_help.output
    assert "login" in model_help.output


def test_canary_command_pins_exact_prompt_seed_and_explicit_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def capture(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr("dm_assistant.cli.main.dungeon_prompt", capture)
    result = runner.invoke(
        app,
        [
            "dungeon",
            "canary",
            "--provider",
            "openai-codex",
            "--model",
            "gpt-synthetic",
            "--acknowledge-advisory-output-cap",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["prompt"] == DUNGEON_TIER_A_CANARY.prompt
    assert captured["seed"] == DUNGEON_TIER_A_CANARY.seed
    assert captured["provider"] == "openai-codex"
    assert captured["model"] == "gpt-synthetic"
    assert captured["effort"] is ReasoningEffort.FAST
    assert captured["acknowledge_advisory_output_cap"] is True
    assert "Stop on the first failure" in result.output


def test_provider_smoke_profile_is_short_lived_and_tool_free() -> None:
    profile = _provider_smoke_profile(
        _provider(authenticated=True),
        _provider(authenticated=True).models[0],
        ReasoningEffort.STANDARD,
    )

    assert profile.allowed_tools == ()
    assert profile.turn_budget == 1
    assert profile.tool_budget == 0
    assert profile.time_budget_seconds == 30
    assert profile.token_budget == 256


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


def test_container_login_automatically_selects_device_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses: list[tuple[str, str, str]] = []
    gateway = _LoginGateway()
    monkeypatch.setattr(
        "dm_assistant.cli.main.typer.prompt",
        lambda *args, **kwargs: pytest.fail("device-code selection must not prompt"),
    )
    gateway.respond_to_login = lambda login_id, prompt_id, value: responses.append(
        (login_id, prompt_id, value)
    )

    _render_login_event(
        gateway,  # type: ignore[arg-type]
        "login-1",
        GatewayLoginEvent(
            type="prompt",
            prompt_id="prompt-1",
            prompt_type="select",
            message="Select login method",
            options=(
                {"id": "browser", "label": "Browser login"},
                {"id": "device_code", "label": "Device code login"},
            ),
        ),
    )

    assert responses == [("login-1", "prompt-1", "device_code")]


def test_github_default_uses_pinned_task_baseline_not_largest_model() -> None:
    models = (
        GatewayCatalogModel(
            id="kimi-k3",
            name="Kimi K3",
            input=("text",),
            capabilities=("text", "thinking", "tool_calls"),
            contextWindow=1_048_576,
            maxOutputTokens=131_072,
        ),
        GatewayCatalogModel(
            id="gpt-4.1",
            name="GPT-4.1",
            input=("text",),
            capabilities=("text", "tool_calls"),
            contextWindow=128_000,
            maxOutputTokens=16_384,
        ),
    )

    selected = _default_model(models, "github-copilot")

    assert selected is not None
    assert selected.id == "gpt-4.1"


def test_github_login_uses_github_com_without_reprompting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses: list[tuple[str, str, str]] = []
    gateway = _LoginGateway()
    monkeypatch.setattr(
        "dm_assistant.cli.main.typer.prompt",
        lambda *args, **kwargs: pytest.fail("github.com default must not prompt"),
    )
    gateway.respond_to_login = lambda login_id, prompt_id, value: responses.append(
        (login_id, prompt_id, value)
    )

    _render_login_event(
        gateway,  # type: ignore[arg-type]
        "login-1",
        GatewayLoginEvent(
            type="prompt",
            prompt_id="enterprise-domain",
            prompt_type="text",
            message="GitHub Enterprise URL/domain (blank for github.com)",
        ),
    )

    assert responses == [("login-1", "enterprise-domain", "")]


def test_first_login_offers_subscription_provider_choice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    choices: list[str] = []

    def choose(*args: object, **kwargs: object) -> str:
        del args, kwargs
        choices.append("asked")
        return "github-copilot"

    monkeypatch.setattr("dm_assistant.cli.main.typer.prompt", choose)

    selected = _default_login_provider(
        (
            _provider(authenticated=False),
            _provider(
                authenticated=False,
                provider_id="github-copilot",
                name="GitHub Copilot",
            ),
        )
    )

    assert selected is not None
    assert selected.id == "github-copilot"
    assert choices == ["asked"]


@pytest.mark.parametrize(
    ("reason", "expected"),
    (
        (
            "model output failed schema validation within the repair budget",
            "did not match the required schema after a repair attempt",
        ),
        (
            "dungeon_prompt_repair_usage_unavailable",
            "gateway did not report token usage, so the safe automatic repair could not run",
        ),
        (
            "dungeon_prompt_rejected_after_repair",
            "This was not a model abstention.",
        ),
        (
            "dungeon_prompt_token_budget_exhausted",
            "exceeded the dungeon run token ceiling reported by the gateway",
        ),
        (
            "a provider supplied response that must not be shown",
            "The selected model explicitly abstained instead of providing a usable dungeon intent.",
        ),
        (
            "tool budget exhausted before completion",
            "requested more deterministic dungeon tool work",
        ),
    ),
)
def test_prompt_failure_is_actionable_without_exposing_model_response(
    reason: str,
    expected: str,
) -> None:
    error = _model_run_rejected_error(ModelRunAbstained(reason))

    assert error.code.value == "model_run_rejected"
    assert expected in error.public_message
    assert "provider supplied" not in error.public_message


@pytest.mark.parametrize(
    ("error", "code", "expected"),
    (
        (
            AssetCorruptionError("hidden storage detail"),
            "asset_storage_unavailable",
            "could not be verified",
        ),
        (
            AssetStorageError("hidden storage detail"),
            "asset_storage_unavailable",
            "could not be persisted safely",
        ),
        (
            ValueError("hidden typed detail"),
            "dungeon_execution_failed",
            "rejected an internal typed input",
        ),
        (
            RuntimeError("hidden implementation detail"),
            "dungeon_execution_failed",
            "stopped during deterministic generation or persistence",
        ),
    ),
)
def test_prompt_execution_failures_are_classified_without_detail_leakage(
    error: Exception,
    code: str,
    expected: str,
) -> None:
    public = _prompt_execution_error(error)

    assert public.code.value == code
    assert expected in public.public_message
    assert "hidden" not in public.public_message


def test_dungeon_failure_summary_identifies_the_exact_deterministic_failure(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _emit_dungeon_failure_summary(
        (
            {
                "code": "geometry.corridor_blocked",
                "message": "Corridor 'conn-vestibule-scriptorium' crosses unrelated room geometry.",
                "affected_ids": [
                    "conn-vestibule-scriptorium",
                    "room-reliquary-approach",
                ],
                "repair_hint": "Reroute around unrelated rooms/blockers.",
            },
        )
    )

    output = capsys.readouterr().err
    assert "Dungeon generation failed deterministic validation" in output
    assert "[geometry.corridor_blocked]" in output
    assert "conn-vestibule-scriptorium, room-reliquary-approach" in output
    assert "Reroute around unrelated rooms/blockers." in output


def test_version_prints_package_version() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.output.strip() == __version__
