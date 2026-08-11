"""Shared doctor orchestration, safe rendering, and CLI exit tests."""

import json
from unittest.mock import MagicMock

import pytest
from sqlalchemy import Engine
from typer.testing import CliRunner

import dm_assistant.cli.main as cli_module
from dm_assistant.cli.main import app
from dm_assistant.config import Settings
from dm_assistant.doctor import (
    collect_doctor_report,
    render_doctor_human,
    render_doctor_json,
)
from dm_assistant.errors import ConfigurationError
from dm_assistant.readiness import (
    EXPECTED_SCHEMA_REVISION,
    ComponentName,
    ComponentReadiness,
    ComponentState,
    ReadinessCode,
    ReadinessReport,
    configuration_failure_report,
)

runner = CliRunner()


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


def test_collect_doctor_report_uses_probe_and_disposes_engine(
    test_settings: Settings,
) -> None:
    engine = MagicMock(spec=Engine)
    expected = ready_report()

    def probe(received: Engine) -> ReadinessReport:
        assert received is engine
        return expected

    report = collect_doctor_report(
        settings_loader=lambda: test_settings,
        engine_builder=lambda _: engine,
        readiness_probe=probe,
    )

    assert report == expected
    engine.dispose.assert_called_once_with()


def test_configuration_failure_report_never_builds_engine() -> None:
    def fail_settings() -> Settings:
        raise ConfigurationError(("api_token", "database_url"))

    def forbidden_engine(_: Settings) -> Engine:
        raise AssertionError("engine must not be built")

    report = collect_doctor_report(
        settings_loader=fail_settings,
        engine_builder=forbidden_engine,
    )

    assert report == configuration_failure_report()
    assert "api_token" not in render_doctor_human(report)
    assert "database_url" not in render_doctor_json(report)


def test_human_and_json_output_contain_only_safe_states_and_versions() -> None:
    report = ready_report()

    human = render_doctor_human(report)
    json_output = render_doctor_json(report)

    assert human.splitlines()[-1] == "overall: ready"
    assert "database: ready (version=16, expected=16)" in human
    assert "postgresql://" not in human
    assert json.loads(json_output) == report.doctor_payload()
    assert "password" not in json_output


def test_doctor_cli_ready_human_and_json_modes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli_module, "collect_doctor_report", ready_report)

    human = runner.invoke(app, ["doctor"])
    machine = runner.invoke(app, ["doctor", "--json"])

    assert human.exit_code == 0
    assert "overall: ready" in human.output
    assert machine.exit_code == 0
    assert json.loads(machine.output)["status"] == "ready"


def test_doctor_cli_returns_nonzero_for_safe_not_ready_report(
    monkeypatch: pytest.MonkeyPatch,
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
    monkeypatch.setattr(cli_module, "collect_doctor_report", lambda: unavailable)

    result = runner.invoke(app, ["doctor", "--json"])

    assert result.exit_code == 1
    assert json.loads(result.output)["components"][1] == {
        "name": "database",
        "state": "not_ready",
        "expected_version": "16",
        "code": "unavailable",
    }
    assert "secret" not in result.output
