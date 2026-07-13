# mcp-server Specification

## Purpose

CyberArche's own FastMCP server: document and knowledge tools over the caller's accessible content, sharing the application use cases with HTTP.
## Requirements
### Requirement: FastMCP server surface
The system SHALL expose a FastMCP server that publishes tools operating over the
caller's own and shared documents, sharing the same application use cases and
composition root as the HTTP API.

#### Scenario: List available tools
- **WHEN** an authenticated MCP client connects
- **THEN** the server SHALL advertise the CyberArche document and knowledge tools

### Requirement: Document tools
The MCP server SHALL provide tools to search documents, read a document, create a
document, and edit a document. Editing SHALL support appending blocks, inserting
blocks after a given block, and replacing an existing block's content. Every
edit SHALL be applied through the document CRDT and SHALL enforce the caller's
edit permission.

#### Scenario: Search then read
- **WHEN** a client calls the search tool with a query
- **THEN** the server SHALL return matching documents the caller may access
- **AND** a subsequent read tool call SHALL return that document's content

#### Scenario: Append blocks through a tool
- **WHEN** a client calls the insert tool with no position
- **THEN** the blocks SHALL be appended to the end of the document
- **AND** the edit SHALL be visible to live collaborators

#### Scenario: Insert blocks at a position
- **WHEN** a client calls the insert tool with an `after_block_id`
- **THEN** the new blocks SHALL appear immediately after that block
- **AND** the remaining blocks SHALL keep their order

#### Scenario: Replace a block's content
- **WHEN** a client calls the replace tool with a block id and new content
- **THEN** that block's type and data SHALL be replaced
- **AND** other blocks SHALL be unchanged

#### Scenario: Editing without permission is refused
- **WHEN** a caller who may only view the document calls an edit tool
- **THEN** the server SHALL refuse the edit

### Requirement: Knowledge tools
The MCP server SHALL provide tools to ingest a file into the workspace knowledge
base and to run a RAG query, delegating to the rag-knowledge capability.

#### Scenario: RAG query tool
- **WHEN** a client calls the RAG query tool for a workspace it can access
- **THEN** the server SHALL return retrieved results from that workspace's RAG
  project

### Requirement: Authenticated and authorized tools
Every MCP tool call SHALL be authenticated with a CyberdyneAuth token or a
CyberArche personal API key, and SHALL enforce the caller's permissions;
tools SHALL never return content the caller is not authorized to access.

#### Scenario: Reject unauthorized read
- **WHEN** a client calls the read tool for a document it may not access
- **THEN** the server SHALL deny the call

#### Scenario: Tenant scoping on tools
- **WHEN** a client calls the search tool
- **THEN** results SHALL be limited to the caller's tenant and shared resources

#### Scenario: External MCP client with an API key
- **WHEN** an MCP client (e.g. Claude or ChatGPT) connects with a valid
  personal API key as its Bearer credential
- **THEN** the server SHALL serve tool calls as the key's owning user

#### Scenario: Revoked API key on tools
- **WHEN** an MCP client presents a revoked or expired API key
- **THEN** every tool call SHALL be rejected as unauthenticated

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

### Requirement: MCP workspace and teamspace discovery

The MCP server SHALL expose tools to list the caller's workspaces and to list a
workspace's teamspaces (those the caller may see), so a client can obtain the
ids required by the document and knowledge tools. Creating a document over MCP
SHALL accept an optional teamspace so a shared document can be placed in a
teamspace. These tools SHALL return only what the authenticated caller may
access.

#### Scenario: Discover a workspace and its teamspaces

- **WHEN** an authenticated client lists workspaces and then a workspace's
  teamspaces
- **THEN** it SHALL receive the workspaces the caller belongs to and that
  workspace's visible teamspaces

#### Scenario: Create a document in a teamspace over MCP

- **WHEN** a client creates a document with a teamspace id
- **THEN** the document SHALL be created in that teamspace

