"""Transport-neutral domain error rendering tests."""

import pytest

from dm_assistant.errors import (
    AuthenticationRequiredError,
    ConfigurationError,
    ConflictError,
    DatabaseUnavailableError,
    DomainError,
    ForbiddenError,
    InvalidInputError,
    ResourceNotFoundError,
    domain_error_payload,
    format_cli_error,
)


@pytest.mark.parametrize(
    ("error", "status_code"),
    (
        (AuthenticationRequiredError(), 401),
        (InvalidInputError(), 422),
        (ResourceNotFoundError(), 404),
        (ConflictError(), 409),
        (DatabaseUnavailableError(), 503),
        (ForbiddenError(), 403),
        (ConfigurationError(("api_token",)), 500),
    ),
)
def test_domain_errors_have_stable_codes_messages_and_statuses(
    error: DomainError,
    status_code: int,
) -> None:
    payload = domain_error_payload(error, request_id="req-1")["error"]

    assert error.status_code == status_code
    assert payload == {
        "code": error.code.value,
        "message": error.public_message,
        "request_id": "req-1",
    }
    assert format_cli_error(error) == (
        f"error [{payload['code']}]: {payload['message']}"
    )


def test_configuration_error_sorts_fields_without_values() -> None:
    error = ConfigurationError(("source_roots", "api_token", "api_token"))

    assert error.invalid_fields == ("api_token", "source_roots")
    assert str(error) == ("Invalid or missing configuration: api_token, source_roots.")
