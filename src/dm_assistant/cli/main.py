"""DM Assistant command-line entry point."""

import typer

from dm_assistant import __version__

app = typer.Typer(
    name="dm",
    help="DM Assistant Workbench.",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def main() -> None:
    """Run DM Assistant commands."""


@app.command()
def version() -> None:
    """Show the installed DM Assistant version."""
    typer.echo(__version__)


if __name__ == "__main__":
    app()
