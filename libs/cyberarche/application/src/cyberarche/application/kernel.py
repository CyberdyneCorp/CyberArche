"""Caller identity as resolved from verified token claims.

Tenant and identity come ONLY from verified claims (auth-integration spec) —
inbound adapters build a CallerContext before any use case runs, and use
cases trust nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from cyberarche.domain.ids import TenantId, UserId


@dataclass(frozen=True, slots=True)
class CallerContext:
    user_id: UserId
    tenant_id: TenantId
    email: str | None = None
    scopes: frozenset[str] = field(default_factory=frozenset)
    is_service: bool = False
