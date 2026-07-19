# collections Specification

## ADDED Requirements

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
