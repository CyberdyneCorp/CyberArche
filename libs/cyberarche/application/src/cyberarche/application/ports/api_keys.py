"""API key repository port."""

from __future__ import annotations

from typing import Protocol

from cyberarche.domain.api_keys import ApiKey
from cyberarche.domain.ids import TenantId, UserId


class ApiKeyRepository(Protocol):
    async def add(self, key: ApiKey) -> None: ...

    async def by_hash(self, secret_hash: str) -> ApiKey | None: ...

    async def get(self, user_id: UserId, key_id: str) -> ApiKey | None: ...

    async def list_for_user(
        self, tenant_id: TenantId, user_id: UserId
    ) -> list[ApiKey]: ...

    async def update(self, key: ApiKey) -> None: ...
