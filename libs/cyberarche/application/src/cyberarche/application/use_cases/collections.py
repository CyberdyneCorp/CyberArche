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
    TITLE_PROPERTY,
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
from cyberarche.domain.rollup import ROLLUP_FUNCTIONS, aggregate
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
        relation_collection_id: str = "",
        rollup_relation_property_id: str = "",
        rollup_target_property_id: str = "",
        rollup_function: str = "",
        reminder_minutes: int = -1,
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
            relation_collection_id=relation_collection_id,
            rollup_relation_property_id=rollup_relation_property_id,
            rollup_target_property_id=rollup_target_property_id,
            rollup_function=rollup_function,
            # A reminder is only meaningful on a DATE property; inert elsewhere.
            reminder_minutes=reminder_minutes if type == PropertyType.DATE else -1,
        )
        await self._validate_relation_rollup(caller, collection, prop)
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
        relation_collection_id: str | None = None,
        rollup_relation_property_id: str | None = None,
        rollup_target_property_id: str | None = None,
        rollup_function: str | None = None,
        reminder_minutes: int | None = None,
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
            relation_collection_id=_pick(relation_collection_id, prop.relation_collection_id),
            rollup_relation_property_id=_pick(
                rollup_relation_property_id, prop.rollup_relation_property_id
            ),
            rollup_target_property_id=_pick(
                rollup_target_property_id, prop.rollup_target_property_id
            ),
            rollup_function=_pick(rollup_function, prop.rollup_function),
            reminder_minutes=(
                prop.reminder_minutes if reminder_minutes is None else reminder_minutes
            ),
        )
        await self._validate_relation_rollup(caller, collection, edited)
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
            if prop.type == PropertyType.ROLLUP:
                raise ValidationFailed("rollup properties are read-only")
            if prop.type == PropertyType.RELATION:
                props[property_id] = await self._coerce_relation(caller, prop, value)
            else:
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

    async def delete_rows(
        self,
        caller: CallerContext,
        collection_id: CollectionId,
        document_ids: list[str],
    ) -> int:
        """Delete every id that is a non-trashed row of this collection, reusing
        the single-row trash path (which enforces EDITOR per document). Ids that
        are missing, trashed, or belong to another collection are skipped; a real
        per-row access failure (NotAuthorized) on an in-collection row propagates.
        Returns the number of rows deleted."""
        collection = await self._require(caller, collection_id, Role.VIEWER)
        rows = await self._rows_in_collection(caller, collection, document_ids)
        for row in rows:
            await self._document_use_cases.trash(caller, row.id)
        return len(rows)

    async def set_rows_value(
        self,
        caller: CallerContext,
        collection_id: CollectionId,
        document_ids: list[str],
        *,
        property_id: str,
        value: object,
    ) -> int:
        """Set one property's value on every id that is a row of this collection,
        reusing the single-row coercion/set path (which enforces EDITOR). The
        property and value are validated once up front, so a bad or read-only
        (formula/rollup) property fails fast for all. Ids not in the collection
        are skipped; a per-row access failure propagates. Returns the count set."""
        collection = await self._require(caller, collection_id, Role.VIEWER)
        prop = self._settable_property(collection, property_id)
        if prop.type != PropertyType.RELATION:
            _coerce_value(prop, value)  # fail fast on a bad value for all rows
        rows = await self._rows_in_collection(caller, collection, document_ids)
        for row in rows:
            await self.set_row_value(caller, row.id, property_id, value)
        return len(rows)

    async def query_view(
        self, caller: CallerContext, collection_id: CollectionId, view_id: str
    ) -> list[Document]:
        rows, _related = await self._query_view(caller, collection_id, view_id)
        return rows

    async def query_view_with_related(
        self, caller: CallerContext, collection_id: CollectionId, view_id: str
    ) -> tuple[list[Document], list[tuple[str, str]]]:
        """Like :meth:`query_view`, but also returns ``(id, title)`` for every
        row linked by a relation cell in the result, so the client can render
        relations by title."""
        return await self._query_view(caller, collection_id, view_id)

    async def list_rows(
        self, caller: CallerContext, collection_id: CollectionId
    ) -> list[tuple[str, str]]:
        """The non-trashed rows of a collection as ``(id, title)`` — backs the
        relation row picker. Requires workspace VIEWER."""
        collection = await self._require(caller, collection_id, Role.VIEWER)
        rows = await self._documents_repo.list_by_collection(
            caller.tenant_id, collection.id
        )
        return [(row.id, row.title) for row in rows]

    # ---- helpers -----------------------------------------------------------

    async def _query_view(
        self, caller: CallerContext, collection_id: CollectionId, view_id: str
    ) -> tuple[list[Document], list[tuple[str, str]]]:
        collection = await self._require(caller, collection_id, Role.VIEWER)
        view = collection.view(view_id)
        if view is None:
            raise NotFound("view not found")
        rows = await self._documents_repo.list_by_collection(
            caller.tenant_id, collection.id
        )
        linked = await self._load_linked(caller, collection, rows)
        now = self._clock.now()
        enriched = [self._enrich(collection, row, linked, now=now) for row in rows]
        result = apply_view(enriched, view)
        return result, _related_titles(collection, result, linked)

    def _enrich(
        self, collection: Collection, row: Document, linked: dict[str, Document], *, now
    ) -> Document:
        """Merge computed rollups then formulas onto a row's stored values.
        Rollups land before formulas, so a formula may reference a rollup."""
        rollups = _compute_rollups(collection, row, linked)
        if rollups:
            row = row.with_properties(
                {**row.properties, **rollups}, now=row.updated_at
            )
        return _compute_formulas(collection, row, now=now)

    async def _load_linked(
        self, caller: CallerContext, collection: Collection, rows: list[Document]
    ) -> dict[str, Document]:
        """Batch-load every document referenced by any relation cell across the
        rows into an ``{id: Document}`` map (deduped, non-trashed only)."""
        relation_props = [
            p for p in collection.properties if p.type == PropertyType.RELATION
        ]
        if not relation_props:
            return {}
        ids: set[str] = set()
        for row in rows:
            for prop in relation_props:
                ids.update(_linked_ids(row, prop.id))
        linked: dict[str, Document] = {}
        for doc_id in ids:
            doc = await self._documents_repo.get(caller.tenant_id, DocumentId(doc_id))
            if doc is not None and not doc.trashed:
                linked[doc_id] = doc
        return linked

    async def _coerce_relation(
        self, caller: CallerContext, prop: PropertyDef, value: object
    ) -> list[str]:
        """Coerce a relation write to the ids that are non-trashed rows of the
        target collection in the caller's tenant; drop everything else."""
        target = CollectionId(prop.relation_collection_id)
        valid: list[str] = []
        for doc_id in _as_id_list(value):
            doc = await self._documents_repo.get(caller.tenant_id, DocumentId(doc_id))
            if doc is not None and not doc.trashed and doc.collection_id == target:
                valid.append(doc_id)
        return valid

    async def _validate_relation_rollup(
        self, caller: CallerContext, collection: Collection, prop: PropertyDef
    ) -> None:
        if prop.type == PropertyType.RELATION:
            await self._validate_relation_target(caller, prop.relation_collection_id)
        elif prop.type == PropertyType.ROLLUP:
            await self._validate_rollup(caller, collection, prop)

    async def _validate_relation_target(
        self, caller: CallerContext, relation_collection_id: str
    ) -> None:
        if not relation_collection_id:
            raise ValidationFailed("a relation requires a target collection")
        target = await self._collections.get(
            caller.tenant_id, CollectionId(relation_collection_id)
        )
        if target is None:
            raise ValidationFailed("relation target collection not found")

    async def _validate_rollup(
        self, caller: CallerContext, collection: Collection, prop: PropertyDef
    ) -> None:
        if prop.rollup_function not in ROLLUP_FUNCTIONS:
            raise ValidationFailed(f"unknown rollup function {prop.rollup_function!r}")
        relation = collection.property(prop.rollup_relation_property_id)
        if relation is None or relation.type != PropertyType.RELATION:
            raise ValidationFailed("a rollup must follow a relation property")
        target = await self._collections.get(
            caller.tenant_id, CollectionId(relation.relation_collection_id)
        )
        if target is None:
            raise ValidationFailed("relation target collection not found")
        target_id = prop.rollup_target_property_id
        if target_id != TITLE_PROPERTY and target.property(target_id) is None:
            raise ValidationFailed("rollup target property not found")

    async def _require(
        self, caller: CallerContext, collection_id: CollectionId, role: Role
    ) -> Collection:
        collection = await self._collections.get(caller.tenant_id, collection_id)
        if collection is None:
            raise NotFound("collection not found")
        await self._access.require_workspace(caller, collection.workspace_id, role)
        return collection

    async def _rows_in_collection(
        self, caller: CallerContext, collection: Collection, document_ids: list[str]
    ) -> list[Document]:
        """Load the given ids and keep only the non-trashed rows of ``collection``
        (tenant-scoped; no per-row access check here — callers do that when they
        mutate). Ids that are missing, trashed, or in another collection drop out."""
        rows: list[Document] = []
        for doc_id in document_ids:
            document = await self._documents_repo.get(
                caller.tenant_id, DocumentId(doc_id)
            )
            if document is None or document.trashed:
                continue
            if document.collection_id != collection.id:
                continue
            rows.append(document)
        return rows

    def _settable_property(
        self, collection: Collection, property_id: str
    ) -> PropertyDef:
        """The property to bulk-set, or ``ValidationFailed`` if it is unknown or
        read-only (formula/rollup) — mirrors the single-row write rules."""
        prop = collection.property(property_id)
        if prop is None:
            raise ValidationFailed(f"unknown property {property_id}")
        if prop.type == PropertyType.FORMULA:
            raise ValidationFailed("formula properties are read-only")
        if prop.type == PropertyType.ROLLUP:
            raise ValidationFailed("rollup properties are read-only")
        return prop

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


def _pick(value: str | None, current: str) -> str:
    """Explicit value wins; ``None`` leaves the current value unchanged."""
    return current if value is None else value


def _linked_ids(row: Document, property_id: str) -> list[str]:
    """The stored linked-document ids of a relation cell (empty when absent)."""
    value = row.properties.get(property_id)
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item) for item in value]


def _as_id_list(value: object) -> list[str]:
    """Normalize an incoming relation write to a deduped list of id strings."""
    if value is None or value == "":
        return []
    items = value if isinstance(value, (list, tuple)) else [value]
    result: list[str] = []
    for item in items:
        if item is None or item == "":
            continue
        text = str(item)
        if text not in result:
            result.append(text)
    return result


def _target_value(doc: Document, target_property_id: str) -> object:
    if target_property_id == TITLE_PROPERTY:
        return doc.title
    return doc.properties.get(target_property_id)


def _compute_rollups(
    collection: Collection, row: Document, linked: dict[str, Document]
) -> dict[str, object]:
    """The computed value of each rollup property for a row, keyed by id."""
    rollups = [p for p in collection.properties if p.type == PropertyType.ROLLUP]
    return {p.id: _rollup_value(collection, row, p, linked) for p in rollups}


def _rollup_value(
    collection: Collection,
    row: Document,
    prop: PropertyDef,
    linked: dict[str, Document],
) -> object:
    relation = collection.property(prop.rollup_relation_property_id)
    if relation is None or relation.type != PropertyType.RELATION:
        return None
    values: list[object] = []
    for doc_id in _linked_ids(row, relation.id):
        doc = linked.get(doc_id)
        if doc is not None:
            values.append(_target_value(doc, prop.rollup_target_property_id))
    return aggregate(prop.rollup_function, values)


def _related_titles(
    collection: Collection, rows: list[Document], linked: dict[str, Document]
) -> list[tuple[str, str]]:
    """``(id, title)`` for every row linked by a relation cell in ``rows``."""
    relation_props = [
        p for p in collection.properties if p.type == PropertyType.RELATION
    ]
    seen: dict[str, str] = {}
    for row in rows:
        for prop in relation_props:
            for doc_id in _linked_ids(row, prop.id):
                doc = linked.get(doc_id)
                if doc is not None and doc_id not in seen:
                    seen[doc_id] = doc.title
    return list(seen.items())


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
