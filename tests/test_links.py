"""document-search + document-links specs: workspace search and backlinks."""

from __future__ import annotations

from cyberarche.application.ports.llm import LLMResponse
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


async def test_teamspace_graph_links_only_in_scope_documents(use_cases: UseCases, alice):
    from cyberarche.domain.ids import TeamspaceId

    ws = await use_cases.workspaces.create(alice, name="WS")
    team = await use_cases.teamspaces.create(alice, ws.id, name="Team")
    other = await use_cases.teamspaces.create(alice, ws.id, name="Other")
    a = await use_cases.documents.create(
        alice, workspace_id=ws.id, title="Alpha", teamspace_id=team.id
    )
    b = await use_cases.documents.create(
        alice, workspace_id=ws.id, title="Beta", teamspace_id=team.id
    )
    outside = await use_cases.documents.create(
        alice, workspace_id=ws.id, title="Gamma", teamspace_id=other.id
    )
    # Alpha links Beta (in scope, case-insensitive) and Gamma (out of scope).
    await use_cases.agent.apply_blocks(alice, a.id, [para("see [[beta]] and [[Gamma]]")])
    await use_cases.agent.apply_blocks(alice, b.id, [para("back to [[Alpha]]")])

    graph = await use_cases.links.graph(alice, teamspace_id=TeamspaceId(team.id))

    assert {n.id for n in graph.nodes} == {a.id, b.id}  # Gamma is not in scope
    edges = {(e.source, e.target) for e in graph.edges}
    assert (a.id, b.id) in edges and (b.id, a.id) in edges
    # The out-of-scope link (Gamma) is not an edge.
    assert all(outside.id not in (e.source, e.target) for e in graph.edges)


async def test_folder_graph_scopes_to_the_folder(use_cases: UseCases, alice):
    from cyberarche.domain.ids import FolderId

    ws = await use_cases.workspaces.create(alice, name="WS")
    team = await use_cases.teamspaces.create(alice, ws.id, name="Team")
    folder = await use_cases.folders.create(
        alice, ws.id, name="Notes", teamspace_id=team.id
    )
    a = await use_cases.documents.create(
        alice, workspace_id=ws.id, title="One", teamspace_id=team.id
    )
    b = await use_cases.documents.create(
        alice, workspace_id=ws.id, title="Two", teamspace_id=team.id
    )
    await use_cases.documents.place_in_folder(alice, a.id, folder.id)
    await use_cases.documents.place_in_folder(alice, b.id, folder.id)
    await use_cases.agent.apply_blocks(alice, a.id, [para("linking [[Two]]")])

    graph = await use_cases.links.graph(alice, folder_id=FolderId(folder.id))

    assert {n.id for n in graph.nodes} == {a.id, b.id}
    assert {(e.source, e.target) for e in graph.edges} == {(a.id, b.id)}


async def test_inferred_graph_is_typed_and_cached(use_cases: UseCases, llm, alice):
    from cyberarche.domain.ids import TeamspaceId

    ws = await use_cases.workspaces.create(alice, name="WS")
    team = await use_cases.teamspaces.create(alice, ws.id, name="Team")
    a = await use_cases.documents.create(
        alice, workspace_id=ws.id, title="Derivatives", teamspace_id=team.id
    )
    b = await use_cases.documents.create(
        alice, workspace_id=ws.id, title="Limits", teamspace_id=team.id
    )
    await use_cases.agent.apply_blocks(
        alice, a.id, [para("Understanding limits is required before a derivative.")]
    )
    await use_cases.agent.apply_blocks(alice, b.id, [para("The limit of a function.")])

    # Each document is classified once; only Derivatives→Limits resolves (a
    # Limits→Limits self-link is dropped), so one inferred edge results.
    rel = '[{"target":"Limits","type":"depends_on","confidence":94,"evidence":"limits first"}]'
    llm._responses = [LLMResponse(text=rel), LLMResponse(text=rel)]

    graph = await use_cases.links.inferred_graph(alice, teamspace_id=TeamspaceId(team.id))
    inferred = [e for e in graph.edges if e.inferred]
    assert any(e.type == "depends_on" and e.confidence == 94 for e in inferred)
    assert (a.id, b.id) in {(e.source, e.target) for e in inferred}
    calls = len(llm.requests)
    assert calls == 2  # one LLM call per document

    # Re-request with nothing changed → served from cache → NO new LLM calls.
    graph2 = await use_cases.links.inferred_graph(alice, teamspace_id=TeamspaceId(team.id))
    assert len(llm.requests) == calls  # the model was not asked again
    assert any(e.inferred and e.type == "depends_on" for e in graph2.edges)


async def test_only_changed_documents_are_reinferred(use_cases: UseCases, llm, alice):
    from cyberarche.domain.ids import TeamspaceId

    ws = await use_cases.workspaces.create(alice, name="WS")
    team = await use_cases.teamspaces.create(alice, ws.id, name="Team")
    a = await use_cases.documents.create(
        alice, workspace_id=ws.id, title="One", teamspace_id=team.id
    )
    b = await use_cases.documents.create(
        alice, workspace_id=ws.id, title="Two", teamspace_id=team.id
    )
    await use_cases.agent.apply_blocks(alice, a.id, [para("first")])
    await use_cases.agent.apply_blocks(alice, b.id, [para("second")])

    llm._responses = [LLMResponse(text="[]"), LLMResponse(text="[]")]
    await use_cases.links.inferred_graph(alice, teamspace_id=TeamspaceId(team.id))
    calls = len(llm.requests)  # 2

    # Change only document A → its content hash changes → only A is re-classified.
    await use_cases.agent.apply_blocks(alice, a.id, [para("first, now expanded")])
    llm._responses = [LLMResponse(text="[]")]
    await use_cases.links.inferred_graph(alice, teamspace_id=TeamspaceId(team.id))
    assert len(llm.requests) == calls + 1  # exactly one document re-inferred
