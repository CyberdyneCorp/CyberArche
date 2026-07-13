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
