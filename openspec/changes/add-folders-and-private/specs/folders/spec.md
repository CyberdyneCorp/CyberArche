# folders Specification

## ADDED Requirements

### Requirement: Folders group documents within a workspace
The system SHALL let an authorized user create a folder in a workspace, either
inside a teamspace or in their private space, and SHALL allow folders to nest.
A folder in a teamspace SHALL be visible to that teamspace's members; a private
folder SHALL be visible only to its creator.

#### Scenario: Create a folder in a teamspace
- **WHEN** a teamspace member creates a folder in that teamspace
- **THEN** the folder SHALL be listed for the teamspace's members

#### Scenario: Create a private folder
- **WHEN** a user creates a folder with no teamspace
- **THEN** the folder SHALL be visible only to that user

#### Scenario: Folders nest
- **WHEN** a folder is created inside another folder
- **THEN** it SHALL be listed as a child of that folder

### Requirement: Folder lifecycle
The system SHALL let an authorized user rename and delete a folder. Deleting a
folder SHALL NOT delete its documents: they SHALL be detached (their folder
reference cleared) rather than destroyed. Nested folders SHALL be removed with
their parent.

#### Scenario: Deleting a folder keeps its documents
- **GIVEN** a folder containing a document
- **WHEN** the folder is deleted
- **THEN** the document SHALL still exist
- **AND** it SHALL no longer reference the deleted folder

#### Scenario: Deleting a folder removes its sub-folders
- **GIVEN** a folder containing a sub-folder
- **WHEN** the parent folder is deleted
- **THEN** the sub-folder SHALL also be removed
