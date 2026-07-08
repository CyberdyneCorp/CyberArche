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
from cyberarche.application.use_cases.knowledge import KnowledgeUseCases
from cyberarche.application.use_cases.realtime import RealtimeUseCases
from cyberarche.domain.blocks import validate_block_type
from cyberarche.domain.errors import NotFound, ValidationFailed
from cyberarche.domain.ids import AgentRunId, DocumentId
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


_SYSTEM_PROMPT = (
    "You are CyberArche's document agent. You help create, summarize, and "
    "restructure documents. Ground answers in the provided document content "
    "and knowledge-base results; cite block ids (e.g. [block:abc123]) or "
    "source filenames for every claim you take from them. When asked to "
    "produce content, return it as plain paragraphs separated by blank lines."
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
        self._register_builtin_tools()

    # ---- public capabilities ----------------------------------------------

    async def ask(
        self, caller: CallerContext, document_id: DocumentId, *, instruction: str
    ) -> str:
        """Answer/act grounded in the document, with tool use."""
        document, context = await self._document_context(caller, document_id)
        messages = [
            LLMMessage(role="system", content=_SYSTEM_PROMPT),
            LLMMessage(
                role="user",
                content=f"Document '{document.title}':\n{context}\n\n{instruction}",
            ),
        ]
        return await self._run_loop(caller, document_id, instruction, messages)

    async def summarize(
        self, caller: CallerContext, document_id: DocumentId
    ) -> list[dict]:
        text = await self.ask(
            caller,
            document_id,
            instruction="Summarize this document concisely for a reader who has "
            "not seen it. Cite the block ids you drew from.",
        )
        return _paragraph_blocks(self._ids, text)

    async def draft(
        self, caller: CallerContext, document_id: DocumentId, *, instruction: str
    ) -> list[dict]:
        text = await self.ask(
            caller,
            document_id,
            instruction=f"Draft the following as document content:\n{instruction}",
        )
        return _paragraph_blocks(self._ids, text)

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
        prompt: str,
        messages: list[LLMMessage],
    ) -> str:
        tools_used: list[str] = []
        response = await self._llm.complete(messages, tools=self._tools.specs())
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
                result = await self._tools.dispatch(caller, call)
                messages.append(
                    LLMMessage(
                        role="tool",
                        tool_result=ToolResult(call_id=call.id, content=result),
                    )
                )
            response = await self._llm.complete(messages, tools=self._tools.specs())
        await self._record(
            caller,
            document_id,
            prompt=prompt,
            tools=tuple(tools_used),
            outcome=response.text[:500],
            model=response.model,
        )
        return response.text

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


def _render_block(block: dict) -> str:
    data = block.get("data", {})
    text = data.get("text", "") if isinstance(data, dict) else ""
    return f"[block:{block.get('id', '?')}] ({block.get('type', '?')}) {text}"


def _paragraph_blocks(ids: IdPort, text: str) -> list[dict]:
    return [
        {"id": ids.new_id(), "type": "paragraph", "data": {"text": chunk.strip()}}
        for chunk in text.split("\n\n")
        if chunk.strip()
    ]
