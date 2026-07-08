# block-editor Specification

## MODIFIED Requirements

### Requirement: Block editing with slash menu
The editor SHALL let a user insert, edit, move, split, merge, and delete blocks,
and SHALL provide a slash (`/`) command menu to insert any supported block type
at the cursor. Deleting a block SHALL be reachable from the block's controls,
not only by emptying it.

#### Scenario: Insert a block via slash menu
- **WHEN** a user types `/` and selects a block type
- **THEN** the editor SHALL insert a block of that type at the cursor
- **AND** the change SHALL be applied to the document CRDT

#### Scenario: Split a paragraph on Enter
- **WHEN** a user presses Enter in the middle of a paragraph block
- **THEN** the editor SHALL split it into two blocks preserving both fragments

#### Scenario: Delete a block from its controls
- **WHEN** a user activates the delete control on a block
- **THEN** the block SHALL be removed from the document
- **AND** the deletion SHALL be undoable
