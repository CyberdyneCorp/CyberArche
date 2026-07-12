# mcp-server Specification

## ADDED Requirements

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
