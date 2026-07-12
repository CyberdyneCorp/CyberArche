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
    kind: str  # 'mention'
    actor_id: UserId
    document_id: DocumentId | None
    comment_id: str | None
    snippet: str
    created_at: datetime
    read: bool = False
