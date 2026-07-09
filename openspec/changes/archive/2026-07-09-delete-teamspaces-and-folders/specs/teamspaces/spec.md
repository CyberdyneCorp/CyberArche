# teamspaces Specification

## ADDED Requirements
### Requirement: Delete a teamspace
The system SHALL let a teamspace owner delete a teamspace. Deleting a teamspace
SHALL move every document in it — including documents grouped under its folders —
to Trash, where they remain recoverable, and SHALL remove the teamspace's
folders. A user who is not an owner of the teamspace SHALL NOT be able to delete
it.

#### Scenario: Owner deletes a teamspace
- **GIVEN** a teamspace with documents, some grouped in folders
- **WHEN** an owner deletes the teamspace
- **THEN** the teamspace SHALL no longer be listed
- **AND** its documents SHALL be moved to Trash
- **AND** its folders SHALL be removed

#### Scenario: A trashed document from a deleted teamspace can be restored
- **GIVEN** a teamspace was deleted and its documents moved to Trash
- **WHEN** the owner restores one of those documents
- **THEN** the document SHALL exist again outside the trash

#### Scenario: A non-owner cannot delete a teamspace
- **WHEN** a member who is not an owner attempts to delete the teamspace
- **THEN** the request SHALL be refused
- **AND** the teamspace SHALL still be listed
