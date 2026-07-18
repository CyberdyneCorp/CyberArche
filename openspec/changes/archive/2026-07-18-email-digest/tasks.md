# Tasks
- [ ] 1.1 `NotificationPreferences`: add `email` + `last_digest_at`; capture email on update (preserve last_digest_at)
- [ ] 1.2 Ports: `NotificationRepository.unread_since`; prefs repo `list_email_recipients` + `mark_digested`
- [ ] 1.3 `NotificationDigestUseCases.run_due(now)`: per-user cadence, aggregate unread-since-last-digest, deliver via channels with recipient_email, mark digested; skip when nothing unread
- [ ] 1.4 In-memory + postgres repos implement the new methods; migration `0018_notification_digest.sql` (email, last_digest_at columns)
- [ ] 1.5 Wiring/config/bootstrap: `enable_digest`, `digest_interval_seconds`; build digest use case; schedule the loop (postgres only)
- [ ] 1.6 Tests: aggregation + recipient_email, cadence skip, empty-skip, email captured (last_digest_at preserved), email-enabled-only, channel gating
- [ ] 1.7 `openspec validate email-digest --strict`; gates green; docs updated
