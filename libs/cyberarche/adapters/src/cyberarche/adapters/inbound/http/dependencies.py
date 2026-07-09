"""FastAPI dependencies: resolve the Container and authenticate the caller.

Identity and tenant come ONLY from verified token claims — never from the
request path or body (auth-integration spec). A missing or invalid token
fails with 401 before any use case runs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, Request

from cyberarche.application.kernel import CallerContext
from cyberarche.application.use_cases import UseCases
from cyberarche.domain.errors import NotAuthenticated
from cyberarche.domain.ids import TenantId, UserId

if TYPE_CHECKING:  # wiring imports adapters; avoid a runtime cycle
    from cyberarche.adapters.wiring import Container


def get_container(request: Request) -> "Container":
    return request.app.state.container


def get_use_cases(request: Request) -> UseCases:
    return get_container(request).use_cases


def _bearer_token(request: Request) -> str:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise NotAuthenticated("missing bearer token")
    return token.strip()


async def require_caller(
    request: Request,
    container: Annotated["Container", Depends(get_container)],
) -> CallerContext:
    claims = await container.token_port.verify(_bearer_token(request))
    return CallerContext(
        user_id=UserId(claims.subject),
        tenant_id=TenantId(claims.tenant_id),
        email=claims.email,
        scopes=claims.scopes,
        is_service=claims.is_service,
    )


def access_token(request: Request) -> str:
    """The caller's raw bearer, for outbound calls that run as the user
    (e.g. the Python interpreter authorizes per-user)."""
    return _bearer_token(request)


Cases = Annotated[UseCases, Depends(get_use_cases)]
Caller = Annotated[CallerContext, Depends(require_caller)]
AccessToken = Annotated[str, Depends(access_token)]
