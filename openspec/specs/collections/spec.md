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

