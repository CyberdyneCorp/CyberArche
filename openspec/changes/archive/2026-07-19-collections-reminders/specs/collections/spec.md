# collections Specification

## ADDED Requirements

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
