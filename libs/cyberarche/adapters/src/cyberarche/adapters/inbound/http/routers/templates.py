"""Template endpoints (templates spec): save a document as a template, list,
create a document from one, and delete."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from cyberarche.adapters.inbound.http.dependencies import Caller, Cases
from cyberarche.adapters.inbound.http.schemas import DocumentResponse
from cyberarche.domain.ids import DocumentId, TemplateId, TeamspaceId, WorkspaceId
from cyberarche.domain.templates import Template

router = APIRouter(tags=["templates"])


class TemplateResponse(BaseModel):
    id: str
    name: str
    created_by: str
    created_at: datetime
    block_count: int

    @staticmethod
    def from_domain(t: Template) -> "TemplateResponse":
        return TemplateResponse(
            id=t.id,
            name=t.name,
            created_by=t.created_by,
            created_at=t.created_at,
            block_count=len(t.content),
        )


class SaveTemplateRequest(BaseModel):
    name: str
    document_id: str


class InstantiateRequest(BaseModel):
    title: str = ""
    teamspace_id: str | None = None


@router.post("/api/v1/workspaces/{workspace_id}/templates", status_code=201)
async def save_template(
    workspace_id: str, body: SaveTemplateRequest, cases: Cases, caller: Caller
) -> TemplateResponse:
    template = await cases.templates.save_from_document(
        caller,
        WorkspaceId(workspace_id),
        name=body.name,
        document_id=DocumentId(body.document_id),
    )
    return TemplateResponse.from_domain(template)


@router.get("/api/v1/workspaces/{workspace_id}/templates")
async def list_templates(
    workspace_id: str, cases: Cases, caller: Caller
) -> list[TemplateResponse]:
    templates = await cases.templates.list(caller, WorkspaceId(workspace_id))
    return [TemplateResponse.from_domain(t) for t in templates]


@router.post(
    "/api/v1/workspaces/{workspace_id}/templates/{template_id}/instantiate",
    status_code=201,
)
async def instantiate_template(
    workspace_id: str,
    template_id: str,
    body: InstantiateRequest,
    cases: Cases,
    caller: Caller,
) -> DocumentResponse:
    document = await cases.templates.instantiate(
        caller,
        WorkspaceId(workspace_id),
        template_id=TemplateId(template_id),
        title=body.title,
        teamspace_id=TeamspaceId(body.teamspace_id) if body.teamspace_id else None,
    )
    return DocumentResponse.from_domain(document)


@router.delete("/api/v1/templates/{template_id}", status_code=204)
async def delete_template(template_id: str, cases: Cases, caller: Caller) -> None:
    await cases.templates.delete(caller, TemplateId(template_id))
