"""collections-formula: safe evaluator, validation gate, and use-case wiring.

Covers the pure expression evaluator (arithmetic / conditional / functions /
degrade-to-None), the security whitelist that `validate_formula` enforces, and
`CollectionUseCases` computing formula columns in `query_view` (filterable and
sortable), rejecting writes to a formula property, and rejecting bad expressions.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from cyberarche.application.use_cases import UseCases
from cyberarche.domain.collections import Filter, PropertyType, Sort
from cyberarche.domain.errors import ValidationFailed
from cyberarche.domain.formula import evaluate_formula, validate_formula

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _resolver(values: dict[str, object]):
    def resolve(name: str) -> object:
        return values.get(name)

    return resolve


# ---- pure evaluator --------------------------------------------------------


def test_arithmetic_over_props():
    resolve = _resolver({"Price": 10, "Qty": 3})
    assert evaluate_formula('prop("Price") * prop("Qty")', resolve, now=NOW) == 30
    assert evaluate_formula('prop("Price") + prop("Qty")', resolve, now=NOW) == 13
    assert evaluate_formula('prop("Price") - prop("Qty")', resolve, now=NOW) == 7
    assert evaluate_formula('prop("Price") % prop("Qty")', resolve, now=NOW) == 1
    assert evaluate_formula('prop("Qty") ** 2', resolve, now=NOW) == 9
    assert evaluate_formula("-prop(\"Qty\")", resolve, now=NOW) == -3


def test_conditional_if_function_and_ternary():
    resolve = _resolver({"Done": True})
    assert evaluate_formula('if(prop("Done"), "yes", "no")', resolve, now=NOW) == "yes"
    assert (
        evaluate_formula('if(prop("Done"), "yes", "no")', _resolver({"Done": False}), now=NOW)
        == "no"
    )
    # The Python ternary form is supported and NOT confused with the if() call.
    assert evaluate_formula('"a" if prop("Done") else "b"', resolve, now=NOW) == "a"
    # A parenthesised ternary condition stays a ternary, not a call.
    assert evaluate_formula("1 if (prop(\"Done\")) else 2", resolve, now=NOW) == 1


def test_comparisons_and_boolean_logic():
    resolve = _resolver({"Score": 7})
    assert evaluate_formula('prop("Score") > 5', resolve, now=NOW) is True
    assert evaluate_formula('prop("Score") >= 7 and prop("Score") < 10', resolve, now=NOW) is True
    assert evaluate_formula('prop("Score") < 5 or prop("Score") == 7', resolve, now=NOW) is True
    assert evaluate_formula('not (prop("Score") > 5)', resolve, now=NOW) is False


def test_dates_days_between_and_now():
    resolve = _resolver({"Due": "2026-01-11"})
    assert evaluate_formula('days_between(now(), prop("Due"))', resolve, now=NOW) == 10
    # date() parses an ISO string to a datetime; days_between is whole days.
    assert evaluate_formula('days_between(date("2026-01-01"), date("2026-01-04"))', resolve, now=NOW) == 3
    # Bad date input degrades to None.
    assert evaluate_formula('days_between(now(), prop("Missing"))', resolve, now=NOW) is None


def test_string_and_numeric_functions():
    resolve = _resolver({"First": "ab", "Qty": 3})
    assert evaluate_formula('concat(prop("First"), "-", prop("Qty"))', resolve, now=NOW) == "ab-3"
    assert evaluate_formula('length(prop("First"))', resolve, now=NOW) == 2
    assert evaluate_formula('contains(prop("First"), "a")', resolve, now=NOW) is True
    assert evaluate_formula('upper(prop("First"))', resolve, now=NOW) == "AB"
    assert evaluate_formula('lower("HELLO")', resolve, now=NOW) == "hello"
    assert evaluate_formula('round(10 / 3, 2)', resolve, now=NOW) == 3.33
    assert evaluate_formula("abs(-4)", resolve, now=NOW) == 4
    assert evaluate_formula("min(3, 1, 2)", resolve, now=NOW) == 1
    assert evaluate_formula("max(3, 1, 2)", resolve, now=NOW) == 3
    assert evaluate_formula('number("42")', resolve, now=NOW) == 42
    assert evaluate_formula('number("nope")', resolve, now=NOW) is None
    # Empty args degrade rather than raise.
    assert evaluate_formula("min()", resolve, now=NOW) is None
    assert evaluate_formula('length(prop("Missing"))', resolve, now=NOW) == 0


def test_degrades_to_none_on_bad_input():
    resolve = _resolver({"Price": 10})
    # Missing prop.
    assert evaluate_formula('prop("Missing") * 2', resolve, now=NOW) is None
    # Divide / modulo by zero.
    assert evaluate_formula('prop("Price") / 0', resolve, now=NOW) is None
    assert evaluate_formula('prop("Price") % 0', resolve, now=NOW) is None
    # Type error (string times string via +).
    assert evaluate_formula('prop("Missing") - 1', resolve, now=NOW) is None


def test_title_and_constants():
    def resolve(name: str) -> object:
        return "My Title" if name == "Title" else None

    assert evaluate_formula('prop("Title")', resolve, now=NOW) == "My Title"
    assert evaluate_formula("True and False", resolve, now=NOW) is False
    assert evaluate_formula("None", resolve, now=NOW) is None


# ---- security: the validation whitelist ------------------------------------


@pytest.mark.parametrize(
    "expr",
    [
        '__import__("os")',
        "prop.__class__",
        'prop("x").__class__',
        "os",
        "x[0]",
        "lambda: 1",
        "[1, 2, 3]",
        "(1, 2)",
        "{1: 2}",
        "{1, 2}",
        "[n for n in range(3)]",
        "foo(1)",
        "open('/etc/passwd')",
        "round(1, n=2)",
        "prop('x') := 1",
        "1;2",
    ],
)
def test_validate_rejects_unsafe_or_unsupported(expr: str):
    with pytest.raises(ValidationFailed):
        validate_formula(expr)


def test_validate_rejects_syntax_error():
    with pytest.raises(ValidationFailed):
        validate_formula("prop(")


def test_validate_rejects_unterminated_string():
    # Exercises the tokenizer-error fallback in the source rewrite.
    with pytest.raises(ValidationFailed):
        validate_formula('concat("oops')


def test_evaluate_bare_name_does_not_execute():
    # A raw name never reaches a handler (it isn't whitelisted); it surfaces as
    # a ValidationFailed rather than resolving to anything.
    with pytest.raises(ValidationFailed):
        evaluate_formula("os", _resolver({}), now=NOW)


def test_evaluator_value_edge_cases():
    resolve = _resolver({"N": 3})
    # length() of a non-string stringifies first.
    assert evaluate_formula('length(prop("N"))', resolve, now=NOW) == 1
    # date() of a non-date/non-string argument degrades to None.
    assert evaluate_formula("date(123)", resolve, now=NOW) is None
    # days_between with an unparseable ISO string degrades to None.
    assert evaluate_formula('days_between("garbage", now())', resolve, now=NOW) is None
    # `or` returns the last (falsy) operand when nothing is truthy.
    assert evaluate_formula("0 or None", resolve, now=NOW) is None
    # number() passes numeric input straight through.
    assert evaluate_formula('number(prop("N"))', resolve, now=NOW) == 3


def test_validate_accepts_supported_forms():
    for expr in [
        'prop("Price") * prop("Qty") + 1',
        'if(prop("Done"), "yes", "no")',
        '"a" if prop("Done") else "b"',
        'days_between(now(), prop("Due"))',
        'concat(prop("A"), upper(prop("B")))',
        "min(1, 2, max(3, 4))",
    ]:
        validate_formula(expr)  # must not raise


def test_evaluate_never_executes_unsafe_call():
    # Even if evaluation were reached, an unwhitelisted call surfaces as a
    # ValidationFailed rather than running anything.
    with pytest.raises(ValidationFailed):
        evaluate_formula('__import__("os")', _resolver({}), now=NOW)


# ---- use case --------------------------------------------------------------


async def _collection_with_number(use_cases: UseCases, alice):
    ws = await use_cases.workspaces.create(alice, name="WS")
    col = await use_cases.collections.create_collection(alice, workspace_id=ws.id, name="C")
    col = await use_cases.collections.add_property(
        alice, col.id, name="Price", type=PropertyType.NUMBER
    )
    col = await use_cases.collections.add_property(
        alice, col.id, name="Qty", type=PropertyType.NUMBER
    )
    return col


async def test_add_formula_property_persists_expression(use_cases: UseCases, alice):
    col = await _collection_with_number(use_cases, alice)
    col = await use_cases.collections.add_property(
        alice,
        col.id,
        name="Total",
        type=PropertyType.FORMULA,
        formula='prop("Price") * prop("Qty")',
    )
    total = col.properties[-1]
    assert total.type is PropertyType.FORMULA
    assert total.formula == 'prop("Price") * prop("Qty")'
    # Options are ignored for a formula property.
    assert total.options == ()


async def test_add_formula_property_rejects_invalid_expression(use_cases: UseCases, alice):
    col = await _collection_with_number(use_cases, alice)
    with pytest.raises(ValidationFailed):
        await use_cases.collections.add_property(
            alice, col.id, name="Bad", type=PropertyType.FORMULA, formula='__import__("os")'
        )


async def test_update_property_revalidates_formula(use_cases: UseCases, alice):
    col = await _collection_with_number(use_cases, alice)
    col = await use_cases.collections.add_property(
        alice, col.id, name="Total", type=PropertyType.FORMULA, formula='prop("Price")'
    )
    total_id = col.properties[-1].id

    col = await use_cases.collections.update_property(
        alice, col.id, total_id, formula='prop("Price") * prop("Qty")'
    )
    assert col.properties[-1].formula == 'prop("Price") * prop("Qty")'

    with pytest.raises(ValidationFailed):
        await use_cases.collections.update_property(
            alice, col.id, total_id, formula="prop.__class__"
        )


async def test_query_view_includes_computed_formula(use_cases: UseCases, alice):
    col = await _collection_with_number(use_cases, alice)
    price, qty = col.properties[0].id, col.properties[1].id
    col = await use_cases.collections.add_property(
        alice, col.id, name="Total", type=PropertyType.FORMULA,
        formula='prop("Price") * prop("Qty")',
    )
    total = col.properties[-1].id

    row = await use_cases.collections.add_row(alice, col.id, title="Widget")
    await use_cases.collections.set_row_values(alice, row.id, {price: 10, qty: 3})

    rows = await use_cases.collections.query_view(alice, col.id, col.views[0].id)
    assert rows[0].properties[total] == 30


async def test_query_view_can_filter_and_sort_on_formula(use_cases: UseCases, alice):
    col = await _collection_with_number(use_cases, alice)
    price, qty = col.properties[0].id, col.properties[1].id
    col = await use_cases.collections.add_property(
        alice, col.id, name="Total", type=PropertyType.FORMULA,
        formula='prop("Price") * prop("Qty")',
    )
    total = col.properties[-1].id

    a = await use_cases.collections.add_row(alice, col.id, title="A")
    b = await use_cases.collections.add_row(alice, col.id, title="B")
    c = await use_cases.collections.add_row(alice, col.id, title="C")
    await use_cases.collections.set_row_values(alice, a.id, {price: 10, qty: 1})  # 10
    await use_cases.collections.set_row_values(alice, b.id, {price: 10, qty: 5})  # 50
    await use_cases.collections.set_row_values(alice, c.id, {price: 10, qty: 3})  # 30

    # Filter on the computed column: Total > 20 keeps B and C.
    view = await use_cases.collections.update_view(
        alice, col.id, col.views[0].id,
        filters=(Filter(total, "gt", 20),),
        sorts=(Sort(total, "desc"),),
    )
    rows = await use_cases.collections.query_view(alice, col.id, view.id)
    assert [r.title for r in rows] == ["B", "C"]  # 50 before 30

    # Ascending sort by the computed column across all rows.
    view = await use_cases.collections.update_view(
        alice, col.id, view.id, filters=(), sorts=(Sort(total, "asc"),)
    )
    rows = await use_cases.collections.query_view(alice, col.id, view.id)
    assert [r.title for r in rows] == ["A", "C", "B"]  # 10, 30, 50


async def test_setting_a_formula_value_is_rejected(use_cases: UseCases, alice):
    col = await _collection_with_number(use_cases, alice)
    col = await use_cases.collections.add_property(
        alice, col.id, name="Total", type=PropertyType.FORMULA,
        formula='prop("Price") * prop("Qty")',
    )
    total = col.properties[-1].id
    row = await use_cases.collections.add_row(alice, col.id, title="X")

    with pytest.raises(ValidationFailed):
        await use_cases.collections.set_row_value(alice, row.id, total, 999)


async def test_formula_cell_degrades_to_none_without_inputs(use_cases: UseCases, alice):
    col = await _collection_with_number(use_cases, alice)
    col = await use_cases.collections.add_property(
        alice, col.id, name="Total", type=PropertyType.FORMULA,
        formula='prop("Price") * prop("Qty")',
    )
    total = col.properties[-1].id
    # A row with no Price/Qty values: the formula degrades to None (blank).
    await use_cases.collections.add_row(alice, col.id, title="Empty")

    rows = await use_cases.collections.query_view(alice, col.id, col.views[0].id)
    assert rows[0].properties[total] is None


async def test_formula_can_reference_the_title(use_cases: UseCases, alice):
    ws = await use_cases.workspaces.create(alice, name="WS")
    col = await use_cases.collections.create_collection(alice, workspace_id=ws.id, name="C")
    col = await use_cases.collections.add_property(
        alice, col.id, name="Upper", type=PropertyType.FORMULA, formula='upper(prop("Title"))'
    )
    upper = col.properties[-1].id
    await use_cases.collections.add_row(alice, col.id, title="widget")

    rows = await use_cases.collections.query_view(alice, col.id, col.views[0].id)
    assert rows[0].properties[upper] == "WIDGET"
