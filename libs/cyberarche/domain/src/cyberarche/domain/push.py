"""Web push (notifications spec): a browser's Web Push subscription for a user.

The browser mints one of these per device when the user enables push; the
`endpoint` (the push service URL) is its natural unique key. The keys are the
subscription's public P-256 ECDH key (`p256dh`) and auth secret (`auth`) used to
encrypt the payload (RFC 8291)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from cyberarche.domain.ids import TenantId, UserId


@dataclass(frozen=True, slots=True)
class PushSubscription:
    tenant_id: TenantId
    user_id: UserId
    endpoint: str
    p256dh: str
    auth: str
    created_at: datetime
