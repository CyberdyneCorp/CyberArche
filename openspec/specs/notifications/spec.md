# notifications Specification

## Purpose
TBD - created by archiving change mentions-and-notifications. Update Purpose after archive.
## Requirements
### Requirement: Per-user notification inbox

The system SHALL keep a per-user inbox of notifications. Each notification SHALL
record its kind, the acting user, the source document, a short snippet, whether
it has been read, and when it was created. A user SHALL be able to list their
notifications, see how many are unread, mark one read, and mark all read. A user
SHALL only ever see and modify their own notifications.

#### Scenario: Read and clear notifications

- **GIVEN** a user has unread notifications
- **WHEN** they list notifications and mark one read
- **THEN** that notification SHALL be marked read
- **AND** the unread count SHALL decrease

#### Scenario: Notifications are private

- **WHEN** a user requests notifications
- **THEN** only that user's own notifications SHALL be returned

