"""RagPort adapter over the CyberdyneRAG API.

Endpoints (see the service's OpenAPI):
- POST   /api/v1/projects/                                  create project
- GET    /api/v1/projects/{slug}                            check existence
- POST   /api/v1/projects/{slug}/documents/upload           multipart upload -> task
- GET    /api/v1/projects/{slug}/tasks/{task_id}            poll task
- GET    /api/v1/projects/{slug}/queries/sync               query (mode param)
- DELETE /api/v1/projects/{slug}/datasources/{filename}     delete + cascade
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import httpx

from cyberarche.application.ports.rag import RagQueryMode, RagTask, RagTaskStatus
from cyberarche.domain.errors import Conflict, NotFound

TokenSource = Callable[[], Awaitable[str]]


class CyberdyneRagAdapter:
    def __init__(
        self, base_url: str, http: httpx.AsyncClient, token_source: TokenSource
    ) -> None:
        self._base = base_url.rstrip("/")
        self._http = http
        self._token_source = token_source

    async def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {await self._token_source()}"}

    async def ensure_project(self, slug: str, *, name: str) -> None:
        headers = await self._headers()
        existing = await self._http.get(
            f"{self._base}/api/v1/projects/{slug}", headers=headers
        )
        if existing.status_code == 200:
            return
        created = await self._http.post(
            f"{self._base}/api/v1/projects/",
            json={"slug": slug, "name": name},
            headers=headers,
        )
        if created.status_code not in (200, 201, 409):  # 409: raced another creator
            raise Conflict(f"RAG project provisioning failed ({created.status_code})")

    async def upload(
        self, slug: str, *, filename: str, content: bytes, content_type: str
    ) -> RagTask:
        response = await self._http.post(
            f"{self._base}/api/v1/projects/{slug}/documents/upload",
            files={"files": (filename, content, content_type)},
            headers=await self._headers(),
        )
        response.raise_for_status()
        payload = response.json()
        return RagTask(
            task_id=str(payload["task_id"]), status=RagTaskStatus.PROCESSING
        )

    async def task_status(self, slug: str, task_id: str) -> RagTask:
        response = await self._http.get(
            f"{self._base}/api/v1/projects/{slug}/tasks/{task_id}",
            headers=await self._headers(),
        )
        if response.status_code == 404:
            raise NotFound("RAG task not found")
        response.raise_for_status()
        payload = response.json()
        return RagTask(
            task_id=task_id,
            status=RagTaskStatus(payload["status"]),
            error=payload.get("error_message"),
        )

    async def query(self, slug: str, *, query: str, mode: RagQueryMode) -> str:
        response = await self._http.get(
            f"{self._base}/api/v1/projects/{slug}/queries/sync",
            params={"query": query, "mode": mode.value},
            headers=await self._headers(),
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("result") or payload.get("response") or ""

    async def delete_datasource(self, slug: str, filename: str) -> None:
        response = await self._http.delete(
            f"{self._base}/api/v1/projects/{slug}/datasources/{filename}",
            headers=await self._headers(),
        )
        if response.status_code not in (200, 202, 204, 404):
            response.raise_for_status()
