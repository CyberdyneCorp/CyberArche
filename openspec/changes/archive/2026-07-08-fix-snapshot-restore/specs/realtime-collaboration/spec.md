# realtime-collaboration Specification

## ADDED Requirements

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
