# collections Specification

## Purpose
TBD - created by archiving change collections-foundation. Update Purpose after archive.
## Requirements
### Requirement: Collection with property schema

The system SHALL let a member create a collection within a workspace. A
collection SHALL have a name and a property schema: an ordered list of property
definitions, each with a name and a type (text, number, single-select,
multi-select, date, checkbox, or url); select and multi-select properties SHALL
carry their allowed options. A member with edit access SHALL be able to add,
rename, retype, and remove properties; reading a collection SHALL require view
access to its workspace. Collections SHALL be scoped to the caller's tenant.

#### Scenario: Create a collection and edit its schema

- **GIVEN** a member with edit access to a workspace
- **WHEN** they create a collection and add a single-select property with options
- **THEN** the collection SHALL persist with that property in its schema

#### Scenario: Reading requires access

- **WHEN** a caller without view access to the workspace requests a collection
- **THEN** the system SHALL refuse the request

### Requirement: Rows are documents with property values

Each row of a collection SHALL be a document that belongs to the collection and
carries a value for each schema property. Adding a row SHALL create a member
document (with its own blocks, comments, and permissions); setting a row's
property value SHALL update that document's stored properties; removing a row
SHALL remove the document from the collection. A row document SHALL be openable
and editable like any other document.

#### Scenario: Add and edit a row

- **GIVEN** a collection with a schema
- **WHEN** a member adds a row and sets its property values
- **THEN** a document SHALL be created as a member of the collection with those
  property values
- **AND** the document SHALL be openable as a normal page

### Requirement: Named views over a collection

A collection SHALL have one or more named views. A view SHALL have a kind (table,
board, gallery, or calendar) and MAY carry filters, sorts, a group-by property,
and a date property. Querying a view SHALL return the collection's rows with the
view's filters applied and then its sorts applied. A newly created collection
SHALL have a default table view.

#### Scenario: Query the table view

- **GIVEN** a collection with rows and a table view
- **WHEN** a member queries that view
- **THEN** the system SHALL return the rows with the view's filters and sorts
  applied

#### Scenario: Default view

- **WHEN** a collection is created
- **THEN** it SHALL have a default table view

### Requirement: Interactive filter and sort controls

The collection surface SHALL let a member edit the current view's filters and
sorts. Members SHALL be able to add, change, and remove filter rules — each a
property, an operator appropriate to that property's type, and a value — and add,
remove, and reorder sort rules (a property and a direction). Edits SHALL persist
to the view and the displayed rows SHALL update to reflect the view's filters
applied then its sorts applied. The surface SHALL indicate how many filters and
sorts are active.

#### Scenario: Filter a view

- **GIVEN** a member viewing a collection
- **WHEN** they add a filter rule on a property
- **THEN** the rule SHALL persist to the view and only matching rows SHALL show

#### Scenario: Sort a view

- **WHEN** a member adds a sort on a property
- **THEN** the sort SHALL persist and the rows SHALL be ordered by it

#### Scenario: Operators match the property type

- **WHEN** a member adds a filter on a checkbox versus a text property
- **THEN** the offered operators SHALL be appropriate to that property's type

### Requirement: Board view

A collection SHALL offer a Board (kanban) view that groups its rows into columns
by a chosen single-select property. There SHALL be a column per option of that
property plus a column for rows with no value. Each card SHALL show the row's
title and its property values. Moving a card to another column SHALL set the
row's grouping property to that column's value. The Board view SHALL honor the
view's active filters and sorts.

#### Scenario: Group rows on a board

- **GIVEN** a collection with a single-select property and rows
- **WHEN** a member views it as a Board grouped by that property
- **THEN** rows SHALL appear in the column matching their value, and rows with no
  value SHALL appear in the uncategorized column

#### Scenario: Move a card

- **WHEN** a member moves a card to another column
- **THEN** the row's grouping property SHALL be set to that column's value

### Requirement: Gallery view

A collection SHALL offer a Gallery view that presents its rows as a grid of
cards, each showing the row's title and property values, honoring the view's
active filters and sorts.

#### Scenario: Show rows as a gallery

- **GIVEN** a collection with rows
- **WHEN** a member views it as a Gallery
- **THEN** the rows SHALL be presented as a grid of cards

