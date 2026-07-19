"""Collection date reminders (collections-reminders spec).

A scheduled cross-tenant sweep: for each date property that carries a reminder
lead time, notify a row's creator once when the row's date, minus the lead, has
been reached. De-dup is keyed by (row, property, date value) so the reminder
fires at most once per value and re-arms when the date is changed.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from cyberarche.application.ports.collections import (
    CollectionRepository,
    ReminderStateRepository,
)
from cyberarche.application.ports.repositories import DocumentRepository
from cyberarche.application.ports.telemetry import IdPort
from cyberarche.application.use_cases.notifications import NotificationDispatcher
from cyberarche.domain.collections import Collection, PropertyDef, PropertyType
from cyberarche.domain.documents import Document
from cyberarche.domain.ids import NotificationId
from cyberarche.domain.notifications import Notification

logger = logging.getLogger(__name__)


class CollectionReminderUseCases:
    """The scheduled job that fires date-property reminders. A single bad row or
    collection is logged and skipped; it never aborts the sweep (mirroring the
    digest's tolerance)."""

    def __init__(
        self,
        collections: CollectionRepository,
        documents_repo: DocumentRepository,
        reminders: ReminderStateRepository,
        dispatcher: NotificationDispatcher,
        ids: IdPort,
    ) -> None:
        self._collections = collections
        self._documents_repo = documents_repo
        self._reminders = reminders
        self._dispatcher = dispatcher
        self._ids = ids

    async def run_due(self, now: datetime) -> int:
        """Fire every armed, due, not-yet-sent reminder. Returns the count sent."""
        sent = 0
        for collection in await self._collections.list_all():
            try:
                sent += await self._sweep_collection(collection, now)
            except Exception:  # a bad collection must never abort the sweep
                logger.exception("reminder sweep failed for collection %s", collection.id)
        return sent

    async def _sweep_collection(self, collection: Collection, now: datetime) -> int:
        props = _reminder_props(collection)
        if not props:
            return 0
        rows = await self._documents_repo.list_by_collection(
            collection.tenant_id, collection.id
        )
        sent = 0
        for row in rows:
            sent += await self._sweep_row(collection, row, props, now)
        return sent

    async def _sweep_row(
        self,
        collection: Collection,
        row: Document,
        props: list[PropertyDef],
        now: datetime,
    ) -> int:
        sent = 0
        for prop in props:
            try:
                if await self._maybe_fire(collection, row, prop, now):
                    sent += 1
            except Exception:  # a bad row must never abort the sweep
                logger.exception("reminder failed for row %s prop %s", row.id, prop.id)
        return sent

    async def _maybe_fire(
        self,
        collection: Collection,
        row: Document,
        prop: PropertyDef,
        now: datetime,
    ) -> bool:
        value = row.properties.get(prop.id)
        if value is None or value == "":
            return False
        date = _parse_date(value)
        if date is None:
            return False
        fire_at = date - timedelta(minutes=prop.reminder_minutes)
        if fire_at > now:
            return False
        if await self._reminders.was_reminded(row.id, prop.id, str(value)):
            return False
        await self._dispatcher.notify(self._build(collection, row, prop, now))
        await self._reminders.mark_reminded(row.id, prop.id, str(value))
        return True

    def _build(
        self,
        collection: Collection,
        row: Document,
        prop: PropertyDef,
        now: datetime,
    ) -> Notification:
        title = row.title or "Untitled"
        return Notification(
            id=NotificationId(self._ids.new_id()),
            tenant_id=collection.tenant_id,
            recipient_id=row.created_by,
            kind="reminder",
            actor_id=row.created_by,
            document_id=row.id,
            comment_id=None,
            snippet=f"Reminder: '{prop.name}' for '{title}' is due",
            created_at=now,
        )


def _reminder_props(collection: Collection) -> list[PropertyDef]:
    """The date properties on a collection that carry a reminder lead time."""
    return [
        p
        for p in collection.properties
        if p.type == PropertyType.DATE and p.reminder_minutes >= 0
    ]


def _parse_date(value: object) -> datetime | None:
    """Parse an ISO date/timestamp string to an aware datetime, or None if it is
    unparseable. A date-only or naive value is assumed to be UTC."""
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
