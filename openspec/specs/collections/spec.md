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

### Requirement: Calendar view

A collection SHALL offer a Calendar view that lays its rows out on a month grid
by a chosen date property. Each row SHALL appear on the day its date property
falls on; rows whose date property is missing or unparseable SHALL be reported as
unscheduled rather than placed. The view SHALL allow navigating between months
and SHALL honor the view's active filters and sorts. Selecting a row SHALL open
it as its page.

#### Scenario: Place rows on the calendar

- **GIVEN** a collection with a date property and rows carrying dates
- **WHEN** a member views it as a Calendar for the month
- **THEN** each row SHALL appear on the day matching its date
- **AND** rows with no valid date SHALL be reported as unscheduled

#### Scenario: Navigate months

- **WHEN** a member moves to the next or previous month
- **THEN** the grid SHALL show that month and place its rows accordingly

### Requirement: Formula properties

The system SHALL support formula properties: a read-only column whose value is
computed from an expression over the row's other properties. The system SHALL
evaluate a formula from the row's non-formula property values and its title, and
SHALL include the computed value in a view's rows so it can be displayed,
filtered, and sorted like any other column. A formula property's value SHALL NOT
be directly editable. The expression language SHALL support arithmetic,
comparison, and boolean operations, a conditional, a bounded set of functions,
`prop("Name")` to reference another property's value, and the current time; it
SHALL be evaluated safely without executing arbitrary code. An invalid
expression SHALL be rejected when the property is created or edited.

#### Scenario: Compute a formula column

- **GIVEN** a collection with a number property and a formula property that
  references it
- **WHEN** a member queries a view
- **THEN** each row SHALL include the formula's computed value

#### Scenario: Formula values are read-only

- **WHEN** a member attempts to set a value on a formula property
- **THEN** the system SHALL reject the write

#### Scenario: Invalid expressions are rejected

- **WHEN** a member creates a formula property with an unparseable or unsafe
  expression
- **THEN** the system SHALL reject it

### Requirement: Relation properties

The system SHALL support relation properties: a property whose value is a set of
links from a row to rows of a target collection. Setting a relation SHALL accept
only links to rows that belong to the target collection within the caller's
tenant, and SHALL ignore or reject others. A row-query result SHALL include the
id and title of every linked row so the client can display relations by title.
The system SHALL provide the rows of a collection (id and title) so a member can
choose which rows to link.

#### Scenario: Link rows across collections

- **GIVEN** two collections and a relation property targeting the second
- **WHEN** a member sets a row's relation to rows of the second collection
- **THEN** the links SHALL be stored and the linked rows' titles SHALL be
  available when the view is queried

#### Scenario: Only valid links are accepted

- **WHEN** a member sets a relation to a row that is not in the target collection
- **THEN** the system SHALL not store that link

### Requirement: Rollup properties

The system SHALL support rollup properties: a read-only column that aggregates a
chosen property of the rows reached through a relation property, using a function
that is one of count, sum, average, minimum, maximum, earliest, latest, or list.
The rollup value SHALL be computed from the current linked rows when a view is
queried, and SHALL NOT be directly editable. A rollup SHALL be configured with
the relation property to follow, the target property to aggregate, and the
function.

#### Scenario: Roll up related values

- **GIVEN** a relation property and a rollup that counts the linked rows
- **WHEN** a member queries a view
- **THEN** each row SHALL include the rollup's computed aggregate over its linked
  rows

#### Scenario: Rollup values are read-only

- **WHEN** a member attempts to set a value on a rollup property
- **THEN** the system SHALL reject the write

### Requirement: Date property reminders

The system SHALL let a date property carry a reminder lead time. When a row's
date value, minus that lead time, is reached, the system SHALL send a
notification to the row's creator through the notification dispatcher, and SHALL
do so at most once for a given row, property, and date value — changing the date
SHALL re-arm the reminder. Reminders SHALL be evaluated by a scheduled sweep on
the deployment that runs background jobs, and SHALL apply only to date
properties for which a reminder lead time is set.

#### Scenario: Remind when a date arrives

- **GIVEN** a row with a date property whose reminder lead time has elapsed
- **WHEN** the reminder sweep runs
- **THEN** the system SHALL notify the row's creator once

#### Scenario: Not reminded twice

- **WHEN** the sweep runs again for a row already reminded for that date value
- **THEN** the system SHALL NOT send another notification

#### Scenario: Changing the date re-arms it

- **GIVEN** a row already reminded for a date value
- **WHEN** its date is changed and that new date's reminder time is reached
- **THEN** the system SHALL notify again for the new value

