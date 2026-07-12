# Tasks

## 1. Notifications store + use case
- [x] 1.1 Migration `0010_notifications.sql` (id, tenant, recipient, kind, actor, document_id, comment_id, snippet, read, created_at) + RLS
- [x] 1.2 `Notification` domain value
- [x] 1.3 `NotificationRepository` port (add, list_for_user, unread_count, mark_read, mark_all_read) + in-memory + Postgres adapters
- [x] 1.4 `NotificationUseCases` (list, unread_count, mark_read, mark_all_read — own notifications only)
- [x] 1.5 Wire into container

## 2. @mentions in comments
- [x] 2.1 `SharingUseCases.add_comment` parses `@[id]`, notifies each mentioned workspace member (not the author)
- [x] 2.2 Tests: a mention notifies the member; self-mention and non-member are ignored

## 3. HTTP
- [x] 3.1 GET /notifications, GET /notifications/unread-count, POST /notifications/{id}/read, POST /notifications/read-all

## 4. Frontend
- [x] 4.1 `api/notifications`; notifications view-model (list, unread count, poll, mark read/all)
- [x] 4.2 Notifications bell + unread badge + dropdown inbox (open doc + mark read)
- [x] 4.3 Comment composer: `@` autocomplete from members → insert `@[id]`; render mention chips

## 5. Validate
- [x] 5.1 `openspec validate mentions-and-notifications --strict`; backend + import-linter; web typecheck + build
