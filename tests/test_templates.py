"""templates spec: save a document as a template, instantiate, list, delete."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from cyberarche.adapters.outbound.postgres.templates import PostgresTemplateRepository
from cyberarche.application.use_cases import UseCases
from cyberarche.domain.errors import NotFound
from cyberarche.domain.ids import TemplateId, TenantId, UserId, WorkspaceId
from cyberarche.domain.templates import Template


def para(text: str, bid: str) -> dict:
    return {"id": bid, "type": "paragraph", "data": {"text": text}}


async def test_save_and_instantiate_template(use_cases: UseCases, alice):
    ws = await use_cases.workspaces.create(alice, name="WS")
    team = await use_cases.teamspaces.create(alice, ws.id, name="Team")
    source = await use_cases.documents.create(
        alice, workspace_id=ws.id, title="Meeting notes", teamspace_id=team.id
    )
    await use_cases.agent.apply_blocks(
        alice, source.id, [para("Agenda", "b1"), para("Action items", "b2")]
    )

    template = await use_cases.templates.save_from_document(
        alice, ws.id, name="Standup", document_id=source.id
    )
    assert template.name == "Standup"
    assert [b["data"]["text"] for b in template.content] == ["Agenda", "Action items"]
    assert [t.id for t in await use_cases.templates.list(alice, ws.id)] == [template.id]

    # Instantiate → a new document pre-filled with the template's blocks (fresh ids).
    doc = await use_cases.templates.instantiate(
        alice, ws.id, template_id=template.id, title="Today's standup", teamspace_id=team.id
    )
    assert doc.id != source.id
    state = await use_cases.realtime.current_state(alice, doc.id)
    blocks = use_cases.agent._engine.read_blocks(state)
    assert [b["data"]["text"] for b in blocks] == ["Agenda", "Action items"]
    # Fresh ids — the new document must not reuse the template's source block ids.
    assert {b["id"] for b in blocks}.isdisjoint({"b1", "b2"})


async def test_delete_template(use_cases: UseCases, alice):
    ws = await use_cases.workspaces.create(alice, name="WS")
    doc = await use_cases.documents.create(alice, workspace_id=ws.id, title="Doc")
    template = await use_cases.templates.save_from_document(
        alice, ws.id, name="T", document_id=doc.id
    )
    await use_cases.templates.delete(alice, template.id)
    assert await use_cases.templates.list(alice, ws.id) == []
    with pytest.raises(NotFound):
        await use_cases.templates.delete(alice, template.id)


# ---- HTTP router -----------------------------------------------------------


def _auth(token: str = "alice-token") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_workspace_http(api) -> str:
    return api.post("/api/v1/workspaces", json={"name": "WS"}, headers=_auth()).json()[
        "id"
    ]


def test_templates_router_roundtrip(api):
    ws = _make_workspace_http(api)
    team = api.post(
        f"/api/v1/workspaces/{ws}/teamspaces", json={"name": "Team"}, headers=_auth()
    ).json()
    source = api.post(
        "/api/v1/documents",
        json={"workspace_id": ws, "title": "Meeting notes", "teamspace_id": team["id"]},
        headers=_auth(),
    ).json()
    base = f"/api/v1/workspaces/{ws}/templates"

    created = api.post(
        base,
        json={"name": "Standup", "document_id": source["id"]},
        headers=_auth(),
    )
    assert created.status_code == 201
    template = created.json()
    assert template["name"] == "Standup"
    assert template["created_by"] == "alice"
    assert template["block_count"] == 0  # the source document is empty

    listed = api.get(base, headers=_auth())
    assert listed.status_code == 200
    assert [t["id"] for t in listed.json()] == [template["id"]]

    # Instantiate into a teamspace with an explicit title.
    in_team = api.post(
        f"{base}/{template['id']}/instantiate",
        json={"title": "Today's standup", "teamspace_id": team["id"]},
        headers=_auth(),
    )
    assert in_team.status_code == 201
    document = in_team.json()
    assert document["title"] == "Today's standup"
    assert document["workspace_id"] == ws
    assert document["teamspace_id"] == team["id"]
    assert document["id"] != source["id"]

    # Defaults: empty title falls back to the template name, no teamspace.
    private = api.post(
        f"{base}/{template['id']}/instantiate", json={}, headers=_auth()
    )
    assert private.status_code == 201
    assert private.json()["title"] == "Standup"
    assert private.json()["teamspace_id"] is None

    deleted = api.delete(f"/api/v1/templates/{template['id']}", headers=_auth())
    assert deleted.status_code == 204
    assert api.get(base, headers=_auth()).json() == []


def test_templates_router_error_mapping(api):
    ws = _make_workspace_http(api)
    base = f"/api/v1/workspaces/{ws}/templates"

    # Saving from a document that does not exist -> 404.
    missing_doc = api.post(
        base, json={"name": "T", "document_id": "missing"}, headers=_auth()
    )
    assert missing_doc.status_code == 404

    # Instantiating or deleting an unknown template -> 404.
    assert (
        api.post(f"{base}/missing/instantiate", json={}, headers=_auth()).status_code
        == 404
    )
    assert api.delete("/api/v1/templates/missing", headers=_auth()).status_code == 404

    # A template belongs to its workspace: instantiating it from another
    # workspace's URL is a 404.
    doc = api.post(
        "/api/v1/documents",
        json={"workspace_id": ws, "title": "Doc"},
        headers=_auth(),
    ).json()
    template = api.post(
        base, json={"name": "T", "document_id": doc["id"]}, headers=_auth()
    ).json()
    other_ws = api.post(
        "/api/v1/workspaces", json={"name": "Other"}, headers=_auth()
    ).json()["id"]
    crossed = api.post(
        f"/api/v1/workspaces/{other_ws}/templates/{template['id']}/instantiate",
        json={},
        headers=_auth(),
    )
    assert crossed.status_code == 404


def test_templates_router_requires_auth_and_membership(api):
    ws = _make_workspace_http(api)
    base = f"/api/v1/workspaces/{ws}/templates"

    # No token -> 401 before any use case runs.
    assert api.get(base).status_code == 401
    # A caller outside the workspace cannot list its templates -> 403.
    assert api.get(base, headers=_auth("mallory-token")).status_code == 403


# ---- Postgres adapter ------------------------------------------------------
# Unit-level: a scripted pool stands in for asyncpg so the adapter's SQL
# parameter mapping and row decoding are covered without a database.

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class _ScriptedPool:
    """Records every query and replays canned rows (dicts stand in for Records)."""

    def __init__(self, *, rows: list[dict] | None = None, row: dict | None = None):
        self.calls: list[tuple[str, str, tuple]] = []
        self._rows = rows or []
        self._row = row

    async def execute(self, query: str, *args) -> str:
        self.calls.append(("execute", query, args))
        return "OK"

    async def fetch(self, query: str, *args) -> list[dict]:
        self.calls.append(("fetch", query, args))
        return self._rows

    async def fetchrow(self, query: str, *args) -> dict | None:
        self.calls.append(("fetchrow", query, args))
        return self._row


def _template(**kw) -> Template:
    return Template(
        id=TemplateId(kw.get("id", "tpl-1")),
        tenant_id=TenantId("acme"),
        workspace_id=WorkspaceId("ws-1"),
        name=kw.get("name", "Standup"),
        created_by=UserId("alice"),
        created_at=NOW,
        content=kw.get("content", [para("Agenda", "b1")]),
    )


def _row(**kw) -> dict:
    return {
        "id": kw.get("id", "tpl-1"),
        "tenant_id": "acme",
        "workspace_id": "ws-1",
        "name": kw.get("name", "Standup"),
        "created_by": "alice",
        "created_at": NOW,
        "content": kw.get("content", [para("Agenda", "b1")]),
    }


async def test_postgres_templates_add_serializes_content_as_json():
    pool = _ScriptedPool()
    await PostgresTemplateRepository(pool).add(_template())

    kind, query, args = pool.calls[0]
    assert kind == "execute" and "INSERT INTO templates" in query
    assert args[:6] == ("tpl-1", "acme", "ws-1", "Standup", "alice", NOW)
    assert json.loads(args[6]) == [para("Agenda", "b1")]  # jsonb param is a string


async def test_postgres_templates_list_for_workspace_decodes_rows():
    # Postgres may hand jsonb back as a str or an already-decoded list.
    pool = _ScriptedPool(rows=[
        _row(id="tpl-1", content=json.dumps([para("Agenda", "b1")])),
        _row(id="tpl-2", content=[para("Notes", "b2")]),
    ])
    listed = await PostgresTemplateRepository(pool).list_for_workspace(
        TenantId("acme"), WorkspaceId("ws-1")
    )

    assert [t.id for t in listed] == ["tpl-1", "tpl-2"]
    assert listed[0].content == [para("Agenda", "b1")]
    assert listed[1].content == [para("Notes", "b2")]
    kind, query, args = pool.calls[0]
    assert kind == "fetch" and args == ("acme", "ws-1")
    assert "ORDER BY created_at DESC" in query


async def test_postgres_templates_get_maps_row_and_null_content():
    pool = _ScriptedPool(row=_row(content=None))
    got = await PostgresTemplateRepository(pool).get(TenantId("acme"), TemplateId("tpl-1"))

    assert got is not None
    assert got.content == []  # NULL content -> empty block list
    assert (got.id, got.tenant_id, got.workspace_id) == ("tpl-1", "acme", "ws-1")
    assert (got.name, got.created_by, got.created_at) == ("Standup", "alice", NOW)
    assert pool.calls[0][2] == ("acme", "tpl-1")


async def test_postgres_templates_get_missing_returns_none():
    pool = _ScriptedPool(row=None)
    repo = PostgresTemplateRepository(pool)
    assert await repo.get(TenantId("acme"), TemplateId("missing")) is None


async def test_postgres_templates_delete_scopes_by_tenant():
    pool = _ScriptedPool()
    await PostgresTemplateRepository(pool).delete(TenantId("acme"), TemplateId("tpl-1"))

    kind, query, args = pool.calls[0]
    assert kind == "execute" and query.startswith("DELETE FROM templates")
    assert args == ("acme", "tpl-1")
