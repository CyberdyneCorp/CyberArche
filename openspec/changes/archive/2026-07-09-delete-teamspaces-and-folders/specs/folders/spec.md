# folders Specification

## MODIFIED Requirements
### Requirement: Folder lifecycle
The system SHALL let an authorized user rename and delete a folder. Deleting a
folder SHALL move the folder's documents — across the folder and its
sub-folders — to Trash, where they remain recoverable rather than being purged.
Nested folders SHALL be removed with their parent.

#### Scenario: Deleting a folder moves its documents to Trash
- **GIVEN** a folder containing a document
- **WHEN** the folder is deleted
- **THEN** the document SHALL be moved to Trash
- **AND** the document SHALL still exist and be restorable

#### Scenario: Deleting a folder removes its sub-folders
- **GIVEN** a folder containing a sub-folder
- **WHEN** the parent folder is deleted
- **THEN** the sub-folder SHALL also be removed
- **AND** documents in the sub-folder SHALL be moved to Trash
