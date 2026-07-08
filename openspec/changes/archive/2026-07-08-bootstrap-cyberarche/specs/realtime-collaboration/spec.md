# realtime-collaboration Specification

## ADDED Requirements

### Requirement: CRDT document synchronization
The system SHALL synchronize document edits using a CRDT (Yjs), relaying binary
updates over a WebSocket connection so that concurrent edits from multiple
clients converge to the same state without conflicts.

#### Scenario: Two editors converge
- **WHEN** two connected clients edit different parts of a document concurrently
- **THEN** both edits SHALL be preserved
- **AND** both clients SHALL converge to the same final document state

#### Scenario: Late joiner catches up
- **WHEN** a client connects to a document that already has state
- **THEN** the server SHALL send the current state so the client renders the
  latest content

### Requirement: Server-side persistence of updates
The server SHALL persist the CRDT update stream and SHALL periodically compact it
into a snapshot, so a document can be fully reconstructed after a restart.

#### Scenario: Reconstruct after restart
- **WHEN** the realtime service restarts and a client reconnects
- **THEN** the server SHALL reconstruct the document from persisted
  updates/snapshots without data loss

### Requirement: Presence and live cursors
The system SHALL broadcast awareness state (each participant's identity,
selection, and cursor position) to other participants in the same document.

#### Scenario: Show collaborator cursor
- **WHEN** a collaborator moves their cursor or selection
- **THEN** other participants SHALL see that collaborator's cursor/selection
  labeled with their identity

#### Scenario: Presence cleared on disconnect
- **WHEN** a participant disconnects
- **THEN** their cursor and presence SHALL be removed for other participants

### Requirement: Offline editing and reconnection
A client SHALL allow local edits while disconnected and SHALL merge them into the
shared document upon reconnection.

#### Scenario: Merge offline edits
- **WHEN** a client edits while offline and later reconnects
- **THEN** the offline edits SHALL be merged conflict-free into the document

### Requirement: Authorized realtime access
The realtime connection SHALL be authenticated and authorized: a client SHALL
only join a document it is permitted to view, and SHALL only apply edits if it
has edit permission.

#### Scenario: Reject unauthorized editor
- **WHEN** a client with view-only permission attempts to send an update
- **THEN** the server SHALL reject the update and not broadcast it
