# collections Specification

## ADDED Requirements

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
