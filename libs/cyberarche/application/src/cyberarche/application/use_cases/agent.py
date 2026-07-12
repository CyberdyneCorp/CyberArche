"""AI agent use cases (ai-agent spec).

The agent is document-scoped: its context is the document's block tree plus
the workspace's RAG knowledge. It edits through the same CRDT channel as
humans (attributed "agent:<user>"), and every run is audited.

Tool calls are dispatched through a registry; group 9/10 plug the MCP
server tools and external connectors into the same registry.
"""

from __future__ import annotations

import json
import re

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from cyberarche.application.authz import AccessControl
from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.agent import AgentRun, AgentRunRepository
from cyberarche.application.ports.crdt import CrdtEnginePort
from cyberarche.application.ports.code_exec import (
    CodeExecutionPort,
    CodeExecutionResult,
)
from cyberarche.application.ports.extraction import FileExtractorPort
from cyberarche.application.ports.images import ImageGenerationPort
from cyberarche.application.ports.meetings import (
    MeetingSummary,
    MeetingTranscript,
    MeetingsPort,
)
from cyberarche.application.ports.storage import BlobStoragePort
from cyberarche.application.ports.web_media import (
    PlaylistVideo,
    SearchResult,
    Transcript,
    WebMediaPort,
)
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
from cyberarche.application.use_cases.excalidraw_scene import (
    build_mindmap,
    describe_scene,
)
from cyberarche.application.use_cases.knowledge import KnowledgeUseCases
from cyberarche.application.use_cases.realtime import RealtimeUseCases
from cyberarche.domain.blocks import validate_block_type
from cyberarche.domain.connectors import split_qualified
from cyberarche.domain.ids import WorkspaceId
from cyberarche.domain.errors import NotAuthorized, NotFound, ValidationFailed
from cyberarche.application.use_cases.agent_persona import AgentPersonaUseCases
from cyberarche.domain.ids import AgentMemoryId, AgentRunId, ConnectorId, DocumentId
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


_MAX_TOOL_RESULT_CHARS = 4000


@dataclass(frozen=True, slots=True)
class ToolCallLog:
    """One tool call the agent made during a run, surfaced to the chat UI so the
    user can inspect what the agent did (name, inputs, output)."""

    name: str
    kind: str  # "mcp" | "editing" | "builtin"
    connector: str | None  # the MCP connector slug, for kind == "mcp"
    arguments: dict
    result: str
    ok: bool


@dataclass(frozen=True, slots=True)
class AgentAnswer:
    """An answer plus the blocks the user may insert into the document."""

    text: str
    blocks: list[dict]
    tool_calls: list[ToolCallLog] = field(default_factory=list)


_MAX_HISTORY_TURNS = 10
_HISTORY_CHARS = 4000


_SYSTEM_PROMPT = (
    "You are CyberArche's document agent. You help create, summarize, "
    "restructure, and EDIT the open document. Ground answers in the provided "
    "document content and knowledge-base results; cite block ids (e.g. "
    "[block:abc123]) or source filenames for every claim you take from them. "
    "The open document and its block ids are given to you — never look it up "
    "by title. To change it, call insert_blocks / update_block / update_table / "
    "delete_block; these act on the open document only. To edit a `(table)` "
    "block, use update_table (update_block only changes text blocks). When asked "
    "to produce content "
    "without editing, return plain paragraphs separated by blank lines. The "
    "editor renders your answer: write math as $inline$ or $$display$$, "
    "diagrams as ```mermaid fenced blocks, and code as ```language fenced "
    "blocks — do not use \\[ \\] or \\( \\) delimiters. To compute, analyze "
    "data, simulate, or plot, call run_python: it EXECUTES the code and inserts "
    "the resulting figure into the document, then returns its output for you to "
    "explain. When the user asks to create/plot/compute/run something, or to "
    "'insert'/'run' a plot or result, call run_python — do NOT paste the code as "
    "a code block unless they explicitly ask to see the source. In matplotlib "
    "use raw strings for LaTeX in labels/titles, e.g. r'$\\frac{1}{x}$', so "
    "backslashes are not mangled. Follow-up messages continue the same "
    "conversation — 'the plot' / 'the code' refer to what was just discussed."
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
        images: ImageGenerationPort | None = None,
        blobs: BlobStoragePort | None = None,
        code: CodeExecutionPort | None = None,
        meetings: MeetingsPort | None = None,
        web_media: WebMediaPort | None = None,
        persona: AgentPersonaUseCases | None = None,
    ) -> None:
        self._llm = llm
        self._images = images
        self._blobs = blobs
        self._code = code
        self._meetings = meetings
        self._web_media = web_media
        self._persona = persona
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
        history: list[tuple[str, str]] | None = None,
        access_token: str | None = None,
        reasoning: bool = False,
    ) -> AgentAnswer:
        """Answer/act grounded in the document, with tool use.

        The reply always carries insertable blocks so the UI can offer
        'Insert as block' on any answer (ai-agent spec). `session_connectors`,
        if given, restricts external MCP tools to that opt-in set for this run.
        `history` is recent (role, content) turns so follow-ups like 'insert the
        plot' resolve against the conversation, not just the document.
        """
        document, context = await self._document_context(caller, document_id)
        system_prompt = _SYSTEM_PROMPT
        if self._persona is not None:
            # Prepend the workspace's custom instructions and recalled memory.
            system_prompt += await self._persona.build_context(
                caller, document.workspace_id, instruction
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
                content=(
                    f"Open document '{document.title}' (id: {document.id}).\n"
                    f"Its blocks:\n{context}\n\n{instruction}"
                ),
            )
        )
        text, edited, tool_calls = await self._run_loop(
            caller,
            document_id,
            document.workspace_id,
            instruction,
            messages,
            session_connectors,
            access_token,
            # The chat's Reasoning toggle: deeper thinking when on, fast when off.
            reasoning_effort="medium" if reasoning else "minimal",
        )
        # If the agent already applied its edit live, don't offer to insert it
        # again (that produced a duplicate block); otherwise carry insertables.
        blocks = [] if edited else _answer_blocks(self._ids, text)
        return AgentAnswer(text=text, blocks=blocks, tool_calls=tool_calls)

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

    def _prepare_blocks(self, blocks: list[dict]) -> list[dict]:
        """Normalize model-supplied blocks, then split any paragraph that hides
        block-level markdown (## heading, fenced code, lists) into real blocks,
        and validate the result. Shared by every CRDT-peer insertion path."""
        prepared: list[dict] = []
        for block in blocks:
            prepared.extend(_expand_block(self._ids, _normalize_block(block)))
        for block in prepared:
            validate_block_type(block.get("type", ""))
        return prepared

    async def apply_blocks(
        self, caller: CallerContext, document_id: DocumentId, blocks: list[dict]
    ) -> bytes:
        """Insert blocks as a CRDT peer: live, attributed, conflict-free."""
        blocks = self._prepare_blocks(blocks)
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
        blocks = self._prepare_blocks(blocks)
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
        access_token: str | None = None,
        reasoning_effort: str | None = None,
    ) -> tuple[str, bool, list[ToolCallLog]]:
        tools_used: list[str] = []
        call_log: list[ToolCallLog] = []
        tools = await self._available_tools(
            caller, workspace_id, document_id, session_connectors, access_token
        )
        response = await self._llm.complete(
            messages, tools=tools, reasoning_effort=reasoning_effort
        )
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
                    caller,
                    workspace_id,
                    document_id,
                    call,
                    session_connectors,
                    access_token,
                )
                kind, connector = _classify_tool(call.name)
                call_log.append(
                    ToolCallLog(
                        name=call.name,
                        kind=kind,
                        connector=connector,
                        arguments=dict(call.arguments or {}),
                        result=result[:_MAX_TOOL_RESULT_CHARS],
                        ok=not result.startswith("error:"),
                    )
                )
                messages.append(
                    LLMMessage(
                        role="tool",
                        tool_result=ToolResult(call_id=call.id, content=result),
                    )
                )
            response = await self._llm.complete(
                messages, tools=tools, reasoning_effort=reasoning_effort
            )
        await self._record(
            caller,
            document_id,
            prompt=prompt,
            tools=tuple(tools_used),
            outcome=response.text[:500],
            model=response.model,
        )
        # Whether the agent already wrote to the document during this run — if so
        # the answer's content is in the doc, and offering a manual Insert would
        # duplicate it.
        edited = any(name in _EDITING_TOOL_NAMES for name in tools_used)
        return response.text, edited, call_log

    async def _available_tools(
        self,
        caller: CallerContext,
        workspace_id: WorkspaceId,
        document_id: DocumentId,
        session_connectors: set[str] | None,
        access_token: str | None = None,
    ) -> list[ToolSpec]:
        """Document-bound editing tools, the built-in tools, and the external
        MCP tools active for this document + session (namespaced by connector)."""
        tools = (
            [spec for spec, _ in _editing_tools()]
            + [_mindmap_tool_spec()]
            + self._tools.specs()
        )
        if self._images is not None and self._blobs is not None:
            tools = tools + [_image_tool_spec()]
        if self._code is not None:
            tools = tools + [_python_tool_spec()]
        # Per-user meeting tools need the caller's own token (delegated auth), so
        # they only appear on the authenticated request path.
        if self._meetings is not None and access_token:
            tools = tools + _meeting_tool_specs()
        # Web/media tools forward the caller's own token to the DAO backend, so
        # (like meetings) they only appear on the authenticated request path.
        if self._web_media is not None and access_token:
            tools = tools + _web_media_tool_specs()
        if self._persona is not None:
            tools = tools + _persona_tool_specs()
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
        access_token: str | None = None,
    ) -> str:
        """Editing tools bind to the OPEN document (design D-2), so a
        hallucinated id can never reach another document."""
        if call.name in _MEETING_TOOL_NAMES:
            return await self._run_meetings_tool(call, access_token)
        if call.name in _WEB_MEDIA_TOOL_NAMES:
            return await self._run_web_media_tool(call, access_token)
        if call.name in _PERSONA_TOOL_NAMES:
            return await self._run_persona_tool(caller, workspace_id, call)
        if call.name == "generate_image":
            return await self._run_generate_image(
                caller, workspace_id, document_id, call.arguments
            )
        if call.name == "run_python":
            return await self._run_python(
                caller, workspace_id, document_id, call.arguments
            )
        if call.name == "create_mindmap":
            return await self._run_create_mindmap(caller, document_id, call.arguments)
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
            if operation == "update_table":
                block_id = str(arguments["block_id"])
                data: dict = {
                    "rows": [
                        [str(cell) for cell in row]
                        for row in arguments.get("rows", [])
                    ]
                }
                if arguments.get("header") is not None:
                    data["header"] = [str(col) for col in arguments["header"]]
                await self.update_block(caller, document_id, block_id, data)
                return f"updated table {block_id}"
            if operation == "delete_block":
                await self.delete_block(caller, document_id, str(arguments["block_id"]))
                return f"deleted block {arguments['block_id']}"
        except NotAuthorized:
            return "error: you do not have permission to edit this document"
        except Exception as error:
            return f"error: {error}"
        return f"error: unknown operation {operation}"

    async def _run_generate_image(
        self,
        caller: CallerContext,
        workspace_id: WorkspaceId,
        document_id: DocumentId,
        arguments: dict,
    ) -> str:
        if self._images is None or self._blobs is None:
            return "error: image generation is not configured"
        prompt = str(arguments.get("prompt", "")).strip()
        if not prompt:
            return "error: prompt required"
        size = str(arguments.get("size", "") or "1024x1024")
        try:
            document = await self._get_document(caller, document_id)
            await self._access.require_document(caller, document, Role.EDITOR)
            image = await self._images.generate(prompt, size=size)
            file_id = self._ids.new_id()
            await self._blobs.put(
                f"files/{workspace_id}/{file_id}",
                image.content,
                content_type=image.content_type,
            )
            url = f"/api/v1/workspaces/{workspace_id}/files/{file_id}"
            block = {
                "id": self._ids.new_id(),
                "type": "image",
                "data": {"url": url, "alt": prompt},
            }
            await self.apply_blocks(caller, document_id, [block])
            return f"generated and inserted an image for: {prompt}"
        except NotAuthorized:
            return "error: you do not have permission to edit this document"
        except Exception as error:
            return f"error: {error}"

    async def _run_create_mindmap(
        self,
        caller: CallerContext,
        document_id: DocumentId,
        arguments: dict,
    ) -> str:
        central = str(arguments.get("central", "")).strip()
        branches = arguments.get("branches") or []
        if not central:
            return "error: central topic required"
        if not isinstance(branches, list) or not branches:
            return "error: at least one branch required"
        try:
            document = await self._get_document(caller, document_id)
            await self._access.require_document(caller, document, Role.EDITOR)
            scene = build_mindmap(central, branches)
            block = {
                "id": self._ids.new_id(),
                "type": "excalidraw",
                "data": {"scene": json.dumps(scene)},
            }
            await self.apply_blocks(caller, document_id, [block])
            return f"created a mind map for '{central}' with {len(branches)} branch(es)"
        except NotAuthorized:
            return "error: you do not have permission to edit this document"
        except Exception as error:
            return f"error: {error}"

    async def _run_meetings_tool(
        self, call: ToolCall, access_token: str | None
    ) -> str:
        """Read the caller's meetings via the delegated access token. The token
        is used only as the provider bearer here — never logged or recorded."""
        if self._meetings is None:
            return "error: meeting transcripts are not configured"
        if not access_token:
            return "error: sign in required to access meetings"
        args = call.arguments or {}
        try:
            if call.name == "list_meetings":
                items = await self._meetings.list_recordings(
                    access_token, limit=int(args.get("limit") or 20)
                )
                return _render_meeting_list(items)
            if call.name == "get_meeting_transcript":
                recording_id = str(args.get("recording_id", "")).strip()
                if not recording_id:
                    return "error: recording_id required"
                rec = await self._meetings.get_recording(access_token, recording_id)
                return _render_meeting_transcript(rec)
            if call.name == "ask_meetings":
                question = str(args.get("question", "")).strip()
                if not question:
                    return "error: question required"
                return await self._meetings.ask(access_token, question)
        except Exception as error:
            return f"error: {_meetings_error(error)}"
        return f"error: unknown meetings tool {call.name}"

    async def _run_web_media_tool(
        self, call: ToolCall, access_token: str | None
    ) -> str:
        """Web search + YouTube tools. The caller's token is forwarded to the DAO
        backend as the bearer — used only there, never logged or recorded."""
        if self._web_media is None:
            return "error: web and media tools are not configured"
        if not access_token:
            return "error: sign in required to use web and media tools"
        args = call.arguments or {}
        try:
            if call.name == "web_search":
                query = str(args.get("query", "")).strip()
                if not query:
                    return "error: query required"
                results = await self._web_media.search(
                    access_token, query, num=int(args.get("num") or 10)
                )
                return _render_search(results)
            if call.name == "youtube_transcript":
                video = str(args.get("video", "")).strip()
                if not video:
                    return "error: video required"
                lang = str(args.get("lang", "")).strip() or None
                transcript = await self._web_media.youtube_transcript(
                    access_token, video, lang=lang
                )
                return _render_transcript(transcript)
            if call.name == "youtube_playlist":
                playlist = str(args.get("playlist", "")).strip()
                if not playlist:
                    return "error: playlist required"
                videos = await self._web_media.youtube_playlist(
                    access_token, playlist
                )
                return _render_playlist(videos)
        except Exception as error:
            return f"error: {_web_media_error(error)}"
        return f"error: unknown web/media tool {call.name}"

    async def _run_persona_tool(
        self, caller: CallerContext, workspace_id: WorkspaceId, call: ToolCall
    ) -> str:
        """Durable memory tools (remember / list / forget), workspace-scoped."""
        if self._persona is None:
            return "error: agent memory is not configured"
        args = call.arguments or {}
        try:
            if call.name == "remember":
                note = str(args.get("note", "")).strip()
                if not note:
                    return "error: note required"
                memory = await self._persona.add_memory(caller, workspace_id, note)
                return f"remembered (id={memory.id})"
            if call.name == "list_memories":
                items = await self._persona.list_memories(caller, workspace_id)
                return _render_memories(items)
            if call.name == "forget":
                memory_id = str(args.get("memory_id", "")).strip()
                if not memory_id:
                    return "error: memory_id required"
                await self._persona.delete_memory(
                    caller, workspace_id, AgentMemoryId(memory_id)
                )
                return f"forgot memory {memory_id}"
        except Exception as error:
            return f"error: {error}"
        return f"error: unknown memory tool {call.name}"

    async def _run_python(
        self,
        caller: CallerContext,
        workspace_id: WorkspaceId,
        document_id: DocumentId,
        arguments: dict,
    ) -> str:
        if self._code is None or self._blobs is None:
            return "error: code execution is not configured"
        code = str(arguments.get("code", "")).strip()
        if not code:
            return "error: code required"
        try:
            document = await self._get_document(caller, document_id)
            await self._access.require_document(caller, document, Role.EDITOR)
            outcome = await self._code.run(code)
            # Store each figure and insert it into the document as an image block.
            blocks = []
            for image in outcome.images:
                file_id = self._ids.new_id()
                await self._blobs.put(
                    f"files/{workspace_id}/{file_id}",
                    image.content,
                    content_type=image.content_type,
                )
                blocks.append(
                    {
                        "id": self._ids.new_id(),
                        "type": "image",
                        "data": {
                            "url": f"/api/v1/workspaces/{workspace_id}/files/{file_id}",
                            "alt": "Generated by run_python",
                        },
                    }
                )
            if blocks:
                await self.apply_blocks(caller, document_id, blocks)
            return _summarize_python(outcome, inserted=len(blocks))
        except NotAuthorized:
            return "error: you do not have permission to edit this document"
        except Exception as error:
            return f"error: {error}"

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


_EDITING_TOOL_NAMES = {
    "insert_blocks",
    "update_block",
    "update_table",
    "delete_block",
    "generate_image",
    "create_mindmap",
}


def _summarize_python(outcome: CodeExecutionResult, *, inserted: int) -> str:
    """Compact textual summary of a run for the model (figures go to the doc)."""
    parts: list[str] = ["success" if outcome.success else "failed"]
    if outcome.stdout.strip():
        parts.append(f"stdout:\n{outcome.stdout[:2000]}")
    if outcome.result and outcome.result != "None":
        parts.append(f"result: {outcome.result[:500]}")
    if not outcome.success:
        detail = (outcome.error or outcome.stderr or "").strip()
        if detail:
            parts.append(f"error:\n{detail[:1000]}")
    for table in outcome.tables[:2]:
        parts.append(f"table:\n{table[:1500]}")
    if inserted:
        parts.append(f"inserted {inserted} figure(s) into the document")
    return "\n".join(parts)


def _classify_tool(name: str) -> tuple[str, str | None]:
    """(kind, connector_slug). MCP tools are namespaced 'slug__tool'; the fixed
    document-editing tools are their own kind; everything else is built-in."""
    if name in _EDITING_TOOL_NAMES:
        return "editing", None
    parts = split_qualified(name)
    if parts is not None:
        return "mcp", parts[0]
    return "builtin", None


def _python_tool_spec() -> ToolSpec:
    return ToolSpec(
        name="run_python",
        description=(
            "Run Python to compute, analyze data (pandas/numpy), run or simulate "
            "code, and make plots (matplotlib). This EXECUTES the code: any figures "
            "it creates are inserted into the open document as images, and stdout, "
            "the result value, and errors are returned to you to explain. Prefer "
            "this over an insert_blocks code block whenever the user wants to SEE a "
            "plot or result — a code block only shows source, it does not run. Each "
            "call is isolated (no variables/imports persist). Figures are captured "
            "and inserted automatically — just create the plot, do NOT call "
            "plt.savefig. Use raw strings for LaTeX in matplotlib labels/titles, "
            "e.g. r'$\\frac{1}{x}$'."
        ),
        parameters={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python source to run."}
            },
            "required": ["code"],
        },
    )


def _mindmap_tool_spec() -> ToolSpec:
    return ToolSpec(
        name="create_mindmap",
        description=(
            "Draw a mind map on an Excalidraw whiteboard and insert it into the "
            "open document. Use this when the user asks to 'create a mind map', "
            "'map out', or 'draw a diagram' of a topic and its ideas — it renders "
            "as an editable diagram, not text. Provide the central topic and its "
            "branches; a branch may carry its own sub-items."
        ),
        parameters={
            "type": "object",
            "properties": {
                "central": {
                    "type": "string",
                    "description": "The central topic at the centre of the map.",
                },
                "branches": {
                    "type": "array",
                    "description": "The main branches radiating from the centre.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string"},
                            "children": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": ["label"],
                    },
                },
            },
            "required": ["central", "branches"],
        },
    )


_MEETING_TOOL_NAMES = {"list_meetings", "get_meeting_transcript", "ask_meetings"}


def _meeting_tool_specs() -> list[ToolSpec]:
    return [
        ToolSpec(
            name="list_meetings",
            description=(
                "List the user's recent meeting recordings (from Cyberflies). "
                "Returns each meeting's id, captured time, status, and headline. "
                "Use a returned id with get_meeting_transcript to read one."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Max meetings to list (default 20).",
                    }
                },
                "required": [],
            },
        ),
        ToolSpec(
            name="get_meeting_transcript",
            description=(
                "Fetch one meeting's transcript and summary (headline, abstract, "
                "key points, action items) by its recording id (from "
                "list_meetings). Use this to add a meeting's notes or transcript "
                "to the document."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "recording_id": {
                        "type": "string",
                        "description": "The meeting's recording id.",
                    }
                },
                "required": ["recording_id"],
            },
        ),
        ToolSpec(
            name="ask_meetings",
            description=(
                "Ask a natural-language question answered across ALL the user's "
                "meetings, e.g. 'what action items came out of my meetings this "
                "week?'. Returns a synthesized answer grounded in their meetings."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "The question."}
                },
                "required": ["question"],
            },
        ),
    ]


def _meetings_error(error: Exception) -> str:
    """Friendly text for a provider failure, without importing the HTTP client."""
    response = getattr(error, "response", None)
    status = getattr(response, "status_code", None)
    if status in (401, 403):
        return "not signed in to the meetings service, or no access to it"
    if status == 404:
        return "that meeting was not found"
    return str(error) or "meetings service error"


def _render_meeting_list(items: list[MeetingSummary]) -> str:
    if not items:
        return "no meetings found"
    lines = [
        f"- id={m.id} | {m.captured_at or 'unknown time'} | {m.status} | "
        f"{m.headline or '(no summary yet)'}"
        for m in items
    ]
    return "meetings:\n" + "\n".join(lines)


def _render_meeting_transcript(rec: MeetingTranscript) -> str:
    parts = [f"meeting {rec.id} ({rec.status})"]
    if rec.captured_at:
        parts.append(f"captured: {rec.captured_at}")
    if rec.headline:
        parts.append(f"headline: {rec.headline}")
    if rec.abstract:
        parts.append(f"abstract: {rec.abstract}")
    if rec.bullets:
        parts.append("key points:\n" + "\n".join(f"- {b}" for b in rec.bullets))
    if rec.action_items:
        parts.append("action items:\n" + "\n".join(f"- {a}" for a in rec.action_items))
    parts.append(
        "transcript:\n" + rec.transcript
        if rec.transcript
        else "(transcript not ready yet)"
    )
    return "\n\n".join(parts)


_WEB_MEDIA_TOOL_NAMES = {"web_search", "youtube_transcript", "youtube_playlist"}


def _web_media_tool_specs() -> list[ToolSpec]:
    return [
        ToolSpec(
            name="web_search",
            description=(
                "Search the live web for up-to-date information. Returns ranked "
                "results with title, URL, and snippet. Use it to research a "
                "topic or find current sources; cite the URLs and, when asked, "
                "insert a summary with links into the document."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query."},
                    "num": {
                        "type": "integer",
                        "description": "Max results (default 10, max 20).",
                    },
                },
                "required": ["query"],
            },
        ),
        ToolSpec(
            name="youtube_transcript",
            description=(
                "Fetch a YouTube video's transcript. `video` is a URL or the "
                "11-character video id. Use it to summarize the talk into the "
                "document, or — when the user asks to add it to the knowledge "
                "base — ingest the transcript into the workspace RAG."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "video": {
                        "type": "string",
                        "description": "Video URL or 11-char id.",
                    },
                    "lang": {
                        "type": "string",
                        "description": "Preferred transcript language (BCP-47).",
                    },
                },
                "required": ["video"],
            },
        ),
        ToolSpec(
            name="youtube_playlist",
            description=(
                "List the videos in a YouTube playlist. `playlist` is a URL or "
                "id. Returns each video's title and URL; follow up with "
                "youtube_transcript to read one."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "playlist": {
                        "type": "string",
                        "description": "Playlist URL or id.",
                    }
                },
                "required": ["playlist"],
            },
        ),
    ]


def _web_media_error(error: Exception) -> str:
    """Friendly text for a DAO-backend failure, without importing the HTTP client."""
    response = getattr(error, "response", None)
    status = getattr(response, "status_code", None)
    if status in (401, 403):
        return "not signed in to the web/media service, or no access to it"
    if status == 404:
        return "that video or playlist was not found"
    if status is not None and status >= 500:
        # 503 in particular: YouTube throttles the backend's datacenter IP for
        # transcript fetches. Surface a retryable, non-leaky message.
        return (
            "the web/media service is temporarily unavailable "
            "(the source may be rate-limiting) — try again shortly"
        )
    return str(error) or "web/media service unavailable"


def _render_search(results: list[SearchResult]) -> str:
    if not results:
        return "no results found"
    lines = []
    for i, r in enumerate(results, 1):
        line = f"{i}. {r.title or r.url} — {r.url}"
        if r.snippet:
            line += f"\n   {r.snippet}"
        lines.append(line)
    return "web results:\n" + "\n".join(lines)


def _render_transcript(t: Transcript) -> str:
    header = f"transcript for video {t.video_id}"
    if t.title:
        header += f" — {t.title}"
    if t.lang:
        header += f" [{t.lang}]"
    if not t.text:
        return header + "\n(no transcript available)"
    return header + "\n\n" + t.text


def _render_playlist(videos: list[PlaylistVideo]) -> str:
    if not videos:
        return "no videos found"
    lines = [
        f"{i}. {v.title or v.video_id} — {v.url}" for i, v in enumerate(videos, 1)
    ]
    return "playlist videos:\n" + "\n".join(lines)


_PERSONA_TOOL_NAMES = {"remember", "list_memories", "forget"}


def _persona_tool_specs() -> list[ToolSpec]:
    return [
        ToolSpec(
            name="remember",
            description=(
                "Save a durable fact or preference about this workspace so you "
                "recall it in future conversations (e.g. 'the team writes in "
                "Portuguese', 'we deploy on Coolify'). Store lasting facts, not "
                "one-off details — and NEVER store secrets, tokens, passwords, "
                "or credentials."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "note": {
                        "type": "string",
                        "description": "The durable fact/preference to remember.",
                    }
                },
                "required": ["note"],
            },
        ),
        ToolSpec(
            name="list_memories",
            description=(
                "List the durable memories saved for this workspace, with their "
                "ids. Use before forget to find the id to remove."
            ),
            parameters={"type": "object", "properties": {}, "required": []},
        ),
        ToolSpec(
            name="forget",
            description=(
                "Delete a saved workspace memory by its id (from list_memories)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "memory_id": {
                        "type": "string",
                        "description": "The memory id to delete.",
                    }
                },
                "required": ["memory_id"],
            },
        ),
    ]


def _render_memories(items: list) -> str:
    if not items:
        return "no memories saved for this workspace"
    lines = [f"- id={m.id} | {m.text}" for m in items]
    return "workspace memories:\n" + "\n".join(lines)


def _image_tool_spec() -> ToolSpec:
    return ToolSpec(
        name="generate_image",
        description=(
            "Generate an image from a text prompt and insert it as an image "
            "block into the open document. Use for illustrations, diagrams the "
            "user asks to 'draw'/'picture', or requested artwork."
        ),
        parameters={
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "What the image should depict.",
                },
                "size": {
                    "type": "string",
                    "description": "Optional, e.g. 1024x1024, 1024x1536, 1536x1024.",
                },
            },
            "required": ["prompt"],
        },
    )


def _editing_tools() -> list[tuple[ToolSpec, str]]:
    """(spec, operation) pairs. These act on the agent's OPEN document — the
    model never supplies a document id, so it cannot address another one."""
    return [
        (
            ToolSpec(
                name="insert_blocks",
                description=(
                    "Append blocks to the open document. Each block is "
                    "{type, data}. Data by type: paragraph/heading/quote/callout/"
                    "bulleted_list/numbered_list/todo -> {text}; code -> "
                    "{source, language}; latex -> {source}; mermaid -> {source}; "
                    "table -> {header: [..], rows: [[..]]}; image -> {url, alt} "
                    "(an existing image URL); embed -> {url} (a YouTube/Vimeo/https "
                    "link). Put math in $…$/$$…$$, diagrams in a mermaid block, code "
                    "in a code block. A mermaid block's source MUST start with a "
                    "valid diagram type (flowchart, sequenceDiagram, classDiagram, "
                    "stateDiagram-v2, erDiagram, gantt, timeline, mindmap, pie) — for "
                    "a roadmap or schedule use 'gantt' or 'timeline'; 'roadmap' is "
                    "NOT valid. To CREATE a new image from a prompt, use the "
                    "generate_image tool instead of an image block."
                ),
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
                name="update_table",
                description=(
                    "Edit an existing TABLE block (by the block id shown in the "
                    "context — a `(table)` block). Provide the FULL new `rows` (a "
                    "list of rows, each a list of cell strings) and optionally a "
                    "new `header` (list of column names). This replaces the "
                    "table's cells, so include every row/column, not just the "
                    "changed ones. Cell text may contain inline markdown, "
                    "including links written as [label](https://example.com). "
                    "update_block does NOT work on tables — always use this."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "block_id": {"type": "string"},
                        "header": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "rows": {
                            "type": "array",
                            "items": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                    },
                    "required": ["block_id", "rows"],
                },
            ),
            "update_table",
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
    block_type = block.get("type", "?")
    data = block.get("data", {}) if isinstance(block.get("data"), dict) else {}
    if block_type == "excalidraw":
        body = describe_scene(data.get("scene", ""))
    elif block_type in _SOURCE_BLOCKS:
        body = (data.get("source") or "").strip()
    elif block_type == "table":
        # Render the cells so the agent can see and edit them (via update_table).
        body = "\n" + _table_to_text(
            data.get("header") or [], data.get("rows") or []
        )
    else:
        body = data.get("text", "")
    return f"[block:{block.get('id', '?')}] ({block_type}) {body}"


def _table_to_text(header: list, rows: list) -> str:
    """A markdown rendering of a table block's cells for the agent's context."""

    def cell(value: object) -> str:
        return str(value).replace("\n", " ").strip()

    lines = []
    if header:
        lines.append("| " + " | ".join(cell(h) for h in header) + " |")
        lines.append("| " + " | ".join("---" for _ in header) + " |")
    for row in rows:
        lines.append("| " + " | ".join(cell(c) for c in row) + " |")
    return "\n".join(lines) if lines else "(empty table)"


def _connector_ids(session_connectors: set[str] | None) -> set[ConnectorId] | None:
    """The session opt-in set as ConnectorIds (None = no restriction)."""
    if session_connectors is None:
        return None
    return {ConnectorId(cid) for cid in session_connectors}


_FENCE_RE = re.compile(r"```([a-zA-Z0-9_+-]*)\n(.*?)```", re.DOTALL)
_DISPLAY_MATH_RE = re.compile(r"\$\$(.+?)\$\$|\\\[(.+?)\\\]", re.DOTALL)

# Block-level markdown recognized line-by-line inside prose. A model that
# ignores the "one {type, data} block each" contract and dumps a markdown blob
# into a single paragraph is split back into real blocks so the editor (which
# only renders block-level markdown as its own block, never inside a paragraph)
# shows a heading/list/quote instead of raw "## …" text.
_HEADING_RE = re.compile(r"^(#{1,4})\s+(.*)$")
_TODO_RE = re.compile(r"^(?:[-*+]\s+)?\[([ xX])\]\s+(.*)$")
_QUOTE_RE = re.compile(r"^>\s+(.*)$")
_BULLET_RE = re.compile(r"^[-*+]\s+(.*)$")
_NUMBERED_RE = re.compile(r"^\d+[.)]\s+(.*)$")
# Any line that starts a non-paragraph block — used to decide whether a
# paragraph the model produced actually needs splitting.
_BLOCK_MD_LINE_RE = re.compile(
    r"^(#{1,4}\s|>\s|[-*+]\s|\d+[.)]\s|\[[ xX]\]\s|(?:---|\*\*\*|___)\s*$)"
)


def _line_block(ids: IdPort, line: str) -> dict | None:
    """Map one stripped line of block-level markdown to a block, else None."""
    heading = _HEADING_RE.match(line)
    if heading:
        return {
            "id": ids.new_id(),
            "type": "heading",
            "data": {
                "text": _inline_math(heading.group(2).strip()),
                "level": len(heading.group(1)),
            },
        }
    if line in ("---", "***", "___"):
        return {"id": ids.new_id(), "type": "divider", "data": {}}
    quote = _QUOTE_RE.match(line)
    if quote:
        return {
            "id": ids.new_id(),
            "type": "quote",
            "data": {"text": _inline_math(quote.group(1).strip())},
        }
    todo = _TODO_RE.match(line)  # before bullet: "- [ ] x" also matches _BULLET_RE
    if todo:
        return {
            "id": ids.new_id(),
            "type": "todo",
            "data": {
                "text": _inline_math(todo.group(2).strip()),
                "checked": todo.group(1).lower() == "x",
            },
        }
    bullet = _BULLET_RE.match(line)
    if bullet:
        return {
            "id": ids.new_id(),
            "type": "bulleted_list",
            "data": {"text": _inline_math(bullet.group(1).strip())},
        }
    numbered = _NUMBERED_RE.match(line)
    if numbered:
        return {
            "id": ids.new_id(),
            "type": "numbered_list",
            "data": {"text": _inline_math(numbered.group(1).strip())},
        }
    return None


def _needs_expansion(text: str) -> bool:
    """A paragraph's text hides block-level markdown that should be its own block."""
    if "```" in text or "$$" in text or "\\[" in text:
        return True
    return any(_BLOCK_MD_LINE_RE.match(line.strip()) for line in text.split("\n"))


def _expand_block(ids: IdPort, block: dict) -> list[dict]:
    """Split a paragraph carrying block-level markdown into real blocks.

    Non-paragraph blocks and plain prose paragraphs pass through untouched, so
    this is safe to run over every block a model hands us.
    """
    if block.get("type", "paragraph") != "paragraph":
        return [block]
    text = (block.get("data") or {}).get("text")
    if not isinstance(text, str) or not _needs_expansion(text):
        return [block]
    return _answer_blocks(ids, text) or [block]


_SOURCE_BLOCKS = {"code", "latex", "mermaid"}


def _normalize_block(block: dict) -> dict:
    """Repair blocks whose content the model put under the wrong key.

    Source-based blocks (code/latex/mermaid) render from data.source; a model
    that only saw "text blocks use data.text" often fills data.text/code/content
    instead, yielding an empty (placeholder-only) block. Map those to source,
    and default a code block's language.
    """
    block_type = block.get("type", "paragraph")
    data = dict(block.get("data") or {})
    if block_type in _SOURCE_BLOCKS and not (data.get("source") or "").strip():
        data["source"] = (
            data.get("text") or data.get("code") or data.get("content") or ""
        )
    if block_type == "code" and not data.get("language"):
        data["language"] = data.get("lang") or "text"
    if block_type in {"image", "embed"} and not (data.get("url") or "").strip():
        # Models often put the address under src/href instead of url.
        data["url"] = data.get("src") or data.get("href") or data.get("url") or ""
    return {**block, "data": data}


def _answer_blocks(ids: IdPort, text: str) -> list[dict]:
    """Parse an agent answer into typed, renderable blocks.

    Fenced ```mermaid -> mermaid, ```lang -> code, display math ($$…$$ or
    \\[…\\]) -> latex, and prose -> paragraphs. Inline \\(…\\) in prose is
    normalized to $…$ so the editor's inline renderer typesets it. The editor
    already renders latex/mermaid/code blocks; this is what lets an inserted
    answer show as more than raw source.
    """
    blocks: list[dict] = []

    def paragraphs(chunk: str) -> None:
        # Line-based: a blank line or a block-markdown line (heading/list/quote/
        # divider) ends the current paragraph; consecutive prose lines join.
        buffer: list[str] = []

        def flush() -> None:
            if buffer:
                body = _inline_math("\n".join(buffer).strip())
                if body:
                    blocks.append(
                        {
                            "id": ids.new_id(),
                            "type": "paragraph",
                            "data": {"text": body},
                        }
                    )
                buffer.clear()

        for raw in chunk.split("\n"):
            line = raw.strip()
            if not line:
                flush()
                continue
            block = _line_block(ids, line)
            if block is not None:
                flush()
                blocks.append(block)
            else:
                buffer.append(raw)
        flush()

    def emit_display_math(segment: str) -> None:
        last = 0
        for m in _DISPLAY_MATH_RE.finditer(segment):
            paragraphs(segment[last : m.start()])
            source = (m.group(1) or m.group(2) or "").strip()
            blocks.append(
                {"id": ids.new_id(), "type": "latex", "data": {"source": source}}
            )
            last = m.end()
        paragraphs(segment[last:])

    # Split on fenced blocks first; the gaps between fences are prose+math.
    cursor = 0
    for fence in _FENCE_RE.finditer(text):
        emit_display_math(text[cursor : fence.start()])
        lang = (fence.group(1) or "").strip().lower()
        source = fence.group(2).rstrip("\n")
        if lang == "mermaid":
            blocks.append(
                {"id": ids.new_id(), "type": "mermaid", "data": {"source": source}}
            )
        else:
            blocks.append(
                {
                    "id": ids.new_id(),
                    "type": "code",
                    "data": {"source": source, "language": lang or "text"},
                }
            )
        cursor = fence.end()
    emit_display_math(text[cursor:])

    # Never return nothing: fall back to the raw text as one paragraph.
    if not blocks and text.strip():
        blocks.append(
            {"id": ids.new_id(), "type": "paragraph", "data": {"text": text.strip()}}
        )
    return blocks


def _inline_math(text: str) -> str:
    r"""Normalize inline \(…\) to $…$ so the editor's inline renderer typesets it."""
    return re.sub(r"\\\((.+?)\\\)", lambda m: f"${m.group(1).strip()}$", text)


# Kept as a thin alias: some callers/tests refer to the old name.
def _paragraph_blocks(ids: IdPort, text: str) -> list[dict]:
    return _answer_blocks(ids, text)
