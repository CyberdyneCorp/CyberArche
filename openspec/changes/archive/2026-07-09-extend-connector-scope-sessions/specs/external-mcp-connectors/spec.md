# external-mcp-connectors Specification

## MODIFIED Requirements

### Requirement: Register external MCP servers
The system SHALL let an authorized user register an external MCP server for a
workspace or for a specific document by providing its transport endpoint and
credentials, so the agent can use that server's tools. A workspace-scoped
connector SHALL be available to the agent on every document in the workspace; a
document-scoped connector SHALL be available only when the agent is working on
that document.

#### Scenario: Add a workspace-scoped external MCP server
- **WHEN** a user registers an external MCP server with a valid endpoint and no document
- **THEN** the system SHALL store the connector for the workspace
- **AND** its tools SHALL be available to the agent on any document in the workspace

#### Scenario: Add a document-scoped external MCP server
- **WHEN** a user registers a connector for a specific document
- **THEN** its tools SHALL be available to the agent on that document
- **AND** SHALL NOT be available on other documents in the workspace

#### Scenario: Reject unreachable server
- **WHEN** a user registers an endpoint that fails connection/handshake
- **THEN** the system SHALL reject the registration with a clear error

## MODIFIED Requirements

### Requirement: Per-session opt-in and control
An external MCP server's tools SHALL only be used within sessions where the
connector is enabled. A user SHALL be able to enable or disable a connector
globally, and a session SHALL be able to restrict itself to a chosen subset of
the enabled connectors. A globally disabled connector SHALL never be used.

#### Scenario: Disable a connector globally
- **WHEN** a user disables a connector
- **THEN** its tools SHALL not be offered to the agent in any session

#### Scenario: A session restricts itself to chosen connectors
- **GIVEN** two enabled connectors A and B
- **WHEN** a session opts in to only A
- **THEN** the agent SHALL be offered A's tools
- **AND** SHALL NOT be offered B's tools

#### Scenario: No session restriction offers all enabled connectors
- **WHEN** a session places no restriction
- **THEN** the agent SHALL be offered the tools of every enabled connector
