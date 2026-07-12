"""Template use cases (templates spec): save a document as a reusable page
template, and create new documents from templates."""

from __future__ import annotations

from typing import Any

from cyberarche.application.authz import AccessControl
from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.crdt import CrdtEnginePort
from cyberarche.application.ports.telemetry import ClockPort, IdPort
from cyberarche.application.ports.templates import TemplateRepository
from cyberarche.application.use_cases.documents import DocumentUseCases
from cyberarche.application.use_cases.realtime import RealtimeUseCases
from cyberarche.domain.documents import Document
from cyberarche.domain.errors import NotAuthorized, NotFound
from cyberarche.domain.ids import (
    DocumentId,
    TemplateId,
    TeamspaceId,
    WorkspaceId,
)
from cyberarche.domain.memberships import Role
from cyberarche.domain.templates import Template


def _with_fresh_ids(blocks: list[dict[str, Any]], ids: IdPort) -> list[dict[str, Any]]:
    """Copy blocks with brand-new ids (recursively) so an instantiated document
    never shares block ids with the template's source."""
    out: list[dict[str, Any]] = []
    for block in blocks:
        fresh = {**block, "id": ids.new_id()}
        children = block.get("children")
        if isinstance(children, list):
            fresh["children"] = _with_fresh_ids(children, ids)
        out.append(fresh)
    return out


class TemplateUseCases:
    def __init__(
        self,
        templates: TemplateRepository,
        documents: DocumentUseCases,
        realtime: RealtimeUseCases,
        engine: CrdtEnginePort,
        access: AccessControl,
        clock: ClockPort,
        ids: IdPort,
    ) -> None:
        self._templates = templates
        self._documents = documents
        self._realtime = realtime
        self._engine = engine
        self._access = access
        self._clock = clock
        self._ids = ids

    async def save_from_document(
        self,
        caller: CallerContext,
        workspace_id: WorkspaceId,
        *,
        name: str,
        document_id: DocumentId,
    ) -> Template:
        await self._access.require_workspace(caller, workspace_id, Role.EDITOR)
        blocks = await self._realtime.read_blocks(caller, document_id)  # needs viewer
        template = Template(
            id=TemplateId(self._ids.new_id()),
            tenant_id=caller.tenant_id,
            workspace_id=workspace_id,
            name=name.strip() or "Untitled template",
            created_by=caller.user_id,
            created_at=self._clock.now(),
            content=blocks,
        )
        await self._templates.add(template)
        return template

    async def list(
        self, caller: CallerContext, workspace_id: WorkspaceId
    ) -> list[Template]:
        await self._access.require_workspace(caller, workspace_id, Role.VIEWER)
        return await self._templates.list_for_workspace(caller.tenant_id, workspace_id)

    async def instantiate(
        self,
        caller: CallerContext,
        workspace_id: WorkspaceId,
        *,
        template_id: TemplateId,
        title: str,
        teamspace_id: TeamspaceId | None = None,
    ) -> Document:
        template = await self._templates.get(caller.tenant_id, template_id)
        if template is None or template.workspace_id != workspace_id:
            raise NotFound("template not found")
        # DocumentUseCases.create enforces workspace/teamspace membership.
        document = await self._documents.create(
            caller,
            workspace_id=workspace_id,
            title=title or template.name,
            teamspace_id=teamspace_id,
        )
        if template.content:
            blocks = _with_fresh_ids(template.content, self._ids)
            state = await self._realtime.current_state(caller, document.id)
            update = self._engine.append_blocks(state, blocks)
            await self._realtime.apply(
                caller, document.id, update, origin=f"template:{caller.user_id}"
            )
        return document

    async def delete(self, caller: CallerContext, template_id: TemplateId) -> None:
        template = await self._templates.get(caller.tenant_id, template_id)
        if template is None:
            raise NotFound("template not found")
        if str(template.created_by) != str(caller.user_id):
            # Only the creator or a workspace owner may delete a template.
            try:
                await self._access.require_workspace(
                    caller, template.workspace_id, Role.OWNER
                )
            except NotAuthorized:
                raise NotAuthorized("only the creator or an owner may delete this")
        await self._templates.delete(caller.tenant_id, template_id)
