# Agent web search and YouTube media tools

## Why

The document AI agent is grounded in the open document and the workspace RAG
knowledge, but it cannot reach the live internet. Users ask it to research a
topic, cite up-to-date sources, or pull in a talk they watched — and today it
can only answer from what is already in the workspace. Our sibling DAO backend
already exposes web search and YouTube (transcript + playlist) endpoints behind
CyberdyneAuth, so the capability exists; the agent just has no port to it.

CyberdyneAuth has no delegation/token-exchange grant, so we cannot mint a
service token on the caller's behalf. These are interactive, per-caller tools,
so — exactly as the Cyberflies meeting tools already do — we forward the
caller's own CyberdyneAuth bearer token to the DAO backend, which validates it
and returns only what that caller may access. No new shared secret is
introduced.

## What Changes

- Add three agent tools, gated (like the meeting tools) on the DAO base URL
  being configured AND a caller `access_token` being present:
  - `web_search(query, num?)` → DAO `GET /api/v1/search?q=&num=` — ranked
    web/internet results (title, url, snippet) the agent can cite and insert.
  - `youtube_transcript(video, lang?)` → DAO `GET /api/v1/youtube/transcript?video=&lang=`
    — a video's transcript (`video` = URL or 11-char id); the agent can
    summarize it into the open document or ingest it into the workspace RAG.
  - `youtube_playlist(playlist)` → DAO `GET /api/v1/youtube/playlist?playlist=`
    — list a playlist's videos.
- Expose `web_search` and `youtube_transcript` as MCP `@mcp.tool`s on the
  inbound FastMCP server; each resolves the caller and forwards the bearer.
- Add an outbound `WebMediaPort` and a `DaoBackendWebMediaAdapter`; wire the DAO
  base URL through `WiringConfig` and the composition root.

## Impact

- Affected specs: `ai-agent` (new web search + YouTube requirements),
  `mcp-server` (new MCP web search + YouTube transcript tools).
- Affected code:
  - New `application/ports/web_media.py` (outbound port, Protocol + DTOs).
  - New `adapters/outbound/web_media/dao_backend.py` (DAO HTTP adapter).
  - `application/use_cases/agent.py` — assemble the tools in `_available_tools()`
    and route them in `_dispatch()`, following the meetings gating pattern.
  - `adapters/inbound/mcp/server.py` — add the two MCP tools.
  - `adapters/wiring/__init__.py` + `WiringConfig` — DAO base URL and adapter
    construction (mirrors `_build_meetings`).
- Auth note: token-forwarding only. Tools are unavailable unless the DAO base
  URL is configured and the caller presented an `access_token`; the DAO backend
  is the authority on what results the forwarded token may see. The inbound →
  outbound import-linter contract holds (agent use case depends on the new port;
  only the adapter and wiring touch DAO HTTP).
