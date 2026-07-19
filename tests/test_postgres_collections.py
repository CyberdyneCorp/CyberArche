"""Unit tests for PostgresCollectionRepository (thin row<->aggregate mapping).

Mirrors test_postgres_repositories.py: a FakePool records the SQL and bound
parameters and replays canned rows, so both directions of the JSONB mapping
are asserted without a live database.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from cyberarche.adapters.outbound.postgres.collections import (
    PostgresCollectionRepository,
)
from cyberarche.domain.collections import (
    Collection,
    Filter,
    PropertyDef,
    PropertyType,
    Sort,
    View,
    ViewKind,
)
from cyberarche.domain.ids import CollectionId, TenantId, WorkspaceId

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class FakePool:
    def __init__(self, *, rows: list | None = None, row: dict | None = None) -> None:
        self.rows = rows or []
        self.row = row
        self.calls: list[tuple[str, tuple]] = []

    async def execute(self, query: str, *args: object) -> None:
        self.calls.append((" ".join(query.split()), args))

    async def fetch(self, query: str, *args: object) -> list:
        self.calls.append((" ".join(query.split()), args))
        return self.rows

    async def fetchrow(self, query: str, *args: object) -> dict | None:
        self.calls.append((" ".join(query.split()), args))
        return self.row


def make_collection(**overrides: object) -> Collection:
    view = View(
        id="v-1",
        name="Table",
        kind=ViewKind.TABLE,
        filters=(Filter("p-1", "eq", "todo"),),
        sorts=(Sort("__title__", "desc"),),
        group_by="p-1",
    )
    prop = PropertyDef(
        id="p-1", name="Status", type=PropertyType.SELECT, options=("todo", "done")
    )
    fields: dict = dict(
        id=CollectionId("col-1"),
        tenant_id=TenantId("acme"),
        workspace_id=WorkspaceId("ws-1"),
        name="Tasks",
        properties=(prop,),
        views=(view,),
        created_at=NOW,
    )
    fields.update(overrides)
    return Collection(**fields)


def collection_row(**overrides: object) -> dict:
    row = {
        "id": "col-1",
        "tenant_id": "acme",
        "workspace_id": "ws-1",
        "name": "Tasks",
        "properties": json.dumps(
            [{"id": "p-1", "name": "Status", "type": "select", "options": ["todo", "done"]}]
        ),
        "views": json.dumps(
            [
                {
                    "id": "v-1",
                    "name": "Table",
                    "kind": "table",
                    "filters": [{"property_id": "p-1", "op": "eq", "value": "todo"}],
                    "sorts": [{"property_id": "__title__", "direction": "desc"}],
                    "group_by": "p-1",
                    "date_by": None,
                }
            ]
        ),
        "created_at": NOW,
    }
    row.update(overrides)
    return row


async def test_add_serializes_schema_and_views_to_jsonb():
    pool = FakePool()
    await PostgresCollectionRepository(pool).add(make_collection())

    query, args = pool.calls[0]
    assert query.startswith("INSERT INTO collections")
    assert args[0:4] == ("col-1", "acme", "ws-1", "Tasks")
    assert json.loads(args[4]) == [
        {
            "id": "p-1",
            "name": "Status",
            "type": "select",
            "options": ["todo", "done"],
            "formula": "",
            "relation_collection_id": "",
            "rollup_relation_property_id": "",
            "rollup_target_property_id": "",
            "rollup_function": "",
            "reminder_minutes": -1,
        }
    ]
    views = json.loads(args[5])
    assert views[0]["kind"] == "table"
    assert views[0]["filters"] == [{"property_id": "p-1", "op": "eq", "value": "todo"}]
    assert args[6] == NOW


async def test_get_maps_row_and_scopes_by_tenant():
    pool = FakePool(row=collection_row())
    found = await PostgresCollectionRepository(pool).get(
        TenantId("acme"), CollectionId("col-1")
    )

    assert found == make_collection()
    assert found.properties[0].type is PropertyType.SELECT
    assert found.views[0].sorts[0].direction == "desc"
    _, args = pool.calls[0]
    assert args == ("col-1", "acme")


async def test_get_returns_none_when_missing():
    pool = FakePool(row=None)
    repo = PostgresCollectionRepository(pool)
    assert await repo.get(TenantId("acme"), CollectionId("nope")) is None


async def test_get_handles_dict_jsonb_from_driver():
    # asyncpg may already decode JSONB to Python objects (not a str).
    pool = FakePool(row=collection_row(properties=[], views=[]))
    found = await PostgresCollectionRepository(pool).get(
        TenantId("acme"), CollectionId("col-1")
    )
    assert found.properties == ()
    assert found.views == ()


async def test_list_in_workspace_maps_rows():
    pool = FakePool(rows=[collection_row(), collection_row(id="col-2", name="Two")])
    listed = await PostgresCollectionRepository(pool).list_in_workspace(
        TenantId("acme"), WorkspaceId("ws-1")
    )

    assert [c.id for c in listed] == ["col-1", "col-2"]
    _, args = pool.calls[0]
    assert args == ("acme", "ws-1")


async def test_update_binds_name_and_jsonb_columns():
    pool = FakePool()
    await PostgresCollectionRepository(pool).update(make_collection(name="Renamed"))

    query, args = pool.calls[0]
    assert query.startswith("UPDATE collections SET")
    assert args[0] == "col-1"
    assert args[1] == "Renamed"
    assert json.loads(args[2])[0]["id"] == "p-1"
    assert json.loads(args[3])[0]["id"] == "v-1"


async def test_formula_property_round_trips_through_jsonb():
    formula_prop = PropertyDef(
        id="p-2",
        name="Total",
        type=PropertyType.FORMULA,
        formula='prop("Price") * prop("Qty")',
    )
    collection = make_collection(properties=(formula_prop,))

    # Serialize on add: the expression is written into the JSONB payload.
    pool = FakePool()
    await PostgresCollectionRepository(pool).add(collection)
    _, args = pool.calls[0]
    serialized = json.loads(args[4])[0]
    assert serialized["type"] == "formula"
    assert serialized["formula"] == 'prop("Price") * prop("Qty")'

    # Deserialize back: the expression survives.
    pool = FakePool(row=collection_row(properties=[serialized]))
    found = await PostgresCollectionRepository(pool).get(
        TenantId("acme"), CollectionId("col-1")
    )
    assert found.properties == (formula_prop,)
    assert found.properties[0].formula == 'prop("Price") * prop("Qty")'


async def test_property_without_formula_key_defaults_to_empty():
    # Rows written before formula properties existed have no "formula" key.
    legacy = {"id": "p-9", "name": "Old", "type": "text", "options": []}
    pool = FakePool(row=collection_row(properties=[legacy]))
    found = await PostgresCollectionRepository(pool).get(
        TenantId("acme"), CollectionId("col-1")
    )
    assert found.properties[0].formula == ""


async def test_relation_and_rollup_properties_round_trip_through_jsonb():
    relation = PropertyDef(
        id="p-rel", name="Tasks", type=PropertyType.RELATION,
        relation_collection_id="col-tasks",
    )
    rollup = PropertyDef(
        id="p-roll", name="Task count", type=PropertyType.ROLLUP,
        rollup_relation_property_id="p-rel", rollup_target_property_id="__title__",
        rollup_function="count",
    )
    collection = make_collection(properties=(relation, rollup))

    # Serialize on add: the relation/rollup config lands in the JSONB payload.
    pool = FakePool()
    await PostgresCollectionRepository(pool).add(collection)
    _, args = pool.calls[0]
    serialized = json.loads(args[4])
    assert serialized[0]["relation_collection_id"] == "col-tasks"
    assert serialized[1]["rollup_relation_property_id"] == "p-rel"
    assert serialized[1]["rollup_target_property_id"] == "__title__"
    assert serialized[1]["rollup_function"] == "count"

    # Deserialize back: both property definitions survive intact.
    pool = FakePool(row=collection_row(properties=serialized))
    found = await PostgresCollectionRepository(pool).get(
        TenantId("acme"), CollectionId("col-1")
    )
    assert found.properties == (relation, rollup)


async def test_relation_rollup_keys_default_to_empty_when_absent():
    # Legacy rows predate relation/rollup and lack the new keys.
    legacy = {"id": "p-9", "name": "Old", "type": "text", "options": []}
    pool = FakePool(row=collection_row(properties=[legacy]))
    found = await PostgresCollectionRepository(pool).get(
        TenantId("acme"), CollectionId("col-1")
    )
    prop = found.properties[0]
    assert prop.relation_collection_id == ""
    assert prop.rollup_relation_property_id == ""
    assert prop.rollup_target_property_id == ""
    assert prop.rollup_function == ""


async def test_date_reminder_minutes_round_trips_through_jsonb():
    date_prop = PropertyDef(
        id="p-due", name="Due", type=PropertyType.DATE, reminder_minutes=1440
    )
    collection = make_collection(properties=(date_prop,))

    # Serialize on add: the reminder lead time lands in the JSONB payload.
    pool = FakePool()
    await PostgresCollectionRepository(pool).add(collection)
    _, args = pool.calls[0]
    serialized = json.loads(args[4])[0]
    assert serialized["reminder_minutes"] == 1440

    # Deserialize back: the reminder lead time survives.
    pool = FakePool(row=collection_row(properties=[serialized]))
    found = await PostgresCollectionRepository(pool).get(
        TenantId("acme"), CollectionId("col-1")
    )
    assert found.properties == (date_prop,)
    assert found.properties[0].reminder_minutes == 1440


async def test_reminder_minutes_defaults_to_negative_one_when_absent():
    # Rows written before date reminders existed have no "reminder_minutes" key.
    legacy = {"id": "p-9", "name": "Old", "type": "date", "options": []}
    pool = FakePool(row=collection_row(properties=[legacy]))
    found = await PostgresCollectionRepository(pool).get(
        TenantId("acme"), CollectionId("col-1")
    )
    assert found.properties[0].reminder_minutes == -1


async def test_list_all_fetches_every_collection_cross_tenant():
    pool = FakePool(
        rows=[collection_row(), collection_row(id="col-2", tenant_id="globex")]
    )
    listed = await PostgresCollectionRepository(pool).list_all()

    assert [c.id for c in listed] == ["col-1", "col-2"]
    # No tenant binding — the background sweep enumerates every tenant.
    query, args = pool.calls[0]
    assert query.startswith("SELECT * FROM collections")
    assert args == ()


async def test_delete_scopes_by_tenant():
    pool = FakePool()
    await PostgresCollectionRepository(pool).delete(
        TenantId("acme"), CollectionId("col-1")
    )

    query, args = pool.calls[0]
    assert query.startswith("DELETE FROM collections")
    assert args == ("col-1", "acme")
