# document-model Specification

## MODIFIED Requirements

### Requirement: Soft delete and trash
Deleting a document SHALL move it to a trash state rather than erasing it, and
trashed documents SHALL be restorable until permanently purged. The system
SHALL allow permanently purging a trashed document, which SHALL remove the
document, its descendant documents, and everything they own (CRDT updates,
snapshots, comments, share links, grants, and favourites), and SHALL make them
unrestorable. Purging SHALL be permitted only for a document already in the
trash, and SHALL require the `editor` role.

#### Scenario: Trash then restore
- **WHEN** a user deletes a document
- **THEN** the document SHALL be marked trashed and hidden from normal listings
- **AND** the user SHALL be able to restore it to its previous parent

#### Scenario: Purge removes a trashed document permanently
- **GIVEN** a document in the trash
- **WHEN** an editor purges it
- **THEN** the document SHALL no longer appear in any listing, including the trash
- **AND** it SHALL NOT be restorable

#### Scenario: Purge cascades to the document's subtree and owned data
- **GIVEN** a trashed document with a child document, snapshots, and comments
- **WHEN** the document is purged
- **THEN** the child document SHALL also be removed
- **AND** the snapshots and comments SHALL be removed

#### Scenario: A live document cannot be purged
- **WHEN** an editor attempts to purge a document that is not in the trash
- **THEN** the system SHALL reject the request
- **AND** the document SHALL be unchanged

#### Scenario: Purge requires edit permission
- **WHEN** a user without the editor role attempts to purge a trashed document
- **THEN** the system SHALL reject the request
- **AND** the document SHALL remain in the trash
