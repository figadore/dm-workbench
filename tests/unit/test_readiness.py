"""Secret-safe readiness aggregation tests with injected database probes."""

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError
from sqlalchemy import Engine
from sqlalchemy.exc import OperationalError

from dm_assistant.readiness import (
    EXPECTED_SCHEMA_REVISION,
    ComponentName,
    ComponentState,
    ReadinessCode,
    ReadinessReport,
    check_readiness,
    configuration_failure_report,
)


def engine_with_scalars(*values: object) -> Engine:
    connection = MagicMock()
    connection.scalar.side_effect = values
    context = MagicMock()
    context.__enter__.return_value = connection
    engine = MagicMock(spec=Engine)
    engine.connect.return_value = context
    return engine


def test_ready_report_requires_exact_database_extension_and_schema_versions() -> None:
    report = check_readiness(
        engine_with_scalars(
            "16.11 (Debian synthetic)",
            "0.8.1",
            "alembic_version",
            EXPECTED_SCHEMA_REVISION,
        )
    )

    assert report.ready is True
    assert [item.name for item in report.components] == [
        ComponentName.CONFIGURATION,
        ComponentName.DATABASE,
        ComponentName.PGVECTOR,
        ComponentName.SCHEMA,
    ]
    assert all(item.state is ComponentState.READY for item in report.components)
    assert report.health_payload() == {
        "status": "ready",
        "checks": {
            "configuration": "ready",
            "database": "ready",
            "pgvector": "ready",
            "schema": "ready",
        },
    }
    assert "16" not in str(report.health_payload())
    assert report.doctor_payload()["components"][1]["version"] == "16"


def test_version_and_revision_mismatches_are_distinguishable() -> None:
    report = check_readiness(
        engine_with_scalars("15.9", "0.7.4", "alembic_version", "old_revision")
    )

    assert report.ready is False
    assert [item.code for item in report.components] == [
        None,
        ReadinessCode.VERSION_MISMATCH,
        ReadinessCode.VERSION_MISMATCH,
        ReadinessCode.REVISION_MISMATCH,
    ]
    assert all(item.state is ComponentState.NOT_READY for item in report.components[1:])


def test_missing_vector_and_schema_are_reported_without_query_errors() -> None:
    report = check_readiness(engine_with_scalars("16.11", None, None))

    assert report.ready is False
    assert report.components[2].code is ReadinessCode.EXTENSION_MISSING
    assert report.components[3].code is ReadinessCode.REVISION_MISMATCH


def test_connection_failure_marks_dependencies_not_checked_without_details() -> None:
    engine = MagicMock(spec=Engine)
    engine.connect.side_effect = OperationalError(
        "connect",
        {},
        RuntimeError("host secret-password.example.invalid"),
    )

    report = check_readiness(engine)
    document = str(report.doctor_payload())

    assert report.ready is False
    assert report.components[1].code is ReadinessCode.UNAVAILABLE
    assert all(
        item.state is ComponentState.NOT_CHECKED for item in report.components[2:]
    )
    assert "secret-password" not in document
    assert "example.invalid" not in document


def test_report_rejects_incomplete_or_inconsistent_aggregate() -> None:
    with pytest.raises(ValidationError, match="complete and ordered"):
        ReadinessReport(ready=True, components=())


def test_configuration_failure_does_not_attempt_other_checks() -> None:
    report = configuration_failure_report()

    assert report.ready is False
    assert report.components[0].code is ReadinessCode.CONFIGURATION_INVALID
    assert all(
        item.state is ComponentState.NOT_CHECKED for item in report.components[1:]
    )
