"""CLI smoke tests."""

from typer.testing import CliRunner

from dm_assistant import __version__
from dm_assistant.cli.main import app

runner = CliRunner()


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


def test_version_prints_package_version() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.output.strip() == __version__
