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

### Requirement: Notification preferences

Each user SHALL have notification preferences controlling which channels
(in-app, email, push) and which kinds of notification they receive. In-app
notifications SHALL always be stored. Preferences SHALL default to in-app plus
mentions enabled, and SHALL be readable and updatable by the owning user only,
scoped to the caller's tenant.

#### Scenario: Default preferences

- **WHEN** a user has never set preferences
- **THEN** the system SHALL treat in-app and mention notifications as enabled

#### Scenario: Update preferences

- **WHEN** a user enables or disables a channel or kind
- **THEN** the setting SHALL persist and apply to future notifications

### Requirement: Multi-channel delivery

When a notification is created, the system SHALL always store it for the in-app
inbox and SHALL additionally deliver it to each of the recipient's enabled
channels that is configured on the deployment. A channel that is not configured
SHALL be a no-op. Delivery SHALL respect the recipient's per-kind preferences.

#### Scenario: In-app always stored

- **WHEN** a notification is created
- **THEN** it SHALL be stored for the recipient's in-app inbox regardless of
  channel configuration

#### Scenario: Deliver to an enabled, configured channel

- **GIVEN** a recipient who enabled a channel that is configured on the deployment
- **WHEN** a notification of an enabled kind is created for them
- **THEN** the system SHALL deliver it through that channel

#### Scenario: Disabled or unconfigured channel is skipped

- **WHEN** the recipient disabled a channel, or the channel is not configured
- **THEN** the system SHALL NOT attempt delivery on that channel, and SHALL not fail

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

### Requirement: Web-push delivery channel

The system SHALL support delivering notifications to a user's browsers via Web
Push (VAPID). A user SHALL be able to register and remove a browser push
subscription, scoped to themselves; subscriptions SHALL be private to the owning
user and tenant. When the push channel is configured and a user has push
delivery enabled, the dispatcher SHALL deliver eligible notifications to each of
that user's registered subscriptions as an encrypted Web Push message. A
subscription that the browser reports as expired or gone SHALL be removed. The
push channel SHALL be present only when the deployment configures VAPID keys; a
delivery failure SHALL NOT break the in-app store.

#### Scenario: Deliver to a subscribed browser

- **GIVEN** a user with push enabled and a registered subscription, on a
  deployment with VAPID configured
- **WHEN** a notification is dispatched to that user
- **THEN** the system SHALL send an encrypted Web Push message to that
  subscription

#### Scenario: Expired subscription is pruned

- **WHEN** a push send reports the subscription as gone (HTTP 404/410)
- **THEN** the system SHALL remove that subscription and SHALL NOT retry it

#### Scenario: Subscriptions are private

- **WHEN** a user registers or removes a push subscription
- **THEN** it SHALL affect only that user's own subscriptions within their tenant

