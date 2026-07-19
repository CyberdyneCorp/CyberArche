"""Collection use cases (collections-foundation spec).

A collection is a workspace-scoped database. Reads require workspace VIEWER and
writes require workspace EDITOR, mirroring the other workspace-scoped use cases.
Rows are documents: row creation composes DocumentUseCases so it reuses the same
access check and validation, then tags the document with its collection.
"""

from __future__ import annotations

from dataclasses import replace

from cyberarche.application.authz import AccessControl
from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.collections import CollectionRepository
from cyberarche.application.ports.repositories import DocumentRepository
from cyberarche.application.ports.telemetry import ClockPort, IdPort
from cyberarche.application.use_cases.documents import DocumentUseCases
from cyberarche.domain.collections import (
    Collection,
    Filter,
    PropertyDef,
    PropertyType,
    Sort,
    View,
    ViewKind,
    apply_view,
)
from cyberarche.domain.documents import Document
from cyberarche.domain.errors import NotFound, ValidationFailed
from cyberarche.domain.formula import Resolver, evaluate_formula, validate_formula
from cyberarche.domain.ids import CollectionId, DocumentId, WorkspaceId
from cyberarche.domain.memberships import Role

# Sentinel distinguishing "leave unchanged" from an explicit None on the
# nullable view fields (group_by / date_by).
_UNSET: object = object()


class CollectionUseCases:
    def __init__(
        self,
        collections: CollectionRepository,
        documents_repo: DocumentRepository,
        document_use_cases: DocumentUseCases,
        access: AccessControl,
        clock: ClockPort,
        ids: IdPort,
    ) -> None:
        self._collections = collections
        self._documents_repo = documents_repo
        self._document_use_cases = document_use_cases
        self._access = access
        self._clock = clock
        self._ids = ids

    # ---- collection CRUD ---------------------------------------------------

    async def create_collection(
        self, caller: CallerContext, *, workspace_id: WorkspaceId, name: str
    ) -> Collection:
        await self._access.require_workspace(caller, workspace_id, Role.EDITOR)
        collection = Collection.default(
            id=CollectionId(self._ids.new_id()),
            tenant_id=caller.tenant_id,
            workspace_id=workspace_id,
            name=name,
            view_id=self._ids.new_id(),
            created_at=self._clock.now(),
        )
        await self._collections.add(collection)
        return collection

    async def list_collections(
        self, caller: CallerContext, workspace_id: WorkspaceId
    ) -> list[Collection]:
        await self._access.require_workspace(caller, workspace_id, Role.VIEWER)
        return await self._collections.list_in_workspace(caller.tenant_id, workspace_id)

    async def get_collection(
        self, caller: CallerContext, collection_id: CollectionId
    ) -> Collection:
        return await self._require(caller, collection_id, Role.VIEWER)

    async def rename_collection(
        self, caller: CallerContext, collection_id: CollectionId, *, name: str
    ) -> Collection:
        collection = await self._require(caller, collection_id, Role.EDITOR)
        updated = collection.with_name(name)
        await self._collections.update(updated)
        return updated

    async def delete_collection(
        self, caller: CallerContext, collection_id: CollectionId
    ) -> None:
        await self._require(caller, collection_id, Role.EDITOR)
        await self._collections.delete(caller.tenant_id, collection_id)

    # ---- property schema ---------------------------------------------------

    async def add_property(
        self,
        caller: CallerContext,
        collection_id: CollectionId,
        *,
        name: str,
        type: PropertyType,
        options: tuple[str, ...] = (),
        formula: str = "",
    ) -> Collection:
        collection = await self._require(caller, collection_id, Role.EDITOR)
        is_formula = type == PropertyType.FORMULA
        if is_formula or formula:
            validate_formula(formula)
        prop = PropertyDef(
            id=self._ids.new_id(),
            name=_valid_prop_name(name),
            type=type,
            # A formula property ignores options; it carries the expression.
            options=() if is_formula else tuple(options),
            formula=formula,
        )
        updated = collection.with_properties(collection.properties + (prop,))
        await self._collections.update(updated)
        return updated

    async def update_property(
        self,
        caller: CallerContext,
        collection_id: CollectionId,
        property_id: str,
        *,
        name: str | None = None,
        options: tuple[str, ...] | None = None,
        formula: str | None = None,
    ) -> Collection:
        collection = await self._require(caller, collection_id, Role.EDITOR)
        prop = collection.property(property_id)
        if prop is None:
            raise NotFound("property not found")
        new_formula = prop.formula if formula is None else formula
        if prop.type == PropertyType.FORMULA or (formula is not None and formula):
            validate_formula(new_formula)
        edited = replace(
            prop,
            name=_valid_prop_name(name) if name is not None else prop.name,
            options=tuple(options) if options is not None else prop.options,
            formula=new_formula,
        )
        props = tuple(edited if p.id == property_id else p for p in collection.properties)
        updated = collection.with_properties(props)
        await self._collections.update(updated)
        return updated

    async def remove_property(
        self, caller: CallerContext, collection_id: CollectionId, property_id: str
    ) -> Collection:
        """Remove a property from the schema. Any value already stored on a row
        for it is left in place (harmless orphan); it simply stops being read."""
        collection = await self._require(caller, collection_id, Role.EDITOR)
        if collection.property(property_id) is None:
            raise NotFound("property not found")
        props = tuple(p for p in collection.properties if p.id != property_id)
        updated = collection.with_properties(props)
        await self._collections.update(updated)
        return updated

    # ---- views -------------------------------------------------------------

    async def create_view(
        self,
        caller: CallerContext,
        collection_id: CollectionId,
        *,
        name: str,
        kind: ViewKind,
    ) -> View:
        collection = await self._require(caller, collection_id, Role.EDITOR)
        view = View(id=self._ids.new_id(), name=name.strip() or "View", kind=kind)
        await self._collections.update(collection.with_views(collection.views + (view,)))
        return view

    async def update_view(
        self,
        caller: CallerContext,
        collection_id: CollectionId,
        view_id: str,
        *,
        name: str | None = None,
        filters: tuple[Filter, ...] | None = None,
        sorts: tuple[Sort, ...] | None = None,
        group_by: object = _UNSET,
        date_by: object = _UNSET,
    ) -> View:
        collection = await self._require(caller, collection_id, Role.EDITOR)
        view = collection.view(view_id)
        if view is None:
            raise NotFound("view not found")
        edited = replace(
            view,
            name=name if name is not None else view.name,
            filters=tuple(filters) if filters is not None else view.filters,
            sorts=tuple(sorts) if sorts is not None else view.sorts,
            group_by=view.group_by if group_by is _UNSET else group_by,
            date_by=view.date_by if date_by is _UNSET else date_by,
        )
        views = tuple(edited if v.id == view_id else v for v in collection.views)
        await self._collections.update(collection.with_views(views))
        return edited

    async def delete_view(
        self, caller: CallerContext, collection_id: CollectionId, view_id: str
    ) -> None:
        collection = await self._require(caller, collection_id, Role.EDITOR)
        if collection.view(view_id) is None:
            raise NotFound("view not found")
        if len(collection.views) <= 1:
            raise ValidationFailed("a collection must keep at least one view")
        views = tuple(v for v in collection.views if v.id != view_id)
        await self._collections.update(collection.with_views(views))

    # ---- rows --------------------------------------------------------------

    async def add_row(
        self, caller: CallerContext, collection_id: CollectionId, *, title: str = ""
    ) -> Document:
        """Create a member document for the collection. DocumentUseCases.create
        enforces workspace EDITOR and title validation; we then tag the fresh
        document with its collection and an empty property map."""
        collection = await self._require(caller, collection_id, Role.EDITOR)
        document = await self._document_use_cases.create(
            caller, workspace_id=collection.workspace_id, title=title
        )
        row = replace(
            document,
            collection_id=collection.id,
            properties={},
            updated_at=self._clock.now(),
        )
        await self._documents_repo.update(row)
        return row

    async def set_row_values(
        self,
        caller: CallerContext,
        document_id: DocumentId,
        values: dict[str, object],
    ) -> Document:
        document, collection = await self._require_row(caller, document_id)
        props = dict(document.properties)
        for property_id, value in values.items():
            prop = collection.property(property_id)
            if prop is None:
                raise ValidationFailed(f"unknown property {property_id}")
            if prop.type == PropertyType.FORMULA:
                raise ValidationFailed("formula properties are read-only")
            props[property_id] = _coerce_value(prop, value)
        updated = document.with_properties(props, now=self._clock.now())
        await self._documents_repo.update(updated)
        return updated

    async def set_row_value(
        self,
        caller: CallerContext,
        document_id: DocumentId,
        property_id: str,
        value: object,
    ) -> Document:
        return await self.set_row_values(caller, document_id, {property_id: value})

    async def remove_row(
        self, caller: CallerContext, document_id: DocumentId
    ) -> None:
        """Remove a row: trash its document (DocumentUseCases enforces EDITOR).
        The document survives in the trash and drops out of collection queries."""
        await self._document_use_cases.trash(caller, document_id)

    async def query_view(
        self, caller: CallerContext, collection_id: CollectionId, view_id: str
    ) -> list[Document]:
        collection = await self._require(caller, collection_id, Role.VIEWER)
        view = collection.view(view_id)
        if view is None:
            raise NotFound("view not found")
        rows = await self._documents_repo.list_by_collection(
            caller.tenant_id, collection.id
        )
        now = self._clock.now()
        enriched = [_compute_formulas(collection, row, now=now) for row in rows]
        return apply_view(enriched, view)

    # ---- helpers -----------------------------------------------------------

    async def _require(
        self, caller: CallerContext, collection_id: CollectionId, role: Role
    ) -> Collection:
        collection = await self._collections.get(caller.tenant_id, collection_id)
        if collection is None:
            raise NotFound("collection not found")
        await self._access.require_workspace(caller, collection.workspace_id, role)
        return collection

    async def _require_row(
        self, caller: CallerContext, document_id: DocumentId
    ) -> tuple[Document, Collection]:
        document = await self._documents_repo.get(caller.tenant_id, document_id)
        if document is None or document.trashed:
            raise NotFound("row not found")
        await self._access.require_document(caller, document, Role.EDITOR)
        if document.collection_id is None:
            raise ValidationFailed("document is not a collection row")
        collection = await self._collections.get(
            caller.tenant_id, document.collection_id
        )
        if collection is None:
            raise NotFound("collection not found")
        return document, collection


def _make_resolver(collection: Collection, row: Document) -> Resolver:
    """A `prop("Name")` resolver over a row's STORED values: `prop("Title")`
    returns the document title; any other name maps to the property of that name
    and returns the row's stored value for it (None when absent). Formula
    properties are looked up against stored values, which are empty — so a
    formula never references another formula's computed result."""
    by_name = {prop.name: prop for prop in collection.properties}

    def resolve(name: str) -> object:
        if name == "Title":
            return row.title
        prop = by_name.get(name)
        return None if prop is None else row.properties.get(prop.id)

    return resolve


def _compute_formulas(collection: Collection, row: Document, *, now) -> Document:
    """Return a row whose properties merge stored values with each formula
    property's freshly computed value. Read-only: `updated_at` is untouched."""
    formulas = [p for p in collection.properties if p.type == PropertyType.FORMULA]
    if not formulas:
        return row
    resolve = _make_resolver(collection, row)
    computed = {
        prop.id: evaluate_formula(prop.formula, resolve, now=now) for prop in formulas
    }
    return row.with_properties({**row.properties, **computed}, now=row.updated_at)


def _valid_prop_name(name: str) -> str:
    name = name.strip()
    if not name:
        raise ValidationFailed("property name must not be empty")
    return name


def _coerce_value(prop: PropertyDef, value: object) -> object:
    """Coerce/validate a raw property value by its type. Empty clears to None
    (except checkbox, which is always a bool, and multi_select, whose empty is
    a list)."""
    if prop.type == PropertyType.CHECKBOX:
        return bool(value)
    if prop.type == PropertyType.MULTI_SELECT:
        return _coerce_options(prop, value)
    if value is None or value == "":
        return None
    if prop.type == PropertyType.NUMBER:
        return _coerce_number(value)
    if prop.type == PropertyType.SELECT:
        return _coerce_option(prop, value)
    # DATE (ISO string), URL, TEXT
    return str(value)


def _coerce_number(value: object) -> float | int:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise ValidationFailed("value must be a number")
    return int(number) if number.is_integer() else number


def _coerce_option(prop: PropertyDef, value: object) -> str:
    text = str(value)
    if text not in prop.options:
        raise ValidationFailed(f"'{text}' is not an allowed option")
    return text


def _coerce_options(prop: PropertyDef, value: object) -> list[str]:
    if value is None or value == "":
        return []
    if not isinstance(value, (list, tuple)):
        raise ValidationFailed("multi_select value must be a list")
    result: list[str] = []
    for item in value:
        text = str(item)
        if text not in prop.options:
            raise ValidationFailed(f"'{text}' is not an allowed option")
        result.append(text)
    return result
