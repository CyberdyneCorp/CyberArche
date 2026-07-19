"""Collection aggregate (collections-foundation spec).

A collection is a Notion-style database: a named property schema plus one or
more named views over its rows. A row IS a full Document (blocks, comments,
permissions) that additionally carries typed property values, so this module
never stores rows itself — it only describes the schema/views and provides the
pure `apply_view` query over Documents handed in by the application layer.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from cyberarche.domain.documents import Document
from cyberarche.domain.errors import ValidationFailed
from cyberarche.domain.ids import CollectionId, TenantId, WorkspaceId

MAX_NAME_LENGTH = 200

# The special property id that reads a row's document title instead of a stored
# property value. Sorts and filters may target it.
TITLE_PROPERTY = "__title__"

# Supported filter operators.
FILTER_OPS = frozenset(
    {"eq", "neq", "contains", "gt", "lt", "is_empty", "not_empty"}
)


class PropertyType(StrEnum):
    TEXT = "text"
    NUMBER = "number"
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    DATE = "date"
    CHECKBOX = "checkbox"
    URL = "url"
    # Read-only, server-computed from `PropertyDef.formula` (collections-formula).
    FORMULA = "formula"
    # Links to rows of another collection (collections-relations-rollups). The
    # stored value is a list of linked document ids.
    RELATION = "relation"
    # Read-only, server-computed aggregate over a relation's linked rows.
    ROLLUP = "rollup"


class ViewKind(StrEnum):
    TABLE = "table"
    BOARD = "board"
    GALLERY = "gallery"
    CALENDAR = "calendar"


@dataclass(frozen=True, slots=True)
class PropertyDef:
    id: str
    name: str
    type: PropertyType
    # Allowed options for select / multi_select; empty for other types.
    options: tuple[str, ...] = ()
    # Expression for a FORMULA property; empty string for every other type.
    formula: str = ""
    # RELATION: the target collection whose rows this property links to.
    relation_collection_id: str = ""
    # ROLLUP: which RELATION property on THIS collection to follow.
    rollup_relation_property_id: str = ""
    # ROLLUP: which property on the target collection to aggregate. The special
    # value TITLE_PROPERTY (``"__title__"``) aggregates the linked row's title.
    rollup_target_property_id: str = ""
    # ROLLUP: the aggregation function (see domain.rollup.ROLLUP_FUNCTIONS).
    rollup_function: str = ""


@dataclass(frozen=True, slots=True)
class Filter:
    property_id: str
    op: str
    value: object | None = None


@dataclass(frozen=True, slots=True)
class Sort:
    property_id: str
    direction: str = "asc"  # "asc" | "desc"


@dataclass(frozen=True, slots=True)
class View:
    id: str
    name: str
    kind: ViewKind
    filters: tuple[Filter, ...] = ()
    sorts: tuple[Sort, ...] = ()
    group_by: str | None = None
    date_by: str | None = None


@dataclass(frozen=True, slots=True)
class Collection:
    id: CollectionId
    tenant_id: TenantId
    workspace_id: WorkspaceId
    name: str
    properties: tuple[PropertyDef, ...]
    views: tuple[View, ...]
    created_at: datetime

    @classmethod
    def default(
        cls,
        *,
        id: CollectionId,
        tenant_id: TenantId,
        workspace_id: WorkspaceId,
        name: str,
        view_id: str,
        created_at: datetime,
    ) -> "Collection":
        """A new collection: an empty schema and one default table view."""
        table = View(id=view_id, name="Table", kind=ViewKind.TABLE)
        return cls(
            id=id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            name=_valid_name(name),
            properties=(),
            views=(table,),
            created_at=created_at,
        )

    def with_name(self, name: str) -> "Collection":
        return replace(self, name=_valid_name(name))

    def with_properties(self, properties: tuple[PropertyDef, ...]) -> "Collection":
        return replace(self, properties=properties)

    def with_views(self, views: tuple[View, ...]) -> "Collection":
        return replace(self, views=views)

    def property(self, property_id: str) -> PropertyDef | None:
        for prop in self.properties:
            if prop.id == property_id:
                return prop
        return None

    def view(self, view_id: str) -> View | None:
        for view in self.views:
            if view.id == view_id:
                return view
        return None


def _valid_name(name: str) -> str:
    name = name.strip()
    if not name:
        raise ValidationFailed("collection name must not be empty")
    if len(name) > MAX_NAME_LENGTH:
        raise ValidationFailed(f"collection name exceeds {MAX_NAME_LENGTH} characters")
    return name


# ---- Pure view query --------------------------------------------------------


def apply_view(rows: list[Document], view: View) -> list[Document]:
    """Filter rows by ALL of the view's filters (AND), then apply its sorts in
    order as a stable multi-key sort. Pure: no I/O, no mutation."""
    filtered = [row for row in rows if _matches_all(row, view.filters)]
    for sort in reversed(view.sorts):
        reverse = sort.direction == "desc"
        filtered.sort(key=lambda row, s=sort: _sort_key(row, s.property_id), reverse=reverse)
    return filtered


def _row_value(row: Document, property_id: str) -> object:
    if property_id == TITLE_PROPERTY:
        return row.title
    return row.properties.get(property_id)


def _matches_all(row: Document, filters: tuple[Filter, ...]) -> bool:
    return all(_matches(row, f) for f in filters)


def _is_empty(value: object) -> bool:
    return value is None or value == "" or value == []


def _matches(row: Document, flt: Filter) -> bool:
    value = _row_value(row, flt.property_id)
    if flt.op == "is_empty":
        return _is_empty(value)
    if flt.op == "not_empty":
        return not _is_empty(value)
    if flt.op == "contains":
        return _contains(value, flt.value)
    if flt.op == "eq":
        return _compare(value, flt.value) == 0
    if flt.op == "neq":
        return _compare(value, flt.value) != 0
    if flt.op == "gt":
        return _compare(value, flt.value) > 0
    if flt.op == "lt":
        return _compare(value, flt.value) < 0
    return False


def _contains(value: object, needle: object) -> bool:
    """Membership for multi_select lists; case-insensitive substring for text."""
    if isinstance(value, (list, tuple)):
        return needle in value
    if value is None:
        return False
    return str(needle).lower() in str(value).lower()


def _as_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _compare(left: object, right: object) -> int:
    """Three-way compare: numeric when both parse as numbers, else
    case-insensitive string compare. Missing values sort before present ones."""
    left_num, right_num = _as_number(left), _as_number(right)
    if left_num is not None and right_num is not None:
        return (left_num > right_num) - (left_num < right_num)
    left_str = "" if left is None else str(left).lower()
    right_str = "" if right is None else str(right).lower()
    return (left_str > right_str) - (left_str < right_str)


def _sort_key(row: Document, property_id: str) -> tuple[int, float, str]:
    """A total ordering key: (present-flag, number, string). Empty values sort
    first; numbers compare numerically, everything else lexicographically."""
    value = _row_value(row, property_id)
    if _is_empty(value):
        return (0, 0.0, "")
    number = _as_number(value)
    if number is not None:
        return (1, number, "")
    return (2, 0.0, str(value).lower())
