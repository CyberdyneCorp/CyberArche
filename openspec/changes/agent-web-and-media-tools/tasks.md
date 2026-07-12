# Tasks

## 1. Outbound port and adapter

- [ ] 1.1 Add `application/ports/web_media.py`: `WebMediaPort` Protocol +
  frozen DTOs (`SearchResult`, `Transcript`, `PlaylistVideo`); every method
  takes the caller `access_token` as its delegation credential.
- [ ] 1.2 Add `adapters/outbound/web_media/dao_backend.py`
  (`DaoBackendWebMediaAdapter`) calling DAO `GET /api/v1/search`,
  `/api/v1/youtube/transcript`, `/api/v1/youtube/playlist` with
  `Authorization: Bearer <access_token>`; map JSON → DTOs; map HTTP
  401/403/404/5xx to clear errors.

## 2. Wiring and config

- [ ] 2.1 Add `dao_base_url: str = ""` to `WiringConfig`.
- [ ] 2.2 Add `_build_web_media(config, shared_http)` returning `None` when the
  URL is empty (mirrors `_build_meetings`); no service token.
- [ ] 2.3 Thread the `WebMediaPort | None` into the agent use case and expose it
  on the container for the MCP server.

## 3. Agent tools

- [ ] 3.1 Add `_web_media_tool_specs()`: `web_search(query, num?)`,
  `youtube_transcript(video, lang?)`, `youtube_playlist(playlist)` with
  descriptions that tell the agent it may cite/insert search results and may
  summarize a transcript into the document or ingest it into the workspace RAG.
- [ ] 3.2 Assemble the tools in `_available_tools()` only when
  `self._web_media is not None and access_token` (meetings gate pattern).
- [ ] 3.3 Route the three tool names in `_dispatch()` to
  `_run_web_media_tool(call, access_token)`; render compact result strings.

## 4. MCP tools

- [ ] 4.1 Add `web_search` and `youtube_transcript` `@mcp.tool`s in
  `adapters/inbound/mcp/server.py`; each resolves the caller and forwards the
  raw bearer to `WebMediaPort`; register only when a `WebMediaPort` is configured.

## 5. Delegated-auth gating

- [ ] 5.1 Confirm the tools are absent when the DAO base URL is unset OR no
  caller `access_token` is present; invoking a mis-offered tool returns a
  graceful `error: … not configured / sign in required`.
- [ ] 5.2 Confirm no new shared secret / service token is introduced; the caller
  token is the only credential sent to the DAO.

## 6. Tests

- [ ] 6.1 Application: fake `WebMediaPort`; the three tools appear only when
  configured + token present, and are routed/rendered correctly.
- [ ] 6.2 Adapter: DAO responses map to DTOs; 401/403/404/5xx map to the graceful
  error strings; the forwarded `Authorization: Bearer` header is asserted.
- [ ] 6.3 MCP: `web_search` and `youtube_transcript` resolve the caller and
  forward the bearer; unauthenticated calls raise `NotAuthenticated`.
- [ ] 6.4 Regression: transcript result can be summarized into the document and
  ingested into RAG via the existing paths.

## 7. Spec and docs

- [ ] 7.1 `openspec validate agent-web-and-media-tools --strict` passes.
- [ ] 7.2 Update `project.md` / docs external-services list with the DAO backend
  and the token-forwarding auth note; backend lint/type/tests green.
