"""Notification endpoints (notifications spec): the caller's own inbox."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from cyberarche.adapters.inbound.http.dependencies import Caller, Cases
from cyberarche.domain.ids import NotificationId
from cyberarche.domain.notifications import Notification

router = APIRouter(tags=["notifications"])


class NotificationResponse(BaseModel):
    id: str
    kind: str
    actor_id: str
    document_id: str | None
    comment_id: str | None
    snippet: str
    read: bool
    created_at: datetime

    @staticmethod
    def from_domain(n: Notification) -> "NotificationResponse":
        return NotificationResponse(
            id=n.id,
            kind=n.kind,
            actor_id=n.actor_id,
            document_id=n.document_id,
            comment_id=n.comment_id,
            snippet=n.snippet,
            read=n.read,
            created_at=n.created_at,
        )


@router.get("/api/v1/notifications")
async def list_notifications(cases: Cases, caller: Caller) -> list[NotificationResponse]:
    items = await cases.notifications.list(caller)
    return [NotificationResponse.from_domain(n) for n in items]


@router.get("/api/v1/notifications/unread-count")
async def unread_count(cases: Cases, caller: Caller) -> dict:
    return {"count": await cases.notifications.unread_count(caller)}


@router.post("/api/v1/notifications/{notification_id}/read", status_code=204)
async def mark_read(notification_id: str, cases: Cases, caller: Caller) -> None:
    await cases.notifications.mark_read(caller, NotificationId(notification_id))


@router.post("/api/v1/notifications/read-all", status_code=204)
async def mark_all_read(cases: Cases, caller: Caller) -> None:
    await cases.notifications.mark_all_read(caller)
