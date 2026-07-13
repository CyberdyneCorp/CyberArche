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
    teamspace = await use_cases.teamspaces.create(alice, workspace.id, name="Team")
    document = await use_cases.documents.create(
        alice, workspace_id=workspace.id, title=title, teamspace_id=teamspace.id
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


async def test_ask_includes_recent_conversation_history(use_cases, llm, alice):
    """Follow-ups like 'insert the plot' need the prior turns — the agent was
    stateless, so the model had no idea what 'the plot' referred to."""
    _, document = await make_document(use_cases, alice)
    llm._responses = [LLMResponse(text="ok", model="m")]

    await use_cases.agent.ask(
        alice,
        document.id,
        instruction="insert the plot",
        history=[
            ("user", "create a plot of 1/x"),
            ("agent", "here is the plot code"),
        ],
    )

    sent = llm.requests[0]
    assert [m.role for m in sent] == ["system", "user", "assistant", "user"]
    assert "create a plot of 1/x" in sent[1].content
    assert "here is the plot code" in sent[2].content
    assert "insert the plot" in sent[-1].content


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


async def test_ask_maps_reasoning_toggle_to_effort(use_cases, llm, alice):
    _, document = await make_document(use_cases, alice)

    llm._responses = [LLMResponse(text="off", model="m")]
    await use_cases.agent.ask(alice, document.id, instruction="hi", reasoning=False)
    assert llm.reasoning_seen[-1] == "minimal"  # fast by default

    llm._responses = [LLMResponse(text="on", model="m")]
    await use_cases.agent.ask(alice, document.id, instruction="hi", reasoning=True)
    assert llm.reasoning_seen[-1] == "medium"  # deeper when toggled on


def test_classify_tool_distinguishes_mcp_editing_builtin():
    from cyberarche.application.use_cases.agent import _classify_tool

    assert _classify_tool("insert_blocks") == ("editing", None)
    assert _classify_tool("generate_image") == ("editing", None)
    assert _classify_tool("create_mindmap") == ("editing", None)
    assert _classify_tool("rag_query") == ("builtin", None)
    assert _classify_tool("github__create_issue") == ("mcp", "github")


def test_build_mindmap_is_a_valid_excalidraw_scene():
    from cyberarche.application.use_cases.excalidraw_scene import (
        build_mindmap,
        describe_scene,
    )

    scene = build_mindmap(
        "AI", [{"label": "ML", "children": ["DL", "RL"]}, "NLP", "Vision"]
    )
    assert scene["type"] == "excalidraw" and scene["version"] == 2
    # centre (rect+text) + 3 branches (rect+text+arrow) + 2 children (rect+text+arrow)
    assert len(scene["elements"]) == 2 + 3 * 3 + 2 * 3
    ids = [e["id"] for e in scene["elements"]]
    assert len(ids) == len(set(ids))  # unique ids
    for element in scene["elements"]:  # every element carries the full base fields
        for field in ("id", "x", "y", "width", "height", "seed", "version", "isDeleted"):
            assert field in element
    described = describe_scene(scene)
    assert "AI" in described and "ML → DL" in described and "AI → NLP" in described


def test_describe_scene_tolerates_bad_input():
    from cyberarche.application.use_cases.excalidraw_scene import describe_scene

    assert describe_scene("") == "(empty canvas)"
    assert describe_scene("{not json") == "(unreadable canvas)"
    assert describe_scene({"elements": []}) == "(empty canvas)"


async def test_agent_create_mindmap_inserts_an_excalidraw_block(use_cases, llm, alice):
    import json

    _, document = await make_document(use_cases, alice)
    llm._responses = [
        LLMResponse(
            text="",
            tool_calls=(
                ToolCall(
                    id="c1",
                    name="create_mindmap",
                    arguments={
                        "central": "Roadmap",
                        "branches": [{"label": "Q1", "children": ["Auth"]}, "Q2"],
                    },
                ),
            ),
        ),
        LLMResponse(text="Here is your mind map.", model="m"),
    ]

    answer = await use_cases.agent.ask(alice, document.id, instruction="map the roadmap")

    state = await use_cases.realtime.current_state(alice, document.id)
    blocks = use_cases.agent._engine.read_blocks(state)
    excalidraw = [b for b in blocks if b["type"] == "excalidraw"]
    assert len(excalidraw) == 1
    scene = json.loads(excalidraw[0]["data"]["scene"])
    assert scene["type"] == "excalidraw"
    labels = {e.get("text") for e in scene["elements"] if e.get("type") == "text"}
    assert {"Roadmap", "Q1", "Q2", "Auth"} <= labels
    # The edit is surfaced to the chat as a tool call.
    assert any(c.name == "create_mindmap" for c in answer.tool_calls)


async def test_render_block_describes_an_excalidraw_scene(use_cases, alice):
    import json

    from cyberarche.application.use_cases.agent import _render_block
    from cyberarche.application.use_cases.excalidraw_scene import build_mindmap

    scene = build_mindmap("Topic", ["Idea A", "Idea B"])
    rendered = _render_block(
        {"id": "b1", "type": "excalidraw", "data": {"scene": json.dumps(scene)}}
    )
    assert "(excalidraw)" in rendered
    assert "Topic" in rendered and "Idea A" in rendered


async def test_ask_returns_tool_calls_for_the_chat(use_cases, llm, alice):
    workspace, document = await make_document(use_cases, alice)
    llm._responses = [
        LLMResponse(
            text="",
            tool_calls=(
                ToolCall(
                    id="c1",
                    name="rag_query",
                    arguments={"workspace_id": workspace.id, "query": "specs"},
                ),
                ToolCall(
                    id="c2",
                    name="insert_blocks",
                    arguments={"blocks": [{"type": "paragraph", "data": {"text": "hi"}}]},
                ),
            ),
        ),
        LLMResponse(text="done", model="m"),
    ]

    answer = await use_cases.agent.ask(alice, document.id, instruction="do stuff")

    calls = {c.name: c for c in answer.tool_calls}
    assert calls["rag_query"].kind == "builtin"
    assert calls["insert_blocks"].kind == "editing"
    # Arguments and result are captured so the chat can expand the call.
    assert calls["rag_query"].arguments["query"] == "specs"
    assert calls["rag_query"].ok
    assert calls["insert_blocks"].result.startswith("inserted 1 block")


async def test_agent_reads_a_meeting_transcript_with_delegated_token(
    use_cases, llm, meetings, alice
):
    _, document = await make_document(use_cases, alice)
    llm._responses = [
        LLMResponse(
            text="",
            tool_calls=(
                ToolCall(
                    id="c1",
                    name="get_meeting_transcript",
                    arguments={"recording_id": "rec-1"},
                ),
            ),
        ),
        LLMResponse(text="Added the standup notes.", model="m"),
    ]

    answer = await use_cases.agent.ask(
        alice,
        document.id,
        instruction="add my standup transcript",
        access_token="tok-123",
    )

    # The caller's own token is forwarded to the provider (delegated auth).
    assert meetings.tokens == ["tok-123"]
    call = next(c for c in answer.tool_calls if c.name == "get_meeting_transcript")
    assert "Weekly standup" in call.result
    assert "Alice: draft the spec" in call.result  # action item rendered
    assert "Alice: hello everyone" in call.result  # transcript body rendered


async def test_agent_asks_across_meetings(use_cases, llm, meetings, alice):
    _, document = await make_document(use_cases, alice)
    llm._responses = [
        LLMResponse(
            text="",
            tool_calls=(
                ToolCall(
                    id="c1", name="ask_meetings", arguments={"question": "roadmap?"}
                ),
            ),
        ),
        LLMResponse(text="done", model="m"),
    ]

    await use_cases.agent.ask(
        alice,
        document.id,
        instruction="what did my meetings say about the roadmap?",
        access_token="tok-xyz",
    )

    assert meetings.asked == ["roadmap?"]
    assert meetings.tokens == ["tok-xyz"]


async def test_meeting_tools_require_a_caller_token(use_cases, alice):
    _, document = await make_document(use_cases, alice)
    # No access token on the request path → the per-user tools are not offered.
    without = await use_cases.agent._available_tools(
        alice, document.workspace_id, document.id, None, None
    )
    assert "list_meetings" not in {t.name for t in without}
    # With the caller's token they appear.
    with_token = await use_cases.agent._available_tools(
        alice, document.workspace_id, document.id, None, "tok"
    )
    assert {"list_meetings", "get_meeting_transcript", "ask_meetings"} <= {
        t.name for t in with_token
    }


async def test_agent_updates_a_table_block(use_cases, llm, alice):
    # Regression: update_block cannot edit a table (it only writes text); the
    # agent must use update_table, which rewrites header/rows.
    _, document = await make_document(use_cases, alice)
    await use_cases.agent.apply_blocks(
        alice,
        document.id,
        [
            {
                "id": "t1",
                "type": "table",
                "data": {
                    "header": ["Name", "Description"],
                    "rows": [["Cyberfluids", "CFD library"]],
                },
            }
        ],
    )
    llm._responses = [
        LLMResponse(
            text="",
            tool_calls=(
                ToolCall(
                    id="c1",
                    name="update_table",
                    arguments={
                        "block_id": "t1",
                        "header": ["Name", "Description"],
                        "rows": [
                            [
                                "[Cyberfluids](https://github.com/x/cyberfluids)",
                                "CFD library",
                            ]
                        ],
                    },
                ),
            ),
        ),
        LLMResponse(text="Linked the names.", model="m"),
    ]

    await use_cases.agent.ask(alice, document.id, instruction="link the names")

    state = await use_cases.realtime.current_state(alice, document.id)
    table = next(
        b for b in use_cases.agent._engine.read_blocks(state) if b["type"] == "table"
    )
    assert table["data"]["rows"][0][0] == "[Cyberfluids](https://github.com/x/cyberfluids)"


async def test_agent_sees_table_cells_in_its_context():
    # The agent's context renders a table's cells (so it can target them),
    # not an empty body.
    from cyberarche.application.use_cases.agent import _render_block

    rendered = _render_block(
        {
            "id": "t1",
            "type": "table",
            "data": {"header": ["Name"], "rows": [["Cyberfluids"], ["CalculixPP"]]},
        }
    )
    assert "[block:t1] (table)" in rendered
    assert "Cyberfluids" in rendered and "CalculixPP" in rendered
    assert "| Name |" in rendered


async def test_web_media_tools_require_a_caller_token(use_cases, alice):
    _, document = await make_document(use_cases, alice)
    # No access token → the per-caller web/media tools are not offered.
    without = await use_cases.agent._available_tools(
        alice, document.workspace_id, document.id, None, None
    )
    assert "web_search" not in {t.name for t in without}
    # With the caller's token they appear.
    with_token = await use_cases.agent._available_tools(
        alice, document.workspace_id, document.id, None, "tok"
    )
    assert {"web_search", "youtube_transcript", "youtube_playlist"} <= {
        t.name for t in with_token
    }


async def test_agent_web_search_forwards_token_and_renders(
    use_cases, llm, web_media, alice
):
    _, document = await make_document(use_cases, alice)
    llm._responses = [
        LLMResponse(
            text="",
            tool_calls=(
                ToolCall(
                    id="c1", name="web_search", arguments={"query": "cyberdyne"}
                ),
            ),
        ),
        LLMResponse(text="Here is what I found.", model="m"),
    ]

    answer = await use_cases.agent.ask(
        alice,
        document.id,
        instruction="research cyberdyne",
        access_token="tok-web",
    )

    # The caller's own token is forwarded to the DAO backend (delegated auth).
    assert web_media.tokens == ["tok-web"]
    assert web_media.searched == ["cyberdyne"]
    call = next(c for c in answer.tool_calls if c.name == "web_search")
    assert "First" in call.result and "https://a.test/1" in call.result


async def test_agent_youtube_transcript_forwards_token(
    use_cases, llm, web_media, alice
):
    _, document = await make_document(use_cases, alice)
    llm._responses = [
        LLMResponse(
            text="",
            tool_calls=(
                ToolCall(
                    id="c1",
                    name="youtube_transcript",
                    arguments={"video": "abc123"},
                ),
            ),
        ),
        LLMResponse(text="Summarized.", model="m"),
    ]

    answer = await use_cases.agent.ask(
        alice,
        document.id,
        instruction="summarize this video",
        access_token="tok-yt",
    )

    assert web_media.tokens == ["tok-yt"]
    assert web_media.transcripts == ["abc123"]
    call = next(c for c in answer.tool_calls if c.name == "youtube_transcript")
    assert "Hello and welcome" in call.result


async def test_web_media_tool_reports_unavailable_when_unconfigured(use_cases, alice):
    from cyberarche.application.ports.llm import ToolCall as _ToolCall

    use_cases.agent._web_media = None
    result = await use_cases.agent._run_web_media_tool(
        _ToolCall(id="c", name="web_search", arguments={"query": "x"}), "tok"
    )
    assert result.startswith("error:") and "not configured" in result


async def test_web_media_error_maps_5xx_to_graceful_message():
    # Regression: a 503 from the DAO backend must not leak the raw httpx URL/error
    # to the model; it maps to a retryable, non-leaky message.
    from cyberarche.application.use_cases.agent import _web_media_error

    class _Resp:
        status_code = 503

    class _HttpError(Exception):
        response = _Resp()

    msg = _web_media_error(_HttpError("Server error '503 Service Unavailable' for url ..."))
    assert "temporarily unavailable" in msg
    assert "http" not in msg.lower() and "url" not in msg.lower()


async def test_web_media_tool_requires_sign_in(use_cases, alice):
    from cyberarche.application.ports.llm import ToolCall as _ToolCall

    result = await use_cases.agent._run_web_media_tool(
        _ToolCall(id="c", name="web_search", arguments={"query": "x"}), None
    )
    assert result.startswith("error:") and "sign in" in result


async def test_meetings_tool_reports_unavailable_when_unconfigured(use_cases, alice):
    from cyberarche.application.ports.llm import ToolCall as _ToolCall

    use_cases.agent._meetings = None
    result = await use_cases.agent._run_meetings_tool(
        _ToolCall(id="c", name="list_meetings", arguments={}), "tok"
    )
    assert result.startswith("error:") and "not configured" in result


async def test_cyberflies_adapter_maps_transcript_and_sends_caller_token():
    import httpx

    from cyberarche.adapters.outbound.meetings.cyberflies import (
        CyberfliesMeetingsAdapter,
    )

    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization", "")
        seen["path"] = request.url.path
        return httpx.Response(
            200,
            json={
                "id": "rec-9",
                "status": "ready",
                "created_at": "2026-07-02T09:00:00Z",
                "media": {},
                "transcription": {"text": "hello world", "word_count": 2},
                "summary": {
                    "headline": "Kickoff",
                    "abstract": "We started.",
                    "bullets": ["scoped it"],
                    "action_items": [{"text": "Bob: build it", "assignee": "Bob"}],
                },
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = CyberfliesMeetingsAdapter("https://cyberflies", client)
    rec = await adapter.get_recording("USER-TOKEN", "rec-9")
    await client.aclose()

    assert seen["auth"] == "Bearer USER-TOKEN"  # caller token forwarded as bearer
    assert seen["path"] == "/api/v1/recordings/rec-9"
    assert rec.headline == "Kickoff"
    assert rec.transcript == "hello world"
    assert rec.action_items == ["Bob: build it"]
    assert rec.bullets == ["scoped it"]


async def test_agent_generate_image_inserts_an_image_block(
    use_cases, llm, images, alice
):
    workspace, document = await make_document(use_cases, alice)
    llm._responses = [
        LLMResponse(
            text="",
            tool_calls=(
                ToolCall(id="c1", name="generate_image", arguments={"prompt": "a red fox"}),
            ),
        ),
        LLMResponse(text="Here is your image.", model="m"),
    ]

    answer = await use_cases.agent.ask(alice, document.id, instruction="draw a fox")

    assert images.prompts == ["a red fox"]
    state = await use_cases.realtime.current_state(alice, document.id)
    image_blocks = [
        b for b in use_cases.agent._engine.read_blocks(state) if b["type"] == "image"
    ]
    assert len(image_blocks) == 1
    assert image_blocks[0]["data"]["url"].startswith(
        f"/api/v1/workspaces/{workspace.id}/files/"
    )
    assert image_blocks[0]["data"]["alt"] == "a red fox"
    # The agent edited the doc, so it does not also offer manual-insert blocks.
    assert answer.blocks == []


async def test_agent_run_python_inserts_figures_and_returns_output(
    use_cases, llm, code_exec, alice
):
    workspace, document = await make_document(use_cases, alice)
    llm._responses = [
        LLMResponse(
            text="",
            tool_calls=(
                ToolCall(
                    id="c1",
                    name="run_python",
                    arguments={"code": "import matplotlib.pyplot as plt\nplt.plot([1,2,3])"},
                ),
            ),
        ),
        LLMResponse(text="Here is your plot.", model="m"),
    ]

    answer = await use_cases.agent.ask(alice, document.id, instruction="plot it")

    assert code_exec.calls  # the code actually ran
    state = await use_cases.realtime.current_state(alice, document.id)
    image_blocks = [
        b for b in use_cases.agent._engine.read_blocks(state) if b["type"] == "image"
    ]
    assert len(image_blocks) == 1
    assert image_blocks[0]["data"]["url"].startswith(
        f"/api/v1/workspaces/{workspace.id}/files/"
    )
    # The run_python call is surfaced to the chat with its captured output.
    py = next(c for c in answer.tool_calls if c.name == "run_python")
    assert py.kind == "builtin"
    assert "stdout" in py.result
    assert "inserted 1 figure" in py.result


async def test_run_python_reports_unavailable_when_unconfigured(use_cases, alice):
    workspace, document = await make_document(use_cases, alice)
    use_cases.agent._code = None  # simulate no interpreter configured
    result = await use_cases.agent._run_python(
        alice, workspace.id, document.id, {"code": "1 + 1"}
    )
    assert "not configured" in result


async def test_interpreter_adapter_sends_code_unmodified_and_dedupes_figures():
    """Regression: the interpreter auto-captures figures, so we must NOT append a
    savefig epilogue (it produced a second file → the plot was inserted twice)."""
    import httpx

    from cyberarche.adapters.outbound.code_exec.cyberdyne_interpreter import (
        CyberdyneInterpreterAdapter,
    )

    original = "import matplotlib.pyplot as plt\nplt.plot([1, 2, 3])\nplt.show()"
    sent = {}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/sessions":
            return httpx.Response(200, json={"session_id": "s1"})
        if path == "/execute":
            import json as _json

            sent["code"] = _json.loads(request.content)["code"]
            # Same figure listed under two names → must collapse to one image.
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "stdout": "",
                    "stderr": "",
                    "result": None,
                    "rich_outputs": [{"mime_type": "image/png", "artifact": "fig-1.png"}],
                    "artifacts": [{"name": "figure_1.png", "size_bytes": 3, "modified_at": 0}],
                },
            )
        if path.startswith("/files/"):
            return httpx.Response(200, content=b"PNGBYTES", headers={"content-type": "image/png"})
        return httpx.Response(404)

    async def token() -> str:
        return "t"

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = CyberdyneInterpreterAdapter("https://interp", client, token)
    outcome = await adapter.run(original)
    await client.aclose()

    assert sent["code"] == original  # no epilogue appended
    assert outcome.success
    assert len(outcome.images) == 1  # byte-identical duplicate collapsed


async def test_generate_image_reports_unavailable_when_unconfigured(use_cases, alice):
    workspace, document = await make_document(use_cases, alice)
    use_cases.agent._images = None  # simulate no image provider configured
    result = await use_cases.agent._run_generate_image(
        alice, workspace.id, document.id, {"prompt": "x"}
    )
    assert "not configured" in result


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


# ---- answer -> typed blocks (agent-renderable-blocks) -----------------------

from cyberarche.application.use_cases.agent import _answer_blocks  # noqa: E402


class _Ids:
    def __init__(self): self.n = 0
    def new_id(self):
        self.n += 1
        return f"id{self.n}"


def test_answer_blocks_detects_code_mermaid_latex_and_prose():
    text = (
        "Here is the idea.\n\n"
        "```python\nprint('hi')\n```\n\n"
        "A diagram:\n\n"
        "```mermaid\ngraph TD; A-->B\n```\n\n"
        "The law is $$E = mc^2$$ exactly."
    )
    blocks = _answer_blocks(_Ids(), text)
    kinds = [(b["type"], b["data"]) for b in blocks]

    assert ("paragraph", {"text": "Here is the idea."}) in kinds
    code = next(b for b in blocks if b["type"] == "code")
    assert code["data"] == {"source": "print('hi')", "language": "python"}
    mermaid = next(b for b in blocks if b["type"] == "mermaid")
    assert mermaid["data"]["source"] == "graph TD; A-->B"
    latex = next(b for b in blocks if b["type"] == "latex")
    assert latex["data"]["source"] == "E = mc^2"


def test_answer_blocks_converts_bracket_display_math_to_latex():
    text = "The equations:\n\n\\[ \\nabla \\cdot E = 0 \\]"
    blocks = _answer_blocks(_Ids(), text)
    latex = [b for b in blocks if b["type"] == "latex"]
    assert len(latex) == 1
    assert latex[0]["data"]["source"] == "\\nabla \\cdot E = 0"


def test_answer_blocks_normalizes_inline_paren_math_to_dollar():
    blocks = _answer_blocks(_Ids(), "The value \\(x^2\\) is positive.")
    assert blocks[0]["type"] == "paragraph"
    assert blocks[0]["data"]["text"] == "The value $x^2$ is positive."


def test_answer_blocks_plain_prose_is_paragraphs():
    blocks = _answer_blocks(_Ids(), "First para.\n\nSecond para.")
    assert [b["type"] for b in blocks] == ["paragraph", "paragraph"]
    assert [b["data"]["text"] for b in blocks] == ["First para.", "Second para."]


def test_answer_blocks_never_empty_for_nonempty_text():
    blocks = _answer_blocks(_Ids(), "just text")
    assert blocks and blocks[0]["data"]["text"] == "just text"


def test_answer_blocks_parses_headings_and_lists():
    text = (
        "# Title\n"
        "## Section\n"
        "### Subsection\n"
        "#### Detail\n"
        "Intro line.\n"
        "- first\n"
        "- second\n"
        "1. one\n"
        "> a quote\n"
        "- [ ] todo open\n"
        "- [x] todo done"
    )
    blocks = _answer_blocks(_Ids(), text)
    kinds = [(b["type"], b["data"]) for b in blocks]
    assert ("heading", {"text": "Title", "level": 1}) in kinds
    assert ("heading", {"text": "Section", "level": 2}) in kinds
    assert ("heading", {"text": "Subsection", "level": 3}) in kinds
    assert ("heading", {"text": "Detail", "level": 4}) in kinds
    assert ("paragraph", {"text": "Intro line."}) in kinds
    assert ("bulleted_list", {"text": "first"}) in kinds
    assert ("numbered_list", {"text": "one"}) in kinds
    assert ("quote", {"text": "a quote"}) in kinds
    assert ("todo", {"text": "todo open", "checked": False}) in kinds
    assert ("todo", {"text": "todo done", "checked": True}) in kinds


# ---- paragraph carrying a markdown blob is split into real blocks -----------

from cyberarche.application.use_cases.agent import _expand_block  # noqa: E402


def test_expand_block_splits_paragraph_with_heading_and_fenced_code():
    # The exact regression: a model dumped a "## heading" + ```python fence into
    # one paragraph, which the editor rendered as raw "## …" / "```python" text.
    para = {
        "type": "paragraph",
        "data": {
            "text": (
                "## Example (Python):\n"
                "```python\n"
                "def f(x):\n"
                "    return x**2 + 2*x + 1\n"
                "```"
            )
        },
    }
    out = _expand_block(_Ids(), para)
    types = [b["type"] for b in out]
    assert types == ["heading", "code"]
    assert out[0]["data"] == {"text": "Example (Python):", "level": 2}
    assert out[1]["data"]["language"] == "python"
    assert "def f(x):" in out[1]["data"]["source"]


def test_expand_block_leaves_plain_paragraph_and_typed_blocks_untouched():
    para = {"type": "paragraph", "data": {"text": "Just a normal sentence."}}
    assert _expand_block(_Ids(), para) == [para]
    # A dash mid-sentence is not a list; the paragraph is preserved verbatim.
    ranged = {"type": "paragraph", "data": {"text": "The range is 3 - 5 items."}}
    assert _expand_block(_Ids(), ranged) == [ranged]
    code = {"type": "code", "data": {"source": "## not a heading", "language": "md"}}
    assert _expand_block(_Ids(), code) == [code]


# ---- block normalization: no empty source blocks (agent-renderable-blocks) --

from cyberarche.application.use_cases.agent import _normalize_block  # noqa: E402


def test_normalize_maps_misplaced_content_to_source():
    # The model put the mermaid source under data.text (it only knew text blocks).
    b = _normalize_block({"type": "mermaid", "data": {"text": "graph TD; A-->B"}})
    assert b["data"]["source"] == "graph TD; A-->B"

    b = _normalize_block({"type": "latex", "data": {"code": "E=mc^2"}})
    assert b["data"]["source"] == "E=mc^2"


def test_normalize_defaults_code_language_and_source():
    b = _normalize_block({"type": "code", "data": {"text": "print(1)"}})
    assert b["data"]["source"] == "print(1)"
    assert b["data"]["language"] == "text"


def test_normalize_keeps_correct_source_and_leaves_text_blocks():
    b = _normalize_block({"type": "mermaid", "data": {"source": "graph LR; X-->Y"}})
    assert b["data"]["source"] == "graph LR; X-->Y"
    p = _normalize_block({"type": "paragraph", "data": {"text": "hello"}})
    assert p["data"] == {"text": "hello"}


async def test_agent_insert_of_a_sourceless_mermaid_is_not_empty(use_cases, alice):
    # Regression: an agent-inserted mermaid with content in the wrong key used to
    # land as an empty (placeholder-only) block.
    _, document = await make_document(use_cases, alice)
    await use_cases.agent.apply_blocks(
        alice, document.id, [{"type": "mermaid", "data": {"text": "graph TD; A-->B"}}]
    )
    state = await use_cases.realtime.current_state(alice, document.id)
    block = use_cases.agent._engine.read_blocks(state)[0]
    assert block["type"] == "mermaid"
    assert block["data"]["source"] == "graph TD; A-->B"  # not empty


# ---- no duplicate insert: agent that edits live offers no manual Insert ------


async def test_answer_has_no_insert_blocks_when_agent_edited_live(use_cases, llm, alice):
    """Regression: the agent inserted a diagram via its tool AND the answer
    offered Insert, so clicking it added a second (and the live one was empty).
    When the agent edits during the run, the answer carries no insertable blocks.
    """
    _, document = await make_document(use_cases, alice)
    llm._responses = [
        LLMResponse(
            text="",
            tool_calls=(
                ToolCall(
                    id="c1",
                    name="insert_blocks",
                    arguments={"blocks": [{"type": "mermaid", "data": {"source": "graph TD; A-->B"}}]},
                ),
            ),
        ),
        LLMResponse(text="I added the diagram.", model="m"),
    ]

    answer = await use_cases.agent.ask(alice, document.id, instruction="draw it")

    assert answer.text == "I added the diagram."
    assert answer.blocks == []  # already in the doc; nothing to insert again
    # And the live insert is a real (non-empty) mermaid block.
    state = await use_cases.realtime.current_state(alice, document.id)
    blocks = use_cases.agent._engine.read_blocks(state)
    assert [b["type"] for b in blocks] == ["mermaid"]
    assert blocks[0]["data"]["source"] == "graph TD; A-->B"


async def test_answer_carries_blocks_when_agent_did_not_edit(use_cases, llm, alice):
    _, document = await make_document(use_cases, alice)
    llm._responses = [LLMResponse(text="Here is a summary paragraph.", model="m")]

    answer = await use_cases.agent.ask(alice, document.id, instruction="explain")

    assert answer.blocks and answer.blocks[0]["type"] == "paragraph"


# ---- tool registry -----------------------------------------------------------


def _spec(name: str):
    from cyberarche.application.ports.llm import ToolSpec

    return ToolSpec(name=name, description="d", parameters={"type": "object"})


def test_tool_registry_rejects_a_duplicate_name():
    from cyberarche.application.use_cases.agent import ToolRegistry

    registry = ToolRegistry()

    async def handler(caller, arguments):
        return "ok"

    registry.register(_spec("t"), handler)
    with pytest.raises(ValidationFailed):
        registry.register(_spec("t"), handler)


async def test_tool_registry_dispatch_unknown_tool_reports_error(alice):
    from cyberarche.application.use_cases.agent import ToolRegistry

    registry = ToolRegistry()
    result = await registry.dispatch(
        alice, ToolCall(id="c", name="nope", arguments={})
    )
    assert result == "error: unknown tool 'nope'"


async def test_tool_registry_returns_handler_failures_to_the_model(alice):
    from cyberarche.application.use_cases.agent import ToolRegistry

    registry = ToolRegistry()

    async def handler(caller, arguments):
        raise RuntimeError("boom")

    registry.register(_spec("t"), handler)
    result = await registry.dispatch(alice, ToolCall(id="c", name="t", arguments={}))
    assert result == "error: boom"


# ---- document lookup guards ---------------------------------------------------


async def test_ask_unknown_document_raises_not_found(use_cases, llm, alice):
    from cyberarche.domain.errors import NotFound
    from cyberarche.domain.ids import DocumentId

    with pytest.raises(NotFound):
        await use_cases.agent.ask(alice, DocumentId("ghost"), instruction="hi")


async def test_ask_trashed_document_raises_not_found(use_cases, llm, alice):
    from cyberarche.domain.errors import NotFound

    _, document = await make_document(use_cases, alice)
    await use_cases.documents.trash(alice, document.id)

    with pytest.raises(NotFound):
        await use_cases.agent.ask(alice, document.id, instruction="hi")


async def test_history_skips_blank_turns_and_clips_long_ones(use_cases, llm, alice):
    _, document = await make_document(use_cases, alice)
    llm._responses = [LLMResponse(text="ok", model="m")]

    await use_cases.agent.ask(
        alice,
        document.id,
        instruction="hi",
        history=[("user", "   "), ("user", "y" * 5000)],
    )

    sent = llm.requests[0]
    assert [m.role for m in sent] == ["system", "user", "user"]  # blank skipped
    assert len(sent[1].content) == 4000  # clipped to the history budget


async def test_draft_prefixes_the_instruction_and_returns_blocks(
    use_cases, llm, alice
):
    _, document = await make_document(use_cases, alice)
    llm._responses = [LLMResponse(text="A drafted paragraph.", model="m")]

    blocks = await use_cases.agent.draft(
        alice, document.id, instruction="a launch plan"
    )

    assert blocks and blocks[0]["type"] == "paragraph"
    prompt = llm.requests[0][-1].content
    assert "Draft the following as document content:" in prompt
    assert "a launch plan" in prompt


async def test_read_document_tool_reads_another_accessible_document(
    use_cases, llm, alice
):
    _, document = await make_document(use_cases, alice)
    _, other = await make_document(use_cases, alice, title="Roadmap")
    await seed_blocks(use_cases, alice, other.id, ["Q3 goals"])
    llm._responses = [
        LLMResponse(
            text="",
            tool_calls=(
                ToolCall(
                    id="c1",
                    name="read_document",
                    arguments={"document_id": other.id},
                ),
            ),
        ),
        LLMResponse(text="ok", model="m"),
    ]

    answer = await use_cases.agent.ask(alice, document.id, instruction="read it")

    call = next(c for c in answer.tool_calls if c.name == "read_document")
    assert call.ok
    assert "# Roadmap" in call.result and "Q3 goals" in call.result


async def test_read_document_tool_reports_missing_document_as_error(
    use_cases, llm, alice
):
    _, document = await make_document(use_cases, alice)
    llm._responses = [
        LLMResponse(
            text="",
            tool_calls=(
                ToolCall(
                    id="c1",
                    name="read_document",
                    arguments={"document_id": "ghost"},
                ),
            ),
        ),
        LLMResponse(text="ok", model="m"),
    ]

    answer = await use_cases.agent.ask(alice, document.id, instruction="read it")

    call = next(c for c in answer.tool_calls if c.name == "read_document")
    assert not call.ok and call.result.startswith("error:")


# ---- background (autonomous) runs ---------------------------------------------


async def test_run_background_succeeds_and_reports_workspace(use_cases, llm, alice):
    workspace, document = await make_document(use_cases, alice)
    llm._responses = [LLMResponse(text="daily report done", model="m")]

    result = await use_cases.agent.run_background(
        alice, document.id, instruction="write the report"
    )

    assert result.text == "daily report done"
    assert result.outcome == "succeeded"
    assert result.edited is False
    assert result.tools_used == []
    assert result.workspace_id == workspace.id


async def test_run_background_refuses_destructive_tools(use_cases, llm, alice):
    _, document = await make_document(use_cases, alice)
    await seed_blocks(use_cases, alice, document.id, ["precious"])
    llm._responses = [
        LLMResponse(
            text="",
            tool_calls=(
                ToolCall(id="c1", name="delete_block", arguments={"block_id": "b1"}),
            ),
        ),
        LLMResponse(text="could not delete", model="m"),
    ]

    result = await use_cases.agent.run_background(
        alice, document.id, instruction="clean up"
    )

    # The refusal goes back to the model, and the block survives.
    tool_reply = llm.requests[1][-1].tool_result.content
    assert "destructive tools are disabled" in tool_reply
    state = await use_cases.realtime.current_state(alice, document.id)
    assert use_cases.agent._engine.read_blocks(state)[0]["data"]["text"] == "precious"
    assert result.outcome == "succeeded"


async def test_background_tool_list_omits_destructive_tools(use_cases, alice):
    _, document = await make_document(use_cases, alice)

    offered = {
        spec.name
        for spec in await use_cases.agent._available_tools(
            alice, document.workspace_id, document.id, None, None, background=True
        )
    }
    assert "delete_block" not in offered
    assert {"insert_blocks", "update_block", "update_table"} <= offered


async def test_run_background_stops_at_the_round_limit(use_cases, llm, alice):
    _, document = await make_document(use_cases, alice)
    insert = LLMResponse(
        text="",
        tool_calls=(
            ToolCall(
                id="c",
                name="insert_blocks",
                arguments={"blocks": [{"type": "paragraph", "data": {"text": "x"}}]},
            ),
        ),
    )
    llm._responses = [insert] * 10

    result = await use_cases.agent.run_background(
        alice, document.id, instruction="loop", max_tool_rounds=1
    )

    assert result.outcome == "stopped_rounds"
    assert result.edited is True
    assert result.tools_used == ["insert_blocks"]


async def test_run_background_stops_at_the_action_limit_mid_response(
    use_cases, llm, alice
):
    _, document = await make_document(use_cases, alice)
    llm._responses = [
        LLMResponse(
            text="",
            tool_calls=(
                ToolCall(
                    id="c1",
                    name="insert_blocks",
                    arguments={"blocks": [{"type": "paragraph", "data": {"text": "a"}}]},
                ),
                ToolCall(
                    id="c2",
                    name="insert_blocks",
                    arguments={"blocks": [{"type": "paragraph", "data": {"text": "b"}}]},
                ),
            ),
        ),
        LLMResponse(text="never reached", model="m"),
    ]

    result = await use_cases.agent.run_background(
        alice, document.id, instruction="loop", max_actions=1
    )

    assert result.outcome == "stopped_actions"
    assert result.tools_used == ["insert_blocks"]  # the second call never ran


async def test_run_background_stops_at_the_deadline(use_cases, llm, alice):
    _, document = await make_document(use_cases, alice)
    insert = LLMResponse(
        text="",
        tool_calls=(
            ToolCall(
                id="c",
                name="insert_blocks",
                arguments={"blocks": [{"type": "paragraph", "data": {"text": "x"}}]},
            ),
        ),
    )
    llm._responses = [insert] * 3

    result = await use_cases.agent.run_background(
        alice, document.id, instruction="loop", max_wall_seconds=0
    )

    assert result.outcome == "stopped_timeout"
    assert result.tools_used == []  # timed out before any tool ran


# ---- editing tool argument handling --------------------------------------------


async def test_insert_blocks_tool_requires_blocks(use_cases, alice):
    _, document = await make_document(use_cases, alice)
    result = await use_cases.agent._run_editing_tool(
        alice, document.id, "insert_blocks", {"blocks": []}
    )
    assert result == "error: no blocks provided"


async def test_editing_tool_reports_missing_arguments_as_error(use_cases, alice):
    _, document = await make_document(use_cases, alice)
    result = await use_cases.agent._run_editing_tool(
        alice, document.id, "update_block", {"text": "no block id"}
    )
    assert result.startswith("error:")


async def test_editing_tool_unknown_operation_is_an_error(use_cases, alice):
    _, document = await make_document(use_cases, alice)
    result = await use_cases.agent._run_editing_tool(
        alice, document.id, "explode", {}
    )
    assert result == "error: unknown operation explode"


async def test_update_table_without_header_keeps_existing_header(use_cases, alice):
    _, document = await make_document(use_cases, alice)
    await use_cases.agent.apply_blocks(
        alice,
        document.id,
        [
            {
                "id": "t1",
                "type": "table",
                "data": {"header": ["Name"], "rows": [["old"]]},
            }
        ],
    )

    result = await use_cases.agent._run_editing_tool(
        alice, document.id, "update_table", {"block_id": "t1", "rows": [["new"]]}
    )

    assert result == "updated table t1"
    state = await use_cases.realtime.current_state(alice, document.id)
    table = next(
        b for b in use_cases.agent._engine.read_blocks(state) if b["type"] == "table"
    )
    assert table["data"]["rows"] == [["new"]]
    assert table["data"]["header"] == ["Name"]  # merged, not dropped


# ---- image generation guard rails ----------------------------------------------


async def test_generate_image_requires_a_prompt(use_cases, alice):
    workspace, document = await make_document(use_cases, alice)
    result = await use_cases.agent._run_generate_image(
        alice, workspace.id, document.id, {"prompt": "   "}
    )
    assert result == "error: prompt required"


async def test_generate_image_denies_a_viewer(use_cases, memberships, clock, alice):
    from tests.conftest import caller

    viewer = caller("carol", "acme")
    workspace, document = await make_document(use_cases, alice)
    await memberships.add_workspace_member(
        WorkspaceMembership(
            workspace_id=workspace.id, user_id=viewer.user_id,
            role=Role.VIEWER, granted_at=clock.now(),
        )
    )

    result = await use_cases.agent._run_generate_image(
        viewer, workspace.id, document.id, {"prompt": "a fox"}
    )
    assert result == "error: you do not have permission to edit this document"


async def test_generate_image_maps_provider_failure_to_error(use_cases, alice):
    class _FailingImages:
        async def generate(self, prompt, *, size="1024x1024"):
            raise RuntimeError("provider down")

    workspace, document = await make_document(use_cases, alice)
    use_cases.agent._images = _FailingImages()

    result = await use_cases.agent._run_generate_image(
        alice, workspace.id, document.id, {"prompt": "a fox"}
    )
    assert result == "error: provider down"


# ---- mind map guard rails --------------------------------------------------------


async def test_create_mindmap_requires_central_and_branches(use_cases, alice):
    _, document = await make_document(use_cases, alice)

    result = await use_cases.agent._run_create_mindmap(
        alice, document.id, {"central": "", "branches": ["a"]}
    )
    assert result == "error: central topic required"

    result = await use_cases.agent._run_create_mindmap(
        alice, document.id, {"central": "AI", "branches": []}
    )
    assert result == "error: at least one branch required"

    result = await use_cases.agent._run_create_mindmap(
        alice, document.id, {"central": "AI", "branches": "oops"}
    )
    assert result == "error: at least one branch required"


async def test_create_mindmap_denies_a_viewer(use_cases, memberships, clock, alice):
    from tests.conftest import caller

    viewer = caller("carol", "acme")
    workspace, document = await make_document(use_cases, alice)
    await memberships.add_workspace_member(
        WorkspaceMembership(
            workspace_id=workspace.id, user_id=viewer.user_id,
            role=Role.VIEWER, granted_at=clock.now(),
        )
    )

    result = await use_cases.agent._run_create_mindmap(
        viewer, document.id, {"central": "AI", "branches": ["ML"]}
    )
    assert result == "error: you do not have permission to edit this document"


# ---- meetings tools ---------------------------------------------------------------


async def test_agent_lists_meetings_with_delegated_token(
    use_cases, llm, meetings, alice
):
    _, document = await make_document(use_cases, alice)
    llm._responses = [
        LLMResponse(
            text="",
            tool_calls=(ToolCall(id="c1", name="list_meetings", arguments={}),),
        ),
        LLMResponse(text="here they are", model="m"),
    ]

    answer = await use_cases.agent.ask(
        alice, document.id, instruction="list my meetings", access_token="tok-m"
    )

    assert meetings.tokens == ["tok-m"]
    call = next(c for c in answer.tool_calls if c.name == "list_meetings")
    assert call.result.startswith("meetings:")
    assert "id=rec-1" in call.result and "Weekly standup" in call.result


async def test_meetings_tool_requires_sign_in(use_cases, alice):
    result = await use_cases.agent._run_meetings_tool(
        ToolCall(id="c", name="list_meetings", arguments={}), None
    )
    assert result == "error: sign in required to access meetings"


async def test_meetings_tool_validates_arguments(use_cases, alice):
    result = await use_cases.agent._run_meetings_tool(
        ToolCall(id="c", name="get_meeting_transcript", arguments={}), "tok"
    )
    assert result == "error: recording_id required"

    result = await use_cases.agent._run_meetings_tool(
        ToolCall(id="c", name="ask_meetings", arguments={"question": " "}), "tok"
    )
    assert result == "error: question required"

    result = await use_cases.agent._run_meetings_tool(
        ToolCall(id="c", name="bogus_meetings", arguments={}), "tok"
    )
    assert result == "error: unknown meetings tool bogus_meetings"


def test_meetings_error_maps_provider_statuses():
    from cyberarche.application.use_cases.agent import _meetings_error

    class _Resp:
        def __init__(self, status):
            self.status_code = status

    class _HttpError(Exception):
        def __init__(self, status):
            super().__init__(f"HTTP {status}")
            self.response = _Resp(status)

    assert "not signed in" in _meetings_error(_HttpError(401))
    assert "not signed in" in _meetings_error(_HttpError(403))
    assert "not found" in _meetings_error(_HttpError(404))
    assert _meetings_error(RuntimeError("weird")) == "weird"
    assert _meetings_error(RuntimeError("")) == "meetings service error"


async def test_meetings_provider_failure_is_returned_as_error(use_cases, alice):
    class _FailingMeetings:
        async def list_recordings(self, access_token, *, limit=20):
            raise RuntimeError("down")

    use_cases.agent._meetings = _FailingMeetings()
    result = await use_cases.agent._run_meetings_tool(
        ToolCall(id="c", name="list_meetings", arguments={}), "tok"
    )
    assert result == "error: down"


def test_render_meeting_list_and_transcript_edge_cases():
    from cyberarche.application.ports.meetings import MeetingTranscript
    from cyberarche.application.use_cases.agent import (
        _render_meeting_list,
        _render_meeting_transcript,
    )

    assert _render_meeting_list([]) == "no meetings found"

    bare = MeetingTranscript(
        id="rec-2", status="processing", captured_at=None, headline=None,
        abstract=None, bullets=[], action_items=[], transcript=None,
    )
    rendered = _render_meeting_transcript(bare)
    assert "meeting rec-2 (processing)" in rendered
    assert "(transcript not ready yet)" in rendered


# ---- web/media tools ---------------------------------------------------------------


async def test_agent_youtube_playlist_forwards_token(use_cases, llm, web_media, alice):
    _, document = await make_document(use_cases, alice)
    llm._responses = [
        LLMResponse(
            text="",
            tool_calls=(
                ToolCall(
                    id="c1", name="youtube_playlist", arguments={"playlist": "pl-1"}
                ),
            ),
        ),
        LLMResponse(text="listed", model="m"),
    ]

    answer = await use_cases.agent.ask(
        alice, document.id, instruction="list the playlist", access_token="tok-pl"
    )

    assert web_media.tokens == ["tok-pl"]
    assert web_media.playlists == ["pl-1"]
    call = next(c for c in answer.tool_calls if c.name == "youtube_playlist")
    assert call.result.startswith("playlist videos:")
    assert "Ep 1" in call.result and "https://y.test/v2" in call.result


async def test_web_media_tool_validates_arguments(use_cases, alice):
    result = await use_cases.agent._run_web_media_tool(
        ToolCall(id="c", name="web_search", arguments={"query": " "}), "tok"
    )
    assert result == "error: query required"

    result = await use_cases.agent._run_web_media_tool(
        ToolCall(id="c", name="youtube_transcript", arguments={}), "tok"
    )
    assert result == "error: video required"

    result = await use_cases.agent._run_web_media_tool(
        ToolCall(id="c", name="youtube_playlist", arguments={"playlist": ""}), "tok"
    )
    assert result == "error: playlist required"

    result = await use_cases.agent._run_web_media_tool(
        ToolCall(id="c", name="bogus_media", arguments={}), "tok"
    )
    assert result == "error: unknown web/media tool bogus_media"


def test_web_media_error_maps_auth_and_missing_statuses():
    from cyberarche.application.use_cases.agent import _web_media_error

    class _Resp:
        def __init__(self, status):
            self.status_code = status

    class _HttpError(Exception):
        def __init__(self, status):
            super().__init__(f"HTTP {status}")
            self.response = _Resp(status)

    assert "not signed in" in _web_media_error(_HttpError(401))
    assert "not found" in _web_media_error(_HttpError(404))
    assert _web_media_error(RuntimeError("odd")) == "odd"
    assert _web_media_error(RuntimeError("")) == "web/media service unavailable"


async def test_web_media_provider_failure_is_returned_as_error(use_cases, alice):
    class _FailingWebMedia:
        async def search(self, access_token, query, *, num=10):
            raise RuntimeError("down")

    use_cases.agent._web_media = _FailingWebMedia()
    result = await use_cases.agent._run_web_media_tool(
        ToolCall(id="c", name="web_search", arguments={"query": "x"}), "tok"
    )
    assert result == "error: down"


def test_render_web_media_edge_cases():
    from cyberarche.application.ports.web_media import Transcript
    from cyberarche.application.use_cases.agent import (
        _render_playlist,
        _render_search,
        _render_transcript,
    )

    assert _render_search([]) == "no results found"
    assert _render_playlist([]) == "no videos found"

    silent = Transcript(video_id="v9", text="", title=None, lang=None)
    assert _render_transcript(silent) == "transcript for video v9\n(no transcript available)"


# ---- persona (durable memory) tools -------------------------------------------------


async def test_persona_tools_report_unconfigured_when_absent(use_cases, alice):
    workspace, _ = await make_document(use_cases, alice)
    use_cases.agent._persona = None
    result = await use_cases.agent._run_persona_tool(
        alice, workspace.id, ToolCall(id="c", name="remember", arguments={"note": "x"})
    )
    assert result == "error: agent memory is not configured"


async def test_persona_tool_validates_arguments(use_cases, alice):
    workspace, _ = await make_document(use_cases, alice)

    result = await use_cases.agent._run_persona_tool(
        alice, workspace.id, ToolCall(id="c", name="remember", arguments={"note": " "})
    )
    assert result == "error: note required"

    result = await use_cases.agent._run_persona_tool(
        alice, workspace.id, ToolCall(id="c", name="forget", arguments={})
    )
    assert result == "error: memory_id required"

    result = await use_cases.agent._run_persona_tool(
        alice, workspace.id, ToolCall(id="c", name="bogus_memory", arguments={})
    )
    assert result == "error: unknown memory tool bogus_memory"


async def test_agent_lists_and_forgets_memories_via_tools(use_cases, llm, alice):
    workspace, document = await make_document(use_cases, alice)
    memory = await use_cases.persona.add_memory(
        alice, workspace.id, "We deploy on Fridays."
    )
    llm._responses = [
        LLMResponse(
            text="",
            tool_calls=(ToolCall(id="c1", name="list_memories", arguments={}),),
        ),
        LLMResponse(
            text="",
            tool_calls=(
                ToolCall(id="c2", name="forget", arguments={"memory_id": memory.id}),
            ),
        ),
        LLMResponse(text="forgotten", model="m"),
    ]

    answer = await use_cases.agent.ask(
        alice, document.id, instruction="forget the deploy day"
    )

    listed = next(c for c in answer.tool_calls if c.name == "list_memories")
    assert "We deploy on Fridays." in listed.result
    assert f"id={memory.id}" in listed.result
    forgot = next(c for c in answer.tool_calls if c.name == "forget")
    assert forgot.result == f"forgot memory {memory.id}"
    assert await use_cases.persona.list_memories(alice, workspace.id) == []


async def test_remember_tool_rejects_a_secret_as_an_error_string(use_cases, alice):
    workspace, _ = await make_document(use_cases, alice)
    result = await use_cases.agent._run_persona_tool(
        alice,
        workspace.id,
        ToolCall(
            id="c",
            name="remember",
            arguments={"note": "the API key is sk-proj-ABCDEFGHIJKLMNOPQRSTUVWX"},
        ),
    )
    assert result.startswith("error:") and "secret" in result


def test_render_memories_empty():
    from cyberarche.application.use_cases.agent import _render_memories

    assert _render_memories([]) == "no memories saved for this workspace"


# ---- google tools (agent-side dispatch) ----------------------------------------------


async def test_google_tools_report_unconfigured_when_absent(use_cases, alice):
    workspace, document = await make_document(use_cases, alice)
    use_cases.agent._google = None
    result = await use_cases.agent._run_google_tool(
        alice,
        workspace.id,
        document.id,
        ToolCall(id="c", name="google_gmail_search", arguments={"query": "x"}),
    )
    assert result == "error: Google Workspace is not configured"


async def test_google_tool_failure_is_returned_as_error(use_cases, alice):
    # No Google connection → the use case raises and the agent maps it to error text.
    workspace, document = await make_document(use_cases, alice)
    result = await use_cases.agent._run_google_tool(
        alice,
        workspace.id,
        document.id,
        ToolCall(id="c", name="google_gmail_search", arguments={"query": "x"}),
    )
    assert result.startswith("error:")


async def test_google_read_tools_render_results(use_cases, google_port, alice):
    from tests.test_google_workspace import _connect

    workspace, document = await make_document(use_cases, alice)
    await _connect(
        use_cases, google_port, alice, workspace.id,
        ["gmail_read", "gmail_compose", "calendar", "drive"],
    )

    def call(name, arguments):
        return use_cases.agent._run_google_tool(
            alice, workspace.id, document.id,
            ToolCall(id="c", name=name, arguments=arguments),
        )

    search = await call("google_gmail_search", {"query": "hello"})
    assert search.startswith("gmail results:") and "id=m1" in search

    read = await call("google_gmail_read", {"message_id": "m1"})
    assert "Subject — from a@b.com" in read and "full body" in read

    draft = await call(
        "google_gmail_draft", {"to": "x@y.z", "subject": "s", "body": "b"}
    )
    assert "draft created (id=draft-1)" in draft
    assert "the agent does not send mail" in draft

    events = await call(
        "google_calendar_list", {"time_min": "t0", "time_max": "t1"}
    )
    assert events.startswith("calendar events:") and "Standup" in events

    busy = await call("google_free_busy", {"time_min": "t0", "time_max": "t1"})
    assert busy.startswith("busy periods:") and "t0 → t1" in busy

    files = await call("google_drive_search", {"query": "plan"})
    assert files.startswith("drive files:") and "id=d1" in files

    unknown = await call("google_gmail_send", {})
    assert unknown == "error: unknown Google tool google_gmail_send"


async def test_google_empty_results_render_friendly_text(
    use_cases, google_port, alice
):
    from tests.test_google_workspace import _connect

    workspace, document = await make_document(use_cases, alice)
    await _connect(
        use_cases, google_port, alice, workspace.id, ["calendar", "drive"]
    )

    async def none_busy(access_token, *, time_min, time_max):
        return []

    async def no_files(access_token, query, *, limit=10):
        return []

    async def empty_doc(access_token, doc_id):
        return []

    google_port.calendar_free_busy = none_busy
    google_port.drive_search = no_files
    google_port.import_doc = empty_doc

    def call(name, arguments):
        return use_cases.agent._run_google_tool(
            alice, workspace.id, document.id,
            ToolCall(id="c", name=name, arguments=arguments),
        )

    assert await call(
        "google_free_busy", {"time_min": "t0", "time_max": "t1"}
    ) == "no busy periods in that window"
    assert await call("google_drive_search", {"query": "x"}) == "no files found"
    assert await call("google_import_doc", {"doc_id": "d1"}) == "the doc was empty"


async def test_google_tools_offered_match_the_granted_scopes(
    use_cases, google_port, alice
):
    from tests.test_google_workspace import _connect

    workspace, document = await make_document(use_cases, alice)
    await _connect(
        use_cases, google_port, alice, workspace.id,
        ["gmail_read", "gmail_compose", "calendar", "drive"],
    )

    offered = {
        spec.name
        for spec in await use_cases.agent._available_tools(
            alice, workspace.id, document.id, None, None
        )
    }
    assert {
        "google_gmail_search",
        "google_gmail_read",
        "google_gmail_draft",
        "google_calendar_list",
        "google_free_busy",
        "google_drive_search",
        "google_import_doc",
    } <= offered


def test_render_gmail_and_events_empty():
    from cyberarche.application.use_cases.agent import _render_events, _render_gmail

    assert _render_gmail([]) == "no messages found"
    assert _render_events([]) == "no events in that window"


# ---- run_python guard rails -----------------------------------------------------------


async def test_run_python_requires_code(use_cases, alice):
    workspace, document = await make_document(use_cases, alice)
    result = await use_cases.agent._run_python(
        alice, workspace.id, document.id, {"code": "  "}
    )
    assert result == "error: code required"


async def test_run_python_needs_blob_storage_too(use_cases, alice):
    workspace, document = await make_document(use_cases, alice)
    use_cases.agent._blobs = None
    result = await use_cases.agent._run_python(
        alice, workspace.id, document.id, {"code": "1 + 1"}
    )
    assert result == "error: code execution is not configured"


async def test_run_python_denies_a_viewer(use_cases, memberships, clock, alice):
    from tests.conftest import caller

    viewer = caller("carol", "acme")
    workspace, document = await make_document(use_cases, alice)
    await memberships.add_workspace_member(
        WorkspaceMembership(
            workspace_id=workspace.id, user_id=viewer.user_id,
            role=Role.VIEWER, granted_at=clock.now(),
        )
    )
    result = await use_cases.agent._run_python(
        viewer, workspace.id, document.id, {"code": "1 + 1"}
    )
    assert result == "error: you do not have permission to edit this document"


async def test_run_python_maps_interpreter_failure_to_error(use_cases, alice):
    class _BrokenInterpreter:
        async def run(self, code):
            raise RuntimeError("sandbox unreachable")

    workspace, document = await make_document(use_cases, alice)
    use_cases.agent._code = _BrokenInterpreter()
    result = await use_cases.agent._run_python(
        alice, workspace.id, document.id, {"code": "1 + 1"}
    )
    assert result == "error: sandbox unreachable"


def test_summarize_python_reports_failure_result_and_tables():
    from cyberarche.application.ports.code_exec import CodeExecutionResult
    from cyberarche.application.use_cases.agent import _summarize_python

    outcome = CodeExecutionResult(
        success=False,
        stdout="partial\n",
        stderr="Traceback: boom",
        result="42",
        error=None,
        images=[],
        tables=["| a | b |", "| c |", "| never shown |"],
    )
    summary = _summarize_python(outcome, inserted=0)

    assert summary.startswith("failed")
    assert "stdout:\npartial" in summary
    assert "result: 42" in summary
    assert "error:\nTraceback: boom" in summary  # stderr used when error is None
    assert summary.count("table:") == 2  # capped at two tables
    assert "never shown" not in summary
    assert "inserted" not in summary  # no figures were inserted


# ---- block normalization / answer parsing extras ---------------------------------------


def test_normalize_maps_src_and_href_to_url():
    b = _normalize_block({"type": "image", "data": {"src": "https://x/i.png"}})
    assert b["data"]["url"] == "https://x/i.png"
    b = _normalize_block({"type": "embed", "data": {"href": "https://x/v"}})
    assert b["data"]["url"] == "https://x/v"
    # A correct url is kept.
    b = _normalize_block({"type": "image", "data": {"url": "https://x/ok.png"}})
    assert b["data"]["url"] == "https://x/ok.png"


def test_answer_blocks_parses_a_divider():
    blocks = _answer_blocks(_Ids(), "above\n\n---\n\nbelow")
    assert [b["type"] for b in blocks] == ["paragraph", "divider", "paragraph"]


async def test_available_tools_without_persona_omits_memory_tools(use_cases, alice):
    _, document = await make_document(use_cases, alice)
    use_cases.agent._persona = None

    offered = {
        spec.name
        for spec in await use_cases.agent._available_tools(
            alice, document.workspace_id, document.id, None, None
        )
    }
    assert not ({"remember", "list_memories", "forget"} & offered)


async def test_ask_without_persona_uses_the_plain_system_prompt(
    use_cases, llm, alice
):
    _, document = await make_document(use_cases, alice)
    use_cases.agent._persona = None
    llm._responses = [LLMResponse(text="ok", model="m")]

    await use_cases.agent.ask(alice, document.id, instruction="hi")

    system = llm.requests[0][0]
    assert system.role == "system"
    assert "Remembered facts" not in system.content


# --- PostgresAgentRunRepository: SQL translation over a recorded stub pool ---


class _StubPool:
    """Records every query and returns canned rows — no real Postgres."""

    def __init__(self, rows: list[dict] | None = None) -> None:
        self.rows = rows or []
        self.calls: list[tuple[str, str, tuple]] = []

    async def execute(self, query: str, *args) -> str:
        self.calls.append(("execute", query, args))
        return "INSERT 0 1"

    async def fetch(self, query: str, *args) -> list[dict]:
        self.calls.append(("fetch", query, args))
        return self.rows


def _run(**kw):
    from datetime import UTC, datetime

    from cyberarche.application.ports.agent import AgentRun
    from cyberarche.domain.ids import AgentRunId, DocumentId, TenantId, UserId

    now = datetime(2026, 1, 1, tzinfo=UTC)
    defaults = dict(
        id=AgentRunId("run-1"),
        tenant_id=TenantId("acme"),
        user_id=UserId("alice"),
        document_id=DocumentId("doc-1"),
        model="claude",
        prompt="Summarize",
        tools_used=("read_document", "edit_blocks"),
        outcome="ok",
        started_at=now,
        finished_at=now,
    )
    defaults.update(kw)
    return AgentRun(**defaults)


async def test_postgres_agent_run_add_persists_every_column():
    import json

    from cyberarche.adapters.outbound.postgres.agent_runs import (
        PostgresAgentRunRepository,
    )

    pool = _StubPool()
    run = _run()
    await PostgresAgentRunRepository(pool).add(run)

    kind, query, args = pool.calls[0]
    assert kind == "execute" and "INSERT INTO agent_runs" in query
    assert args == (
        run.id, run.tenant_id, run.document_id, run.user_id, run.model,
        run.prompt, json.dumps(["read_document", "edit_blocks"]),
        run.outcome, run.started_at, run.finished_at,
    )


async def test_postgres_agent_run_list_maps_rows_back_to_domain():
    from cyberarche.adapters.outbound.postgres.agent_runs import (
        PostgresAgentRunRepository,
    )
    from cyberarche.domain.ids import DocumentId, TenantId

    stored = _run()
    row = {
        "id": stored.id, "tenant_id": stored.tenant_id,
        "user_id": stored.user_id, "document_id": stored.document_id,
        "model": stored.model, "prompt": stored.prompt,
        "tools_used": '["read_document", "edit_blocks"]',
        "outcome": stored.outcome, "started_at": stored.started_at,
        "finished_at": stored.finished_at,
    }
    pool = _StubPool(rows=[row])

    runs = await PostgresAgentRunRepository(pool).list_for_document(
        TenantId("acme"), DocumentId("doc-1")
    )

    assert runs == [stored]
    kind, query, args = pool.calls[0]
    assert kind == "fetch" and "FROM agent_runs" in query
    assert args == (TenantId("acme"), DocumentId("doc-1"))


async def test_postgres_agent_run_list_handles_null_document_id():
    """Workspace-level runs (no document) round-trip document_id=None."""
    from cyberarche.adapters.outbound.postgres.agent_runs import (
        PostgresAgentRunRepository,
    )
    from cyberarche.domain.ids import DocumentId, TenantId

    stored = _run(document_id=None, tools_used=(), outcome=None)
    row = {
        "id": stored.id, "tenant_id": stored.tenant_id,
        "user_id": stored.user_id, "document_id": None,
        "model": stored.model, "prompt": stored.prompt,
        "tools_used": "[]", "outcome": None,
        "started_at": stored.started_at, "finished_at": stored.finished_at,
    }
    pool = _StubPool(rows=[row])

    runs = await PostgresAgentRunRepository(pool).list_for_document(
        TenantId("acme"), DocumentId("doc-1")
    )
    assert runs == [stored]
    assert runs[0].document_id is None and runs[0].tools_used == ()


async def test_postgres_agent_run_list_returns_empty_for_no_rows():
    from cyberarche.adapters.outbound.postgres.agent_runs import (
        PostgresAgentRunRepository,
    )
    from cyberarche.domain.ids import DocumentId, TenantId

    pool = _StubPool(rows=[])
    runs = await PostgresAgentRunRepository(pool).list_for_document(
        TenantId("acme"), DocumentId("missing")
    )
    assert runs == []
