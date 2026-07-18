"""Web Push channel + subscriptions (notifications spec): the VAPID push
delivery channel, the caller-scoped subscription use case, the postgres repo,
and the HTTP endpoints."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from pywebpush import WebPushException

from cyberarche.adapters.outbound.notifications import webpush as webpush_module
from cyberarche.adapters.outbound.notifications.webpush import (
    WebPushNotificationChannel,
)
from cyberarche.adapters.outbound.postgres.push_subscriptions import (
    PostgresPushSubscriptionRepository,
)
from cyberarche.api.bootstrap import create_app
from cyberarche.api.config import Settings
from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.identity import Claims
from cyberarche.application.testing.fakes import (
    FixedClock,
    InMemoryPushSubscriptionRepository,
    StaticTokenPort,
)
from cyberarche.application.use_cases.notifications import PushSubscriptionUseCases
from cyberarche.domain.ids import DocumentId, NotificationId, TenantId, UserId
from cyberarche.domain.notifications import Notification
from cyberarche.domain.push import PushSubscription

NOW = datetime(2026, 1, 1, tzinfo=UTC)
BOB = CallerContext(user_id=UserId("bob"), tenant_id=TenantId("acme"))
ALICE = CallerContext(user_id=UserId("alice"), tenant_id=TenantId("acme"))


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


def make_sub(endpoint: str, *, user: str = "bob") -> PushSubscription:
    return PushSubscription(
        tenant_id=TenantId("acme"),
        user_id=UserId(user),
        endpoint=endpoint,
        p256dh=f"p256dh-{endpoint}",
        auth=f"auth-{endpoint}",
        created_at=NOW,
    )


class _Response:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


# --- WebPushNotificationChannel ---------------------------------------------


async def test_channel_delivers_to_every_subscription(monkeypatch):
    repo = InMemoryPushSubscriptionRepository()
    await repo.add(make_sub("https://push.example/a"))
    await repo.add(make_sub("https://push.example/b"))
    calls: list[dict] = []

    def fake_webpush(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(webpush_module, "webpush", fake_webpush)
    channel = WebPushNotificationChannel(
        repo, private_key="priv", subject="mailto:push@x"
    )

    await channel.send(make_notification())

    assert len(calls) == 2
    endpoints = {c["subscription_info"]["endpoint"] for c in calls}
    assert endpoints == {"https://push.example/a", "https://push.example/b"}
    payload = json.loads(calls[0]["data"])
    assert payload == {
        "title": "New mention",
        "body": "hey @[bob]",
        "kind": "mention",
        "document_id": "d-1",
    }
    assert calls[0]["vapid_private_key"] == "priv"
    assert calls[0]["vapid_claims"] == {"sub": "mailto:push@x"}


async def test_channel_prunes_an_expired_subscription_and_continues(monkeypatch):
    repo = InMemoryPushSubscriptionRepository()
    await repo.add(make_sub("https://push.example/gone"))
    await repo.add(make_sub("https://push.example/live"))
    delivered: list[str] = []

    def fake_webpush(**kwargs):
        endpoint = kwargs["subscription_info"]["endpoint"]
        if endpoint.endswith("gone"):
            raise WebPushException("expired", response=_Response(410))
        delivered.append(endpoint)

    monkeypatch.setattr(webpush_module, "webpush", fake_webpush)
    channel = WebPushNotificationChannel(repo, private_key="priv", subject="s")

    await channel.send(make_notification())

    # The live endpoint still received the push.
    assert delivered == ["https://push.example/live"]
    # The expired endpoint was pruned; only the live one remains.
    remaining = await repo.list_for_user(TenantId("acme"), UserId("bob"))
    assert [s.endpoint for s in remaining] == ["https://push.example/live"]


async def test_channel_swallows_other_errors_without_pruning(monkeypatch):
    repo = InMemoryPushSubscriptionRepository()
    await repo.add(make_sub("https://push.example/flaky"))
    await repo.add(make_sub("https://push.example/ok"))
    delivered: list[str] = []

    def fake_webpush(**kwargs):
        endpoint = kwargs["subscription_info"]["endpoint"]
        if endpoint.endswith("flaky"):
            raise WebPushException("boom", response=_Response(500))
        delivered.append(endpoint)

    monkeypatch.setattr(webpush_module, "webpush", fake_webpush)
    channel = WebPushNotificationChannel(repo, private_key="priv", subject="s")

    # Must not raise; the other subscription still gets delivered.
    await channel.send(make_notification())

    assert delivered == ["https://push.example/ok"]
    # A transient (non-404/410) failure does NOT prune the subscription.
    remaining = {
        s.endpoint for s in await repo.list_for_user(TenantId("acme"), UserId("bob"))
    }
    assert remaining == {"https://push.example/flaky", "https://push.example/ok"}


async def test_channel_title_falls_back_for_unknown_kind(monkeypatch):
    repo = InMemoryPushSubscriptionRepository()
    await repo.add(make_sub("https://push.example/a"))
    captured: list[dict] = []
    monkeypatch.setattr(
        webpush_module, "webpush", lambda **kw: captured.append(kw)
    )
    channel = WebPushNotificationChannel(repo, private_key="p", subject="s")

    await channel.send(make_notification(kind="weird", document_id=None))

    payload = json.loads(captured[0]["data"])
    assert payload["title"] == "Notification"
    assert payload["document_id"] is None


# --- PushSubscriptionUseCases (caller-scoped) --------------------------------


async def test_subscribe_adds_a_subscription_for_the_caller():
    repo = InMemoryPushSubscriptionRepository()
    cases = PushSubscriptionUseCases(repo, FixedClock(NOW))

    await cases.subscribe(
        BOB, endpoint="https://push/x", p256dh="key", auth="secret"
    )

    (sub,) = await repo.list_for_user(TenantId("acme"), UserId("bob"))
    assert sub == PushSubscription(
        tenant_id=TenantId("acme"),
        user_id=UserId("bob"),
        endpoint="https://push/x",
        p256dh="key",
        auth="secret",
        created_at=NOW,
    )


async def test_unsubscribe_removes_only_the_callers_subscription():
    repo = InMemoryPushSubscriptionRepository()
    # Alice registers a device with the same endpoint value is not possible
    # (endpoint is unique), so use distinct endpoints per user.
    await repo.add(make_sub("https://push/bob", user="bob"))
    await repo.add(make_sub("https://push/alice", user="alice"))
    cases = PushSubscriptionUseCases(repo, FixedClock(NOW))

    # Bob cannot remove Alice's subscription (scoped to the caller).
    await cases.unsubscribe(BOB, endpoint="https://push/alice")
    assert len(await repo.list_for_user(TenantId("acme"), UserId("alice"))) == 1

    # Bob removes his own.
    await cases.unsubscribe(BOB, endpoint="https://push/bob")
    assert await repo.list_for_user(TenantId("acme"), UserId("bob")) == []
    assert len(await repo.list_for_user(TenantId("acme"), UserId("alice"))) == 1


# --- PostgresPushSubscriptionRepository -------------------------------------


class FakePool:
    """Stands in for asyncpg.Pool: records queries, replays canned rows."""

    def __init__(self, *, rows: list | None = None) -> None:
        self.rows = rows or []
        self.calls: list[tuple[str, tuple]] = []

    async def execute(self, query: str, *args: object) -> None:
        self.calls.append((" ".join(query.split()), args))

    async def fetch(self, query: str, *args: object) -> list:
        self.calls.append((" ".join(query.split()), args))
        return self.rows


def sub_row(**overrides: object) -> dict:
    row = {
        "tenant_id": "acme",
        "user_id": "bob",
        "endpoint": "https://push/x",
        "p256dh": "key",
        "auth": "secret",
        "created_at": NOW,
    }
    row.update(overrides)
    return row


async def test_postgres_add_upserts_on_endpoint():
    pool = FakePool()
    await PostgresPushSubscriptionRepository(pool).add(make_sub("https://push/x"))

    query, args = pool.calls[0]
    assert query.startswith("INSERT INTO push_subscriptions")
    assert "ON CONFLICT (endpoint) DO UPDATE" in query
    assert args == ("acme", "bob", "https://push/x", "p256dh-https://push/x",
                    "auth-https://push/x", NOW)


async def test_postgres_list_for_user_maps_rows():
    pool = FakePool(rows=[sub_row(), sub_row(endpoint="https://push/y")])
    listed = await PostgresPushSubscriptionRepository(pool).list_for_user(
        TenantId("acme"), UserId("bob")
    )

    assert listed[0].endpoint == "https://push/x"
    assert listed[1].endpoint == "https://push/y"
    query, args = pool.calls[0]
    assert "WHERE tenant_id = $1 AND user_id = $2" in query
    assert args == ("acme", "bob")


async def test_postgres_remove_scopes_by_tenant_user_endpoint():
    pool = FakePool()
    await PostgresPushSubscriptionRepository(pool).remove(
        TenantId("acme"), UserId("bob"), "https://push/x"
    )

    query, args = pool.calls[0]
    assert query.startswith("DELETE FROM push_subscriptions")
    assert "tenant_id = $1 AND user_id = $2 AND endpoint = $3" in query
    assert args == ("acme", "bob", "https://push/x")


async def test_postgres_remove_by_endpoint_ignores_owner():
    pool = FakePool()
    await PostgresPushSubscriptionRepository(pool).remove_by_endpoint(
        "https://push/x"
    )

    query, args = pool.calls[0]
    assert query == "DELETE FROM push_subscriptions WHERE endpoint = $1"
    assert args == ("https://push/x",)


# --- HTTP endpoints ----------------------------------------------------------

TOKENS = {
    "bob-token": Claims(subject="bob", tenant_id="acme", email="bob@acme.test"),
}


def _app(**settings_overrides) -> TestClient:
    app = create_app(
        Settings(
            backend="memory",
            auth_base_url="",
            rag_base_url="",
            **settings_overrides,
        ),
        token_port=StaticTokenPort(dict(TOKENS)),
    )
    return TestClient(app)


@pytest.fixture
def api() -> TestClient:
    with _app(push_vapid_public_key="pub-key-123") as client:
        yield client


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_vapid_public_key_returns_configured_key(api):
    response = api.get("/api/v1/push/vapid-public-key")
    assert response.status_code == 200
    assert response.json() == {"key": "pub-key-123"}


def test_vapid_public_key_is_empty_when_unconfigured():
    with _app() as client:
        response = client.get("/api/v1/push/vapid-public-key")
        assert response.json() == {"key": ""}


def test_subscribe_and_list_over_http(api):
    body = {
        "endpoint": "https://push.example/dev1",
        "keys": {"p256dh": "the-key", "auth": "the-secret"},
    }
    response = api.post(
        "/api/v1/push/subscriptions", json=body, headers=auth("bob-token")
    )
    assert response.status_code == 204


def test_unsubscribe_over_http(api):
    body = {
        "endpoint": "https://push.example/dev1",
        "keys": {"p256dh": "k", "auth": "s"},
    }
    api.post("/api/v1/push/subscriptions", json=body, headers=auth("bob-token"))

    response = api.request(
        "DELETE",
        "/api/v1/push/subscriptions",
        json={"endpoint": "https://push.example/dev1"},
        headers=auth("bob-token"),
    )
    assert response.status_code == 204


def test_push_endpoints_require_auth(api):
    assert api.post(
        "/api/v1/push/subscriptions",
        json={"endpoint": "e", "keys": {"p256dh": "k", "auth": "s"}},
    ).status_code == 401
    assert api.request(
        "DELETE", "/api/v1/push/subscriptions", json={"endpoint": "e"}
    ).status_code == 401
