# collections Specification

## ADDED Requirements

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
