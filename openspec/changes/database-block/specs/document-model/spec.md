# document-model Specification

## ADDED Requirements

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
