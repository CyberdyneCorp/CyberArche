# Tasks
- [ ] 1.1 Domain: `PropertyDef.reminder_minutes` (-1 = off); fire-time = date − lead
- [ ] 1.2 CollectionRepository.list_all (cross-tenant, background sweep); ReminderStateRepository (was_reminded/mark_reminded) in-memory + postgres; migration 0021
- [ ] 1.3 CollectionReminderUseCases.run_due(now): due rows → notify creator once (kind "reminder") via the dispatcher; record reminded
- [ ] 1.4 Wiring + bootstrap scheduler loop (postgres only) + enable_reminders/interval settings; postgres (de)serialization of reminder_minutes
- [ ] 1.5 Frontend: reminder lead-time control on the date property (add/edit)
- [ ] 1.6 Tests: fire-time due logic, notify-once + re-arm on date change, recipient = creator, only reminder-enabled date props, no fire before lead; postgres round-trip; frontend
- [ ] 1.7 `openspec validate collections-reminders --strict`; gates green
