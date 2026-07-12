"""Agent persona + memory use cases (ai-agent spec).

Custom instructions (a workspace house style plus an optional per-user layer)
and durable memories that are recalled into later runs. All reads/writes are
tenant-isolated and role-checked through `AccessControl`; `build_context`
selects and renders the persona sections the agent use case prepends to its
system prompt within a fixed budget.
"""

from __future__ import annotations

from cyberarche.application.authz import AccessControl
from cyberarche.application.kernel import CallerContext
from cyberarche.application.ports.agent_memory import (
    AgentMemoryRepository,
    CustomInstructionsRepository,
)
from cyberarche.application.ports.telemetry import ClockPort, IdPort
from cyberarche.domain.agent_persona import (
    AgentMemory,
    CustomInstructions,
    looks_like_secret,
)
from cyberarche.domain.errors import NotAuthorized, ValidationFailed
from cyberarche.domain.ids import (
    AgentMemoryId,
    CustomInstructionsId,
    UserId,
    WorkspaceId,
)
from cyberarche.domain.memberships import Role

# Injection budget (D-4): persona must not crowd out the document context.
_WORKSPACE_INSTR_MAX = 4000
_PERSONAL_INSTR_MAX = 2000
_MEMORY_MAX_ITEMS = 20
_MEMORY_MAX_CHARS = 2000
_RECENT_SEED = 10


def _clip(text: str, limit: int) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


class AgentPersonaUseCases:
    def __init__(
        self,
        instructions: CustomInstructionsRepository,
        memories: AgentMemoryRepository,
        access: AccessControl,
        clock: ClockPort,
        ids: IdPort,
    ) -> None:
        self._instructions = instructions
        self._memories = memories
        self._access = access
        self._clock = clock
        self._ids = ids

    # ---- custom instructions ----------------------------------------------

    async def get_workspace_instructions(
        self, caller: CallerContext, workspace_id: WorkspaceId
    ) -> str | None:
        await self._access.require_workspace(caller, workspace_id, Role.VIEWER)
        record = await self._instructions.get(caller.tenant_id, workspace_id, None)
        return record.instructions if record else None

    async def set_workspace_instructions(
        self, caller: CallerContext, workspace_id: WorkspaceId, text: str
    ) -> None:
        await self._access.require_workspace(caller, workspace_id, Role.EDITOR)
        await self._upsert_instructions(caller, workspace_id, None, text)

    async def clear_workspace_instructions(
        self, caller: CallerContext, workspace_id: WorkspaceId
    ) -> None:
        await self._access.require_workspace(caller, workspace_id, Role.EDITOR)
        await self._instructions.clear(caller.tenant_id, workspace_id, None)

    async def get_personal_instructions(
        self, caller: CallerContext, workspace_id: WorkspaceId
    ) -> str | None:
        await self._access.require_workspace(caller, workspace_id, Role.VIEWER)
        record = await self._instructions.get(
            caller.tenant_id, workspace_id, caller.user_id
        )
        return record.instructions if record else None

    async def set_personal_instructions(
        self, caller: CallerContext, workspace_id: WorkspaceId, text: str
    ) -> None:
        # A personal layer is private to its author; workspace membership only.
        await self._access.require_workspace(caller, workspace_id, Role.VIEWER)
        await self._upsert_instructions(caller, workspace_id, caller.user_id, text)

    async def clear_personal_instructions(
        self, caller: CallerContext, workspace_id: WorkspaceId
    ) -> None:
        await self._access.require_workspace(caller, workspace_id, Role.VIEWER)
        await self._instructions.clear(
            caller.tenant_id, workspace_id, caller.user_id
        )

    async def _upsert_instructions(
        self,
        caller: CallerContext,
        workspace_id: WorkspaceId,
        user_id: UserId | None,
        text: str,
    ) -> None:
        text = text.strip()
        if not text:
            await self._instructions.clear(caller.tenant_id, workspace_id, user_id)
            return
        existing = await self._instructions.get(
            caller.tenant_id, workspace_id, user_id
        )
        record = CustomInstructions(
            id=existing.id
            if existing
            else CustomInstructionsId(self._ids.new_id()),
            tenant_id=caller.tenant_id,
            workspace_id=workspace_id,
            user_id=user_id,
            instructions=text,
            updated_by=caller.user_id,
            updated_at=self._clock.now(),
        )
        await self._instructions.upsert(record)

    # ---- memories ----------------------------------------------------------

    async def list_memories(
        self, caller: CallerContext, workspace_id: WorkspaceId
    ) -> list[AgentMemory]:
        await self._access.require_workspace(caller, workspace_id, Role.VIEWER)
        return await self._memories.list_for_workspace(
            caller.tenant_id, workspace_id
        )

    async def add_memory(
        self, caller: CallerContext, workspace_id: WorkspaceId, text: str
    ) -> AgentMemory:
        await self._access.require_workspace(caller, workspace_id, Role.EDITOR)
        text = text.strip()
        if not text:
            raise ValidationFailed("memory text is empty")
        if looks_like_secret(text):
            raise ValidationFailed(
                "refusing to store a memory that looks like a secret or credential"
            )
        now = self._clock.now()
        memory = AgentMemory(
            id=AgentMemoryId(self._ids.new_id()),
            tenant_id=caller.tenant_id,
            workspace_id=workspace_id,
            text=text,
            created_by=caller.user_id,
            created_at=now,
            updated_at=now,
        )
        await self._memories.add(memory)
        return memory

    async def update_memory(
        self,
        caller: CallerContext,
        workspace_id: WorkspaceId,
        memory_id: AgentMemoryId,
        text: str,
    ) -> AgentMemory:
        await self._access.require_workspace(caller, workspace_id, Role.EDITOR)
        memory = await self._require_memory(caller, workspace_id, memory_id)
        text = text.strip()
        if not text:
            raise ValidationFailed("memory text is empty")
        if looks_like_secret(text):
            raise ValidationFailed(
                "refusing to store a memory that looks like a secret or credential"
            )
        updated = AgentMemory(
            id=memory.id,
            tenant_id=memory.tenant_id,
            workspace_id=memory.workspace_id,
            text=text,
            created_by=memory.created_by,
            created_at=memory.created_at,
            updated_at=self._clock.now(),
        )
        await self._memories.update(updated)
        return updated

    async def delete_memory(
        self,
        caller: CallerContext,
        workspace_id: WorkspaceId,
        memory_id: AgentMemoryId,
    ) -> None:
        memory = await self._require_memory(caller, workspace_id, memory_id)
        # EDITOR may delete any workspace memory; the author may delete their own.
        role = await self._access.workspace_role(caller, workspace_id)
        is_editor = role is not None and role in (Role.EDITOR, Role.OWNER)
        if not is_editor and str(memory.created_by) != str(caller.user_id):
            raise NotAuthorized("only an editor or the author may delete a memory")
        await self._memories.delete(caller.tenant_id, memory_id)

    async def _require_memory(
        self,
        caller: CallerContext,
        workspace_id: WorkspaceId,
        memory_id: AgentMemoryId,
    ) -> AgentMemory:
        await self._access.require_workspace(caller, workspace_id, Role.VIEWER)
        memory = await self._memories.get(caller.tenant_id, memory_id)
        if memory is None or str(memory.workspace_id) != str(workspace_id):
            raise ValidationFailed("memory not found")
        return memory

    # ---- injection ---------------------------------------------------------

    async def build_context(
        self, caller: CallerContext, workspace_id: WorkspaceId, instruction: str
    ) -> str:
        """Persona sections to append to the system prompt, within budget.

        Returns "" when the caller is not a workspace member (a private document
        shared directly does not expose the workspace's persona/memory)."""
        role = await self._access.workspace_role(caller, workspace_id)
        if role is None:
            return ""

        sections: list[str] = []
        workspace = await self._instructions.get(caller.tenant_id, workspace_id, None)
        if workspace and workspace.instructions.strip():
            sections.append(
                "## Workspace instructions (house style — follow these)\n"
                + _clip(workspace.instructions, _WORKSPACE_INSTR_MAX)
            )
        personal = await self._instructions.get(
            caller.tenant_id, workspace_id, caller.user_id
        )
        if personal and personal.instructions.strip():
            sections.append(
                "## The current user's personal instructions\n"
                + _clip(personal.instructions, _PERSONAL_INSTR_MAX)
            )

        memories = await self._select_memories(caller, workspace_id, instruction)
        if memories:
            lines, used = [], 0
            for memory in memories:
                snippet = memory.text.strip().replace("\n", " ")
                if used + len(snippet) > _MEMORY_MAX_CHARS:
                    break
                lines.append(f"- {snippet}")
                used += len(snippet)
            if lines:
                sections.append(
                    "## Remembered facts about this workspace (durable memory)\n"
                    + "\n".join(lines)
                )

        if not sections:
            return ""
        return "\n\n" + "\n\n".join(sections)

    async def _select_memories(
        self, caller: CallerContext, workspace_id: WorkspaceId, instruction: str
    ) -> list[AgentMemory]:
        recent = await self._memories.recent(
            caller.tenant_id, workspace_id, _RECENT_SEED
        )
        relevant = await self._memories.relevant(
            caller.tenant_id, workspace_id, instruction, _RECENT_SEED
        )
        merged: dict[str, AgentMemory] = {}
        for memory in [*relevant, *recent]:  # keyword hits first, then recency
            merged.setdefault(str(memory.id), memory)
        ordered = sorted(
            merged.values(), key=lambda m: m.created_at, reverse=True
        )
        return ordered[:_MEMORY_MAX_ITEMS]
