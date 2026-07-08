"""SPA session endpoints: credential exchange proxied to CyberdyneAuth.

The auth service's CORS policy does not admit browser origins, so the
web app signs in through our API. Tokens are returned to the client and
used as Bearer tokens on every subsequent call — this service stays
stateless.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr

from cyberarche.adapters.inbound.http.dependencies import get_container
from cyberarche.domain.errors import NotFound

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class SessionResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


def _gateway(container=Depends(get_container)):
    gateway = container.auth_gateway
    if gateway is None:
        raise NotFound("session login is not configured on this deployment")
    return gateway


@router.post("/session")
async def create_session(
    body: LoginRequest, gateway: Annotated[object, Depends(_gateway)]
) -> SessionResponse:
    pair = await gateway.password_login(email=body.email, password=body.password)
    return SessionResponse(
        access_token=pair.access_token, refresh_token=pair.refresh_token
    )


@router.post("/session/refresh")
async def refresh_session(
    body: RefreshRequest, gateway: Annotated[object, Depends(_gateway)]
) -> SessionResponse:
    pair = await gateway.refresh(refresh_token=body.refresh_token)
    return SessionResponse(
        access_token=pair.access_token, refresh_token=pair.refresh_token
    )
