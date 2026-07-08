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


class AuthorizationPort(Protocol):
    """Evaluates whether an identity may perform an action on a resource.

    Delegates to CyberdyneAuth IAM where policy evaluation is needed;
    role-based checks on memberships happen in use cases.
    """

    async def evaluate(self, *, user_id: str, action: str, resource: str) -> bool: ...
