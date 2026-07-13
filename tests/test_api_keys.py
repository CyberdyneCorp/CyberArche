"""auth-integration spec: personal API keys for external MCP clients."""

from __future__ import annotations

from datetime import timedelta

import pytest

from cyberarche.application.kernel import CallerContext
from cyberarche.application.testing.fakes import (
    FixedClock,
    InMemoryApiKeyRepository,
    SequentialIds,
    StaticTokenPort,
)
from cyberarche.application.use_cases.api_keys import (
    ApiKeyUseCases,
    CompositeTokenVerifier,
)
from cyberarche.domain.api_keys import KEY_PREFIX, hash_secret
from cyberarche.domain.errors import NotAuthenticated
from cyberarche.domain.ids import TenantId, UserId

ALICE = CallerContext(user_id=UserId("alice"), tenant_id=TenantId("acme"))


@pytest.fixture
def repo() -> InMemoryApiKeyRepository:
    return InMemoryApiKeyRepository()


@pytest.fixture
def keys(repo, clock) -> ApiKeyUseCases:
    return ApiKeyUseCases(repo, clock, SequentialIds())


@pytest.fixture
def verifier(repo, clock) -> CompositeTokenVerifier:
    return CompositeTokenVerifier(repo, StaticTokenPort({}), clock)


async def test_create_returns_secret_once_and_stores_only_the_hash(keys, repo):
    created = await keys.create(ALICE, name="Claude Desktop")

    assert created.secret.startswith(KEY_PREFIX)
    assert created.key.secret_hash == hash_secret(created.secret)
    assert created.secret not in str(vars(repo))  # never persisted raw

    listed = await keys.list(ALICE)
    assert [k.name for k in listed] == ["Claude Desktop"]
    assert listed[0].prefix.endswith("…")
    assert not hasattr(listed[0], "secret")


async def test_key_authenticates_as_its_owner(keys, verifier):
    created = await keys.create(ALICE, name="ChatGPT")

    claims = await verifier.verify(created.secret)

    assert claims.subject == "alice"
    assert claims.tenant_id == "acme"
    assert claims.is_service is False


async def test_wrong_or_unknown_key_is_rejected(keys, verifier):
    await keys.create(ALICE, name="k")
    with pytest.raises(NotAuthenticated):
        await verifier.verify("cak_definitely-not-a-real-key")


async def test_revoked_key_is_rejected_immediately(keys, verifier):
    created = await keys.create(ALICE, name="leaky")
    await verifier.verify(created.secret)  # works before revocation

    await keys.revoke(ALICE, created.key.id)

    with pytest.raises(NotAuthenticated):
        await verifier.verify(created.secret)


async def test_expired_key_is_rejected(keys, verifier, clock: FixedClock):
    created = await keys.create(
        ALICE, name="temp", expires_at=clock.now() + timedelta(hours=1)
    )
    await verifier.verify(created.secret)

    clock.tick(seconds=2 * 3600)

    with pytest.raises(NotAuthenticated):
        await verifier.verify(created.secret)


async def test_last_used_is_tracked(keys, verifier, repo, clock: FixedClock):
    created = await keys.create(ALICE, name="tracked")
    assert created.key.last_used_at is None

    clock.tick(60)
    await verifier.verify(created.secret)

    stored = await repo.get(ALICE.user_id, created.key.id)
    assert stored.last_used_at == clock.now()


async def test_non_key_tokens_fall_through_to_the_inner_verifier(repo, clock):
    from cyberarche.application.ports.identity import Claims

    inner = StaticTokenPort({"jwt-ish": Claims(subject="bob", tenant_id="globex")})
    verifier = CompositeTokenVerifier(repo, inner, clock)

    claims = await verifier.verify("jwt-ish")
    assert claims.subject == "bob"


async def test_users_cannot_revoke_each_others_keys(keys):
    from cyberarche.domain.errors import NotFound
    from tests.conftest import caller

    created = await keys.create(ALICE, name="mine")
    with pytest.raises(NotFound):
        await keys.revoke(caller("mallory", "acme"), created.key.id)


def test_api_key_authenticates_http_and_mcp_like_surfaces(api):
    """The composite verifier sits on container.token_port, so a key minted
    over HTTP immediately authenticates any surface using that seam."""
    headers = {"Authorization": "Bearer alice-token"}
    created = api.post(
        "/api/v1/api-keys", json={"name": "Claude"}, headers=headers
    ).json()
    assert created["secret"].startswith("cak_")

    # Listing never exposes the secret again.
    listed = api.get("/api/v1/api-keys", headers=headers).json()
    assert "secret" not in listed[0]

    # The key works as alice on the HTTP surface...
    key_headers = {"Authorization": f"Bearer {created['secret']}"}
    workspace = api.post(
        "/api/v1/workspaces", json={"name": "Via Key"}, headers=key_headers
    )
    assert workspace.status_code == 201

    # ...and on the WebSocket relay (same token seam as MCP).
    document = api.post(
        "/api/v1/documents",
        json={"workspace_id": workspace.json()["id"], "title": "Key Doc"},
        headers=key_headers,
    ).json()
    with api.websocket_connect(
        f"/api/v1/documents/{document['id']}/sync?token={created['secret']}"
    ) as ws:
        assert ws.receive_bytes()[0] == 0  # initial state frame

    # Revoke -> denied everywhere.
    api.delete(f"/api/v1/api-keys/{created['id']}", headers=headers)
    denied = api.get("/api/v1/workspaces", headers=key_headers)
    assert denied.status_code == 401


# --- PostgresApiKeyRepository: SQL translation over a recorded stub pool ---

from datetime import UTC, datetime

from cyberarche.adapters.outbound.postgres.api_keys import PostgresApiKeyRepository
from cyberarche.domain.api_keys import ApiKey

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class _StubPool:
    """Records every query and returns canned rows — no real Postgres."""

    def __init__(self, rows: list[dict] | None = None, row: dict | None = None) -> None:
        self.rows = rows or []
        self.row = row
        self.calls: list[tuple[str, str, tuple]] = []

    async def execute(self, query: str, *args) -> str:
        self.calls.append(("execute", query, args))
        return "OK"

    async def fetch(self, query: str, *args) -> list[dict]:
        self.calls.append(("fetch", query, args))
        return self.rows

    async def fetchrow(self, query: str, *args) -> dict | None:
        self.calls.append(("fetchrow", query, args))
        return self.row


def _key(**kw) -> ApiKey:
    defaults = dict(
        id="k-1",
        tenant_id=TenantId("acme"),
        user_id=UserId("alice"),
        name="Claude",
        secret_hash="hash-1",
        prefix="cak_abcd1234…",
        created_at=NOW,
        expires_at=None,
        revoked_at=None,
        last_used_at=None,
    )
    defaults.update(kw)
    return ApiKey(**defaults)


def _row(key: ApiKey) -> dict:
    return {
        "id": key.id, "tenant_id": key.tenant_id, "user_id": key.user_id,
        "name": key.name, "secret_hash": key.secret_hash, "prefix": key.prefix,
        "created_at": key.created_at, "expires_at": key.expires_at,
        "revoked_at": key.revoked_at, "last_used_at": key.last_used_at,
    }


async def test_postgres_api_key_add_persists_every_column():
    pool = _StubPool()
    key = _key(expires_at=NOW + timedelta(days=30))

    await PostgresApiKeyRepository(pool).add(key)

    kind, query, args = pool.calls[0]
    assert kind == "execute" and "INSERT INTO api_keys" in query
    assert args == (
        key.id, key.tenant_id, key.user_id, key.name, key.secret_hash,
        key.prefix, key.created_at, key.expires_at, key.revoked_at,
        key.last_used_at,
    )


async def test_postgres_api_key_by_hash_maps_row_and_misses_return_none():
    key = _key(revoked_at=NOW, last_used_at=NOW)
    hit = PostgresApiKeyRepository(_StubPool(row=_row(key)))
    assert await hit.by_hash("hash-1") == key

    miss_pool = _StubPool(row=None)
    assert await PostgresApiKeyRepository(miss_pool).by_hash("nope") is None
    kind, query, args = miss_pool.calls[0]
    assert kind == "fetchrow" and "secret_hash = $1" in query
    assert args == ("nope",)


async def test_postgres_api_key_get_scopes_by_user():
    key = _key()
    pool = _StubPool(row=_row(key))

    found = await PostgresApiKeyRepository(pool).get(UserId("alice"), "k-1")

    assert found == key
    kind, query, args = pool.calls[0]
    assert kind == "fetchrow" and "id = $1 AND user_id = $2" in query
    assert args == ("k-1", UserId("alice"))

    # Another user's lookup (no matching row) is None, not an error.
    empty = PostgresApiKeyRepository(_StubPool(row=None))
    assert await empty.get(UserId("mallory"), "k-1") is None


async def test_postgres_api_key_list_for_user_maps_rows_in_order():
    first, second = _key(id="k-1"), _key(id="k-2", name="CLI")
    pool = _StubPool(rows=[_row(first), _row(second)])

    listed = await PostgresApiKeyRepository(pool).list_for_user(
        TenantId("acme"), UserId("alice")
    )

    assert listed == [first, second]
    kind, query, args = pool.calls[0]
    assert kind == "fetch" and "FROM api_keys" in query
    assert args == (TenantId("acme"), UserId("alice"))

    empty = _StubPool(rows=[])
    assert await PostgresApiKeyRepository(empty).list_for_user(
        TenantId("acme"), UserId("bob")
    ) == []


async def test_postgres_api_key_update_writes_revocation_and_usage():
    pool = _StubPool()
    key = _key().revoke(NOW).touched(NOW)

    await PostgresApiKeyRepository(pool).update(key)

    kind, query, args = pool.calls[0]
    assert kind == "execute" and "UPDATE api_keys" in query
    assert args == (key.id, NOW, NOW)
