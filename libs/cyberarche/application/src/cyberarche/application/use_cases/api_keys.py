"""API key use cases (auth-integration spec): create/list/revoke, plus the
CompositeTokenVerifier that lets keys ride the existing TokenPort seam so
HTTP, the WS relay, and MCP all accept them with no surface changes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.api_keys import ApiKeyRepository
from cyberarche.application.ports.identity import Claims, TokenPort
from cyberarche.application.ports.telemetry import ClockPort, IdPort
from cyberarche.domain.api_keys import (
    ApiKey,
    display_prefix,
    generate_secret,
    hash_secret,
    looks_like_api_key,
)
from cyberarche.domain.errors import NotAuthenticated, NotFound, ValidationFailed


@dataclass(frozen=True, slots=True)
class CreatedApiKey:
    key: ApiKey
    secret: str  # returned exactly once


class ApiKeyUseCases:
    def __init__(
        self, keys: ApiKeyRepository, clock: ClockPort, ids: IdPort
    ) -> None:
        self._keys = keys
        self._clock = clock
        self._ids = ids

    async def create(
        self,
        caller: CallerContext,
        *,
        name: str,
        expires_at: datetime | None = None,
    ) -> CreatedApiKey:
        name = name.strip()
        if not name:
            raise ValidationFailed("api key name must not be empty")
        secret = generate_secret()
        key = ApiKey(
            id=self._ids.new_id(),
            tenant_id=caller.tenant_id,
            user_id=caller.user_id,
            name=name,
            secret_hash=hash_secret(secret),
            prefix=display_prefix(secret),
            created_at=self._clock.now(),
            expires_at=expires_at,
        )
        await self._keys.add(key)
        return CreatedApiKey(key=key, secret=secret)

    async def list(self, caller: CallerContext) -> list[ApiKey]:
        """Metadata only — hashes are never exposed, secrets don't exist."""
        return await self._keys.list_for_user(caller.tenant_id, caller.user_id)

    async def revoke(self, caller: CallerContext, key_id: str) -> ApiKey:
        key = await self._keys.get(caller.user_id, key_id)
        if key is None:
            raise NotFound("api key not found")
        revoked = key.revoke(self._clock.now())
        await self._keys.update(revoked)
        return revoked


class CompositeTokenVerifier:
    """TokenPort: `cak_…` secrets resolve as API keys; everything else
    delegates to the inner verifier (JWKS / introspection)."""

    def __init__(
        self, keys: ApiKeyRepository, inner: TokenPort, clock: ClockPort
    ) -> None:
        self._keys = keys
        self._inner = inner
        self._clock = clock

    async def verify(self, token: str) -> Claims:
        if not looks_like_api_key(token):
            return await self._inner.verify(token)
        key = await self._keys.by_hash(hash_secret(token))
        now = self._clock.now()
        if key is None or not key.is_usable(now):
            raise NotAuthenticated("api key is invalid, revoked, or expired")
        await self._keys.update(key.touched(now))  # last-used tracking
        return Claims(subject=key.user_id, tenant_id=key.tenant_id)
