"""FastMCP inbound adapter (mcp-server spec).

Tools are thin wrappers over the same use cases as the HTTP routers, so
authorization and tenant scoping are enforced once, in the application
layer, and cannot diverge per surface (architecture-quality spec).

Every tool call authenticates: the caller resolver extracts the bearer
token from the MCP request's HTTP headers and verifies it against
CyberdyneAuth. Tests inject a resolver.
"""

from __future__ import annotations

import base64
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from fastmcp import FastMCP

from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.rag import RagQueryMode
from cyberarche.domain.errors import NotAuthenticated
from cyberarche.domain.ids import DocumentId, TenantId, UserId, WorkspaceId

if TYPE_CHECKING:
    from cyberarche.adapters.wiring import Container

CallerResolver = Callable[[], Awaitable[CallerContext]]

_INSTRUCTIONS = (
    "Tools over the caller's CyberArche documents and workspace knowledge. "
    "All results are scoped to what the authenticated caller may access."
)


def _http_caller_resolver(container: "Container") -> CallerResolver:
    async def resolve() -> CallerContext:
        from fastmcp.server.dependencies import get_http_headers

        # include_all: fastmcp strips the authorization header by default.
        header = get_http_headers(include_all=True).get("authorization", "")
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise NotAuthenticated("missing bearer token")
        claims = await container.token_port.verify(token.strip())
        return CallerContext(
            user_id=UserId(claims.subject),
            tenant_id=TenantId(claims.tenant_id),
            email=claims.email,
            scopes=claims.scopes,
            is_service=claims.is_service,
        )

    return resolve


def build_mcp_server(
    container: "Container", *, caller_resolver: CallerResolver | None = None
) -> FastMCP:
    resolve = caller_resolver or _http_caller_resolver(container)
    cases = container.use_cases
    mcp = FastMCP(name="cyberarche", instructions=_INSTRUCTIONS)

    @mcp.custom_route("/health", methods=["GET"])
    async def health(request):  # noqa: ANN001 - starlette signature
        from starlette.responses import PlainTextResponse

        return PlainTextResponse("ok")

    # ---- document tools ----------------------------------------------------

    @mcp.tool
    async def search_documents(query: str, limit: int = 20) -> list[dict]:
        """Search the caller's documents by title. Returns only documents
        the caller may access."""
        caller = await resolve()
        documents = await cases.documents.search(caller, query=query, limit=limit)
        return [
            {"id": d.id, "title": d.title, "workspace_id": d.workspace_id}
            for d in documents
        ]

    @mcp.tool
    async def read_document(document_id: str) -> dict:
        """Read a document's metadata and block content."""
        caller = await resolve()
        document = await cases.documents.get(caller, DocumentId(document_id))
        state = await cases.realtime.current_state(caller, DocumentId(document_id))
        return {
            "id": document.id,
            "title": document.title,
            "workspace_id": document.workspace_id,
            "blocks": container.crdt_engine.read_blocks(state),
        }

    @mcp.tool
    async def create_document(
        workspace_id: str, title: str, parent_id: str | None = None
    ) -> dict:
        """Create a document in a workspace the caller can edit."""
        caller = await resolve()
        document = await cases.documents.create(
            caller,
            workspace_id=WorkspaceId(workspace_id),
            title=title,
            parent_id=DocumentId(parent_id) if parent_id else None,
        )
        return {"id": document.id, "title": document.title}

    @mcp.tool
    async def insert_blocks(document_id: str, blocks: list[dict[str, Any]]) -> dict:
        """Append blocks to a document through the live CRDT channel; the
        edit appears immediately to connected collaborators."""
        caller = await resolve()
        await cases.agent.apply_blocks(caller, DocumentId(document_id), blocks)
        return {"inserted": len(blocks)}

    # ---- knowledge tools ---------------------------------------------------

    @mcp.tool
    async def rag_query(
        workspace_id: str, query: str, mode: str = "hybrid"
    ) -> dict:
        """Query the workspace knowledge base (modes: local, global, hybrid,
        naive, mix)."""
        caller = await resolve()
        result = await cases.knowledge.query(
            caller,
            WorkspaceId(workspace_id),
            query=query,
            mode=RagQueryMode(mode),
        )
        return {"result": result, "mode": mode}

    @mcp.tool
    async def ingest_file(
        workspace_id: str, filename: str, content_base64: str
    ) -> dict:
        """Ingest a file (base64-encoded) into the workspace knowledge base."""
        caller = await resolve()
        record = await cases.knowledge.ingest_file(
            caller,
            WorkspaceId(workspace_id),
            filename=filename,
            content=base64.b64decode(content_base64),
        )
        return {"task_id": record.task_id, "status": record.status.value}

    return mcp
