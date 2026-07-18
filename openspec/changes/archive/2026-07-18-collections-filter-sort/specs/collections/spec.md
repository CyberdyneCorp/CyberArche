# collections Specification

## ADDED Requirements

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
