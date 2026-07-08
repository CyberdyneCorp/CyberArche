# mcp-server Specification

## MODIFIED Requirements

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
