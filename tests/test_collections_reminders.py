"""collections-reminders: the scheduled date-property reminder sweep.

The sweep notifies a row's creator once when a date property's value, minus its
reminder lead time, has been reached — de-duped per (row, property, date value)
so a changed date re-arms it. Postgres round-trips are asserted with a FakePool,
mirroring test_postgres_collections.py.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace

from cyberarche.adapters.outbound.postgres.collection_reminders import (
    PostgresReminderStateRepository,
)
from cyberarche.application.testing.fakes import (
    InMemoryCollectionRepository,
    InMemoryDocumentRepository,
    InMemoryNotificationPreferencesRepository,
    InMemoryNotificationRepository,
    InMemoryReminderStateRepository,
    SequentialIds,
)
from cyberarche.application.use_cases.collection_reminders import CollectionReminderUseCases
from cyberarche.application.use_cases.notifications import NotificationDispatcher
from cyberarche.domain.collections import Collection, PropertyDef, PropertyType
from cyberarche.domain.documents import Document
from cyberarche.domain.ids import (
    CollectionId,
    DocumentId,
    TenantId,
    UserId,
    WorkspaceId,
)

# 2026-07-19 noon: the sweep's "now".
NOW = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)


def date_prop(reminder_minutes: int, *, pid: str = "due", name: str = "Due") -> PropertyDef:
    return PropertyDef(
        id=pid, name=name, type=PropertyType.DATE, reminder_minutes=reminder_minutes
    )


def make_collection(props, *, tenant: str = "acme", cid: str = "col-1") -> Collection:
    return Collection(
        id=CollectionId(cid),
        tenant_id=TenantId(tenant),
        workspace_id=WorkspaceId("ws-1"),
        name="Tasks",
        properties=tuple(props),
        views=(),
        created_at=NOW,
    )


def make_row(
    rid: str,
    *,
    properties: dict,
    tenant: str = "acme",
    cid: str = "col-1",
    created_by: str = "alice",
    title: str = "First",
) -> Document:
    doc = Document.create(
        id=DocumentId(rid),
        workspace_id=WorkspaceId("ws-1"),
        tenant_id=TenantId(tenant),
        title=title,
        parent_id=None,
        position=0,
        created_by=UserId(created_by),
        created_at=NOW,
    )
    return replace(doc, collection_id=CollectionId(cid), properties=properties)


def build(collections, rows, *, dispatcher=None):
    """Wire the use case over in-memory fakes. Returns a namespace of the parts a
    test may need to inspect or mutate."""
    coll_repo = InMemoryCollectionRepository()
    doc_repo = InMemoryDocumentRepository()
    reminders = InMemoryReminderStateRepository()
    notifications = InMemoryNotificationRepository()
    prefs = InMemoryNotificationPreferencesRepository()
    dispatcher = dispatcher or NotificationDispatcher(notifications, prefs)
    return SimpleNamespace(
        uc=CollectionReminderUseCases(
            coll_repo, doc_repo, reminders, dispatcher, SequentialIds()
        ),
        coll_repo=coll_repo,
        doc_repo=doc_repo,
        reminders=reminders,
        notifications=notifications,
        prefs=prefs,
        _seed=(collections, rows),
    )


async def seed(h) -> None:
    collections, rows = h._seed
    for collection in collections:
        await h.coll_repo.add(collection)
    for row in rows:
        await h.doc_repo.add(row)


async def inbox(h, user: str, tenant: str = "acme"):
    return await h.notifications.list_for_user(TenantId(tenant), UserId(user))


# ---- firing / de-dup / re-arm ----------------------------------------------


async def test_fires_for_creator_marks_reminded_and_does_not_repeat():
    # 1440 min (1 day) before 2026-07-20 => fire_at 2026-07-19 00:00 <= NOW.
    h = build([make_collection([date_prop(1440)])], [make_row("r1", properties={"due": "2026-07-20"})])
    await seed(h)

    assert await h.uc.run_due(NOW) == 1
    sent = await inbox(h, "alice")
    assert len(sent) == 1
    assert sent[0].kind == "reminder"
    assert sent[0].recipient_id == UserId("alice")
    assert sent[0].actor_id == UserId("alice")
    assert sent[0].document_id == DocumentId("r1")
    assert "Due" in sent[0].snippet and "First" in sent[0].snippet
    assert await h.reminders.was_reminded("r1", "due", "2026-07-20") is True

    # A second sweep for the same value sends nothing more.
    assert await h.uc.run_due(NOW) == 0
    assert len(await inbox(h, "alice")) == 1


async def test_changing_the_date_re_arms_the_reminder():
    h = build(
        [make_collection([date_prop(0)])],
        [make_row("r1", properties={"due": "2026-07-19T09:00:00+00:00"})],
    )
    await seed(h)
    assert await h.uc.run_due(NOW) == 1
    assert await h.uc.run_due(NOW) == 0  # already reminded for this value

    # Change the row's date to a new (still past-due) value => re-arm.
    await h.doc_repo.update(
        replace(
            await h.doc_repo.get(TenantId("acme"), DocumentId("r1")),
            properties={"due": "2026-07-19T10:00:00+00:00"},
        )
    )
    assert await h.uc.run_due(NOW) == 1
    assert len(await inbox(h, "alice")) == 2


async def test_does_not_fire_before_the_lead_time():
    # 60 min before 2026-07-25 12:00 => fire_at 11:00 that day, well after NOW.
    h = build(
        [make_collection([date_prop(60)])],
        [make_row("r1", properties={"due": "2026-07-25T12:00:00+00:00"})],
    )
    await seed(h)
    assert await h.uc.run_due(NOW) == 0
    assert await inbox(h, "alice") == []


# ---- eligibility -----------------------------------------------------------


async def test_only_date_props_with_a_reminder_are_considered():
    # A date property with -1 never fires; a non-date property's reminder is inert.
    collection = make_collection(
        [
            date_prop(-1, pid="d"),
            PropertyDef(id="t", name="T", type=PropertyType.TEXT, reminder_minutes=0),
        ]
    )
    h = build(
        [collection],
        [make_row("r1", properties={"d": "2026-07-01", "t": "2026-07-01"})],
    )
    await seed(h)
    assert await h.uc.run_due(NOW) == 0
    assert await inbox(h, "alice") == []


async def test_empty_and_unparseable_values_are_skipped_and_a_good_row_still_fires():
    h = build(
        [make_collection([date_prop(0)])],
        [
            make_row("bad", properties={"due": "not-a-date"}),
            make_row("empty", properties={"due": ""}),
            make_row("missing", properties={}),
            make_row("good", created_by="bob", properties={"due": "2026-07-19T00:00:00+00:00"}),
        ],
    )
    await seed(h)
    assert await h.uc.run_due(NOW) == 1
    assert len(await inbox(h, "bob")) == 1
    assert await inbox(h, "alice") == []


# ---- robustness: a bad row/collection must not abort the sweep -------------


class _RaisingDispatcher:
    """Raises when notifying a specific recipient; delegates otherwise."""

    def __init__(self, inner: NotificationDispatcher, fail_for: UserId) -> None:
        self._inner = inner
        self._fail_for = fail_for

    async def notify(self, notification) -> None:
        if notification.recipient_id == self._fail_for:
            raise RuntimeError("boom")
        await self._inner.notify(notification)


async def test_a_dispatch_error_on_one_row_does_not_abort_the_sweep():
    notifications = InMemoryNotificationRepository()
    prefs = InMemoryNotificationPreferencesRepository()
    dispatcher = _RaisingDispatcher(
        NotificationDispatcher(notifications, prefs), UserId("alice")
    )
    h = build(
        [make_collection([date_prop(0)])],
        [
            make_row("r-bad", created_by="alice", properties={"due": "2026-07-19T00:00:00+00:00"}),
            make_row("r-good", created_by="bob", properties={"due": "2026-07-19T00:00:00+00:00"}),
        ],
        dispatcher=dispatcher,
    )
    h.notifications = notifications  # inspect the delegated store
    await seed(h)

    # The good row still fires even though the bad row's dispatch raised.
    assert await h.uc.run_due(NOW) == 1
    assert await h.reminders.was_reminded("r-good", "due", "2026-07-19T00:00:00+00:00") is True
    # The bad row was not marked (its notify failed), so it can retry next sweep.
    assert await h.reminders.was_reminded("r-bad", "due", "2026-07-19T00:00:00+00:00") is False


class _BrokenDocRepo(InMemoryDocumentRepository):
    """Raises when listing a specific collection's rows."""

    def __init__(self, break_collection: CollectionId) -> None:
        super().__init__()
        self._break = break_collection

    async def list_by_collection(self, tenant_id, collection_id):
        if collection_id == self._break:
            raise RuntimeError("db down")
        return await super().list_by_collection(tenant_id, collection_id)


async def test_a_broken_collection_does_not_abort_the_sweep():
    coll_repo = InMemoryCollectionRepository()
    await coll_repo.add(make_collection([date_prop(0)], cid="col-broken"))
    await coll_repo.add(make_collection([date_prop(0)], cid="col-good"))
    doc_repo = _BrokenDocRepo(CollectionId("col-broken"))
    await doc_repo.add(make_row("r1", cid="col-good", properties={"due": "2026-07-19T00:00:00+00:00"}))
    notifications = InMemoryNotificationRepository()
    dispatcher = NotificationDispatcher(
        notifications, InMemoryNotificationPreferencesRepository()
    )
    uc = CollectionReminderUseCases(
        coll_repo, doc_repo, InMemoryReminderStateRepository(), dispatcher, SequentialIds()
    )

    # The broken collection is logged and skipped; the good one still fires.
    assert await uc.run_due(NOW) == 1
    assert len(await notifications.list_for_user(TenantId("acme"), UserId("alice"))) == 1


# ---- postgres reminder-state repo round-trip -------------------------------


class FakeReminderPool:
    """Records SQL and mimics the collection_reminders upsert/select."""

    def __init__(self) -> None:
        self.store: dict[tuple[str, str], str] = {}
        self.calls: list[tuple[str, tuple]] = []

    async def fetchval(self, query: str, *args: object):
        self.calls.append((" ".join(query.split()), args))
        return self.store.get((args[0], args[1]))

    async def execute(self, query: str, *args: object) -> None:
        self.calls.append((" ".join(query.split()), args))
        self.store[(args[0], args[1])] = args[2]


async def test_postgres_reminder_state_round_trips_and_re_arms():
    repo = PostgresReminderStateRepository(FakeReminderPool())

    assert await repo.was_reminded("d1", "p1", "2026-07-20") is False
    await repo.mark_reminded("d1", "p1", "2026-07-20")
    assert await repo.was_reminded("d1", "p1", "2026-07-20") is True

    # A different date value is treated as not-yet-reminded (re-arm), and the
    # upsert replaces the stored value.
    assert await repo.was_reminded("d1", "p1", "2026-07-21") is False
    await repo.mark_reminded("d1", "p1", "2026-07-21")
    assert await repo.was_reminded("d1", "p1", "2026-07-21") is True
    assert await repo.was_reminded("d1", "p1", "2026-07-20") is False


async def test_postgres_reminder_state_uses_expected_sql():
    pool = FakeReminderPool()
    repo = PostgresReminderStateRepository(pool)
    await repo.mark_reminded("d1", "p1", "v1")
    await repo.was_reminded("d1", "p1", "v1")

    insert = pool.calls[0][0]
    assert insert.startswith("INSERT INTO collection_reminders")
    assert "ON CONFLICT (document_id, property_id) DO UPDATE" in insert
    select = pool.calls[1][0]
    assert select.startswith("SELECT reminded_value FROM collection_reminders")
