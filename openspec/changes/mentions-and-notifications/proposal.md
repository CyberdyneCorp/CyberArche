# @mentions and notifications

## Why

CyberArche has comments and teamspace membership, but no way to pull a teammate
into a discussion or tell them something happened. `@mentioning` a member in a
comment should notify them, and every user needs an inbox of their
notifications. This closes the core collaboration loop with the smallest lift.

## What Changes

- Add a **notifications** capability: a per-user inbox of notifications, each
  with a kind, the actor, the source document, a snippet, and a read flag.
  Endpoints to list, count unread, mark one read, and mark all read.
- **@mentions in comments**: when a comment body contains `@[user-id]` for a user
  who is a member of the document's workspace, that user receives a `mention`
  notification (never the author themselves). Mentions are stored in the comment
  body as `@[user-id]` tokens.
- Frontend: a **notifications bell** with an unread badge and a dropdown inbox
  (click a notification to open its document and mark it read; "mark all read").
  The comment composer gets an `@` autocomplete of members and renders mention
  tokens as chips.

## Impact

- New capability spec: `notifications`. Also `permissions-sharing` (a comment
  with mentions notifies the mentioned members).
- Data model: new `notifications` table (migration `0010_notifications.sql`).
- Affected code: `Notification` domain + `NotificationRepository` (in-memory +
  Postgres) + `NotificationUseCases`; `SharingUseCases.add_comment` creates
  mention notifications; new notifications router; wiring. Web: `api/notifications`,
  a notifications view-model, a bell/inbox component, comment `@` autocomplete.
- Access: a user only ever sees their own notifications; mentions only notify
  members of the document's workspace, so mentioning can't reach outsiders.
