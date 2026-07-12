"""In-memory implementations of the application ports.

These are the reference implementations for the port contract tests
(architecture-quality spec): every real adapter must behave like its fake.
"""

from __future__ import annotations

import asyncio
import itertools
from datetime import UTC, datetime, timedelta

from cyberarche.application.ports.agent import AgentRun
from cyberarche.application.ports.bus import MessageHandler, Unsubscribe
from cyberarche.application.ports.crdt import LoggedUpdate
from cyberarche.application.ports.queue import QueuedJob
from cyberarche.application.ports.storage import Blob
from cyberarche.application.ports.identity import Claims
from cyberarche.application.ports.llm import LLMMessage, LLMResponse, ToolSpec
from cyberarche.application.ports.mcp import ExternalTool
from cyberarche.domain.api_keys import ApiKey
from cyberarche.domain.connectors import Connector
from cyberarche.domain.ids import ConnectorId, ShareLinkId
from cyberarche.domain.sharing import Comment, ShareLink
from cyberarche.application.ports.rag import (
    IngestionRecord,
    RagQueryMode,
    RagTask,
    RagTaskStatus,
)
from cyberarche.domain.documents import Document
from cyberarche.domain.errors import NotAuthenticated, NotFound
from cyberarche.domain.ids import (
    DocumentId,
    FolderId,
    SnapshotId,
    TeamspaceId,
    TenantId,
    UserId,
    WorkspaceId,
)
from cyberarche.domain.memberships import DocumentGrant, WorkspaceMembership
from cyberarche.domain.folders import Folder
from cyberarche.domain.snapshots import Snapshot
from cyberarche.domain.teamspaces import Teamspace, TeamspaceMembership
from cyberarche.domain.workspaces import Workspace


class FixedClock:
    def __init__(self, start: datetime | None = None) -> None:
        self._now = start or datetime(2026, 1, 1, tzinfo=UTC)

    def now(self) -> datetime:
        return self._now

    def tick(self, seconds: float = 1.0) -> None:
        self._now += timedelta(seconds=seconds)


class SequentialIds:
    def __init__(self, prefix: str = "id") -> None:
        self._prefix = prefix
        self._counter = itertools.count(1)

    def new_id(self) -> str:
        return f"{self._prefix}-{next(self._counter):04d}"


class InMemoryWorkspaceRepository:
    def __init__(self) -> None:
        self._items: dict[WorkspaceId, Workspace] = {}

    async def add(self, workspace: Workspace) -> None:
        self._items[workspace.id] = workspace

    async def get(self, tenant_id: TenantId, workspace_id: WorkspaceId) -> Workspace | None:
        workspace = self._items.get(workspace_id)
        if workspace is None or workspace.tenant_id != tenant_id:
            return None
        return workspace

    async def list_for_tenant(self, tenant_id: TenantId) -> list[Workspace]:
        return [w for w in self._items.values() if w.tenant_id == tenant_id]

    async def update(self, workspace: Workspace) -> None:
        self._items[workspace.id] = workspace


class InMemoryDocumentRepository:
    def __init__(self) -> None:
        self._items: dict[DocumentId, Document] = {}

    async def add(self, document: Document) -> None:
        self._items[document.id] = document

    async def get(self, tenant_id: TenantId, document_id: DocumentId) -> Document | None:
        document = self._items.get(document_id)
        if document is None or document.tenant_id != tenant_id:
            return None
        return document

    async def get_any_tenant(self, document_id: DocumentId) -> Document | None:
        return self._items.get(document_id)

    async def children(
        self,
        tenant_id: TenantId,
        workspace_id: WorkspaceId,
        parent_id: DocumentId | None,
        *,
        include_trashed: bool = False,
    ) -> list[Document]:
        matches = [
            d
            for d in self._items.values()
            if d.tenant_id == tenant_id
            and d.workspace_id == workspace_id
            and d.parent_id == parent_id
            and (include_trashed or not d.trashed)
        ]
        return sorted(matches, key=lambda d: d.position)

    async def list_trashed(
        self, tenant_id: TenantId, workspace_id: WorkspaceId
    ) -> list[Document]:
        return [
            d
            for d in self._items.values()
            if d.tenant_id == tenant_id and d.workspace_id == workspace_id and d.trashed
        ]

    async def list_in_workspace(
        self, tenant_id: TenantId, workspace_id: WorkspaceId
    ) -> list[Document]:
        matches = [
            d
            for d in self._items.values()
            if d.tenant_id == tenant_id
            and d.workspace_id == workspace_id
            and not d.trashed
        ]
        return sorted(matches, key=lambda d: d.title.lower())

    async def update(self, document: Document) -> None:
        self._items[document.id] = document

    async def update_many(self, documents: list[Document]) -> None:
        for document in documents:
            self._items[document.id] = document

    async def purge(
        self, tenant_id: TenantId, document_id: DocumentId
    ) -> list[DocumentId]:
        root = self._items.get(document_id)
        if root is None or root.tenant_id != tenant_id:
            return []
        # Collect the subtree, then remove it. Owned rows (snapshots, comments,
        # update log) live in sibling stores keyed by document_id and are only
        # reachable through the document, which is gone — so removing the
        # documents matches Postgres's observable cascade.
        removed: list[DocumentId] = []
        frontier = [document_id]
        while frontier:
            current = frontier.pop()
            if current not in self._items:
                continue
            del self._items[current]
            removed.append(current)
            frontier.extend(
                d.id for d in self._items.values() if d.parent_id == current
            )
        return removed

    async def list_for_folder(
        self, tenant_id: TenantId, folder_id: FolderId
    ) -> list[Document]:
        return [
            d
            for d in self._items.values()
            if d.tenant_id == tenant_id and d.folder_id == folder_id and not d.trashed
        ]

    async def list_for_teamspace(
        self, tenant_id: TenantId, teamspace_id: TeamspaceId
    ) -> list[Document]:
        matches = [
            d
            for d in self._items.values()
            if d.tenant_id == tenant_id
            and d.teamspace_id == teamspace_id
            and not d.trashed
        ]
        return sorted(matches, key=lambda d: d.position)

    async def search_by_title(
        self, tenant_id: TenantId, query: str, *, limit: int = 20
    ) -> list[Document]:
        needle = query.lower()
        matches = [
            d
            for d in self._items.values()
            if d.tenant_id == tenant_id and not d.trashed and needle in d.title.lower()
        ]
        return sorted(matches, key=lambda d: d.title)[:limit]


class InMemorySnapshotRepository:
    def __init__(self) -> None:
        self._items: dict[DocumentId, list[Snapshot]] = {}

    async def add(self, snapshot: Snapshot) -> None:
        self._items.setdefault(snapshot.document_id, []).append(snapshot)

    async def get(self, document_id: DocumentId, snapshot_id: SnapshotId) -> Snapshot | None:
        for snapshot in self._items.get(document_id, []):
            if snapshot.id == snapshot_id:
                return snapshot
        return None

    async def list_for_document(self, document_id: DocumentId) -> list[Snapshot]:
        return sorted(self._items.get(document_id, []), key=lambda s: s.seq)

    async def latest(self, document_id: DocumentId) -> Snapshot | None:
        snapshots = self._items.get(document_id, [])
        return max(snapshots, key=lambda s: s.seq) if snapshots else None


class InMemoryMembershipRepository:
    def __init__(self) -> None:
        self._workspace: dict[tuple[WorkspaceId, UserId], WorkspaceMembership] = {}
        self._document: dict[tuple[DocumentId, UserId], DocumentGrant] = {}

    async def add_workspace_member(self, membership: WorkspaceMembership) -> None:
        self._workspace[(membership.workspace_id, membership.user_id)] = membership

    async def workspace_role(
        self, workspace_id: WorkspaceId, user_id: UserId
    ) -> WorkspaceMembership | None:
        return self._workspace.get((workspace_id, user_id))

    async def add_document_grant(self, grant: DocumentGrant) -> None:
        self._document[(grant.document_id, grant.user_id)] = grant

    async def document_grant(
        self, document_id: DocumentId, user_id: UserId
    ) -> DocumentGrant | None:
        return self._document.get((document_id, user_id))

    async def document_grants_for_user(self, user_id: UserId) -> list[DocumentGrant]:
        grants = [g for g in self._document.values() if g.user_id == user_id]
        return sorted(grants, key=lambda g: g.granted_at, reverse=True)


class InMemoryUpdateLog:
    def __init__(self, clock: FixedClock | None = None) -> None:
        self._clock = clock or FixedClock()
        self._items: dict[DocumentId, list[LoggedUpdate]] = {}
        self._seq = itertools.count(1)

    async def append(
        self, document_id: DocumentId, update: bytes, *, origin: str | None
    ) -> LoggedUpdate:
        logged = LoggedUpdate(
            seq=next(self._seq),
            document_id=document_id,
            update=update,
            origin=origin,
            created_at=self._clock.now(),
        )
        self._items.setdefault(document_id, []).append(logged)
        return logged

    async def list_for_document(self, document_id: DocumentId) -> list[LoggedUpdate]:
        return list(self._items.get(document_id, []))

    async def count(self, document_id: DocumentId) -> int:
        return len(self._items.get(document_id, []))

    async def replace_with(
        self, document_id: DocumentId, merged: bytes, *, up_to_seq: int
    ) -> None:
        kept = [u for u in self._items.get(document_id, []) if u.seq > up_to_seq]
        compacted = LoggedUpdate(
            seq=next(self._seq),
            document_id=document_id,
            update=merged,
            origin="compaction",
            created_at=self._clock.now(),
        )
        self._items[document_id] = [compacted] + kept


class InMemoryRag:
    """RagPort fake: isolated per-slug projects, deterministic task lifecycle.

    Uploaded tasks start PROCESSING and complete on the next status poll,
    mimicking the async MMDI pipeline.
    """

    def __init__(self) -> None:
        self.projects: dict[str, dict[str, bytes]] = {}
        self.tasks: dict[str, dict[str, RagTask]] = {}
        self._task_files: dict[str, str] = {}
        self._counter = itertools.count(1)

    async def ensure_project(self, slug: str, *, name: str) -> None:
        self.projects.setdefault(slug, {})
        self.tasks.setdefault(slug, {})

    async def upload(
        self, slug: str, *, filename: str, content: bytes, content_type: str
    ) -> RagTask:
        task = RagTask(
            task_id=f"task-{next(self._counter):04d}",
            status=RagTaskStatus.PROCESSING,
        )
        self.projects.setdefault(slug, {})[filename] = content
        self.tasks.setdefault(slug, {})[task.task_id] = task
        self._task_files[task.task_id] = filename
        return task

    async def task_status(self, slug: str, task_id: str) -> RagTask:
        task = self.tasks.get(slug, {}).get(task_id)
        if task is None:
            raise NotFound("RAG task not found")
        if task.status is RagTaskStatus.PROCESSING:  # completes on next poll
            task = RagTask(task_id=task_id, status=RagTaskStatus.COMPLETED)
            self.tasks[slug][task_id] = task
        return task

    async def query(self, slug: str, *, query: str, mode: RagQueryMode) -> str:
        filenames = sorted(self.projects.get(slug, {}))
        return f"[{slug}:{mode.value}] {query} -> sources: {', '.join(filenames)}"

    async def delete_datasource(self, slug: str, filename: str) -> None:
        self.projects.get(slug, {}).pop(filename, None)


class InMemoryIngestionRepository:
    def __init__(self) -> None:
        self._items: dict[str, IngestionRecord] = {}

    async def add(self, record: IngestionRecord) -> None:
        self._items[record.task_id] = record

    async def get(
        self, workspace_id: WorkspaceId, task_id: str
    ) -> IngestionRecord | None:
        record = self._items.get(task_id)
        if record is None or record.workspace_id != workspace_id:
            return None
        return record

    async def by_hash(
        self, workspace_id: WorkspaceId, content_hash: str
    ) -> IngestionRecord | None:
        for record in self._items.values():
            if record.workspace_id == workspace_id and record.content_hash == content_hash:
                return record
        return None

    async def by_task_id(self, task_id: str) -> IngestionRecord | None:
        return self._items.get(task_id)

    async def list_for_workspace(
        self, workspace_id: WorkspaceId
    ) -> list[IngestionRecord]:
        return [r for r in self._items.values() if r.workspace_id == workspace_id]

    async def update(self, record: IngestionRecord) -> None:
        self._items[record.task_id] = record

    async def delete_by_filename(
        self, workspace_id: WorkspaceId, filename: str
    ) -> None:
        self._items = {
            task_id: record
            for task_id, record in self._items.items()
            if not (record.workspace_id == workspace_id and record.filename == filename)
        }


class ScriptedLLM:
    """LLMPort fake: replays scripted responses and records requests."""

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self.requests: list[list[LLMMessage]] = []
        self.tools_seen: list[list[ToolSpec]] = []
        self.reasoning_seen: list[str | None] = []

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        tools: list[ToolSpec] | None = None,
        reasoning_effort: str | None = None,
    ) -> LLMResponse:
        self.requests.append(list(messages))
        self.tools_seen.append(list(tools or []))
        self.reasoning_seen.append(reasoning_effort)
        if not self._responses:
            return LLMResponse(text="(exhausted)")
        return self._responses.pop(0)


_STUB_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class ScriptedImageGenerator:
    """ImageGenerationPort fake: returns a fixed 1x1 PNG and records prompts."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate(self, prompt: str, *, size: str = "1024x1024"):
        from cyberarche.application.ports.images import GeneratedImage

        self.prompts.append(prompt)
        return GeneratedImage(content=_STUB_PNG, content_type="image/png")


class InMemoryTemplateRepository:
    """TemplateRepository fake."""

    def __init__(self) -> None:
        self._items: dict[str, object] = {}

    async def add(self, template) -> None:
        self._items[str(template.id)] = template

    async def list_for_workspace(self, tenant_id, workspace_id):
        mine = [
            t
            for t in self._items.values()
            if str(t.tenant_id) == str(tenant_id)
            and str(t.workspace_id) == str(workspace_id)
        ]
        mine.sort(key=lambda t: t.created_at, reverse=True)
        return mine

    async def get(self, tenant_id, template_id):
        t = self._items.get(str(template_id))
        return t if t and str(t.tenant_id) == str(tenant_id) else None

    async def delete(self, tenant_id, template_id) -> None:
        t = self._items.get(str(template_id))
        if t and str(t.tenant_id) == str(tenant_id):
            del self._items[str(template_id)]


class InMemoryAgentSkillRepository:
    """AgentSkillRepository fake."""

    def __init__(self) -> None:
        self._items: dict[str, object] = {}

    async def add(self, skill) -> None:
        self._items[str(skill.id)] = skill

    async def list_for_workspace(self, tenant_id, workspace_id):
        mine = [
            s
            for s in self._items.values()
            if str(s.tenant_id) == str(tenant_id)
            and str(s.workspace_id) == str(workspace_id)
        ]
        mine.sort(key=lambda s: s.created_at, reverse=True)
        return mine

    async def get(self, tenant_id, skill_id):
        s = self._items.get(str(skill_id))
        return s if s and str(s.tenant_id) == str(tenant_id) else None

    async def update(self, skill) -> None:
        if str(skill.id) in self._items:
            self._items[str(skill.id)] = skill

    async def delete(self, tenant_id, skill_id) -> None:
        s = self._items.get(str(skill_id))
        if s and str(s.tenant_id) == str(tenant_id):
            del self._items[str(skill_id)]


class InMemoryCustomInstructionsRepository:
    """CustomInstructionsRepository fake, keyed by (tenant, workspace, user)."""

    def __init__(self) -> None:
        self._items: dict[tuple[str, str, str | None], object] = {}

    @staticmethod
    def _key(tenant_id, workspace_id, user_id):
        return (str(tenant_id), str(workspace_id), str(user_id) if user_id else None)

    async def get(self, tenant_id, workspace_id, user_id):
        return self._items.get(self._key(tenant_id, workspace_id, user_id))

    async def upsert(self, record) -> None:
        self._items[self._key(record.tenant_id, record.workspace_id, record.user_id)] = (
            record
        )

    async def clear(self, tenant_id, workspace_id, user_id) -> None:
        self._items.pop(self._key(tenant_id, workspace_id, user_id), None)


def _memory_tokens(query: str) -> list[str]:
    seen: dict[str, None] = {}
    for raw in query.lower().split():
        token = "".join(ch for ch in raw if ch.isalnum())
        if len(token) >= 3:
            seen.setdefault(token, None)
    return list(seen)


class InMemoryAgentMemoryRepository:
    """AgentMemoryRepository fake: recency + keyword recall, tenant-scoped."""

    def __init__(self) -> None:
        self._items: dict[str, object] = {}

    def _scoped(self, tenant_id, workspace_id):
        mine = [
            m
            for m in self._items.values()
            if str(m.tenant_id) == str(tenant_id)
            and str(m.workspace_id) == str(workspace_id)
        ]
        mine.sort(key=lambda m: m.created_at, reverse=True)
        return mine

    async def add(self, memory) -> None:
        self._items[str(memory.id)] = memory

    async def list_for_workspace(self, tenant_id, workspace_id):
        return self._scoped(tenant_id, workspace_id)

    async def recent(self, tenant_id, workspace_id, limit):
        return self._scoped(tenant_id, workspace_id)[: max(0, limit)]

    async def relevant(self, tenant_id, workspace_id, query, limit):
        tokens = _memory_tokens(query)
        if not tokens:
            return []
        hits = [
            m
            for m in self._scoped(tenant_id, workspace_id)
            if any(token in m.text.lower() for token in tokens)
        ]
        return hits[: max(0, limit)]

    async def get(self, tenant_id, memory_id):
        m = self._items.get(str(memory_id))
        return m if m and str(m.tenant_id) == str(tenant_id) else None

    async def update(self, memory) -> None:
        if str(memory.id) in self._items:
            self._items[str(memory.id)] = memory

    async def delete(self, tenant_id, memory_id) -> None:
        m = self._items.get(str(memory_id))
        if m and str(m.tenant_id) == str(tenant_id):
            del self._items[str(memory_id)]


class InMemoryNotificationRepository:
    """NotificationRepository fake: an in-process per-user inbox."""

    def __init__(self) -> None:
        self._items: list = []

    async def add(self, notification) -> None:
        self._items.append(notification)

    async def list_for_user(self, tenant_id, user_id, *, limit: int = 50):
        mine = [
            n
            for n in self._items
            if str(n.tenant_id) == str(tenant_id) and str(n.recipient_id) == str(user_id)
        ]
        mine.sort(key=lambda n: n.created_at, reverse=True)
        return mine[:limit]

    async def unread_count(self, tenant_id, user_id) -> int:
        return sum(
            1
            for n in self._items
            if str(n.tenant_id) == str(tenant_id)
            and str(n.recipient_id) == str(user_id)
            and not n.read
        )

    async def mark_read(self, tenant_id, user_id, notification_id) -> None:
        from dataclasses import replace

        self._items = [
            replace(n, read=True)
            if str(n.id) == str(notification_id)
            and str(n.recipient_id) == str(user_id)
            and str(n.tenant_id) == str(tenant_id)
            else n
            for n in self._items
        ]

    async def mark_all_read(self, tenant_id, user_id) -> None:
        from dataclasses import replace

        self._items = [
            replace(n, read=True)
            if str(n.recipient_id) == str(user_id) and str(n.tenant_id) == str(tenant_id)
            else n
            for n in self._items
        ]


class InMemoryInferredLinkRepository:
    """InferredLinkRepository fake: an in-process cache of inferred relations."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str], object] = {}

    async def get_many(self, tenant_id, source_ids):
        out = {}
        for sid in source_ids:
            record = self._records.get((str(tenant_id), str(sid)))
            if record is not None:
                out[str(sid)] = record
        return out

    async def put(self, tenant_id, record) -> None:
        self._records[(str(tenant_id), record.source_document_id)] = record


class ScriptedMeetings:
    """MeetingsPort fake: records the access token it was called with and returns
    a fixed recording, so the agent meeting tools can be tested offline."""

    def __init__(self) -> None:
        self.tokens: list[str] = []
        self.asked: list[str] = []

    async def list_recordings(self, access_token: str, *, limit: int = 20):
        from cyberarche.application.ports.meetings import MeetingSummary

        self.tokens.append(access_token)
        return [
            MeetingSummary(
                id="rec-1",
                status="ready",
                captured_at="2026-07-01T10:00:00Z",
                headline="Weekly standup",
            )
        ]

    async def get_recording(self, access_token: str, recording_id: str):
        from cyberarche.application.ports.meetings import MeetingTranscript

        self.tokens.append(access_token)
        return MeetingTranscript(
            id=recording_id,
            status="ready",
            captured_at="2026-07-01T10:00:00Z",
            headline="Weekly standup",
            abstract="The team synced on the roadmap.",
            bullets=["Shipped the editor", "Planned Q3"],
            action_items=["Alice: draft the spec"],
            transcript="Alice: hello everyone. Bob: hi.",
        )

    async def ask(self, access_token: str, question: str) -> str:
        self.tokens.append(access_token)
        self.asked.append(question)
        return "Across your meetings: the roadmap was approved."


class ScriptedWebMedia:
    """WebMediaPort fake: records the forwarded access token and the calls, and
    returns fixed results, so the agent web/media tools can be tested offline."""

    def __init__(self) -> None:
        self.tokens: list[str] = []
        self.searched: list[str] = []
        self.transcripts: list[str] = []
        self.playlists: list[str] = []

    async def search(self, access_token: str, query: str, *, num: int = 10):
        from cyberarche.application.ports.web_media import SearchResult

        self.tokens.append(access_token)
        self.searched.append(query)
        return [
            SearchResult(title="First", url="https://a.test/1", snippet="one"),
            SearchResult(title="Second", url="https://a.test/2", snippet=None),
        ][:num]

    async def youtube_transcript(
        self, access_token: str, video: str, *, lang: str | None = None
    ):
        from cyberarche.application.ports.web_media import Transcript

        self.tokens.append(access_token)
        self.transcripts.append(video)
        return Transcript(
            video_id=video,
            text="Hello and welcome to the talk.",
            title="A talk",
            lang=lang or "en",
        )

    async def youtube_playlist(self, access_token: str, playlist: str):
        from cyberarche.application.ports.web_media import PlaylistVideo

        self.tokens.append(access_token)
        self.playlists.append(playlist)
        return [
            PlaylistVideo(video_id="v1", url="https://y.test/v1", title="Ep 1"),
            PlaylistVideo(video_id="v2", url="https://y.test/v2", title="Ep 2"),
        ]


class ScriptedCodeExecutor:
    """CodeExecutionPort fake: records code and returns a scripted result
    (one PNG figure + stdout) so agent code-execution can be tested offline."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def run(self, code: str):
        from cyberarche.application.ports.code_exec import (
            CodeExecutionResult,
            CodeImage,
        )

        self.calls.append(code)
        return CodeExecutionResult(
            success=True,
            stdout="mean=2.0\n",
            stderr="",
            result="None",
            error=None,
            images=[CodeImage("figure_1.png", _STUB_PNG, "image/png")],
            tables=[],
        )


class InMemoryAgentRunRepository:
    def __init__(self) -> None:
        self._items: list[AgentRun] = []

    async def add(self, run: AgentRun) -> None:
        self._items.append(run)

    async def list_for_document(
        self, tenant_id: TenantId, document_id: DocumentId
    ) -> list[AgentRun]:
        return [
            r
            for r in self._items
            if r.tenant_id == tenant_id and r.document_id == document_id
        ]


class FakeMcpClient:
    """McpClientPort fake: scripted per-endpoint tools; unreachable endpoints
    raise. Records calls with the credentials presented."""

    def __init__(self, servers: dict[str, list[ExternalTool]] | None = None) -> None:
        self.servers = servers or {}
        self.calls: list[tuple[str, str, str, dict]] = []
        self.results: dict[str, str] = {}

    async def list_tools(self, endpoint: str, credentials: str) -> list[ExternalTool]:
        if endpoint not in self.servers:
            raise ConnectionError(f"unreachable: {endpoint}")
        return list(self.servers[endpoint])

    async def call_tool(
        self, endpoint: str, credentials: str, tool: str, arguments: dict
    ) -> str:
        if endpoint not in self.servers:
            raise ConnectionError(f"unreachable: {endpoint}")
        self.calls.append((endpoint, credentials, tool, arguments))
        return self.results.get(tool, f"{tool} ok")


class NaiveSecretBox:
    """SecretBoxPort fake: reversible obfuscation, clearly not plaintext."""

    def encrypt(self, plaintext: str) -> bytes:
        return b"enc:" + plaintext.encode()[::-1]

    def decrypt(self, ciphertext: bytes) -> str:
        return ciphertext[4:][::-1].decode()


class InMemoryConnectorRepository:
    def __init__(self) -> None:
        self._items: dict[ConnectorId, Connector] = {}
        self._secrets: dict[ConnectorId, bytes] = {}

    async def add(self, connector: Connector, credentials_encrypted: bytes) -> None:
        self._items[connector.id] = connector
        self._secrets[connector.id] = credentials_encrypted

    async def get(
        self, tenant_id: TenantId, connector_id: ConnectorId
    ) -> Connector | None:
        connector = self._items.get(connector_id)
        if connector is None or connector.tenant_id != tenant_id:
            return None
        return connector

    async def credentials(self, connector_id: ConnectorId) -> bytes:
        if connector_id not in self._secrets:
            raise NotFound("connector not found")
        return self._secrets[connector_id]

    async def list_for_workspace(
        self, tenant_id: TenantId, workspace_id: WorkspaceId
    ) -> list[Connector]:
        return [
            c
            for c in self._items.values()
            if c.tenant_id == tenant_id and c.workspace_id == workspace_id
        ]

    async def by_slug(
        self, tenant_id: TenantId, workspace_id: WorkspaceId, slug: str
    ) -> Connector | None:
        for connector in await self.list_for_workspace(tenant_id, workspace_id):
            if connector.slug == slug:
                return connector
        return None

    async def update(self, connector: Connector) -> None:
        self._items[connector.id] = connector

    async def delete(self, tenant_id: TenantId, connector_id: ConnectorId) -> None:
        connector = self._items.get(connector_id)
        if connector is not None and connector.tenant_id == tenant_id:
            del self._items[connector_id]
            self._secrets.pop(connector_id, None)


class InMemoryShareLinkRepository:
    def __init__(self) -> None:
        self._items: dict[ShareLinkId, ShareLink] = {}

    async def add(self, link: ShareLink) -> None:
        self._items[link.id] = link

    async def get(self, link_id: ShareLinkId) -> ShareLink | None:
        return self._items.get(link_id)

    async def list_for_document(self, document_id: DocumentId) -> list[ShareLink]:
        return [
            link for link in self._items.values() if link.document_id == document_id
        ]

    async def update(self, link: ShareLink) -> None:
        self._items[link.id] = link


class InMemoryCommentRepository:
    def __init__(self) -> None:
        self._items: dict[str, Comment] = {}

    async def add(self, comment: Comment) -> None:
        self._items[comment.id] = comment

    async def get(self, document_id: DocumentId, comment_id: str) -> Comment | None:
        comment = self._items.get(comment_id)
        if comment is None or comment.document_id != document_id:
            return None
        return comment

    async def list_for_document(self, document_id: DocumentId) -> list[Comment]:
        return sorted(
            (c for c in self._items.values() if c.document_id == document_id),
            key=lambda c: c.created_at,
        )

    async def update(self, comment: Comment) -> None:
        self._items[comment.id] = comment


class InMemoryBlobStorage:
    def __init__(self) -> None:
        self.blobs: dict[str, Blob] = {}

    async def put(self, key: str, content: bytes, *, content_type: str) -> None:
        self.blobs[key] = Blob(key=key, content=content, content_type=content_type)

    async def get(self, key: str) -> Blob | None:
        return self.blobs.get(key)

    async def delete(self, key: str) -> None:
        self.blobs.pop(key, None)


class InMemoryTaskQueue:
    """TaskQueuePort fake/single-process adapter over asyncio.Queue."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[QueuedJob] = asyncio.Queue()
        self._counter = itertools.count(1)

    async def enqueue(self, job_type: str, payload: dict) -> str:
        job = QueuedJob(id=f"job-{next(self._counter):04d}", type=job_type, payload=payload)
        await self._queue.put(job)
        return job.id

    async def dequeue(self, *, timeout: float = 5.0) -> QueuedJob | None:
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except TimeoutError:
            return None

    def pending(self) -> int:
        return self._queue.qsize()


class InProcessPeerBus:
    """PeerBusPort adapter for a single process (also the test fake).

    Sharing one instance across several app replicas in a test simulates a
    broker connecting them.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[MessageHandler]] = {}

    async def publish(self, channel: str, message: bytes) -> None:
        for handler in list(self._handlers.get(channel, [])):
            await handler(message)

    async def subscribe(
        self, channel: str, handler: MessageHandler
    ) -> Unsubscribe:
        self._handlers.setdefault(channel, []).append(handler)

        async def unsubscribe() -> None:
            handlers = self._handlers.get(channel, [])
            if handler in handlers:
                handlers.remove(handler)
            if not handlers:
                self._handlers.pop(channel, None)

        return unsubscribe


class InMemoryApiKeyRepository:
    def __init__(self) -> None:
        self._items: dict[str, ApiKey] = {}

    async def add(self, key: ApiKey) -> None:
        self._items[key.id] = key

    async def by_hash(self, secret_hash: str) -> ApiKey | None:
        for key in self._items.values():
            if key.secret_hash == secret_hash:
                return key
        return None

    async def get(self, user_id: UserId, key_id: str) -> ApiKey | None:
        key = self._items.get(key_id)
        if key is None or key.user_id != user_id:
            return None
        return key

    async def list_for_user(
        self, tenant_id: TenantId, user_id: UserId
    ) -> list[ApiKey]:
        return [
            k
            for k in self._items.values()
            if k.tenant_id == tenant_id and k.user_id == user_id
        ]

    async def update(self, key: ApiKey) -> None:
        self._items[key.id] = key


class InMemoryTeamspaceRepository:
    def __init__(self) -> None:
        self._items: dict[TeamspaceId, Teamspace] = {}
        self._members: dict[tuple[TeamspaceId, UserId], TeamspaceMembership] = {}

    async def add(self, teamspace: Teamspace) -> None:
        self._items[teamspace.id] = teamspace

    async def get(
        self, tenant_id: TenantId, teamspace_id: TeamspaceId
    ) -> Teamspace | None:
        teamspace = self._items.get(teamspace_id)
        if teamspace is None or teamspace.tenant_id != tenant_id:
            return None
        return teamspace

    async def list_for_workspace(
        self, tenant_id: TenantId, workspace_id: WorkspaceId
    ) -> list[Teamspace]:
        return [
            t
            for t in self._items.values()
            if t.tenant_id == tenant_id and t.workspace_id == workspace_id
        ]

    async def add_member(self, membership: TeamspaceMembership) -> None:
        self._members[(membership.teamspace_id, membership.user_id)] = membership

    async def remove_member(self, teamspace_id: TeamspaceId, user_id: UserId) -> None:
        self._members.pop((teamspace_id, user_id), None)

    async def member_role(
        self, teamspace_id: TeamspaceId, user_id: UserId
    ) -> TeamspaceMembership | None:
        return self._members.get((teamspace_id, user_id))

    async def members(self, teamspace_id: TeamspaceId) -> list[TeamspaceMembership]:
        return [m for m in self._members.values() if m.teamspace_id == teamspace_id]

    async def teamspaces_for_user(
        self, tenant_id: TenantId, workspace_id: WorkspaceId, user_id: UserId
    ) -> list[Teamspace]:
        mine = {m.teamspace_id for m in self._members.values() if m.user_id == user_id}
        return [
            t
            for t in await self.list_for_workspace(tenant_id, workspace_id)
            if t.id in mine
        ]

    async def delete(self, tenant_id: TenantId, teamspace_id: TeamspaceId) -> None:
        teamspace = self._items.get(teamspace_id)
        if teamspace is None or teamspace.tenant_id != tenant_id:
            return
        del self._items[teamspace_id]
        for key in [k for k in self._members if k[0] == teamspace_id]:
            del self._members[key]


class InMemoryFavoriteRepository:
    def __init__(self) -> None:
        self._items: set[tuple[UserId, DocumentId]] = set()

    async def add(self, user_id: UserId, document_id: DocumentId) -> None:
        self._items.add((user_id, document_id))

    async def remove(self, user_id: UserId, document_id: DocumentId) -> None:
        self._items.discard((user_id, document_id))

    async def list_for_user(self, user_id: UserId) -> list[DocumentId]:
        return [d for (u, d) in self._items if u == user_id]

    async def is_favorite(self, user_id: UserId, document_id: DocumentId) -> bool:
        return (user_id, document_id) in self._items


class StaticTokenPort:
    """Maps opaque test tokens to claims; anything else is rejected."""

    def __init__(self, tokens: dict[str, Claims] | None = None) -> None:
        self._tokens = tokens or {}

    def register(self, token: str, claims: Claims) -> None:
        self._tokens[token] = claims

    async def verify(self, token: str) -> Claims:
        claims = self._tokens.get(token)
        if claims is None:
            raise NotAuthenticated("invalid token")
        return claims


class AllowAllAuthorization:
    async def evaluate(self, *, user_id: str, action: str, resource: str) -> bool:
        return True


class InMemoryFolderRepository:
    def __init__(self) -> None:
        self._items: dict[FolderId, Folder] = {}

    async def add(self, folder: Folder) -> None:
        self._items[folder.id] = folder

    async def get(self, tenant_id: TenantId, folder_id: FolderId) -> Folder | None:
        folder = self._items.get(folder_id)
        if folder is None or folder.tenant_id != tenant_id:
            return None
        return folder

    async def list_for_workspace(
        self, tenant_id: TenantId, workspace_id: WorkspaceId
    ) -> list[Folder]:
        return [
            f
            for f in self._items.values()
            if f.tenant_id == tenant_id and f.workspace_id == workspace_id
        ]

    async def list_for_teamspace(
        self, tenant_id: TenantId, teamspace_id: TeamspaceId
    ) -> list[Folder]:
        return [
            f
            for f in self._items.values()
            if f.tenant_id == tenant_id and f.teamspace_id == teamspace_id
        ]

    async def update(self, folder: Folder) -> None:
        self._items[folder.id] = folder

    async def delete(self, tenant_id: TenantId, folder_id: FolderId) -> None:
        root = self._items.get(folder_id)
        if root is None or root.tenant_id != tenant_id:
            return
        # Cascade sub-folders (mirrors the FK ON DELETE CASCADE).
        frontier = [folder_id]
        while frontier:
            current = frontier.pop()
            if current not in self._items:
                continue
            del self._items[current]
            frontier.extend(
                f.id for f in self._items.values() if f.parent_folder_id == current
            )
