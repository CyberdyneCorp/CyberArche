# notifications Specification

## ADDED Requirements

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
