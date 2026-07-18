# notifications Specification

## ADDED Requirements

### Requirement: Email digest of unread notifications

The system SHALL provide a scheduled digest that delivers a user's unread
notifications by email. For each user who has enabled email delivery, the digest
SHALL aggregate the notifications that are still unread and were created after
that user's previous digest into a single summary, and deliver it through the
deployment's configured notification channel(s) for which the user's preferences
are enabled, addressed to the email captured from the user's verified token
claims. The digest SHALL NOT be sent when the user has no qualifying unread
notifications, SHALL respect a per-user minimum interval between digests, and
SHALL record when a digest was last sent so the same notifications are not
included twice. The digest SHALL NOT alter the read state of the in-app inbox.

#### Scenario: Digest aggregates unread notifications

- **GIVEN** a user with email delivery enabled and several unread notifications
- **WHEN** the digest runs and the per-user interval has elapsed
- **THEN** the system SHALL deliver one summary of those notifications to the
  user's email through an enabled channel
- **AND** SHALL record the digest time so those notifications are not resent

#### Scenario: Nothing to send

- **GIVEN** a user with email delivery enabled and no unread notifications newer
  than their last digest
- **WHEN** the digest runs
- **THEN** the system SHALL NOT deliver a digest to that user

#### Scenario: Email captured from preferences

- **WHEN** a user saves their notification preferences
- **THEN** the system SHALL record the email from their verified token claims so
  the digest can reach them
