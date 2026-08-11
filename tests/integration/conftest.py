"""Safety-gated fixtures for the disposable PostgreSQL integration database."""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def postgres_url() -> str:
    value = os.environ.get("DM_TEST_DATABASE_URL")
    if value is None:
        pytest.skip("DM_TEST_DATABASE_URL is required for PostgreSQL integration tests")
    try:
        database = make_url(value).database
    except Exception:
        pytest.fail("DM_TEST_DATABASE_URL is not a valid SQLAlchemy URL", pytrace=False)
    if database is None or not database.endswith("_test"):
        pytest.fail(
            "refusing destructive integration migrations outside a *_test database",
            pytrace=False,
        )
    return value


@pytest.fixture(scope="session")
def alembic_config(postgres_url: str) -> Iterator[Config]:
    previous = os.environ.get("DM_DATABASE_URL")
    os.environ["DM_DATABASE_URL"] = postgres_url
    config = Config(ROOT / "alembic.ini")
    try:
        command.downgrade(config, "base")
        command.upgrade(config, "head")
        yield config
    finally:
        command.downgrade(config, "base")
        if previous is None:
            os.environ.pop("DM_DATABASE_URL", None)
        else:
            os.environ["DM_DATABASE_URL"] = previous


@pytest.fixture(scope="session")
def db_engine(postgres_url: str, alembic_config: Config) -> Iterator[Engine]:
    del alembic_config
    engine = create_engine(postgres_url, pool_pre_ping=True, hide_parameters=True)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(autouse=True)
def clean_campaigns(db_engine: Engine) -> Iterator[None]:
    _truncate_campaign_if_present(db_engine)
    yield
    _truncate_campaign_if_present(db_engine)


def _truncate_campaign_if_present(engine: Engine) -> None:
    with engine.begin() as connection:
        campaign_exists = connection.scalar(
            text("SELECT to_regclass('public.campaign')")
        )
        asset_exists = connection.scalar(
            text("SELECT to_regclass('public.generated_asset')")
        )
        document_exists = connection.scalar(
            text("SELECT to_regclass('public.document')")
        )
        ingestion_run_exists = connection.scalar(
            text("SELECT to_regclass('public.ingestion_run')")
        )
        tables = []
        if campaign_exists is not None:
            tables.append("campaign")
        if asset_exists is not None:
            tables.append("generated_asset")
        if document_exists is not None:
            tables.append("document")
        if ingestion_run_exists is not None:
            tables.append("ingestion_run")
        if tables:
            connection.execute(text(f"TRUNCATE TABLE {', '.join(tables)} CASCADE"))
