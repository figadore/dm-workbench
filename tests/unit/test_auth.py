"""Single-DM Bearer authentication tests."""

import pytest
from pydantic import SecretStr

from dm_assistant.auth import SessionCodec, authenticate_bearer_token, csrf_matches

_TOKEN = SecretStr("auth-test-token-00000000000000000000")


def test_exact_bearer_token_returns_single_dm_principal() -> None:
    principal = authenticate_bearer_token(
        f"Bearer {_TOKEN.get_secret_value()}",
        _TOKEN,
    )

    assert principal is not None
    assert principal.id == "dm"
    assert principal.scope == "dm"


@pytest.mark.parametrize(
    "header",
    (
        None,
        "",
        "Basic something",
        "Bearer",
        "Bearer wrong-token-0000000000000000000",
        "Bearer token with spaces",
        "Bearer tåken-value-that-is-not-ascii-00000",
    ),
)
def test_malformed_or_wrong_token_is_rejected(header: str | None) -> None:
    assert authenticate_bearer_token(header, _TOKEN) is None


def test_signed_browser_session_round_trip_and_csrf() -> None:
    secret = SecretStr("browser-session-secret-000000000000000")
    codec = SessionCodec(secret, lifetime_seconds=60)

    cookie, issued = codec.issue(now=100)
    decoded = codec.decode(cookie, now=159)

    assert secret.get_secret_value() not in cookie
    assert decoded == issued
    assert decoded is not None
    assert csrf_matches(decoded.csrf_token, decoded) is True
    assert csrf_matches("wrong", decoded) is False
    assert codec.decode(cookie, now=160) is None


def test_signed_browser_session_rejects_tampering_and_malformed_values() -> None:
    codec = SessionCodec(SecretStr("browser-session-secret-000000000000000"))
    cookie, _ = codec.issue(now=100)
    payload, signature = cookie.split(".")

    assert codec.decode(f"{payload}x.{signature}", now=101) is None
    assert codec.decode(f"{payload}.{signature}x", now=101) is None
    assert codec.decode("not-a-session", now=101) is None
    assert codec.decode("x" * 2049, now=101) is None
