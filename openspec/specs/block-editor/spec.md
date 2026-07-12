# block-editor Specification

## Purpose

Block-based editing: text families, slash menu, Markdown shortcuts, and the technical blocks (code, LaTeX, Mermaid, tables).
## Requirements
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

### Requirement: Heading levels
The editor SHALL support four heading levels (H1–H4), each rendered at a
visually distinct size so the document hierarchy reads at a glance. Typing a
markdown heading prefix at the start of a block SHALL set the level from the
number of `#` characters: `#`→H1, `##`→H2, `###`→H3, `####`→H4. A heading whose
stored level exceeds the supported range SHALL be clamped to the nearest
supported level rather than rendered at the base size.

#### Scenario: Markdown prefix sets the heading level
- **WHEN** a user types `###` followed by a space at the start of a block
- **THEN** the block SHALL become a heading at level 3
- **AND** it SHALL render at that level's distinct size

#### Scenario: Four distinct sizes
- **WHEN** headings of levels 1 through 4 appear in a document
- **THEN** each SHALL render at a different size, largest for H1 and smallest
  for H4

### Requirement: LaTeX math blocks
The editor SHALL support LaTeX for both inline math (delimited by `$…$` or by
the TeX delimiters `\(…\)` and `\[…\]` within text) and block-level math (the
`latex` block), rendering both via KaTeX. It SHALL preserve the raw source for
editing and show a non-destructive error on invalid LaTeX.

#### Scenario: Render a block equation
- **WHEN** a user enters a valid LaTeX expression in a `latex` block
- **THEN** the editor SHALL render the typeset equation
- **AND** SHALL preserve the raw LaTeX source for editing

#### Scenario: Render inline math within text
- **WHEN** a paragraph contains a `$…$` fragment and is not being edited
- **THEN** the editor SHALL render that fragment as typeset inline math
- **AND** SHALL restore the raw `$…$` source when the paragraph is focused

#### Scenario: Render TeX-delimited inline math
- **WHEN** a paragraph contains `\(…\)` or `\[…\]` and is not being edited
- **THEN** the editor SHALL render that fragment as typeset inline math

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

### Requirement: Markdown-style shortcuts
The editor SHALL support Markdown-style input shortcuts (e.g. `#` for heading,
`-` for a list item, ``` for a code block).

#### Scenario: Heading shortcut
- **WHEN** a user types `# ` at the start of a block
- **THEN** the block SHALL become a level-1 heading

### Requirement: Image blocks
The editor SHALL provide an image block that renders an image from a URL. An
empty image block SHALL let the user either paste an image URL or upload an image
file; an uploaded image SHALL be stored and referenced by its served URL rather
than embedded in the document. The block SHALL support alt text.

#### Scenario: Render an image from a URL
- **WHEN** a user sets an image block's URL to an image address
- **THEN** the block SHALL display that image

#### Scenario: Upload an image into a block
- **WHEN** a user uploads an image into an empty image block
- **THEN** the image SHALL be stored and the block SHALL display it by its
  served URL

### Requirement: Embed blocks
The editor SHALL provide an embed block that renders a media URL. YouTube,
Vimeo, and Loom links SHALL render as embedded players; any other `https` URL
SHALL render in a sandboxed iframe with a fallback link to open it directly.
Non-`https` URLs SHALL NOT be embedded.

#### Scenario: Embed a YouTube video
- **WHEN** a user sets an embed block's URL to a YouTube link
- **THEN** the block SHALL render the YouTube player for that video

#### Scenario: Embed an arbitrary https page
- **WHEN** a user sets an embed block's URL to an https URL that is not a known
  provider
- **THEN** the block SHALL render it in a sandboxed iframe with a link to open it

#### Scenario: Refuse a non-https URL
- **WHEN** a user sets an embed block's URL to a non-`https` URL
- **THEN** the block SHALL NOT embed it

