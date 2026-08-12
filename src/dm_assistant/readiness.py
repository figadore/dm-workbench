"""Secret-safe application readiness shared by HTTP and CLI adapters."""

from collections.abc import Callable
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

EXPECTED_POSTGRES_MAJOR = "16"
EXPECTED_PGVECTOR_VERSION = "0.8.1"
EXPECTED_SCHEMA_REVISION = "0007_campaign_knowledge_entities"


class ComponentName(StrEnum):
    """Stable readiness component names."""

    CONFIGURATION = "configuration"
    DATABASE = "database"
    PGVECTOR = "pgvector"
    SCHEMA = "schema"


class ComponentState(StrEnum):
    """Safe component states without transport/driver details."""

    READY = "ready"
    NOT_READY = "not_ready"
    NOT_CHECKED = "not_checked"


class ReadinessCode(StrEnum):
    """Stable diagnostic categories suitable for unauthenticated health output."""

    CONFIGURATION_INVALID = "configuration_invalid"
    EXTENSION_MISSING = "extension_missing"
    REVISION_MISMATCH = "revision_mismatch"
    UNAVAILABLE = "unavailable"
    VERSION_MISMATCH = "version_mismatch"


class ComponentReadiness(BaseModel):
    """One safe component result."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    name: ComponentName
    state: ComponentState
    version: str | None = None
    expected_version: str | None = None
    code: ReadinessCode | None = None


class ReadinessReport(BaseModel):
    """Ordered aggregate readiness result."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    ready: bool
    components: tuple[ComponentReadiness, ...]

    @model_validator(mode="after")
    def require_complete_consistent_report(self) -> Self:
        expected_names = tuple(ComponentName)
        if tuple(item.name for item in self.components) != expected_names:
            raise ValueError("readiness components must be complete and ordered")
        all_ready = all(
            component.state is ComponentState.READY for component in self.components
        )
        if self.ready != all_ready:
            raise ValueError("aggregate readiness must match component states")
        return self

    def health_payload(self) -> dict[str, object]:
        """Return minimal public status without deployment versions."""
        return {
            "status": "ready" if self.ready else "not_ready",
            "checks": {
                component.name.value: component.state.value
                for component in self.components
            },
        }

    def doctor_payload(self) -> dict[str, object]:
        """Return safe local diagnostic versions and stable reason codes."""
        return {
            "status": "ready" if self.ready else "not_ready",
            "components": [
                component.model_dump(mode="json", exclude_none=True)
                for component in self.components
            ],
        }


ReadinessCheck = Callable[[], ReadinessReport]


def check_readiness(engine: Engine) -> ReadinessReport:
    """Check configuration, PostgreSQL, pgvector, and exact schema head."""
    configuration = ComponentReadiness(
        name=ComponentName.CONFIGURATION,
        state=ComponentState.READY,
    )
    try:
        with engine.connect() as connection:
            server_version = str(connection.scalar(text("SHOW server_version")))
            vector_version = connection.scalar(
                text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            )
            version_table = connection.scalar(
                text("SELECT to_regclass('public.alembic_version')")
            )
            schema_revision = (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                if version_table is not None
                else None
            )
    except SQLAlchemyError:
        return ReadinessReport(
            ready=False,
            components=(
                configuration,
                ComponentReadiness(
                    name=ComponentName.DATABASE,
                    state=ComponentState.NOT_READY,
                    expected_version=EXPECTED_POSTGRES_MAJOR,
                    code=ReadinessCode.UNAVAILABLE,
                ),
                _not_checked(ComponentName.PGVECTOR, EXPECTED_PGVECTOR_VERSION),
                _not_checked(ComponentName.SCHEMA, EXPECTED_SCHEMA_REVISION),
            ),
        )

    postgres_major = server_version.split(".", maxsplit=1)[0]
    database = _version_component(
        ComponentName.DATABASE,
        postgres_major,
        EXPECTED_POSTGRES_MAJOR,
        ReadinessCode.VERSION_MISMATCH,
    )
    pgvector = (
        _version_component(
            ComponentName.PGVECTOR,
            str(vector_version),
            EXPECTED_PGVECTOR_VERSION,
            ReadinessCode.VERSION_MISMATCH,
        )
        if vector_version is not None
        else ComponentReadiness(
            name=ComponentName.PGVECTOR,
            state=ComponentState.NOT_READY,
            expected_version=EXPECTED_PGVECTOR_VERSION,
            code=ReadinessCode.EXTENSION_MISSING,
        )
    )
    schema = (
        _version_component(
            ComponentName.SCHEMA,
            str(schema_revision),
            EXPECTED_SCHEMA_REVISION,
            ReadinessCode.REVISION_MISMATCH,
        )
        if schema_revision is not None
        else ComponentReadiness(
            name=ComponentName.SCHEMA,
            state=ComponentState.NOT_READY,
            expected_version=EXPECTED_SCHEMA_REVISION,
            code=ReadinessCode.REVISION_MISMATCH,
        )
    )
    components = (configuration, database, pgvector, schema)
    return ReadinessReport(
        ready=all(component.state is ComponentState.READY for component in components),
        components=components,
    )


def configuration_failure_report() -> ReadinessReport:
    """Build a report when full application settings cannot be loaded."""
    return ReadinessReport(
        ready=False,
        components=(
            ComponentReadiness(
                name=ComponentName.CONFIGURATION,
                state=ComponentState.NOT_READY,
                code=ReadinessCode.CONFIGURATION_INVALID,
            ),
            _not_checked(ComponentName.DATABASE, EXPECTED_POSTGRES_MAJOR),
            _not_checked(ComponentName.PGVECTOR, EXPECTED_PGVECTOR_VERSION),
            _not_checked(ComponentName.SCHEMA, EXPECTED_SCHEMA_REVISION),
        ),
    )


def _version_component(
    name: ComponentName,
    actual: str,
    expected: str,
    mismatch_code: ReadinessCode,
) -> ComponentReadiness:
    matches = actual == expected
    return ComponentReadiness(
        name=name,
        state=ComponentState.READY if matches else ComponentState.NOT_READY,
        version=actual,
        expected_version=expected,
        code=None if matches else mismatch_code,
    )


def _not_checked(name: ComponentName, expected: str) -> ComponentReadiness:
    return ComponentReadiness(
        name=name,
        state=ComponentState.NOT_CHECKED,
        expected_version=expected,
        code=ReadinessCode.UNAVAILABLE,
    )
