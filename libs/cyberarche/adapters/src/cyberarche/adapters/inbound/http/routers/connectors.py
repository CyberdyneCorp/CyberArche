"""External MCP connector endpoints (external-mcp-connectors spec).

Responses expose metadata only — credentials are never returned.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from cyberarche.adapters.inbound.http.dependencies import Caller, Cases
from cyberarche.domain.connectors import Connector
from cyberarche.domain.ids import ConnectorId, DocumentId, WorkspaceId

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/connectors", tags=["connectors"]
)


class RegisterConnectorRequest(BaseModel):
    name: str
    endpoint: str
    credentials: str = ""
    # Optional: scope this connector to one document (None = workspace-wide).
    document_id: str | None = None


class ConnectorResponse(BaseModel):
    id: str
    name: str
    slug: str
    endpoint: str
    enabled: bool
    created_by: str
    created_at: datetime

    @staticmethod
    def from_domain(connector: Connector) -> "ConnectorResponse":
        return ConnectorResponse(
            id=connector.id,
            name=connector.name,
            slug=connector.slug,
            endpoint=connector.endpoint,
            enabled=connector.enabled,
            created_by=connector.created_by,
            created_at=connector.created_at,
        )


class ToolResponse(BaseModel):
    name: str
    description: str


class SetEnabledRequest(BaseModel):
    enabled: bool


@router.post("", status_code=201)
async def register_connector(
    workspace_id: str, body: RegisterConnectorRequest, cases: Cases, caller: Caller
) -> ConnectorResponse:
    connector = await cases.connectors.register(
        caller,
        WorkspaceId(workspace_id),
        name=body.name,
        endpoint=body.endpoint,
        credentials=body.credentials,
        document_id=DocumentId(body.document_id) if body.document_id else None,
    )
    return ConnectorResponse.from_domain(connector)


@router.get("")
async def list_connectors(
    workspace_id: str, cases: Cases, caller: Caller
) -> list[ConnectorResponse]:
    connectors = await cases.connectors.list(caller, WorkspaceId(workspace_id))
    return [ConnectorResponse.from_domain(c) for c in connectors]


@router.get("/tools")
async def list_tools(
    workspace_id: str, cases: Cases, caller: Caller
) -> list[ToolResponse]:
    specs = await cases.connectors.tools(caller, WorkspaceId(workspace_id))
    return [ToolResponse(name=s.name, description=s.description) for s in specs]


@router.patch("/{connector_id}")
async def set_enabled(
    workspace_id: str,
    connector_id: str,
    body: SetEnabledRequest,
    cases: Cases,
    caller: Caller,
) -> ConnectorResponse:
    connector = await cases.connectors.set_enabled(
        caller, ConnectorId(connector_id), enabled=body.enabled
    )
    return ConnectorResponse.from_domain(connector)


@router.delete("/{connector_id}", status_code=204)
async def remove_connector(
    workspace_id: str, connector_id: str, cases: Cases, caller: Caller
) -> None:
    await cases.connectors.remove(caller, ConnectorId(connector_id))
