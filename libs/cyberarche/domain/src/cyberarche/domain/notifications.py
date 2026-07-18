"""Notifications (notifications spec): a per-user inbox entry."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from cyberarche.domain.ids import (
    DocumentId,
    NotificationId,
    TenantId,
    UserId,
)


@dataclass(frozen=True, slots=True)
class Notification:
    id: NotificationId
    tenant_id: TenantId
    recipient_id: UserId
    kind: str  # 'mention' | 'agent_task'
    actor_id: UserId
    document_id: DocumentId | None
    comment_id: str | None
    snippet: str
    created_at: datetime
    read: bool = False


@dataclass(frozen=True, slots=True)
class NotificationPreferences:
    """A user's notification preferences. In-app is always on (not a field); the
    other toggles gate additional delivery channels and per-kind delivery. The
    defaults preserve today's behaviour: in-app + mentions on, email/push off."""

    tenant_id: TenantId
    user_id: UserId
    email_enabled: bool = False
    push_enabled: bool = False
    mentions_enabled: bool = True
    agent_results_enabled: bool = True

    @classmethod
    def defaults(
        cls, tenant_id: TenantId, user_id: UserId
    ) -> "NotificationPreferences":
        return cls(tenant_id=tenant_id, user_id=user_id)

    def kind_enabled(self, kind: str) -> bool:
        """Whether this kind should be delivered to external channels. Unknown
        kinds are allowed through; in-app storage is unaffected either way."""
        if kind == "mention":
            return self.mentions_enabled
        if kind == "agent_task":
            return self.agent_results_enabled
        return True

    def channel_enabled(self, channel: str) -> bool:
        """Whether this channel is enabled by the user. 'push' rides the push
        toggle; email and any external webhook delivery ride the email toggle."""
        if channel == "push":
            return self.push_enabled
        return self.email_enabled
