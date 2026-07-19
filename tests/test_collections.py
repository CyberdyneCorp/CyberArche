"""collections-foundation: domain apply_view, use cases, and HTTP surface."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from cyberarche.application.use_cases import UseCases
from cyberarche.domain.collections import (
    Filter,
    PropertyType,
    Sort,
    View,
    ViewKind,
    apply_view,
)
from cyberarche.domain.documents import Document
from cyberarche.domain.errors import NotAuthorized, NotFound, ValidationFailed
from cyberarche.domain.ids import (
    CollectionId,
    DocumentId,
    TenantId,
    UserId,
    WorkspaceId,
)
from cyberarche.domain.memberships import Role, WorkspaceMembership
from tests.conftest import caller

NOW = datetime(2026, 1, 1, tzinfo=UTC)

BOB = caller("bob", "acme")  # same tenant, no workspace role unless granted


# ---- domain: apply_view -----------------------------------------------------


def _row(doc_id: str, title: str, **properties: object) -> Document:
    return Document(
        id=DocumentId(doc_id),
        workspace_id=WorkspaceId("ws-1"),
        tenant_id=TenantId("acme"),
        title=title,
        parent_id=None,
        position=0,
        created_by=UserId("alice"),
        created_at=NOW,
        updated_at=NOW,
        collection_id=CollectionId("col-1"),
        properties=dict(properties),
    )


def _view(**kw: object) -> View:
    return View(id="v", name="V", kind=ViewKind.TABLE, **kw)


def test_apply_view_filters_eq_and_contains():
    rows = [
        _row("d1", "A", status="todo", tags=["x", "y"]),
        _row("d2", "B", status="done", tags=["y"]),
        _row("d3", "C", status="todo", tags=["z"]),
    ]
    view = _view(filters=(Filter("status", "eq", "todo"),))
    assert [r.id for r in apply_view(rows, view)] == ["d1", "d3"]

    view = _view(filters=(Filter("tags", "contains", "x"),))
    assert [r.id for r in apply_view(rows, view)] == ["d1"]


def test_apply_view_empty_and_not_empty():
    rows = [_row("d1", "A", note=""), _row("d2", "B", note="hi"), _row("d3", "C")]
    assert [r.id for r in apply_view(rows, _view(filters=(Filter("note", "is_empty"),)))] == [
        "d1",
        "d3",
    ]
    assert [
        r.id for r in apply_view(rows, _view(filters=(Filter("note", "not_empty"),)))
    ] == ["d2"]


def test_apply_view_numeric_vs_string_comparison():
    rows = [_row("d1", "A", score=2), _row("d2", "B", score=10), _row("d3", "C", score=1)]
    # Numbers compare numerically (not lexicographically: "10" < "2" as strings).
    gt = apply_view(rows, _view(filters=(Filter("score", "gt", 5),)))
    assert [r.id for r in gt] == ["d2"]
    ordered = apply_view(rows, _view(sorts=(Sort("score", "asc"),)))
    assert [r.id for r in ordered] == ["d3", "d1", "d2"]


def test_apply_view_multi_key_and_title_sort():
    rows = [
        _row("d1", "Banana", group="b"),
        _row("d2", "apple", group="a"),
        _row("d3", "Cherry", group="a"),
    ]
    # Sort by group asc, then title asc (case-insensitive, stable).
    view = _view(sorts=(Sort("group", "asc"), Sort("__title__", "asc")))
    assert [r.id for r in apply_view(rows, view)] == ["d2", "d3", "d1"]

    desc = _view(sorts=(Sort("__title__", "desc"),))
    assert [r.id for r in apply_view(rows, desc)] == ["d3", "d1", "d2"]


# ---- use cases: collection CRUD + schema + views ---------------------------


async def _workspace(use_cases: UseCases, alice):
    return await use_cases.workspaces.create(alice, name="WS")


async def test_create_collection_has_a_default_table_view(use_cases: UseCases, alice):
    ws = await _workspace(use_cases, alice)
    collection = await use_cases.collections.create_collection(
        alice, workspace_id=ws.id, name="Tasks"
    )
    assert collection.name == "Tasks"
    assert len(collection.views) == 1
    assert collection.views[0].kind is ViewKind.TABLE
    assert collection.properties == ()


async def test_schema_edit_add_update_remove_property(use_cases: UseCases, alice):
    ws = await _workspace(use_cases, alice)
    col = await use_cases.collections.create_collection(alice, workspace_id=ws.id, name="C")

    col = await use_cases.collections.add_property(
        alice, col.id, name="Status", type=PropertyType.SELECT, options=("todo", "done")
    )
    prop_id = col.properties[0].id
    assert col.properties[0].options == ("todo", "done")

    col = await use_cases.collections.update_property(
        alice, col.id, prop_id, name="State", options=("todo", "done", "wip")
    )
    assert col.properties[0].name == "State"
    assert col.properties[0].options == ("todo", "done", "wip")

    col = await use_cases.collections.remove_property(alice, col.id, prop_id)
    assert col.properties == ()

    with pytest.raises(NotFound):
        await use_cases.collections.remove_property(alice, col.id, prop_id)


async def test_view_crud_cannot_delete_last_view(use_cases: UseCases, alice):
    ws = await _workspace(use_cases, alice)
    col = await use_cases.collections.create_collection(alice, workspace_id=ws.id, name="C")
    first_view = col.views[0].id

    board = await use_cases.collections.create_view(
        alice, col.id, name="Board", kind=ViewKind.BOARD
    )
    updated = await use_cases.collections.update_view(
        alice, col.id, board.id, name="My Board", group_by="p-1"
    )
    assert updated.name == "My Board"
    assert updated.group_by == "p-1"

    await use_cases.collections.delete_view(alice, col.id, board.id)
    with pytest.raises(ValidationFailed):
        await use_cases.collections.delete_view(alice, col.id, first_view)


# ---- use cases: rows -------------------------------------------------------


async def test_add_row_creates_an_openable_document(use_cases: UseCases, alice):
    ws = await _workspace(use_cases, alice)
    col = await use_cases.collections.create_collection(alice, workspace_id=ws.id, name="C")

    row = await use_cases.collections.add_row(alice, col.id, title="First")
    assert row.collection_id == col.id
    assert row.title == "First"

    # The row opens as a normal document page.
    fetched = await use_cases.documents.get(alice, row.id)
    assert fetched.id == row.id
    assert fetched.collection_id == col.id


async def test_set_row_value_validates_and_coerces(use_cases: UseCases, alice):
    ws = await _workspace(use_cases, alice)
    col = await use_cases.collections.create_collection(alice, workspace_id=ws.id, name="C")
    col = await use_cases.collections.add_property(
        alice, col.id, name="Done", type=PropertyType.CHECKBOX
    )
    checkbox = col.properties[0].id
    col = await use_cases.collections.add_property(
        alice, col.id, name="Score", type=PropertyType.NUMBER
    )
    number = col.properties[1].id
    col = await use_cases.collections.add_property(
        alice, col.id, name="Status", type=PropertyType.SELECT, options=("todo", "done")
    )
    select = col.properties[2].id

    row = await use_cases.collections.add_row(alice, col.id)

    row = await use_cases.collections.set_row_value(alice, row.id, checkbox, "yes")
    assert row.properties[checkbox] is True
    row = await use_cases.collections.set_row_value(alice, row.id, number, "42")
    assert row.properties[number] == 42
    row = await use_cases.collections.set_row_value(alice, row.id, select, "todo")
    assert row.properties[select] == "todo"

    with pytest.raises(ValidationFailed):
        await use_cases.collections.set_row_value(alice, row.id, select, "nope")
    with pytest.raises(ValidationFailed):
        await use_cases.collections.set_row_value(alice, row.id, number, "abc")
    with pytest.raises(ValidationFailed):
        await use_cases.collections.set_row_value(alice, row.id, "ghost", "x")


async def test_multi_select_requires_allowed_options(use_cases: UseCases, alice):
    ws = await _workspace(use_cases, alice)
    col = await use_cases.collections.create_collection(alice, workspace_id=ws.id, name="C")
    col = await use_cases.collections.add_property(
        alice, col.id, name="Tags", type=PropertyType.MULTI_SELECT, options=("a", "b")
    )
    tags = col.properties[0].id
    row = await use_cases.collections.add_row(alice, col.id)

    row = await use_cases.collections.set_row_value(alice, row.id, tags, ["a", "b"])
    assert row.properties[tags] == ["a", "b"]
    with pytest.raises(ValidationFailed):
        await use_cases.collections.set_row_value(alice, row.id, tags, ["a", "c"])


async def test_remove_row_drops_it_from_queries(use_cases: UseCases, alice):
    ws = await _workspace(use_cases, alice)
    col = await use_cases.collections.create_collection(alice, workspace_id=ws.id, name="C")
    row = await use_cases.collections.add_row(alice, col.id, title="Doomed")

    await use_cases.collections.remove_row(alice, row.id)
    rows = await use_cases.collections.query_view(alice, col.id, col.views[0].id)
    assert rows == []


async def test_query_view_applies_filters_and_sorts(use_cases: UseCases, alice):
    ws = await _workspace(use_cases, alice)
    col = await use_cases.collections.create_collection(alice, workspace_id=ws.id, name="C")
    col = await use_cases.collections.add_property(
        alice, col.id, name="Status", type=PropertyType.SELECT, options=("todo", "done")
    )
    status = col.properties[0].id

    a = await use_cases.collections.add_row(alice, col.id, title="Alpha")
    b = await use_cases.collections.add_row(alice, col.id, title="Bravo")
    c = await use_cases.collections.add_row(alice, col.id, title="Charlie")
    await use_cases.collections.set_row_value(alice, a.id, status, "todo")
    await use_cases.collections.set_row_value(alice, b.id, status, "done")
    await use_cases.collections.set_row_value(alice, c.id, status, "todo")

    view = await use_cases.collections.update_view(
        alice,
        col.id,
        col.views[0].id,
        filters=(Filter(status, "eq", "todo"),),
        sorts=(Sort("__title__", "desc"),),
    )
    rows = await use_cases.collections.query_view(alice, col.id, view.id)
    assert [r.title for r in rows] == ["Charlie", "Alpha"]


# ---- access control --------------------------------------------------------


async def _viewer_setup(use_cases: UseCases, memberships, clock, alice):
    ws = await _workspace(use_cases, alice)
    col = await use_cases.collections.create_collection(alice, workspace_id=ws.id, name="C")
    await memberships.add_workspace_member(
        WorkspaceMembership(
            workspace_id=ws.id, user_id=BOB.user_id, role=Role.VIEWER,
            granted_at=clock.now(),
        )
    )
    return ws, col


async def test_viewer_can_read_but_not_edit(
    use_cases: UseCases, memberships, clock, alice
):
    ws, col = await _viewer_setup(use_cases, memberships, clock, alice)

    # Viewer may list, get, and query.
    assert [c.id for c in await use_cases.collections.list_collections(BOB, ws.id)] == [
        col.id
    ]
    assert (await use_cases.collections.get_collection(BOB, col.id)).id == col.id
    assert await use_cases.collections.query_view(BOB, col.id, col.views[0].id) == []

    # Viewer may not create, rename, edit schema, or add rows.
    with pytest.raises(NotAuthorized):
        await use_cases.collections.rename_collection(BOB, col.id, name="Nope")
    with pytest.raises(NotAuthorized):
        await use_cases.collections.add_property(
            BOB, col.id, name="P", type=PropertyType.TEXT
        )
    with pytest.raises(NotAuthorized):
        await use_cases.collections.add_row(BOB, col.id)


async def test_non_member_is_refused(use_cases: UseCases, alice, bob_other_tenant):
    ws = await _workspace(use_cases, alice)
    col = await use_cases.collections.create_collection(alice, workspace_id=ws.id, name="C")

    # Different tenant: the collection is invisible (NotFound).
    with pytest.raises(NotFound):
        await use_cases.collections.get_collection(bob_other_tenant, col.id)
    # Same tenant, no workspace role: refused.
    carol = caller("carol", "acme")
    with pytest.raises(NotAuthorized):
        await use_cases.collections.get_collection(carol, col.id)


async def test_get_missing_collection_raises_not_found(use_cases: UseCases, alice):
    with pytest.raises(NotFound):
        await use_cases.collections.get_collection(alice, CollectionId("ghost"))


async def test_set_value_on_non_row_document_is_rejected(use_cases: UseCases, alice):
    ws = await _workspace(use_cases, alice)
    doc = await use_cases.documents.create(alice, workspace_id=ws.id, title="Plain")
    with pytest.raises(ValidationFailed):
        await use_cases.collections.set_row_value(alice, doc.id, "p", "v")


# ---- bulk row actions -------------------------------------------------------


async def _bulk_setup(use_cases: UseCases, alice):
    """A collection with a single-select Status property + a Score number."""
    ws = await _workspace(use_cases, alice)
    col = await use_cases.collections.create_collection(alice, workspace_id=ws.id, name="C")
    col = await use_cases.collections.add_property(
        alice, col.id, name="Status", type=PropertyType.SELECT, options=("todo", "done")
    )
    status = col.properties[0].id
    col = await use_cases.collections.add_property(
        alice, col.id, name="Score", type=PropertyType.NUMBER
    )
    number = col.properties[1].id
    return ws, col, status, number


async def test_delete_rows_deletes_and_returns_count(use_cases: UseCases, alice):
    ws, col, _status, _number = await _bulk_setup(use_cases, alice)
    a = await use_cases.collections.add_row(alice, col.id, title="A")
    b = await use_cases.collections.add_row(alice, col.id, title="B")
    c = await use_cases.collections.add_row(alice, col.id, title="C")

    count = await use_cases.collections.delete_rows(alice, col.id, [a.id, b.id])
    assert count == 2
    remaining = await use_cases.collections.query_view(alice, col.id, col.views[0].id)
    assert [r.id for r in remaining] == [c.id]


async def test_delete_rows_skips_foreign_missing_and_trashed(use_cases: UseCases, alice):
    ws, col, _status, _number = await _bulk_setup(use_cases, alice)
    col2 = await use_cases.collections.create_collection(
        alice, workspace_id=ws.id, name="Other"
    )
    keep = await use_cases.collections.add_row(alice, col.id, title="Keep")
    foreign = await use_cases.collections.add_row(alice, col2.id, title="Foreign")
    trashed = await use_cases.collections.add_row(alice, col.id, title="Trashed")
    await use_cases.collections.remove_row(alice, trashed.id)

    count = await use_cases.collections.delete_rows(
        alice, col.id, [keep.id, foreign.id, trashed.id, "ghost"]
    )
    # Only the one live, in-collection row is deleted.
    assert count == 1
    remaining = await use_cases.collections.query_view(alice, col.id, col.views[0].id)
    assert remaining == []
    # The foreign collection's row is untouched.
    other = await use_cases.collections.query_view(alice, col2.id, col2.views[0].id)
    assert [r.id for r in other] == [foreign.id]


async def test_delete_rows_propagates_not_authorized_for_in_collection_row(
    use_cases: UseCases, memberships, clock, alice
):
    ws, col = await _viewer_setup(use_cases, memberships, clock, alice)
    row = await use_cases.collections.add_row(alice, col.id, title="Alice's row")
    # BOB is a workspace VIEWER: the row IS in the collection, so the per-row
    # EDITOR check is a real authz boundary and must propagate (not be skipped).
    with pytest.raises(NotAuthorized):
        await use_cases.collections.delete_rows(BOB, col.id, [row.id])


async def test_set_rows_value_sets_all_selected_and_returns_count(
    use_cases: UseCases, alice
):
    ws, col, status, _number = await _bulk_setup(use_cases, alice)
    a = await use_cases.collections.add_row(alice, col.id, title="A")
    b = await use_cases.collections.add_row(alice, col.id, title="B")

    count = await use_cases.collections.set_rows_value(
        alice, col.id, [a.id, b.id], property_id=status, value="done"
    )
    assert count == 2
    rows = await use_cases.collections.query_view(alice, col.id, col.views[0].id)
    assert all(r.properties[status] == "done" for r in rows)


async def test_set_rows_value_skips_foreign_ids(use_cases: UseCases, alice):
    ws, col, status, _number = await _bulk_setup(use_cases, alice)
    col2 = await use_cases.collections.create_collection(
        alice, workspace_id=ws.id, name="Other"
    )
    a = await use_cases.collections.add_row(alice, col.id, title="A")
    foreign = await use_cases.collections.add_row(alice, col2.id, title="Foreign")

    count = await use_cases.collections.set_rows_value(
        alice, col.id, [a.id, foreign.id, "ghost"], property_id=status, value="todo"
    )
    assert count == 1
    rows = await use_cases.collections.query_view(alice, col.id, col.views[0].id)
    assert rows[0].properties[status] == "todo"


async def test_set_rows_value_rejects_formula_property(use_cases: UseCases, alice):
    ws, col, _status, _number = await _bulk_setup(use_cases, alice)
    col = await use_cases.collections.add_property(
        alice, col.id, name="Fx", type=PropertyType.FORMULA, formula='prop("Title")'
    )
    fx = next(p.id for p in col.properties if p.type == PropertyType.FORMULA)
    a = await use_cases.collections.add_row(alice, col.id)
    with pytest.raises(ValidationFailed):
        await use_cases.collections.set_rows_value(
            alice, col.id, [a.id], property_id=fx, value="x"
        )


async def test_set_rows_value_rejects_unknown_property_and_bad_value(
    use_cases: UseCases, alice
):
    ws, col, _status, number = await _bulk_setup(use_cases, alice)
    # Unknown property fails up front, even with no matching ids.
    with pytest.raises(ValidationFailed):
        await use_cases.collections.set_rows_value(
            alice, col.id, [], property_id="ghost", value="x"
        )
    # A bad value for the property fails fast, before touching any row.
    with pytest.raises(ValidationFailed):
        await use_cases.collections.set_rows_value(
            alice, col.id, [], property_id=number, value="not-a-number"
        )


# ---- HTTP surface ----------------------------------------------------------


def _make_workspace(api) -> str:
    resp = api.post(
        "/api/v1/workspaces",
        json={"name": "WS"},
        headers={"authorization": "Bearer alice-token"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_http_collection_lifecycle(api):
    headers = {"authorization": "Bearer alice-token"}
    ws_id = _make_workspace(api)

    created = api.post(
        f"/api/v1/workspaces/{ws_id}/collections",
        json={"name": "Tasks"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    col = created.json()
    assert col["name"] == "Tasks"
    assert len(col["views"]) == 1
    col_id, view_id = col["id"], col["views"][0]["id"]

    # Add a select property.
    prop_resp = api.post(
        f"/api/v1/collections/{col_id}/properties",
        json={"name": "Status", "type": "select", "options": ["todo", "done"]},
        headers=headers,
    )
    assert prop_resp.status_code == 201, prop_resp.text
    prop_id = prop_resp.json()["properties"][0]["id"]

    # Add a row and set its value.
    row_resp = api.post(
        f"/api/v1/collections/{col_id}/rows",
        json={"title": "Ship it"},
        headers=headers,
    )
    assert row_resp.status_code == 201, row_resp.text
    row_id = row_resp.json()["id"]

    patched = api.patch(
        f"/api/v1/collections/{col_id}/rows/{row_id}",
        json={"property_id": prop_id, "value": "todo"},
        headers=headers,
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["properties"][prop_id] == "todo"

    # Query the table view returns the row.
    rows = api.get(
        f"/api/v1/collections/{col_id}/views/{view_id}/rows", headers=headers
    )
    assert rows.status_code == 200
    assert [r["title"] for r in rows.json()["rows"]] == ["Ship it"]

    # List collections in the workspace.
    listed = api.get(f"/api/v1/workspaces/{ws_id}/collections", headers=headers)
    assert [c["id"] for c in listed.json()] == [col_id]


def test_http_reading_requires_access(api):
    ws_id = _make_workspace(api)
    created = api.post(
        f"/api/v1/workspaces/{ws_id}/collections",
        json={"name": "Secret"},
        headers={"authorization": "Bearer alice-token"},
    )
    col_id = created.json()["id"]

    # mallory is in another tenant -> the collection is not found for her.
    denied = api.get(
        f"/api/v1/collections/{col_id}",
        headers={"authorization": "Bearer mallory-token"},
    )
    assert denied.status_code == 404
