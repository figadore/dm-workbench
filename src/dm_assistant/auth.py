"""Single-DM Bearer and signed browser-session authentication primitives."""

import base64
import hmac
import json
import secrets
import time
from dataclasses import dataclass

from pydantic import SecretStr

SESSION_COOKIE_NAME = "dm_session"


@dataclass(frozen=True, slots=True)
class DmPrincipal:
    """The sole authenticated principal in the MVP."""

    id: str = "dm"
    scope: str = "dm"


@dataclass(frozen=True, slots=True)
class BrowserSession:
    """Safe signed-cookie claims; no API/OAuth credential is stored."""

    principal: DmPrincipal
    csrf_token: str
    expires_at: int


class SessionCodec:
    """Issue and verify compact HMAC-SHA256 single-DM browser sessions."""

    def __init__(
        self, secret: SecretStr, *, lifetime_seconds: int = 12 * 60 * 60
    ) -> None:
        if lifetime_seconds <= 0:
            raise ValueError("session lifetime must be positive")
        self._key = secret.get_secret_value().encode("ascii")
        self._lifetime_seconds = lifetime_seconds

    def issue(self, *, now: int | None = None) -> tuple[str, BrowserSession]:
        issued_at = int(time.time()) if now is None else now
        session = BrowserSession(
            principal=DmPrincipal(),
            csrf_token=secrets.token_urlsafe(32),
            expires_at=issued_at + self._lifetime_seconds,
        )
        payload = json.dumps(
            {
                "csrf": session.csrf_token,
                "exp": session.expires_at,
                "principal": session.principal.id,
                "version": 1,
            },
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
        encoded = _encode_base64(payload)
        signature = _encode_base64(hmac.digest(self._key, encoded, "sha256"))
        return f"{encoded.decode('ascii')}.{signature.decode('ascii')}", session

    def decode(
        self, cookie: str | None, *, now: int | None = None
    ) -> BrowserSession | None:
        if cookie is None or len(cookie) > 2048:
            return None
        encoded_text, separator, signature_text = cookie.partition(".")
        if not separator:
            return None
        try:
            encoded = encoded_text.encode("ascii")
            supplied_signature = _decode_base64(signature_text)
            expected_signature = hmac.digest(self._key, encoded, "sha256")
            if not hmac.compare_digest(supplied_signature, expected_signature):
                return None
            payload = json.loads(_decode_base64(encoded_text))
            if not isinstance(payload, dict):
                return None
            if payload.get("version") != 1 or payload.get("principal") != "dm":
                return None
            csrf_token = payload.get("csrf")
            expires_at = payload.get("exp")
            if not isinstance(csrf_token, str) or not isinstance(expires_at, int):
                return None
            current = int(time.time()) if now is None else now
            if expires_at <= current:
                return None
            return BrowserSession(
                principal=DmPrincipal(),
                csrf_token=csrf_token,
                expires_at=expires_at,
            )
        except (UnicodeError, ValueError, json.JSONDecodeError):
            return None


def authenticate_bearer_token(
    authorization_header: str | None,
    expected_token: SecretStr,
) -> DmPrincipal | None:
    """Return the DM principal after a constant-time exact Bearer comparison."""
    if authorization_header is None:
        return None
    scheme, separator, credential = authorization_header.partition(" ")
    if (
        not separator
        or scheme.lower() != "bearer"
        or not credential
        or " " in credential
    ):
        return None
    try:
        matches = secrets.compare_digest(
            credential.encode("ascii"),
            expected_token.get_secret_value().encode("ascii"),
        )
    except UnicodeEncodeError:
        return None
    return DmPrincipal() if matches else None


def csrf_matches(supplied: str | None, session: BrowserSession) -> bool:
    """Constant-time CSRF comparison for browser-session write routes."""
    if supplied is None:
        return False
    try:
        return secrets.compare_digest(
            supplied.encode("ascii"),
            session.csrf_token.encode("ascii"),
        )
    except UnicodeEncodeError:
        return False


def _encode_base64(value: bytes) -> bytes:
    return base64.urlsafe_b64encode(value).rstrip(b"=")


def _decode_base64(value: str) -> bytes:
    encoded = value.encode("ascii")
    padding = b"=" * (-len(encoded) % 4)
    return base64.b64decode(encoded + padding, altchars=b"-_", validate=True)
