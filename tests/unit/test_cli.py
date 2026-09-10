"""CLI smoke tests."""

import json
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

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
    _build_dungeon_fixed_case_evidence,
    _default_login_provider,
    _default_model,
    _emit_debug_event,
    _emit_dungeon_failure_summary,
    _emit_output_limit_policy,
    _emit_provider_contract_diagnostic,
    _model_run_rejected_error,
    _prompt_execution_error,
    _provider_smoke_profile,
    _render_login_event,
    _resolve_dungeon_model_selection,
    app,
)
from dm_assistant.modules.modeling import ReasoningEffort
from dm_assistant.orchestration.modeling import ModelRunAbstained

runner = CliRunner()


def test_debug_event_is_json_on_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    _emit_debug_event("gateway_event", {"event": "text_delta", "data": {"delta": "x"}})

    assert capsys.readouterr().err == (
        '{"data":{"data":{"delta":"x"},"event":"text_delta"},"debug":"gateway_event"}\n'
    )


def test_output_limit_policy_discloses_application_only_enforcement(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _emit_output_limit_policy(("text", "tool_calls"))
    assert "application-only" in capsys.readouterr().err

    _emit_output_limit_policy(("text", "hard_output_token_limit", "tool_calls"))
    assert capsys.readouterr().err == ""


def test_contract_diagnostic_filters_transcript_bodies(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _emit_provider_contract_diagnostic(
        "harness_request", {"messages": [{"content": "private prompt"}]}
    )
    _emit_provider_contract_diagnostic(
        "gateway_event",
        {"event": "error", "data": {"message": "private provider body"}},
    )
    _emit_provider_contract_diagnostic(
        "gateway_event",
        {
            "event": "provider_contract_diagnostic",
            "data": {
                "http_status": 400,
                "mentions_max_output_tokens": True,
                "parameter_rejection": True,
                "max_output_tokens_rejection": True,
            },
        },
    )

    captured = capsys.readouterr().err
    assert captured == (
        '{"data":{"http_status":400,"max_output_tokens_rejection":true,'
        '"mentions_max_output_tokens":true,"parameter_rejection":true},'
        '"debug":"provider_contract_diagnostic"}\n'
    )
    assert "private" not in captured


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
    assert "fixed-case" in dungeon_help.output

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

    monkeypatch.setattr("dm_assistant.cli.main._run_dungeon_staged_canary", capture)
    result = runner.invoke(
        app,
        [
            "dungeon",
            "canary",
            "--provider",
            "openai-codex",
            "--model",
            "gpt-synthetic",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["provider"] == "openai-codex"
    assert captured["model"] == "gpt-synthetic"
    assert captured["effort"] is ReasoningEffort.FAST
    assert captured["diagnose_provider_contract"] is False
    assert "prompt" not in captured
    assert "seed" not in captured
    assert "acknowledge_advisory_output_cap" not in captured
    assert "Stop on the first failure" in result.output

    captured.clear()
    diagnostic = runner.invoke(
        app,
        [
            "dungeon",
            "canary",
            "--provider",
            "openai-codex",
            "--model",
            "gpt-synthetic",
            "--diagnose-provider-contract",
        ],
    )
    assert diagnostic.exit_code == 0, diagnostic.output
    assert captured["diagnose_provider_contract"] is True


def test_fixed_case_command_requires_exact_parent_and_runs_one_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def capture(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr("dm_assistant.cli.main._run_dungeon_fixed_case_task", capture)
    result = runner.invoke(
        app,
        [
            "dungeon",
            "fixed-case",
            "tier_a_case_01",
            "variant_01",
            "35ec4e9b-cbc5-416b-9ff7-3fade7865044",
            "e6902ff4-87e8-4966-8d83-25dd744ddc5d",
            "--provider",
            "openai-codex",
            "--model",
            "gpt-5.6-luna",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["case_id"] == "tier_a_case_01"
    assert captured["variant_id"] == "variant_01"
    assert str(captured["artifact_id"]) == "35ec4e9b-cbc5-416b-9ff7-3fade7865044"
    assert str(captured["parent_version_id"]) == (
        "e6902ff4-87e8-4966-8d83-25dd744ddc5d"
    )
    assert captured["provider"] == "openai-codex"
    assert captured["model"] == "gpt-5.6-luna"
    assert captured["effort"] is ReasoningEffort.FAST
    assert captured["resume_from_evaluation_run_id"] is None
    assert "execute one exact staged task" in result.output


def test_fixed_case_start_and_evidence_commands_pin_opaque_variant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started: dict[str, object] = {}
    evidence: dict[str, object] = {}

    monkeypatch.setattr(
        "dm_assistant.cli.main._run_dungeon_fixed_case_structure",
        lambda **kwargs: started.update(kwargs),
    )
    start = runner.invoke(
        app,
        [
            "dungeon",
            "fixed-case-start",
            "tier_a_case_02",
            "variant_01",
            "--provider",
            "openai-codex",
            "--model",
            "gpt-5.6-luna",
        ],
    )
    assert start.exit_code == 0, start.output
    assert started["case_id"] == "tier_a_case_02"
    assert started["variant_id"] == "variant_01"
    assert started["effort"] is ReasoningEffort.FAST

    monkeypatch.setattr(
        "dm_assistant.cli.main._build_dungeon_fixed_case_evidence",
        lambda **kwargs: evidence.update(kwargs),
    )
    result = runner.invoke(
        app,
        [
            "dungeon",
            "fixed-case-evidence",
            "tier_a_case_02",
            "variant_01",
            "35ec4e9b-cbc5-416b-9ff7-3fade7865044",
            "e6902ff4-87e8-4966-8d83-25dd744ddc5d",
            "--run",
            "11111111-1111-1111-1111-111111111111",
            "--run",
            "22222222-2222-2222-2222-222222222222",
            "--review-packet",
            "generated/blinded-case-02",
        ],
    )
    assert result.exit_code == 0, result.output
    assert evidence["case_id"] == "tier_a_case_02"
    assert evidence["variant_id"] == "variant_01"
    run_ids = evidence["evaluation_run_ids"]
    assert isinstance(run_ids, tuple)
    assert tuple(str(item) for item in run_ids) == (
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
    )
    assert evidence["review_packet_dir"] == Path("generated/blinded-case-02")


def test_fixed_case_evidence_loads_persisted_specification_as_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    campaign_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    artifact_id = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    version_id = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    persisted = {"purpose": "ruin", "room_ids": ["room-1"]}
    reviewer_input = object()
    evidence = SimpleNamespace(
        reviewer_input=reviewer_input,
        model_dump=lambda *, mode: {"case_id": "tier_a_case_01", "mode": mode},
    )
    runtime = SimpleNamespace(
        dungeon_fixed_case_evidence=SimpleNamespace(
            build=lambda command, manifest: evidence
        ),
        preparation=SimpleNamespace(
            get_version=lambda selected_campaign_id, selected_version_id: (
                SimpleNamespace(specification=persisted)
            )
        ),
    )

    @contextmanager
    def fake_runtime():
        yield runtime

    captured: dict[str, object] = {}

    class StrictSpecificationParser:
        @staticmethod
        def model_validate_json(value: str) -> object:
            captured["serialized_specification"] = value
            return "validated-specification"

    def fake_packet_writer(
        specification: object, selected_reviewer_input: object, output: Path
    ) -> tuple[SimpleNamespace]:
        captured["packet_arguments"] = (
            specification,
            selected_reviewer_input,
            output,
        )
        return (SimpleNamespace(name="review.json"),)

    monkeypatch.setattr("dm_assistant.cli.main.workbench_runtime", fake_runtime)
    monkeypatch.setattr(
        "dm_assistant.cli.main.DungeonStudioSpecification",
        StrictSpecificationParser,
    )
    monkeypatch.setattr(
        "dm_assistant.cli.main.write_dungeon_tier_a_blinded_review_packet",
        fake_packet_writer,
    )
    monkeypatch.setattr(
        "dm_assistant.cli.main.load_dungeon_tier_a_eval_manifest", lambda: object()
    )
    monkeypatch.setattr(
        "dm_assistant.cli.main._emit_document",
        lambda document: captured.update(emitted_document=document),
    )

    output = tmp_path / "review"
    _build_dungeon_fixed_case_evidence(
        case_id="tier_a_case_01",
        variant_id="variant_01",
        artifact_id=artifact_id,
        artifact_version_id=version_id,
        evaluation_run_ids=(
            UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"),
            UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"),
        ),
        campaign_id=campaign_id,
        review_packet_dir=output,
    )

    assert json.loads(str(captured["serialized_specification"])) == persisted
    assert captured["packet_arguments"] == (
        "validated-specification",
        reviewer_input,
        output,
    )
    emitted = captured["emitted_document"]
    assert isinstance(emitted, dict)
    assert emitted["review_packet"]["files"] == ["review.json"]


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


@pytest.mark.parametrize("provider_id", ["github-copilot", "openai-codex"])
def test_dungeon_default_uses_luna_baseline_not_largest_model(
    provider_id: str,
) -> None:
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
            id="gpt-5.6-luna",
            name="GPT-5.6 Luna",
            input=("text",),
            capabilities=("text", "thinking", "tool_calls"),
            contextWindow=272_000,
            maxOutputTokens=128_000,
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

    selected = _default_model(models, provider_id)

    assert selected is not None
    assert selected.id == "gpt-5.6-luna"


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
