"""Notification use cases (notifications spec): a user's own inbox."""

from __future__ import annotations

from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.notifications import NotificationRepository
from cyberarche.domain.ids import NotificationId
from cyberarche.domain.notifications import Notification


class NotificationUseCases:
    def __init__(self, notifications: NotificationRepository) -> None:
        self._notifications = notifications

    async def list(
        self, caller: CallerContext, *, limit: int = 50
    ) -> list[Notification]:
        return await self._notifications.list_for_user(
            caller.tenant_id, caller.user_id, limit=limit
        )

    async def unread_count(self, caller: CallerContext) -> int:
        return await self._notifications.unread_count(
            caller.tenant_id, caller.user_id
        )

    async def mark_read(
        self, caller: CallerContext, notification_id: NotificationId
    ) -> None:
        await self._notifications.mark_read(
            caller.tenant_id, caller.user_id, notification_id
        )

    async def mark_all_read(self, caller: CallerContext) -> None:
        await self._notifications.mark_all_read(caller.tenant_id, caller.user_id)
