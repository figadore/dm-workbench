"""Typed environment configuration with secret-safe loading failures."""

import ipaddress
import os
import re
from enum import StrEnum
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import (
    AnyHttpUrl,
    Field,
    PostgresDsn,
    SecretStr,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

from dm_assistant.errors import ConfigurationError

_DEFAULT_ENV_FILE: str | None = (
    None if os.environ.get("DM_DISABLE_DOTENV") == "1" else ".env"
)
_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9._~-]{32,256}$")
_POSTGRES_DSN_ADAPTER = TypeAdapter(PostgresDsn)


class RuntimeEnvironment(StrEnum):
    """Supported application environments."""

    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    """Allowed application log thresholds."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ModelGatewayPolicy(StrEnum):
    """Whether the private model gateway may be used by the Workbench."""

    DISABLED = "disabled"
    OPTIONAL = "optional"
    REQUIRED = "required"


class EmbeddingRuntime(StrEnum):
    """Selected embedding execution boundary, separate from chat transport."""

    DISABLED = "disabled"
    LOCAL_CPU = "local_cpu"
    HOSTED = "hosted"


class EmbeddingProviderPolicy(StrEnum):
    """Allowed embedding-provider policy independent of model-gateway auth."""

    DISABLED = "disabled"
    LOCAL_ONLY = "local_only"
    HOSTED_ALLOWED = "hosted_allowed"


class DatabaseSettings(BaseSettings):
    """Minimal typed settings required by database and migration commands."""

    model_config = SettingsConfigDict(
        env_prefix="DM_",
        env_file=_DEFAULT_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        frozen=True,
    )

    database_url: SecretStr

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        raw_value = value.get_secret_value()
        _POSTGRES_DSN_ADAPTER.validate_python(raw_value)
        if not raw_value.lower().startswith("postgresql+psycopg://"):
            raise ValueError("database URL must select the psycopg 3 driver")
        return value


class Settings(DatabaseSettings):
    """Validated Workbench settings loaded from ``DM_*`` variables."""

    environment: RuntimeEnvironment = RuntimeEnvironment.DEVELOPMENT
    log_level: LogLevel = LogLevel.INFO
    source_roots: tuple[Path, ...] = Field(min_length=1)
    asset_root: Path
    scratch_root: Path
    api_token: SecretStr
    session_secret: SecretStr
    model_gateway_url: AnyHttpUrl | None = None
    model_gateway_internal_token: SecretStr | None = None
    model_gateway_policy: ModelGatewayPolicy = ModelGatewayPolicy.DISABLED
    embedding_runtime: EmbeddingRuntime = EmbeddingRuntime.DISABLED
    embedding_provider_policy: EmbeddingProviderPolicy = (
        EmbeddingProviderPolicy.DISABLED
    )
    embedding_api_key: SecretStr | None = None
    embedding_hosted_retention_approved: bool = False

    @field_validator("api_token", "session_secret", "model_gateway_internal_token")
    @classmethod
    def validate_authentication_secret(
        cls, value: SecretStr | None
    ) -> SecretStr | None:
        if value is None:
            return None
        if _TOKEN_PATTERN.fullmatch(value.get_secret_value()) is None:
            raise ValueError(
                "authentication secrets must be 32-256 URL-safe ASCII characters"
            )
        return value

    @field_validator("asset_root", "scratch_root")
    @classmethod
    def normalize_writable_root(cls, value: Path) -> Path:
        expanded = value.expanduser()
        if not expanded.is_absolute():
            raise ValueError("writable roots must be absolute")
        return expanded.resolve(strict=False)

    @field_validator("source_roots")
    @classmethod
    def normalize_source_roots(cls, value: tuple[Path, ...]) -> tuple[Path, ...]:
        expanded = tuple(path.expanduser() for path in value)
        if any(not path.is_absolute() for path in expanded):
            raise ValueError("source roots must be absolute")
        normalized = tuple(path.resolve(strict=False) for path in expanded)
        if len(set(normalized)) != len(normalized):
            raise ValueError("source roots must be distinct")
        return normalized

    @model_validator(mode="after")
    def validate_runtime_policies(self) -> "Settings":
        if self.api_token.get_secret_value() == self.session_secret.get_secret_value():
            raise ValueError("API token and session secret must be different")
        if self.asset_root == self.scratch_root:
            raise ValueError("asset and scratch roots must be distinct")
        if (
            self.model_gateway_policy is ModelGatewayPolicy.DISABLED
            and self.model_gateway_url is not None
        ):
            raise ValueError(
                "model gateway URL requires optional or required gateway policy"
            )
        if (
            self.model_gateway_policy is not ModelGatewayPolicy.DISABLED
            and self.model_gateway_url is None
        ):
            raise ValueError("enabled model gateway policy requires its private URL")
        if (
            self.model_gateway_policy is not ModelGatewayPolicy.DISABLED
            and self.model_gateway_internal_token is None
        ):
            raise ValueError("enabled model gateway policy requires its internal token")
        if (
            self.model_gateway_policy is ModelGatewayPolicy.DISABLED
            and self.model_gateway_internal_token is not None
        ):
            raise ValueError(
                "disabled model gateway policy cannot use an internal token"
            )
        if self.model_gateway_url is not None:
            parsed = urlsplit(str(self.model_gateway_url))
            if parsed.username is not None or parsed.password is not None:
                raise ValueError("model gateway URL cannot contain credentials")
            if parsed.hostname is None or not _is_private_hostname(parsed.hostname):
                raise ValueError("model gateway URL must use a private hostname")
        if self.embedding_runtime is EmbeddingRuntime.DISABLED:
            if self.embedding_provider_policy is not EmbeddingProviderPolicy.DISABLED:
                raise ValueError(
                    "disabled embedding runtime requires disabled provider policy"
                )
            if self.embedding_api_key is not None:
                raise ValueError("disabled embedding runtime cannot use an API key")
            if self.embedding_hosted_retention_approved:
                raise ValueError(
                    "disabled embedding runtime cannot approve hosted retention"
                )
        elif self.embedding_provider_policy is EmbeddingProviderPolicy.DISABLED:
            raise ValueError(
                "enabled embedding runtime requires an enabled provider policy"
            )
        elif (
            self.embedding_runtime is EmbeddingRuntime.HOSTED
            and self.embedding_provider_policy
            is not EmbeddingProviderPolicy.HOSTED_ALLOWED
        ):
            raise ValueError("hosted embedding runtime requires hosted_allowed policy")
        elif self.embedding_runtime is EmbeddingRuntime.HOSTED:
            if self.embedding_api_key is None:
                raise ValueError("hosted embedding runtime requires an API key")
            if not self.embedding_hosted_retention_approved:
                raise ValueError(
                    "hosted embedding runtime requires retention acknowledgement"
                )
        elif self.embedding_api_key is not None:
            raise ValueError("local embedding runtime cannot use a hosted API key")
        elif self.embedding_hosted_retention_approved:
            raise ValueError("local embedding runtime cannot approve hosted retention")
        return self

    def logging_secret_values(self) -> tuple[str, ...]:
        """Return secrets that the configured formatter must scrub from strings."""
        database_url = self.database_url.get_secret_value()
        parsed = urlsplit(database_url)
        values = [
            database_url,
            self.api_token.get_secret_value(),
            self.session_secret.get_secret_value(),
        ]
        if self.model_gateway_internal_token is not None:
            values.append(self.model_gateway_internal_token.get_secret_value())
        if self.embedding_api_key is not None:
            values.append(self.embedding_api_key.get_secret_value())
        if parsed.password:
            values.append(parsed.password)
        return tuple(values)


def _is_private_hostname(hostname: str) -> bool:
    normalized = hostname.rstrip(".").lower()
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        return "." not in normalized or normalized.endswith(
            (".internal", ".lan", ".local", ".localhost")
        )
    return address.is_private or address.is_loopback


def load_database_settings(*, env_file: str | Path | None = ".env") -> DatabaseSettings:
    """Load only database settings for Alembic and operational commands."""
    try:
        return DatabaseSettings(_env_file=env_file)  # type: ignore[call-arg]
    except ValidationError as error:
        raise _safe_configuration_error(error) from None


def load_settings(
    *,
    env_file: str | Path | None = _DEFAULT_ENV_FILE,
) -> Settings:
    """Load settings while replacing Pydantic's value-rich error with field names."""
    try:
        return Settings(_env_file=env_file)  # type: ignore[call-arg]
    except ValidationError as error:
        raise _safe_configuration_error(error) from None


def _safe_configuration_error(error: ValidationError) -> ConfigurationError:
    fields = tuple(
        ".".join(str(part) for part in item["loc"]) or "settings"
        for item in error.errors(include_url=False, include_input=False)
    )
    return ConfigurationError(fields)
