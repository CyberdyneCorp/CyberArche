# document-model Specification

## MODIFIED Requirements

### Requirement: Version snapshots
The system SHALL periodically persist an immutable snapshot of a document's
content (a materialized JSON of the block tree plus the CRDT state vector) and
SHALL allow listing and restoring snapshots. Restoring SHALL replace the
document's live content with the snapshot's content, SHALL apply that change
through the document CRDT so connected editors converge, and SHALL record a
new snapshot representing the restore. Restoring SHALL require the `editor`
role. Restoring SHALL preserve the identity of blocks that exist in both the
snapshot and the current document.

#### Scenario: Restore replaces the live document content
- **GIVEN** a snapshot taken when the document contained block `b1`
- **AND** the document has since been edited to contain only block `b2`
- **WHEN** an editor restores that snapshot
- **THEN** reading the document's blocks SHALL yield `b1`
- **AND** `b2` SHALL NOT be present

#### Scenario: Restore is applied through the CRDT
- **WHEN** an editor restores a snapshot
- **THEN** the restore SHALL be appended to the document's update log
- **AND** SHALL be broadcast to connected editors as an ordinary update

#### Scenario: Restore records a new snapshot
- **WHEN** an editor restores a snapshot
- **THEN** the system SHALL record a new snapshot whose `restored_from`
  identifies the snapshot that was restored

#### Scenario: Blocks surviving a restore keep their identity
- **GIVEN** a snapshot and the current document both contain block `b1`
- **WHEN** the snapshot is restored
- **THEN** `b1` SHALL retain its block id
- **AND** comments anchored to `b1` SHALL remain anchored

#### Scenario: Restoring the same snapshot twice is idempotent
- **GIVEN** a document that was just restored to a snapshot
- **WHEN** the same snapshot is restored again
- **THEN** the document's blocks SHALL be unchanged
- **AND** the system SHALL NOT append an empty update to the update log

#### Scenario: A commenter may not restore
- **WHEN** a user whose effective role is `commenter` attempts a restore
- **THEN** the system SHALL reject the request
- **AND** the document content SHALL be unchanged

#### Scenario: Restoring an unknown snapshot fails
- **WHEN** an editor restores a snapshot id that does not belong to the document
- **THEN** the system SHALL report that the snapshot was not found
