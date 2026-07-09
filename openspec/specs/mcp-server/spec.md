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

