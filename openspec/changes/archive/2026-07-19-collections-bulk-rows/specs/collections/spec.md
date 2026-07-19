# collections Specification

## ADDED Requirements

### Requirement: Bulk row actions

The system SHALL let a member act on multiple rows of a collection at once: to
delete the selected rows, and to set one property's value across all selected
rows. Each affected row SHALL be permission-checked individually and MUST belong
to the collection; ids that are not rows of the collection SHALL be skipped.
Setting a value in bulk SHALL obey the same rules as a single-row edit, including
rejecting writes to read-only (formula or rollup) properties. The system SHALL
report how many rows were changed.

#### Scenario: Delete selected rows

- **GIVEN** a collection with several rows
- **WHEN** a member selects some and deletes them
- **THEN** those rows SHALL be removed and the count deleted SHALL be reported

#### Scenario: Set a property across selected rows

- **WHEN** a member sets a property value on the selected rows
- **THEN** each selected row SHALL take that value

#### Scenario: Read-only properties reject bulk writes

- **WHEN** a member bulk-sets a formula or rollup property
- **THEN** the system SHALL reject the write
