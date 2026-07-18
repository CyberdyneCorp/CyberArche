"""Notification ports (notifications spec)."""

from __future__ import annotations

from typing import Protocol

from cyberarche.domain.ids import NotificationId, TenantId, UserId
from cyberarche.domain.notifications import Notification, NotificationPreferences


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


class NotificationPreferencesRepository(Protocol):
    async def get(
        self, tenant_id: TenantId, user_id: UserId
    ) -> NotificationPreferences | None:
        """The user's saved preferences, or None if they never set any."""
        ...

    async def upsert(self, prefs: NotificationPreferences) -> None:
        """Insert or replace the user's preferences."""
        ...


class NotificationChannelPort(Protocol):
    """An outbound delivery channel (e.g. webhook, email). Built only when the
    deployment configures it; a channel failure must never break the in-app
    store, so the dispatcher swallows exceptions raised here."""

    channel: str

    async def send(
        self, notification: Notification, *, recipient_email: str | None
    ) -> None: ...
