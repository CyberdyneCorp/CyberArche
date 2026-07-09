# external-mcp-connectors Specification

## Purpose

User-attached external MCP servers: registration, encrypted credentials, namespaced tools, and per-session control.
## Requirements
### Requirement: Register external MCP servers
The system SHALL let an authorized user register an external MCP server for a
workspace or document by providing its transport endpoint and credentials, so the
agent can use that server's tools.

#### Scenario: Add an external MCP server
- **WHEN** a user registers an external MCP server with a valid endpoint
- **THEN** the system SHALL store the connector configuration for the scope
- **AND** the server's tools SHALL become available to the agent in that scope

#### Scenario: Reject unreachable server
- **WHEN** a user registers an endpoint that fails connection/handshake
- **THEN** the system SHALL reject the registration with a clear error

### Requirement: Secure credential storage
Credentials for external MCP servers SHALL be stored encrypted at rest and SHALL
NOT be returned in plaintext after creation.

#### Scenario: Credentials not readable
- **WHEN** a user views a registered connector
- **THEN** the system SHALL show its metadata but SHALL NOT reveal stored secrets

### Requirement: Namespaced tool exposure
Tools from external MCP servers SHALL be namespaced to their connector so they do
not collide with CyberArche's own tools, and the agent SHALL see the origin of
each tool.

#### Scenario: Namespaced tool name
- **WHEN** two connectors expose a tool with the same name
- **THEN** the agent SHALL address each via its connector-qualified name

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

