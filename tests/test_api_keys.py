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
