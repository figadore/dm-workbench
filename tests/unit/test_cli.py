"""CLI smoke tests."""

from typer.testing import CliRunner

from dm_assistant import __version__
from dm_assistant.cli.main import app

runner = CliRunner()


def test_help_lists_version_command() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "version" in result.output


def test_version_prints_package_version() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.output.strip() == __version__
