# document-model Specification

## Purpose

Workspaces, the document tree, the typed block model, and version snapshots — the structural core every other capability builds on.
## Requirements
### Requirement: Workspace container
The system SHALL organize documents inside workspaces, and each workspace SHALL
belong to exactly one tenant (organization) derived from the caller's verified
token claims.

#### Scenario: Create a workspace
- **WHEN** an authenticated user creates a workspace with a name
- **THEN** the system SHALL create the workspace owned by the user's tenant
- **AND** the creator SHALL be granted the `owner` role on the workspace

#### Scenario: Workspaces are tenant-isolated
- **WHEN** a user lists workspaces
- **THEN** the system SHALL return only workspaces belonging to the caller's tenant

### Requirement: Document as a tree of documents
The system SHALL model a document with a stable `document_id`, a title, an owner,
a parent (workspace or another document), and an ordered list of child documents,
so documents form a navigable hierarchy.

#### Scenario: Nest a document under a parent
- **WHEN** a user creates a document with a parent document
- **THEN** the child SHALL appear in the parent's ordered children
- **AND** the child SHALL inherit the parent's workspace

#### Scenario: Reorder children
- **WHEN** a user moves a child document to a new position among its siblings
- **THEN** the system SHALL persist the new ordering

### Requirement: Block tree content
A document's body SHALL be an ordered tree of typed blocks. Each block SHALL have
a stable `block_id`, a `type`, type-specific `data`, and an ordered list of child
blocks. The canonical block content SHALL be stored as a CRDT document.

#### Scenario: Supported block types
- **WHEN** a block is created
- **THEN** its `type` SHALL be one of: `paragraph`, `heading`, `bulleted_list`,
  `numbered_list`, `todo`, `callout`, `quote`, `divider`, `code`, `table`,
  `latex`, `mermaid`, `whiteboard`, `image`, `file`, `embed`, `ai_block`

#### Scenario: Reject unknown block type
- **WHEN** a block is created with a `type` outside the supported set
- **THEN** the system SHALL reject it with a validation error

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

### Requirement: Documents may belong to a teamspace
A document SHALL optionally reference a teamspace it belongs to, and SHALL
optionally reference a folder that groups it. A document with no teamspace is
private to its creator. Placing a document in a folder SHALL set the document's
teamspace to the folder's, so its access follows the container; moving a document
directly to a teamspace SHALL set its teamspace and clear any folder reference;
removing it to the private space SHALL clear its teamspace. Listing a workspace
SHALL surface a teamspace's documents to that teamspace's members, and a private
document only to its creator.

#### Scenario: A workspace lists teamspace documents to members
- **WHEN** a member lists a teamspace's documents
- **THEN** the documents belonging to that teamspace SHALL be returned

#### Scenario: Private documents are listed only to their creator
- **WHEN** a user lists their private documents
- **THEN** only their own teamspace-less documents SHALL be returned

#### Scenario: Placing a document in a folder adopts the folder's scope
- **WHEN** a document is placed in a folder that belongs to a teamspace
- **THEN** the document SHALL belong to that teamspace

#### Scenario: Moving a document directly to a teamspace clears its folder
- **GIVEN** a document that lives in a folder
- **WHEN** an editor moves the document to a teamspace
- **THEN** the document SHALL belong to that teamspace
- **AND** the document SHALL no longer reference any folder

#### Scenario: Moving a foldered document to the private space clears its teamspace
- **GIVEN** a document that lives in a folder within a teamspace
- **WHEN** the document is moved to the private space
- **THEN** the document SHALL have no teamspace and no folder
- **AND** it SHALL be listed only to its creator

