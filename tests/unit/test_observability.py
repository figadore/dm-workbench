"""Structured logging context and recursive redaction tests."""

import json
import logging
import sys
from types import TracebackType

import pytest
from pydantic import SecretStr

from dm_assistant.observability import (
    JsonLogFormatter,
    bind_log_context,
    current_log_context,
)


def log_record(
    message: str,
    *,
    event_data: object | None = None,
    exc_info: tuple[type[BaseException], BaseException, TracebackType | None]
    | None = None,
) -> logging.LogRecord:
    record = logging.LogRecord(
        name="dm_assistant.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=exc_info,
    )
    if event_data is not None:
        record.event_data = event_data
    return record


def test_json_formatter_emits_all_bound_correlation_ids() -> None:
    formatter = JsonLogFormatter()
    identifiers = {
        "request_id": "req-1",
        "ingestion_run_id": "ing-1",
        "embedding_run_id": "emb-1",
        "model_run_id": "model-1",
        "generation_run_id": "generation-1",
        "change_set_id": "change-1",
        "campaign_revision_id": "revision-1",
    }

    with bind_log_context(**identifiers):
        document = json.loads(formatter.format(log_record("completed")))

    assert document["message"] == "completed"
    assert document["level"] == "INFO"
    assert document["logger"] == "dm_assistant.test"
    assert document["timestamp"].endswith("+00:00")
    assert {name: document[name] for name in identifiers} == identifiers
    assert current_log_context() == {}


def test_formatter_recursively_redacts_secrets_source_text_and_url_passwords() -> None:
    token = "api-token-that-must-never-appear"
    password = "database-password-that-must-never-appear"
    formatter = JsonLogFormatter(secret_values=(token, password))
    record = log_record(
        f"request token was {token}",
        event_data={
            "headers": {"Authorization": f"Bearer {token}"},
            "nested": [
                {"database_password": password},
                {"source_text": "The hidden villain is Synthetic."},
                {"safe_url": f"postgresql://user:{password}@db/app"},
                {"safe_count": 7},
            ],
            "credential": SecretStr("another-secret-value"),
            "binary": b"private bytes",
        },
    )

    output = formatter.format(record)
    document = json.loads(output)

    for forbidden in (
        token,
        password,
        "hidden villain",
        "another-secret-value",
        "private bytes",
    ):
        assert forbidden not in output
    assert document["message"] == "request token was [REDACTED]"
    assert document["data"]["headers"]["Authorization"] == "[REDACTED]"
    assert document["data"]["nested"][2]["safe_url"] == (
        "postgresql://user:[REDACTED]@db/app"
    )
    assert document["data"]["nested"][3]["safe_count"] == 7
    assert document["data"]["binary"] == "<bytes:13>"


def test_nested_context_restores_outer_values() -> None:
    with bind_log_context(request_id="outer"):
        with bind_log_context(request_id="inner", model_run_id="model"):
            assert current_log_context() == {
                "request_id": "inner",
                "model_run_id": "model",
            }
        assert current_log_context() == {"request_id": "outer"}
    assert current_log_context() == {}


def test_unknown_context_field_fails_closed() -> None:
    with pytest.raises(ValueError, match="unknown log context"):
        with bind_log_context(raw_source_text="do not log"):
            pass


def test_exception_output_includes_type_but_not_exception_message() -> None:
    formatter = JsonLogFormatter()
    try:
        raise RuntimeError("sensitive provider response")
    except RuntimeError as error:
        record = log_record(
            "operation failed",
            exc_info=(RuntimeError, error, sys.exc_info()[2]),
        )

    output = formatter.format(record)

    assert json.loads(output)["exception_type"] == "RuntimeError"
    assert "sensitive provider response" not in output
