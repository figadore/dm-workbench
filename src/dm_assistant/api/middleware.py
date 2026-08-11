"""Default-deny API authentication and request correlation middleware."""

import re
import time
import uuid
from collections.abc import Collection

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import RedirectResponse, Response
from starlette.types import ASGIApp

from dm_assistant.api.errors import domain_error_response
from dm_assistant.auth import (
    SESSION_COOKIE_NAME,
    SessionCodec,
    authenticate_bearer_token,
)
from dm_assistant.config import Settings
from dm_assistant.errors import AuthenticationRequiredError
from dm_assistant.observability import bind_log_context, get_logger

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_REQUEST_ID_HEADER = "X-Request-ID"
logger = get_logger(__name__)


class SecurityObservabilityMiddleware(BaseHTTPMiddleware):
    """Authenticate every path except an explicit health allowlist and add IDs."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        settings: Settings,
        public_paths: Collection[str],
    ) -> None:
        super().__init__(app)
        self._settings = settings
        self._session_codec = SessionCodec(settings.session_secret)
        self._public_paths = frozenset(public_paths)

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = _request_id(request.headers.get(_REQUEST_ID_HEADER))
        request.state.request_id = request_id
        started = time.perf_counter()
        with bind_log_context(request_id=request_id):
            if request.url.path not in self._public_paths:
                principal = authenticate_bearer_token(
                    request.headers.get("Authorization"),
                    self._settings.api_token,
                )
                if principal is not None:
                    request.state.principal = principal
                    request.state.auth_method = "bearer"
                    response = await call_next(request)
                else:
                    browser_session = self._session_codec.decode(
                        request.cookies.get(SESSION_COOKIE_NAME)
                    )
                    if browser_session is not None:
                        request.state.principal = browser_session.principal
                        request.state.browser_session = browser_session
                        request.state.auth_method = "session"
                        response = await call_next(request)
                    elif "text/html" in request.headers.get("Accept", ""):
                        response = RedirectResponse("/login", status_code=303)
                    else:
                        response = domain_error_response(
                            AuthenticationRequiredError(),
                            request_id=request_id,
                        )
            else:
                response = await call_next(request)
            response.headers[_REQUEST_ID_HEADER] = request_id
            route = request.scope.get("route")
            route_template = getattr(route, "path", "<unmatched>")
            logger.info(
                "request completed",
                extra={
                    "event_data": {
                        "method": request.method,
                        "route": route_template,
                        "status_code": response.status_code,
                        "duration_ms": round(
                            (time.perf_counter() - started) * 1000,
                            3,
                        ),
                    }
                },
            )
            return response


def _request_id(candidate: str | None) -> str:
    if candidate is not None and _REQUEST_ID_PATTERN.fullmatch(candidate):
        return candidate
    return uuid.uuid4().hex
