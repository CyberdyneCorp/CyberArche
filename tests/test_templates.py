"""templates spec: save a document as a template, instantiate, list, delete."""

from __future__ import annotations

import pytest

from cyberarche.application.use_cases import UseCases
from cyberarche.domain.errors import NotFound


def para(text: str, bid: str) -> dict:
    return {"id": bid, "type": "paragraph", "data": {"text": text}}


async def test_save_and_instantiate_template(use_cases: UseCases, alice):
    ws = await use_cases.workspaces.create(alice, name="WS")
    team = await use_cases.teamspaces.create(alice, ws.id, name="Team")
    source = await use_cases.documents.create(
        alice, workspace_id=ws.id, title="Meeting notes", teamspace_id=team.id
    )
    await use_cases.agent.apply_blocks(
        alice, source.id, [para("Agenda", "b1"), para("Action items", "b2")]
    )

    template = await use_cases.templates.save_from_document(
        alice, ws.id, name="Standup", document_id=source.id
    )
    assert template.name == "Standup"
    assert [b["data"]["text"] for b in template.content] == ["Agenda", "Action items"]
    assert [t.id for t in await use_cases.templates.list(alice, ws.id)] == [template.id]

    # Instantiate → a new document pre-filled with the template's blocks (fresh ids).
    doc = await use_cases.templates.instantiate(
        alice, ws.id, template_id=template.id, title="Today's standup", teamspace_id=team.id
    )
    assert doc.id != source.id
    state = await use_cases.realtime.current_state(alice, doc.id)
    blocks = use_cases.agent._engine.read_blocks(state)
    assert [b["data"]["text"] for b in blocks] == ["Agenda", "Action items"]
    # Fresh ids — the new document must not reuse the template's source block ids.
    assert {b["id"] for b in blocks}.isdisjoint({"b1", "b2"})


async def test_delete_template(use_cases: UseCases, alice):
    ws = await use_cases.workspaces.create(alice, name="WS")
    doc = await use_cases.documents.create(alice, workspace_id=ws.id, title="Doc")
    template = await use_cases.templates.save_from_document(
        alice, ws.id, name="T", document_id=doc.id
    )
    await use_cases.templates.delete(alice, template.id)
    assert await use_cases.templates.list(alice, ws.id) == []
    with pytest.raises(NotFound):
        await use_cases.templates.delete(alice, template.id)
