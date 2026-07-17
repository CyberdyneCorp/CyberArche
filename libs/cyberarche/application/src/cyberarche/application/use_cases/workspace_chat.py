"""Workspace-wide chat (ai-agent spec): "Chat with your workspace".

A workspace-scoped, conversational assistant grounded in the workspace's
documents — independent of any open document. It composes the existing RAG
knowledge base and full-text search into a single answer, applies the
workspace persona, and considers recent history.

It is READ-ONLY: it calls the LLM with NO tools, so it can never create or
edit a document. Every call requires workspace membership and returns only
content the caller may access (search is itself access-scoped).
"""

from __future__ import annotations

from dataclasses import dataclass

from cyberarche.application.authz import AccessControl
from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.llm import LLMMessage, LLMPort
from cyberarche.application.ports.rag import RagPort, RagQueryMode
from cyberarche.application.ports.repositories import WorkspaceRepository
from cyberarche.application.use_cases.agent_persona import AgentPersonaUseCases
from cyberarche.application.use_cases.search import SearchHit, SearchUseCases
from cyberarche.domain.errors import NotFound
from cyberarche.domain.ids import WorkspaceId
from cyberarche.domain.memberships import Role

_MAX_HISTORY_TURNS = 8
_HISTORY_CHARS = 4000
_SEARCH_LIMIT = 5
_SNIPPET_CHARS = 400

_SYSTEM_PROMPT = (
    "You are CyberArche's workspace assistant. Answer using ONLY the provided "
    "workspace knowledge and document snippets; if the answer is not in them, "
    "say you don't know. You are READ-ONLY: you cannot edit documents, and you "
    "must never claim to have changed anything. Cite the source document "
    "titles you drew from."
)


@dataclass(frozen=True, slots=True)
class ChatSource:
    """A document the answer drew on, so the UI can link back to it."""

    id: str
    title: str


@dataclass(frozen=True, slots=True)
class ChatAnswer:
    text: str
    sources: list[ChatSource]


class WorkspaceChatUseCases:
    def __init__(
        self,
        llm: LLMPort,
        rag: RagPort,
        workspaces: WorkspaceRepository,
        search: SearchUseCases,
        access: AccessControl,
        persona: AgentPersonaUseCases | None = None,
    ) -> None:
        self._llm = llm
        self._rag = rag
        self._workspaces = workspaces
        self._search = search
        self._access = access
        self._persona = persona

    async def ask(
        self,
        caller: CallerContext,
        workspace_id: WorkspaceId,
        *,
        instruction: str,
        history: list[tuple[str, str]] | None = None,
    ) -> ChatAnswer:
        """Answer a question grounded in the workspace, read-only.

        Retrieves the workspace's RAG answer plus the top full-text search hits,
        then synthesizes one conversational reply with the LLM (no tools). The
        reply carries the source documents it drew on. `history` is recent
        (role, content) turns so follow-ups keep context."""
        await self._access.require_workspace(caller, workspace_id, Role.VIEWER)
        rag_answer, hits = await self._grounding(caller, workspace_id, instruction)
        messages = await self._messages(
            caller, workspace_id, instruction, history, rag_answer, hits
        )
        response = await self._llm.complete(messages)
        return ChatAnswer(
            text=response.text,
            sources=[
                ChatSource(id=str(hit.document.id), title=hit.document.title)
                for hit in hits
            ],
        )

    async def _messages(
        self,
        caller: CallerContext,
        workspace_id: WorkspaceId,
        instruction: str,
        history: list[tuple[str, str]] | None,
        rag_answer: str,
        hits: list[SearchHit],
    ) -> list[LLMMessage]:
        system_prompt = _SYSTEM_PROMPT
        if self._persona is not None:
            system_prompt += await self._persona.build_context(
                caller, workspace_id, instruction
            )
        messages = [LLMMessage(role="system", content=system_prompt)]
        for role, content in (history or [])[-_MAX_HISTORY_TURNS:]:
            text = (content or "").strip()
            if not text:
                continue
            normalized = "assistant" if role in ("assistant", "agent") else "user"
            messages.append(
                LLMMessage(role=normalized, content=text[:_HISTORY_CHARS])
            )
        messages.append(
            LLMMessage(
                role="user",
                content=f"{instruction}\n\n{_grounding_block(rag_answer, hits)}",
            )
        )
        return messages

    async def _grounding(
        self, caller: CallerContext, workspace_id: WorkspaceId, instruction: str
    ) -> tuple[str, list[SearchHit]]:
        rag_answer = await self._rag_answer(caller, workspace_id, instruction)
        hits = await self._search.search(
            caller, workspace_id, query=instruction, limit=_SEARCH_LIMIT
        )
        return rag_answer, hits

    async def _rag_answer(
        self, caller: CallerContext, workspace_id: WorkspaceId, instruction: str
    ) -> str:
        """The workspace's RAG answer, or "" when it has no knowledge base yet
        (degrade gracefully — a KB-less workspace still chats over its docs)."""
        workspace = await self._workspaces.get(caller.tenant_id, workspace_id)
        if workspace is None or not workspace.rag_project_slug:
            return ""
        try:
            return await self._rag.query(
                workspace.rag_project_slug,
                query=instruction,
                mode=RagQueryMode.HYBRID,
            )
        except NotFound:
            return ""


def _grounding_block(rag_answer: str, hits: list[SearchHit]) -> str:
    """The retrieval context handed to the model: the RAG answer and the
    matching document titles + snippets."""
    parts: list[str] = []
    if rag_answer.strip():
        parts.append(f"Workspace knowledge base:\n{rag_answer.strip()}")
    if hits:
        lines = [
            f"- {hit.document.title} (id: {hit.document.id})"
            + (f": {hit.snippet.strip()[:_SNIPPET_CHARS]}" if hit.snippet.strip() else "")
            for hit in hits
        ]
        parts.append("Relevant documents:\n" + "\n".join(lines))
    if not parts:
        return "Grounding: (no workspace knowledge or matching documents found)"
    return "Grounding:\n" + "\n\n".join(parts)
