"""ai-agent spec: grounding, tool loop, CRDT peer edits, ingestion, auditing."""

from __future__ import annotations

import csv
import io

import pytest

from cyberarche.application.ports.llm import LLMResponse, ToolCall
from cyberarche.application.use_cases import UseCases
from cyberarche.domain.errors import NotAuthorized, ValidationFailed
from cyberarche.domain.memberships import Role, WorkspaceMembership


async def make_document(use_cases: UseCases, alice, *, title="Doc"):
    workspace = await use_cases.workspaces.create(alice, name="Docs")
    document = await use_cases.documents.create(
        alice, workspace_id=workspace.id, title=title
    )
    return workspace, document


async def seed_blocks(use_cases: UseCases, alice, document_id, texts: list[str]):
    blocks = [
        {"id": f"b{i}", "type": "paragraph", "data": {"text": text}}
        for i, text in enumerate(texts, start=1)
    ]
    await use_cases.agent.apply_blocks(alice, document_id, blocks)
    return blocks


async def test_answer_is_grounded_in_document_blocks(use_cases, llm, alice):
    _, document = await make_document(use_cases, alice)
    await seed_blocks(use_cases, alice, document.id, ["The launch is on March 3."])
    llm._responses = [LLMResponse(text="March 3 [block:b1]", model="m")]

    answer = await use_cases.agent.ask(
        alice, document.id, instruction="When is the launch?"
    )

    assert answer.text == "March 3 [block:b1]"
    assert answer.blocks and answer.blocks[0]["type"] == "paragraph"
    # The document content was in the prompt the model saw.
    prompt = llm.requests[0][-1].content
    assert "The launch is on March 3." in prompt
    assert document.id in prompt  # the agent is told which document is open
    assert "[block:b1]" in prompt


async def test_tool_loop_executes_rag_query_and_feeds_result_back(
    use_cases, llm, alice
):
    workspace, document = await make_document(use_cases, alice)
    await use_cases.knowledge.ingest_file(
        alice, workspace.id, filename="specs.md", content=b"# spec"
    )
    llm._responses = [
        LLMResponse(
            text="",
            tool_calls=(
                ToolCall(
                    id="c1",
                    name="rag_query",
                    arguments={"workspace_id": workspace.id, "query": "spec"},
                ),
            ),
        ),
        LLMResponse(text="Answer citing specs.md", model="m"),
    ]

    answer = await use_cases.agent.ask(alice, document.id, instruction="what spec?")

    assert answer.text == "Answer citing specs.md"
    tool_message = llm.requests[1][-1]
    assert tool_message.role == "tool"
    assert "specs.md" in tool_message.tool_result.content  # RAG result fed back

    runs = await use_cases.agent.run_history(alice, document.id)
    assert runs[0].tools_used == ("rag_query",)


async def test_agent_edit_is_a_crdt_peer_edit_attributed_to_agent(
    use_cases, update_log, alice
):
    _, document = await make_document(use_cases, alice)

    await seed_blocks(use_cases, alice, document.id, ["from the agent"])

    updates = await update_log.list_for_document(document.id)
    assert updates[-1].origin == f"agent:{alice.user_id}"
    # The edit is in the live CRDT state, merged like any human edit.
    state = await use_cases.realtime.current_state(alice, document.id)
    blocks = use_cases.agent._engine.read_blocks(state)
    assert blocks[0]["data"]["text"] == "from the agent"


async def test_agent_edit_merges_with_concurrent_human_edit(use_cases, alice):
    from pycrdt import Doc, Text

    _, document = await make_document(use_cases, alice)

    # Human types concurrently (text edit against the empty base)...
    doc = Doc()
    before = doc.get_state()
    text = doc.get("text", type=Text)
    text += "human typing"
    await use_cases.realtime.apply(alice, document.id, doc.get_update(before))
    # ...while the agent appends a block.
    await seed_blocks(use_cases, alice, document.id, ["agent block"])

    state = await use_cases.realtime.current_state(alice, document.id)
    merged_doc = Doc()
    merged_doc.apply_update(state)
    assert str(merged_doc.get("text", type=Text)) == "human typing"
    assert use_cases.agent._engine.read_blocks(state)[0]["data"]["text"] == "agent block"


async def test_csv_ingestion_creates_matching_table_block(use_cases, rag, alice):
    workspace, document = await make_document(use_cases, alice)
    buffer = io.StringIO()
    csv.writer(buffer).writerows(
        [["name", "score"], ["ada", "99"], ["grace", "97"]]
    )

    blocks = await use_cases.agent.ingest_file_to_document(
        alice, document.id, filename="scores.csv", content=buffer.getvalue().encode()
    )

    assert blocks[0]["type"] == "table"
    assert blocks[0]["data"]["header"] == ["name", "score"]
    assert blocks[0]["data"]["rows"] == [["ada", "99"], ["grace", "97"]]
    # Original was submitted to the workspace knowledge base.
    assert "scores.csv" in rag.projects[workspace.rag_project_slug]


async def test_excel_ingestion_creates_table_per_sheet(use_cases, alice):
    from openpyxl import Workbook

    _, document = await make_document(use_cases, alice)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Data"
    sheet.append(["col_a", "col_b"])
    sheet.append([1, 2])
    buffer = io.BytesIO()
    workbook.save(buffer)

    blocks = await use_cases.agent.ingest_file_to_document(
        alice, document.id, filename="table.xlsx", content=buffer.getvalue()
    )

    table = next(b for b in blocks if b["type"] == "table")
    assert table["data"]["header"] == ["col_a", "col_b"]
    assert table["data"]["rows"] == [["1", "2"]]


async def test_pdf_ingestion_extracts_paragraph_blocks(use_cases, alice):
    _, document = await make_document(use_cases, alice)
    pdf = _tiny_pdf(b"Hello CyberArche")

    blocks = await use_cases.agent.ingest_file_to_document(
        alice, document.id, filename="hello.pdf", content=pdf
    )

    assert blocks, "expected extracted blocks"
    assert blocks[0]["type"] == "paragraph"
    assert "Hello CyberArche" in blocks[0]["data"]["text"]


async def test_unsupported_file_type_is_rejected(use_cases, alice):
    _, document = await make_document(use_cases, alice)
    with pytest.raises(ValidationFailed):
        await use_cases.agent.ingest_file_to_document(
            alice, document.id, filename="binary.exe", content=b"MZ"
        )


async def test_agent_rejects_invalid_block_type_insertion(use_cases, alice):
    _, document = await make_document(use_cases, alice)
    with pytest.raises(ValidationFailed):
        await use_cases.agent.apply_blocks(
            alice, document.id, [{"id": "x", "type": "hologram", "data": {}}]
        )


async def test_viewer_cannot_make_agent_edits(use_cases, memberships, clock, alice):
    from tests.conftest import caller

    viewer = caller("carol", "acme")
    workspace, document = await make_document(use_cases, alice)
    await memberships.add_workspace_member(
        WorkspaceMembership(
            workspace_id=workspace.id,
            user_id=viewer.user_id,
            role=Role.VIEWER,
            granted_at=clock.now(),
        )
    )
    with pytest.raises(NotAuthorized):
        await use_cases.agent.apply_blocks(
            viewer, document.id, [{"id": "x", "type": "paragraph", "data": {}}]
        )


async def test_runs_are_audited_with_prompt_model_and_outcome(use_cases, llm, alice):
    _, document = await make_document(use_cases, alice)
    llm._responses = [LLMResponse(text="fine", model="claude-test-1")]

    await use_cases.agent.ask(alice, document.id, instruction="check")
    runs = await use_cases.agent.run_history(alice, document.id)

    assert len(runs) == 1
    assert runs[0].prompt == "check"
    assert runs[0].model == "claude-test-1"
    assert runs[0].outcome == "fine"
    assert runs[0].user_id == alice.user_id


def _tiny_pdf(text: bytes) -> bytes:
    """Hand-assembled single-page PDF with one text object."""
    stream = b"BT /F1 12 Tf 50 700 Td (" + text + b") Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for index, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{index} 0 obj\n".encode() + body + b"\nendobj\n")
    xref_at = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n".encode())
    out.write(b"0000000000 65535 f \n")
    for offset in offsets:
        out.write(f"{offset:010d} 00000 n \n".encode())
    out.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_at}\n%%EOF".encode()
    )
    return out.getvalue()


# ---- agent document editing (the reported bug: "agent cannot edit") --------


async def test_agent_adds_text_to_an_existing_block(use_cases, llm, alice):
    """Regression: 'add the text Hello World on the current block' used to
    fail because the agent had no editing tool and guessed read_document."""
    _, document = await make_document(use_cases, alice, title="Test Document")
    await seed_blocks(use_cases, alice, document.id, ["Hi"])

    llm._responses = [
        LLMResponse(
            text="",
            tool_calls=(
                ToolCall(id="c1", name="update_block",
                         arguments={"block_id": "b1", "text": "Hi Hello World"}),
            ),
        ),
        LLMResponse(text="Done — I updated the block.", model="m"),
    ]

    answer = await use_cases.agent.ask(
        alice, document.id, instruction="Add the text Hello World to that block"
    )

    assert answer.text == "Done — I updated the block."
    state = await use_cases.realtime.current_state(alice, document.id)
    assert use_cases.agent._engine.read_blocks(state)[0]["data"]["text"] == "Hi Hello World"


async def test_agent_update_merges_data_and_keeps_other_keys(use_cases, alice):
    """A text edit must not drop a whiteboard scene stored on the same block."""
    _, document = await make_document(use_cases, alice)
    await use_cases.agent.apply_blocks(alice, document.id, [
        {"id": "wb", "type": "whiteboard", "data": {"elements": {"a": {"kind": "rect"}}}},
    ])

    await use_cases.agent.update_block(alice, document.id, "wb", {"caption": "diagram"})

    state = await use_cases.realtime.current_state(alice, document.id)
    data = use_cases.agent._engine.read_blocks(state)[0]["data"]
    assert data["caption"] == "diagram"
    assert data["elements"] == {"a": {"kind": "rect"}}  # scene survived


async def test_agent_inserts_and_deletes_blocks_via_tools(use_cases, llm, alice):
    _, document = await make_document(use_cases, alice)
    await seed_blocks(use_cases, alice, document.id, ["keep", "remove me"])

    llm._responses = [
        LLMResponse(text="", tool_calls=(
            ToolCall(id="c1", name="insert_blocks",
                     arguments={"blocks": [{"type": "heading", "data": {"text": "Goals"}}]}),
            ToolCall(id="c2", name="delete_block", arguments={"block_id": "b2"}),
        )),
        LLMResponse(text="ok", model="m"),
    ]

    await use_cases.agent.ask(alice, document.id, instruction="restructure")

    state = await use_cases.realtime.current_state(alice, document.id)
    blocks = use_cases.agent._engine.read_blocks(state)
    assert [b["type"] for b in blocks] == ["paragraph", "heading"]
    assert blocks[0]["data"]["text"] == "keep"


async def test_editing_tools_are_offered_and_bound_to_the_open_document(
    use_cases, llm, alice
):
    _, document = await make_document(use_cases, alice)
    _, other = await make_document(use_cases, alice, title="Other")
    await seed_blocks(use_cases, alice, other.id, ["untouched"])
    llm._responses = [LLMResponse(text="hi", model="m")]

    await use_cases.agent.ask(alice, document.id, instruction="hello")

    # The model is offered the editing tools alongside rag_query/read_document.
    offered = {spec.name for spec in llm.tools_seen[0]}
    assert {"insert_blocks", "update_block", "delete_block"} <= offered
    # No tool takes a document_id -> the model cannot address another document.
    for spec in llm.tools_seen[0]:
        if spec.name in {"insert_blocks", "update_block", "delete_block"}:
            assert "document_id" not in spec.parameters["properties"]


async def test_viewer_agent_edit_is_denied_and_reported_to_the_model(
    use_cases, llm, memberships, clock, alice
):
    from tests.conftest import caller

    viewer = caller("carol", "acme")
    workspace, document = await make_document(use_cases, alice)
    await seed_blocks(use_cases, alice, document.id, ["original"])
    await memberships.add_workspace_member(
        WorkspaceMembership(workspace_id=workspace.id, user_id=viewer.user_id,
                            role=Role.VIEWER, granted_at=clock.now())
    )
    llm._responses = [
        LLMResponse(text="", tool_calls=(
            ToolCall(id="c1", name="update_block",
                     arguments={"block_id": "b1", "text": "sneaky"}),
        )),
        LLMResponse(text="I cannot edit this document.", model="m"),
    ]

    await use_cases.agent.ask(viewer, document.id, instruction="change it")

    tool_reply = llm.requests[1][-1].tool_result.content
    assert "permission" in tool_reply
    state = await use_cases.realtime.current_state(alice, document.id)
    assert use_cases.agent._engine.read_blocks(state)[0]["data"]["text"] == "original"


def test_agent_block_endpoints_replace_and_delete(api):
    """Agent panel 'Replace selection' and the block delete path over HTTP."""
    headers = {"Authorization": "Bearer alice-token"}
    workspace = api.post("/api/v1/workspaces", json={"name": "WS"}, headers=headers).json()
    document = api.post(
        "/api/v1/documents", json={"workspace_id": workspace["id"], "title": "D"},
        headers=headers,
    ).json()
    api.post(
        f"/api/v1/documents/{document['id']}/agent/blocks",
        json={"blocks": [{"id": "b1", "type": "paragraph", "data": {"text": "old"}}]},
        headers=headers,
    )

    replaced = api.patch(
        f"/api/v1/documents/{document['id']}/agent/blocks/b1",
        json={"text": "new text"}, headers=headers,
    )
    assert replaced.status_code == 200

    assert api.delete(
        f"/api/v1/documents/{document['id']}/agent/blocks/b1", headers=headers
    ).status_code == 204
    # Deleting a missing block is a 404, not a 500.
    assert api.delete(
        f"/api/v1/documents/{document['id']}/agent/blocks/b1", headers=headers
    ).status_code == 404


# ---- positional insert / replace / summarize-selection (extend-agent-mcp) ---


async def test_agent_inserts_blocks_at_a_position(use_cases, alice):
    _, document = await make_document(use_cases, alice)
    await seed_blocks(use_cases, alice, document.id, ["first", "third"])

    await use_cases.agent.insert_blocks(
        alice,
        document.id,
        [{"id": "mid", "type": "paragraph", "data": {"text": "second"}}],
        after_id="b1",
    )

    state = await use_cases.realtime.current_state(alice, document.id)
    ids = [b["id"] for b in use_cases.agent._engine.read_blocks(state)]
    assert ids == ["b1", "mid", "b2"]


async def test_agent_replaces_a_block_keeping_its_id(use_cases, alice):
    _, document = await make_document(use_cases, alice)
    await seed_blocks(use_cases, alice, document.id, ["plain paragraph"])

    await use_cases.agent.replace_block(
        alice, document.id, "b1", {"type": "heading", "data": {"text": "Title", "level": 1}}
    )

    state = await use_cases.realtime.current_state(alice, document.id)
    block = use_cases.agent._engine.read_blocks(state)[0]
    assert block["id"] == "b1" and block["type"] == "heading"
    assert block["data"]["level"] == 1


async def test_viewer_cannot_insert_or_replace(use_cases, memberships, clock, alice):
    from tests.conftest import caller

    viewer = caller("carol", "acme")
    workspace, document = await make_document(use_cases, alice)
    await seed_blocks(use_cases, alice, document.id, ["only block"])
    await memberships.add_workspace_member(
        WorkspaceMembership(
            workspace_id=workspace.id,
            user_id=viewer.user_id,
            role=Role.VIEWER,
            granted_at=clock.now(),
        )
    )

    with pytest.raises(NotAuthorized):
        await use_cases.agent.insert_blocks(
            viewer, document.id, [{"id": "x", "type": "paragraph", "data": {}}], after_id="b1"
        )
    with pytest.raises(NotAuthorized):
        await use_cases.agent.replace_block(
            viewer, document.id, "b1", {"type": "paragraph", "data": {"text": "hijacked"}}
        )


async def test_summarize_selection_scopes_the_prompt_to_the_blocks(use_cases, llm, alice):
    _, document = await make_document(use_cases, alice)
    await seed_blocks(use_cases, alice, document.id, ["keep this", "and this", "ignore me"])
    llm._responses = [LLMResponse(text="summary of b1, b2 [block:b1]", model="m")]

    await use_cases.agent.summarize(alice, document.id, block_ids=["b1", "b2"])

    prompt = llm.requests[0][-1].content
    assert "b1, b2" in prompt  # the selection is named to the model
    assert "only these blocks" in prompt.lower()


async def test_summarize_without_selection_covers_the_whole_document(use_cases, llm, alice):
    _, document = await make_document(use_cases, alice)
    await seed_blocks(use_cases, alice, document.id, ["a", "b"])
    llm._responses = [LLMResponse(text="whole-doc summary", model="m")]

    await use_cases.agent.summarize(alice, document.id)

    prompt = llm.requests[0][-1].content
    assert "only these blocks" not in prompt.lower()
