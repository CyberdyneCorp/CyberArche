# Email digest for unread notifications

## Why

The `email_enabled` preference and the outbound notification channel port both
exist, but nothing ever aggregates a user's unread notifications into a periodic
email. Per-notification email would be noisy; a scheduled digest is the useful
delivery. All the plumbing (prefs, channel port, in-process scheduler) is
already shipped — this wires it together.

## What Changes

- Capture the user's email on their preferences (from their verified token
  claims) when they save preferences, so a background job can reach them —
  there is no user directory to look it up otherwise.
- Add a scheduled digest that, per email-enabled user, aggregates the
  notifications that are still unread and newer than their last digest, and
  delivers a single summary through the configured notification channel(s),
  respecting per-user cadence. Nothing is sent when there is nothing unread.
- Run it from the existing in-process scheduler (postgres deployment only),
  gated by a new `enable_digest` / `digest_interval_seconds` setting.

## Impact

- Affected specs: `notifications`.
- Affected code: `domain/notifications.py` (email, last_digest_at on prefs);
  notification ports (`unread_since`, `list_email_recipients`, `mark_digested`);
  `use_cases/notifications.py` (capture email; new digest use case); in-memory +
  postgres repos; migration `0018`; wiring + config + bootstrap scheduler.
