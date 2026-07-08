"""Identity ports: token verification and service-to-service auth."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Claims:
    """Verified claims extracted from an access token."""

    subject: str
    tenant_id: str
    email: str | None = None
    scopes: frozenset[str] = field(default_factory=frozenset)
    is_service: bool = False


class TokenPort(Protocol):
    """Verifies an access token and returns its claims.

    Raises domain NotAuthenticated on invalid/expired/unverifiable tokens.
    """

    async def verify(self, token: str) -> Claims: ...


class ServiceTokenPort(Protocol):
    """Obtains a service token (OAuth2 client-credentials) for outbound calls."""

    async def service_token(self) -> str: ...


@dataclass(frozen=True, slots=True)
class TokenPair:
    access_token: str
    refresh_token: str


class AuthGatewayPort(Protocol):
    """Session gateway for the SPA: the browser talks only to our API,
    which forwards credential exchanges to CyberdyneAuth (its CORS policy
    does not admit browser origins)."""

    async def password_login(self, *, email: str, password: str) -> TokenPair: ...

    async def refresh(self, *, refresh_token: str) -> TokenPair: ...


class AuthorizationPort(Protocol):
    """Evaluates whether an identity may perform an action on a resource.

    Delegates to CyberdyneAuth IAM where policy evaluation is needed;
    role-based checks on memberships happen in use cases.
    """

    async def evaluate(self, *, user_id: str, action: str, resource: str) -> bool: ...
