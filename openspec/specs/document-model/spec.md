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
content, and SHALL allow listing, naming (an optional label), restoring, and
**diffing** snapshots. Restoring SHALL replace the current content and is itself
recorded as a new snapshot. A diff SHALL report the block-level changes between
two snapshots, or between a snapshot and the current document state. All
operations SHALL be access-scoped to callers who may view (list/diff) or edit
(restore) the document.

#### Scenario: Name a version

- **WHEN** a snapshot is recorded or renamed with a label
- **THEN** the label SHALL be stored and returned when listing versions

#### Scenario: Diff two versions

- **GIVEN** two snapshots of a document
- **WHEN** a caller requests a diff between them
- **THEN** the system SHALL return the blocks added, removed, and modified
  between them

#### Scenario: Diff a version against the current document

- **WHEN** a caller diffs a snapshot with no second snapshot given
- **THEN** the system SHALL compare it against the document's current content

#### Scenario: Restore records a new snapshot

- **GIVEN** a prior snapshot
- **WHEN** an editor restores it
- **THEN** the current content SHALL be replaced and a new snapshot SHALL record
  the restore

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

### Requirement: Database block

The system SHALL provide a `database` block that holds a schema of typed
properties and rows of records. A property SHALL have a name and a type that is
one of: text, number, select (with named options), checkbox, or date. A row
SHALL hold a value per property. The database's content SHALL persist in the
document so reopening restores it, and SHALL merge concurrent edits to different
rows.

#### Scenario: Create and edit a database

- **WHEN** a user inserts a `database` block, adds columns and rows, and edits
  cells
- **THEN** the schema and row values SHALL persist as part of the document
- **AND** reopening the document SHALL restore them

### Requirement: Database table and board views

The `database` block SHALL offer a table view and a board view. The table view
SHALL let the user add and remove rows and columns, rename a column, change its
type, edit cells with a type-appropriate editor, and sort by a column. The board
view SHALL group rows by a chosen select property into a column per option, let
the user move a row between groups (changing that property's value), and add a
row to a group.

#### Scenario: Group rows on a board

- **GIVEN** a database with a select property
- **WHEN** the user switches to the board view grouped by that property
- **THEN** rows SHALL appear as cards in the column matching their value
- **AND** moving a card to another column SHALL set that property's value

#### Scenario: Sort a table

- **WHEN** the user sorts the table by a column
- **THEN** the rows SHALL be ordered by that column's values

### Requirement: Database filters

The `database` block SHALL let the user filter rows by conditions on properties,
with type-appropriate operators (e.g. text contains/is, number comparisons,
select is/is-not, checkbox checked/unchecked, date before/after, and is-empty).
Multiple filters SHALL combine with AND and SHALL apply to both the table and
board views. Filters SHALL persist in the document.

#### Scenario: Filter rows

- **WHEN** the user adds a filter (e.g. Status is Done)
- **THEN** only rows matching every active filter SHALL be shown in both views

#### Scenario: Filters persist

- **WHEN** filters are set and the document is reopened
- **THEN** the same filters SHALL still apply

### Requirement: Calendar and gallery views, and rows as pages

The `database` block SHALL additionally offer a calendar view (rows placed on a
month grid by a chosen date property, with month navigation and adding a row on
a day) and a gallery view (rows as cards). Each row SHALL be openable as a page:
opening a row that has no page yet SHALL create a document for it and link it to
the row; opening SHALL navigate to that document.

#### Scenario: Place rows on a calendar

- **GIVEN** a database with a date property
- **WHEN** the user switches to the calendar view
- **THEN** each row SHALL appear on the day matching its date

#### Scenario: Open a row as a page

- **WHEN** the user opens a row as a page for the first time
- **THEN** a document SHALL be created and linked to that row
- **AND** the document SHALL open
- **AND** opening the same row again SHALL reopen that document

### Requirement: Document breadcrumb path

The system SHALL provide the ancestor path of a document as an ordered list of
crumbs so the client can show where the document lives and let the user navigate
upward. The path SHALL begin with the document's workspace, then its teamspace
when it belongs to one, then its folders from the outermost to the innermost when
it is filed in a folder, then its ancestor documents from the topmost ancestor
down to its immediate parent, and finally the document itself. Each crumb SHALL
carry a kind (workspace, teamspace, folder, or document), an id, and a label.
Requesting the path SHALL require view access to the document and be scoped to
the caller's tenant.

#### Scenario: Path of a nested document

- **GIVEN** a document filed in a folder within a teamspace and nested under a
  parent document
- **WHEN** its path is requested by a member with view access
- **THEN** the crumbs SHALL be ordered workspace, teamspace, folder(s), ancestor
  document(s), then the document, each with its label

#### Scenario: Path of a root document

- **GIVEN** a document at the workspace root with no teamspace or folder
- **WHEN** its path is requested
- **THEN** the crumbs SHALL be the workspace followed by the document

#### Scenario: Access required

- **WHEN** a caller without view access requests a document's path
- **THEN** the system SHALL refuse the request

