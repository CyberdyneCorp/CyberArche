"""In-memory implementations of the application ports.

These are the reference implementations for the port contract tests
(architecture-quality spec): every real adapter must behave like its fake.
"""

from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta

from cyberarche.application.ports.crdt import LoggedUpdate
from cyberarche.application.ports.identity import Claims
from cyberarche.application.ports.rag import (
    IngestionRecord,
    RagQueryMode,
    RagTask,
    RagTaskStatus,
)
from cyberarche.domain.documents import Document
from cyberarche.domain.errors import NotAuthenticated, NotFound
from cyberarche.domain.ids import DocumentId, SnapshotId, TenantId, UserId, WorkspaceId
from cyberarche.domain.memberships import DocumentGrant, WorkspaceMembership
from cyberarche.domain.snapshots import Snapshot
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

    async def update(self, document: Document) -> None:
        self._items[document.id] = document

    async def update_many(self, documents: list[Document]) -> None:
        for document in documents:
            self._items[document.id] = document


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
