"""Notification HTTP endpoints (notifications spec): the caller's own inbox."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cyberarche.api.bootstrap import create_app
from cyberarche.api.config import Settings
from cyberarche.application.ports.identity import Claims
from cyberarche.application.testing.fakes import StaticTokenPort

# Two users in the same tenant, so a mention can land in a teammate's inbox.
TOKENS = {
    "alice-token": Claims(subject="alice", tenant_id="acme", email="alice@acme.test"),
    "bob-token": Claims(subject="bob", tenant_id="acme", email="bob@acme.test"),
}


@pytest.fixture
def api() -> TestClient:
    app = create_app(
        Settings(
            backend="memory",
            auth_base_url="",
            rag_base_url="",
            rag_webhook_secret="hook-secret",
        ),
        token_port=StaticTokenPort(dict(TOKENS)),
    )
    with TestClient(app) as client:
        yield client


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def mention_bob(api: TestClient, body: str = "hey @[bob], look") -> tuple[str, str]:
    """Alice mentions Bob (a workspace member) in a comment; returns
    (document_id, comment_id) — the only inbound path that fills an inbox."""
    headers = auth("alice-token")
    workspace = api.post("/api/v1/workspaces", json={"name": "WS"}, headers=headers).json()
    api.post(
        f"/api/v1/workspaces/{workspace['id']}/invites",
        json={"user_id": "bob", "role": "editor"},
        headers=headers,
    )
    document = api.post(
        "/api/v1/documents",
        json={"workspace_id": workspace["id"], "title": "Doc"},
        headers=headers,
    ).json()
    comment = api.post(
        f"/api/v1/documents/{document['id']}/comments",
        json={"block_id": "b1", "body": body},
        headers=headers,
    ).json()
    return document["id"], comment["id"]


def test_mention_appears_in_recipients_inbox_over_http(api):
    document_id, comment_id = mention_bob(api)

    inbox = api.get("/api/v1/notifications", headers=auth("bob-token"))
    assert inbox.status_code == 200
    (item,) = inbox.json()
    assert item["kind"] == "mention"
    assert item["actor_id"] == "alice"
    assert item["document_id"] == document_id
    assert item["comment_id"] == comment_id
    assert "@[bob]" in item["snippet"]
    assert item["read"] is False
    assert item["created_at"]


def test_inbox_and_unread_count_are_scoped_to_the_caller(api):
    mention_bob(api)

    # The mention author sees nothing in their own inbox.
    assert api.get("/api/v1/notifications", headers=auth("alice-token")).json() == []
    count = api.get("/api/v1/notifications/unread-count", headers=auth("alice-token"))
    assert count.json() == {"count": 0}
    bob_count = api.get("/api/v1/notifications/unread-count", headers=auth("bob-token"))
    assert bob_count.json() == {"count": 1}


def test_mark_read_over_http_clears_unread(api):
    mention_bob(api)
    (item,) = api.get("/api/v1/notifications", headers=auth("bob-token")).json()

    response = api.post(
        f"/api/v1/notifications/{item['id']}/read", headers=auth("bob-token")
    )
    assert response.status_code == 204

    count = api.get("/api/v1/notifications/unread-count", headers=auth("bob-token"))
    assert count.json() == {"count": 0}
    (item,) = api.get("/api/v1/notifications", headers=auth("bob-token")).json()
    assert item["read"] is True


def test_mark_all_read_over_http(api):
    mention_bob(api, body="first @[bob]")
    mention_bob(api, body="second @[bob]")
    count = api.get("/api/v1/notifications/unread-count", headers=auth("bob-token"))
    assert count.json() == {"count": 2}

    response = api.post("/api/v1/notifications/read-all", headers=auth("bob-token"))
    assert response.status_code == 204

    count = api.get("/api/v1/notifications/unread-count", headers=auth("bob-token"))
    assert count.json() == {"count": 0}
    assert all(
        n["read"] for n in api.get("/api/v1/notifications", headers=auth("bob-token")).json()
    )


def test_marking_someone_elses_notification_is_a_noop(api):
    mention_bob(api)
    (item,) = api.get("/api/v1/notifications", headers=auth("bob-token")).json()

    # Alice cannot mark Bob's notification read — 204, but nothing changes.
    response = api.post(
        f"/api/v1/notifications/{item['id']}/read", headers=auth("alice-token")
    )
    assert response.status_code == 204
    count = api.get("/api/v1/notifications/unread-count", headers=auth("bob-token"))
    assert count.json() == {"count": 1}


def test_notification_endpoints_require_auth(api):
    assert api.get("/api/v1/notifications").status_code == 401
    assert api.get("/api/v1/notifications/unread-count").status_code == 401
    assert api.post("/api/v1/notifications/n-1/read").status_code == 401
    assert api.post("/api/v1/notifications/read-all").status_code == 401


# --- PostgresNotificationRepository (postgres/notifications.py) --------------
#
# Unit tests over a stubbed asyncpg pool: assert the SQL shape, the bound
# parameters (tenant + recipient scoping), and the row->Notification mapping.

from datetime import UTC, datetime

from cyberarche.adapters.outbound.postgres.notifications import (
    PostgresNotificationRepository,
)
from cyberarche.domain.ids import DocumentId, NotificationId, TenantId, UserId
from cyberarche.domain.notifications import Notification

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class FakePool:
    """Stands in for asyncpg.Pool: records queries, replays canned rows."""

    def __init__(self, *, rows: list | None = None, value: int | None = None) -> None:
        self.rows = rows or []
        self.value = value
        self.calls: list[tuple[str, tuple]] = []

    async def execute(self, query: str, *args: object) -> None:
        self.calls.append((" ".join(query.split()), args))

    async def fetch(self, query: str, *args: object) -> list:
        self.calls.append((" ".join(query.split()), args))
        return self.rows

    async def fetchval(self, query: str, *args: object) -> int | None:
        self.calls.append((" ".join(query.split()), args))
        return self.value


def notification_row(**overrides: object) -> dict:
    row = {
        "id": "n-1",
        "tenant_id": "acme",
        "recipient_id": "bob",
        "kind": "mention",
        "actor_id": "alice",
        "document_id": "d-1",
        "comment_id": "c-1",
        "snippet": "hey @[bob]",
        "created_at": NOW,
        "read": False,
    }
    row.update(overrides)
    return row


def make_notification(**overrides: object) -> Notification:
    fields: dict = dict(
        id=NotificationId("n-1"),
        tenant_id=TenantId("acme"),
        recipient_id=UserId("bob"),
        kind="mention",
        actor_id=UserId("alice"),
        document_id=DocumentId("d-1"),
        comment_id="c-1",
        snippet="hey @[bob]",
        created_at=NOW,
        read=False,
    )
    fields.update(overrides)
    return Notification(**fields)


async def test_postgres_add_binds_every_column():
    pool = FakePool()
    await PostgresNotificationRepository(pool).add(make_notification())

    query, args = pool.calls[0]
    assert query.startswith("INSERT INTO notifications")
    assert args == (
        "n-1", "acme", "bob", "mention", "alice", "d-1",
        "c-1", "hey @[bob]", False, NOW,
    )


async def test_postgres_list_for_user_maps_rows_with_default_limit():
    pool = FakePool(rows=[notification_row(), notification_row(id="n-2", read=True)])
    listed = await PostgresNotificationRepository(pool).list_for_user(
        TenantId("acme"), UserId("bob")
    )

    assert listed[0] == make_notification()
    assert listed[1].id == NotificationId("n-2")
    assert listed[1].read is True
    query, args = pool.calls[0]
    assert "ORDER BY created_at DESC" in query
    assert args == ("acme", "bob", 50)


async def test_postgres_list_for_user_honors_custom_limit():
    pool = FakePool(rows=[])
    await PostgresNotificationRepository(pool).list_for_user(
        TenantId("acme"), UserId("bob"), limit=5
    )

    _, args = pool.calls[0]
    assert args == ("acme", "bob", 5)


async def test_postgres_row_without_document_maps_to_none():
    pool = FakePool(rows=[notification_row(document_id=None, comment_id=None)])
    (item,) = await PostgresNotificationRepository(pool).list_for_user(
        TenantId("acme"), UserId("bob")
    )

    assert item.document_id is None
    assert item.comment_id is None


async def test_postgres_unread_count_scopes_by_tenant_and_recipient():
    pool = FakePool(value=3)
    count = await PostgresNotificationRepository(pool).unread_count(
        TenantId("acme"), UserId("bob")
    )

    assert count == 3
    query, args = pool.calls[0]
    assert "read = FALSE" in query
    assert args == ("acme", "bob")


async def test_postgres_mark_read_binds_id_tenant_and_recipient():
    pool = FakePool()
    await PostgresNotificationRepository(pool).mark_read(
        TenantId("acme"), UserId("bob"), NotificationId("n-1")
    )

    query, args = pool.calls[0]
    assert query.startswith("UPDATE notifications SET read = TRUE")
    assert args == ("n-1", "acme", "bob")


async def test_postgres_mark_all_read_binds_tenant_and_recipient():
    pool = FakePool()
    await PostgresNotificationRepository(pool).mark_all_read(
        TenantId("acme"), UserId("bob")
    )

    query, args = pool.calls[0]
    assert query.startswith("UPDATE notifications SET read = TRUE")
    assert "read = FALSE" in query
    assert args == ("acme", "bob")


# --- Preferences + dispatcher (domain + use case + dispatch) ----------------

from cyberarche.application.kernel import CallerContext
from cyberarche.application.testing.fakes import (
    InMemoryNotificationPreferencesRepository,
    InMemoryNotificationRepository,
)
from cyberarche.application.use_cases.notifications import (
    NotificationDispatcher,
    NotificationPreferencesUseCases,
)
from cyberarche.domain.notifications import NotificationPreferences

BOB = CallerContext(user_id=UserId("bob"), tenant_id=TenantId("acme"))


class RecordingChannel:
    """NotificationChannelPort fake: records what it was asked to deliver."""

    def __init__(self, channel: str = "webhook") -> None:
        self.channel = channel
        self.sent: list[Notification] = []

    async def send(self, notification, *, recipient_email=None) -> None:
        self.sent.append(notification)


class BrokenChannel:
    channel = "webhook"

    def __init__(self) -> None:
        self.attempts = 0

    async def send(self, notification, *, recipient_email=None) -> None:
        self.attempts += 1
        raise RuntimeError("channel is down")


async def test_default_preferences_have_in_app_and_mentions_on():
    prefs = NotificationPreferencesUseCases(
        InMemoryNotificationPreferencesRepository()
    )

    resolved = await prefs.get(BOB)

    assert resolved.mentions_enabled is True
    assert resolved.agent_results_enabled is True
    assert resolved.email_enabled is False
    assert resolved.push_enabled is False
    # In-app is always on — it is not a stored field.
    assert not hasattr(resolved, "in_app_enabled")


async def test_update_preferences_persists():
    prefs = NotificationPreferencesUseCases(
        InMemoryNotificationPreferencesRepository()
    )

    await prefs.update(
        BOB,
        email_enabled=True,
        push_enabled=False,
        mentions_enabled=False,
        agent_results_enabled=True,
    )
    resolved = await prefs.get(BOB)

    assert resolved.email_enabled is True
    assert resolved.mentions_enabled is False
    assert resolved.agent_results_enabled is True


async def test_dispatcher_always_stores_in_app_even_without_channels():
    repo = InMemoryNotificationRepository()
    dispatcher = NotificationDispatcher(
        repo, InMemoryNotificationPreferencesRepository()
    )

    await dispatcher.notify(make_notification())

    (stored,) = await repo.list_for_user(TenantId("acme"), UserId("bob"))
    assert stored == make_notification()


async def test_dispatcher_delivers_to_an_enabled_channel():
    repo = InMemoryNotificationRepository()
    prefs = InMemoryNotificationPreferencesRepository()
    await prefs.upsert(
        NotificationPreferences(
            tenant_id=TenantId("acme"), user_id=UserId("bob"), email_enabled=True
        )
    )
    channel = RecordingChannel()
    dispatcher = NotificationDispatcher(repo, prefs, [channel])

    await dispatcher.notify(make_notification())

    assert len(channel.sent) == 1
    # In-app store still happened.
    assert len(await repo.list_for_user(TenantId("acme"), UserId("bob"))) == 1


async def test_dispatcher_skips_a_channel_the_user_disabled():
    repo = InMemoryNotificationRepository()
    prefs = InMemoryNotificationPreferencesRepository()
    # email_enabled defaults to False -> the webhook channel (email toggle) is off.
    channel = RecordingChannel()
    dispatcher = NotificationDispatcher(repo, prefs, [channel])

    await dispatcher.notify(make_notification())

    assert channel.sent == []
    assert len(await repo.list_for_user(TenantId("acme"), UserId("bob"))) == 1


async def test_dispatcher_skips_a_disabled_kind():
    repo = InMemoryNotificationRepository()
    prefs = InMemoryNotificationPreferencesRepository()
    await prefs.upsert(
        NotificationPreferences(
            tenant_id=TenantId("acme"),
            user_id=UserId("bob"),
            email_enabled=True,
            mentions_enabled=False,
        )
    )
    channel = RecordingChannel()
    dispatcher = NotificationDispatcher(repo, prefs, [channel])

    await dispatcher.notify(make_notification(kind="mention"))

    assert channel.sent == []


async def test_unconfigured_channel_is_a_noop_but_still_stored():
    repo = InMemoryNotificationRepository()
    prefs = InMemoryNotificationPreferencesRepository()
    await prefs.upsert(
        NotificationPreferences(
            tenant_id=TenantId("acme"), user_id=UserId("bob"), email_enabled=True
        )
    )
    # No channels configured (empty) — like today's deployment.
    dispatcher = NotificationDispatcher(repo, prefs, [])

    await dispatcher.notify(make_notification())

    assert len(await repo.list_for_user(TenantId("acme"), UserId("bob"))) == 1


async def test_a_channel_that_raises_does_not_break_the_store():
    repo = InMemoryNotificationRepository()
    prefs = InMemoryNotificationPreferencesRepository()
    await prefs.upsert(
        NotificationPreferences(
            tenant_id=TenantId("acme"), user_id=UserId("bob"), email_enabled=True
        )
    )
    channel = BrokenChannel()
    dispatcher = NotificationDispatcher(repo, prefs, [channel])

    # Must not raise.
    await dispatcher.notify(make_notification())

    assert channel.attempts == 1
    assert len(await repo.list_for_user(TenantId("acme"), UserId("bob"))) == 1


# --- Preferences HTTP endpoints ---------------------------------------------


def test_preferences_default_over_http(api):
    prefs = api.get("/api/v1/notification-preferences", headers=auth("bob-token"))
    assert prefs.status_code == 200
    assert prefs.json() == {
        "email_enabled": False,
        "push_enabled": False,
        "mentions_enabled": True,
        "agent_results_enabled": True,
    }


def test_update_preferences_over_http_persists(api):
    body = {
        "email_enabled": True,
        "push_enabled": True,
        "mentions_enabled": False,
        "agent_results_enabled": True,
    }
    updated = api.put(
        "/api/v1/notification-preferences", json=body, headers=auth("bob-token")
    )
    assert updated.status_code == 200
    assert updated.json() == body

    # A fresh read returns the persisted values.
    reread = api.get("/api/v1/notification-preferences", headers=auth("bob-token"))
    assert reread.json() == body


def test_preferences_endpoints_require_auth(api):
    assert api.get("/api/v1/notification-preferences").status_code == 401
    assert api.put("/api/v1/notification-preferences", json={}).status_code == 401


# --- PostgresNotificationPreferencesRepository ------------------------------

from cyberarche.adapters.outbound.postgres.notification_prefs import (
    PostgresNotificationPreferencesRepository,
)


class FakePrefsPool(FakePool):
    """FakePool with fetchrow, for the single-row preferences read."""

    def __init__(self, *, row: dict | None = None) -> None:
        super().__init__()
        self.row = row

    async def fetchrow(self, query: str, *args: object):
        self.calls.append((" ".join(query.split()), args))
        return self.row


async def test_postgres_prefs_get_returns_none_when_absent():
    pool = FakePrefsPool(row=None)
    result = await PostgresNotificationPreferencesRepository(pool).get(
        TenantId("acme"), UserId("bob")
    )

    assert result is None
    _, args = pool.calls[0]
    assert args == ("acme", "bob")


async def test_postgres_prefs_get_maps_row():
    pool = FakePrefsPool(
        row={
            "tenant_id": "acme",
            "user_id": "bob",
            "email_enabled": True,
            "push_enabled": False,
            "mentions_enabled": True,
            "agent_results_enabled": False,
        }
    )
    result = await PostgresNotificationPreferencesRepository(pool).get(
        TenantId("acme"), UserId("bob")
    )

    assert result == NotificationPreferences(
        tenant_id=TenantId("acme"),
        user_id=UserId("bob"),
        email_enabled=True,
        push_enabled=False,
        mentions_enabled=True,
        agent_results_enabled=False,
    )


async def test_postgres_prefs_upsert_binds_every_column():
    pool = FakePrefsPool()
    await PostgresNotificationPreferencesRepository(pool).upsert(
        NotificationPreferences(
            tenant_id=TenantId("acme"),
            user_id=UserId("bob"),
            email_enabled=True,
            push_enabled=True,
            mentions_enabled=False,
            agent_results_enabled=True,
        )
    )

    query, args = pool.calls[0]
    assert query.startswith("INSERT INTO notification_preferences")
    assert "ON CONFLICT (tenant_id, user_id) DO UPDATE" in query
    assert args == ("acme", "bob", True, True, False, True)
