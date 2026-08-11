"""Structured JSON logging with contextual IDs and fail-closed redaction."""

import json
import logging
import re
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import SecretStr

_LOGGER_NAME = "dm_assistant"
_REDACTED = "[REDACTED]"
_CONTEXT_FIELDS = (
    "request_id",
    "ingestion_run_id",
    "embedding_run_id",
    "model_run_id",
    "generation_run_id",
    "change_set_id",
    "campaign_revision_id",
)
_CONTEXT: ContextVar[dict[str, str] | None] = ContextVar(
    "dm_assistant_log_context",
    default=None,
)
_SECRET_KEYS = {
    "api_key",
    "authorization",
    "compiled_context",
    "content",
    "context",
    "cookie",
    "credential",
    "database_url",
    "document_text",
    "dsn",
    "messages",
    "oauth_token",
    "password",
    "prompt",
    "raw_text",
    "request_body",
    "response_body",
    "secret",
    "source",
    "source_body",
    "source_content",
    "source_text",
    "token",
}
_CREDENTIAL_URL = re.compile(
    r"(?P<prefix>[A-Za-z][A-Za-z0-9+.-]*://[^:/@\s]+:)(?P<password>[^@/\s]+)(?=@)"
)


@contextmanager
def bind_log_context(**identifiers: str | None) -> Iterator[None]:
    """Bind known correlation IDs for all logs in the current async context."""
    unknown = set(identifiers) - set(_CONTEXT_FIELDS)
    if unknown:
        raise ValueError(f"unknown log context fields: {', '.join(sorted(unknown))}")
    merged = dict(_CONTEXT.get() or {})
    merged.update(
        (name, value) for name, value in identifiers.items() if value is not None
    )
    token = _CONTEXT.set(merged)
    try:
        yield
    finally:
        _CONTEXT.reset(token)


def current_log_context() -> dict[str, str]:
    """Return a copy of the currently bound correlation identifiers."""
    return dict(_CONTEXT.get() or {})


class JsonLogFormatter(logging.Formatter):
    """Emit one canonical JSON object without arbitrary LogRecord values."""

    def __init__(self, *, secret_values: Sequence[str] = ()) -> None:
        super().__init__()
        self._secret_values = tuple(
            sorted(
                {value for value in secret_values if len(value) >= 4},
                key=len,
                reverse=True,
            )
        )

    def format(self, record: logging.LogRecord) -> str:
        document: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": self._redact_string(record.getMessage()),
        }
        context = current_log_context()
        for field in _CONTEXT_FIELDS:
            if value := context.get(field):
                document[field] = value
        event_data = getattr(record, "event_data", None)
        if event_data is not None:
            document["data"] = self.redact(event_data)
        if record.exc_info is not None and record.exc_info[0] is not None:
            document["exception_type"] = record.exc_info[0].__name__
        return json.dumps(
            document,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    def redact(self, value: object, *, _depth: int = 0) -> Any:
        """Recursively reduce values to safe JSON and redact sensitive fields."""
        if _depth >= 12:
            return "<maximum-depth>"
        if isinstance(value, SecretStr):
            return _REDACTED
        if value is None or isinstance(value, (bool, int)):
            return value
        if isinstance(value, float):
            return (
                value if value == value and abs(value) != float("inf") else str(value)
            )
        if isinstance(value, str):
            return self._redact_string(value)
        if isinstance(value, Enum):
            return self.redact(value.value, _depth=_depth + 1)
        if isinstance(value, Path):
            return self._redact_string(str(value))
        if isinstance(value, bytes):
            return f"<bytes:{len(value)}>"
        if isinstance(value, Mapping):
            output: dict[str, Any] = {}
            for raw_key, item in value.items():
                key = str(raw_key)
                if _is_secret_key(key):
                    output[key] = _REDACTED
                else:
                    output[key] = self.redact(item, _depth=_depth + 1)
            return output
        if isinstance(value, Sequence):
            return [self.redact(item, _depth=_depth + 1) for item in value]
        return f"<{type(value).__name__}>"

    def _redact_string(self, value: str) -> str:
        redacted = value
        for secret in self._secret_values:
            redacted = redacted.replace(secret, _REDACTED)
        return _CREDENTIAL_URL.sub(rf"\g<prefix>{_REDACTED}", redacted)


def configure_logging(
    level: str,
    *,
    secret_values: Sequence[str] = (),
) -> logging.Logger:
    """Configure only the Workbench logger, leaving host logging untouched."""
    logger = logging.getLogger(_LOGGER_NAME)
    logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter(secret_values=secret_values))
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger


def get_logger(name: str) -> logging.Logger:
    """Return a child of the centrally configured application logger."""
    suffix = name.removeprefix(f"{_LOGGER_NAME}.").removeprefix(_LOGGER_NAME)
    return logging.getLogger(f"{_LOGGER_NAME}.{suffix.lstrip('.')}")


def _is_secret_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
    return (
        normalized in _SECRET_KEYS
        or normalized.endswith("_password")
        or normalized.endswith("_secret")
        or normalized.endswith("_token")
        or normalized.endswith("_api_key")
        or normalized.endswith("_credential")
    )
