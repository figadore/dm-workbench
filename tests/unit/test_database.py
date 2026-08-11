"""Database boundary unit tests that require no running PostgreSQL."""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from dm_assistant.config import DatabaseSettings
from dm_assistant.db import (
    build_engine,
    build_session_factory,
    check_database_connection,
    transactional_session,
)
from dm_assistant.errors import DatabaseUnavailableError


def test_engine_hides_parameters_and_password() -> None:
    password = "database-password-not-for-logs"
    settings = DatabaseSettings(
        database_url=f"postgresql+psycopg://user:{password}@db/app"
    )

    engine = build_engine(settings)
    try:
        assert engine.hide_parameters is True
        assert password not in str(engine.url)
        assert password not in repr(engine.url)
        assert build_session_factory(engine).kw == {
            "bind": engine,
            "autoflush": False,
            "expire_on_commit": False,
        }
    finally:
        engine.dispose()


def sqlite_factory() -> tuple[Engine, sessionmaker[Session]]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE item (value TEXT NOT NULL)"))
    return engine, build_session_factory(engine)


def values(engine: Engine) -> list[str]:
    with engine.connect() as connection:
        return list(connection.scalars(text("SELECT value FROM item ORDER BY value")))


def test_transactional_session_commits_success_and_closes() -> None:
    engine, factory = sqlite_factory()
    captured: Session | None = None
    try:
        with transactional_session(factory) as session:
            captured = session
            session.execute(text("INSERT INTO item (value) VALUES ('committed')"))

        assert values(engine) == ["committed"]
        assert captured is not None
        assert captured.in_transaction() is False
    finally:
        engine.dispose()


def test_transactional_session_rolls_back_every_failure() -> None:
    engine, factory = sqlite_factory()
    try:
        with pytest.raises(RuntimeError, match="synthetic failure"):
            with transactional_session(factory) as session:
                session.execute(text("INSERT INTO item (value) VALUES ('rolled-back')"))
                raise RuntimeError("synthetic failure")

        assert values(engine) == []
    finally:
        engine.dispose()


def test_connection_probe_maps_driver_error_to_safe_domain_error() -> None:
    engine = create_engine(
        "postgresql+psycopg://user:secret-password@127.0.0.1:1/missing",
        connect_args={"connect_timeout": 1},
        hide_parameters=True,
    )
    try:
        with pytest.raises(DatabaseUnavailableError) as captured:
            check_database_connection(engine)
    finally:
        engine.dispose()

    assert str(captured.value) == "Database is unavailable."
    assert "secret-password" not in str(captured.value)
