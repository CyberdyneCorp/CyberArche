# mcp-server Specification

## ADDED Requirements

### Requirement: FastMCP server surface
The system SHALL expose a FastMCP server that publishes tools operating over the
caller's own and shared documents, sharing the same application use cases and
composition root as the HTTP API.

#### Scenario: List available tools
- **WHEN** an authenticated MCP client connects
- **THEN** the server SHALL advertise the CyberArche document and knowledge tools

### Requirement: Document tools
The MCP server SHALL provide tools to search documents, read a document, create a
document, and edit a document (append/insert/replace blocks).

#### Scenario: Search then read
- **WHEN** a client calls the search tool with a query
- **THEN** the server SHALL return matching documents the caller may access
- **AND** a subsequent read tool call SHALL return that document's content

#### Scenario: Edit through a tool
- **WHEN** a client calls the edit tool to insert a block
- **THEN** the edit SHALL be applied through the document CRDT and visible to
  live collaborators

### Requirement: Knowledge tools
The MCP server SHALL provide tools to ingest a file into the workspace knowledge
base and to run a RAG query, delegating to the rag-knowledge capability.

#### Scenario: RAG query tool
- **WHEN** a client calls the RAG query tool for a workspace it can access
- **THEN** the server SHALL return retrieved results from that workspace's RAG
  project

### Requirement: Authenticated and authorized tools
Every MCP tool call SHALL be authenticated with a CyberdyneAuth token and SHALL
enforce the caller's permissions; tools SHALL never return content the caller is
not authorized to access.

#### Scenario: Reject unauthorized read
- **WHEN** a client calls the read tool for a document it may not access
- **THEN** the server SHALL deny the call

#### Scenario: Tenant scoping on tools
- **WHEN** a client calls the search tool
- **THEN** results SHALL be limited to the caller's tenant and shared resources
