"""PostgreSQL extension, migration, constraint, and transaction gates."""

import uuid

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, inspect, select, text
from sqlalchemy.exc import IntegrityError

from dm_assistant.db import (
    Base,
    Campaign,
    build_session_factory,
    check_database_connection,
    transactional_session,
)
from dm_assistant.readiness import (
    EXPECTED_SCHEMA_REVISION,
    ComponentState,
    check_readiness,
)

pytestmark = pytest.mark.integration


def test_foundation_revision_extension_and_schema_are_current(
    db_engine: Engine,
    alembic_config: Config,
) -> None:
    assert ScriptDirectory.from_config(alembic_config).get_current_head() == (
        EXPECTED_SCHEMA_REVISION
    )
    check_database_connection(db_engine)
    with db_engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            )
            == "0.8.1"
        )
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            EXPECTED_SCHEMA_REVISION
        )
        context = MigrationContext.configure(connection)
        assert compare_metadata(context, Base.metadata) == []

    inspector = inspect(db_engine)
    assert set(inspector.get_table_names()) >= {"alembic_version", "campaign"}
    assert {item["name"] for item in inspector.get_check_constraints("campaign")} == {
        "ck_campaign_name_not_blank"
    }
    assert {item["name"] for item in inspector.get_unique_constraints("campaign")} == {
        "uq_campaign_name"
    }


def test_application_readiness_uses_live_versions_without_public_leakage(
    db_engine: Engine,
) -> None:
    report = check_readiness(db_engine)

    assert report.ready is True
    assert all(item.state is ComponentState.READY for item in report.components)
    assert report.doctor_payload()["components"][2]["version"] == "0.8.1"
    assert "version" not in str(report.health_payload())


def test_campaign_constraints_reject_blank_and_duplicate_names(
    db_engine: Engine,
) -> None:
    with pytest.raises(IntegrityError):
        with db_engine.begin() as connection:
            connection.execute(
                Campaign.__table__.insert().values(id=uuid.uuid4(), name="   ")
            )

    campaign_id = uuid.uuid4()
    with db_engine.begin() as connection:
        connection.execute(
            Campaign.__table__.insert().values(
                id=campaign_id,
                name="Synthetic Test Campaign",
            )
        )
    with pytest.raises(IntegrityError):
        with db_engine.begin() as connection:
            connection.execute(
                Campaign.__table__.insert().values(
                    id=uuid.uuid4(),
                    name="Synthetic Test Campaign",
                )
            )


def test_transaction_boundary_commits_and_rolls_back(db_engine: Engine) -> None:
    factory = build_session_factory(db_engine)
    committed_id = uuid.uuid4()
    with transactional_session(factory) as session:
        session.add(Campaign(id=committed_id, name="Committed Synthetic Campaign"))

    with transactional_session(factory) as session:
        assert session.scalar(select(Campaign.id)) == committed_id

    with pytest.raises(RuntimeError, match="abort synthetic transaction"):
        with transactional_session(factory) as session:
            session.add(Campaign(name="Rolled Back Synthetic Campaign"))
            session.flush()
            raise RuntimeError("abort synthetic transaction")

    with transactional_session(factory) as session:
        names = set(session.scalars(select(Campaign.name)))
    assert names == {"Committed Synthetic Campaign"}


def test_migration_downgrade_upgrade_round_trip(
    db_engine: Engine,
    alembic_config: Config,
) -> None:
    command.downgrade(alembic_config, "base")
    assert "campaign" not in inspect(db_engine).get_table_names()
    with db_engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT count(*) FROM pg_extension WHERE extname = 'vector'")
            )
            == 0
        )

    command.upgrade(alembic_config, "head")
    assert "campaign" in inspect(db_engine).get_table_names()
    with db_engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT count(*) FROM pg_extension WHERE extname = 'vector'")
            )
            == 1
        )
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            EXPECTED_SCHEMA_REVISION
        )
