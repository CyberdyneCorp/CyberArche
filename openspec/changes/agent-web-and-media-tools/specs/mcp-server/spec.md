# mcp-server Specification

## ADDED Requirements

### Requirement: MCP web search and YouTube transcript tools

The MCP server SHALL expose a `web_search` tool and a `youtube_transcript` tool
backed by the DAO backend. Each tool SHALL resolve the authenticated caller and
forward the caller's CyberdyneAuth bearer token to the DAO backend, so results
are scoped to what that caller may access; the system SHALL NOT substitute a
delegation or service token. The tools SHALL be registered only when the DAO
backend is configured, and unauthenticated calls SHALL be rejected.

#### Scenario: Web search over MCP forwards the caller's token

- **GIVEN** an authenticated MCP client and a configured DAO backend
- **WHEN** the client calls `web_search` with a query
- **THEN** the server SHALL forward the caller's bearer token to the DAO backend
- **AND** SHALL return ranked results (title, url, snippet) the caller may access

#### Scenario: YouTube transcript over MCP

- **WHEN** an authenticated client calls `youtube_transcript` with a video URL or id
- **THEN** the server SHALL return that video's transcript, forwarding the caller's
  bearer token

#### Scenario: Unauthenticated call is rejected

- **GIVEN** a request without a valid bearer token
- **WHEN** `web_search` or `youtube_transcript` is invoked
- **THEN** the server SHALL reject the call as not authenticated
