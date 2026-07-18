# notifications Specification

## ADDED Requirements

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
