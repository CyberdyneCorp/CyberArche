"""ai-agent spec: workspace-wide chat — grounding, sources, membership,
graceful no-KB degradation, history, read-only (no tools)."""

from __future__ import annotations

import pytest

from cyberarche.application.ports.llm import LLMResponse
from cyberarche.domain.errors import NotAuthorized, NotFound

from tests.test_agent import make_document, seed_blocks


async def test_answer_uses_llm_text_and_sources_from_search(use_cases, llm, alice):
    workspace, document = await make_document(use_cases, alice, title="Roadmap")
    await seed_blocks(use_cases, alice, document.id, ["The launch is on March 3."])
    llm._responses = [LLMResponse(text="It launches March 3.", model="m")]

    answer = await use_cases.workspace_chat.ask(
        alice, workspace.id, instruction="launch"
    )

    assert answer.text == "It launches March 3."
    # Sources come from the full-text search hits.
    assert [s.id for s in answer.sources] == [document.id]
    assert answer.sources[0].title == "Roadmap"


async def test_grounding_block_is_in_the_prompt(use_cases, llm, alice):
    workspace, document = await make_document(use_cases, alice, title="Specs")
    await seed_blocks(use_cases, alice, document.id, ["The API returns JSON."])
    llm._responses = [LLMResponse(text="ok", model="m")]

    await use_cases.workspace_chat.ask(alice, workspace.id, instruction="API")

    # The document snippet and the RAG answer are both handed to the model,
    # and the assistant is told it is read-only.
    system = llm.requests[0][0].content
    prompt = llm.requests[0][-1].content
    assert "READ-ONLY" in system
    assert "The API returns JSON." in prompt
    assert "Specs" in prompt
    # Read-only: the chat calls the LLM with NO tools.
    assert llm.tools_seen[0] == []


async def test_membership_is_required(use_cases, alice, bob_other_tenant):
    workspace, _ = await make_document(use_cases, alice)

    with pytest.raises(NotAuthorized):
        await use_cases.workspace_chat.ask(
            bob_other_tenant, workspace.id, instruction="anything"
        )


async def test_no_knowledge_base_degrades_gracefully(use_cases, llm, rag, alice):
    """A workspace whose RAG project isn't ready must still chat over its docs
    instead of erroring — a NotFound from the RAG service is swallowed."""
    workspace, document = await make_document(use_cases, alice)
    await seed_blocks(use_cases, alice, document.id, ["Doc content here."])
    llm._responses = [LLMResponse(text="grounded answer", model="m")]

    async def _raise_not_found(*_args, **_kwargs):
        raise NotFound("workspace has no knowledge base yet")

    rag.query = _raise_not_found  # type: ignore[method-assign]

    answer = await use_cases.workspace_chat.ask(
        alice, workspace.id, instruction="content"
    )

    assert answer.text == "grounded answer"
    # No RAG section, but the document grounding still flows through.
    prompt = llm.requests[0][-1].content
    assert "Workspace knowledge base" not in prompt
    assert "Doc content here." in prompt


async def test_history_is_passed_to_the_llm(use_cases, llm, alice):
    workspace, _ = await make_document(use_cases, alice)
    llm._responses = [LLMResponse(text="ok", model="m")]

    await use_cases.workspace_chat.ask(
        alice,
        workspace.id,
        instruction="and after that?",
        history=[
            ("user", "what happened first?"),
            ("assistant", "the kickoff meeting"),
        ],
    )

    sent = llm.requests[0]
    assert [m.role for m in sent] == ["system", "user", "assistant", "user"]
    assert "what happened first?" in sent[1].content
    assert "the kickoff meeting" in sent[2].content
    assert "and after that?" in sent[-1].content
