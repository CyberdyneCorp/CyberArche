"""Personal API keys (auth-integration spec).

A key is a long-lived bearer credential for external MCP clients
(Claude, ChatGPT, other agents). It authenticates strictly as its owning
user; only a SHA-256 hash is ever stored.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, replace
from datetime import datetime

from cyberarche.domain.ids import TenantId, UserId

KEY_PREFIX = "cak_"  # CyberArche key
_SECRET_BYTES = 32
_DISPLAY_CHARS = 8


def generate_secret() -> str:
    return KEY_PREFIX + secrets.token_urlsafe(_SECRET_BYTES)

def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()

def display_prefix(secret: str) -> str:
    return secret[: len(KEY_PREFIX) + _DISPLAY_CHARS] + "…"

def looks_like_api_key(token: str) -> bool:
    return token.startswith(KEY_PREFIX)


@dataclass(frozen=True, slots=True)
class ApiKey:
    id: str
    tenant_id: TenantId
    user_id: UserId
    name: str
    secret_hash: str
    prefix: str  # non-secret display form, e.g. "cak_a1b2c3d4…"
    created_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    last_used_at: datetime | None = None

    def is_usable(self, now: datetime) -> bool:
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None and now >= self.expires_at:
            return False
        return True

    def revoke(self, now: datetime) -> "ApiKey":
        return replace(self, revoked_at=now)

    def touched(self, now: datetime) -> "ApiKey":
        return replace(self, last_used_at=now)
