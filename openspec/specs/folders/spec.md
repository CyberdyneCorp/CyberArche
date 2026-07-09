# folders Specification

## Purpose
TBD - created by archiving change add-folders-and-private. Update Purpose after archive.
## Requirements
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

### Requirement: Reorganize documents by drag and drop
The sidebar SHALL let a user drag a document onto a teamspace, a folder, or the
private space to move it there. Dropping onto a folder SHALL place the document
in that folder; dropping onto a teamspace SHALL move it to that teamspace with no
folder; dropping onto the private space SHALL make it private.

#### Scenario: Drag a document onto a teamspace
- **GIVEN** a private document in the sidebar
- **WHEN** the user drags it onto a teamspace row
- **THEN** the document SHALL be listed under that teamspace

#### Scenario: Drag a document onto a folder
- **WHEN** the user drags a document onto a folder row
- **THEN** the document SHALL be listed under that folder

### Requirement: Row actions on teamspace and folder documents
The sidebar SHALL offer star, add-child, and trash actions on documents that live
inside a teamspace or a folder, not only on private documents.

#### Scenario: Star a teamspace document from the sidebar
- **GIVEN** a document listed under a teamspace
- **WHEN** the user stars it from its sidebar row
- **THEN** the document SHALL appear in the user's favourites

#### Scenario: Trash a teamspace document from the sidebar
- **GIVEN** a document listed under a teamspace
- **WHEN** the user trashes it from its sidebar row
- **THEN** the document SHALL no longer be listed under that teamspace

