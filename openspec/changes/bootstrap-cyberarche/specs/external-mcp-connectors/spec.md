# external-mcp-connectors Specification

## ADDED Requirements

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
connector is enabled, and a user SHALL be able to enable/disable a connector.

#### Scenario: Disable a connector
- **WHEN** a user disables a connector
- **THEN** its tools SHALL not be offered to the agent in subsequent sessions
