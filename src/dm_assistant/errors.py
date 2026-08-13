"""Safe shared domain errors and transport-neutral rendering."""

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    """Stable public error codes shared by API and CLI adapters."""

    AUTHENTICATION_REQUIRED = "authentication_required"
    CONFIGURATION_INVALID = "configuration_invalid"
    CONFLICT = "conflict"
    DATABASE_UNAVAILABLE = "database_unavailable"
    FORBIDDEN = "forbidden"
    ASSET_STORAGE_UNAVAILABLE = "asset_storage_unavailable"
    DUNGEON_EXECUTION_FAILED = "dungeon_execution_failed"
    INVALID_INPUT = "invalid_input"
    MODEL_RUN_REJECTED = "model_run_rejected"
    NOT_FOUND = "not_found"


class DomainError(Exception):
    """An expected failure with a deliberately public, secret-safe message."""

    def __init__(self, code: ErrorCode, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.public_message = message
        self.status_code = status_code


class AuthenticationRequiredError(DomainError):
    """A generic authentication failure that never identifies the bad value."""

    def __init__(self) -> None:
        super().__init__(
            ErrorCode.AUTHENTICATION_REQUIRED,
            "Authentication required.",
            status_code=401,
        )


class ConfigurationError(DomainError):
    """A safe configuration failure that exposes field names, never values."""

    def __init__(self, invalid_fields: tuple[str, ...]) -> None:
        fields = ", ".join(sorted(set(invalid_fields))) or "unknown"
        super().__init__(
            ErrorCode.CONFIGURATION_INVALID,
            f"Invalid or missing configuration: {fields}.",
            status_code=500,
        )
        self.invalid_fields = tuple(sorted(set(invalid_fields)))


class DatabaseUnavailableError(DomainError):
    """A generic database failure without driver or connection details."""

    def __init__(self) -> None:
        super().__init__(
            ErrorCode.DATABASE_UNAVAILABLE,
            "Database is unavailable.",
            status_code=503,
        )


class ForbiddenError(DomainError):
    """An authenticated request failed a non-overridable security check."""

    def __init__(self, message: str = "The request is not permitted.") -> None:
        super().__init__(ErrorCode.FORBIDDEN, message, status_code=403)


class InvalidInputError(DomainError):
    """A domain-level validation failure with a caller-authored safe message."""

    def __init__(self, message: str = "The request is invalid.") -> None:
        super().__init__(ErrorCode.INVALID_INPUT, message, status_code=422)


class AssetStorageUnavailableError(DomainError):
    """Asset persistence cannot safely publish or verify a generated artifact."""

    def __init__(self, message: str) -> None:
        super().__init__(ErrorCode.ASSET_STORAGE_UNAVAILABLE, message, status_code=503)


class DungeonExecutionFailedError(DomainError):
    """An unexpected deterministic/persistence execution failure was contained."""

    def __init__(self, message: str) -> None:
        super().__init__(ErrorCode.DUNGEON_EXECUTION_FAILED, message, status_code=500)


class ModelRunRejectedError(DomainError):
    """A bounded model run failed safely before it could produce a draft."""

    def __init__(self, message: str) -> None:
        super().__init__(ErrorCode.MODEL_RUN_REJECTED, message, status_code=422)


class ResourceNotFoundError(DomainError):
    """A generic missing-resource failure without sensitive identifiers."""

    def __init__(self, message: str = "The requested resource was not found.") -> None:
        super().__init__(ErrorCode.NOT_FOUND, message, status_code=404)


class ConflictError(DomainError):
    """A safe domain conflict."""

    def __init__(
        self, message: str = "The requested operation conflicts with state."
    ) -> None:
        super().__init__(ErrorCode.CONFLICT, message, status_code=409)


def domain_error_payload(
    error: DomainError,
    *,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Build the canonical public error envelope."""
    payload: dict[str, Any] = {
        "code": error.code.value,
        "message": error.public_message,
    }
    if request_id is not None:
        payload["request_id"] = request_id
    return {"error": payload}


def format_cli_error(error: DomainError) -> str:
    """Render the same stable code/message pair for CLI commands."""
    return f"error [{error.code.value}]: {error.public_message}"
