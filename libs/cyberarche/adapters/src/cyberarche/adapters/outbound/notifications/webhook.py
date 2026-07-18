"""NotificationChannelPort adapter that POSTs a notification to a configured
webhook URL (Slack-style incoming webhook, or any HTTP receiver). Built only
when `notification_webhook_url` is configured; otherwise the channel is absent
and delivery is a no-op."""

from __future__ import annotations

import httpx

from cyberarche.domain.notifications import Notification


class WebhookNotificationChannel:
    channel = "webhook"

    def __init__(self, url: str, http: httpx.AsyncClient) -> None:
        self._url = url
        self._http = http

    async def send(
        self, notification: Notification, *, recipient_email: str | None = None
    ) -> None:
        await self._http.post(
            self._url,
            json={
                "kind": notification.kind,
                "snippet": notification.snippet,
                "actor": str(notification.actor_id),
                "document_id": str(notification.document_id)
                if notification.document_id
                else None,
            },
        )
