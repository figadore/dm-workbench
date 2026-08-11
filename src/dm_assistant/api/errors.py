"""FastAPI adapter for safe domain errors."""

from fastapi import Request
from fastapi.responses import JSONResponse

from dm_assistant.errors import DomainError, domain_error_payload


def domain_error_response(
    error: DomainError,
    *,
    request_id: str | None,
) -> JSONResponse:
    """Render a domain error as the canonical JSON envelope."""
    headers = {"WWW-Authenticate": "Bearer"} if error.status_code == 401 else None
    return JSONResponse(
        status_code=error.status_code,
        content=domain_error_payload(error, request_id=request_id),
        headers=headers,
    )


async def domain_error_handler(request: Request, error: Exception) -> JSONResponse:
    """FastAPI exception handler for expected application failures."""
    if not isinstance(error, DomainError):
        raise TypeError("domain error handler received an unexpected exception")
    return domain_error_response(
        error,
        request_id=getattr(request.state, "request_id", None),
    )
