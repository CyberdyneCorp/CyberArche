# Tasks
- [x] 1.1 NotificationPreferences (domain + migration 0017 + postgres repo + fake); defaults (in-app + mentions on)
- [x] 1.2 NotificationChannelPort + a config-gated webhook adapter (no-op when unset); dispatcher stores + delivers per prefs
- [x] 1.3 Route the mention + agent-result notification sites through the dispatcher
- [x] 1.4 Prefs use case + GET/PUT endpoints
- [x] 1.5 Frontend: Notifications settings section (push/email/mentions toggles) + viewmodel + api client
- [x] 1.6 Tests: prefs default + update; dispatch stores in-app always; a disabled channel/kind isn't delivered; unconfigured channel is a no-op; frontend viewmodel
- [x] 1.7 `openspec validate notification-channels --strict`; backend + frontend gates green
