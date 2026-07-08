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
