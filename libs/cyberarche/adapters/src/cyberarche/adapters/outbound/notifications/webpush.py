"""NotificationChannelPort adapter that delivers a notification to each of the
recipient's browser Web Push subscriptions, encrypted per RFC 8291 (VAPID).

Built only when VAPID keys are configured; otherwise the channel is absent and
push delivery is a no-op. pywebpush's `webpush()` is synchronous, so it is run
off the event loop via `asyncio.to_thread`. A subscription the push service has
expired (404/410) is pruned; any other single-subscription failure is swallowed
so it never aborts delivery to the recipient's other devices (mirroring the
dispatcher's channel-failure tolerance)."""

from __future__ import annotations

import asyncio
import json
import logging

from pywebpush import WebPushException, webpush

from cyberarche.application.ports.notifications import PushSubscriptionRepository
from cyberarche.domain.notifications import Notification
from cyberarche.domain.push import PushSubscription

logger = logging.getLogger(__name__)

_TITLES = {
    "mention": "New mention",
    "agent_task": "Agent result",
    "digest": "Notification digest",
}


class WebPushNotificationChannel:
    channel = "push"

    def __init__(
        self,
        subscriptions: PushSubscriptionRepository,
        *,
        private_key: str,
        subject: str,
    ) -> None:
        self._subscriptions = subscriptions
        self._private_key = private_key
        self._subject = subject

    async def send(
        self, notification: Notification, *, recipient_email: str | None = None
    ) -> None:
        subs = await self._subscriptions.list_for_user(
            notification.tenant_id, notification.recipient_id
        )
        payload = json.dumps(
            {
                "title": _TITLES.get(notification.kind, "Notification"),
                "body": notification.snippet,
                "kind": notification.kind,
                "document_id": str(notification.document_id)
                if notification.document_id
                else None,
            }
        )
        for sub in subs:
            await self._deliver_one(sub, payload)

    async def _deliver_one(self, sub: PushSubscription, payload: str) -> None:
        subscription_info = {
            "endpoint": sub.endpoint,
            "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
        }
        try:
            await asyncio.to_thread(
                webpush,
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=self._private_key,
                vapid_claims={"sub": self._subject},
            )
        except WebPushException as exc:
            if exc.response is not None and exc.response.status_code in (404, 410):
                await self._subscriptions.remove_by_endpoint(sub.endpoint)
            else:
                logger.warning("web push delivery failed: %s", exc)
        except Exception as exc:  # a single bad subscription must not abort the rest
            logger.warning("web push delivery error: %s", exc)
