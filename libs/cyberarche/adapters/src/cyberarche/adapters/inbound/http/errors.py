"""The single DomainError -> HTTP status seam."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from cyberarche.domain.errors import (
    Conflict,
    DomainError,
    NotAuthenticated,
    NotAuthorized,
    NotFound,
    ValidationFailed,
)

_STATUS_BY_ERROR: list[tuple[type[DomainError], int]] = [
    (NotAuthenticated, 401),
    (NotAuthorized, 403),
    (NotFound, 404),
    (Conflict, 409),
    (ValidationFailed, 422),
]


def _status_for(error: DomainError) -> int:
    for error_type, status in _STATUS_BY_ERROR:
        if isinstance(error, error_type):
            return status
    return 500


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain_error(request: Request, error: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=_status_for(error),
            content={"error": type(error).__name__, "detail": str(error)},
        )
