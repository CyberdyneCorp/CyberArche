# Design — Agent web search and YouTube media tools

## Context

The DAO backend (`https://dao.backend.coolify.cyberdynecorp.ai`) exposes, behind
CyberdyneAuth Bearer auth:

- `GET /api/v1/search?q=<query>&num=<n>` — web/internet search; ranked results
  with title, url, snippet.
- `GET /api/v1/youtube/transcript?video=<url-or-id>&lang=<code>` — a video's
  transcript.
- `GET /api/v1/youtube/playlist?playlist=<url-or-id>` — a playlist's videos.

Both CyberArche and the DAO backend trust the same CyberdyneAuth issuer and both
authenticate with HTTP Bearer. The document agent already receives a per-caller
`access_token` (threaded for the Cyberflies meeting tools). This change reuses
that thread rather than inventing a new mechanism.

## Decision 1 — Token forwarding, not a service token

CyberdyneAuth has **no delegation / token-exchange grant**, so CyberArche cannot
mint a downstream token that represents the caller. These tools are interactive
and strictly per-caller, so we forward the caller's own CyberdyneAuth bearer
token to the DAO backend on every call. The DAO backend validates the token and
scopes results to what that caller may access — CyberArche performs no extra
authorization of its own and stores no DAO credential.

Consequences:

- The tools are only assembled for a call when BOTH the DAO base URL is
  configured AND a caller `access_token` is present — identical to the meeting
  tools' gate (`self._meetings is not None and access_token`). Background/worker
  runs without a caller token simply do not get these tools.
- No new shared secret and no `WiringConfig` service-token field for the DAO.
- This deliberately differs from RAG / code-exec, which use a service token
  because they act on workspace-owned (not per-caller) resources.

## Decision 2 — New outbound port + adapter (hexagonal)

Add `application/ports/web_media.py`: a `WebMediaPort` Protocol plus frozen DTOs,
mirroring `ports/meetings.py`. Every method takes `access_token: str` as its
first argument (the delegation credential) and returns provider-agnostic DTOs so
use cases never see DAO HTTP shapes.

Sketch:

```
@dataclass(frozen=True, slots=True)
class SearchResult:      # one ranked web result
    title: str
    url: str
    snippet: str | None

@dataclass(frozen=True, slots=True)
class Transcript:        # one video's transcript
    video_id: str
    title: str | None
    lang: str | None
    text: str

@dataclass(frozen=True, slots=True)
class PlaylistVideo:
    video_id: str
    title: str | None
    url: str

class WebMediaPort(Protocol):
    async def search(self, access_token: str, query: str, *, num: int = 10) -> list[SearchResult]: ...
    async def youtube_transcript(self, access_token: str, video: str, *, lang: str | None = None) -> Transcript: ...
    async def youtube_playlist(self, access_token: str, playlist: str) -> list[PlaylistVideo]: ...
```

Adapter `adapters/outbound/web_media/dao_backend.py`
(`DaoBackendWebMediaAdapter`) holds the DAO base URL and a shared
`httpx.AsyncClient`. Each call issues the GET with
`Authorization: Bearer <access_token>` and maps the JSON to DTOs. This mirrors
`CyberfliesMeetingsAdapter`. The inbound layer never imports it; only the agent
use case (through the port) and the composition root reference it, preserving the
import-linter `inbound !-> outbound` contract.

## Decision 3 — Wiring & config

Add `dao_base_url: str = ""` to `WiringConfig`. Add `_build_web_media(config,
shared_http)` returning `None` when the URL is empty (mirrors
`_build_meetings`), and thread the resulting `WebMediaPort | None` into the
agent use case in `adapters/wiring/__init__.py`. No service token is created.

## Decision 4 — Agent tool assembly, routing, rendering

In `agent.py`, mirror the meetings pattern:

- `_available_tools(...)` appends `_web_media_tool_specs()` only when
  `self._web_media is not None and access_token`.
- `_dispatch(...)` routes the three tool names to `_run_web_media_tool(call,
  access_token)`.
- Tool result strings are rendered compactly for the LLM: search → a numbered
  list of `title — url` with snippet; transcript → the text (with a title/lang
  header); playlist → a numbered list of `title — url`.
- Tool descriptions tell the agent it may cite/insert search results, and may
  either summarize a transcript into the open document or ingest it into the
  workspace RAG.

## Decision 5 — Transcript → RAG flow (optional)

`youtube_transcript` only *returns* the transcript text; it does not itself write
to RAG. When the caller asks to "add this to the knowledge base", the agent
chains the returned transcript into the existing RAG ingestion path (the same
one used for file ingestion), so ingestion permission and workspace scoping are
enforced exactly as for any other document. Summarizing-into-the-document uses
the agent's normal CRDT edit path. No new ingestion surface is added here.

## Decision 6 — MCP tools

`adapters/inbound/mcp/server.py` gains `web_search(query, num=10)` and
`youtube_transcript(video, lang=None)` as `@mcp.tool`s. Each calls `resolve()`
to authenticate, obtains the raw bearer via the existing header path, and
forwards it to `WebMediaPort`. `youtube_playlist` is agent-only for now
(transcript is the ingest-worthy surface over MCP). Tools appear only when the
container has a configured `WebMediaPort`; otherwise they are not registered.

## Decision 7 — Error handling

The adapter raises on transport/auth failure and maps HTTP status, mirroring the
meetings adapter's `_meetings_error`:

- DAO base URL not configured OR no caller token → the tool is not offered at
  all; if somehow invoked, it returns `error: web/media tools are not
  configured` / `error: sign in required`.
- DAO returns 401/403 → `error: not signed in to the web/media service, or no
  access to it` (the forwarded token was rejected — expected for expired
  tokens).
- DAO returns 404 (unknown/private video or playlist) → `error: that video or
  playlist was not found`.
- Transport error / 5xx → a graceful `error: web/media service unavailable`.

In every failure case the agent reports gracefully and continues the turn rather
than aborting the run — matching how meeting-tool failures are surfaced.
