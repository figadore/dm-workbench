"""Synchronous SQLAlchemy engine and explicit transaction ownership."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from dm_assistant.config import DatabaseSettings
from dm_assistant.errors import DatabaseUnavailableError
from dm_assistant.observability import get_logger

logger = get_logger(__name__)
SessionFactory = sessionmaker[Session]


def build_engine(settings: DatabaseSettings) -> Engine:
    """Build a lazy synchronous psycopg engine without SQL/value logging."""
    return create_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
        hide_parameters=True,
        echo=False,
    )


def build_session_factory(engine: Engine) -> SessionFactory:
    """Bind sessions whose successful unit of work commits exactly once."""
    return sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        expire_on_commit=False,
    )


@contextmanager
def transactional_session(factory: SessionFactory) -> Iterator[Session]:
    """Commit success, roll back every failure, and always close the session."""
    session = factory()
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()


def check_database_connection(engine: Engine) -> None:
    """Run a safe connectivity probe and hide driver/DSN failure details."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        logger.error(
            "database connectivity check failed",
            extra={"event_data": {"exception_type": type(error).__name__}},
        )
        raise DatabaseUnavailableError() from None
