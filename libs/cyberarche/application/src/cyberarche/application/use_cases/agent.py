"""AI agent use cases (ai-agent spec).

The agent is document-scoped: its context is the document's block tree plus
the workspace's RAG knowledge. It edits through the same CRDT channel as
humans (attributed "agent:<user>"), and every run is audited.

Tool calls are dispatched through a registry; group 9/10 plug the MCP
server tools and external connectors into the same registry.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from cyberarche.application.authz import AccessControl
from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.agent import AgentRun, AgentRunRepository
from cyberarche.application.ports.crdt import CrdtEnginePort
from cyberarche.application.ports.extraction import FileExtractorPort
from cyberarche.application.ports.llm import (
    LLMMessage,
    LLMPort,
    ToolCall,
    ToolResult,
    ToolSpec,
)
from cyberarche.application.ports.repositories import DocumentRepository
from cyberarche.application.ports.telemetry import ClockPort, IdPort
from cyberarche.application.use_cases.connectors import ConnectorUseCases
from cyberarche.application.use_cases.knowledge import KnowledgeUseCases
from cyberarche.application.use_cases.realtime import RealtimeUseCases
from cyberarche.domain.blocks import validate_block_type
from cyberarche.domain.connectors import split_qualified
from cyberarche.domain.ids import WorkspaceId
from cyberarche.domain.errors import NotAuthorized, NotFound, ValidationFailed
from cyberarche.domain.ids import AgentRunId, ConnectorId, DocumentId
from cyberarche.domain.memberships import Role

MAX_TOOL_ROUNDS = 8

ToolHandler = Callable[[CallerContext, dict], Awaitable[str]]


@dataclass(frozen=True, slots=True)
class RegisteredTool:
    spec: ToolSpec
    handler: ToolHandler


class ToolRegistry:
    """Named tools the agent may call, permission-scoped via the caller."""

    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(self, spec: ToolSpec, handler: ToolHandler) -> None:
        if spec.name in self._tools:
            raise ValidationFailed(f"tool already registered: {spec.name}")
        self._tools[spec.name] = RegisteredTool(spec, handler)

    def specs(self) -> list[ToolSpec]:
        return [tool.spec for tool in self._tools.values()]

    async def dispatch(self, caller: CallerContext, call: ToolCall) -> str:
        tool = self._tools.get(call.name)
        if tool is None:
            return f"error: unknown tool {call.name!r}"
        try:
            return await tool.handler(caller, call.arguments)
        except Exception as error:  # tool failures go back to the model
            return f"error: {error}"


@dataclass(frozen=True, slots=True)
class AgentAnswer:
    """An answer plus the blocks the user may insert into the document."""

    text: str
    blocks: list[dict]


_SYSTEM_PROMPT = (
    "You are CyberArche's document agent. You help create, summarize, "
    "restructure, and EDIT the open document. Ground answers in the provided "
    "document content and knowledge-base results; cite block ids (e.g. "
    "[block:abc123]) or source filenames for every claim you take from them. "
    "The open document and its block ids are given to you — never look it up "
    "by title. To change it, call insert_blocks / update_block / delete_block; "
    "these act on the open document only. When asked to produce content "
    "without editing, return plain paragraphs separated by blank lines."
)


class AgentUseCases:
    def __init__(
        self,
        llm: LLMPort,
        documents: DocumentRepository,
        realtime: RealtimeUseCases,
        knowledge: KnowledgeUseCases,
        runs: AgentRunRepository,
        extractor: FileExtractorPort,
        engine: CrdtEnginePort,
        access: AccessControl,
        clock: ClockPort,
        ids: IdPort,
        tools: ToolRegistry | None = None,
        model_name: str = "",
        connectors: ConnectorUseCases | None = None,
    ) -> None:
        self._llm = llm
        self._documents = documents
        self._realtime = realtime
        self._knowledge = knowledge
        self._runs = runs
        self._extractor = extractor
        self._engine = engine
        self._access = access
        self._clock = clock
        self._ids = ids
        self._tools = tools or ToolRegistry()
        self._model_name = model_name
        self._connectors = connectors
        self._register_builtin_tools()

    # ---- public capabilities ----------------------------------------------

    async def ask(
        self,
        caller: CallerContext,
        document_id: DocumentId,
        *,
        instruction: str,
        session_connectors: set[str] | None = None,
    ) -> AgentAnswer:
        """Answer/act grounded in the document, with tool use.

        The reply always carries insertable blocks so the UI can offer
        'Insert as block' on any answer (ai-agent spec). `session_connectors`,
        if given, restricts external MCP tools to that opt-in set for this run.
        """
        document, context = await self._document_context(caller, document_id)
        messages = [
            LLMMessage(role="system", content=_SYSTEM_PROMPT),
            LLMMessage(
                role="user",
                content=(
                    f"Open document '{document.title}' (id: {document.id}).\n"
                    f"Its blocks:\n{context}\n\n{instruction}"
                ),
            ),
        ]
        text = await self._run_loop(
            caller,
            document_id,
            document.workspace_id,
            instruction,
            messages,
            session_connectors,
        )
        return AgentAnswer(text=text, blocks=_paragraph_blocks(self._ids, text))

    async def summarize(
        self,
        caller: CallerContext,
        document_id: DocumentId,
        *,
        block_ids: list[str] | None = None,
    ) -> list[dict]:
        if block_ids:
            selection = ", ".join(block_ids)
            instruction = (
                "Summarize only these blocks, ignoring the rest of the "
                f"document: {selection}. Write for a reader who has not seen "
                "them, and cite the block ids you drew from."
            )
        else:
            instruction = (
                "Summarize this document concisely for a reader who has not "
                "seen it. Cite the block ids you drew from."
            )
        answer = await self.ask(caller, document_id, instruction=instruction)
        return answer.blocks

    async def draft(
        self, caller: CallerContext, document_id: DocumentId, *, instruction: str
    ) -> list[dict]:
        answer = await self.ask(
            caller,
            document_id,
            instruction=f"Draft the following as document content:\n{instruction}",
        )
        return answer.blocks

    # ---- document editing (agent as a CRDT peer) ---------------------------

    async def update_block(
        self,
        caller: CallerContext,
        document_id: DocumentId,
        block_id: str,
        data: dict,
    ) -> bytes:
        """Merge `data` into a block; permission checked like a human edit."""
        state = await self._realtime.current_state(caller, document_id)
        update = self._engine.update_block(state, block_id, data)
        return await self._realtime.apply(
            caller, document_id, update, origin=f"agent:{caller.user_id}"
        )

    async def delete_block(
        self, caller: CallerContext, document_id: DocumentId, block_id: str
    ) -> bytes:
        state = await self._realtime.current_state(caller, document_id)
        update = self._engine.delete_block(state, block_id)
        return await self._realtime.apply(
            caller, document_id, update, origin=f"agent:{caller.user_id}"
        )

    async def apply_blocks(
        self, caller: CallerContext, document_id: DocumentId, blocks: list[dict]
    ) -> bytes:
        """Insert blocks as a CRDT peer: live, attributed, conflict-free."""
        for block in blocks:
            validate_block_type(block.get("type", ""))
        state = await self._realtime.current_state(caller, document_id)
        update = self._engine.append_blocks(state, blocks)
        return await self._realtime.apply(
            caller, document_id, update, origin=f"agent:{caller.user_id}"
        )

    async def insert_blocks(
        self,
        caller: CallerContext,
        document_id: DocumentId,
        blocks: list[dict],
        *,
        after_id: str | None = None,
    ) -> bytes:
        """Insert blocks after `after_id` (append when None), as a CRDT peer."""
        for block in blocks:
            validate_block_type(block.get("type", ""))
        state = await self._realtime.current_state(caller, document_id)
        update = self._engine.insert_blocks_after(state, after_id, blocks)
        return await self._realtime.apply(
            caller, document_id, update, origin=f"agent:{caller.user_id}"
        )

    async def replace_block(
        self,
        caller: CallerContext,
        document_id: DocumentId,
        block_id: str,
        block: dict,
    ) -> bytes:
        """Replace a block's type and data wholesale, as a CRDT peer."""
        validate_block_type(block.get("type", ""))
        state = await self._realtime.current_state(caller, document_id)
        update = self._engine.replace_block(state, block_id, block)
        return await self._realtime.apply(
            caller, document_id, update, origin=f"agent:{caller.user_id}"
        )

    async def ingest_file_to_document(
        self,
        caller: CallerContext,
        document_id: DocumentId,
        *,
        filename: str,
        content: bytes,
    ) -> list[dict]:
        """Extract a PDF/CSV/Excel into blocks, insert them live, and submit
        the original to the workspace knowledge base."""
        document = await self._get_document(caller, document_id)
        await self._access.require_document(caller, document, Role.EDITOR)
        blocks = self._extractor.extract_blocks(filename=filename, content=content)
        if blocks:
            await self.apply_blocks(caller, document_id, blocks)
        await self._knowledge.ingest_file(
            caller, document.workspace_id, filename=filename, content=content
        )
        await self._record(
            caller,
            document_id,
            prompt=f"ingest:{filename}",
            tools=("extract_file", "rag_ingest"),
            outcome=f"{len(blocks)} blocks inserted",
        )
        return blocks

    async def run_history(
        self, caller: CallerContext, document_id: DocumentId
    ) -> list[AgentRun]:
        document = await self._get_document(caller, document_id)
        await self._access.require_document(caller, document, Role.VIEWER)
        return await self._runs.list_for_document(caller.tenant_id, document_id)

    @property
    def tools(self) -> ToolRegistry:
        return self._tools

    # ---- internals ---------------------------------------------------------

    async def _run_loop(
        self,
        caller: CallerContext,
        document_id: DocumentId,
        workspace_id: WorkspaceId,
        prompt: str,
        messages: list[LLMMessage],
        session_connectors: set[str] | None = None,
    ) -> str:
        tools_used: list[str] = []
        tools = await self._available_tools(
            caller, workspace_id, document_id, session_connectors
        )
        response = await self._llm.complete(messages, tools=tools)
        for _ in range(MAX_TOOL_ROUNDS):
            if not response.wants_tools:
                break
            messages.append(
                LLMMessage(
                    role="assistant",
                    content=response.text,
                    tool_calls=response.tool_calls,
                )
            )
            for call in response.tool_calls:
                tools_used.append(call.name)
                result = await self._dispatch(
                    caller, workspace_id, document_id, call, session_connectors
                )
                messages.append(
                    LLMMessage(
                        role="tool",
                        tool_result=ToolResult(call_id=call.id, content=result),
                    )
                )
            response = await self._llm.complete(messages, tools=tools)
        await self._record(
            caller,
            document_id,
            prompt=prompt,
            tools=tuple(tools_used),
            outcome=response.text[:500],
            model=response.model,
        )
        return response.text

    async def _available_tools(
        self,
        caller: CallerContext,
        workspace_id: WorkspaceId,
        document_id: DocumentId,
        session_connectors: set[str] | None,
    ) -> list[ToolSpec]:
        """Document-bound editing tools, the built-in tools, and the external
        MCP tools active for this document + session (namespaced by connector)."""
        tools = [spec for spec, _ in _editing_tools()] + self._tools.specs()
        if self._connectors is not None:
            tools = tools + await self._connectors.tools(
                caller,
                workspace_id,
                document_id=document_id,
                session_connectors=_connector_ids(session_connectors),
            )
        return tools

    async def _dispatch(
        self,
        caller: CallerContext,
        workspace_id: WorkspaceId,
        document_id: DocumentId,
        call: ToolCall,
        session_connectors: set[str] | None = None,
    ) -> str:
        """Editing tools bind to the OPEN document (design D-2), so a
        hallucinated id can never reach another document."""
        for spec, operation in _editing_tools():
            if spec.name == call.name:
                return await self._run_editing_tool(
                    caller, document_id, operation, call.arguments
                )
        if self._connectors is not None and split_qualified(call.name):
            try:
                return await self._connectors.call(
                    caller,
                    workspace_id,
                    qualified_name=call.name,
                    arguments=call.arguments,
                    document_id=document_id,
                    session_connectors=_connector_ids(session_connectors),
                )
            except Exception as error:  # external failures go back to the model
                return f"error: {error}"
        return await self._tools.dispatch(caller, call)

    async def _run_editing_tool(
        self,
        caller: CallerContext,
        document_id: DocumentId,
        operation: str,
        arguments: dict,
    ) -> str:
        try:
            if operation == "insert_blocks":
                blocks = [
                    {
                        "id": self._ids.new_id(),
                        "type": block.get("type", "paragraph"),
                        "data": block.get("data", {}),
                    }
                    for block in arguments.get("blocks", [])
                ]
                if not blocks:
                    return "error: no blocks provided"
                await self.apply_blocks(caller, document_id, blocks)
                return f"inserted {len(blocks)} block(s): {[b['id'] for b in blocks]}"
            if operation == "update_block":
                await self.update_block(
                    caller,
                    document_id,
                    str(arguments["block_id"]),
                    {"text": str(arguments["text"])},
                )
                return f"updated block {arguments['block_id']}"
            if operation == "delete_block":
                await self.delete_block(caller, document_id, str(arguments["block_id"]))
                return f"deleted block {arguments['block_id']}"
        except NotAuthorized:
            return "error: you do not have permission to edit this document"
        except Exception as error:
            return f"error: {error}"
        return f"error: unknown operation {operation}"

    async def _document_context(
        self, caller: CallerContext, document_id: DocumentId
    ) -> tuple:
        document = await self._get_document(caller, document_id)
        await self._access.require_document(caller, document, Role.VIEWER)
        state = await self._realtime.current_state(caller, document_id)
        blocks = self._engine.read_blocks(state)
        rendered = "\n".join(_render_block(block) for block in blocks) or "(empty)"
        return document, rendered

    async def _get_document(self, caller: CallerContext, document_id: DocumentId):
        document = await self._documents.get(caller.tenant_id, document_id)
        if document is None or document.trashed:
            raise NotFound("document not found")
        return document

    async def _record(
        self,
        caller: CallerContext,
        document_id: DocumentId | None,
        *,
        prompt: str,
        tools: tuple[str, ...],
        outcome: str,
        model: str = "",
    ) -> None:
        now = self._clock.now()
        await self._runs.add(
            AgentRun(
                id=AgentRunId(self._ids.new_id()),
                tenant_id=caller.tenant_id,
                user_id=caller.user_id,
                document_id=document_id,
                model=model or self._model_name,
                prompt=prompt,
                tools_used=tools,
                outcome=outcome,
                started_at=now,
                finished_at=now,
            )
        )

    def _register_builtin_tools(self) -> None:
        self._tools.register(
            ToolSpec(
                name="rag_query",
                description="Search the workspace knowledge base (RAG). Returns "
                "retrieved passages with their source filenames.",
                parameters={
                    "type": "object",
                    "properties": {
                        "workspace_id": {"type": "string"},
                        "query": {"type": "string"},
                    },
                    "required": ["workspace_id", "query"],
                },
            ),
            self._tool_rag_query,
        )
        self._tools.register(
            ToolSpec(
                name="read_document",
                description="Read another document's content by id (only if the "
                "caller may access it).",
                parameters={
                    "type": "object",
                    "properties": {"document_id": {"type": "string"}},
                    "required": ["document_id"],
                },
            ),
            self._tool_read_document,
        )

    async def _tool_rag_query(self, caller: CallerContext, arguments: dict) -> str:
        from cyberarche.domain.ids import WorkspaceId

        return await self._knowledge.query(
            caller,
            WorkspaceId(str(arguments["workspace_id"])),
            query=str(arguments["query"]),
        )

    async def _tool_read_document(self, caller: CallerContext, arguments: dict) -> str:
        document_id = DocumentId(str(arguments["document_id"]))
        document, rendered = await self._document_context(caller, document_id)
        return f"# {document.title}\n{rendered}"


def _editing_tools() -> list[tuple[ToolSpec, str]]:
    """(spec, operation) pairs. These act on the agent's OPEN document — the
    model never supplies a document id, so it cannot address another one."""
    return [
        (
            ToolSpec(
                name="insert_blocks",
                description="Append blocks to the open document. Each block is "
                "{type, data}; text blocks use data.text.",
                parameters={
                    "type": "object",
                    "properties": {
                        "blocks": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string"},
                                    "data": {"type": "object"},
                                },
                                "required": ["type", "data"],
                            },
                        }
                    },
                    "required": ["blocks"],
                },
            ),
            "insert_blocks",
        ),
        (
            ToolSpec(
                name="update_block",
                description="Replace the text of a block of the open document, "
                "identified by the block id shown in the context.",
                parameters={
                    "type": "object",
                    "properties": {
                        "block_id": {"type": "string"},
                        "text": {"type": "string"},
                    },
                    "required": ["block_id", "text"],
                },
            ),
            "update_block",
        ),
        (
            ToolSpec(
                name="delete_block",
                description="Delete a block of the open document by its id.",
                parameters={
                    "type": "object",
                    "properties": {"block_id": {"type": "string"}},
                    "required": ["block_id"],
                },
            ),
            "delete_block",
        ),
    ]


def _render_block(block: dict) -> str:
    data = block.get("data", {})
    text = data.get("text", "") if isinstance(data, dict) else ""
    return f"[block:{block.get('id', '?')}] ({block.get('type', '?')}) {text}"


def _connector_ids(session_connectors: set[str] | None) -> set[ConnectorId] | None:
    """The session opt-in set as ConnectorIds (None = no restriction)."""
    if session_connectors is None:
        return None
    return {ConnectorId(cid) for cid in session_connectors}


def _paragraph_blocks(ids: IdPort, text: str) -> list[dict]:
    return [
        {"id": ids.new_id(), "type": "paragraph", "data": {"text": chunk.strip()}}
        for chunk in text.split("\n\n")
        if chunk.strip()
    ]
