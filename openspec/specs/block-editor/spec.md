# block-editor Specification

## Purpose

Block-based editing: text families, slash menu, Markdown shortcuts, and the technical blocks (code, LaTeX, Mermaid, tables).

## Requirements

### Requirement: Block editing with slash menu
The editor SHALL let a user insert, edit, move, split, merge, and delete blocks,
and SHALL provide a slash (`/`) command menu to insert any supported block type
at the cursor.

#### Scenario: Insert a block via slash menu
- **WHEN** a user types `/` and selects a block type
- **THEN** the editor SHALL insert a block of that type at the cursor
- **AND** the change SHALL be applied to the document CRDT

#### Scenario: Split a paragraph on Enter
- **WHEN** a user presses Enter in the middle of a paragraph block
- **THEN** the editor SHALL split it into two blocks preserving both fragments

### Requirement: LaTeX math blocks
The editor SHALL support LaTeX for both inline math and block-level math, and
SHALL render it (via KaTeX) live as the user edits.

#### Scenario: Render a block equation
- **WHEN** a user enters a valid LaTeX expression in a `latex` block
- **THEN** the editor SHALL render the typeset equation
- **AND** SHALL preserve the raw LaTeX source for editing

#### Scenario: Invalid LaTeX
- **WHEN** a user enters LaTeX that fails to parse
- **THEN** the editor SHALL show an inline error without losing the source

### Requirement: Mermaid diagram blocks
The editor SHALL support `mermaid` blocks that render Mermaid source to a diagram
and preserve the editable source.

#### Scenario: Render a flowchart
- **WHEN** a user enters valid Mermaid source
- **THEN** the editor SHALL render the diagram and keep the source editable

#### Scenario: Mermaid parse error
- **WHEN** the Mermaid source is invalid
- **THEN** the editor SHALL display the parser error and retain the source

### Requirement: Code blocks
The editor SHALL support `code` blocks with a selectable language and syntax
highlighting.

#### Scenario: Highlight by language
- **WHEN** a user sets a code block's language
- **THEN** the editor SHALL apply syntax highlighting for that language

### Requirement: Table blocks
The editor SHALL support editable `table` blocks with add/remove row and column
operations, and cells that may contain rich text.

#### Scenario: Add a column
- **WHEN** a user adds a column to a table
- **THEN** every row SHALL gain a cell in the new column position

#### Scenario: Tables from ingested tabular data
- **WHEN** the AI agent ingests a CSV or Excel sheet into the document
- **THEN** the system SHALL produce a `table` block whose rows and columns match
  the source sheet

### Requirement: Markdown-style shortcuts
The editor SHALL support Markdown-style input shortcuts (e.g. `#` for heading,
`-` for a list item, ``` for a code block).

#### Scenario: Heading shortcut
- **WHEN** a user types `# ` at the start of a block
- **THEN** the block SHALL become a level-1 heading
