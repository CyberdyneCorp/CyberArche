"""CodeExecutionPort adapter for the Cyberdyne Python Interpreter.

Flow (see the service OpenAPI): POST /sessions to get a workspace, POST /execute
to run code, then GET /files/{session_id}/{name} to download any figure the run
produced. The interpreter itself auto-captures open matplotlib figures (its
worker saves every `plt.get_fignums()` figure), so we send the user's code
unmodified — appending our own savefig would double-insert the same plot.
Authenticated with a CyberdyneAuth bearer from the service-token source (same
seam as the RAG adapter).
"""

from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable

import httpx

from cyberarche.application.ports.code_exec import CodeExecutionResult, CodeImage

TokenSource = Callable[[], Awaitable[str]]

_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")
_TEXT_MIME_PREFIXES = ("text/", "application/json")


def _dedupe_images(images: list[CodeImage]) -> list[CodeImage]:
    """Drop byte-identical duplicates (e.g. a figure listed under two names)."""
    seen: set[str] = set()
    unique: list[CodeImage] = []
    for image in images:
        digest = hashlib.sha256(image.content).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        unique.append(image)
    return unique


class CyberdyneInterpreterAdapter:
    def __init__(
        self, base_url: str, http: httpx.AsyncClient, token_source: TokenSource
    ) -> None:
        self._base = base_url.rstrip("/")
        self._http = http
        self._token_source = token_source

    async def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {await self._token_source()}"}

    async def run(self, code: str) -> CodeExecutionResult:
        headers = await self._headers()
        session_resp = await self._http.post(
            f"{self._base}/sessions", json={}, headers=headers
        )
        session_resp.raise_for_status()
        session_id = str(session_resp.json()["session_id"])

        exec_resp = await self._http.post(
            f"{self._base}/execute",
            json={
                # Unmodified: the interpreter auto-captures open figures itself.
                "code": code,
                "session_id": session_id,
                "restricted": True,
            },
            headers=headers,
        )
        exec_resp.raise_for_status()
        body = exec_resp.json()

        images = _dedupe_images(
            await self._download_images(session_id, body, headers)
        )
        tables = [
            str(ro.get("text"))
            for ro in body.get("rich_outputs", []) or []
            if ro.get("text")
            and str(ro.get("mime_type", "")).startswith(_TEXT_MIME_PREFIXES)
        ]
        return CodeExecutionResult(
            success=bool(body.get("success")),
            stdout=str(body.get("stdout", "") or ""),
            stderr=str(body.get("stderr", "") or ""),
            result=body.get("result"),
            error=body.get("error"),
            images=images,
            tables=tables,
        )

    async def _download_images(
        self, session_id: str, body: dict, headers: dict[str, str]
    ) -> list[CodeImage]:
        names: list[str] = []
        for ro in body.get("rich_outputs", []) or []:
            if str(ro.get("mime_type", "")).startswith("image/") and ro.get("artifact"):
                names.append(str(ro["artifact"]))
        for artifact in body.get("artifacts", []) or []:
            name = artifact.get("name") if isinstance(artifact, dict) else artifact
            if name and str(name).lower().endswith(_IMAGE_EXTS):
                names.append(str(name))

        images: list[CodeImage] = []
        seen: set[str] = set()
        for name in names:
            if name in seen:
                continue
            seen.add(name)
            resp = await self._http.get(
                f"{self._base}/files/{session_id}/{name}", headers=headers
            )
            if resp.status_code == 200 and resp.content:
                images.append(
                    CodeImage(
                        filename=name,
                        content=resp.content,
                        content_type=resp.headers.get("content-type", "image/png"),
                    )
                )
        return images
