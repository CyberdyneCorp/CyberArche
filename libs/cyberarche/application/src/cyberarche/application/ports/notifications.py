"""Notification repository port (notifications spec)."""

from __future__ import annotations

from typing import Protocol

from cyberarche.domain.ids import NotificationId, TenantId, UserId
from cyberarche.domain.notifications import Notification


class NotificationRepository(Protocol):
    async def add(self, notification: Notification) -> None: ...

    async def list_for_user(
        self, tenant_id: TenantId, user_id: UserId, *, limit: int = 50
    ) -> list[Notification]:
        """The user's notifications, newest first."""
        ...

    async def unread_count(self, tenant_id: TenantId, user_id: UserId) -> int: ...

    async def mark_read(
        self, tenant_id: TenantId, user_id: UserId, notification_id: NotificationId
    ) -> None:
        """Mark one of the user's notifications read (no-op if not theirs)."""
        ...

    async def mark_all_read(self, tenant_id: TenantId, user_id: UserId) -> None: ...
