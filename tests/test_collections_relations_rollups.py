"""collections-relations-rollups: pure aggregation, relation coercion/validation,
rollup compute in query_view, linked-title resolution, and read-only rollups."""

from __future__ import annotations

import pytest

from cyberarche.application.use_cases import UseCases
from cyberarche.domain.collections import TITLE_PROPERTY, PropertyType
from cyberarche.domain.errors import ValidationFailed
from cyberarche.domain.rollup import ROLLUP_FUNCTIONS, aggregate

# ---- pure aggregation ------------------------------------------------------


def test_aggregate_count_counts_links_regardless_of_value():
    # One entry per linked row; count ignores the values themselves.
    assert aggregate("count", [None, 5, "x"]) == 3
    assert aggregate("count", []) == 0


def test_aggregate_numeric_functions_ignore_non_numeric():
    values = [10, "5", None, "x", 3]
    assert aggregate("sum", values) == 18
    assert aggregate("min", values) == 3
    assert aggregate("max", values) == 10
    assert aggregate("average", [2, 4, "x"]) == 3
    # Empty numeric input: sum -> 0, the rest -> None.
    assert aggregate("sum", ["x", None]) == 0
    assert aggregate("average", []) is None
    assert aggregate("min", []) is None
    assert aggregate("max", []) is None


def test_aggregate_dates_earliest_and_latest():
    values = ["2026-03-01", "2026-01-15", "garbage", None, "2026-02-20"]
    assert aggregate("earliest", values) == "2026-01-15"
    assert aggregate("latest", values) == "2026-03-01"
    # Datetime strings parse too.
    assert aggregate("latest", ["2026-01-01T09:00:00", "2026-01-01T18:00:00"]) == (
        "2026-01-01T18:00:00"
    )
    # Nothing parseable -> None.
    assert aggregate("earliest", ["nope"]) is None


def test_aggregate_list_joins_distinct_non_empty():
    assert aggregate("list", ["a", "b", "a", None, "", "c"]) == "a, b, c"
    assert aggregate("list", [1, 2, 1]) == "1, 2"
    assert aggregate("list", [None, ""]) == ""


def test_aggregate_unknown_function_is_none():
    assert aggregate("median", [1, 2, 3]) is None
    assert aggregate("", []) is None
    assert ROLLUP_FUNCTIONS >= {"count", "sum", "list"}


# ---- use-case fixtures -----------------------------------------------------


async def _projects_and_tasks(use_cases: UseCases, alice):
    """Two collections: Tasks (with an Hours number + Due date) and Projects
    (with a relation to Tasks)."""
    ws = await use_cases.workspaces.create(alice, name="WS")
    tasks = await use_cases.collections.create_collection(
        alice, workspace_id=ws.id, name="Tasks"
    )
    tasks = await use_cases.collections.add_property(
        alice, tasks.id, name="Hours", type=PropertyType.NUMBER
    )
    tasks = await use_cases.collections.add_property(
        alice, tasks.id, name="Due", type=PropertyType.DATE
    )
    projects = await use_cases.collections.create_collection(
        alice, workspace_id=ws.id, name="Projects"
    )
    projects = await use_cases.collections.add_property(
        alice, projects.id, name="Tasks", type=PropertyType.RELATION,
        relation_collection_id=tasks.id,
    )
    return ws, projects, tasks


def _prop_id(collection, name: str) -> str:
    return next(p.id for p in collection.properties if p.name == name)


# ---- relation property validation ------------------------------------------


async def test_add_relation_property_persists_valid_target(use_cases: UseCases, alice):
    _ws, projects, tasks = await _projects_and_tasks(use_cases, alice)
    rel = projects.properties[-1]
    assert rel.type is PropertyType.RELATION
    assert rel.relation_collection_id == tasks.id


async def test_add_relation_property_rejects_missing_target(use_cases: UseCases, alice):
    ws = await use_cases.workspaces.create(alice, name="WS")
    col = await use_cases.collections.create_collection(
        alice, workspace_id=ws.id, name="C"
    )
    with pytest.raises(ValidationFailed):
        await use_cases.collections.add_property(
            alice, col.id, name="Bad", type=PropertyType.RELATION,
            relation_collection_id="does-not-exist",
        )
    with pytest.raises(ValidationFailed):
        await use_cases.collections.add_property(
            alice, col.id, name="Bad2", type=PropertyType.RELATION,
        )


# ---- rollup property validation --------------------------------------------


async def _projects_with_rollups(use_cases: UseCases, alice):
    ws, projects, tasks = await _projects_and_tasks(use_cases, alice)
    rel_id = _prop_id(projects, "Tasks")
    hours_id = _prop_id(tasks, "Hours")
    projects = await use_cases.collections.add_property(
        alice, projects.id, name="Task count", type=PropertyType.ROLLUP,
        rollup_relation_property_id=rel_id, rollup_target_property_id=TITLE_PROPERTY,
        rollup_function="count",
    )
    projects = await use_cases.collections.add_property(
        alice, projects.id, name="Total hours", type=PropertyType.ROLLUP,
        rollup_relation_property_id=rel_id, rollup_target_property_id=hours_id,
        rollup_function="sum",
    )
    return ws, projects, tasks


async def test_add_rollup_property_persists_valid_config(use_cases: UseCases, alice):
    _ws, projects, _tasks = await _projects_with_rollups(use_cases, alice)
    total = next(p for p in projects.properties if p.name == "Total hours")
    assert total.type is PropertyType.ROLLUP
    assert total.rollup_function == "sum"
    assert total.rollup_relation_property_id == _prop_id(projects, "Tasks")


async def test_add_rollup_property_rejects_bad_config(use_cases: UseCases, alice):
    _ws, projects, tasks = await _projects_and_tasks(use_cases, alice)
    rel_id = _prop_id(projects, "Tasks")
    hours_id = _prop_id(tasks, "Hours")

    # Unknown aggregation function.
    with pytest.raises(ValidationFailed):
        await use_cases.collections.add_property(
            alice, projects.id, name="R", type=PropertyType.ROLLUP,
            rollup_relation_property_id=rel_id,
            rollup_target_property_id=hours_id, rollup_function="median",
        )
    # Source is not a relation property (points at a number column).
    non_relation = await use_cases.collections.add_property(
        alice, projects.id, name="Budget", type=PropertyType.NUMBER
    )
    budget_id = _prop_id(non_relation, "Budget")
    with pytest.raises(ValidationFailed):
        await use_cases.collections.add_property(
            alice, projects.id, name="R2", type=PropertyType.ROLLUP,
            rollup_relation_property_id=budget_id,
            rollup_target_property_id=hours_id, rollup_function="sum",
        )
    # Target property does not exist on the target collection.
    with pytest.raises(ValidationFailed):
        await use_cases.collections.add_property(
            alice, projects.id, name="R3", type=PropertyType.ROLLUP,
            rollup_relation_property_id=rel_id,
            rollup_target_property_id="nope", rollup_function="sum",
        )


# ---- relation value coercion -----------------------------------------------


async def test_relation_coercion_keeps_only_valid_links(use_cases: UseCases, alice):
    ws, projects, tasks = await _projects_and_tasks(use_cases, alice)
    rel_id = _prop_id(projects, "Tasks")

    t1 = await use_cases.collections.add_row(alice, tasks.id, title="T1")
    t2 = await use_cases.collections.add_row(alice, tasks.id, title="T2")
    trashed = await use_cases.collections.add_row(alice, tasks.id, title="Gone")
    await use_cases.collections.remove_row(alice, trashed.id)

    # A row of another collection (wrong collection_id) is not a valid link.
    other = await use_cases.collections.create_collection(
        alice, workspace_id=ws.id, name="Other"
    )
    other_row = await use_cases.collections.add_row(alice, other.id, title="X")

    project = await use_cases.collections.add_row(alice, projects.id, title="P")
    updated = await use_cases.collections.set_row_value(
        alice, project.id, rel_id,
        [t1.id, t2.id, trashed.id, other_row.id, "bogus-id"],
    )
    assert updated.properties[rel_id] == [t1.id, t2.id]


async def test_setting_a_rollup_value_is_rejected(use_cases: UseCases, alice):
    _ws, projects, _tasks = await _projects_with_rollups(use_cases, alice)
    rollup_id = _prop_id(projects, "Task count")
    project = await use_cases.collections.add_row(alice, projects.id, title="P")
    with pytest.raises(ValidationFailed):
        await use_cases.collections.set_row_value(alice, project.id, rollup_id, 5)


# ---- rollup compute + related titles in query_view -------------------------


async def test_query_view_computes_rollups_and_returns_related(
    use_cases: UseCases, alice
):
    ws, projects, tasks = await _projects_with_rollups(use_cases, alice)
    rel_id = _prop_id(projects, "Tasks")
    hours_id = _prop_id(tasks, "Hours")
    count_id = _prop_id(projects, "Task count")
    total_id = _prop_id(projects, "Total hours")

    t1 = await use_cases.collections.add_row(alice, tasks.id, title="Design")
    t2 = await use_cases.collections.add_row(alice, tasks.id, title="Build")
    await use_cases.collections.set_row_value(alice, t1.id, hours_id, 3)
    await use_cases.collections.set_row_value(alice, t2.id, hours_id, 5)

    project = await use_cases.collections.add_row(alice, projects.id, title="Launch")
    await use_cases.collections.set_row_value(alice, project.id, rel_id, [t1.id, t2.id])

    rows, related = await use_cases.collections.query_view_with_related(
        alice, projects.id, projects.views[0].id
    )
    row = rows[0]
    assert row.properties[count_id] == 2
    assert row.properties[total_id] == 8
    assert dict(related) == {t1.id: "Design", t2.id: "Build"}


async def test_rollup_and_formula_coexist(use_cases: UseCases, alice):
    _ws, projects, tasks = await _projects_with_rollups(use_cases, alice)
    rel_id = _prop_id(projects, "Tasks")
    count_id = _prop_id(projects, "Task count")
    # A formula that references the rollup value (rollups are merged first).
    projects = await use_cases.collections.add_property(
        alice, projects.id, name="Count plus one", type=PropertyType.FORMULA,
        formula='prop("Task count") + 1',
    )
    formula_id = projects.properties[-1].id

    t1 = await use_cases.collections.add_row(alice, tasks.id, title="A")
    project = await use_cases.collections.add_row(alice, projects.id, title="P")
    await use_cases.collections.set_row_value(alice, project.id, rel_id, [t1.id])

    rows = await use_cases.collections.query_view(alice, projects.id, projects.views[0].id)
    assert rows[0].properties[count_id] == 1
    assert rows[0].properties[formula_id] == 2


async def test_list_rows_returns_non_trashed_id_and_title(use_cases: UseCases, alice):
    ws = await use_cases.workspaces.create(alice, name="WS")
    col = await use_cases.collections.create_collection(
        alice, workspace_id=ws.id, name="C"
    )
    a = await use_cases.collections.add_row(alice, col.id, title="Alpha")
    b = await use_cases.collections.add_row(alice, col.id, title="Beta")
    gone = await use_cases.collections.add_row(alice, col.id, title="Gone")
    await use_cases.collections.remove_row(alice, gone.id)

    listed = await use_cases.collections.list_rows(alice, col.id)
    assert set(listed) == {(a.id, "Alpha"), (b.id, "Beta")}


async def test_update_property_can_change_relation_target(use_cases: UseCases, alice):
    ws, projects, tasks = await _projects_and_tasks(use_cases, alice)
    rel_id = _prop_id(projects, "Tasks")
    other = await use_cases.collections.create_collection(
        alice, workspace_id=ws.id, name="Other"
    )
    updated = await use_cases.collections.update_property(
        alice, projects.id, rel_id, relation_collection_id=other.id
    )
    rel = next(p for p in updated.properties if p.id == rel_id)
    assert rel.relation_collection_id == other.id
    # Retargeting to a missing collection is rejected.
    with pytest.raises(ValidationFailed):
        await use_cases.collections.update_property(
            alice, projects.id, rel_id, relation_collection_id="missing"
        )
