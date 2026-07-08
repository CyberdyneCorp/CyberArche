# auth-integration Specification

## ADDED Requirements

### Requirement: Personal API keys
The system SHALL let an authenticated user create named personal API keys,
list them (identified by a non-secret prefix), and revoke them. The full key
secret SHALL be shown exactly once, at creation, and SHALL be stored only as
a cryptographic hash.

#### Scenario: Create and show once
- **WHEN** a user creates an API key with a name
- **THEN** the system SHALL return the full secret exactly once
- **AND** subsequent listings SHALL expose only the name, prefix, creation
  time, and last-used time

#### Scenario: Secrets are hashed at rest
- **WHEN** an API key is persisted
- **THEN** the stored record SHALL contain a hash of the secret, never the
  secret itself

### Requirement: API keys authenticate as their owner
A valid API key presented as a Bearer credential SHALL authenticate the
request as the key's owning user, with exactly that user's tenant and
permissions, on every inbound surface (HTTP, realtime, MCP).

#### Scenario: MCP client connects with an API key
- **WHEN** an external MCP client presents a valid API key
- **THEN** tool calls SHALL execute with the owner's identity and be subject
  to the owner's permissions

#### Scenario: Key never escalates
- **WHEN** a request authenticates with an API key
- **THEN** it SHALL be denied anything the owning user could not do

### Requirement: API key lifecycle
Revoked or expired API keys SHALL be rejected immediately, and the system
SHALL record when each key was last used.

#### Scenario: Revoked key is rejected
- **WHEN** a request presents a key that has been revoked
- **THEN** the system SHALL reject it with an authentication error

#### Scenario: Expired key is rejected
- **WHEN** a request presents a key past its expiry
- **THEN** the system SHALL reject it with an authentication error
