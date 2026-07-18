"""Notification use cases (notifications spec): a user's own inbox, their
delivery preferences, and the dispatcher that stores + fans out a notification."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

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
        # upsert replaces the row, so carry last_digest_at forward from any
        # existing prefs (don't clobber the digest cadence). Capture the
        # caller's verified email so the scheduled digest can reach them.
        existing = await self._prefs.get(caller.tenant_id, caller.user_id)
        prefs = NotificationPreferences(
            tenant_id=caller.tenant_id,
            user_id=caller.user_id,
            email_enabled=email_enabled,
            push_enabled=push_enabled,
            mentions_enabled=mentions_enabled,
            agent_results_enabled=agent_results_enabled,
            email=caller.email,
            last_digest_at=existing.last_digest_at if existing else None,
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


def _digest_snippet(items: Sequence[Notification]) -> str:
    """A human summary line plus up to ~10 of the unread item snippets."""
    lines = [f"You have {len(items)} unread notifications"]
    lines.extend(item.snippet for item in items[:10])
    return "\n".join(lines)


class NotificationDigestUseCases:
    """The scheduled job that aggregates each email-enabled user's unread
    notifications into one summary and delivers it through the configured
    channels. It never alters the in-app read state; a channel failure never
    breaks the run (each delivery swallows exceptions, mirroring the
    dispatcher)."""

    def __init__(
        self,
        repo: NotificationRepository,
        prefs: NotificationPreferencesRepository,
        channels: Sequence[NotificationChannelPort] = (),
        *,
        min_interval_seconds: int,
    ) -> None:
        self._repo = repo
        self._prefs = prefs
        self._channels = tuple(channels)
        self._min_interval_seconds = min_interval_seconds

    async def run_due(self, now: datetime) -> int:
        """Send a digest to every eligible user whose interval has elapsed and
        who has qualifying unread notifications. Returns the number sent."""
        if not self._channels:
            return 0
        sent = 0
        for pref in await self._prefs.list_email_recipients():
            if await self._run_for_user(pref, now):
                sent += 1
        return sent

    async def _run_for_user(
        self, pref: NotificationPreferences, now: datetime
    ) -> bool:
        if self._within_interval(pref, now):
            return False
        items = await self._repo.unread_since(
            pref.tenant_id, pref.user_id, since=pref.last_digest_at
        )
        if not items:
            return False
        digest = self._build_digest(pref, items, now)
        if not await self._deliver_all(pref, digest):
            return False  # no enabled channel for this user — nothing attempted
        await self._prefs.mark_digested(pref.tenant_id, pref.user_id, now)
        return True

    def _within_interval(
        self, pref: NotificationPreferences, now: datetime
    ) -> bool:
        if pref.last_digest_at is None:
            return False
        elapsed = (now - pref.last_digest_at).total_seconds()
        return elapsed < self._min_interval_seconds

    def _build_digest(
        self, pref: NotificationPreferences, items: Sequence[Notification], now: datetime
    ) -> Notification:
        return Notification(
            id=NotificationId(uuid.uuid4().hex),
            tenant_id=pref.tenant_id,
            recipient_id=pref.user_id,
            kind="digest",
            actor_id=pref.user_id,
            document_id=None,
            comment_id=None,
            snippet=_digest_snippet(items),
            created_at=now,
        )

    async def _deliver_all(
        self, pref: NotificationPreferences, digest: Notification
    ) -> bool:
        """Deliver to each enabled channel; returns whether any was attempted."""
        attempted = False
        for channel in self._channels:
            if pref.channel_enabled(channel.channel):
                await self._deliver(channel, digest, pref.email)
                attempted = True
        return attempted

    async def _deliver(
        self, channel: NotificationChannelPort, digest: Notification, email: str | None
    ) -> None:
        try:
            await channel.send(digest, recipient_email=email)
        except Exception:  # a channel failure must never break the run
            pass
