"""Rollup aggregation for collections (collections-relations-rollups).

A rollup property aggregates a chosen target value across the rows reached
through a relation property. This module is pure: the use case gathers the
target-property value of each linked row (one entry per link, ``None`` when the
row has no such value) and calls :func:`aggregate` with the chosen function.

``count`` therefore counts the *links* (the length of the supplied list),
independent of the target values; the numeric/date functions ignore entries
they cannot interpret.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime

# The aggregation functions a rollup may use.
ROLLUP_FUNCTIONS = frozenset(
    {"count", "sum", "average", "min", "max", "earliest", "latest", "list"}
)


def aggregate(function: str, values: list[object]) -> object:
    """Aggregate ``values`` (one entry per linked row) with ``function``.

    An unknown function yields ``None``. ``count`` returns the number of links;
    sum/average/min/max operate over the numeric entries (ignoring the rest);
    earliest/latest over parseable ISO dates; list joins the distinct non-empty
    stringified entries with ``", "``.
    """
    handler = _HANDLERS.get(function)
    return None if handler is None else handler(values)


def _to_number(value: object) -> float | int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            parsed = float(value)
        except ValueError:
            return None
        return int(parsed) if parsed.is_integer() else parsed
    return None


def _to_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=UTC)
    if not isinstance(value, str):
        return None
    text = value.strip()
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    try:
        parsed = date.fromisoformat(text)
    except ValueError:
        return None
    return datetime(parsed.year, parsed.month, parsed.day, tzinfo=UTC)


def _numbers(values: list[object]) -> list[float | int]:
    return [n for n in (_to_number(v) for v in values) if n is not None]


def _count(values: list[object]) -> object:
    return len(values)


def _sum(values: list[object]) -> object:
    return sum(_numbers(values))


def _average(values: list[object]) -> object:
    numbers = _numbers(values)
    return sum(numbers) / len(numbers) if numbers else None


def _min(values: list[object]) -> object:
    numbers = _numbers(values)
    return min(numbers) if numbers else None


def _max(values: list[object]) -> object:
    numbers = _numbers(values)
    return max(numbers) if numbers else None


def _pick_date(values: list[object], *, earliest: bool) -> object:
    dated = [(dt, v) for v in values if (dt := _to_datetime(v)) is not None]
    if not dated:
        return None
    chooser = min if earliest else max
    return chooser(dated, key=lambda pair: pair[0])[1]


def _earliest(values: list[object]) -> object:
    return _pick_date(values, earliest=True)


def _latest(values: list[object]) -> object:
    return _pick_date(values, earliest=False)


def _list(values: list[object]) -> object:
    seen: list[str] = []
    for value in values:
        if value is None or value == "":
            continue
        text = str(value)
        if text not in seen:
            seen.append(text)
    return ", ".join(seen)


_HANDLERS: dict[str, Callable[[list[object]], object]] = {
    "count": _count,
    "sum": _sum,
    "average": _average,
    "min": _min,
    "max": _max,
    "earliest": _earliest,
    "latest": _latest,
    "list": _list,
}
