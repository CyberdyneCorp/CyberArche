# Notification channels + preferences

## Why

Notifications are in-app inbox only. There's no way to get them by email/push,
and no per-user control over what you're notified about. This adds notification
preferences and a delivery mechanism that fans a notification out to the
recipient's enabled, configured channels — without changing the in-app inbox.

## What Changes

- **Preferences** (per user): toggles for in-app (always on), email, push, and
  which kinds (mentions/comments, agent task results). Migration 0017 adds a
  `notification_preferences` table; get/update use case + endpoints; settings UI.
- **Delivery dispatch**: a `NotificationDispatcher` that stores every
  notification (in-app) and then, per the recipient's prefs, sends it via a
  `NotificationChannelPort`. Channel adapters (webhook/Slack, email) are built
  only when configured (empty config = disabled), so today's behaviour
  (in-app only) is unchanged until an operator configures a channel.
- The mention and agent-result notification sites store via the dispatcher
  instead of the raw repository, so delivery happens automatically.

## Impact

- Affected specs: `notifications`.
- Affected code: `domain/notifications.py` (preferences), a
  `NotificationChannelPort`, a `NotificationDispatcher`, prefs use case + repo +
  `db/migrations/0017_notification_preferences.sql`, wiring, a prefs router;
  sharing + scheduled-agents dispatch through it. Frontend: a Notifications
  settings section with the toggles + viewmodel + api client.
