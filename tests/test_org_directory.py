"""org-directory spec: org user listing, service-identity adapter, degradation."""

from __future__ import annotations

import httpx
import pytest

from cyberarche.adapters.inbound.http.errors import _status_for
from cyberarche.adapters.outbound.auth.cyberdyne import (
    CyberdyneAuthConfig,
    CyberdyneDirectory,
)
from cyberarche.application.testing.fakes import InMemoryDirectory
from cyberarche.application.ports.identity import DirectoryUser
from cyberarche.application.use_cases.org_directory import OrgDirectoryUseCases
from cyberarche.domain.errors import UpstreamUnavailable
from tests.conftest import caller

ACME_USERS = [
    DirectoryUser(id="alice", email="alice@acme.test", avatar_url="http://a/alice.png"),
    DirectoryUser(id="bob", email="bob@acme.test"),
    DirectoryUser(id="ada", email="ada@acme.test", is_active=False),
]


def acme_directory() -> InMemoryDirectory:
    return InMemoryDirectory({"acme": list(ACME_USERS)})


async def test_lists_the_callers_org(alice):
    cases = OrgDirectoryUseCases(acme_directory())

    page = await cases.list_org_users(alice)

    assert [u.id for u in page.users] == ["alice", "bob", "ada"]
    assert page.total == 3


async def test_search_filters_by_email(alice):
    cases = OrgDirectoryUseCases(acme_directory())

    page = await cases.list_org_users(alice, search="ADA")

    assert [u.id for u in page.users] == ["ada"]
    assert page.total == 1


async def test_pagination(alice):
    cases = OrgDirectoryUseCases(acme_directory())

    page = await cases.list_org_users(alice, page=2, page_size=2)

    assert [u.id for u in page.users] == ["ada"]
    assert (page.total, page.page, page.page_size) == (3, 2, 2)


async def test_personal_tenant_gets_an_empty_page_not_an_error():
    solo = caller("solo", "solo")  # tenant == subject: no organization

    page = await OrgDirectoryUseCases(None).list_org_users(solo)

    assert page.users == [] and page.total == 0


async def test_unconfigured_directory_is_unavailable(alice):
    with pytest.raises(UpstreamUnavailable):
        await OrgDirectoryUseCases(None).list_org_users(alice)


def test_upstream_unavailable_maps_to_503():
    assert _status_for(UpstreamUnavailable("down")) == 503


# ---- CyberdyneDirectory adapter ---------------------------------------------

CONFIG = CyberdyneAuthConfig(base_url="https://auth.test", client_id="cyberarche")


class StubServiceTokens:
    async def service_token(self) -> str:
        return "service-token"


def directory_with(handler) -> CyberdyneDirectory:
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return CyberdyneDirectory(CONFIG, http, StubServiceTokens())


async def test_adapter_calls_the_org_members_endpoint_with_the_service_token():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(
            200,
            json={
                "members": [
                    {"id": "u1", "email": "u1@acme.test", "avatar_url": None,
                     "is_active": True},
                ],
                "total": 1,
                "page": 1,
                "page_size": 50,
            },
        )

    page = await directory_with(handler).list_org_users("org-1", search="u1")

    assert seen["url"] == (
        "https://auth.test/api/v1/orgs/org-1/members"
        "?page=1&page_size=50&search=u1"
    )
    assert seen["auth"] == "Bearer service-token"
    assert page.users == [DirectoryUser(id="u1", email="u1@acme.test")]
    assert page.total == 1


async def test_adapter_treats_an_unknown_org_as_empty():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "org not found"})

    page = await directory_with(handler).list_org_users("gone")

    assert page.users == [] and page.total == 0


async def test_adapter_maps_provider_errors_to_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"detail": "missing directory:read"})

    with pytest.raises(UpstreamUnavailable):
        await directory_with(handler).list_org_users("org-1")


async def test_adapter_maps_network_failures_to_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    with pytest.raises(UpstreamUnavailable):
        await directory_with(handler).list_org_users("org-1")
