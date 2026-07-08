# realtime-collaboration Specification

## ADDED Requirements

### Requirement: Refused realtime connections carry a reason
When the system refuses a realtime connection it SHALL deliver an application
close code identifying the reason — unauthenticated, forbidden, or unknown
document — rather than denying the handshake without a code. The system SHALL
NOT send any document state on a refused connection.

#### Scenario: An unauthenticated connection is refused with a readable code
- **WHEN** a client connects with a missing, malformed, or expired token
- **THEN** the client SHALL receive close code 4401
- **AND** SHALL NOT receive any document state

#### Scenario: A forbidden document is refused with a readable code
- **WHEN** an authenticated client connects to a document it may not view
- **THEN** the client SHALL receive close code 4403

#### Scenario: An unknown document is refused with a readable code
- **WHEN** a client connects to a document that does not exist
- **THEN** the client SHALL receive close code 4404
