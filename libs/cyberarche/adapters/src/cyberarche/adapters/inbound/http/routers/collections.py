"""Collection endpoints (collections-foundation spec).

A collection is a workspace-scoped database; its rows are documents that open as
full pages. Routers stay thin: parse -> use case -> DTO.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from cyberarche.adapters.inbound.http.dependencies import Caller, Cases
from cyberarche.domain.collections import (
    Collection,
    Filter,
    PropertyDef,
    PropertyType,
    Sort,
    View,
    ViewKind,
)
from cyberarche.domain.documents import Document
from cyberarche.domain.ids import CollectionId, DocumentId, WorkspaceId

router = APIRouter(tags=["collections"])


# ---- DTOs ------------------------------------------------------------------


class PropertyResponse(BaseModel):
    id: str
    name: str
    type: PropertyType
    options: list[str]
    formula: str = ""
    relation_collection_id: str = ""
    rollup_relation_property_id: str = ""
    rollup_target_property_id: str = ""
    rollup_function: str = ""
    reminder_minutes: int = -1

    @staticmethod
    def from_domain(prop: PropertyDef) -> "PropertyResponse":
        return PropertyResponse(
            id=prop.id,
            name=prop.name,
            type=prop.type,
            options=list(prop.options),
            formula=prop.formula,
            relation_collection_id=prop.relation_collection_id,
            rollup_relation_property_id=prop.rollup_relation_property_id,
            rollup_target_property_id=prop.rollup_target_property_id,
            rollup_function=prop.rollup_function,
            reminder_minutes=prop.reminder_minutes,
        )


class FilterModel(BaseModel):
    property_id: str
    op: str
    value: Any | None = None


class SortModel(BaseModel):
    property_id: str
    direction: str = "asc"


class ViewResponse(BaseModel):
    id: str
    name: str
    kind: ViewKind
    filters: list[FilterModel]
    sorts: list[SortModel]
    group_by: str | None = None
    date_by: str | None = None

    @staticmethod
    def from_domain(view: View) -> "ViewResponse":
        return ViewResponse(
            id=view.id,
            name=view.name,
            kind=view.kind,
            filters=[
                FilterModel(property_id=f.property_id, op=f.op, value=f.value)
                for f in view.filters
            ],
            sorts=[
                SortModel(property_id=s.property_id, direction=s.direction)
                for s in view.sorts
            ],
            group_by=view.group_by,
            date_by=view.date_by,
        )


class CollectionResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    properties: list[PropertyResponse]
    views: list[ViewResponse]
    created_at: datetime

    @staticmethod
    def from_domain(collection: Collection) -> "CollectionResponse":
        return CollectionResponse(
            id=collection.id,
            workspace_id=collection.workspace_id,
            name=collection.name,
            properties=[PropertyResponse.from_domain(p) for p in collection.properties],
            views=[ViewResponse.from_domain(v) for v in collection.views],
            created_at=collection.created_at,
        )


class CollectionRowResponse(BaseModel):
    id: str
    workspace_id: str
    title: str
    collection_id: str | None
    properties: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def from_domain(document: Document) -> "CollectionRowResponse":
        return CollectionRowResponse(
            id=document.id,
            workspace_id=document.workspace_id,
            title=document.title,
            collection_id=document.collection_id,
            properties=dict(document.properties),
            created_at=document.created_at,
            updated_at=document.updated_at,
        )


class RelatedRowResponse(BaseModel):
    """A linked row's id + title: for the relation row picker and for rendering
    relation cells by title."""

    id: str
    title: str


class CollectionRowsResponse(BaseModel):
    """A view's rows plus the id/title of every row they link to via relations."""

    rows: list[CollectionRowResponse]
    related: list[RelatedRowResponse]


# ---- Requests --------------------------------------------------------------


class CreateCollectionRequest(BaseModel):
    name: str


class RenameCollectionRequest(BaseModel):
    name: str


class AddPropertyRequest(BaseModel):
    name: str
    type: PropertyType
    options: list[str] = []
    formula: str = ""
    relation_collection_id: str = ""
    rollup_relation_property_id: str = ""
    rollup_target_property_id: str = ""
    rollup_function: str = ""
    reminder_minutes: int = -1


class UpdatePropertyRequest(BaseModel):
    name: str | None = None
    options: list[str] | None = None
    formula: str | None = None
    relation_collection_id: str | None = None
    rollup_relation_property_id: str | None = None
    rollup_target_property_id: str | None = None
    rollup_function: str | None = None
    reminder_minutes: int | None = None


class CreateViewRequest(BaseModel):
    name: str
    kind: ViewKind = ViewKind.TABLE


class UpdateViewRequest(BaseModel):
    name: str | None = None
    filters: list[FilterModel] | None = None
    sorts: list[SortModel] | None = None
    # group_by/date_by are nullable and meaningfully settable to null (clearing
    # the grouping/date property), so "omitted" is distinguished from "set to
    # null" via model_fields_set in the handler.
    group_by: str | None = None
    date_by: str | None = None


class AddRowRequest(BaseModel):
    title: str = ""


class SetRowValuesRequest(BaseModel):
    property_id: str | None = None
    value: Any | None = None
    values: dict[str, Any] | None = None


class BulkDeleteRowsRequest(BaseModel):
    ids: list[str] = []


class BulkSetRowsRequest(BaseModel):
    ids: list[str] = []
    property_id: str
    value: Any | None = None


class BulkDeleteResponse(BaseModel):
    deleted: int


class BulkSetResponse(BaseModel):
    updated: int


# ---- collection CRUD -------------------------------------------------------


@router.post("/api/v1/workspaces/{workspace_id}/collections", status_code=201)
async def create_collection(
    workspace_id: str, body: CreateCollectionRequest, cases: Cases, caller: Caller
) -> CollectionResponse:
    collection = await cases.collections.create_collection(
        caller, workspace_id=WorkspaceId(workspace_id), name=body.name
    )
    return CollectionResponse.from_domain(collection)


@router.get("/api/v1/workspaces/{workspace_id}/collections")
async def list_collections(
    workspace_id: str, cases: Cases, caller: Caller
) -> list[CollectionResponse]:
    collections = await cases.collections.list_collections(
        caller, WorkspaceId(workspace_id)
    )
    return [CollectionResponse.from_domain(c) for c in collections]


@router.get("/api/v1/collections/{collection_id}")
async def get_collection(
    collection_id: str, cases: Cases, caller: Caller
) -> CollectionResponse:
    collection = await cases.collections.get_collection(
        caller, CollectionId(collection_id)
    )
    return CollectionResponse.from_domain(collection)


@router.patch("/api/v1/collections/{collection_id}")
async def rename_collection(
    collection_id: str, body: RenameCollectionRequest, cases: Cases, caller: Caller
) -> CollectionResponse:
    collection = await cases.collections.rename_collection(
        caller, CollectionId(collection_id), name=body.name
    )
    return CollectionResponse.from_domain(collection)


@router.delete("/api/v1/collections/{collection_id}", status_code=204)
async def delete_collection(
    collection_id: str, cases: Cases, caller: Caller
) -> None:
    await cases.collections.delete_collection(caller, CollectionId(collection_id))


# ---- property schema -------------------------------------------------------


@router.post("/api/v1/collections/{collection_id}/properties", status_code=201)
async def add_property(
    collection_id: str, body: AddPropertyRequest, cases: Cases, caller: Caller
) -> CollectionResponse:
    collection = await cases.collections.add_property(
        caller,
        CollectionId(collection_id),
        name=body.name,
        type=body.type,
        options=tuple(body.options),
        formula=body.formula,
        relation_collection_id=body.relation_collection_id,
        rollup_relation_property_id=body.rollup_relation_property_id,
        rollup_target_property_id=body.rollup_target_property_id,
        rollup_function=body.rollup_function,
        reminder_minutes=body.reminder_minutes,
    )
    return CollectionResponse.from_domain(collection)


@router.patch("/api/v1/collections/{collection_id}/properties/{property_id}")
async def update_property(
    collection_id: str,
    property_id: str,
    body: UpdatePropertyRequest,
    cases: Cases,
    caller: Caller,
) -> CollectionResponse:
    collection = await cases.collections.update_property(
        caller,
        CollectionId(collection_id),
        property_id,
        name=body.name,
        options=tuple(body.options) if body.options is not None else None,
        formula=body.formula,
        relation_collection_id=body.relation_collection_id,
        rollup_relation_property_id=body.rollup_relation_property_id,
        rollup_target_property_id=body.rollup_target_property_id,
        rollup_function=body.rollup_function,
        reminder_minutes=body.reminder_minutes,
    )
    return CollectionResponse.from_domain(collection)


@router.delete(
    "/api/v1/collections/{collection_id}/properties/{property_id}"
)
async def remove_property(
    collection_id: str, property_id: str, cases: Cases, caller: Caller
) -> CollectionResponse:
    collection = await cases.collections.remove_property(
        caller, CollectionId(collection_id), property_id
    )
    return CollectionResponse.from_domain(collection)


# ---- views -----------------------------------------------------------------


@router.post("/api/v1/collections/{collection_id}/views", status_code=201)
async def create_view(
    collection_id: str, body: CreateViewRequest, cases: Cases, caller: Caller
) -> ViewResponse:
    view = await cases.collections.create_view(
        caller, CollectionId(collection_id), name=body.name, kind=body.kind
    )
    return ViewResponse.from_domain(view)


@router.patch("/api/v1/collections/{collection_id}/views/{view_id}")
async def update_view(
    collection_id: str,
    view_id: str,
    body: UpdateViewRequest,
    cases: Cases,
    caller: Caller,
) -> ViewResponse:
    filters = (
        tuple(Filter(f.property_id, f.op, f.value) for f in body.filters)
        if body.filters is not None
        else None
    )
    sorts = (
        tuple(Sort(s.property_id, s.direction) for s in body.sorts)
        if body.sorts is not None
        else None
    )
    # Only forward group_by/date_by when the client actually sent them, so an
    # omitted field leaves the view unchanged while an explicit null clears it.
    extra: dict[str, Any] = {}
    if "group_by" in body.model_fields_set:
        extra["group_by"] = body.group_by
    if "date_by" in body.model_fields_set:
        extra["date_by"] = body.date_by
    view = await cases.collections.update_view(
        caller,
        CollectionId(collection_id),
        view_id,
        name=body.name,
        filters=filters,
        sorts=sorts,
        **extra,
    )
    return ViewResponse.from_domain(view)


@router.delete(
    "/api/v1/collections/{collection_id}/views/{view_id}", status_code=204
)
async def delete_view(
    collection_id: str, view_id: str, cases: Cases, caller: Caller
) -> None:
    await cases.collections.delete_view(caller, CollectionId(collection_id), view_id)


# ---- rows ------------------------------------------------------------------


@router.post("/api/v1/collections/{collection_id}/rows", status_code=201)
async def add_row(
    collection_id: str, body: AddRowRequest, cases: Cases, caller: Caller
) -> CollectionRowResponse:
    row = await cases.collections.add_row(
        caller, CollectionId(collection_id), title=body.title
    )
    return CollectionRowResponse.from_domain(row)


@router.get("/api/v1/collections/{collection_id}/rows")
async def list_rows(
    collection_id: str, cases: Cases, caller: Caller
) -> list[RelatedRowResponse]:
    """The collection's rows as id+title, for the relation row picker."""
    rows = await cases.collections.list_rows(caller, CollectionId(collection_id))
    return [RelatedRowResponse(id=row_id, title=title) for row_id, title in rows]


@router.get("/api/v1/collections/{collection_id}/views/{view_id}/rows")
async def query_view(
    collection_id: str, view_id: str, cases: Cases, caller: Caller
) -> CollectionRowsResponse:
    rows, related = await cases.collections.query_view_with_related(
        caller, CollectionId(collection_id), view_id
    )
    return CollectionRowsResponse(
        rows=[CollectionRowResponse.from_domain(r) for r in rows],
        related=[RelatedRowResponse(id=row_id, title=title) for row_id, title in related],
    )


@router.patch("/api/v1/collections/{collection_id}/rows/{document_id}")
async def set_row_values(
    collection_id: str,
    document_id: str,
    body: SetRowValuesRequest,
    cases: Cases,
    caller: Caller,
) -> CollectionRowResponse:
    values = dict(body.values) if body.values is not None else {}
    if body.property_id is not None:
        values[body.property_id] = body.value
    row = await cases.collections.set_row_values(caller, DocumentId(document_id), values)
    return CollectionRowResponse.from_domain(row)


@router.delete(
    "/api/v1/collections/{collection_id}/rows/{document_id}", status_code=204
)
async def delete_row(
    collection_id: str, document_id: str, cases: Cases, caller: Caller
) -> None:
    await cases.collections.remove_row(caller, DocumentId(document_id))


@router.post("/api/v1/collections/{collection_id}/rows/bulk-delete")
async def bulk_delete_rows(
    collection_id: str, body: BulkDeleteRowsRequest, cases: Cases, caller: Caller
) -> BulkDeleteResponse:
    deleted = await cases.collections.delete_rows(
        caller, CollectionId(collection_id), body.ids
    )
    return BulkDeleteResponse(deleted=deleted)


@router.post("/api/v1/collections/{collection_id}/rows/bulk-set")
async def bulk_set_rows(
    collection_id: str, body: BulkSetRowsRequest, cases: Cases, caller: Caller
) -> BulkSetResponse:
    updated = await cases.collections.set_rows_value(
        caller,
        CollectionId(collection_id),
        body.ids,
        property_id=body.property_id,
        value=body.value,
    )
    return BulkSetResponse(updated=updated)
