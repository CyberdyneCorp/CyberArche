"""SPA session endpoints: credential exchange proxied to CyberdyneAuth.

The auth service's CORS policy does not admit browser origins, so the web
app signs in through our API (BFF). The short-lived ACCESS token is returned
in the JSON body for the SPA to hold in memory and send as a Bearer token.
The long-lived REFRESH token is set as an HttpOnly, Secure, SameSite cookie
scoped to the refresh endpoint — never exposed to JavaScript, so an XSS
cannot exfiltrate it for persistent account takeover (security audit F-004).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, EmailStr

from cyberarche.adapters.inbound.http.dependencies import get_container
from cyberarche.domain.errors import NotAuthenticated, NotFound

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# HttpOnly cookie holding the refresh token. Path-scoped to the refresh
# endpoint so it is only ever sent there, not on every API call.
_REFRESH_COOKIE = "cyberarche_refresh"
_REFRESH_PATH = "/api/v1/auth/session"
_REFRESH_MAX_AGE = 30 * 24 * 3600  # 30 days


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SessionResponse(BaseModel):
    """The refresh token is intentionally absent — it lives in the cookie."""

    access_token: str
    token_type: str = "bearer"


def _gateway(container=Depends(get_container)):
    gateway = container.auth_gateway
    if gateway is None:
        raise NotFound("session login is not configured on this deployment")
    return gateway


def _set_refresh_cookie(response: Response, request: Request, refresh_token: str) -> None:
    response.set_cookie(
        _REFRESH_COOKIE,
        refresh_token,
        max_age=_REFRESH_MAX_AGE,
        httponly=True,
        # Secure whenever the external scheme is https (proxy sets X-Forwarded-Proto,
        # honoured via --proxy-headers). Lets local http dev still work.
        secure=request.url.scheme == "https",
        samesite="strict",
        path=_REFRESH_PATH,
    )


@router.post("/session")
async def create_session(
    body: LoginRequest,
    request: Request,
    response: Response,
    gateway: Annotated[object, Depends(_gateway)],
) -> SessionResponse:
    pair = await gateway.password_login(email=body.email, password=body.password)
    _set_refresh_cookie(response, request, pair.refresh_token)
    return SessionResponse(access_token=pair.access_token)


@router.post("/session/refresh")
async def refresh_session(
    request: Request,
    response: Response,
    gateway: Annotated[object, Depends(_gateway)],
) -> SessionResponse:
    """Refresh using the HttpOnly cookie — the SPA never sees the refresh token.
    The refresh token is rotated: a fresh one replaces the cookie each time."""
    refresh_token = request.cookies.get(_REFRESH_COOKIE)
    if not refresh_token:
        raise NotAuthenticated("no refresh session")
    pair = await gateway.refresh(refresh_token=refresh_token)
    _set_refresh_cookie(response, request, pair.refresh_token)
    return SessionResponse(access_token=pair.access_token)


@router.post("/session/logout")
async def logout(response: Response) -> Response:
    """Clear the refresh cookie so it can no longer mint access tokens."""
    response.delete_cookie(_REFRESH_COOKIE, path=_REFRESH_PATH)
    response.status_code = 204
    return response
