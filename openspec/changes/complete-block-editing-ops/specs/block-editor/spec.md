# block-editor Specification

## MODIFIED Requirements

### Requirement: Block editing with slash menu
The editor SHALL let a user insert, edit, move, split, merge, and delete blocks,
and SHALL provide a slash (`/`) command menu to insert any supported block type
at the cursor. Deleting a block SHALL be reachable from the block's controls,
not only by emptying it. Pressing Backspace at the start of a non-empty block
SHALL merge it into the previous block, joining their text.

#### Scenario: Insert a block via slash menu
- **WHEN** a user types `/` and selects a block type
- **THEN** the editor SHALL insert a block of that type at the cursor
- **AND** the change SHALL be applied to the document CRDT

#### Scenario: Split a paragraph on Enter
- **WHEN** a user presses Enter in the middle of a paragraph block
- **THEN** the editor SHALL split it into two blocks preserving both fragments

#### Scenario: Merge into the previous block on Backspace
- **WHEN** a user presses Backspace at the start of a non-empty block
- **THEN** the block's text SHALL be appended to the previous block
- **AND** the now-empty block SHALL be removed
- **AND** the merge SHALL be undoable as a single step

#### Scenario: Delete a block from its controls
- **WHEN** a user activates the delete control on a block
- **THEN** the block SHALL be removed from the document

### Requirement: LaTeX math blocks
The editor SHALL support LaTeX for both inline math (delimited by `$…$` within
text) and block-level math (the `latex` block), rendering both via KaTeX. It
SHALL preserve the raw source for editing and show a non-destructive error on
invalid LaTeX.

#### Scenario: Render a block equation
- **WHEN** a user enters a valid LaTeX expression in a `latex` block
- **THEN** the editor SHALL render the typeset equation
- **AND** SHALL preserve the raw LaTeX source for editing

#### Scenario: Render inline math within text
- **WHEN** a paragraph contains a `$…$` fragment and is not being edited
- **THEN** the editor SHALL render that fragment as typeset inline math
- **AND** SHALL restore the raw `$…$` source when the paragraph is focused

#### Scenario: Invalid LaTeX
- **WHEN** a user enters LaTeX that fails to parse
- **THEN** the editor SHALL show an inline error without losing the source

### Requirement: Table blocks
The editor SHALL support editable `table` blocks with add/remove row and column
operations, and cells that may contain rich text (inline emphasis and math via
the same inline renderer as paragraphs).

#### Scenario: Add a column
- **WHEN** a user adds a column to a table
- **THEN** every row SHALL gain a cell in the new column position

#### Scenario: A cell renders inline rich text
- **WHEN** a cell holds `**bold**` or `$x^2$` and is not being edited
- **THEN** the editor SHALL render the emphasis or math
- **AND** SHALL restore the raw source when the cell is focused

#### Scenario: Tables from ingested tabular data
- **WHEN** the AI agent ingests a CSV or Excel sheet into the document
- **THEN** the system SHALL produce a `table` block whose rows and columns match
  the source sheet
