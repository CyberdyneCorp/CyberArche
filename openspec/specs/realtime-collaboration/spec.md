# realtime-collaboration Specification

## Purpose

CRDT (Yjs) synchronization over the WebSocket relay: convergence, persistence, presence, offline merge, and authorized access.
## Requirements
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

### Requirement: Snapshot restores propagate to connected editors
A snapshot restore SHALL be applied as a CRDT update on the document, so that
every connected editor converges on the restored content without reloading.
The update SHALL be attributed to the restoring user.

#### Scenario: An open editor sees a restore
- **GIVEN** a user has the document open over the realtime connection
- **WHEN** another editor restores a prior snapshot
- **THEN** the open editor SHALL receive the restoring update
- **AND** SHALL converge on the snapshot's content

#### Scenario: Restores are attributed
- **WHEN** a restore is applied
- **THEN** the logged update's origin SHALL identify it as a restore by that user

### Requirement: Realtime sessions survive access-token expiry
Access tokens are short-lived. A realtime client SHALL obtain a current access
token for each connection attempt rather than reusing one captured when the
document was opened. When the server rejects the connection as unauthenticated,
the client SHALL refresh its token at most once and retry with the new one, and
SHALL NOT retry using a token the server has already rejected. When the server
rejects the connection as forbidden, the client SHALL NOT retry.

#### Scenario: An expired token is refreshed and the session continues
- **GIVEN** an editor whose access token expired while the document was open
- **WHEN** the realtime connection is refused as unauthenticated
- **THEN** the client SHALL refresh its token
- **AND** SHALL reconnect using the refreshed token

#### Scenario: A failed refresh ends the session
- **WHEN** the connection is refused as unauthenticated and the refresh fails
- **THEN** the client SHALL stop reconnecting
- **AND** SHALL surface the loss of access rather than retrying the dead token

#### Scenario: A forbidden document is not retried
- **WHEN** the connection is refused because the user has no role on the document
- **THEN** the client SHALL NOT attempt a refresh
- **AND** SHALL NOT reconnect

#### Scenario: A burst of rejections triggers one refresh
- **WHEN** several connection attempts are refused as unauthenticated at once
- **THEN** the client SHALL refresh exactly once

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

