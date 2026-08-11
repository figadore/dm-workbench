"""FastAPI application factory."""

from fastapi import FastAPI

from dm_assistant import __version__


def create_app() -> FastAPI:
    """Create the DM Assistant HTTP application."""
    return FastAPI(title="DM Assistant", version=__version__)
