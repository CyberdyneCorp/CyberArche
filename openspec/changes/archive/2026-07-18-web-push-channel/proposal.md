# Web-push notification channel (VAPID)

## Why

The "Push notifications" preference toggle exists but is inert — there is no
push delivery channel, so turning it on does nothing. A standard Web Push
(VAPID / RFC 8291) channel makes the toggle real: users get browser
notifications for mentions and agent results even when the tab is closed.

## What Changes

- Store per-user browser push subscriptions (endpoint + keys), created/removed
  by the browser when the user enables/disables the toggle. New table + repo +
  endpoints (`GET /push/vapid-public-key`, `POST`/`DELETE /push/subscriptions`).
- Add a `NotificationChannelPort` adapter (`channel = "push"`) that encrypts and
  delivers a notification to each of the recipient's subscriptions via VAPID,
  pruning subscriptions the browser has expired (404/410). Built only when VAPID
  keys are configured.
- Frontend: a service worker that renders push events, and subscribe/unsubscribe
  wired to the existing push toggle.

## Impact

- Affected specs: `notifications`.
- Affected code: `domain` (PushSubscription); a push-subscription port + use
  case; in-memory + postgres repos; migration; the web-push channel adapter
  (new `pywebpush` dependency, run off the event loop); push router; wiring +
  config; a service worker + push client + prefs-toggle wiring. Data-model +
  credential-bearing change → OpenSpec-tracked.
