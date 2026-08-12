"""Typed settings precedence, policy, and secret-safe failure tests."""

from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from dm_assistant.config import (
    EmbeddingProviderPolicy,
    EmbeddingRuntime,
    LogLevel,
    ModelGatewayPolicy,
    RuntimeEnvironment,
    Settings,
    load_database_settings,
    load_settings,
)
from dm_assistant.errors import ConfigurationError

_BASE_TOKEN = "config-test-token-00000000000000000"
_OVERRIDE_TOKEN = "override-test-token-000000000000000"
_SESSION_SECRET = "config-session-secret-00000000000000"
_MODEL_GATEWAY_TOKEN = "config-gateway-token-00000000000000"


def write_env(path: Path, source_root: Path) -> None:
    path.write_text(
        "\n".join(
            (
                "DM_ENVIRONMENT=test",
                "DM_DATABASE_URL=postgresql+psycopg://user:db-secret@db/app",
                "DM_LOG_LEVEL=INFO",
                f'DM_SOURCE_ROOTS=["{source_root}"]',
                f"DM_ASSET_ROOT={source_root.parent / 'assets'}",
                f"DM_SCRATCH_ROOT={source_root.parent / 'scratch'}",
                f"DM_API_TOKEN={_BASE_TOKEN}",
                f"DM_SESSION_SECRET={_SESSION_SECRET}",
                "DM_MODEL_GATEWAY_POLICY=optional",
                "DM_MODEL_GATEWAY_URL=http://model-gateway:3000",
                f"DM_MODEL_GATEWAY_INTERNAL_TOKEN={_MODEL_GATEWAY_TOKEN}",
                "DM_EMBEDDING_RUNTIME=local_cpu",
                "DM_EMBEDDING_PROVIDER_POLICY=local_only",
            )
        ),
        encoding="utf-8",
    )


def test_environment_overrides_dotenv_and_values_are_typed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "campaign"
    env_file = tmp_path / ".env"
    write_env(env_file, source_root)
    for name in (
        "DM_ENVIRONMENT",
        "DM_DATABASE_URL",
        "DM_SOURCE_ROOTS",
        "DM_SESSION_SECRET",
        "DM_ASSET_ROOT",
        "DM_SCRATCH_ROOT",
        "DM_MODEL_GATEWAY_POLICY",
        "DM_MODEL_GATEWAY_URL",
        "DM_MODEL_GATEWAY_INTERNAL_TOKEN",
        "DM_EMBEDDING_RUNTIME",
        "DM_EMBEDDING_PROVIDER_POLICY",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DM_LOG_LEVEL", "ERROR")
    monkeypatch.setenv("DM_API_TOKEN", _OVERRIDE_TOKEN)

    settings = load_settings(env_file=env_file)

    assert settings.environment is RuntimeEnvironment.TEST
    assert settings.log_level is LogLevel.ERROR
    assert settings.source_roots == (source_root.resolve(),)
    assert settings.asset_root == (tmp_path / "assets").resolve()
    assert settings.scratch_root == (tmp_path / "scratch").resolve()
    assert settings.api_token.get_secret_value() == _OVERRIDE_TOKEN
    assert settings.model_gateway_policy is ModelGatewayPolicy.OPTIONAL
    assert str(settings.model_gateway_url) == "http://model-gateway:3000/"
    assert (
        settings.model_gateway_internal_token is not None
        and settings.model_gateway_internal_token.get_secret_value()
        == _MODEL_GATEWAY_TOKEN
    )
    assert settings.embedding_runtime is EmbeddingRuntime.LOCAL_CPU
    assert settings.embedding_provider_policy is EmbeddingProviderPolicy.LOCAL_ONLY
    representation = repr(settings)
    assert _OVERRIDE_TOKEN not in representation
    assert "db-secret" not in representation


def test_database_only_loader_does_not_require_application_secrets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_file = tmp_path / ".env.database"
    database_url = "postgresql+psycopg://migration:secret@db/app"
    env_file.write_text(f"DM_DATABASE_URL={database_url}\n", encoding="utf-8")
    monkeypatch.delenv("DM_API_TOKEN", raising=False)
    monkeypatch.delenv("DM_SOURCE_ROOTS", raising=False)
    monkeypatch.delenv("DM_DATABASE_URL", raising=False)

    settings = load_database_settings(env_file=env_file)

    assert settings.database_url.get_secret_value() == database_url


def test_missing_configuration_reports_only_field_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "DM_DATABASE_URL",
        "DM_SOURCE_ROOTS",
        "DM_ASSET_ROOT",
        "DM_SCRATCH_ROOT",
        "DM_API_TOKEN",
        "DM_SESSION_SECRET",
        "DM_MODEL_GATEWAY_URL",
        "DM_MODEL_GATEWAY_POLICY",
        "DM_EMBEDDING_RUNTIME",
        "DM_EMBEDDING_PROVIDER_POLICY",
    ):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ConfigurationError) as captured:
        load_settings(env_file=None)

    message = str(captured.value)
    assert message == (
        "Invalid or missing configuration: api_token, asset_root, database_url, "
        "scratch_root, session_secret, source_roots."
    )
    assert "input_value" not in message


def test_invalid_secret_values_are_not_echoed_by_safe_loader(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    leaked_token = "short leaked token"
    leaked_database = "not-postgres://user:leaked-password@example.invalid/db"
    monkeypatch.setenv("DM_API_TOKEN", leaked_token)
    monkeypatch.setenv("DM_SESSION_SECRET", _SESSION_SECRET)
    monkeypatch.setenv("DM_DATABASE_URL", leaked_database)
    monkeypatch.setenv("DM_SOURCE_ROOTS", f'["{tmp_path}"]')
    monkeypatch.setenv("DM_ASSET_ROOT", str(tmp_path / "assets"))
    monkeypatch.setenv("DM_SCRATCH_ROOT", str(tmp_path / "scratch"))

    with pytest.raises(ConfigurationError) as captured:
        load_settings(env_file=None)

    message = str(captured.value)
    assert "api_token" in message
    assert "database_url" in message
    assert leaked_token not in message
    assert leaked_database not in message
    assert "leaked-password" not in message


def test_settings_reject_reusing_api_token_as_session_secret(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="must be different"):
        Settings(
            database_url="postgresql+psycopg://user:password@db/app",
            source_roots=(tmp_path,),
            asset_root=tmp_path / "assets",
            scratch_root=tmp_path / "scratch",
            api_token=_BASE_TOKEN,
            session_secret=_BASE_TOKEN,
        )


def test_settings_reject_relative_or_identical_writable_roots(tmp_path: Path) -> None:
    values = {
        "database_url": "postgresql+psycopg://user:password@db/app",
        "source_roots": (tmp_path,),
        "api_token": _BASE_TOKEN,
        "session_secret": _SESSION_SECRET,
    }
    with pytest.raises(ValidationError, match="writable roots must be absolute"):
        Settings(
            asset_root=Path("relative-assets"),
            scratch_root=tmp_path / "scratch",
            **values,
        )
    with pytest.raises(ValidationError, match="must be distinct"):
        Settings(asset_root=tmp_path, scratch_root=tmp_path, **values)


def test_settings_reject_relative_or_duplicate_source_roots(tmp_path: Path) -> None:
    values = {
        "database_url": "postgresql+psycopg://user:password@db/app",
        "asset_root": tmp_path / "assets",
        "scratch_root": tmp_path / "scratch",
        "api_token": _BASE_TOKEN,
        "session_secret": _SESSION_SECRET,
    }
    with pytest.raises(ValidationError, match="absolute"):
        Settings(source_roots=(Path("relative"),), **values)
    with pytest.raises(ValidationError, match="distinct"):
        Settings(source_roots=(tmp_path, tmp_path / "."), **values)


@pytest.mark.parametrize(
    ("updates", "message"),
    (
        (
            {"model_gateway_policy": ModelGatewayPolicy.REQUIRED},
            "requires its private URL",
        ),
        (
            {
                "embedding_runtime": EmbeddingRuntime.HOSTED,
                "embedding_provider_policy": EmbeddingProviderPolicy.LOCAL_ONLY,
            },
            "hosted_allowed",
        ),
    ),
)
def test_settings_reject_inconsistent_runtime_policies(
    tmp_path: Path,
    updates: dict[str, object],
    message: str,
) -> None:
    values: dict[str, object] = {
        "database_url": "postgresql+psycopg://user:password@db/app",
        "source_roots": (tmp_path,),
        "asset_root": tmp_path / "assets",
        "scratch_root": tmp_path / "scratch",
        "api_token": _BASE_TOKEN,
        "session_secret": _SESSION_SECRET,
        **updates,
    }

    with pytest.raises(ValidationError, match=message):
        Settings(**values)


@pytest.mark.parametrize(
    ("updates", "message"),
    (
        (
            {
                "embedding_runtime": EmbeddingRuntime.HOSTED,
                "embedding_provider_policy": EmbeddingProviderPolicy.HOSTED_ALLOWED,
            },
            "requires an API key",
        ),
        (
            {
                "embedding_runtime": EmbeddingRuntime.HOSTED,
                "embedding_provider_policy": EmbeddingProviderPolicy.HOSTED_ALLOWED,
                "embedding_api_key": "hosted-embedding-secret",
            },
            "retention acknowledgement",
        ),
    ),
)
def test_hosted_embeddings_require_separate_credential_and_retention_acknowledgement(
    tmp_path: Path,
    updates: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        Settings(
            database_url="postgresql+psycopg://user:password@db/app",
            source_roots=(tmp_path,),
            asset_root=tmp_path / "assets",
            scratch_root=tmp_path / "scratch",
            api_token=_BASE_TOKEN,
            session_secret=_SESSION_SECRET,
            **updates,
        )


@pytest.mark.parametrize(
    "url",
    (
        "https://public.example.com",
        "http://user:password@model-gateway:3000",
    ),
)
def test_model_gateway_rejects_public_hosts_and_embedded_credentials(
    tmp_path: Path,
    url: str,
) -> None:
    with pytest.raises(ValidationError, match="model gateway URL"):
        Settings(
            database_url="postgresql+psycopg://user:password@db/app",
            source_roots=(tmp_path,),
            asset_root=tmp_path / "assets",
            scratch_root=tmp_path / "scratch",
            api_token=_BASE_TOKEN,
            session_secret=_SESSION_SECRET,
            model_gateway_policy=ModelGatewayPolicy.OPTIONAL,
            model_gateway_url=url,
            model_gateway_internal_token=_MODEL_GATEWAY_TOKEN,
        )


def test_enabled_model_gateway_requires_private_internal_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "dm_assistant.config._POSTGRES_DSN_ADAPTER.validate_python",
        lambda _: None,
    )
    settings = Settings.model_construct(
        database_url="postgresql+psycopg://unit:unit-password@db/app",
        source_roots=(tmp_path,),
        asset_root=tmp_path / "assets",
        scratch_root=tmp_path / "scratch",
        api_token=_BASE_TOKEN,
        session_secret=_SESSION_SECRET,
        model_gateway_policy=ModelGatewayPolicy.OPTIONAL,
        model_gateway_url="http://model-gateway:3000",
    )
    object.__setattr__(settings, "api_token", SecretStr(_BASE_TOKEN))
    object.__setattr__(settings, "session_secret", SecretStr(_SESSION_SECRET))
    with pytest.raises(ValueError, match="requires its internal token"):
        settings.validate_runtime_policies()


def test_enabled_model_gateway_configuration_requires_internal_token(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValidationError, match="requires its internal token"):
        Settings(
            database_url="postgresql+psycopg://unit:unit-password@db/app",
            source_roots=(tmp_path,),
            asset_root=tmp_path / "assets",
            scratch_root=tmp_path / "scratch",
            api_token=_BASE_TOKEN,
            session_secret=_SESSION_SECRET,
            model_gateway_policy=ModelGatewayPolicy.OPTIONAL,
            model_gateway_url="http://model-gateway:3000",
        )


def test_logging_secret_values_include_token_dsn_and_password(tmp_path: Path) -> None:
    database_url = "postgresql+psycopg://user:super-secret-password@db/app"
    embedding_api_key = "hosted-embedding-secret"
    settings = Settings(
        database_url=database_url,
        source_roots=(tmp_path,),
        asset_root=tmp_path / "assets",
        scratch_root=tmp_path / "scratch",
        api_token=_BASE_TOKEN,
        session_secret=_SESSION_SECRET,
        embedding_runtime=EmbeddingRuntime.HOSTED,
        embedding_provider_policy=EmbeddingProviderPolicy.HOSTED_ALLOWED,
        embedding_api_key=embedding_api_key,
        embedding_hosted_retention_approved=True,
    )

    assert settings.logging_secret_values() == (
        database_url,
        _BASE_TOKEN,
        _SESSION_SECRET,
        embedding_api_key,
        "super-secret-password",
    )
