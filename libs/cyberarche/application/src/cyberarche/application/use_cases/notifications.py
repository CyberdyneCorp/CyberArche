"""Notification use cases (notifications spec): a user's own inbox, their
delivery preferences, and the dispatcher that stores + fans out a notification."""

from __future__ import annotations

from collections.abc import Sequence

from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.notifications import (
    NotificationChannelPort,
    NotificationPreferencesRepository,
    NotificationRepository,
)
from cyberarche.domain.ids import NotificationId
from cyberarche.domain.notifications import Notification, NotificationPreferences


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


class NotificationPreferencesUseCases:
    """Read and update the caller's own notification preferences."""

    def __init__(self, prefs: NotificationPreferencesRepository) -> None:
        self._prefs = prefs

    async def get(self, caller: CallerContext) -> NotificationPreferences:
        prefs = await self._prefs.get(caller.tenant_id, caller.user_id)
        return prefs or NotificationPreferences.defaults(
            caller.tenant_id, caller.user_id
        )

    async def update(
        self,
        caller: CallerContext,
        *,
        email_enabled: bool,
        push_enabled: bool,
        mentions_enabled: bool,
        agent_results_enabled: bool,
    ) -> NotificationPreferences:
        prefs = NotificationPreferences(
            tenant_id=caller.tenant_id,
            user_id=caller.user_id,
            email_enabled=email_enabled,
            push_enabled=push_enabled,
            mentions_enabled=mentions_enabled,
            agent_results_enabled=agent_results_enabled,
        )
        await self._prefs.upsert(prefs)
        return prefs


class NotificationDispatcher:
    """Stores every notification for the in-app inbox, then delivers it to each
    of the recipient's enabled channels that is configured on the deployment.

    In-app storage always happens (preserving today's behaviour when no channel
    is configured). Per-kind and per-channel preferences gate the extra delivery
    only; a channel failure never breaks the store.
    """

    def __init__(
        self,
        repo: NotificationRepository,
        prefs: NotificationPreferencesRepository,
        channels: Sequence[NotificationChannelPort] = (),
    ) -> None:
        self._repo = repo
        self._prefs = prefs
        self._channels = tuple(channels)

    async def notify(self, notification: Notification) -> None:
        await self._repo.add(notification)
        if not self._channels:
            return
        prefs = await self._prefs.get(
            notification.tenant_id, notification.recipient_id
        ) or NotificationPreferences.defaults(
            notification.tenant_id, notification.recipient_id
        )
        if not prefs.kind_enabled(notification.kind):
            return
        for channel in self._channels:
            if prefs.channel_enabled(channel.channel):
                await self._deliver(channel, notification)

    async def _deliver(
        self, channel: NotificationChannelPort, notification: Notification
    ) -> None:
        try:
            # The recipient's email is not resolved here (the recipient may be a
            # mentioned teammate, not the caller); email-style channels that need
            # it can look it up. The webhook channel does not use it.
            await channel.send(notification, recipient_email=None)
        except Exception:  # a channel failure must never break the in-app store
            pass
