"""document-search + document-links specs: workspace search and backlinks."""

from __future__ import annotations

from cyberarche.application.use_cases import UseCases


def para(text: str, bid: str = "b1") -> dict:
    return {"id": bid, "type": "paragraph", "data": {"text": text}}


async def test_search_in_workspace_filters_by_title_and_scope(use_cases: UseCases, alice):
    ws1 = await use_cases.workspaces.create(alice, name="WS1")
    ws2 = await use_cases.workspaces.create(alice, name="WS2")
    await use_cases.documents.create(alice, workspace_id=ws1.id, title="Calculus Notes")
    await use_cases.documents.create(alice, workspace_id=ws1.id, title="Algebra")
    await use_cases.documents.create(alice, workspace_id=ws2.id, title="Calculus Elsewhere")

    hits = await use_cases.documents.search_in_workspace(alice, ws1.id, query="calc")
    assert [d.title for d in hits] == ["Calculus Notes"]  # scoped to ws1, title match

    everything = await use_cases.documents.search_in_workspace(alice, ws1.id, query="")
    assert sorted(d.title for d in everything) == ["Algebra", "Calculus Notes"]


async def test_backlinks_finds_referencing_document(use_cases: UseCases, alice):
    ws = await use_cases.workspaces.create(alice, name="WS")
    target = await use_cases.documents.create(alice, workspace_id=ws.id, title="Target Doc")
    linker = await use_cases.documents.create(alice, workspace_id=ws.id, title="Linker")
    other = await use_cases.documents.create(alice, workspace_id=ws.id, title="Other")
    await use_cases.agent.apply_blocks(
        alice, linker.id, [para("See [[Target Doc]] for details")]
    )
    await use_cases.agent.apply_blocks(alice, other.id, [para("nothing linked here")])

    back = await use_cases.links.backlinks(alice, target.id)
    assert [d.id for d in back] == [linker.id]


async def test_backlinks_are_case_insensitive_and_exclude_self(use_cases: UseCases, alice):
    ws = await use_cases.workspaces.create(alice, name="WS")
    target = await use_cases.documents.create(alice, workspace_id=ws.id, title="Target Doc")
    linker = await use_cases.documents.create(alice, workspace_id=ws.id, title="Linker")
    # Self-reference must not count as a backlink.
    await use_cases.agent.apply_blocks(alice, target.id, [para("I am [[Target Doc]]")])
    await use_cases.agent.apply_blocks(alice, linker.id, [para("ref [[target doc]]")])

    back = await use_cases.links.backlinks(alice, target.id)
    assert [d.id for d in back] == [linker.id]
