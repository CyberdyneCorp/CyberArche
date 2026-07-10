"""CodeExecutionPort adapter for the Cyberdyne Python Interpreter.

Flow (see the service OpenAPI): POST /sessions to get a workspace, POST /execute
to run code, then GET /files/{session_id}/{name} to download any figure the run
produced. Matplotlib under the headless Agg backend writes nothing on show(), so
we append a savefig epilogue when the code plots but does not save — mirroring
the interpreter's own auto-capture. Authenticated with a CyberdyneAuth bearer
from the shared service-token source (same seam as the RAG adapter).
"""

from __future__ import annotations

import textwrap
from collections.abc import Awaitable, Callable

import httpx

from cyberarche.application.ports.code_exec import CodeExecutionResult, CodeImage

TokenSource = Callable[[], Awaitable[str]]

_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")
_TEXT_MIME_PREFIXES = ("text/", "application/json")

# NOTE: RestrictedPython (the interpreter's default `restricted` layer) rejects
# leading-underscore identifiers, so the capture variables use a `cyb_` prefix
# (never `_plt`/`_fig`), and iterate by index rather than the iterator protocol.
_CAPTURE_EPILOGUE = textwrap.dedent(
    """
    try:
        import matplotlib.pyplot as cyb_plt
        cyb_fignums = cyb_plt.get_fignums()
        for cyb_idx in range(len(cyb_fignums)):
            cyb_plt.figure(cyb_fignums[cyb_idx]).savefig("figure_%d.png" % (cyb_idx + 1))
    except Exception:
        pass
    """
)


def _with_figure_capture(code: str) -> str:
    """Append a savefig epilogue for matplotlib code that doesn't save itself."""
    lowered = code.lower()
    plots = "matplotlib" in lowered or "pyplot" in lowered or "plt." in lowered
    if not plots or "savefig" in lowered:
        return code
    return f"{code}\n{_CAPTURE_EPILOGUE}"


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
                "code": _with_figure_capture(code),
                "session_id": session_id,
                "restricted": True,
            },
            headers=headers,
        )
        exec_resp.raise_for_status()
        body = exec_resp.json()

        images = await self._download_images(session_id, body, headers)
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
