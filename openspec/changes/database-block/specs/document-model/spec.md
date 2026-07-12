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
