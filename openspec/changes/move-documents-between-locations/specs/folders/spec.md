# folders Specification

## ADDED Requirements
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
