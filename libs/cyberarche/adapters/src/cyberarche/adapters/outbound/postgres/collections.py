"""CollectionRepository adapter over the collections table.

The property schema and views are stored as two JSONB columns; this module owns
the row<->aggregate mapping only.
"""

from __future__ import annotations

import json
from typing import Any

import asyncpg

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


def _property_to_dict(prop: PropertyDef) -> dict[str, Any]:
    return {
        "id": prop.id,
        "name": prop.name,
        "type": prop.type.value,
        "options": list(prop.options),
        "formula": prop.formula,
        "relation_collection_id": prop.relation_collection_id,
        "rollup_relation_property_id": prop.rollup_relation_property_id,
        "rollup_target_property_id": prop.rollup_target_property_id,
        "rollup_function": prop.rollup_function,
        "reminder_minutes": prop.reminder_minutes,
    }


def _property_from_dict(data: dict[str, Any]) -> PropertyDef:
    return PropertyDef(
        id=data["id"],
        name=data["name"],
        type=PropertyType(data["type"]),
        options=tuple(data.get("options") or ()),
        # Absent on rows written before formula properties existed.
        formula=data.get("formula") or "",
        # Absent on rows written before relation/rollup properties existed.
        relation_collection_id=data.get("relation_collection_id") or "",
        rollup_relation_property_id=data.get("rollup_relation_property_id") or "",
        rollup_target_property_id=data.get("rollup_target_property_id") or "",
        rollup_function=data.get("rollup_function") or "",
        # Absent on rows written before date reminders existed => no reminder.
        reminder_minutes=data.get("reminder_minutes", -1),
    )


def _view_to_dict(view: View) -> dict[str, Any]:
    return {
        "id": view.id,
        "name": view.name,
        "kind": view.kind.value,
        "filters": [
            {"property_id": f.property_id, "op": f.op, "value": f.value}
            for f in view.filters
        ],
        "sorts": [
            {"property_id": s.property_id, "direction": s.direction}
            for s in view.sorts
        ],
        "group_by": view.group_by,
        "date_by": view.date_by,
    }


def _view_from_dict(data: dict[str, Any]) -> View:
    return View(
        id=data["id"],
        name=data["name"],
        kind=ViewKind(data["kind"]),
        filters=tuple(
            Filter(property_id=f["property_id"], op=f["op"], value=f.get("value"))
            for f in data.get("filters") or ()
        ),
        sorts=tuple(
            Sort(property_id=s["property_id"], direction=s.get("direction", "asc"))
            for s in data.get("sorts") or ()
        ),
        group_by=data.get("group_by"),
        date_by=data.get("date_by"),
    )


def _loads(raw: Any) -> list:
    if raw is None:
        return []
    if isinstance(raw, str):
        raw = json.loads(raw)
    return list(raw)


def _from_row(row: asyncpg.Record) -> Collection:
    return Collection(
        id=CollectionId(row["id"]),
        tenant_id=TenantId(row["tenant_id"]),
        workspace_id=WorkspaceId(row["workspace_id"]),
        name=row["name"],
        properties=tuple(_property_from_dict(p) for p in _loads(row["properties"])),
        views=tuple(_view_from_dict(v) for v in _loads(row["views"])),
        created_at=row["created_at"],
    )


def _properties_json(collection: Collection) -> str:
    return json.dumps([_property_to_dict(p) for p in collection.properties])


def _views_json(collection: Collection) -> str:
    return json.dumps([_view_to_dict(v) for v in collection.views])


class PostgresCollectionRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def add(self, collection: Collection) -> None:
        await self._pool.execute(
            """
            INSERT INTO collections
                (id, tenant_id, workspace_id, name, properties, views, created_at)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7)
            """,
            collection.id,
            collection.tenant_id,
            collection.workspace_id,
            collection.name,
            _properties_json(collection),
            _views_json(collection),
            collection.created_at,
        )

    async def get(
        self, tenant_id: TenantId, collection_id: CollectionId
    ) -> Collection | None:
        row = await self._pool.fetchrow(
            "SELECT * FROM collections WHERE id = $1 AND tenant_id = $2",
            collection_id,
            tenant_id,
        )
        return _from_row(row) if row else None

    async def list_in_workspace(
        self, tenant_id: TenantId, workspace_id: WorkspaceId
    ) -> list[Collection]:
        rows = await self._pool.fetch(
            """
            SELECT * FROM collections
            WHERE tenant_id = $1 AND workspace_id = $2
            ORDER BY created_at
            """,
            tenant_id,
            workspace_id,
        )
        return [_from_row(r) for r in rows]

    async def list_all(self) -> list[Collection]:
        rows = await self._pool.fetch(
            "SELECT * FROM collections ORDER BY created_at"
        )
        return [_from_row(r) for r in rows]

    async def update(self, collection: Collection) -> None:
        await self._pool.execute(
            """
            UPDATE collections SET
                name = $2, properties = $3::jsonb, views = $4::jsonb
            WHERE id = $1
            """,
            collection.id,
            collection.name,
            _properties_json(collection),
            _views_json(collection),
        )

    async def delete(
        self, tenant_id: TenantId, collection_id: CollectionId
    ) -> None:
        await self._pool.execute(
            "DELETE FROM collections WHERE id = $1 AND tenant_id = $2",
            collection_id,
            tenant_id,
        )
